"""Live VU-meter demo.

Usage:
    python -m vibrationbelt <esp32-ip>                          # single mic
    python -m vibrationbelt --array left=10.0.0.1 right=10.0.0.2  # array
"""

import logging
import sys

import numpy as np

from . import MicStream, MicArray, MicSpec


def _vu(rms: float, width: int = 60) -> str:
    bars = int(min(rms / 500.0, float(width)))
    return f"[{'█' * bars:<{width}}]"


def _single(ip: str) -> None:
    with MicStream(ip) as mic:
        try:
            for chunk in mic:
                rms = float(np.sqrt(np.mean(chunk.samples.astype(np.float32) ** 2)))
                print(f"\rrms={rms:6.0f}  drops={mic.dropped:4d}  {_vu(rms)}",
                      end="", flush=True)
        except KeyboardInterrupt:
            print()


def _array(specs: dict[str, MicSpec]) -> None:
    array = MicArray(specs)
    with array:
        try:
            while True:
                snap = array.latest_window(0.05)
                if snap is None:
                    continue
                line = "  ".join(
                    f"{n:>5}: rms={float(np.sqrt(np.mean(s.astype(np.float32) ** 2))):5.0f}"
                    for n, s in snap.items())
                print(f"\r{line}", end="", flush=True)
                import time; time.sleep(0.05)
        except KeyboardInterrupt:
            print()


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    args = sys.argv[1:]
    if not args:
        print("usage: python -m vibrationbelt <ip>", file=sys.stderr)
        print("       python -m vibrationbelt --array name=ip [name=ip ...]",
              file=sys.stderr)
        return 1

    if args[0] == "--array":
        specs: dict[str, MicSpec] = {}
        for raw in args[1:]:
            if "=" not in raw:
                print(f"bad spec '{raw}', expected name=ip", file=sys.stderr)
                return 1
            name, ip = raw.split("=", 1)
            specs[name] = MicSpec(ip=ip)
        _array(specs)
    else:
        _single(args[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
