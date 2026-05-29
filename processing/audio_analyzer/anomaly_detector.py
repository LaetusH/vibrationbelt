"""Anomaly Detection: Detect unusual sounds (screams, crashes) above ambient background."""

import numpy as np
from scipy import signal
from typing import Tuple, Optional, List, Dict
from enum import Enum


class AnomalyType(Enum):
    """Categories of detected anomalies."""
    SCREAM_SHOUT = "scream_shout"
    CRASH_BREAK = "crash_break"
    SHARP_NOISE = "sharp_noise"
    ABNORMAL_SPIKE = "abnormal_spike"
    UNKNOWN = "unknown"


class AnomalyDetector:
    """
    Anomaly detection: Detects unusual acoustic events (screams, crashes, etc).
    
    Strategy:
    1. Learn ambient baseline (first ~10 seconds or set manually)
    2. Calculate SNR (Signal vs Noise Ratio)
    3. Analyze spectral anomalies (frequency content differs from baseline)
    4. Analyze temporal anomalies (sudden spikes/changes)
    5. Pattern analysis: Different anomalies have different fingerprints
    """

    def __init__(self, sr: int, baseline_duration_sec: float = 10.0):
        """Initialize anomaly detector.
        
        Args:
            sr: Sample rate
            baseline_duration_sec: How long to learn ambient background (10-20 sec)
        """
        self.sr = sr
        self.baseline_duration_sec = baseline_duration_sec
        
        # Learned baseline (will be set after learning phase)
        self.baseline_rms = None
        self.baseline_spectrum = None
        self.is_calibrated = False

    def learn_baseline(self, audio: np.ndarray) -> Dict:
        """Learn ambient background noise from audio sample (usually silence or background).
        
        Args:
            audio: Audio to learn baseline from (typically ~10 sec of ambient noise)
            
        Returns:
            Dict with baseline statistics
        """
        # Compute baseline RMS
        self.baseline_rms = np.sqrt(np.mean(audio ** 2))
        
        # Compute baseline spectrum (averaged over time)
        freqs, spectra = self._compute_spectrogram(audio)
        self.baseline_spectrum = np.mean(spectra, axis=1)  # Average over time
        
        self.is_calibrated = True
        
        return {
            "baseline_rms": float(self.baseline_rms),
            "baseline_spectrum_bins": len(self.baseline_spectrum),
            "calibrated": True,
        }

    def detect_anomalies(
        self,
        audio: np.ndarray,
        min_snr_db: float = 6.0,  # Must be 6dB above ambient
        min_confidence: float = 0.5,
        sensitivity: float = 0.5,
    ) -> List[Dict]:
        """Detect anomalous events in audio.
        
        Args:
            audio: Audio to analyze
            min_snr_db: Minimum SNR threshold (6dB = must be 2x amplitude of background)
            min_confidence: Minimum confidence to report (0-1)
            sensitivity: Sensitivity multiplier for thresholds
            
        Returns:
            List of detected anomalies with scores
        """
        detections = []
        
        # Safety: If not calibrated, use very basic baseline
        if not self.is_calibrated:
            self._auto_calibrate(audio)
        
        # Compute audio features
        rms = np.sqrt(np.mean(audio ** 2))
        
        # **GATE 1: Overall SNR**
        snr_db = 20 * np.log10(rms / (self.baseline_rms + 1e-10))
        if snr_db < min_snr_db * (1.0 - sensitivity * 0.3):  # Relax with sensitivity
            return []  # Signal not loud enough
        
        # **GATE 2: Duration check (need enough audio)**
        duration_ms = len(audio) / self.sr * 1000
        if duration_ms < 200:  # At least 200ms
            return []
        
        # Analyze different anomaly types
        anomaly_scores = {}
        
        # Check for screams/shouts (high freq spike)
        scream_score = self._score_scream_shout(audio)
        if scream_score > 0.3:
            anomaly_scores[AnomalyType.SCREAM_SHOUT] = scream_score
        
        # Check for crashes/breaks (broad spectrum spike)
        crash_score = self._score_crash_break(audio)
        if crash_score > 0.3:
            anomaly_scores[AnomalyType.CRASH_BREAK] = crash_score
        
        # Check for sharp transients (sudden spike)
        sharp_score = self._score_sharp_noise(audio)
        if sharp_score > 0.3:
            anomaly_scores[AnomalyType.SHARP_NOISE] = sharp_score
        
        # Check for general anomalous spike
        spike_score = self._score_abnormal_spike(audio)
        if spike_score > 0.2:  # More permissive
            anomaly_scores[AnomalyType.ABNORMAL_SPIKE] = spike_score
        
        # Convert scores to detections
        for anomaly_type, score in anomaly_scores.items():
            confidence = self._compute_anomaly_confidence(score, snr_db, audio)
            
            if confidence >= min_confidence:
                detections.append({
                    "type": anomaly_type,
                    "confidence": confidence,
                    "snr_db": float(snr_db),
                    "duration_ms": duration_ms,
                    "rms": float(rms),
                    "baseline_rms": float(self.baseline_rms),
                    "score": score,
                    "timestamp": 0.0,
                })
        
        # Sort by confidence
        detections = sorted(detections, key=lambda x: x["confidence"], reverse=True)
        
        return detections

    def _score_scream_shout(self, audio: np.ndarray) -> float:
        """Score likelihood of scream/shout.
        
        Screams typically:
        - High amplitude (>0.5)
        - High frequencies (>2kHz dominant)
        - Sustained high-freq energy
        - Spectral centroid >3kHz
        """
        amplitude = np.max(np.abs(audio))
        
        # Must be reasonably loud
        if amplitude < 0.2:
            return 0.0
        
        # Compute spectral centroid (where is the energy concentrated?)
        freqs, mags = self._compute_fft(audio)
        if len(freqs) == 0:
            return 0.0
        
        # Spectral centroid
        centroid = np.sum(freqs * mags) / (np.sum(mags) + 1e-10)
        
        # Screams: centroid > 2000 Hz, strong energy > 1000 Hz
        high_freq_mask = freqs > 1000
        high_freq_energy = np.sum(mags[high_freq_mask]) / (np.sum(mags) + 1e-10)
        
        if centroid > 2000 and high_freq_energy > 0.3:
            score = min((centroid - 2000) / 3000 * high_freq_energy, 1.0)
            return float(score)
        
        return 0.0

    def _score_crash_break(self, audio: np.ndarray) -> float:
        """Score likelihood of crash/break sound.
        
        Crashes typically:
        - Transient onset (quick attack)
        - Broad spectrum (energy across many frequencies)
        - Decaying envelope
        - High zero-crossing rate
        """
        # Compute zero-crossing rate (high = sharp/noisy)
        zcr = self._compute_zcr(audio)
        
        # Zero-crossing rate for crashes is typically high (0.2-0.4)
        if zcr < 0.15:
            return 0.0
        
        # Compute spectral spread (how "broad" is the spectrum?)
        freqs, mags = self._compute_fft(audio)
        if len(freqs) == 0:
            return 0.0
        
        centroid = np.sum(freqs * mags) / (np.sum(mags) + 1e-10)
        spread = np.sqrt(np.sum((freqs - centroid) ** 2 * mags) / (np.sum(mags) + 1e-10))
        
        # Crashes have broad spectrum (spread > 1000 Hz)
        if spread > 1000:
            score = min((spread - 1000) / 2000 * zcr, 1.0)
            return float(score)
        
        return 0.0

    def _score_sharp_noise(self, audio: np.ndarray) -> float:
        """Score likelihood of sharp transient noise.
        
        Sharp noises:
        - Very high peak amplitude relative to RMS
        - Quick onset time
        - Crest factor > 5
        """
        peak = np.max(np.abs(audio))
        rms = np.sqrt(np.mean(audio ** 2))
        
        if rms < 1e-10:
            return 0.0
        
        crest_factor = peak / rms
        
        # Sharp sounds have high crest factor (>5)
        if crest_factor > 5:
            score = min((crest_factor - 5) / 10, 1.0)
            return float(score)
        
        return 0.0

    def _score_abnormal_spike(self, audio: np.ndarray) -> float:
        """Score general anomalous spike.
        
        Any event that:
        - Much louder than baseline
        - Different spectral character
        """
        # RMS compared to baseline
        rms = np.sqrt(np.mean(audio ** 2))
        ratio = rms / (self.baseline_rms + 1e-10)
        
        # Must be 3x+ baseline (4.77dB)
        if ratio < 3.0:
            return 0.0
        
        # Compute spectral difference from baseline
        freqs, mags = self._compute_fft(audio)
        if len(freqs) == 0:
            return 0.0
        
        # Compare against baseline spectrum (resample if needed)
        if self.baseline_spectrum is None:
            spectrum_diff = 0.5
        else:
            # Normalize mag to same length as baseline
            if len(mags) != len(self.baseline_spectrum):
                baseline_normalized = np.interp(
                    freqs,
                    np.linspace(0, self.sr/2, len(self.baseline_spectrum)),
                    self.baseline_spectrum
                )
            else:
                baseline_normalized = self.baseline_spectrum
            
            # KL divergence or mean squared difference
            eps = 1e-10
            current_norm = mags / (np.sum(mags) + eps)
            baseline_norm = baseline_normalized / (np.sum(baseline_normalized) + eps)
            
            spectrum_diff = np.sqrt(np.mean((current_norm - baseline_norm) ** 2))
        
        # Score: amplitude ratio + spectral difference
        amplitude_score = min((ratio - 3.0) / 10, 1.0)
        spectral_score = min(spectrum_diff, 1.0)
        
        score = 0.6 * amplitude_score + 0.4 * spectral_score
        return float(score)

    def _compute_anomaly_confidence(
        self,
        anomaly_score: float,
        snr_db: float,
        audio: np.ndarray,
    ) -> float:
        """Compute final confidence (0-1)."""
        # Anomaly pattern: 50%
        pattern_score = anomaly_score * 0.5
        
        # SNR verification: 50%
        # Min 6dB, max 30dB
        snr_score = np.clip((snr_db - 6) / 24, 0, 1) * 0.5
        
        confidence = pattern_score + snr_score
        return min(confidence, 1.0)

    def _auto_calibrate(self, audio: np.ndarray) -> None:
        """Auto-calibrate if not already done (use first half as baseline)."""
        if not self.is_calibrated:
            # Use first 50% as baseline estimate
            baseline_len = len(audio) // 2
            baseline_audio = audio[:baseline_len]
            self.learn_baseline(baseline_audio)

    def _compute_zcr(self, audio: np.ndarray, frame_size: int = 2048) -> float:
        """Compute average zero-crossing rate (0-1)."""
        zcr_frames = []
        
        for i in range(0, len(audio) - frame_size, frame_size):
            frame = audio[i : i + frame_size]
            zcr = np.sum(np.abs(np.diff(np.sign(frame)))) / (2 * len(frame))
            zcr_frames.append(zcr)
        
        return np.mean(zcr_frames) if zcr_frames else 0.0

    def _compute_fft(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute FFT."""
        n_fft = 2 ** int(np.ceil(np.log2(len(audio))))
        window = signal.get_window("hann", len(audio))
        windowed = audio * window
        
        fft_result = np.fft.rfft(windowed, n=n_fft)
        magnitudes = np.abs(fft_result)
        frequencies = np.fft.rfftfreq(n_fft, 1 / self.sr)
        
        return frequencies, magnitudes

    def _compute_spectrogram(
        self,
        audio: np.ndarray,
        n_fft: int = 2048,
        hop_length: int = 512,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Compute spectrogram (freq x time)."""
        freqs, times, spectrogram = signal.spectrogram(
            audio,
            fs=self.sr,
            nperseg=n_fft,
            noverlap=n_fft - hop_length,
        )
        
        return freqs, spectrogram
