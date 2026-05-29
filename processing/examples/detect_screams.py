#!/usr/bin/env python3
"""Real-time anomaly detection: Detect screams, crashes, and unusual sounds."""

import sys
import argparse
import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_analyzer.pipeline import AudioAnalysisPipeline


def record_audio(duration: float = 10.0, sr: int = 16000) -> np.ndarray:
    """Record from microphone."""
    print(f"\n🎤 Recording {duration}s...\n")
    audio = sd.rec(int(sr * duration), samplerate=sr, channels=1, dtype=np.float32)
    sd.wait()
    return audio.flatten()


def detect_screams_live(duration: float = 10.0, sr: int = 16000):
    """Detect screams/anomalies in real-time."""
    print("=" * 70)
    print("🚨 ANOMALY DETECTION (SCREAMS, CRASHES, ETC)")
    print("=" * 70)
    print("\nThis will detect:")
    print("  ✓ Screams/Shouts (high freq + high amplitude)")
    print("  ✓ Crashes/Breaking (broad spectrum + transient)")
    print("  ✓ Sharp noises (sudden spikes)")
    print("  ✓ Any sound much louder than background")
    print()
    print("Tips for best results:")
    print("  - Let it learn background for first 2 seconds (normal ambient)")
    print("  - Then make the sound you want to detect")
    print("  - Detection works best with 6+ dB above ambient noise")
    print()
    
    # Record audio
    audio = record_audio(duration=duration, sr=sr)
    
    # Pipeline
    pipeline = AudioAnalysisPipeline(target_sr=sr)
    
    # Learn baseline from first 2 seconds
    baseline_audio = audio[: sr * 2]
    
    # Analyze with baseline
    result = pipeline.detect_anomalies(
        audio,
        sr=sr,
        baseline_audio=baseline_audio,
        baseline_sr=sr,
        min_snr_db=6.0,  # 6dB above ambient
        min_confidence=0.5,  # Relaxed for demo
        sensitivity=0.6,
    )
    
    print(result["summary"])
    print()
    
    if result["anomalies"]:
        print("📊 Details:")
        for anom in result["anomalies"]:
            print(f"\n  Type: {anom['type'].value}")
            print(f"  Confidence: {anom['confidence']:.0%}")
            print(f"  SNR: {anom['snr_db']:.1f} dB")
            print(f"  Score: {anom['score']:.2f}")
            print(f"  RMS: {anom['rms']:.4f} (baseline: {anom['baseline_rms']:.4f})")
    else:
        print("\n✓ No anomalies detected (background is normal)")
    
    # Save recording
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent / "test_audio"
    output_dir.mkdir(exist_ok=True)
    filepath = output_dir / f"anomaly_{timestamp}.wav"
    sf.write(str(filepath), audio, sr)
    print(f"\n💾 Saved: {filepath}")


def calibrate_anomaly_detector(sr: int = 16000):
    """Interactive calibration for your environment."""
    print("=" * 70)
    print("🔧 ANOMALY DETECTOR CALIBRATION")
    print("=" * 70)
    print()
    print("This calibrates the detector to YOUR environment.")
    print()
    
    # Step 1: Learn background
    print("STEP 1: Learning background noise (ambient environment)")
    print("-" * 70)
    print("Keep it silent for 5 seconds (or play normal background)")
    
    background = record_audio(duration=5.0, sr=sr)
    
    pipeline = AudioAnalysisPipeline(target_sr=sr)
    pipeline.anomaly_detector.learn_baseline(background)
    
    baseline_rms = pipeline.anomaly_detector.baseline_rms
    print(f"✓ Baseline learned: RMS = {baseline_rms:.4f}")
    print()
    
    # Step 2: Test anomaly
    print("STEP 2: Testing anomaly detection")
    print("-" * 70)
    print("Now make an anomalous sound: SCREAM, CRASH, or BANG")
    print("(Must be noticeably louder/different than background)")
    
    test_audio = record_audio(duration=3.0, sr=sr)
    
    # Analyze with baseline
    result = pipeline.detect_anomalies(
        test_audio,
        sr=sr,
        baseline_audio=None,  # Already calibrated
        min_snr_db=6.0,
        min_confidence=0.3,
        sensitivity=0.6,
    )
    
    print(result["summary"])
    print()
    
    if result["anomalies"]:
        print("✅ DETECTED!")
        for anom in result["anomalies"]:
            print(f"   Type: {anom['type'].value} ({anom['confidence']:.0%})")
        print()
        print("RECOMMENDATIONS for your setup:")
        
        # Suggest thresholds
        avg_confidence = np.mean([a["confidence"] for a in result["anomalies"]])
        if avg_confidence > 0.7:
            print(f"  - High detection confidence: Use min_confidence=0.6")
        elif avg_confidence > 0.5:
            print(f"  - Good detection: Use min_confidence=0.5")
        else:
            print(f"  - Borderline detection: Use min_confidence=0.3-0.4")
    else:
        print("❌ No anomalies detected")
        print()
        print("Try:")
        print("  1. Make the sound LOUDER (need 6+ dB above baseline)")
        print("  2. Make it more like a SCREAM/CRASH (clear acoustic event)")
        print("  3. Use CALIBRATE mode multiple times to find thresholds")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Anomaly detection: Detect screams, crashes, and unusual sounds"
    )
    parser.add_argument(
        "mode",
        choices=["detect", "calibrate"],
        help="detect: Detect anomalies | calibrate: Find best thresholds",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Recording duration in seconds (default: 10)",
    )
    parser.add_argument(
        "--sr",
        type=int,
        default=16000,
        help="Sample rate in Hz (default: 16000)",
    )
    
    args = parser.parse_args()
    
    if args.mode == "detect":
        detect_screams_live(duration=args.duration, sr=args.sr)
    elif args.mode == "calibrate":
        calibrate_anomaly_detector(sr=args.sr)


if __name__ == "__main__":
    main()
