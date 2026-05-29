"""Quick sanity check for stereo capture.

Tap each mic separately while watching the bars — the L bar should
respond when you tap the bottom mic piece, R when you tap the top.
If they always move together, stereo PDM RX isn't actually working and
we need to fall back to the ADAU7002 I²S path.

    python check_stereo.py 10.8.5.177
"""

import sys
import time

import numpy as np

import vibrationbelt as vb


def bar(rms: float, width: int = 30) -> str:
    n = int(min(rms / 500.0, float(width)))
    return f"[{'█' * n:<{width}}]"


def main():
    if len(sys.argv) < 2:
        print("usage: python check_stereo.py <esp32-ip>"); sys.exit(1)

    assert vb.CHANNELS == 2, "vibrationbelt.CHANNELS must be 2 for this test"

    with vb.MicStream(sys.argv[1]) as mic:
        last_print = 0.0
        l_acc = np.zeros(0, dtype=np.int16)
        r_acc = np.zeros(0, dtype=np.int16)
        for chunk in mic:
            l_acc = np.concatenate([l_acc, chunk.samples[:, 0]])
            r_acc = np.concatenate([r_acc, chunk.samples[:, 1]])
            now = time.monotonic()
            if now - last_print < 0.1:
                continue
            l_rms = float(np.sqrt(np.mean(l_acc.astype(np.float32) ** 2)))
            r_rms = float(np.sqrt(np.mean(r_acc.astype(np.float32) ** 2)))
            # Cross-correlation peak — if mics are wired right and the
            # source is roughly equidistant, this is near 0.
            print(f"\rL rms={l_rms:6.0f} {bar(l_rms)}   "
                  f"R rms={r_rms:6.0f} {bar(r_rms)}",
                  end="", flush=True)
            l_acc = l_acc[-1600:]   # keep last 100 ms
            r_acc = r_acc[-1600:]
            last_print = now


if __name__ == "__main__":
    main()
