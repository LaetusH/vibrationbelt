#!/usr/bin/env python3
"""Example: Analyze a single audio file."""

import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_analyzer.pipeline import AudioAnalysisPipeline


def main():
    """Analyze an audio file and print results."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_file.py <audio_file.wav>")
        print("\nExample:")
        print("  python analyze_file.py alarm.wav")
        sys.exit(1)

    filepath = sys.argv[1]

    # Initialize pipeline
    pipeline = AudioAnalysisPipeline(target_sr=16000)

    # Analyze
    print(f"Analyzing: {filepath}")
    print("-" * 50)

    result = pipeline.analyze_file(
        filepath,
        alarm_sensitivity=0.6,
        alarm_min_confidence=0.5,
    )

    # Print summary
    print(result["summary"])
    print()

    # Print detailed loudness
    print("Loudness Details:")
    print(f"  RMS: {result['loudness']['rms_db']:.1f} dB")
    print(f"  Peak: {result['loudness']['peak_db']:.1f} dB")
    print(f"  LUFS: {result['loudness']['lufs']:.1f}")
    print()

    # Print spectrum peaks
    if result["spectrum"]["peak_frequencies"]:
        print("Top Frequency Peaks:")
        for freq, mag in zip(
            result["spectrum"]["peak_frequencies"][:5],
            result["spectrum"]["peak_magnitudes"][:5],
        ):
            print(f"  {freq:.0f} Hz → magnitude {mag:.2f}")
    print()

    # Detailed alarm info
    if result["alarms"]:
        print("Alarm Details:")
        for i, alarm in enumerate(result["alarms"], 1):
            print(f"\n  Alarm {i}:")
            print(f"    Type: {alarm['alarm_type'].value}")
            print(f"    Time: {alarm['start_time']:.2f}s - {alarm['end_time']:.2f}s")
            print(f"    Confidence: {alarm['confidence']:.0%}")
            print(f"    Frequencies: {alarm['frequencies']}")

    print("\n" + "=" * 50)
    print("✓ Analysis complete")


if __name__ == "__main__":
    main()
