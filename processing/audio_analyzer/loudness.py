"""Loudness measurement and detection (LUFS, peak, RMS)."""

import numpy as np
from scipy import signal
from scipy import ndimage
from typing import Tuple, Optional


class LoudnessDetector:
    """Measure and detect audio loudness levels."""

    @staticmethod
    def compute_rms(audio: np.ndarray) -> float:
        """
        Compute RMS (Root Mean Square) level.
        
        Args:
            audio: Audio signal.
            
        Returns:
            RMS value (linear scale, 0-1 for normalized audio).
        """
        rms = np.sqrt(np.mean(audio ** 2))
        return float(rms)

    @staticmethod
    def compute_peak_amplitude(audio: np.ndarray) -> float:
        """
        Compute peak amplitude.
        
        Args:
            audio: Audio signal.
            
        Returns:
            Peak absolute amplitude.
        """
        return float(np.max(np.abs(audio)))

    @staticmethod
    def rms_to_db(rms: float, ref: float = 1.0) -> float:
        """
        Convert RMS to dB.
        
        Args:
            rms: RMS value.
            ref: Reference level (default 1.0 for 0 dB reference).
            
        Returns:
            dB value.
        """
        eps = 1e-10
        return 20 * np.log10(rms / ref + eps)

    @staticmethod
    def peak_to_db(peak: float, ref: float = 1.0) -> float:
        """Convert peak amplitude to dB."""
        eps = 1e-10
        return 20 * np.log10(peak / ref + eps)

    @staticmethod
    def compute_lufs(
        audio: np.ndarray,
        sr: int,
        block_size: int = 2048,
        overlap: Optional[int] = None,
    ) -> Tuple[float, np.ndarray]:
        """
        Compute LUFS (Loudness Units relative to Full Scale).
        
        Simplified LUFS following ITU-R BS.1770-4 standard:
        - High-pass filter (70 Hz)
        - Frequency weighting (K-weighting approximation)
        - Block-based loudness measurement
        
        Args:
            audio: Audio signal.
            sr: Sample rate (Hz).
            block_size: Block size for loudness calculation.
            overlap: Overlap size. If None, use block_size // 2.
            
        Returns:
            Tuple of (integrated_lufs, frame_lufs_array).
        """
        if overlap is None:
            overlap = block_size // 2

        # High-pass filter (70 Hz)
        sos = signal.butter(2, 70, btype="high", fs=sr, output="sos")
        audio_filtered = signal.sosfilt(sos, audio)

        # K-weighting (simplified approximation)
        audio_weighted = LoudnessDetector._apply_k_weighting(audio_filtered, sr)

        # Block-based loudness
        hop = block_size - overlap
        n_blocks = int(np.ceil((len(audio_weighted) - block_size) / hop)) + 1

        frame_lufs = []
        for i in range(n_blocks):
            start = i * hop
            end = start + block_size
            if end > len(audio_weighted):
                end = len(audio_weighted)
            block = audio_weighted[start:end]
            if len(block) > 0:
                # Mean squared (loudness = -0.691 + 10*log10(mean_square + eps))
                ms = np.mean(block ** 2)
                lufs = -0.691 + 10 * np.log10(ms + 1e-10)
                frame_lufs.append(lufs)

        frame_lufs = np.array(frame_lufs)

        # Integrated LUFS: average of frames
        integrated_lufs = float(np.mean(frame_lufs)) if len(frame_lufs) > 0 else -np.inf

        return integrated_lufs, frame_lufs

    @staticmethod
    def _apply_k_weighting(audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Apply K-weighting (ITU-R BS.1770-4 frequency weighting).
        
        Simplified using 2nd-order IIR filters.
        """
        # High-frequency boost around 2-4 kHz (adapt to Nyquist)
        nyquist = sr / 2
        f_min = min(2000, nyquist * 0.4)
        f_max = min(4000, nyquist * 0.9)
        
        if f_max > f_min:
            sos1 = signal.butter(2, [f_min, f_max], btype="bandpass", fs=sr, output="sos")
            boost = signal.sosfilt(sos1, audio)
            # Apply boost (tuned factor)
            audio_weighted = audio + 0.3 * boost
        else:
            audio_weighted = audio

        return audio_weighted

    @staticmethod
    def detect_loudness_peaks(
        audio: np.ndarray,
        sr: int,
        threshold_db: float = -20,
        min_duration_ms: float = 100,
    ) -> np.ndarray:
        """
        Detect loud sections (peaks) in audio.
        
        Args:
            audio: Audio signal.
            sr: Sample rate (Hz).
            threshold_db: Threshold in dB (relative to peak in signal).
            min_duration_ms: Minimum duration for a peak (ms).
            
        Returns:
            Boolean array indicating loud samples.
        """
        # RMS in sliding windows
        window_size = int(sr * 0.01)  # 10 ms window
        hop_size = int(sr * 0.005)  # 5 ms hop

        rms_values = []
        for i in range(0, len(audio) - window_size, hop_size):
            window = audio[i : i + window_size]
            rms = np.sqrt(np.mean(window ** 2))
            rms_values.append(rms)

        rms_values = np.array(rms_values)

        # Threshold based on peak RMS
        peak_rms = np.max(rms_values)
        threshold_linear = peak_rms * 10 ** (threshold_db / 20)

        # Detect peaks
        peaks = rms_values > threshold_linear

        # Minimum duration filter
        min_samples = int(min_duration_ms * sr / 1000)
        filtered_peaks = ndimage.binary_dilation(peaks, structure=np.ones(min_samples))

        # Expand back to audio length
        peak_audio = np.zeros(len(audio), dtype=bool)
        for i, is_peak in enumerate(filtered_peaks):
            start = i * hop_size
            end = min(start + window_size, len(audio))
            if is_peak:
                peak_audio[start:end] = True

        return peak_audio

    @staticmethod
    def segment_by_loudness(
        audio: np.ndarray,
        sr: int,
        threshold_db: float = -30,
    ) -> list:
        """
        Segment audio into quiet and loud sections.
        
        Args:
            audio: Audio signal.
            sr: Sample rate.
            threshold_db: Threshold relative to peak.
            
        Returns:
            List of dicts with 'start', 'end', 'is_loud' for each segment.
        """
        # Compute frame RMS
        frame_size = int(sr * 0.02)  # 20 ms
        hop_size = int(sr * 0.01)  # 10 ms

        frames = []
        for i in range(0, len(audio) - frame_size, hop_size):
            frame = audio[i : i + frame_size]
            rms = np.sqrt(np.mean(frame ** 2))
            frames.append((i, i + frame_size, rms))

        if not frames:
            return []

        # Threshold
        rms_values = np.array([f[2] for f in frames])
        peak_rms = np.max(rms_values)
        threshold_linear = peak_rms * 10 ** (threshold_db / 20)

        # Group consecutive frames
        segments = []
        current_segment = None
        for start, end, rms in frames:
            is_loud = rms > threshold_linear
            if current_segment is None:
                current_segment = {"start": start, "end": end, "is_loud": is_loud}
            elif current_segment["is_loud"] == is_loud:
                current_segment["end"] = end
            else:
                segments.append(current_segment)
                current_segment = {"start": start, "end": end, "is_loud": is_loud}

        if current_segment:
            segments.append(current_segment)

        return segments

    @staticmethod
    def get_loudness_statistics(audio: np.ndarray, sr: int) -> dict:
        """
        Compute various loudness statistics.
        
        Args:
            audio: Audio signal.
            sr: Sample rate.
            
        Returns:
            Dictionary with loudness metrics.
        """
        rms = LoudnessDetector.compute_rms(audio)
        peak = LoudnessDetector.compute_peak_amplitude(audio)
        lufs, frame_lufs = LoudnessDetector.compute_lufs(audio, sr)

        return {
            "rms_linear": float(rms),
            "rms_db": float(LoudnessDetector.rms_to_db(rms)),
            "peak_linear": float(peak),
            "peak_db": float(LoudnessDetector.peak_to_db(peak)),
            "lufs": float(lufs),
            "lufs_mean": float(np.mean(frame_lufs)) if len(frame_lufs) > 0 else -np.inf,
            "lufs_std": float(np.std(frame_lufs)) if len(frame_lufs) > 0 else 0,
            "lufs_max": float(np.max(frame_lufs)) if len(frame_lufs) > 0 else -np.inf,
            "lufs_min": float(np.min(frame_lufs)) if len(frame_lufs) > 0 else -np.inf,
        }
