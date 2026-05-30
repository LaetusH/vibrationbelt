#!/usr/bin/env python3
"""
Silence/Background Noise Recorder - Collect diverse non-alarm sounds
Records different types of background noise for training the CNN model
to distinguish between alarms and normal sounds.

Silence types:
  - Stille (leerer Raum)
  - Ambient/Hintergrund (Büro, Straße)
  - Musik/Radio
  - Gespräche
  - Maschinenlärm
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


class SilenceRecorder:
    """Records background noise / non-alarm sounds for training."""
    
    SILENCE_TYPES = {
        "quiet": {
            "name": "🔇 Stille (leerer Raum)",
            "color": "⚪",
            "description": "Gar kein Sound - so leise wie möglich",
            "prefix": "quiet",
        },
        "ambient": {
            "name": "🌍 Ambient (Büro/Straße)",
            "color": "⚫",
            "description": "Hintergrund-Lärm: Verkehr, Büro-Geräusche, etc.",
            "prefix": "ambient",
        },
        "music": {
            "name": "🎵 Musik/Radio",
            "color": "🟣",
            "description": "Musik, Podcast, Radio abspielen",
            "prefix": "music",
        },
        "speech": {
            "name": "👥 Gespräche",
            "color": "🟢",
            "description": "Normale Sprache, Konversation",
            "prefix": "speech",
        },
        "machinery": {
            "name": "⚙️  Maschinenlärm",
            "color": "🟤",
            "description": "Ventilator, Bohrer, Motor, etc.",
            "prefix": "machinery",
        },
    }
    
    def __init__(self, sample_rate=16000, chunk_duration=3.0):
        self.sr = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        
        # Create data folders
        self.data_dir = Path("training_data")
        self.silence_dir = self.data_dir / "silence"
        
        self.silence_dir.mkdir(parents=True, exist_ok=True)
        
        # Count existing files
        self.existing_silence = len(list(self.silence_dir.glob("*.wav")))
        
        print(f"📁 Data folder: {self.data_dir.absolute()}")
        print(f"   Existing silence samples: {self.existing_silence}")
    
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
    
    def analyze_silence_quality(self, audio, silence_type):
        """Analyze the recorded silence/noise."""
        max_amp = float(np.abs(audio).max())
        rms = float(np.sqrt(np.mean(audio**2)))
        
        # Frequency analysis
        fft = np.fft.rfft(audio)
        power = np.abs(fft) ** 2
        
        # Energy in alarm frequency range (2-4 kHz alarm)
        freq_resolution = self.sr / len(audio)
        alarm_freq_start = int(2000 / freq_resolution)
        alarm_freq_end = int(4000 / freq_resolution)
        alarm_power = np.sum(power[alarm_freq_start:alarm_freq_end])
        total_power = np.sum(power)
        
        if total_power > 0:
            alarm_ratio = alarm_power / total_power
        else:
            alarm_ratio = 0
        
        return {
            "max_amplitude": max_amp,
            "rms": rms,
            "alarm_frequency_ratio": alarm_ratio,
        }
    
    def print_silence_analysis(self, analysis, silence_type):
        """Print analysis results and quality assessment."""
        max_amp = analysis["max_amplitude"]
        rms = analysis["rms"]
        alarm_ratio = analysis["alarm_frequency_ratio"]
        
        print(f"\n📊 Aufnahme-Analyse:")
        print(f"   Max Amplitude:     {max_amp:.4f}")
        print(f"   RMS Level:         {rms:.4f}")
        print(f"   Alarm-Freq Ratio:  {alarm_ratio:.2%}")
        
        # Quality assessment
        if silence_type == "quiet":
            if max_amp < 0.02:
                print(f"   ✅ Sehr gut! (fast perfekte Stille)")
                quality = "excellent"
            elif max_amp < 0.05:
                print(f"   ✅ Gut (minimales Background-Rauschen)")
                quality = "good"
            elif max_amp < 0.1:
                print(f"   ⚠️  OK aber etwas Lärm")
                quality = "acceptable"
            else:
                print(f"   ❌ Zu viel Lärm für 'Stille'")
                quality = "poor"
        
        elif silence_type == "ambient":
            if 0.05 < max_amp < 0.3:
                print(f"   ✅ Gut - natürlicher Hintergrund")
                quality = "good"
            elif max_amp < 0.05:
                print(f"   ⚠️  Zu leise - muss lauter sein")
                quality = "poor"
            elif max_amp > 0.5:
                print(f"   ⚠️  Zu laut - weniger Lärm bitte")
                quality = "poor"
            else:
                print(f"   ✅ OK")
                quality = "acceptable"
        
        elif silence_type == "music":
            if 0.1 < max_amp < 0.6:
                print(f"   ✅ Gutes Musik-Level")
                quality = "good"
            elif alarm_ratio > 0.3:
                print(f"   ⚠️  Warnung: Viel Energie in Alarm-Frequenzen!")
                quality = "acceptable"
            else:
                print(f"   ✅ OK")
                quality = "good"
        
        elif silence_type == "speech":
            if 0.08 < max_amp < 0.4:
                print(f"   ✅ Gutes Sprach-Level")
                quality = "good"
            else:
                print(f"   ⚠️  Level etwas hoch/tief")
                quality = "acceptable"
        
        elif silence_type == "machinery":
            if 0.1 < max_amp < 0.5:
                print(f"   ✅ Guter Maschinenlärm")
                quality = "good"
            else:
                print(f"   ⚠️  Maschinenlärm-Level außerhalb ideal")
                quality = "acceptable"
        
        return quality
    
    def confirm_recording(self, analysis, silence_type):
        """Ask user to confirm or retry recording."""
        quality = self.print_silence_analysis(analysis, silence_type)
        
        while True:
            choice = input(f"\n  [Y] Speichern | [N] Verwerfen & Wiederholen: ").strip().upper()
            
            if choice in ["Y", "YES"]:
                return True
            elif choice in ["N", "NO"]:
                return False
            else:
                print("  ❌ Ungültig (Y/N)")
    
    def save_silence(self, audio, silence_type):
        """Save silence sample with type prefix."""
        existing = len(list(self.silence_dir.glob(f"{silence_type}_*.wav")))
        filename = self.silence_dir / f"{silence_type}_{existing:02d}.wav"
        
        audio_int16 = (audio * 32767).astype(np.int16)
        wavfile.write(filename, self.sr, audio_int16)
        
        return filename
    
    def record_silence_samples(self, silence_type, count=10):
        """Record multiple samples of one silence type."""
        info = self.SILENCE_TYPES[silence_type]
        color = info["color"]
        name = info["name"]
        desc = info["description"]
        prefix = info["prefix"]
        
        print(f"\n{'='*70}")
        print(f"{color} {name.upper()}")
        print(f"{'='*70}")
        print(f"\nBeschreibung: {desc}")
        print(f"Ziel: {count} Samples à 3 Sekunden = {count*3} Sekunden total")
        print(f"\nProzess:")
        print(f"  1. Ich sage 'RECORDING NOW'")
        print(f"  2. Du machst die passenden Geräusche")
        print(f"  3. Nach 3s zeige ich die Qualität")
        print(f"  4. Du bestätigst oder wiederholst\n")
        
        input("📍 Setup: Bereit? (Enter zum Start)")
        
        successful = 0
        failed = 0
        attempts = 0
        
        while successful < count:
            attempts += 1
            print(f"\n[{successful+1}/{count}] Attempt {attempts}", end="")
            
            self.countdown(seconds=3)
            audio, max_amp = self.record_chunk()
            
            # Analyze and show confirmation dialog
            analysis = self.analyze_silence_quality(audio, silence_type)
            
            if self.confirm_recording(analysis, silence_type):
                filename = self.save_silence(audio, silence_type)
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
    
    def show_stats(self):
        """Show recording statistics."""
        print("\n" + "="*70)
        print("📊 STATISTIKEN")
        print("="*70)
        
        total_silence = 0
        type_counts = {}
        
        for silence_type in self.SILENCE_TYPES.keys():
            count = len(list(self.silence_dir.glob(f"{silence_type}_*.wav")))
            if count > 0:
                type_counts[silence_type] = count
                color = self.SILENCE_TYPES[silence_type]["color"]
                print(f"  {color} {silence_type.upper():12} : {count:3d} samples")
                total_silence += count
        
        print(f"\n  Total:           {total_silence} silence/noise samples")
        print(f"  Goal:            ≥50 samples (verschiedene Typen)")
        
        if total_silence >= 50 and len(type_counts) >= 3:
            print(f"\n  ✅ READY FOR TRAINING!")
            print(f"     python prepare_training_data.py")
            print(f"     python train_cnn_model.py")
        else:
            if total_silence < 50:
                remaining = 50 - total_silence
                print(f"\n  ⏳ {remaining} mehr Samples nötig")
            if len(type_counts) < 3:
                print(f"  ⏳ Mehr Varianten nötig (mind. 3 verschiedene Typen)")
    
    def interactive_menu(self):
        """Main interactive menu."""
        print("\n" + "="*70)
        print("🎙️  SILENCE/BACKGROUND NOISE RECORDER")
        print("="*70)
        print("\nVerfügbare Silence-Typen:")
        
        for i, (key, info) in enumerate(self.SILENCE_TYPES.items(), 1):
            print(f"  [{i}] {info['color']} {info['name']}")
        
        print(f"  [0] Zeige Statistiken")
        print(f"  [9] Fertig - Trainieren!")
        
        total_silence = len(list(self.silence_dir.glob("*.wav")))
        print(f"\n📊 Status: {total_silence} Silence-Samples vorhanden")
    
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
                silence_type = list(self.SILENCE_TYPES.keys())[idx]
                count = self.record_silence_samples(silence_type, count=10)
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
    recorder = SilenceRecorder(sample_rate=16000, chunk_duration=3.0)
    recorder.run()
