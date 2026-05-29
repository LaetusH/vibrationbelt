"""Tests for SpectrogramGenerator."""

import pytest
import numpy as np
from audio_analyzer.spectrogram import SpectrogramGenerator


class TestSpectrogramGenerator:
    """Spectrogram generation unit tests."""

    def test_compute_spectrogram_shape(self, sine_wave):
        """Spectrogram output shape should be valid."""
        _, audio, sr = sine_wave
        
        gen = SpectrogramGenerator()
        spec, freqs, times = gen.compute_spectrogram(audio, sr)
        
        # Shape: (n_freqs, n_frames)
        assert spec.ndim == 2
        assert len(freqs) == spec.shape[0]
        assert len(times) == spec.shape[1]

    def test_compute_spectrogram_values_positive(self, sine_wave):
        """Spectrogram magnitude should be non-negative."""
        _, audio, sr = sine_wave
        
        gen = SpectrogramGenerator()
        spec, _, _ = gen.compute_spectrogram(audio, sr)
        
        assert np.all(spec >= 0)

    def test_compute_log_spectrogram(self, sine_wave):
        """Log spectrogram should be in dB."""
        _, audio, sr = sine_wave
        
        gen = SpectrogramGenerator()
        spec_db, freqs, times = gen.compute_log_spectrogram(audio, sr)
        
        assert spec_db.ndim == 2
        assert np.all(np.isfinite(spec_db))
        # dB values are typically negative
        assert np.min(spec_db) < 0

    def test_extract_mel_spectrogram(self, sine_wave):
        """Mel spectrogram should have n_mels frequency bands."""
        _, audio, sr = sine_wave
        
        n_mels = 64
        gen = SpectrogramGenerator()
        mel_spec, mel_freqs, times = gen.extract_mel_spectrogram(
            audio, sr, n_mels=n_mels
        )
        
        # Should have n_mels frequency bands
        assert mel_spec.shape[0] == n_mels
        assert len(mel_freqs) == n_mels

    def test_spectrogram_time_resolution(self, sine_wave):
        """Time resolution should scale with audio duration."""
        _, audio, sr = sine_wave
        
        gen = SpectrogramGenerator()
        _, _, times = gen.compute_spectrogram(audio, sr, n_fft=512)
        
        # Time should span roughly 1 second
        assert times[-1] == pytest.approx(1.0, abs=0.1)

    def test_get_spectrogram_stats(self, sine_wave):
        """Spectrogram stats should have correct keys."""
        _, audio, sr = sine_wave
        
        gen = SpectrogramGenerator()
        spec, _, _ = gen.compute_spectrogram(audio, sr)
        
        stats = gen.get_spectrogram_stats(spec, axis=1)  # Stats per frequency
        
        assert "mean" in stats
        assert "std" in stats
        assert "max" in stats
        assert "min" in stats
        
        # axis=1 reduces over time, so length = n_freqs
        assert len(stats["mean"]) == spec.shape[0]

    def test_hop_length_parameter(self, sine_wave):
        """hop_length should affect time resolution."""
        _, audio, sr = sine_wave
        
        gen = SpectrogramGenerator()
        
        # Smaller hop = more frames
        _, _, t1 = gen.compute_spectrogram(audio, sr, hop_length=256)
        _, _, t2 = gen.compute_spectrogram(audio, sr, hop_length=512)
        
        assert len(t1) > len(t2)

    def test_mel_filterbank_shape(self, sine_wave):
        """Mel filterbank should be square-ish."""
        sr = 16000
        n_fft = 2048
        n_mels = 128
        
        fb = SpectrogramGenerator._mel_filterbank(sr, n_fft, n_mels)
        
        assert fb.shape == (n_mels, n_fft // 2 + 1)
        assert np.all(fb >= 0)  # Positive values

    def test_hz_mel_conversion(self):
        """Hz to Mel and back should be reversible (approximately)."""
        hz_values = np.array([100, 500, 1000, 5000, 8000])
        
        mel_values = SpectrogramGenerator._hz_to_mel(hz_values)
        hz_back = SpectrogramGenerator._mel_to_hz(mel_values)
        
        np.testing.assert_allclose(hz_values, hz_back, rtol=1e-10)

    def test_spectrogram_window_parameter(self, sine_wave):
        """Different window functions should work."""
        _, audio, sr = sine_wave
        
        for window in ["hann", "hamming", "blackman"]:
            gen = SpectrogramGenerator(window=window)
            spec, _, _ = gen.compute_spectrogram(audio, sr)
            
            assert spec.shape[1] > 0
            assert np.all(np.isfinite(spec))

    def test_mel_spectrogram_concentration(self, sine_wave):
        """Mel spectrogram of sine wave should concentrate energy in one band."""
        _, audio, sr = sine_wave
        
        gen = SpectrogramGenerator()
        mel_spec, _, _ = gen.extract_mel_spectrogram(audio, sr, n_mels=64)
        
        # Average over time
        avg_energy = np.mean(mel_spec, axis=1)
        
        # Max energy should be significantly higher than median
        max_energy = np.max(avg_energy)
        median_energy = np.median(avg_energy)
        
        assert max_energy > 2 * median_energy
