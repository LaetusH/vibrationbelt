"""Multi-mic array: combine multiple `MicStream`s and detect events.

For sample-accurate DoA put both mics on one ESP32 with CHANNELS=2 and
just use `MicStream` directly. This module exists for the multi-ESP32
case (or when you want a unified API regardless of topology).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, Iterable, Optional, Tuple

import numpy as np

from .stream import MicStream, Chunk, SAMPLE_RATE, CHANNELS, DEFAULT_PORT

log = logging.getLogger("vibrationbelt")


@dataclass(frozen=True)
class MicSpec:
    """Describes a single mic node in an array."""
    ip: str
    port: int = DEFAULT_PORT
    position: Optional[Tuple[float, float]] = None   # (x, y) in metres


@dataclass
class Event:
    """A loud audio event observed simultaneously by multiple mics.

    samples
        Per-mic window of audio aligned in receiver wall-clock time.
        Equal length across mics.
    triggered_by
        Name of the mic whose RMS first crossed the threshold.
    timestamp
        ``time.monotonic()`` on the receiver at the moment of trigger.
    rms
        Per-mic RMS over the trigger window (post-DC-block).
    """
    samples: Dict[str, np.ndarray]
    triggered_by: str
    timestamp: float
    rms: Dict[str, float] = field(default_factory=dict)


class MicArray:
    """Combine N MicStreams behind a single context-managed object.

    Example
    -------
        array = MicArray({
            "left":  MicSpec("10.8.5.177", position=(-0.10, 0)),
            "right": MicSpec("10.8.5.178", position=( 0.10, 0)),
        })
        with array:
            for ev in array.events(threshold_rms=2000):
                ...

    Sync model
        We maintain a rolling time-aligned ring buffer per mic, indexed by
        the *receiver* wall-clock time of each packet (`Chunk.received_at`).
        For two-ESP32 setups this gives you only network-precision sync
        (~few ms). For sample-accurate sync put both mics on one ESP32 with
        multi-channel firmware.
    """

    def __init__(self, mics: Dict[str, MicSpec],
                 buffer_seconds: float = 2.0):
        if len(mics) < 1:
            raise ValueError("at least one mic required")
        self._specs = mics
        self._streams: Dict[str, MicStream] = {
            name: MicStream(spec.ip, spec.port, name=name)
            for name, spec in mics.items()
        }
        self._buffer_capacity = int(buffer_seconds * SAMPLE_RATE)
        # rolling buffer per mic: (samples ndarray, end_time wall-clock)
        self._buffers: Dict[str, deque] = {
            n: deque() for n in mics
        }
        self._buf_lock = threading.Lock()
        self._dispatch_threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    # ─── lifecycle ────────────────────────────────────────────────────

    def start(self) -> "MicArray":
        for s in self._streams.values():
            s.start()
        self._stop_event.clear()
        for name, s in self._streams.items():
            t = threading.Thread(
                target=self._consume_into_buffer,
                args=(name, s),
                daemon=True,
                name=f"vbelt-buf-{name}")
            t.start()
            self._dispatch_threads.append(t)
        return self

    def close(self) -> None:
        self._stop_event.set()
        for s in self._streams.values():
            s.close()
        for t in self._dispatch_threads:
            t.join(timeout=2.0)
        self._dispatch_threads.clear()

    def __enter__(self): return self.start()
    def __exit__(self, *exc): self.close()

    # ─── public helpers ───────────────────────────────────────────────

    @property
    def mic_names(self) -> list[str]:
        return list(self._specs.keys())

    @property
    def specs(self) -> Dict[str, MicSpec]:
        return dict(self._specs)

    def baseline_m(self, a: str, b: str) -> float:
        """Geometric distance in meters between mic `a` and mic `b`."""
        pa = self._specs[a].position
        pb = self._specs[b].position
        if pa is None or pb is None:
            raise ValueError("both mics must have positions configured")
        return float(np.hypot(pa[0] - pb[0], pa[1] - pb[1]))

    def latest_window(self, seconds: float
                      ) -> Optional[Dict[str, np.ndarray]]:
        """Snapshot the most recent `seconds` of audio from every mic.

        Returns None if any mic doesn't have enough buffered audio yet.
        The arrays are equal-length across mics and zero-padded on the
        front if a mic was recently silent.
        """
        n = int(seconds * SAMPLE_RATE)
        out: Dict[str, np.ndarray] = {}
        with self._buf_lock:
            for name, dq in self._buffers.items():
                if not dq:
                    return None
                # concatenate the trailing items until we have ≥n samples
                pieces: list[np.ndarray] = []
                total = 0
                for arr, _t in reversed(dq):
                    pieces.append(arr)
                    total += arr.shape[0]
                    if total >= n:
                        break
                joined = np.concatenate(list(reversed(pieces)))
                if joined.shape[0] < n:
                    pad_shape = (n - joined.shape[0],) + joined.shape[1:]
                    joined = np.concatenate(
                        [np.zeros(pad_shape, dtype=joined.dtype), joined])
                out[name] = joined[-n:]
        return out

    def events(
        self,
        threshold_rms: float,
        window_ms: int = 200,
        cooldown_ms: int = 500,
        post_trigger_ms: int = 100,
    ) -> Iterator[Event]:
        """Yield Events when any mic's RMS crosses `threshold_rms`.

        For each event we return a `window_ms`-long snapshot from every
        mic, ending `post_trigger_ms` after the trigger so the trigger
        signal sits comfortably inside the window. After firing we
        sleep for `cooldown_ms` before re-arming, to avoid one loud
        sound producing dozens of events.
        """
        window_s = window_ms / 1000.0
        # Inner window where we measure RMS to decide if we trigger.
        # Smaller than the returned window so we react quickly.
        probe_s = min(window_s, 0.05)
        last_trigger = 0.0

        while not self._stop_event.is_set():
            time.sleep(0.02)
            now = time.monotonic()
            if (now - last_trigger) * 1000 < cooldown_ms:
                continue

            probe = self.latest_window(probe_s)
            if probe is None:
                continue

            rms_now = {n: float(np.sqrt(np.mean(s.astype(np.float32) ** 2)))
                       for n, s in probe.items()}
            loud = {n: r for n, r in rms_now.items() if r >= threshold_rms}
            if not loud:
                continue

            # Wait the post-trigger duration so the snapshot includes
            # samples from just after the trigger as well.
            time.sleep(post_trigger_ms / 1000.0)

            full = self.latest_window(window_s)
            if full is None:
                continue

            full_rms = {n: float(np.sqrt(np.mean(s.astype(np.float32) ** 2)))
                        for n, s in full.items()}
            triggered_by = max(loud, key=loud.get)
            last_trigger = time.monotonic()
            yield Event(
                samples=full,
                triggered_by=triggered_by,
                timestamp=last_trigger,
                rms=full_rms,
            )

    def watch(self, callback: Callable[[Event], None], **event_kwargs) -> None:
        """Callback-style version of `events()`. Blocks until close()."""
        for ev in self.events(**event_kwargs):
            try:
                callback(ev)
            except Exception:
                log.exception("event callback raised")

    # ─── internals ────────────────────────────────────────────────────

    def _consume_into_buffer(self, name: str, stream: MicStream) -> None:
        """Drain `stream` into the per-mic ring buffer.

        Each entry is (samples_block, wall_clock_end_time). We keep at
        most `buffer_capacity` samples per mic — older blocks are evicted.
        """
        for chunk in stream:
            if self._stop_event.is_set():
                return
            with self._buf_lock:
                dq = self._buffers[name]
                dq.append((chunk.samples, chunk.received_at))
                # evict until total samples ≤ capacity
                total = sum(b.shape[0] for b, _ in dq)
                while dq and total > self._buffer_capacity:
                    head, _ = dq.popleft()
                    total -= head.shape[0]
