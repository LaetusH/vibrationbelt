#!/usr/bin/env python3
"""Example: Batch alarm detection across multiple files."""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_analyzer.pipeline import AudioAnalysisPipeline


def main():
    """Detect alarms in multiple audio files."""
    if len(sys.argv) < 2:
        print("Usage: python batch_detect.py <directory> [pattern]")
        print("\nExample:")
        print("  python batch_detect.py ./audio_files *.wav")
        print("  python batch_detect.py ./audio_files")
        sys.exit(1)

    directory = Path(sys.argv[1])
    pattern = sys.argv[2] if len(sys.argv) > 2 else "*.wav"

    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)

    # Find audio files
    files = sorted(directory.glob(pattern))
    if not files:
        print(f"No files matching '{pattern}' in {directory}")
        sys.exit(1)

    print(f"Found {len(files)} audio file(s)")
    print("-" * 60)

    # Initialize pipeline
    pipeline = AudioAnalysisPipeline(target_sr=16000)

    # Process each file
    results = []
    for i, filepath in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {filepath.name}")

        try:
            alarms = pipeline.detect_alarms_in_file(
                str(filepath),
                sensitivity=0.6,
                min_confidence=0.5,
            )

            if alarms:
                print(f"  ✓ {len(alarms)} alarm(s) detected")
                for alarm in alarms:
                    print(
                        f"    - {alarm['alarm_type'].value} @ {alarm['start_time']:.2f}s"
                        f" (confidence: {alarm['confidence']:.0%})"
                    )
            else:
                print("  ✗ No alarms detected")

            results.append(
                {
                    "file": filepath.name,
                    "alarms": len(alarms),
                    "detections": alarms,
                }
            )

        except Exception as e:
            print(f"  ERROR: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total files: {len(results)}")
    total_alarms = sum(r["alarms"] for r in results)
    print(f"  Total alarms found: {total_alarms}")
    if total_alarms > 0:
        files_with_alarms = sum(1 for r in results if r["alarms"] > 0)
        print(f"  Files with alarms: {files_with_alarms}")


if __name__ == "__main__":
    main()
