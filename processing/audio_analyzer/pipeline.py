"""High-level audio analysis pipeline."""

import numpy as np
from pathlib import Path
from typing import Optional, List, Dict

from .loader import AudioLoader
from .fft import FFTAnalyzer
from .spectrogram import SpectrogramGenerator
from .loudness import LoudnessDetector
from .alarm_detector import AlarmDetector, AlarmType
from .anomaly_detector import AnomalyDetector, AnomalyType


class AudioAnalysisPipeline:
    """Complete audio analysis pipeline for alarm detection."""

    def __init__(self, target_sr: int = 16000):
        """
        Initialize pipeline.
        
        Args:
            target_sr: Target sample rate (Hz). Audio will be resampled if needed.
        """
        self.target_sr = target_sr
        self.loader = AudioLoader(target_sr=target_sr)
        self.fft_analyzer = FFTAnalyzer()
        self.spectrogram_gen = SpectrogramGenerator()
        self.loudness_detector = LoudnessDetector()
        self.alarm_detector = AlarmDetector(target_sr)
        self.anomaly_detector = AnomalyDetector(target_sr)

    def analyze_file(
        self,
        filepath: str,
        alarm_sensitivity: float = 0.5,
        alarm_min_confidence: float = 0.6,
    ) -> Dict:
        """
        Analyze an audio file end-to-end.
        
        Args:
            filepath: Path to WAV file.
            alarm_sensitivity: Alarm detection sensitivity (0-1).
            alarm_min_confidence: Minimum alarm confidence threshold.
            
        Returns:
            Dictionary with complete analysis results:
            - audio: audio array
            - sr: sample rate
            - duration_sec: duration in seconds
            - loudness: loudness statistics
            - spectrum: FFT results
            - spectrogram: time-frequency analysis
            - alarms: detected alarms
            - summary: human-readable summary
        """
        # Load audio
        audio, sr = self.loader.load(filepath)
        duration = len(audio) / sr

        # Loudness analysis
        loudness_stats = self.loudness_detector.get_loudness_statistics(audio, sr)

        # FFT analysis
        frequencies, magnitudes = self.fft_analyzer.compute_fft(audio, sr)
        peak_freqs, peak_mags = self.fft_analyzer.find_peaks(frequencies, magnitudes)

        # Spectrogram
        spec_db, freqs, times = self.spectrogram_gen.compute_log_spectrogram(
            audio, sr
        )

        # Alarm detection
        alarms = self.alarm_detector.detect_alarms(
            audio,
            sensitivity=alarm_sensitivity,
            min_confidence=alarm_min_confidence,
        )

        # Build result
        result = {
            "filepath": str(filepath),
            "audio": audio,
            "sr": sr,
            "duration_sec": duration,
            "loudness": loudness_stats,
            "spectrum": {
                "frequencies": frequencies,
                "magnitudes": magnitudes,
                "peak_frequencies": peak_freqs[:5].tolist() if len(peak_freqs) > 0 else [],
                "peak_magnitudes": peak_mags[:5].tolist() if len(peak_mags) > 0 else [],
            },
            "spectrogram": {
                "spec_db": spec_db,
                "frequencies": freqs,
                "times": times,
            },
            "alarms": alarms,
            "summary": self._generate_summary(audio, sr, loudness_stats, alarms),
        }

        return result

    def analyze_audio(
        self,
        audio: np.ndarray,
        sr: int,
        alarm_sensitivity: float = 0.5,
        alarm_min_confidence: float = 0.6,
    ) -> Dict:
        """
        Analyze an audio array.
        
        Args:
            audio: Audio data (1D numpy array).
            sr: Sample rate (Hz).
            alarm_sensitivity: Alarm detection sensitivity.
            alarm_min_confidence: Minimum alarm confidence.
            
        Returns:
            Analysis results dictionary.
        """
        # Resample if needed
        if sr != self.target_sr:
            from scipy import signal as scipy_signal
            
            ratio = self.target_sr / sr
            n_samples = int(len(audio) * ratio)
            audio = scipy_signal.resample(audio, n_samples).astype(np.float32)
            sr = self.target_sr

        duration = len(audio) / sr

        # Loudness
        loudness_stats = self.loudness_detector.get_loudness_statistics(audio, sr)

        # FFT
        frequencies, magnitudes = self.fft_analyzer.compute_fft(audio, sr)
        peak_freqs, peak_mags = self.fft_analyzer.find_peaks(frequencies, magnitudes)

        # Spectrogram
        spec_db, freqs, times = self.spectrogram_gen.compute_log_spectrogram(
            audio, sr
        )

        # Alarms
        alarms = self.alarm_detector.detect_alarms(
            audio,
            sensitivity=alarm_sensitivity,
            min_confidence=alarm_min_confidence,
        )

        result = {
            "audio": audio,
            "sr": sr,
            "duration_sec": duration,
            "loudness": loudness_stats,
            "spectrum": {
                "frequencies": frequencies,
                "magnitudes": magnitudes,
                "peak_frequencies": peak_freqs[:5].tolist() if len(peak_freqs) > 0 else [],
                "peak_magnitudes": peak_mags[:5].tolist() if len(peak_mags) > 0 else [],
            },
            "spectrogram": {
                "spec_db": spec_db,
                "frequencies": freqs,
                "times": times,
            },
            "alarms": alarms,
            "summary": self._generate_summary(audio, sr, loudness_stats, alarms),
        }

        return result

    def detect_alarms_in_file(
        self,
        filepath: str,
        sensitivity: float = 0.5,
        min_confidence: float = 0.6,
    ) -> List[Dict]:
        """
        Fast alarm detection in file (skips full analysis).
        
        Args:
            filepath: Path to WAV file.
            sensitivity: Alarm sensitivity.
            min_confidence: Minimum confidence.
            
        Returns:
            List of detected alarms.
        """
        audio, sr = self.loader.load(filepath)
        return self.alarm_detector.detect_alarms(
            audio, sensitivity=sensitivity, min_confidence=min_confidence
        )

    def is_audio_too_loud(
        self,
        audio: np.ndarray,
        sr: int,
        threshold_lufs: float = -20.0,
    ) -> bool:
        """
        Check if audio exceeds loudness threshold.
        
        Args:
            audio: Audio data.
            sr: Sample rate.
            threshold_lufs: Loudness threshold (LUFS).
            
        Returns:
            True if audio is louder than threshold.
        """
        lufs, _ = self.loudness_detector.compute_lufs(audio, sr)
        return lufs > threshold_lufs

    def get_fundamental_frequency(
        self,
        audio: np.ndarray,
        sr: int,
        freq_min: float = 20.0,
        freq_max: float = 2000.0,
    ) -> Optional[float]:
        """
        Estimate fundamental frequency (pitch).
        
        Args:
            audio: Audio data.
            sr: Sample rate.
            freq_min: Minimum frequency to consider (Hz).
            freq_max: Maximum frequency to consider (Hz).
            
        Returns:
            Fundamental frequency (Hz) or None if not found.
        """
        frequencies, magnitudes = self.fft_analyzer.compute_fft(audio, sr)
        fundamental, _ = self.fft_analyzer.estimate_fundamental(
            frequencies, magnitudes, freq_min, freq_max
        )
        return fundamental

    @staticmethod
    def _generate_summary(
        audio: np.ndarray,
        sr: int,
        loudness_stats: dict,
        alarms: List[Dict],
    ) -> str:
        """Generate human-readable summary."""
        duration = len(audio) / sr
        peak_db = loudness_stats["peak_db"]
        lufs = loudness_stats["lufs"]

        lines = [
            f"Audio Analysis Summary",
            f"======================",
            f"Duration: {duration:.2f} sec",
            f"Peak Level: {peak_db:.1f} dB",
            f"LUFS: {lufs:.1f}",
            "",
        ]

        if alarms:
            lines.append(f"Alarms Detected: {len(alarms)}")
            for i, alarm in enumerate(alarms, 1):
                alarm_type = alarm["alarm_type"].value
                confidence = alarm["confidence"]
                start = alarm["start_time"]
                end = alarm["end_time"]
                lines.append(
                    f"  {i}. {alarm_type} ({confidence:.0%}) @ {start:.2f}-{end:.2f}s"
                )
        else:
            lines.append("Alarms Detected: None")

        return "\n".join(lines)

    def detect_anomalies(
        self,
        audio: np.ndarray,
        sr: int,
        baseline_audio: Optional[np.ndarray] = None,
        baseline_sr: Optional[int] = None,
        min_snr_db: float = 6.0,
        min_confidence: float = 0.5,
        sensitivity: float = 0.5,
    ) -> Dict:
        """
        Detect acoustic anomalies (screams, crashes, sharp noises).
        
        Args:
            audio: Audio data to analyze.
            sr: Sample rate.
            baseline_audio: Audio to learn ambient baseline from. If None, uses first half of audio.
            baseline_sr: Sample rate of baseline audio (if different).
            min_snr_db: Minimum SNR threshold (dB).
            min_confidence: Minimum confidence threshold (0-1).
            sensitivity: Detection sensitivity multiplier (0.1-1.0).
            
        Returns:
            Dictionary with anomaly detections.
        """
        # Resample if needed
        if sr != self.target_sr:
            from scipy import signal as scipy_signal
            ratio = self.target_sr / sr
            n_samples = int(len(audio) * ratio)
            audio = scipy_signal.resample(audio, n_samples)
            sr = self.target_sr
        
        # Learn baseline
        if baseline_audio is not None:
            if baseline_sr and baseline_sr != self.target_sr:
                from scipy import signal as scipy_signal
                ratio = self.target_sr / baseline_sr
                n_samples = int(len(baseline_audio) * ratio)
                baseline_audio = scipy_signal.resample(baseline_audio, n_samples)
            self.anomaly_detector.learn_baseline(baseline_audio)
        
        # Detect anomalies
        anomalies = self.anomaly_detector.detect_anomalies(
            audio,
            min_snr_db=min_snr_db,
            min_confidence=min_confidence,
            sensitivity=sensitivity,
        )
        
        # Generate summary
        summary = self._generate_anomaly_summary(audio, sr, anomalies)
        
        return {
            "audio": audio,
            "sr": sr,
            "duration_sec": len(audio) / sr,
            "anomalies": anomalies,
            "summary": summary,
            "baseline_rms": self.anomaly_detector.baseline_rms,
        }

    @staticmethod
    def _generate_anomaly_summary(
        audio: np.ndarray,
        sr: int,
        anomalies: List[Dict],
    ) -> str:
        """Generate anomaly detection summary."""
        duration = len(audio) / sr
        rms = np.sqrt(np.mean(audio ** 2))
        peak = np.max(np.abs(audio))
        
        lines = [
            "Anomaly Detection Summary",
            "=========================",
            f"Duration: {duration:.2f} sec",
            f"Peak: {peak:.4f}",
            f"RMS: {rms:.4f}",
            "",
        ]
        
        if anomalies:
            lines.append(f"Anomalies Detected: {len(anomalies)}")
            for i, anom in enumerate(anomalies, 1):
                anom_type = anom["type"].value
                confidence = anom["confidence"]
                snr_db = anom["snr_db"]
                lines.append(
                    f"  {i}. {anom_type} ({confidence:.0%}) SNR:{snr_db:.1f}dB"
                )
        else:
            lines.append("Anomalies Detected: None")
        
        return "\n".join(lines)
