"""Live direction-of-arrival demo using the stereo mic stream.

Geometry:
    Two mics on the belt, BASELINE_M apart, both facing the world.
    Bottom = L channel, Top = R channel (per the Shield2Go 0Ω strap).
    Angle output is broadside-referenced: 0° = source directly in front
    (perpendicular to the mic line), positive = source toward R, negative
    toward L. ±90° = source endfire (in line with the mics).

    python doa_demo.py 10.8.5.177
"""

import sys
from collections import deque

import numpy as np

import vibrationbelt as vb
from vibrationbelt import gcc_phat, tdoa_to_angle

BASELINE_M     = 0.20             # distance between the two mic pieces (m)
TRIGGER_RMS    = 2000             # arm when either channel exceeds this RMS
WINDOW_MS      = 200              # length of the analysis window
COOLDOWN_S     = 0.4              # ignore re-triggers for this long after each event
CONFIDENCE_MIN = 0.4              # discard GCC-PHAT results below this confidence


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python doa_demo.py <esp32-ip>"); return 1
    if vb.CHANNELS != 2:
        print("vibrationbelt.CHANNELS must be 2 for DoA"); return 2

    window_n   = int(WINDOW_MS / 1000 * vb.SAMPLE_RATE)
    max_lag_s  = BASELINE_M / vb.SPEED_OF_SOUND * 1.1   # +10% margin

    # Rolling buffer of the last `window_n` stereo frames.
    buf = deque(maxlen=window_n)
    last_trigger = -1e9

    with vb.MicStream(sys.argv[1]) as mic:
        print(f"Listening… baseline={BASELINE_M*100:.0f} cm, "
              f"window={WINDOW_MS} ms, threshold rms={TRIGGER_RMS}")
        for chunk in mic:
            # chunk.samples shape: (n, 2). Push frames one by one (cheap; n is small).
            for frame in chunk.samples:
                buf.append(frame)
            if len(buf) < window_n:
                continue
            if chunk.timestamp_us / 1e6 - last_trigger < COOLDOWN_S:
                continue

            arr = np.asarray(buf, dtype=np.int16)        # shape (window_n, 2)
            l, r = arr[:, 0], arr[:, 1]
            l_rms = float(np.sqrt(np.mean(l.astype(np.float32) ** 2)))
            r_rms = float(np.sqrt(np.mean(r.astype(np.float32) ** 2)))
            if max(l_rms, r_rms) < TRIGGER_RMS:
                continue

            # NB the sign convention here: gcc_phat returns the lag of `l`
            # relative to `r`. Positive lag = l is the late mic = source
            # is on R's side, which we want to print as a positive angle.
            tdoa, conf = gcc_phat(l, r, vb.SAMPLE_RATE, max_delay_s=max_lag_s)
            if conf < CONFIDENCE_MIN:
                continue

            angle = tdoa_to_angle(tdoa, baseline_m=BASELINE_M)
            side  = "RIGHT" if angle > 5 else "LEFT" if angle < -5 else "CENTER"
            print(f"event  L_rms={l_rms:5.0f}  R_rms={r_rms:5.0f}  "
                  f"τ={tdoa*1e6:+5.0f}µs  conf={conf:.2f}  "
                  f"angle={angle:+6.1f}°  → {side}")
            last_trigger = chunk.timestamp_us / 1e6

    return 0


if __name__ == "__main__":
    sys.exit(main())
