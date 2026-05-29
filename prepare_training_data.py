#!/usr/bin/env python3
"""
Convert WAV files to spectrograms for CNN training.
"""

import numpy as np
from pathlib import Path
from scipy.io import wavfile
import sys

# Import spectrogram generator
from analysis_engine.spectrogram.generator import SpectrogramGenerator


def prepare_training_data(wav_dir="training_data", output_dir="train_spectrograms"):
    """
    Convert all WAV files in wav_dir to spectrograms.
    
    Input structure:
        training_data/
            ├── alarm/
            │   ├── alarm_00_000.wav
            │   └── ...
            └── silence/
                ├── silence_00_000.wav
                └── ...
    
    Output structure:
        train_spectrograms/
            ├── alarm/
            │   ├── alarm_00_000.npy
            │   └── ...
            └── noise/  (renamed from silence)
                ├── silence_00_000.npy
                └── ...
    """
    wav_path = Path(wav_dir)
    out_path = Path(output_dir)
    
    # Create output directories
    (out_path / "alarm").mkdir(parents=True, exist_ok=True)
    (out_path / "noise").mkdir(parents=True, exist_ok=True)
    
    # Initialize spectrogram generator
    spec_gen = SpectrogramGenerator(sr=16000)
    
    print("=" * 70)
    print("🎵 PREPARING TRAINING DATA (WAV → Spectrogram)")
    print("=" * 70)
    
    # Process alarm samples
    print("\n🔴 Processing ALARM samples...")
    alarm_count = 0
    for wav_file in (wav_path / "alarm").glob("*.wav"):
        try:
            # Read WAV
            sr, audio = wavfile.read(wav_file)
            
            # Convert to float if needed
            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            elif audio.dtype == np.int32:
                audio = audio.astype(np.float32) / 2147483648.0
            else:
                audio = audio.astype(np.float32)
            
            # Handle stereo → mono
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            
            # Generate spectrogram
            spec = spec_gen.generate(audio, normalize=True)
            
            # Save as NPY
            output_file = out_path / "alarm" / wav_file.stem
            np.save(f"{output_file}.npy", spec.astype(np.float32))
            
            alarm_count += 1
            if alarm_count % 20 == 0:
                print(f"  Processed: {alarm_count}")
        
        except Exception as e:
            print(f"  ❌ Error processing {wav_file.name}: {e}")
    
    # Process silence/noise samples
    print(f"\n🔇 Processing SILENCE/NOISE samples...")
    noise_count = 0
    for wav_file in (wav_path / "silence").glob("*.wav"):
        try:
            # Read WAV
            sr, audio = wavfile.read(wav_file)
            
            # Convert to float if needed
            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            elif audio.dtype == np.int32:
                audio = audio.astype(np.float32) / 2147483648.0
            else:
                audio = audio.astype(np.float32)
            
            # Handle stereo → mono
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            
            # Generate spectrogram
            spec = spec_gen.generate(audio, normalize=True)
            
            # Save as NPY
            output_file = out_path / "noise" / wav_file.stem
            np.save(f"{output_file}.npy", spec.astype(np.float32))
            
            noise_count += 1
            if noise_count % 20 == 0:
                print(f"  Processed: {noise_count}")
        
        except Exception as e:
            print(f"  ❌ Error processing {wav_file.name}: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ TRAINING DATA PREPARED!")
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"  Alarm spectrograms:   {alarm_count}")
    print(f"  Noise spectrograms:   {noise_count}")
    print(f"  Total:                {alarm_count + noise_count}")
    print(f"\n📁 Output: {out_path.absolute()}")
    print(f"\nNext: python train_cnn_model.py")


if __name__ == "__main__":
    prepare_training_data()
