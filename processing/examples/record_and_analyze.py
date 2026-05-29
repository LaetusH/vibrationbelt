#!/usr/bin/env python3
"""Record audio from MacBook microphone and analyze for alarms."""

import sys
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_analyzer.pipeline import AudioAnalysisPipeline


def record_audio(duration: float = 5.0, sr: int = 16000) -> np.ndarray:
    """
    Record audio from microphone.
    
    Args:
        duration: Recording duration in seconds.
        sr: Sample rate (Hz).
        
    Returns:
        Audio array (numpy).
    """
    print(f"🎤 Recording for {duration} seconds... (speak/alarm now!)")
    print("   Press Ctrl+C to stop early")
    
    try:
        audio = sd.rec(int(sr * duration), samplerate=sr, channels=1, dtype=np.float32)
        sd.wait()  # Wait until recording is done
        audio = audio.flatten()  # Convert to 1D
        print(f"✓ Recording complete ({len(audio)} samples)")
        return audio
    except KeyboardInterrupt:
        print("\n✓ Recording stopped")
        return None


def main():
    """Record from mic and analyze."""
    # Parse arguments
    duration = 5.0
    if len(sys.argv) > 1:
        try:
            duration = float(sys.argv[1])
        except ValueError:
            print(f"Usage: python record_and_analyze.py [duration_seconds]")
            print(f"       Default: {duration}s")
            print(f"Example: python record_and_analyze.py 10")
            sys.exit(1)

    # Check sounddevice availability
    try:
        import sounddevice
    except ImportError:
        print("❌ sounddevice not installed")
        print("   Install: pip install sounddevice")
        sys.exit(1)

    print("=" * 60)
    print("Audio Recorder + Alarm Detector")
    print("=" * 60)
    
    # List available devices (useful for debugging)
    print("\n📍 Available audio devices:")
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    for i, device in enumerate(devices):
        marker = " ← default" if i == default_input else ""
        if "input" in device["name"].lower() or device["max_input_channels"] > 0:
            print(f"   {i}: {device['name']} ({device['max_input_channels']} in){marker}")
    
    print()

    # Record
    sr = 16000
    audio = record_audio(duration=duration, sr=sr)
    
    if audio is None or len(audio) == 0:
        print("No audio recorded")
        sys.exit(1)

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path(__file__).parent.parent / "test_audio" / f"mic_recording_{timestamp}.wav"
    output_file.parent.mkdir(exist_ok=True)
    
    sf.write(str(output_file), audio, sr)
    print(f"💾 Saved: {output_file}")
    print()

    # Analyze
    print("=" * 60)
    print("🔍 Analyzing...")
    print("=" * 60)
    print()
    
    pipeline = AudioAnalysisPipeline(target_sr=sr)
    result = pipeline.analyze_audio(
        audio, sr,
        alarm_sensitivity=0.6,
        alarm_min_confidence=0.5
    )

    # Print summary
    print(result["summary"])
    print()

    # Print detailed loudness
    print("📊 Loudness Details:")
    print(f"  RMS: {result['loudness']['rms_db']:.1f} dB")
    print(f"  Peak: {result['loudness']['peak_db']:.1f} dB")
    print(f"  LUFS: {result['loudness']['lufs']:.1f}")
    print()

    # Print spectrum peaks
    if result["spectrum"]["peak_frequencies"]:
        print("🎵 Top Frequency Peaks:")
        for freq, mag in zip(
            result["spectrum"]["peak_frequencies"][:5],
            result["spectrum"]["peak_magnitudes"][:5],
        ):
            print(f"  {freq:.0f} Hz → magnitude {mag:.2f}")
    print()

    # Detailed alarm info
    if result["alarms"]:
        print("🚨 Alarm Details:")
        for i, alarm in enumerate(result["alarms"], 1):
            print(f"\n  Alarm {i}:")
            print(f"    Type: {alarm['alarm_type'].value}")
            print(f"    Time: {alarm['start_time']:.2f}s - {alarm['end_time']:.2f}s")
            print(f"    Confidence: {alarm['confidence']:.0%}")
            print(f"    Frequencies: {alarm['frequencies']}")
    else:
        print("✓ No alarms detected (clean signal)")

    print("\n" + "=" * 60)
    print(f"✓ Analysis saved to {output_file}")


if __name__ == "__main__":
    main()
