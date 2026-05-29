#!/usr/bin/env python3
"""
Test suite for Analysis Engine

Run with: python test_pipeline.py
"""

import numpy as np
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis_engine import (
    DOAEstimator,
    SpectrogramGenerator,
    AlarmRecognizer,
    MotorMapper,
    AudioAnalysisPipeline,
)


def test_doa_estimator():
    """Test DOA estimation."""
    print("\n" + "="*60)
    print("TEST: DOA Estimator")
    print("="*60)
    
    sr = 16000
    doa = DOAEstimator(mic_distance=0.05, sample_rate=sr)
    
    # Create test signals
    duration = 1.0
    t = np.arange(int(sr * duration)) / sr
    freq = 1000  # 1kHz
    
    # Simulate sound from 45° (right)
    signal = np.sin(2 * np.pi * freq * t).astype(np.float32)
    
    # Add slight delay to second mic
    delay_samples = 10
    signal2 = np.concatenate([np.zeros(delay_samples), signal[:-delay_samples]]).astype(np.float32)
    
    result = doa.estimate(signal, signal2)
    
    print(f"✓ DOA Estimate: {result:.1f}°")
    assert result is not None, "DOA should not be None"
    assert 0 <= result <= 360, "DOA should be in range [0, 360]"
    print(f"✓ PASS")


def test_spectrogram_generator():
    """Test spectrogram generation."""
    print("\n" + "="*60)
    print("TEST: Spectrogram Generator")
    print("="*60)
    
    sr = 16000
    spec_gen = SpectrogramGenerator(sr=sr)
    
    # Create test audio
    duration = 1.0
    t = np.arange(int(sr * duration)) / sr
    audio = np.sin(2 * np.pi * 1000 * t).astype(np.float32) * 0.1
    
    spec = spec_gen.generate(audio)
    
    print(f"✓ Spectrogram shape: {spec.shape}")
    assert spec.shape == (224, 224), f"Expected (224, 224), got {spec.shape}"
    assert 0 <= np.min(spec) and np.max(spec) <= 1, "Should be normalized to [0, 1]"
    print(f"✓ Min: {np.min(spec):.4f}, Max: {np.max(spec):.4f}")
    print(f"✓ PASS")


def test_alarm_recognizer():
    """Test alarm recognizer."""
    print("\n" + "="*60)
    print("TEST: Alarm Recognizer")
    print("="*60)
    
    recognizer = AlarmRecognizer(use_template_only=True)
    
    # Create dummy spectrogram
    spec = np.random.rand(224, 224).astype(np.float32) * 0.5
    
    result = recognizer.recognize(spec, debug=True)
    
    print(f"✓ Result: {result}")
    assert 'confidence' in result, "Result should have 'confidence'"
    assert 'is_alarm' in result, "Result should have 'is_alarm'"
    assert 'method' in result, "Result should have 'method'"
    print(f"✓ PASS")


def test_motor_mapper():
    """Test motor mapping."""
    print("\n" + "="*60)
    print("TEST: Motor Mapper")
    print("="*60)
    
    test_cases = [
        (0, 0, "Front"),
        (45, 1, "Right"),
        (90, 1, "Right"),
        (135, 2, "Back"),
        (180, 2, "Back"),
        (225, 3, "Left"),
        (270, 3, "Left"),
        (315, 0, "Front"),
    ]
    
    for angle, expected_motor, label in test_cases:
        motor = MotorMapper.get_motor(angle)
        assert motor == expected_motor, f"Angle {angle}° should map to motor {expected_motor}, got {motor}"
        print(f"✓ {angle:3d}° → Motor {motor} ({label})")
    
    # Test motor intensities
    intensities = MotorMapper.angle_to_motor_intensity(45, spread=60.0)
    print(f"\n✓ Motor intensities at 45°: {intensities}")
    assert sum(intensities.values()) > 0, "At least one motor should be active"
    
    print(f"✓ PASS")


def test_full_pipeline():
    """Test full analysis pipeline."""
    print("\n" + "="*60)
    print("TEST: Full Pipeline")
    print("="*60)
    
    sr = 16000
    pipeline = AudioAnalysisPipeline(sample_rate=sr, use_template_only=True)
    
    # Create test audio
    duration = 0.5
    t = np.arange(int(sr * duration)) / sr
    
    # Mic 1: alarm signal
    mic1 = np.sin(2 * np.pi * 800 * t).astype(np.float32) * 0.2
    
    # Mic 2: delayed version
    mic2 = np.concatenate([np.zeros(5), mic1[:-5]]).astype(np.float32)
    
    result = pipeline.analyze(mic1, mic2, debug=True)
    
    print(f"\n✓ Analysis Result:")
    print(f"  DOA: {result['doa_degrees']}°")
    print(f"  Alarm Confidence: {result['alarm_confidence']:.2%}")
    print(f"  Is Alarm: {result['is_alarm']}")
    print(f"  Predicted Motor: {result['predicted_motor']}")
    print(f"  Motor Intensities: {result['motor_intensities']}")
    
    assert 'doa_degrees' in result, "Result should have DOA"
    assert 'alarm_confidence' in result, "Result should have alarm confidence"
    assert result['spectrogram'] is not None, "Should have spectrogram"
    print(f"\n✓ PASS")


def test_batch_processing():
    """Test batch processing."""
    print("\n" + "="*60)
    print("TEST: Batch Processing")
    print("="*60)
    
    sr = 16000
    pipeline = AudioAnalysisPipeline(sample_rate=sr, use_template_only=True)
    
    # Create batch of audio
    batch_size = 5
    chunk_length = int(sr * 0.5)  # 500ms chunks
    
    batch1 = np.random.randn(batch_size, chunk_length).astype(np.float32) * 0.1
    batch2 = np.random.randn(batch_size, chunk_length).astype(np.float32) * 0.1
    
    results = pipeline.analyze_batch(batch1, batch2)
    
    print(f"✓ Processed {len(results)} chunks")
    assert len(results) == batch_size, f"Expected {batch_size} results, got {len(results)}"
    
    for i, r in enumerate(results):
        print(f"  Chunk {i}: Motor={r['predicted_motor']}, Confidence={r['alarm_confidence']:.2%}")
    
    print(f"✓ PASS")


def test_pipeline_config():
    """Test pipeline configuration."""
    print("\n" + "="*60)
    print("TEST: Pipeline Configuration")
    print("="*60)
    
    pipeline = AudioAnalysisPipeline()
    config = pipeline.get_config()
    
    print(f"✓ Configuration:")
    import json
    print(json.dumps(config, indent=2))
    
    status = pipeline.get_status()
    print(f"\n✓ Status:")
    print(json.dumps(status, indent=2))
    
    print(f"✓ PASS")


if __name__ == '__main__':
    print("\n" + "🧪 ANALYSIS ENGINE TEST SUITE".center(60))
    print("="*60)
    
    try:
        test_doa_estimator()
        test_spectrogram_generator()
        test_alarm_recognizer()
        test_motor_mapper()
        test_full_pipeline()
        test_batch_processing()
        test_pipeline_config()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED".center(60))
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
