"""
Spectrogram Generator - Convert audio to visual representation

Generates Mel-scaled spectrograms (224x224 images) from audio chunks.
These can be fed to CNN or used for template matching.
"""

import numpy as np
from scipy import signal
from scipy.fft import rfft, rfftfreq
from typing import Tuple, Optional


class SpectrogramGenerator:
    """
    Generates Mel-scaled spectrograms from audio.
    
    Output: 224×224 normalized images (0-1 range)
    Suitable for CNN input or visual inspection.
    """

    def __init__(self, sr: int = 16000, n_mels: int = 128, n_fft: int = 512):
        """
        Args:
            sr: Sample rate in Hz
            n_mels: Number of Mel frequency bands
            n_fft: FFT window size
        """
        self.sr = sr
        self.n_mels = n_mels
        self.n_fft = n_fft
        
        # Pre-compute Mel filterbank
        self.mel_fb = self._create_mel_filterbank()

    def generate(self, audio: np.ndarray, normalize: bool = True) -> np.ndarray:
        """
        Generate spectrogram from audio.
        
        Args:
            audio: Audio samples (1D array)
            normalize: Whether to normalize to 0-1 range
            
        Returns:
            Spectrogram image (224, 224) normalized to 0-1
        """
        if len(audio) == 0:
            return np.zeros((224, 224), dtype=np.float32)
        
        audio = np.asarray(audio, dtype=np.float32)
        
        # Generate spectrogram using STFT
        freqs, times, Sxx = signal.spectrogram(
            audio,
            fs=self.sr,
            nperseg=self.n_fft,
            noverlap=self.n_fft // 2,
        )
        
        # Convert to Mel scale (power to dB)
        S_mel = self._apply_mel_scale(Sxx)
        S_db = 10 * np.log10(S_mel + 1e-10)
        
        # Resize to 224×224
        S_resized = self._resize_to_224(S_db)
        
        # Normalize
        if normalize:
            S_resized = self._normalize(S_resized)
        
        return S_resized.astype(np.float32)

    def generate_batch(self, audio_chunks: list) -> np.ndarray:
        """
        Generate spectrograms for multiple audio chunks.
        
        Args:
            audio_chunks: List of audio arrays
            
        Returns:
            Array of shape (N, 224, 224)
        """
        specs = []
        for chunk in audio_chunks:
            spec = self.generate(chunk)
            specs.append(spec)
        
        return np.stack(specs, axis=0)

    def _create_mel_filterbank(self) -> np.ndarray:
        """Create Mel-scale filterbank."""
        # Frequencies for FFT
        freqs = rfftfreq(self.n_fft, 1 / self.sr)
        
        # Mel scale conversion
        mel_points = np.linspace(
            self._hz_to_mel(freqs[0] + 1),
            self._hz_to_mel(freqs[-1]),
            self.n_mels + 2
        )
        hz_points = self._mel_to_hz(mel_points)
        
        # Create filterbank
        fb = np.zeros((self.n_mels, len(freqs)))
        for m in range(1, self.n_mels + 1):
            f_left = hz_points[m - 1]
            f_center = hz_points[m]
            f_right = hz_points[m + 1]
            
            for k in range(len(freqs)):
                f = freqs[k]
                if f_left < f < f_center:
                    fb[m - 1, k] = (f - f_left) / (f_center - f_left)
                elif f_center < f < f_right:
                    fb[m - 1, k] = (f_right - f) / (f_right - f_center)
        
        return fb

    def _apply_mel_scale(self, Sxx: np.ndarray) -> np.ndarray:
        """Apply Mel filterbank to spectrogram."""
        return np.dot(self.mel_fb, Sxx)

    def _hz_to_mel(self, hz: float) -> float:
        """Convert Hz to Mel scale."""
        return 2595 * np.log10(1 + hz / 700)

    def _mel_to_hz(self, mel: float) -> float:
        """Convert Mel scale to Hz."""
        return 700 * (10 ** (mel / 2595) - 1)

    def _resize_to_224(self, spec: np.ndarray) -> np.ndarray:
        """Resize spectrogram to 224×224."""
        from scipy.ndimage import zoom
        
        current_shape = spec.shape
        target_shape = (224, 224)
        
        zoom_factors = (
            target_shape[0] / current_shape[0],
            target_shape[1] / current_shape[1],
        )
        
        resized = zoom(spec, zoom_factors, order=1)
        
        # Ensure exact size
        resized = resized[:224, :224]
        if resized.shape != target_shape:
            padded = np.zeros(target_shape)
            padded[:resized.shape[0], :resized.shape[1]] = resized
            resized = padded
        
        return resized

    def _normalize(self, spec: np.ndarray) -> np.ndarray:
        """Normalize to 0-1 range."""
        spec_min = np.min(spec)
        spec_max = np.max(spec)
        
        if spec_max - spec_min < 1e-10:
            return np.zeros_like(spec)
        
        return (spec - spec_min) / (spec_max - spec_min)

    def spectrogram_to_image(self, spec: np.ndarray, cmap: str = 'viridis') -> bytes:
        """
        Convert spectrogram to PNG image bytes.
        
        Args:
            spec: Spectrogram array (224, 224)
            cmap: Colormap name
            
        Returns:
            PNG image bytes
        """
        import matplotlib.pyplot as plt
        from io import BytesIO
        
        fig, ax = plt.subplots(figsize=(4, 4), dpi=56)
        im = ax.imshow(spec, aspect='auto', origin='lower', cmap=cmap)
        ax.set_ylabel('Frequency')
        ax.set_xlabel('Time')
        plt.colorbar(im, ax=ax)
        
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=56)
        buf.seek(0)
        plt.close(fig)
        
        return buf.getvalue()

    def spectrogram_to_dataurl(self, spec: np.ndarray) -> str:
        """Convert spectrogram to base64 data URL for HTML."""
        import base64
        
        img_bytes = self.spectrogram_to_image(spec)
        data = base64.b64encode(img_bytes).decode()
        return f"data:image/png;base64,{data}"

    def get_config(self) -> dict:
        """Return configuration"""
        return {
            'sample_rate_hz': self.sr,
            'n_mels': self.n_mels,
            'n_fft': self.n_fft,
            'output_shape': (224, 224),
        }
