"""Spectrogram generation and time-frequency analysis."""

import numpy as np
from scipy import signal
from typing import Tuple, Optional


class SpectrogramGenerator:
    """Generate and analyze spectrograms."""

    def __init__(self, window: str = "hann"):
        """
        Initialize spectrogram generator.
        
        Args:
            window: Window function for STFT.
        """
        self.window = window

    def compute_spectrogram(
        self,
        audio: np.ndarray,
        sr: int,
        n_fft: int = 2048,
        hop_length: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute spectrogram (magnitude).
        
        Args:
            audio: Audio signal.
            sr: Sample rate (Hz).
            n_fft: FFT size.
            hop_length: Hop length (samples). If None, use n_fft // 4.
            
        Returns:
            Tuple of (spectrogram, frequencies, times).
            - spectrogram: Shape (n_freqs, n_frames).
            - frequencies: Frequency bins (Hz).
            - times: Time bins (seconds).
        """
        if hop_length is None:
            hop_length = n_fft // 4

        f, t, Sxx = signal.spectrogram(
            audio,
            fs=sr,
            window=self.window,
            nperseg=n_fft,
            noverlap=n_fft - hop_length,
            scaling="spectrum",
        )

        return np.abs(Sxx), f, t

    def compute_log_spectrogram(
        self,
        audio: np.ndarray,
        sr: int,
        n_fft: int = 2048,
        hop_length: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute log-scaled spectrogram (dB).
        
        Args:
            audio: Audio signal.
            sr: Sample rate (Hz).
            n_fft: FFT size.
            hop_length: Hop length (samples).
            
        Returns:
            Tuple of (spectrogram_db, frequencies, times).
        """
        spectrogram, f, t = self.compute_spectrogram(
            audio, sr, n_fft, hop_length
        )

        # Convert to dB
        eps = 1e-10
        spectrogram_db = 10 * np.log10(spectrogram + eps)

        return spectrogram_db, f, t

    def extract_mel_spectrogram(
        self,
        audio: np.ndarray,
        sr: int,
        n_mels: int = 128,
        n_fft: int = 2048,
        hop_length: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Compute Mel-scale spectrogram (mimics human hearing).
        
        Args:
            audio: Audio signal.
            sr: Sample rate (Hz).
            n_mels: Number of Mel bands.
            n_fft: FFT size.
            hop_length: Hop length.
            
        Returns:
            Tuple of (mel_spectrogram_db, mel_frequencies, times).
        """
        if hop_length is None:
            hop_length = n_fft // 4

        S = signal.spectrogram(
            audio,
            fs=sr,
            window=self.window,
            nperseg=n_fft,
            noverlap=n_fft - hop_length,
            scaling="spectrum",
        )[2]

        # Create Mel filter bank
        mel_fb = self._mel_filterbank(sr, n_fft, n_mels)

        # Apply filters
        mel_spec = mel_fb @ np.abs(S)

        # Convert to dB
        eps = 1e-10
        mel_spec_db = 10 * np.log10(mel_spec + eps)

        # Mel frequencies
        mel_freqs = self._hz_to_mel(np.linspace(0, sr / 2, n_mels))

        # Time bins
        n_frames = S.shape[1]
        times = np.arange(n_frames) * hop_length / sr

        return mel_spec_db, mel_freqs, times

    def get_spectrogram_stats(
        self,
        spectrogram: np.ndarray,
        axis: int = 0,
    ) -> dict:
        """
        Compute statistics over spectrogram.
        
        Args:
            spectrogram: Spectrogram (dB).
            axis: Axis along which to compute stats (0=freq, 1=time).
            
        Returns:
            Dict with mean, std, max, min per frequency/time.
        """
        return {
            "mean": np.mean(spectrogram, axis=axis),
            "std": np.std(spectrogram, axis=axis),
            "max": np.max(spectrogram, axis=axis),
            "min": np.min(spectrogram, axis=axis),
        }

    @staticmethod
    def _mel_filterbank(sr: int, n_fft: int, n_mels: int) -> np.ndarray:
        """Create Mel-scale filter bank."""
        # Frequency limits
        f_min = 0
        f_max = sr / 2
        
        # Convert to Mel scale
        m_min = 2595 * np.log10(1 + f_min / 700)
        m_max = 2595 * np.log10(1 + f_max / 700)
        
        # Mel-spaced points
        m_pts = np.linspace(m_min, m_max, n_mels + 2)
        f_pts = 700 * (10 ** (m_pts / 2595) - 1)
        
        # FFT bin indices
        bin_pts = np.floor((n_fft + 1) * f_pts / sr).astype(int)
        
        # Create filter bank
        fb = np.zeros((n_mels, n_fft // 2 + 1))
        for m in range(n_mels):
            f_l = bin_pts[m]
            f_c = bin_pts[m + 1]
            f_r = bin_pts[m + 2]
            
            if f_c > f_l:
                fb[m, f_l:f_c] = np.linspace(0, 1, f_c - f_l)
            if f_r > f_c:
                fb[m, f_c:f_r] = np.linspace(1, 0, f_r - f_c)
        
        return fb

    @staticmethod
    def _hz_to_mel(hz: np.ndarray) -> np.ndarray:
        """Convert Hz to Mel scale."""
        return 2595 * np.log10(1 + hz / 700)

    @staticmethod
    def _mel_to_hz(mel: np.ndarray) -> np.ndarray:
        """Convert Mel scale to Hz."""
        return 700 * (10 ** (mel / 2595) - 1)
