"""
Live direction-of-arrival tracker for a single stereo mic node.

This mirrors the behaviour of the Blazor debug demo: it runs GCC-PHAT
on a rolling window of stereo audio, but only *accepts* a new estimate
when there's real signal (RMS gate) and the correlation peak is sharp
(confidence gate). Accepted estimates are smoothed with an exponential
moving average; when nothing passes the gate the last good direction is
held instead of jumping to noise.

Why gate + smooth?
    The raw cross-correlation produces an estimate on every window,
    including on silence — where the peak is essentially random. Without
    gating, the reported angle flails between words. The gate suppresses
    that; the EMA removes residual jitter on real signal.

Usage
-----
    import vibrationbelt as vb

    with vb.DirectionTracker("10.8.5.177", baseline_m=0.20) as doa:
        for fix in doa:
            if fix.live:
                print(f"{fix.angle_deg:+6.1f}°  {fix.hint}  conf={fix.confidence:.2f}")

Or poll the latest fix from your own loop:

    doa = vb.DirectionTracker("10.8.5.177", baseline_m=0.20).start()
    ...
    fix = doa.current        # most recent DirectionFix (or None)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator, Optional

import numpy as np

from .stream import MicStream, SAMPLE_RATE, CHANNELS, DEFAULT_PORT
from .doa import gcc_phat, tdoa_to_angle, SPEED_OF_SOUND

__all__ = ["DirectionTracker", "DirectionFix"]


@dataclass(frozen=True)
class DirectionFix:
    """One direction estimate.

    angle_deg
        Smoothed, broadside-referenced angle in [-90, +90].
        0° = source straight ahead, negative = toward the LEFT mic
        (channel 0), positive = toward the RIGHT mic (channel 1).
    raw_angle_deg
        The latest *unsmoothed* angle (useful for debugging / plotting).
    tdoa_us
        Inter-mic time-of-arrival difference in microseconds.
    confidence
        GCC-PHAT peak sharpness in [0, 1].
    live
        True if this fix was just updated from real signal; False if the
        tracker is holding the last good fix because the input is quiet
        or ambiguous.
    hint
        "LEFT" / "CENTER" / "RIGHT" convenience label.
    left_rms, right_rms
        Per-channel RMS over the analysis window.
    timestamp_us
        Receiver-side arrival time (microseconds, time.monotonic-based) of
        the most recent packet in the window.
    """
    angle_deg: float
    raw_angle_deg: float
    tdoa_us: float
    confidence: float
    live: bool
    hint: str
    left_rms: float
    right_rms: float
    timestamp_us: int


class DirectionTracker:
    """Wraps a stereo :class:`MicStream` and produces smoothed DoA fixes.

    Parameters
    ----------
    ip, port
        ESP32 mic node address.
    baseline_m
        Physical distance between the two mics, in metres. This sets the
        TDoA→angle scale and bounds the correlation search window.
    window_ms
        Length of the rolling analysis window. Longer = more stable but
        laggier and worse at localising short transients. 64 ms is a good
        default at 8 kHz (512 samples).
    min_rms
        Signal floor (post-gain). Below this on both channels the input is
        treated as silence and the fix is held. Raise if it twitches on
        room noise.
    min_conf
        Minimum GCC-PHAT confidence to accept an estimate.
    ema
        Smoothing factor in (0, 1]. Lower = steadier/slower, higher =
        snappier/jumpier. 0.30 matches the debug demo.
    hold_seconds
        How long a fix stays flagged ``live`` after the last accepted
        update before it decays to held.
    """

    def __init__(self, ip: str, port: int = DEFAULT_PORT, *,
                 baseline_m: float = 0.20,
                 window_ms: float = 64.0,
                 min_rms: float = 1500.0,
                 min_conf: float = 0.55,
                 ema: float = 0.30,
                 hold_seconds: float = 1.0,
                 sample_rate: int = SAMPLE_RATE):
        if CHANNELS != 2:
            raise RuntimeError(
                "DirectionTracker needs a stereo stream "
                "(vibrationbelt.CHANNELS must be 2)")
        self._stream = MicStream(ip, port=port, name=f"doa@{ip}")
        self._baseline = baseline_m
        self._sample_rate = sample_rate
        self._window_n = max(64, int(window_ms / 1000.0 * sample_rate))
        self._min_rms = min_rms
        self._min_conf = min_conf
        self._ema = ema
        self._hold_seconds = hold_seconds
        # +10% margin on the physical max delay bounds the search window
        # and rejects reflections arriving from outside the array geometry.
        self._max_delay_s = baseline_m / SPEED_OF_SOUND * 1.1

        # Rolling stereo window (window_n, 2).
        self._window = np.zeros((self._window_n, 2), dtype=np.int16)

        # Smoother / hold state.
        self._display_angle = 0.0
        self._have_fix = False
        self._last_fix_monotonic = 0.0
        self._current: Optional[DirectionFix] = None

    # ─── lifecycle ─────────────────────────────────────────────────────

    def start(self) -> "DirectionTracker":
        self._stream.start()
        return self

    def close(self) -> None:
        self._stream.close()

    def __enter__(self) -> "DirectionTracker":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # ─── reading ──────────────────────────────────────────────────────

    @property
    def current(self) -> Optional[DirectionFix]:
        """The most recent :class:`DirectionFix`, or None before the first."""
        return self._current

    @property
    def dropped(self) -> int:
        """Packets dropped on the underlying stream (stream health)."""
        return self._stream.dropped

    def __iter__(self) -> Iterator[DirectionFix]:
        return self.iter_fixes()

    def iter_fixes(self, timeout: Optional[float] = None
                   ) -> Iterator[DirectionFix]:
        """Yield a :class:`DirectionFix` for every incoming audio packet."""
        for chunk in self._stream.iter_chunks(timeout=timeout):
            fix = self._ingest(chunk.samples, int(chunk.received_at * 1e6))
            if fix is not None:
                yield fix

    # ─── core ─────────────────────────────────────────────────────────

    def _ingest(self, samples: np.ndarray, t_us: int) -> Optional[DirectionFix]:
        """Push a new stereo block into the rolling window and re-estimate."""
        if samples.ndim != 2 or samples.shape[1] != 2:
            return None

        # Slide the window: drop the oldest n, append the new block.
        n = samples.shape[0]
        if n >= self._window_n:
            self._window = samples[-self._window_n:].copy()
        else:
            self._window = np.roll(self._window, -n, axis=0)
            self._window[-n:] = samples

        left  = self._window[:, 0]
        right = self._window[:, 1]
        l_rms = float(np.sqrt(np.mean(left.astype(np.float32) ** 2)))
        r_rms = float(np.sqrt(np.mean(right.astype(np.float32) ** 2)))

        tdoa_s, conf = gcc_phat(left, right, self._sample_rate,
                                max_delay_s=self._max_delay_s)
        raw_angle = tdoa_to_angle(tdoa_s, self._baseline)

        # Gate: accept only on real, unambiguous signal.
        loud_enough = max(l_rms, r_rms) >= self._min_rms
        accepted = loud_enough and conf >= self._min_conf
        if accepted:
            if not self._have_fix:
                self._display_angle = raw_angle
                self._have_fix = True
            else:
                self._display_angle += self._ema * (raw_angle - self._display_angle)
            self._last_fix_monotonic = time.monotonic()

        live = (self._have_fix and
                (time.monotonic() - self._last_fix_monotonic) < self._hold_seconds)

        angle = self._display_angle
        hint = "LEFT" if angle < -10 else "RIGHT" if angle > 10 else "CENTER"

        fix = DirectionFix(
            angle_deg=angle,
            raw_angle_deg=raw_angle,
            tdoa_us=tdoa_s * 1e6,
            confidence=conf,
            live=live,
            hint=hint,
            left_rms=l_rms,
            right_rms=r_rms,
            timestamp_us=t_us,
        )
        self._current = fix
        return fix
