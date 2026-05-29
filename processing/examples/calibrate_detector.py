#!/usr/bin/env python3
"""Calibrate detector: Find the minimum confidence threshold for your alarm."""

import sys
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_analyzer.alarm_detector import AlarmDetector


def record_audio(duration: float = 5.0, sr: int = 16000) -> np.ndarray:
    """Record from microphone."""
    print(f"🎤 Recording {duration}s (PLAY YOUR ALARM NOW)...\n")
    audio = sd.rec(int(sr * duration), samplerate=sr, channels=1, dtype=np.float32)
    sd.wait()
    return audio.flatten()


def analyze_at_threshold(audio: np.ndarray, sr: int, threshold: float) -> dict:
    """Analyze with specific confidence threshold."""
    detector = AlarmDetector(sr)
    detections = detector.detect_alarms(audio, min_confidence=threshold)
    return detections


def main():
    """Calibrate detector thresholds."""
    sr = 16000
    
    print("=" * 70)
    print("🔧 DETECTOR CALIBRATION")
    print("=" * 70)
    print()
    print("This will help find the right confidence threshold for your alarms.")
    print("You'll record 5 seconds with your alarm sound.")
    print()
    
    # Record alarm
    audio = record_audio(duration=5.0, sr=sr)
    
    # Save recording
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent / "test_audio"
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / f"calibration_{timestamp}.wav"
    sf.write(str(filepath), audio, sr)
    print(f"💾 Saved: {filepath}\n")
    
    # Analyze at different thresholds
    print("Testing at different confidence thresholds...")
    print("-" * 70)
    
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        detections = analyze_at_threshold(audio, sr, threshold)
        
        print(f"\nThreshold: {threshold:.1f}")
        if detections:
            for det in detections:
                print(f"  ✓ {det['alarm_type'].value}")
                print(f"    Confidence: {det['confidence']:.0%}")
                print(f"    Freq match: {det['features'].get('freq_match', 'N/A')}")
                print(f"    Periodicity: {det['features'].get('periodicity', 'N/A')}")
                print(f"    Pattern strength: {det['features'].get('pattern_strength', 'N/A')}")
        else:
            print(f"  ✗ No detection")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATION:")
    print("=" * 70)
    
    # Find optimal threshold
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
        dets = analyze_at_threshold(audio, sr, threshold)
        if dets:
            print(f"\n✓ Use: alarm_min_confidence={threshold}")
            print(f"  (detects your alarm reliably)")
            break
    else:
        print("\n❌ Your alarm is too quiet/noisy to detect.")
        print("   Try a louder alarm or clearer pattern (steady pulsing).")
        
        # Debug info
        print("\nDebug Info:")
        detector = AlarmDetector(sr)
        
        # Check frequency content
        print("\nFrequency analysis:")
        for freq_range in [(800, 1200), (2500, 3500)]:
            freqs, mags = detector._compute_fft(audio)
            mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
            if np.any(mask):
                band_max = np.max(mags[mask])
                band_mean = np.mean(mags[mask])
                print(f"  {freq_range[0]}-{freq_range[1]} Hz: max={band_max:.1f}, mean={band_mean:.1f}")
        
        # Check periodicity
        print("\nPeriodicity analysis:")
        acf = detector._autocorrelation(audio)
        if len(acf) > 0:
            print(f"  ACF max: {np.max(acf):.3f}")
            print(f"  ACF mean: {np.mean(acf):.3f}")


if __name__ == "__main__":
    main()
