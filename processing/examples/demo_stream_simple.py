#!/usr/bin/env python3
"""
Simple demo: Show how to connect live audio to detection pipeline.

This demo:
1. Creates synthetic audio (with siren + scream events)
2. Streams it through StreamProcessor
3. Prints detections in real-time

In production, replace the synthetic audio with:
- vibrationbelt.MicStream("10.8.5.177") for ESP32
- sounddevice stream for USB microphone
- Any other audio source
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from datetime import datetime
from audio_analyzer.stream_processor import (
    StreamProcessor,
    DetectionType,
)


def generate_simple_scream(sr=16000, duration_sec=3.0):
    """Generate a simple high-frequency scream."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    
    # High-freq tone + noise
    scream = 0.4 * np.sin(2 * np.pi * 3500 * t)
    scream += 0.15 * np.random.randn(len(scream))
    
    return scream.astype(np.float32) / np.max(np.abs(scream))


def generate_simple_siren(sr=16000, duration_sec=2.0):
    """Generate a simple pulsing siren."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    
    # 800 Hz with 1 Hz pulsing
    siren = 0.3 * np.sin(2 * np.pi * 800 * t)
    siren *= (1 + 0.5 * np.sin(2 * np.pi * 1.0 * t))
    
    return siren.astype(np.float32)


def main():
    """Main demo."""
    sr = 16000
    frame_size = 2048  # ~128ms
    
    print("\n╔════════════════════════════════════════════════════════╗")
    print("║    StreamProcessor Demo — Live Detection              ║")
    print("╚════════════════════════════════════════════════════════╝\n")
    
    # Create processor
    print("Creating StreamProcessor...")
    processor = StreamProcessor(
        source="demo_stream",
        sr=sr,
        frame_size=frame_size,
        baseline_duration_sec=5.0,
        alarm_sensitivity=0.5,
        anomaly_sensitivity=0.6,
    )
    
    # Setup detection callback
    detections_log = []
    
    def on_detection(detection):
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = (
            f"[{timestamp}] 🎯 DETECTED: {detection.type.value:12} | "
            f"Type: {detection.detector_type:15} | "
            f"Confidence: {detection.confidence:3.0%} | "
            f"SNR: {detection.snr_db:5.1f}dB @ {detection.timestamp_sec:5.1f}s"
        )
        print(msg)
        detections_log.append(detection)
    
    processor.on_detection(on_detection)
    
    # Generate synthetic stream with events
    print("Generating synthetic audio stream (15 seconds)...\n")
    
    # Build timeline:
    # 0-5s: Baseline (quiet)
    # 5-7s: Siren
    # 7-10s: Quiet
    # 10-13s: Scream
    # 13-15s: Quiet
    
    timeline = []
    
    # Baseline
    baseline_len = int(5 * sr)
    baseline = 0.01 * np.random.randn(baseline_len).astype(np.float32)
    timeline.append(("baseline", baseline))
    print("0-5s:   Baseline (learning ambient)")
    
    # Siren
    siren = generate_simple_siren(sr=sr, duration_sec=2.0)
    timeline.append(("siren", siren))
    print("5-7s:   Siren (alarm event)")
    
    # Quiet
    quiet1 = 0.01 * np.random.randn(int(3 * sr)).astype(np.float32)
    timeline.append(("quiet", quiet1))
    print("7-10s:  Quiet")
    
    # Scream
    scream = generate_simple_scream(sr=sr, duration_sec=3.0)
    timeline.append(("scream", scream))
    print("10-13s: Scream (anomaly event)")
    
    # Quiet
    quiet2 = 0.01 * np.random.randn(int(2 * sr)).astype(np.float32)
    timeline.append(("quiet", quiet2))
    print("13-15s: Quiet")
    
    print("\n" + "="*60)
    print("Processing...\n")
    
    # Concatenate all
    full_audio = np.concatenate([audio for _, audio in timeline])
    
    # Process in chunks
    total_frames = 0
    for i in range(0, len(full_audio), frame_size):
        chunk = full_audio[i:i+frame_size]
        processor.process_chunk(chunk)
        total_frames += len(chunk)
        elapsed_sec = total_frames / sr
        
        # Progress indicator every second
        if elapsed_sec % 1.0 < frame_size/sr:
            print(f"  {elapsed_sec:.1f}s processed ({len(detections_log)} detections)", flush=True)
    
    processor.close()
    
    # Summary
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    print(f"\nTotal detections: {len(detections_log)}\n")
    
    if detections_log:
        print("Detections:")
        for i, d in enumerate(detections_log, 1):
            print(f"  {i}. {d.type.value:12} @ {d.timestamp_sec:5.1f}s | "
                  f"{d.detector_type:15} | {d.confidence:.0%}")
    else:
        print("(No detections — this is normal during initial calibration)")
    
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
