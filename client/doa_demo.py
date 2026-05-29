"""Live direction-of-arrival demo, using the vibrationbelt library's
DirectionTracker (same gating + smoothing as the Blazor debug UI).

    python doa_demo.py 10.8.5.177 [baseline_m]

Make a sound near one mic and watch the bar swing toward it. The bar
holds its last position during silence instead of jumping to noise.
"""

import sys

import vibrationbelt as vb


def bar(angle_deg: float, width: int = 41) -> str:
    """ASCII left↔right meter. Center = broadside (0°)."""
    pos = int(round((angle_deg + 90) / 180 * (width - 1)))
    pos = max(0, min(width - 1, pos))
    cells = ["·"] * width
    cells[width // 2] = "|"        # broadside marker
    cells[pos] = "●"
    return "".join(cells)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python doa_demo.py <esp32-ip> [baseline_m]")
        return 1
    ip = sys.argv[1]
    baseline = float(sys.argv[2]) if len(sys.argv) > 2 else 0.20

    print(f"Tracking DoA from {ip}, baseline {baseline*100:.0f} cm. "
          f"Ctrl-C to stop.\n")
    print(f"  LEFT {'':<18}CENTER{'':<18} RIGHT")

    with vb.DirectionTracker(ip, baseline_m=baseline) as doa:
        try:
            for fix in doa:
                state = "● LIVE" if fix.live else "○ held"
                color_hint = fix.hint if fix.live else "—"
                print(f"\r[{bar(fix.angle_deg)}] "
                      f"{fix.angle_deg:+6.1f}°  {state}  "
                      f"{color_hint:<6} conf={fix.confidence:.2f} "
                      f"drops={doa.dropped:4d}",
                      end="", flush=True)
        except KeyboardInterrupt:
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
