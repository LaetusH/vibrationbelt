#!/usr/bin/env python3
"""
Quick YAMNet Test - Verify model loading and basic classification
"""

import sys
import numpy as np
from pathlib import Path

try:
    import tensorflow as tf
    import tensorflow_hub as hub
except ImportError:
    print("❌ Missing dependencies:")
    print("   pip install tensorflow tensorflow-hub")
    sys.exit(1)


def test_yamnet():
    """Test YAMNet model loading and inference."""
    
    print("="*70)
    print("🧪 YAMNet Quick Test")
    print("="*70)
    
    # Test 1: Load model
    print("\n[1/4] Loading YAMNet model...")
    try:
        model = hub.load('https://www.kaggle.com/models/google/yamnet/TensorFlow2/yamnet/1')
        print("    ✅ Model loaded successfully")
    except Exception as e:
        print(f"    ❌ Failed to load model: {e}")
        return False
    
    # Test 2: Generate test audio
    print("\n[2/4] Generating test audio...")
    sample_rate = 16000
    duration = 3.0
    samples = int(sample_rate * duration)
    
    # Sine wave at 2 kHz (alarm-like)
    t = np.arange(samples) / sample_rate
    frequency = 2000  # Hz
    waveform = np.sin(2 * np.pi * frequency * t).astype(np.float32)
    waveform = np.clip(waveform * 0.3, -1.0, 1.0)  # Normalize
    
    print(f"    ✅ Generated {duration}s audio (2kHz sine wave)")
    print(f"       Shape: {waveform.shape}")
    print(f"       Min: {waveform.min():.3f}, Max: {waveform.max():.3f}")
    
    # Test 3: Run inference
    print("\n[3/4] Running YAMNet inference...")
    try:
        scores, embeddings, spectrogram = model(waveform)
        print("    ✅ Inference successful")
        print(f"       Scores shape: {scores.shape}")
        print(f"       Top-5 predictions:")
        
        # Get top-5 classes
        top_indices = np.argsort(scores[0].numpy())[-5:][::-1]
        
        for rank, idx in enumerate(top_indices, 1):
            confidence = scores[0].numpy()[int(idx)]
            print(f"         {rank}. Class {int(idx)} : {confidence:.2%}")
    
    except Exception as e:
        print(f"    ❌ Inference failed: {e}")
        return False
    
    # Test 4: Silence audio
    print("\n[4/4] Testing with silence...")
    silence = np.zeros(samples, dtype=np.float32)
    
    try:
        scores_silence, _, _ = model(silence)
        print("    ✅ Silence processing successful")
        print(f"       Max confidence: {scores_silence[0].numpy().max():.2%}")
    
    except Exception as e:
        print(f"    ❌ Silence processing failed: {e}")
        return False
    
    # Summary
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70)
    print("\nYAMNet is ready to use!")
    print("\nNext: python3 run_live_analysis_yamnet.py --simulate")
    
    return True


if __name__ == "__main__":
    success = test_yamnet()
    sys.exit(0 if success else 1)
