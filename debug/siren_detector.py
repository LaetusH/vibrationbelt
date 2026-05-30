#!/usr/bin/env python3
"""
Emergency Vehicle Siren Detection using YAMNet
Pipeline based on Kaggle notebook by Mustafa Gulhan
Modified for: Laptop Microphone Input → Binary Classification (ALARM / QUIET)
"""

import sys
import os
import csv
import time
import urllib.request
import numpy as np
import librosa
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

try:
    import tensorflow as tf
    import tensorflow_hub as hub
    import sounddevice as sd
except ImportError:
    print("❌ Missing dependencies:")
    print("   pip install tensorflow tensorflow-hub librosa sounddevice matplotlib seaborn pandas")
    sys.exit(1)


# ============================================================================
# YAMNet Setup & Class Loading
# ============================================================================

def setup_yamnet():
    """
    Setup YAMNet model and load class labels.
    Returns: (model, class_names)
    """
    # Download class map if not exists
    class_map_path = 'yamnet_class_map.csv'
    if not os.path.exists(class_map_path):
        print("📥 Downloading YAMNet class map...")
        urllib.request.urlretrieve(
            'https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv',
            class_map_path)
        print("   ✅ Downloaded")

    # Load class names
    class_names = []
    with open(class_map_path) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            class_names.append(row['display_name'])

    print("📥 Loading YAMNet model...")
    model = hub.load('https://tfhub.dev/google/yamnet/1')
    print(f"   ✅ Model loaded! Total classes: {len(class_names)}")
    
    return model, class_names


# ============================================================================
# Audio Processing (from Kaggle notebook)
# ============================================================================

def load_and_process_audio(file_path, target_sr=16000):
    """
    Load and preprocess audio file for YAMNet analysis.
    
    Args:
        file_path (str): Path to audio file OR 'microphone' for live input
        target_sr (int): Target sample rate (YAMNet requires 16kHz)
    
    Returns:
        numpy.ndarray: Processed audio data
    """
    if file_path == 'microphone':
        print("🎤 Recording from microphone...")
        duration_sec = 3
        samples = int(target_sr * duration_sec)
        
        audio = sd.rec(samples, samplerate=target_sr, channels=1, dtype='float32', blocking=True)
        audio = np.clip(audio.flatten(), -1.0, 1.0)
        
        print(f"   ✅ Recorded {duration_sec}s audio")
        return audio
    
    else:
        print(f"📂 Loading audio file: {file_path}")
        
        # Load audio file
        audio, sr = librosa.load(file_path, sr=target_sr)
        
        # Ensure audio is mono
        if len(audio.shape) > 1:
            print("   Converting stereo to mono...")
            audio = np.mean(audio, axis=1)
        
        print(f"   ✅ Audio duration: {len(audio)/target_sr:.2f} seconds")
        return audio


def analyze_audio(audio_data, model, class_names, confidence_threshold=0.1):
    """
    Analyze audio data using YAMNet and return predictions.
    
    Args:
        audio_data (numpy.ndarray): Audio data to analyze
        model: YAMNet model
        class_names (list): List of class names
        confidence_threshold (float): Minimum confidence score
    
    Returns:
        tuple: (results, all_scores)
    """
    print("🔍 Running YAMNet inference...")
    
    # Get model predictions
    scores, embeddings, spectrogram = model(audio_data)
    scores = scores.numpy()
    
    # Get top predictions
    top_indices = np.argsort(scores.mean(axis=0))[-5:][::-1]
    
    results = []
    for idx in top_indices:
        score = scores.mean(axis=0)[idx]
        if score > confidence_threshold:
            results.append({
                'class': class_names[idx],
                'class_id': idx,
                'confidence': float(score)
            })
    
    return results, scores


# ============================================================================
# Alarm Classification (Custom Logic)
# ============================================================================

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
    'whistle',
]

# Quiet/non-alarm keywords
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
    'background',
    'noise',
    'hum',
    'buzz',
]


def classify_alarm_or_quiet(results):
    """
    Binary classification: ALARM or QUIET based on top predictions.
    
    Args:
        results (list): List of predictions from YAMNet
    
    Returns:
        dict: {
            'classification': 'ALARM' or 'QUIET',
            'confidence': float (0-1),
            'reason': str,
            'top_class': str,
            'top_confidence': float
        }
    """
    
    if not results:
        return {
            'classification': 'QUIET',
            'confidence': 1.0,
            'reason': 'No predictions',
            'top_class': None,
            'top_confidence': 0.0
        }
    
    top_result = results[0]
    top_class = top_result['class'].lower()
    top_conf = top_result['confidence']
    
    # Check if top class is alarm
    is_alarm = any(keyword in top_class for keyword in ALARM_KEYWORDS)
    is_quiet = any(keyword in top_class for keyword in QUIET_KEYWORDS)
    
    if is_alarm and top_conf > 0.3:
        return {
            'classification': 'ALARM',
            'confidence': top_conf,
            'reason': f'Top class "{top_result["class"]}" is alarm-like',
            'top_class': top_result['class'],
            'top_confidence': top_conf
        }
    
    elif is_quiet or top_conf < 0.3:
        return {
            'classification': 'QUIET',
            'confidence': 1.0 - top_conf if not is_quiet else 1.0,
            'reason': f'Top class "{top_result["class"]}" is quiet/non-alarm or low confidence',
            'top_class': top_result['class'],
            'top_confidence': top_conf
        }
    
    else:
        # Uncertain - check other predictions
        alarm_count = sum(1 for r in results[:3] if any(k in r['class'].lower() for k in ALARM_KEYWORDS))
        
        if alarm_count >= 2:
            return {
                'classification': 'ALARM',
                'confidence': np.mean([r['confidence'] for r in results[:3]]),
                'reason': f'Multiple alarm-like predictions in top-3',
                'top_class': top_result['class'],
                'top_confidence': top_conf
            }
        else:
            return {
                'classification': 'QUIET',
                'confidence': 0.5,
                'reason': f'Uncertain classification',
                'top_class': top_result['class'],
                'top_confidence': top_conf
            }


# ============================================================================
# Visualization (from Kaggle notebook)
# ============================================================================

def plot_audio_analysis(audio_data, results, sample_rate=16000):
    """Create visualization of audio analysis."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
    
    # Plot waveform
    time = np.arange(len(audio_data)) / sample_rate
    ax1.plot(time, audio_data)
    ax1.set_title('Audio Waveform')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Amplitude')
    ax1.grid(True)
    
    # Plot predictions
    pred_df = pd.DataFrame(results)
    
    if not pred_df.empty:
        sns.barplot(data=pred_df, x='confidence', y='class', ax=ax2)
    
    ax2.set_title('Top Sound Classifications')
    ax2.set_xlabel('Confidence Score')
    
    plt.tight_layout()
    plt.savefig('analysis_plot.png', dpi=100, bbox_inches='tight')
    print("📊 Saved: analysis_plot.png")
    plt.close()


def plot_spectrogram(audio_data, sample_rate=16000):
    """Plot the spectrogram of the audio data."""
    plt.figure(figsize=(12, 8))
    D = librosa.amplitude_to_db(np.abs(librosa.stft(audio_data)), ref=np.max)
    librosa.display.specshow(D, sr=sample_rate, x_axis='time', y_axis='hz')
    plt.colorbar(format='%+2.0f dB')
    plt.title('Audio Spectrogram')
    plt.savefig('spectrogram.png', dpi=100, bbox_inches='tight')
    print("📊 Saved: spectrogram.png")
    plt.close()


# ============================================================================
# Main Pipeline
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Emergency Vehicle Siren Detection using YAMNet"
    )
    parser.add_argument(
        "--input",
        default="microphone",
        help="Input: 'microphone' (default) or path to audio file"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3,
        help="Recording duration in seconds (microphone only, default: 3)"
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip visualization plots"
    )
    
    args = parser.parse_args()
    
    print("="*80)
    print("🚨 EMERGENCY VEHICLE SIREN DETECTION - YAMNet Pipeline")
    print("="*80 + "\n")
    
    # Step 1: Setup YAMNet
    model, class_names = setup_yamnet()
    
    # Step 2: Load audio
    print()
    audio_data = load_and_process_audio(args.input, target_sr=16000)
    
    # Step 3: Analyze audio
    print()
    results, all_scores = analyze_audio(audio_data, model, class_names, confidence_threshold=0.1)
    
    # Step 4: Binary classification
    print()
    classification = classify_alarm_or_quiet(results)
    
    # Step 5: Print results
    print("\n" + "="*80)
    print("📊 RESULTS")
    print("="*80)
    print(f"\n🎯 Classification: {classification['classification']}")
    print(f"   Confidence: {classification['confidence']:.2%}")
    print(f"   Reason: {classification['reason']}")
    
    print(f"\n📈 Top 5 YAMNet Predictions:")
    for i, result in enumerate(results[:5], 1):
        print(f"   {i}. {result['class']:<40} {result['confidence']:.3f}")
    
    # Step 6: Generate visualizations
    if not args.no_plot:
        print("\n📊 Generating visualizations...")
        plot_audio_analysis(audio_data, results)
        plot_spectrogram(audio_data)
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
