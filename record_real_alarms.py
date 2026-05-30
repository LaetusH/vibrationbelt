#!/usr/bin/env python3
"""
Real Alarm Sound Recorder - Collect diverse alarm types
Records 5 different alarm categories with clear countdown prompts.
"""

import os
import sys
import time
import numpy as np
from pathlib import Path

try:
    import sounddevice as sd
    import scipy.io.wavfile as wavfile
except ImportError:
    print("❌ Missing dependencies:")
    print("   pip install sounddevice scipy")
    sys.exit(1)


class RealAlarmRecorder:
    """Records real alarm sounds for training."""
    
    ALARM_TYPES = {
        "fire": {
            "name": "🔥 Feuerwehr-Sirene",
            "color": "🔴",
            "prefix": "fire",
        },
        "ambulance": {
            "name": "🚑 Krankenwagen-Sirene",
            "color": "🟠",
            "prefix": "ambulance",
        },
        "smoke": {
            "name": "💨 Rauchmelder",
            "color": "🟡",
            "prefix": "smoke",
        },
        "police": {
            "name": "🚓 Polizeiwagen",
            "color": "🔵",
            "prefix": "police",
        },
        "horn": {
            "name": "🚙 Autohupe",
            "color": "🟢",
            "prefix": "horn",
        },
    }
    
    def __init__(self, sample_rate=16000, chunk_duration=3.0):
        self.sr = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        
        # Create data folders
        self.data_dir = Path("training_data")
        self.alarm_dir = self.data_dir / "alarm"
        self.silence_dir = self.data_dir / "silence"
        
        self.alarm_dir.mkdir(parents=True, exist_ok=True)
        self.silence_dir.mkdir(parents=True, exist_ok=True)
        
        # Count existing files
        self.existing_alarms = len(list(self.alarm_dir.glob("*.wav")))
        self.existing_noise = len(list(self.silence_dir.glob("*.wav")))
        
        print(f"📁 Data folder: {self.data_dir.absolute()}")
        print(f"   Existing: {self.existing_alarms} alarm samples, {self.existing_noise} noise samples")
    
    def countdown(self, seconds=3):
        """Visual countdown before recording."""
        for i in range(seconds, 0, -1):
            print(f"\r⏱️  {i}s ... ", end="", flush=True)
            time.sleep(1)
        print("\r🔴 RECORDING NOW!  \n", flush=True)
    
    def record_chunk(self):
        """Record a single audio chunk."""
        samples = int(self.sr * self.chunk_duration)
        
        audio = sd.rec(samples, samplerate=self.sr, channels=1, dtype='float32')
        sd.wait()
        
        # Normalize
        audio = np.clip(audio.flatten(), -1.0, 1.0)
        max_amp = float(np.abs(audio).max())
        
        return audio, max_amp
    
    def confirm_recording(self, max_amp):
        """Ask user to confirm or retry recording."""
        print(f"\n📊 Aufnahme-Details:")
        print(f"   Amplitude: {max_amp:.3f}")
        print(f"   Dauer: {self.chunk_duration}s")
        
        if max_amp < 0.01:
            print(f"   ⚠️  WARNUNG: Signal sehr leise! (< 0.01)")
        elif max_amp < 0.05:
            print(f"   ⚠️  Signal leise, evtl. lauter abspielen")
        elif max_amp > 0.9:
            print(f"   ⚠️  Signal sehr laut! Könnte verzerrt sein")
        else:
            print(f"   ✅ Signal OK")
        
        while True:
            choice = input(f"\n  [Y] Speichern | [N] Verwerfen & Wiederholen: ").strip().upper()
            
            if choice in ["Y", "YES"]:
                return True
            elif choice in ["N", "NO"]:
                return False
            else:
                print("  ❌ Ungültig (Y/N)")
    
    def save_alarm(self, audio, alarm_type):
        """Save alarm sample with type prefix."""
        existing = len(list(self.alarm_dir.glob(f"{alarm_type}_*.wav")))
        filename = self.alarm_dir / f"{alarm_type}_{existing:02d}.wav"
        
        audio_int16 = (audio * 32767).astype(np.int16)
        wavfile.write(filename, self.sr, audio_int16)
        
        return filename
    
    def save_noise(self):
        """Save background noise sample."""
        existing = len(list(self.silence_dir.glob("noise_*.wav")))
        filename = self.silence_dir / f"noise_{existing:02d}.wav"
        
        audio_int16 = (np.random.randn(int(self.sr * self.chunk_duration)) * 0.01).astype(np.int16)
        wavfile.write(filename, self.sr, audio_int16)
        
        return filename
    
    def record_alarm_samples(self, alarm_type, count=10):
        """Record multiple samples of one alarm type."""
        info = self.ALARM_TYPES[alarm_type]
        color = info["color"]
        name = info["name"]
        prefix = info["prefix"]
        
        print(f"\n{'='*70}")
        print(f"{color} {name.upper()}")
        print(f"{'='*70}")
        print(f"\nZiel: {count} Samples à 3 Sekunden = {count*3} Sekunden total")
        print(f"\nProzess:")
        print(f"  1. Ich sage 'RECORDING NOW'")
        print(f"  2. Du spielst den Sound ab")
        print(f"  3. Nach 3s zeige ich die Qualität")
        print(f"  4. Du bestätigst oder wiederholst\n")
        
        input("📍 Setup: Sound bereit? (Enter zum Start)")
        
        successful = 0
        failed = 0
        attempts = 0
        
        while successful < count:
            attempts += 1
            print(f"\n[{successful+1}/{count}] Attempt {attempts}", end="")
            
            self.countdown(seconds=3)
            audio, max_amp = self.record_chunk()
            
            # Show confirmation dialog
            if self.confirm_recording(max_amp):
                filename = self.save_alarm(audio, prefix)
                print(f"✅ GESPEICHERT - {filename.name}")
                successful += 1
                
                if successful < count:
                    print(f"   Nächstes Sample in 2s...", end="")
                    time.sleep(2)
                    print("\r                      ", end="\r")
            else:
                print(f"🔄 Verworfen - Nächster Versuch")
                failed += 1
                time.sleep(1)
        
        print(f"\n{'─'*70}")
        print(f"✅ Fertig: {successful}/{count} erfolgreich ({attempts} Versuche total)")
        
        return successful
    
    def interactive_menu(self):
        """Main interactive menu."""
        print("\n" + "="*70)
        print("🎙️  REAL ALARM SOUND RECORDER")
        print("="*70)
        print("\nVerfügbare Alarm-Typen:")
        
        for i, (key, info) in enumerate(self.ALARM_TYPES.items(), 1):
            print(f"  [{i}] {info['color']} {info['name']}")
        
        print(f"  [0] Zeige Statistiken")
        print(f"  [9] Fertig - Trainieren!")
        
        total_alarms = len(list(self.alarm_dir.glob("*.wav")))
        print(f"\n📊 Status: {total_alarms} Alarm-Samples vorhanden")
        
    def show_stats(self):
        """Show recording statistics."""
        print("\n" + "="*70)
        print("📊 STATISTIKEN")
        print("="*70)
        
        total_alarms = 0
        for alarm_type in self.ALARM_TYPES.keys():
            count = len(list(self.alarm_dir.glob(f"{alarm_type}_*.wav")))
            if count > 0:
                print(f"  {self.ALARM_TYPES[alarm_type]['color']} {alarm_type.upper():12} : {count:3d} samples")
                total_alarms += count
        
        noise_count = len(list(self.silence_dir.glob("noise_*.wav")))
        
        print(f"\n  Total:           {total_alarms} alarm samples")
        print(f"  Goal:            ≥50 samples")
        
        if total_alarms >= 50:
            print(f"\n  ✅ READY FOR TRAINING!")
            print(f"     python prepare_training_data.py")
            print(f"     python train_cnn_model.py")
        else:
            remaining = 50 - total_alarms
            print(f"\n  ⏳ {remaining} mehr Samples nötig")
    
    def run(self):
        """Run interactive recording session."""
        self.interactive_menu()
        
        total_recorded = 0
        
        while True:
            choice = input("\nWähle (0-9): ").strip()
            
            if choice == "0":
                self.show_stats()
            
            elif choice in "12345":
                idx = int(choice) - 1
                alarm_type = list(self.ALARM_TYPES.keys())[idx]
                count = self.record_alarm_samples(alarm_type, count=10)
                total_recorded += count
            
            elif choice == "9":
                print("\n" + "="*70)
                print("✅ FERTIG!")
                print("="*70)
                self.show_stats()
                print(f"\nNächster Schritt:")
                print(f"  python prepare_training_data.py")
                print(f"  python train_cnn_model.py")
                break
            
            else:
                print("❌ Ungültige Eingabe (0-9)")


if __name__ == "__main__":
    recorder = RealAlarmRecorder(sample_rate=16000, chunk_duration=3.0)
    recorder.run()
