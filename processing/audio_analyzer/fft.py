"""FFT analysis and frequency domain utilities."""

import numpy as np
from scipy import signal
from typing import Tuple, Optional


class FFTAnalyzer:
    """Fast Fourier Transform analysis for audio signals."""

    def __init__(self, window: str = "hann"):
        """
        Initialize FFT analyzer.
        
        Args:
            window: Window function ('hann', 'hamming', 'blackman', etc.).
        """
        self.window = window

    def compute_fft(
        self,
        audio: np.ndarray,
        sr: int,
        n_fft: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute FFT magnitude spectrum.
        
        Args:
            audio: Audio signal (1D numpy array).
            sr: Sample rate (Hz).
            n_fft: FFT size. If None, use power of 2 >= len(audio).
            
        Returns:
            Tuple of (frequencies, magnitudes).
            - frequencies: Frequency bins (Hz), shape (n_fft // 2 + 1,).
            - magnitudes: Magnitude spectrum (linear), shape (n_fft // 2 + 1,).
        """
        if n_fft is None:
            n_fft = 2 ** int(np.ceil(np.log2(len(audio))))

        # Apply window
        window_func = signal.get_window(self.window, len(audio))
        windowed = audio * window_func

        # Compute FFT
        fft_result = np.fft.rfft(windowed, n=n_fft)
        magnitudes = np.abs(fft_result)

        # Frequency bins
        frequencies = np.fft.rfftfreq(n_fft, 1 / sr)

        return frequencies, magnitudes

    def compute_power_spectrum(
        self,
        audio: np.ndarray,
        sr: int,
        n_fft: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute power spectrum (magnitude squared, in dB).
        
        Args:
            audio: Audio signal.
            sr: Sample rate (Hz).
            n_fft: FFT size.
            
        Returns:
            Tuple of (frequencies, power_db).
            - frequencies: Frequency bins (Hz).
            - power_db: Power spectrum in dB scale.
        """
        frequencies, magnitudes = self.compute_fft(audio, sr, n_fft)

        # Power = magnitude^2, normalized by window energy
        power = magnitudes ** 2
        window_func = signal.get_window(self.window, len(audio))
        window_energy = np.sum(window_func ** 2)

        power_normalized = power / window_energy

        # Convert to dB (add small epsilon to avoid log(0))
        eps = 1e-10
        power_db = 10 * np.log10(power_normalized + eps)

        return frequencies, power_db

    def find_peaks(
        self,
        frequencies: np.ndarray,
        magnitudes: np.ndarray,
        height_threshold: float = 0.1,
        distance: int = 5,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find prominent peaks in frequency spectrum.
        
        Args:
            frequencies: Frequency bins.
            magnitudes: Magnitude values.
            height_threshold: Minimum height (as fraction of max) for peak.
            distance: Minimum distance (in samples) between peaks.
            
        Returns:
            Tuple of (peak_frequencies, peak_magnitudes).
        """
        max_magnitude = np.max(magnitudes)
        height = height_threshold * max_magnitude

        peaks, _ = signal.find_peaks(magnitudes, height=height, distance=distance)

        peak_frequencies = frequencies[peaks]
        peak_magnitudes = magnitudes[peaks]

        # Sort by magnitude (descending)
        sorted_idx = np.argsort(-peak_magnitudes)

        return peak_frequencies[sorted_idx], peak_magnitudes[sorted_idx]

    def estimate_fundamental(
        self,
        frequencies: np.ndarray,
        magnitudes: np.ndarray,
        freq_min: float = 20.0,
        freq_max: float = 2000.0,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Estimate fundamental frequency (pitch).
        
        Args:
            frequencies: Frequency bins.
            magnitudes: Magnitude values.
            freq_min: Minimum frequency to consider.
            freq_max: Maximum frequency to consider.
            
        Returns:
            Tuple of (fundamental_freq, magnitude) or (None, None) if not found.
        """
        # Find peaks in range
        mask = (frequencies >= freq_min) & (frequencies <= freq_max)
        if not np.any(mask):
            return None, None

        peak_freqs, peak_mags = self.find_peaks(
            frequencies[mask], magnitudes[mask], height_threshold=0.05
        )

        if len(peak_freqs) == 0:
            return None, None

        # Return strongest peak as fundamental
        return peak_freqs[0], peak_mags[0]

    def get_frequency_band_energy(
        self,
        frequencies: np.ndarray,
        magnitudes: np.ndarray,
        freq_min: float,
        freq_max: float,
    ) -> float:
        """
        Compute total energy in a frequency band.
        
        Args:
            frequencies: Frequency bins.
            magnitudes: Magnitude values.
            freq_min: Band start (Hz).
            freq_max: Band end (Hz).
            
        Returns:
            Total energy (sum of magnitudes squared) in band.
        """
        mask = (frequencies >= freq_min) & (frequencies <= freq_max)
        band_magnitudes = magnitudes[mask]
        energy = np.sum(band_magnitudes ** 2)
        return energy
