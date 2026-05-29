#!/usr/bin/env python3
"""
Quick training data recorder for alarm detection.
Records audio chunks and saves as WAV files.
"""

import os
import sys
import time
import numpy as np
from pathlib import Path

# Try to import audio libraries
try:
    import sounddevice as sd
    import scipy.io.wavfile as wavfile
except ImportError:
    print("❌ Missing dependencies. Install with:")
    print("   pip install sounddevice scipy")
    sys.exit(1)


class TrainingDataRecorder:
    """Records audio samples for CNN training."""
    
    def __init__(self, sample_rate=16000, chunk_duration=3.0):
        """
        Args:
            sample_rate: Recording sample rate (Hz)
            chunk_duration: Length of each recording (seconds)
        """
        self.sr = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        
        # Create data folders
        self.data_dir = Path("training_data")
        self.alarm_dir = self.data_dir / "alarm"
        self.silence_dir = self.data_dir / "silence"
        
        self.alarm_dir.mkdir(parents=True, exist_ok=True)
        self.silence_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Data folder: {self.data_dir.absolute()}")
    
    def record_chunk(self, duration=None):
        """Record a single audio chunk."""
        if duration is None:
            duration = self.chunk_duration
        
        samples = int(self.sr * duration)
        print(f"🔴 Recording {duration}s... ", end="", flush=True)
        
        audio = sd.rec(samples, samplerate=self.sr, channels=1, dtype='float32')
        sd.wait()
        
        # Normalize to -1..1
        audio = np.clip(audio.flatten(), -1.0, 1.0)
        
        print(f"✓ ({np.abs(audio).max():.2f} max amplitude)")
        return audio
    
    def save_chunk(self, audio, category, index):
        """Save recorded audio as WAV file."""
        if category == "alarm":
            output_dir = self.alarm_dir
            prefix = "alarm"
        elif category == "silence":
            output_dir = self.silence_dir
            prefix = "silence"
        else:
            raise ValueError(f"Unknown category: {category}")
        
        filename = output_dir / f"{prefix}_{index:03d}.wav"
        
        # Convert to int16 for WAV
        audio_int16 = (audio * 32767).astype(np.int16)
        wavfile.write(filename, self.sr, audio_int16)
        
        print(f"   💾 Saved: {filename.name}")
        return filename
    
    def interactive_session(self):
        """Interactive recording session."""
        print("\n" + "=" * 70)
        print("🎙️  TRAINING DATA RECORDER")
        print("=" * 70)
        print(f"\nSettings:")
        print(f"  Sample Rate: {self.sr} Hz")
        print(f"  Chunk Duration: {self.chunk_duration}s")
        print(f"  Output: {self.data_dir.absolute()}\n")
        
        while True:
            print("\nOptions:")
            print("  [1] Record ALARM sample (3s)")
            print("  [2] Record SILENCE/NOISE sample (3s)")
            print("  [3] Record ALARM batch (10x3s)")
            print("  [4] Record SILENCE batch (10x3s)")
            print("  [5] Show statistics")
            print("  [6] Exit")
            
            choice = input("\nChoice (1-6): ").strip()
            
            if choice == "1":
                audio = self.record_chunk()
                idx = len(list(self.alarm_dir.glob("*.wav"))) + 1
                self.save_chunk(audio, "alarm", idx)
            
            elif choice == "2":
                audio = self.record_chunk()
                idx = len(list(self.silence_dir.glob("*.wav"))) + 1
                self.save_chunk(audio, "silence", idx)
            
            elif choice == "3":
                print("\n🔴 Recording 10 ALARM samples (30 seconds total)")
                for i in range(10):
                    print(f"\nSample {i+1}/10:")
                    audio = self.record_chunk()
                    idx = len(list(self.alarm_dir.glob("*.wav"))) + 1
                    self.save_chunk(audio, "alarm", idx)
                    if i < 9:
                        print("   (next sample in 2s)", end="")
                        time.sleep(2)
                        print("\r                   ", end="\r")
            
            elif choice == "4":
                print("\n🔇 Recording 10 SILENCE samples (30 seconds total)")
                for i in range(10):
                    print(f"\nSample {i+1}/10:")
                    audio = self.record_chunk()
                    idx = len(list(self.silence_dir.glob("*.wav"))) + 1
                    self.save_chunk(audio, "silence", idx)
                    if i < 9:
                        print("   (next sample in 2s)", end="")
                        time.sleep(2)
                        print("\r                   ", end="\r")
            
            elif choice == "5":
                alarm_count = len(list(self.alarm_dir.glob("*.wav")))
                silence_count = len(list(self.silence_dir.glob("*.wav")))
                total = alarm_count + silence_count
                
                print(f"\n📊 Statistics:")
                print(f"  Alarm samples:   {alarm_count}")
                print(f"  Silence samples: {silence_count}")
                print(f"  Total:           {total}")
                print(f"\n  ✅ Goal: 200+ total samples (100+ each type)")
                
                if total >= 200:
                    print("  🎉 READY FOR TRAINING!")
            
            elif choice == "6":
                print("\n✓ Goodbye!")
                break
            
            else:
                print("❌ Invalid choice")
    
    def quick_batch(self, category, count=10):
        """Quick batch recording without interactive prompts."""
        print(f"\n🔴 Quick Recording: {count}x ALARM samples")
        
        for i in range(count):
            print(f"\n[{i+1}/{count}] Preparing to record...", flush=True)
            time.sleep(1)
            
            audio = self.record_chunk(duration=self.chunk_duration)
            idx = len(list(self.alarm_dir.glob("*.wav"))) + 1
            self.save_chunk(audio, category, idx)


if __name__ == "__main__":
    recorder = TrainingDataRecorder(sample_rate=16000, chunk_duration=3.0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        # Quick batch mode (for testing)
        recorder.quick_batch("alarm", count=3)
    else:
        # Interactive mode
        recorder.interactive_session()
