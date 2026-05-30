#!/usr/bin/env python3
"""
Live Microphone Test - Continuous YAMNet Classification
Shows all Top-5 classifications every 250ms
"""

import sys
import time
import numpy as np
from pathlib import Path
from collections import deque

try:
    import sounddevice as sd
    import tensorflow as tf
    import tensorflow_hub as hub
    import csv
    import io
    import urllib.request
except ImportError:
    print("❌ Missing dependencies:")
    print("   pip install sounddevice tensorflow tensorflow-hub")
    sys.exit(1)


# YAMNet known alarm classes
YAMNET_ALARM_CLASSES = {
    399: "🚨 Siren",
    400: "🚓 Police",
    401: "🚑 Ambulance",
    402: "🚒 Fire Engine",
    377: "🚙 Horn",
    378: "🚗 Beep",
}


def load_yamnet_classes():
    """Load YAMNet class names from CSV."""
    print("📥 Loading YAMNet class names...")
    
    # Try to get from GitHub
    try:
        url = "https://raw.githubusercontent.com/tensorflow/models/master/research/audio_recognition/yamnet/yamnet_class_map.csv"
        response = urllib.request.urlopen(url, timeout=5)
        csv_data = response.read().decode('utf-8')
        
        reader = csv.reader(io.StringIO(csv_data))
        classes = {}
        for row in reader:
            if len(row) >= 3:
                try:
                    idx = int(row[0])
                    name = row[2]
                    classes[idx] = name
                except:
                    pass
        
        if len(classes) > 400:
            print(f"   ✅ Loaded {len(classes)} YAMNet classes")
            return classes
    except Exception as e:
        print(f"   ⚠️  Could not load from GitHub: {e}")
    
    # Fallback: hardcoded common classes
    print("   Using fallback class list...")
    fallback = {
        0: "Speech",
        1: "Child speech",
        68: "Music",
        69: "Musical instrument",
        117: "Applause",
        146: "Wind",
        149: "Thunderstorm",
        377: "Vehicle horn, car horn, honking",
        378: "Beep, bleep",
        379: "Race car, accelerating",
        383: "Truck",
        399: "Siren",
        400: "Police car siren",
        401: "Ambulance siren",
        402: "Fire engine, fire truck, siren",
    }
    
    # Fill in missing indices
    for i in range(521):
        if i not in fallback:
            fallback[i] = f"Class {i}"
    
    return fallback


class LiveMicTest:
    """Continuous microphone capture with YAMNet classification."""
    
    def __init__(self, sample_rate=16000, chunk_duration=0.25):
        self.sr = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        
        # Load model and classes
        print("📥 Loading YAMNet model...")
        self.model = hub.load('https://www.kaggle.com/models/google/yamnet/TensorFlow2/yamnet/1')
        print("✅ YAMNet loaded")
        
        self.classes = load_yamnet_classes()
        
        # History
        self.amplitude_history = deque(maxlen=30)
        self.rms_history = deque(maxlen=30)
        self.classification_history = deque(maxlen=10)
        
        self.total_chunks = 0
    
    def record_chunk(self, device=None):
        """Record one chunk from microphone."""
        try:
            audio = sd.rec(
                self.chunk_samples,
                samplerate=self.sr,
                channels=1,
                dtype='float32',
                device=device,
                blocking=True
            )
            
            audio = np.clip(audio.flatten(), -1.0, 1.0)
            return audio, True
        
        except Exception as e:
            print(f"❌ Recording error: {e}")
            return None, False
    
    def analyze_audio(self, audio):
        """Analyze audio levels."""
        if audio is None:
            return None
        
        max_amp = float(np.abs(audio).max())
        rms = float(np.sqrt(np.mean(audio**2)))
        
        return {
            'max_amplitude': max_amp,
            'rms': rms,
            'audio': audio,
        }
    
    def classify_with_yamnet(self, audio):
        """Run YAMNet classification - return top-5 predictions with names."""
        try:
            scores, _, _ = self.model(audio)
            scores_np = scores[0].numpy()
            
            # Get top-5 classes
            top_5_indices = np.argsort(scores_np)[-5:][::-1]
            top_5_scores = scores_np[top_5_indices]
            
            results = []
            for class_id, conf in zip(top_5_indices, top_5_scores):
                class_id = int(class_id)
                class_name = self.classes.get(class_id, f"Class {class_id}")
                results.append({
                    'id': class_id,
                    'name': class_name,
                    'confidence': float(conf)
                })
            
            return results
        
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def draw_level_meter(self, value, max_val=1.0, width=15):
        """Draw ASCII level meter."""
        normalized = min(1.0, value / max(max_val, 0.01))
        filled = int(normalized * width)
        meter = "█" * filled + "░" * (width - filled)
        return meter
    
    def print_line(self, analysis, predictions):
        """Print one line with current classification."""
        max_amp = analysis['max_amplitude']
        rms = analysis['rms']
        
        self.amplitude_history.append(max_amp)
        self.rms_history.append(rms)
        
        # Calculate stats
        avg_amp = np.mean(self.amplitude_history) if self.amplitude_history else 0
        max_seen = max(self.amplitude_history) if self.amplitude_history else 0
        
        # Clear line
        print("\r" + " " * 200, end="")
        print("\r", end="")
        
        # Amplitude and RMS meters
        amp_meter = self.draw_level_meter(max_amp, max_val=1.0, width=15)
        rms_meter = self.draw_level_meter(rms, max_val=0.2, width=12)
        
        print(f"📊 [{amp_meter}] {max_amp:.4f} | RMS [{rms_meter}] {rms:.4f} | ", end="")
        
        # Classification
        if predictions:
            pred_str = ""
            for rank, pred in enumerate(predictions[:5], 1):
                name = pred['name']
                conf = pred['confidence']
                # Truncate long names
                if len(name) > 25:
                    name = name[:22] + "..."
                pred_str += f"{rank}. {name} ({conf*100:.0f}%) | "
            
            print(pred_str, end="")
        else:
            print("❌ No classification", end="")
        
        sys.stdout.flush()
    
    def print_audio_quality_assessment(self):
        """Print assessment of microphone quality."""
        if not self.amplitude_history:
            return
        
        avg_amp = np.mean(self.amplitude_history)
        max_amp = max(self.amplitude_history)
        
        print("\n\n" + "="*100)
        print("📈 AUDIO QUALITY ASSESSMENT")
        print("="*100)
        print(f"\nAmplitude Stats:")
        print(f"  Average: {avg_amp:.4f}")
        print(f"  Peak:    {max_amp:.4f}")
        
        # Quality assessment
        if max_amp < 0.01:
            print(f"\n⚠️  WARNUNG: Signal ist SEHR LEISE!")
            print(f"   - Mikrofon könnte zu weit weg sein")
            print(f"   - Mikrofon-Level muss erhöht werden")
            print(f"   - Laptop-Mikrofon-Einstellungen überprüfen")
        
        elif max_amp < 0.05:
            print(f"\n⚠️  Signal ist zu leise")
            print(f"   - Sollte mindestens 0.1 sein für gute Erkennung")
        
        elif max_amp < 0.1:
            print(f"\n🟡 Signal ist etwas leise")
            print(f"   - OK aber nicht optimal")
        
        elif max_amp < 0.5:
            print(f"\n✅ Signal ist GUT")
        
        else:
            print(f"\n⚠️  Signal ist zu LAUT (könnte verzerren)")
        
        print("="*100 + "\n")
    
    def run(self, device=None, duration_sec=60):
        """Run the test."""
        print("="*100)
        print("🎤 LIVE MICROPHONE TEST - YAMNet Classification (every 250ms)")
        print("="*100)
        print(f"\nRecording for {duration_sec} seconds...")
        print("🔊 Speak, play sound, or generate noise near the microphone\n")
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_sec:
                # Record chunk
                audio, success = self.record_chunk(device=device)
                
                if not success:
                    time.sleep(0.1)
                    continue
                
                # Analyze
                analysis = self.analyze_audio(audio)
                
                # Classify with YAMNet
                predictions = self.classify_with_yamnet(audio)
                
                # Display
                self.print_line(analysis, predictions)
                
                self.total_chunks += 1
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped by user")
        
        finally:
            print()
            self.print_audio_quality_assessment()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Live microphone test with YAMNet")
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Audio device ID"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)"
    )
    
    args = parser.parse_args()
    
    tester = LiveMicTest(sample_rate=16000, chunk_duration=0.25)
    tester.run(device=args.device, duration_sec=args.duration)


if __name__ == "__main__":
    main()
