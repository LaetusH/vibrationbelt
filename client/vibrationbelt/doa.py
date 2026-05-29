"""Direction-of-arrival helpers.

GCC-PHAT (Generalized Cross-Correlation with Phase Transform) is the
standard sub-sample TDoA estimator. It's robust to broadband signals
and far better than naïve cross-correlation under reverberation /
non-flat spectra.

Why PHAT weighting?
    Plain cross-correlation peaks where the signals' energies happen to
    align, so a dominant low-frequency component drowns out everything
    else. PHAT whitens both spectra before correlating, so the result
    depends only on phase — which is what carries the timing info.

References
    Knapp & Carter, "The generalized correlation method for estimation
    of time delay", IEEE TASSP, 1976.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

SPEED_OF_SOUND = 343.0      # m/s, dry air ~20°C


def gcc_phat(
    x: np.ndarray,
    y: np.ndarray,
    sample_rate: int,
    max_delay_s: Optional[float] = None,
    interp: bool = True,
) -> Tuple[float, float]:
    """Estimate the time delay τ of `x` relative to `y`.

    A *positive* τ means the signal in `x` arrived later than in `y`,
    i.e. the source is on `y`'s side of the array.

    Parameters
    ----------
    x, y
        Equal-length 1-D arrays of samples (any numeric dtype).
    sample_rate
        Samples per second.
    max_delay_s
        Limit the search to ±this many seconds. Use this when you know
        the physical inter-mic distance: ``max_delay_s = baseline / c``
        plus a small margin. Restricting the search avoids spurious
        peaks from reflections.
    interp
        Parabolic interpolation around the peak for sub-sample resolution.

    Returns
    -------
    (delay_seconds, confidence)
        `confidence` is in [0, 1]; the ratio of the peak magnitude to
        the largest competing peak in the search window. Below ~0.4
        the estimate is unreliable (probably noise or no real signal).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("x and y must be 1-D arrays of equal length")

    n = x.size
    if n < 4:
        return 0.0, 0.0

    n_fft = 1 << int(np.ceil(np.log2(2 * n)))   # zero-pad to avoid wrap

    X = np.fft.rfft(x, n_fft)
    Y = np.fft.rfft(y, n_fft)
    R = X * np.conj(Y)
    R /= np.abs(R) + 1e-15                       # PHAT whitening

    cc = np.fft.irfft(R, n_fft)
    # Re-arrange so index 0 is lag -n_fft/2 and the centre is lag 0.
    cc = np.concatenate((cc[-(n_fft // 2):], cc[:n_fft // 2]))
    centre = n_fft // 2

    if max_delay_s is None:
        max_lag = n_fft // 2
    else:
        max_lag = max(1, int(round(max_delay_s * sample_rate)))

    lo = max(0, centre - max_lag)
    hi = min(n_fft, centre + max_lag + 1)
    region = cc[lo:hi]
    peak = int(np.argmax(region))
    lag_samples = float(peak - (centre - lo))

    # Parabolic interpolation for sub-sample resolution.
    if interp and 0 < peak < region.size - 1:
        a, b, c = region[peak - 1], region[peak], region[peak + 1]
        denom = (a - 2 * b + c)
        if denom != 0:
            lag_samples += 0.5 * (a - c) / denom

    # Confidence: peak relative to the next-best peak elsewhere.
    region_copy = region.copy()
    notch = slice(max(0, peak - 2), min(region.size, peak + 3))
    region_copy[notch] = 0
    second = float(np.max(region_copy)) if region_copy.size else 0.0
    peak_val = float(region[peak])
    confidence = 0.0 if peak_val <= 0 else 1.0 - max(0.0, second) / peak_val

    return lag_samples / sample_rate, confidence


def tdoa_to_angle(
    tdoa_s: float,
    baseline_m: float,
    speed_of_sound: float = SPEED_OF_SOUND,
) -> float:
    """Convert an inter-mic time-of-arrival difference to angle of arrival.

    Geometry
        Two omni mics separated by `baseline_m`. The angle is measured
        from the perpendicular bisector of the pair (broadside = 0°).
        Positive `tdoa_s` (the signal arrived at the FIRST mic *later*)
        means the source is on the SECOND mic's side, returned as a
        positive angle.

    Returns
    -------
    angle_deg in [-90, +90].

    Notes
    -----
    Two-mic arrays cannot disambiguate front from back — the same TDoA
    corresponds to two physical directions (cone of confusion). Use ≥3
    mics if you need a unique bearing.
    """
    sin_theta = tdoa_s * speed_of_sound / baseline_m
    sin_theta = float(np.clip(sin_theta, -1.0, 1.0))
    return float(np.degrees(np.arcsin(sin_theta)))
