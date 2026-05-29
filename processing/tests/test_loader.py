"""Tests for AudioLoader."""

import pytest
import numpy as np
from pathlib import Path

from audio_analyzer.loader import AudioLoader


class TestAudioLoader:
    """AudioLoader unit tests."""

    def test_load_mono_sine(self, sine_wave):
        """Load a simple sine wave."""
        filepath, expected_audio, expected_sr = sine_wave
        
        loader = AudioLoader()
        audio, sr = loader.load(str(filepath))
        
        assert sr == expected_sr
        assert len(audio) == len(expected_audio)
        assert audio.dtype == np.float32
        np.testing.assert_allclose(audio, expected_audio, rtol=1e-4, atol=1e-4)

    def test_load_returns_mono(self, stereo_audio):
        """Stereo audio should be converted to mono."""
        filepath, _, sr = stereo_audio
        
        loader = AudioLoader()
        audio, _ = loader.load(str(filepath))
        
        assert audio.ndim == 1, "Audio should be 1D (mono)"

    def test_load_nonexistent_file(self, nonexistent_file):
        """Loading non-existent file raises FileNotFoundError."""
        loader = AudioLoader()
        
        with pytest.raises(FileNotFoundError):
            loader.load(str(nonexistent_file))

    def test_load_invalid_file(self, empty_file):
        """Loading invalid file raises ValueError."""
        loader = AudioLoader()
        
        with pytest.raises(ValueError):
            loader.load(str(empty_file))

    def test_load_with_resampling(self, sine_wave):
        """Resample audio to different sample rate."""
        filepath, _, _ = sine_wave
        target_sr = 8000
        
        loader = AudioLoader(target_sr=target_sr)
        audio, sr = loader.load(str(filepath))
        
        assert sr == target_sr
        # Expected length after resampling: 1 sec at 8 kHz = 8000 samples
        assert len(audio) == target_sr

    def test_load_mono_method(self, sine_wave):
        """load_mono convenience method works."""
        filepath, _, sr = sine_wave
        
        loader = AudioLoader()
        audio, sr_out = loader.load_mono(str(filepath))
        
        assert audio.ndim == 1
        assert sr_out == sr

    def test_get_info(self, sine_wave):
        """Get audio file info without loading."""
        filepath, _, sr = sine_wave
        
        info = AudioLoader.get_info(str(filepath))
        
        assert info["sample_rate"] == sr
        assert info["duration_sec"] == pytest.approx(1.0, abs=0.01)
        assert info["channels"] == 1

    def test_get_info_nonexistent(self, nonexistent_file):
        """get_info on non-existent file raises ValueError."""
        with pytest.raises(ValueError):
            AudioLoader.get_info(str(nonexistent_file))

    def test_load_white_noise(self, white_noise):
        """Load white noise."""
        filepath, expected_audio, sr = white_noise
        
        loader = AudioLoader()
        audio, sr_out = loader.load(str(filepath))
        
        assert sr_out == sr
        assert len(audio) == len(expected_audio)
        np.testing.assert_allclose(audio, expected_audio, rtol=1e-4, atol=1e-4)

    def test_audio_dtype(self, sine_wave):
        """Audio should be returned as float32."""
        filepath, _, _ = sine_wave
        
        loader = AudioLoader()
        audio, _ = loader.load(str(filepath))
        
        assert audio.dtype == np.float32
