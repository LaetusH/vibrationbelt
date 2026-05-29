#!/usr/bin/env python3
"""
Create synthetic training data for alarm detection.
This allows CNN training WITHOUT recording real audio.
(For final deployment, use real recordings!)
"""

import numpy as np
from pathlib import Path
from scipy.io import wavfile
import sys


def create_alarm_sample(sr=16000, duration=3.0, alarm_type="beep"):
    """
    Create a synthetic alarm-like sound.
    
    Types:
    - "beep": Repeating high-frequency beep (typical alarm)
    - "siren": Sweeping frequency (siren sound)
    - "chirp": Modulated high frequency
    """
    t = np.arange(int(sr * duration)) / sr
    
    if alarm_type == "beep":
        # 3 kHz repeating beep (alarm-like)
        freq = 3000
        beep_pattern = np.sin(2 * np.pi * (t % 0.5) * 10)  # 0.5s cycle
        beep_pattern = (beep_pattern > 0).astype(float)  # Square wave envelope
        signal = beep_pattern * 0.5 * np.sin(2 * np.pi * freq * t)
    
    elif alarm_type == "siren":
        # Sweeping 2-4 kHz (siren)
        freq = 2000 + 2000 * np.sin(2 * np.pi * 2 * t)  # 2-4 kHz sweep
        signal = 0.5 * np.sin(2 * np.pi * freq * t)
    
    elif alarm_type == "chirp":
        # Modulated high-frequency
        freq = 4000
        envelope = 0.5 * (1 + np.sin(2 * np.pi * 3 * t))  # Vary amplitude
        signal = envelope * np.sin(2 * np.pi * freq * t)
    
    else:
        raise ValueError(f"Unknown alarm type: {alarm_type}")
    
    # Add some harmonics (makes it more realistic)
    signal += 0.2 * np.sin(2 * np.pi * (freq * 2) * t)
    signal += 0.1 * np.sin(2 * np.pi * (freq * 0.5) * t)
    
    # Normalize
    signal = np.clip(signal, -1.0, 1.0)
    return signal.astype(np.float32)


def create_silence_sample(sr=16000, duration=3.0, noise_type="quiet"):
    """
    Create non-alarm sounds.
    
    Types:
    - "quiet": Minimal background noise
    - "speech": Speech-like (0.1-0.5 kHz)
    - "music": Music-like (varied frequencies)
    - "noise": Brown noise
    """
    t = np.arange(int(sr * duration)) / sr
    
    if noise_type == "quiet":
        # Very quiet white noise
        signal = 0.02 * np.random.randn(len(t)).astype(np.float32)
    
    elif noise_type == "speech":
        # Low-frequency speech-like sound (0.1-0.5 kHz)
        freq = 200 + 150 * np.sin(2 * np.pi * 2 * t)
        signal = 0.3 * np.sin(2 * np.pi * freq * t)
        signal += 0.1 * np.random.randn(len(t))
    
    elif noise_type == "music":
        # Random musical notes (varied frequencies)
        freqs = np.random.choice([440, 494, 523, 587, 659, 740], size=len(t)//sr)
        signal = np.zeros(len(t))
        for i, freq in enumerate(freqs):
            start = i * sr
            end = start + sr
            if end > len(t):
                end = len(t)
            signal[start:end] = 0.2 * np.sin(2 * np.pi * freq * t[start:end])
        signal += 0.05 * np.random.randn(len(t))
    
    elif noise_type == "noise":
        # Brown noise (low-frequency)
        white = np.random.randn(len(t))
        brown = np.zeros(len(t))
        for i in range(1, len(t)):
            brown[i] = 0.9 * brown[i-1] + 0.1 * white[i]
        signal = 0.15 * brown
    
    else:
        raise ValueError(f"Unknown noise type: {noise_type}")
    
    signal = np.clip(signal, -1.0, 1.0)
    return signal.astype(np.float32)


def main():
    sr = 16000
    duration = 3.0
    
    # Create output folders
    data_dir = Path("training_data")
    alarm_dir = data_dir / "alarm"
    silence_dir = data_dir / "silence"
    
    alarm_dir.mkdir(parents=True, exist_ok=True)
    silence_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("🎵 SYNTHETIC TRAINING DATA GENERATOR")
    print("=" * 70)
    print(f"\nSettings:")
    print(f"  Sample Rate: {sr} Hz")
    print(f"  Duration: {duration}s per sample")
    print(f"  Output: {data_dir.absolute()}\n")
    
    # Generate alarm samples
    print("🔴 Generating ALARM samples...")
    alarm_types = ["beep", "siren", "chirp"]
    for type_idx, alarm_type in enumerate(alarm_types):
        for sample_idx in range(40):  # 40 samples per type
            signal = create_alarm_sample(sr, duration, alarm_type)
            
            # Add some variation
            signal = signal * (0.8 + 0.4 * np.random.rand())  # Random volume
            signal = np.clip(signal, -1.0, 1.0)
            
            filename = alarm_dir / f"alarm_{type_idx:02d}_{sample_idx:03d}.wav"
            audio_int16 = (signal * 32767).astype(np.int16)
            wavfile.write(filename, sr, audio_int16)
            
            if (sample_idx + 1) % 10 == 0:
                print(f"  {alarm_type}: {sample_idx + 1}/40")
    
    # Generate silence/noise samples
    print("\n🔇 Generating SILENCE/NOISE samples...")
    noise_types = ["quiet", "speech", "music", "noise"]
    for type_idx, noise_type in enumerate(noise_types):
        for sample_idx in range(40):  # 40 samples per type
            signal = create_silence_sample(sr, duration, noise_type)
            
            # Add some variation
            signal = signal * (0.8 + 0.4 * np.random.rand())
            signal = np.clip(signal, -1.0, 1.0)
            
            filename = silence_dir / f"silence_{type_idx:02d}_{sample_idx:03d}.wav"
            audio_int16 = (signal * 32767).astype(np.int16)
            wavfile.write(filename, sr, audio_int16)
            
            if (sample_idx + 1) % 10 == 0:
                print(f"  {noise_type}: {sample_idx + 1}/40")
    
    # Show statistics
    alarm_count = len(list(alarm_dir.glob("*.wav")))
    silence_count = len(list(silence_dir.glob("*.wav")))
    total = alarm_count + silence_count
    
    print("\n" + "=" * 70)
    print("✅ TRAINING DATA CREATED!")
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"  Alarm samples:   {alarm_count}")
    print(f"  Silence samples: {silence_count}")
    print(f"  Total:           {total}")
    print(f"\n📁 Location: {data_dir.absolute()}")
    print(f"\n⚠️  NOTE: This is SYNTHETIC data!")
    print(f"   For production, record REAL alarm sounds!")


if __name__ == "__main__":
    main()
