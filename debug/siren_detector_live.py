#!/usr/bin/env python3
"""
Live Emergency Vehicle Siren Detection
Continuously monitors laptop microphone and outputs: ALARM or QUIET
"""

import sys
import os
import csv
import time
import urllib.request
import numpy as np

try:
    import tensorflow as tf
    import tensorflow_hub as hub
    import sounddevice as sd
except ImportError:
    print("❌ Missing dependencies:")
    print("   pip install tensorflow tensorflow-hub sounddevice")
    sys.exit(1)


# Target alarm classes (from Kaggle notebook)
ALARM_KEYWORDS = [
    'emergency vehicle',
    'siren',
    'police',
    'ambulance',
    'fire engine',
    'fire truck',
    'horn',
    'honk',
    'alarm',
    'klaxon',
]

QUIET_KEYWORDS = [
    'speech',
    'music',
    'silence',
    'ambient',
    'wind',
    'rain',
    'traffic',
    'crowd',
    'applause',
    'laughter',
    'chatter',
    'conversation',
]


def setup_yamnet():
    """Setup YAMNet model and load class labels."""
    class_map_path = 'yamnet_class_map.csv'
    if not os.path.exists(class_map_path):
        print("📥 Downloading YAMNet class map...")
        urllib.request.urlretrieve(
            'https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv',
            class_map_path)

    class_names = []
    with open(class_map_path) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            class_names.append(row['display_name'])

    print("📥 Loading YAMNet model...")
    model = hub.load('https://tfhub.dev/google/yamnet/1')
    print(f"✅ Model loaded! Total classes: {len(class_names)}\n")
    
    return model, class_names


def classify_alarm_or_quiet(results):
    """Binary classification: ALARM or QUIET."""
    if not results:
        return 'QUIET', 0.0, 'No predictions'
    
    top_class = results[0]['class'].lower()
    top_conf = results[0]['confidence']
    
    is_alarm = any(keyword in top_class for keyword in ALARM_KEYWORDS)
    
    if is_alarm and top_conf > 0.3:
        return 'ALARM', top_conf, results[0]['class']
    else:
        return 'QUIET', 1.0 - top_conf, results[0]['class']


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Live siren detection")
    parser.add_argument("--duration", type=float, default=60, help="Test duration in seconds")
    parser.add_argument("--chunk-size", type=float, default=1.0, help="Chunk size in seconds")
    
    args = parser.parse_args()
    
    # Setup
    model, class_names = setup_yamnet()
    
    sr = 16000
    chunk_samples = int(sr * args.chunk_size)
    
    print("="*80)
    print("🚨 LIVE SIREN DETECTION - ALARM or QUIET")
    print("="*80)
    print(f"Duration: {args.duration}s, Chunk: {args.chunk_size}s\n")
    print("Recording...\n")
    
    start_time = time.time()
    chunk_num = 0
    
    try:
        while time.time() - start_time < args.duration:
            # Record chunk
            audio = sd.rec(chunk_samples, samplerate=sr, channels=1, dtype='float32', blocking=True)
            audio = np.clip(audio.flatten(), -1.0, 1.0)
            
            # Inference
            scores, _, _ = model(audio)
            scores_np = scores.numpy()
            
            # Top-5
            top_indices = np.argsort(scores_np.mean(axis=0))[-5:][::-1]
            results = []
            for idx in top_indices:
                score = scores_np.mean(axis=0)[idx]
                if score > 0.1:
                    results.append({
                        'class': class_names[idx],
                        'confidence': float(score)
                    })
            
            # Classify
            classification, confidence, top_class = classify_alarm_or_quiet(results)
            
            # Print
            chunk_num += 1
            elapsed = time.time() - start_time
            
            # Colored output
            if classification == 'ALARM':
                output = f"\r[{elapsed:6.1f}s] 🚨 ALARM     | {confidence:.2%} | {top_class:<30} "
            else:
                output = f"\r[{elapsed:6.1f}s] 🔇 QUIET     | {confidence:.2%} | {top_class:<30} "
            
            print(output, end="", flush=True)
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
