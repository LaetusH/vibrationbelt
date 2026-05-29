"""Pytest fixtures for audio analyzer tests."""

import pytest
import numpy as np
import soundfile as sf
from pathlib import Path
import tempfile


@pytest.fixture
def temp_audio_dir():
    """Create temporary directory for audio files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sine_wave(temp_audio_dir):
    """Generate and save a sine wave (1 kHz, 1 sec, 16 kHz SR)."""
    sr = 16000
    duration = 1.0
    freq = 1000.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    
    filepath = temp_audio_dir / "sine_1khz.wav"
    sf.write(str(filepath), audio, sr)
    
    return filepath, audio, sr


@pytest.fixture
def white_noise(temp_audio_dir):
    """Generate and save white noise (1 sec, 16 kHz SR)."""
    sr = 16000
    duration = 1.0
    
    audio = (0.1 * np.random.randn(int(sr * duration))).astype(np.float32)
    
    filepath = temp_audio_dir / "white_noise.wav"
    sf.write(str(filepath), audio, sr)
    
    return filepath, audio, sr


@pytest.fixture
def stereo_audio(temp_audio_dir):
    """Generate and save stereo audio."""
    sr = 16000
    duration = 1.0
    freq = 440.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    left = 0.3 * np.sin(2 * np.pi * freq * t)
    right = 0.3 * np.sin(2 * np.pi * freq * 1.5 * t)
    
    audio = np.column_stack([left, right]).astype(np.float32)
    
    filepath = temp_audio_dir / "stereo.wav"
    sf.write(str(filepath), audio, sr)
    
    return filepath, audio, sr


@pytest.fixture
def empty_file(temp_audio_dir):
    """Create an invalid/empty audio file."""
    filepath = temp_audio_dir / "empty.wav"
    filepath.write_text("")
    return filepath


@pytest.fixture
def nonexistent_file():
    """Return path to non-existent file."""
    return Path("/tmp/nonexistent_audio_12345.wav")
