"""Tests for FFTAnalyzer."""

import pytest
import numpy as np
from audio_analyzer.fft import FFTAnalyzer


class TestFFTAnalyzer:
    """FFT analysis unit tests."""

    def test_compute_fft_sine(self, sine_wave):
        """FFT of sine wave should have peak at signal frequency."""
        filepath, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        frequencies, magnitudes = analyzer.compute_fft(audio, sr)
        
        # Find peak
        peak_idx = np.argmax(magnitudes)
        peak_freq = frequencies[peak_idx]
        
        # Should be close to 1000 Hz
        assert np.isclose(peak_freq, 1000, atol=10), f"Peak at {peak_freq} Hz, expected ~1000 Hz"

    def test_compute_fft_returns_valid_shapes(self, sine_wave):
        """FFT output shapes should be consistent."""
        _, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        frequencies, magnitudes = analyzer.compute_fft(audio, sr)
        
        assert frequencies.shape == magnitudes.shape
        assert len(frequencies) > 0
        assert frequencies[0] >= 0  # Non-negative frequencies

    def test_compute_power_spectrum(self, sine_wave):
        """Power spectrum should be in dB."""
        _, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        frequencies, power_db = analyzer.compute_power_spectrum(audio, sr)
        
        assert power_db.dtype in [np.float32, np.float64]
        assert np.all(np.isfinite(power_db))
        # dB values can be negative
        assert np.min(power_db) < 0

    def test_find_peaks(self, sine_wave):
        """find_peaks should detect frequency peaks."""
        _, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        frequencies, magnitudes = analyzer.compute_fft(audio, sr)
        
        peak_freqs, peak_mags = analyzer.find_peaks(frequencies, magnitudes)
        
        assert len(peak_freqs) > 0
        assert len(peak_freqs) == len(peak_mags)
        # Strongest peak should be around 1000 Hz
        assert np.isclose(peak_freqs[0], 1000, atol=20)

    def test_find_peaks_returns_sorted(self, sine_wave):
        """Peaks should be sorted by magnitude (descending)."""
        _, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        frequencies, magnitudes = analyzer.compute_fft(audio, sr)
        peak_freqs, peak_mags = analyzer.find_peaks(frequencies, magnitudes)
        
        # Magnitudes should be sorted descending
        assert np.all(peak_mags[:-1] >= peak_mags[1:])

    def test_estimate_fundamental(self, sine_wave):
        """estimate_fundamental should find the dominant frequency."""
        _, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        frequencies, magnitudes = analyzer.compute_fft(audio, sr)
        
        fundamental, mag = analyzer.estimate_fundamental(frequencies, magnitudes)
        
        assert fundamental is not None
        assert np.isclose(fundamental, 1000, atol=20)
        assert mag > 0

    def test_get_frequency_band_energy(self, sine_wave):
        """Band energy should be concentrated around signal frequency."""
        _, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        frequencies, magnitudes = analyzer.compute_fft(audio, sr)
        
        # Energy around 1000 Hz should be high
        energy_signal = analyzer.get_frequency_band_energy(
            frequencies, magnitudes, 900, 1100
        )
        
        # Energy far from signal should be low
        energy_noise = analyzer.get_frequency_band_energy(
            frequencies, magnitudes, 5000, 6000
        )
        
        assert energy_signal > energy_noise

    def test_window_functions(self, sine_wave):
        """Different windows should work."""
        _, audio, sr = sine_wave
        
        for window in ["hann", "hamming", "blackman"]:
            analyzer = FFTAnalyzer(window=window)
            frequencies, magnitudes = analyzer.compute_fft(audio, sr)
            
            assert len(magnitudes) > 0
            assert np.all(np.isfinite(magnitudes))

    def test_fft_white_noise(self, white_noise):
        """FFT of white noise should be relatively flat."""
        _, audio, sr = white_noise
        
        analyzer = FFTAnalyzer()
        frequencies, magnitudes = analyzer.compute_fft(audio, sr)
        
        # For white noise, magnitude should be roughly constant
        cv = np.std(magnitudes) / np.mean(magnitudes)  # Coefficient of variation
        
        # White noise should have lower variance than pure sine (less structured)
        # Relaxed threshold due to random nature of white noise
        assert cv < 1.0, f"White noise CV too high: {cv}"

    def test_fft_n_fft_parameter(self, sine_wave):
        """n_fft parameter should control resolution."""
        _, audio, sr = sine_wave
        
        analyzer = FFTAnalyzer()
        
        # Small FFT
        f1, m1 = analyzer.compute_fft(audio, sr, n_fft=512)
        
        # Large FFT
        f2, m2 = analyzer.compute_fft(audio, sr, n_fft=4096)
        
        # More bins with larger FFT
        assert len(f2) > len(f1)
