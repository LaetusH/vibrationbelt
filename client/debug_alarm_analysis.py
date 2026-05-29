#!/usr/bin/env python3
"""
🔍 DEBUG: Capture and analyze the ACTUAL alarm pattern

This records 5 seconds of raw audio from ESP32 while you play the alarm.
Then it shows what frequencies are REALLY there.
"""

import sys
import os
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.dirname(project_root))

import vibrationbelt as vb
import numpy as np
from scipy import signal
from scipy.fft import rfft, rfftfreq
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt


def analyze_alarm(esp32_ip, duration_sec=5, esp32_port=4444):
    """Capture and analyze actual alarm audio."""
    
    print("\n" + "=" * 75)
    print("🔍 ALARM PATTERN ANALYZER")
    print("=" * 75)
    print(f"\nTarget: {esp32_ip}:{esp32_port}")
    print(f"Duration: {duration_sec}s")
    
    # Connect
    try:
        mic_stream = vb.MicStream(esp32_ip, port=esp32_port)
        mic_stream.start()
        print(f"✓ Connected")
    except Exception as e:
        print(f"❌ CONNECTION FAILED: {e}")
        return False
    
    # Collect audio
    print(f"\n⏱️  Collecting {duration_sec}s of audio...")
    print("   👉 PLAY YOUR ALARM NOW!")
    
    collected_samples = []
    start_time = time.time()
    
    try:
        for chunk in mic_stream:
            collected_samples.append(chunk.samples.astype(np.float32) / 32768.0)
            
            elapsed = time.time() - start_time
            if elapsed >= duration_sec:
                break
            
            # Progress
            print(f"   [{elapsed:>4.1f}s / {duration_sec}s]", end='\r', flush=True)
    
    except Exception as e:
        print(f"❌ Error during capture: {e}")
        return False
    
    finally:
        mic_stream.close()
    
    # Combine all chunks
    if not collected_samples:
        print("❌ No audio captured!")
        return False
    
    audio = np.concatenate(collected_samples)
    sr = vb.SAMPLE_RATE
    
    print(f"\n✓ Captured {len(audio)} samples ({len(audio)/sr:.2f}s)")
    print(f"  RMS: {np.sqrt(np.mean(audio**2)):.4f}")
    print(f"  Peak: {np.max(np.abs(audio)):.4f}")
    
    # ===== ANALYSIS =====
    print("\n" + "=" * 75)
    print("FREQUENCY ANALYSIS")
    print("=" * 75)
    
    # Full FFT
    windowed = audio * signal.windows.hann(len(audio))
    fft_result = rfft(windowed, n=8192)
    freqs = rfftfreq(8192, 1 / sr)
    magnitude = np.abs(fft_result)
    magnitude = magnitude / np.max(magnitude)
    
    # Find peaks
    peaks, _ = signal.find_peaks(magnitude, height=0.05)
    peak_freqs = freqs[peaks]
    peak_mags = magnitude[peaks]
    
    # Sort by magnitude
    peak_order = np.argsort(-peak_mags)
    top_peaks = peak_order[:10]
    
    print("\nTop frequency peaks:")
    for i, idx in enumerate(top_peaks):
        freq = peak_freqs[idx]
        mag = peak_mags[idx]
        print(f"  {i+1}. {freq:>6.0f} Hz  (magnitude: {mag:.2f})")
    
    # ===== TEMPORAL ANALYSIS =====
    print("\n" + "=" * 75)
    print("TEMPORAL PATTERN (how frequencies change over time)")
    print("=" * 75)
    
    # Spectrogram
    frequencies, times, spectrogram = signal.spectrogram(
        audio,
        fs=sr,
        nperseg=512,
        noverlap=256,
    )
    
    # Find dominant frequency at each time step
    dominant_freqs = []
    for t_idx in range(spectrogram.shape[1]):
        power = spectrogram[:, t_idx]
        peak_idx = np.argmax(power)
        freq = frequencies[peak_idx]
        dominant_freqs.append(freq)
    
    dominant_freqs = np.array(dominant_freqs)
    
    print(f"\nDominant frequency over time:")
    print(f"  Mean: {np.mean(dominant_freqs):.0f} Hz")
    print(f"  Std:  {np.std(dominant_freqs):.1f} Hz")
    print(f"  Min:  {np.min(dominant_freqs):.0f} Hz")
    print(f"  Max:  {np.max(dominant_freqs):.0f} Hz")
    print(f"  Range: {np.max(dominant_freqs) - np.min(dominant_freqs):.0f} Hz")
    
    # Show samples
    step = max(1, len(dominant_freqs) // 20)
    print(f"\n  Frequency samples (every {step} frames):")
    for i in range(0, len(dominant_freqs), step):
        freq = dominant_freqs[i]
        time_sec = i * (len(audio) / len(dominant_freqs)) / sr
        print(f"    {time_sec:.2f}s: {freq:.0f} Hz")
    
    # ===== VISUALIZATION =====
    print("\n" + "=" * 75)
    print("GENERATING PLOTS...")
    print("=" * 75)
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    # Plot 1: Waveform
    time_axis = np.arange(len(audio)) / sr
    axes[0].plot(time_axis, audio, linewidth=0.5)
    axes[0].set_xlabel("Time (s)")
    axes[0].set_ylabel("Amplitude")
    axes[0].set_title("Waveform")
    axes[0].grid()
    
    # Plot 2: FFT
    axes[1].semilogy(freqs[:2000], magnitude[:2000])
    axes[1].set_xlabel("Frequency (Hz)")
    axes[1].set_ylabel("Magnitude (log)")
    axes[1].set_title("FFT Spectrum (0-2000 Hz)")
    axes[1].grid()
    
    # Plot 3: Spectrogram
    spec_db = 10 * np.log10(spectrogram + 1e-10)
    im = axes[2].pcolormesh(times, frequencies, spec_db, shading='gouraud', cmap='viridis')
    axes[2].set_ylabel("Frequency (Hz)")
    axes[2].set_xlabel("Time (s)")
    axes[2].set_title("Spectrogram")
    axes[2].set_ylim([0, 5000])
    plt.colorbar(im, ax=axes[2], label="Power (dB)")
    
    plt.tight_layout()
    plot_path = os.path.join(project_root, "alarm_analysis.png")
    plt.savefig(plot_path, dpi=100)
    print(f"\n✓ Saved to: {plot_path}")
    
    # Save raw audio for inspection
    wav_path = os.path.join(project_root, "alarm_raw.npy")
    np.save(wav_path, audio)
    print(f"✓ Saved raw audio to: {wav_path}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_alarm_analysis.py <ESP32_IP>")
        print("Example: python debug_alarm_analysis.py 10.8.5.177")
        sys.exit(1)
    
    esp32_ip = sys.argv[1]
    success = analyze_alarm(esp32_ip, duration_sec=5)
    sys.exit(0 if success else 1)
