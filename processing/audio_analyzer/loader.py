"""Audio file loader and validator."""

import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Tuple, Optional


class AudioLoader:
    """Load and validate WAV audio files."""

    def __init__(self, target_sr: Optional[int] = None):
        """
        Initialize loader.
        
        Args:
            target_sr: Target sample rate. If None, use file's native rate.
                      If set, resample audio to this rate.
        """
        self.target_sr = target_sr

    def load(self, filepath: str) -> Tuple[np.ndarray, int]:
        """
        Load a WAV file.
        
        Args:
            filepath: Path to WAV file.
            
        Returns:
            Tuple of (audio_data, sample_rate).
            - audio_data: numpy array, shape (n_samples,) for mono or (n_samples, n_channels) for stereo.
            - sample_rate: int, Hz.
            
        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If file is invalid or unsupported.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {filepath}")

        try:
            audio, sr = sf.read(filepath)
        except Exception as e:
            raise ValueError(f"Failed to read audio file: {e}")

        # Validate
        if audio.size == 0:
            raise ValueError("Audio file is empty")

        # Convert to mono if stereo
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Resample if needed
        if self.target_sr is not None and sr != self.target_sr:
            audio = self._resample(audio, sr, self.target_sr)
            sr = self.target_sr

        # Ensure float32
        audio = audio.astype(np.float32)

        return audio, sr

    @staticmethod
    def _resample(audio: np.ndarray, src_sr: int, tgt_sr: int) -> np.ndarray:
        """Resample audio using scipy."""
        import scipy.signal as signal
        
        ratio = tgt_sr / src_sr
        n_samples = int(len(audio) * ratio)
        return signal.resample(audio, n_samples).astype(np.float32)

    def load_mono(self, filepath: str) -> Tuple[np.ndarray, int]:
        """Load audio and ensure mono."""
        audio, sr = self.load(filepath)
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        return audio, sr

    @staticmethod
    def get_info(filepath: str) -> dict:
        """Get audio file info without loading entire file."""
        try:
            info = sf.info(filepath)
            return {
                "duration_sec": info.duration,
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "format": info.format,
                "subtype": info.subtype,
            }
        except Exception as e:
            raise ValueError(f"Failed to read audio info: {e}")
