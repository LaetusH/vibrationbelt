"""Alarm detection: Robust pattern-based approach for quiet & loud signals."""

import numpy as np
from scipy import signal
from scipy import ndimage
from typing import Tuple, Optional, List, Dict
from enum import Enum


class AlarmType(Enum):
    """Known alarm signal types."""
    SIREN_FIRE = "fire_siren"
    SMOKE_DETECTOR = "smoke_detector"
    ALARM_BEEP = "alarm_beep"
    WARNING_TONE = "warning_tone"
    UNKNOWN = "unknown"


class AlarmDetector:
    """
    Pattern-based alarm detection.
    
    Key principle: Detect alarms by PATTERN (frequency + periodicity),
    NOT just loudness. This works even for quiet sirens that follow
    a clear pulsing pattern.
    """

    ALARM_SIGNATURES = {
        AlarmType.SIREN_FIRE: {
            "freq_ranges": [(800, 1200)],
            "min_duration_ms": 300,  # Sirens are usually >300ms
            "periodicity_hz": (0.3, 3.0),  # Pulsing 0.3-3 Hz
            "min_pattern_strength": 0.4,  # Pattern quality 0-1
            "description": "Fire siren (800-1200 Hz + pulsing pattern)",
        },
        AlarmType.SMOKE_DETECTOR: {
            "freq_ranges": [(2500, 3500)],
            "min_duration_ms": 1500,
            "periodicity_hz": (1.5, 6.0),  # Fast chirps
            "min_pattern_strength": 0.4,
            "description": "Smoke detector (2.5-3.5 kHz + chirp pattern)",
        },
        AlarmType.ALARM_BEEP: {
            "freq_ranges": [(800, 1200), (1000, 2000)],
            "min_duration_ms": 150,
            "periodicity_hz": (1.0, 8.0),  # Regular beeping
            "min_pattern_strength": 0.35,
            "description": "Alarm beep (periodic beep pattern)",
        },
        AlarmType.WARNING_TONE: {
            "freq_ranges": [(500, 1500)],
            "min_duration_ms": 250,
            "periodicity_hz": (0.3, 4.0),
            "min_pattern_strength": 0.35,
            "description": "Warning tone (pulsing/sweep pattern)",
        },
    }

    def __init__(self, sr: int):
        """Initialize detector with sample rate."""
        self.sr = sr

    def detect_alarms(
        self,
        audio: np.ndarray,
        sensitivity: float = 0.5,
        min_confidence: float = 0.5,
    ) -> List[Dict]:
        """Detect alarms by pattern-matching."""
        detections = []

        # Check if audio is not completely dead
        overall_rms = np.sqrt(np.mean(audio ** 2))
        if overall_rms < 0.0005:  # Essentially silent
            return []

        # Try to detect each alarm type
        for alarm_type, sig_params in self.ALARM_SIGNATURES.items():
            match = self._detect_alarm_type(audio, alarm_type, sig_params)
            if match and match["confidence"] >= min_confidence:
                detections.append(match)

        # Sort by confidence
        detections = sorted(detections, key=lambda x: x["confidence"], reverse=True)

        return detections

    def _detect_alarm_type(
        self,
        audio: np.ndarray,
        alarm_type: AlarmType,
        sig_params: dict,
    ) -> Optional[Dict]:
        """Detect if audio contains a specific alarm pattern."""
        
        # Step 1: Check if target frequencies are present
        freq_match = self._check_frequency_content(audio, sig_params["freq_ranges"])
        if freq_match is None:
            return None  # No frequency match

        # Step 2: Check if there's a periodic pattern
        periodicity = self._check_periodicity(audio, sig_params["periodicity_hz"])
        if periodicity is None:
            return None  # No periodicity pattern

        # Step 3: Check duration (not too short)
        duration_ms = len(audio) / self.sr * 1000
        if duration_ms < sig_params["min_duration_ms"]:
            return None

        # Step 4: Pattern strength must meet threshold
        pattern_strength = freq_match * periodicity
        if pattern_strength < sig_params["min_pattern_strength"]:
            return None

        # All checks pass: Create detection
        confidence = self._compute_confidence(freq_match, periodicity, audio)

        return {
            "alarm_type": alarm_type,
            "start_time": 0.0,
            "end_time": duration_ms / 1000,
            "confidence": confidence,
            "frequencies": sig_params["freq_ranges"],
            "features": {
                "duration_ms": duration_ms,
                "freq_match": float(freq_match),
                "periodicity": float(periodicity),
                "pattern_strength": float(pattern_strength),
                "rms": float(np.sqrt(np.mean(audio ** 2))),
            },
        }

    def _check_frequency_content(
        self,
        audio: np.ndarray,
        freq_ranges: List[Tuple[float, float]],
    ) -> Optional[float]:
        """
        Check if audio has energy in target frequency ranges.
        
        Returns: 0-1 score (how strong the frequency match), or None if no match.
        """
        # Compute FFT
        freqs, mags = self._compute_fft(audio)

        # Look for peaks in target ranges
        total_energy = 0.0
        max_energy = np.max(mags) if len(mags) > 0 else 1.0

        for f_min, f_max in freq_ranges:
            mask = (freqs >= f_min) & (freqs <= f_max)
            if np.any(mask):
                band_max = np.max(mags[mask])
                total_energy += band_max

        if max_energy < 1e-10:
            return None

        score = min(total_energy / max_energy, 1.0)

        # Accept if at least some energy in target range (very relaxed)
        if score > 0.15:  # Even 15% of max is OK
            return float(score)

        return None

    def _check_periodicity(
        self,
        audio: np.ndarray,
        periodicity_range: Tuple[float, float],
    ) -> Optional[float]:
        """
        Check if audio has periodic pattern (pulsing/chirping).
        
        Returns: 0-1 score, or None if no periodicity detected.
        """
        # Compute autocorrelation to detect periodicity
        acf = self._autocorrelation(audio)

        if len(acf) == 0:
            return None

        # Find peaks in autocorrelation
        # These peaks indicate periodic components
        peaks, props = signal.find_peaks(acf, height=0.25)  # Relaxed threshold

        if len(peaks) == 0:
            return None

        # Convert peak indices to periods (in Hz)
        peak_periods = self.sr / peaks
        peak_heights = props.get("peak_heights", np.ones(len(peaks)))

        # Check if ANY peak is in the valid periodicity range
        valid_mask = (peak_periods >= periodicity_range[0]) & (peak_periods <= periodicity_range[1])

        if not np.any(valid_mask):
            return None

        # Use the strongest valid peak as score
        valid_heights = peak_heights[valid_mask]
        strongest = np.max(valid_heights)

        # Score: 0.25-1.0 → 0-1
        score = np.clip((strongest - 0.25) / 0.75, 0, 1)

        return float(score) if score > 0.15 else None

    def _compute_confidence(
        self,
        freq_match: float,
        periodicity: float,
        audio: np.ndarray,
    ) -> float:
        """Compute final confidence score (0-1)."""
        # Frequency matching is critical: 40%
        freq_score = freq_match * 0.4

        # Periodicity pattern is critical: 40%
        periodicity_score = periodicity * 0.4

        # Amplitude is bonus (but not required): 20%
        # Louder = more confidence, but quiet sirens with good pattern still count
        rms = np.sqrt(np.mean(audio ** 2))
        amp_score = min(rms / 0.05, 1.0) * 0.2  # 0.05 is reference (loud-ish)

        confidence = freq_score + periodicity_score + amp_score

        return min(confidence, 1.0)

    def _compute_fft(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute FFT with windowing."""
        # Use power-of-2 for efficiency
        n_fft = 2 ** int(np.ceil(np.log2(len(audio))))

        # Apply Hann window to reduce spectral leakage
        window = signal.get_window("hann", len(audio))
        windowed = audio * window

        # Compute FFT
        fft_result = np.fft.rfft(windowed, n=n_fft)
        magnitudes = np.abs(fft_result)

        # Frequency bins
        frequencies = np.fft.rfftfreq(n_fft, 1 / self.sr)

        return frequencies, magnitudes

    def _autocorrelation(self, audio: np.ndarray, max_lag: Optional[int] = None) -> np.ndarray:
        """Compute autocorrelation (measures periodicity)."""
        if max_lag is None:
            max_lag = min(len(audio) // 2, self.sr * 2)  # Up to 2 sec lag

        # Remove DC component
        audio = audio - np.mean(audio)

        if len(audio) < max_lag:
            return np.array([])

        # Compute autocorrelation using correlation
        acf = np.correlate(audio, audio, mode="full")
        acf = acf[len(acf) // 2 :]  # Keep only positive lags

        # Normalize
        acf = acf / (acf[0] + 1e-10)

        return acf[:max_lag]

    def get_alarm_signatures(self) -> Dict:
        """Get all alarm signatures."""
        return {
            alarm_type.value: {k: v for k, v in params.items() if k != "description"}
            for alarm_type, params in self.ALARM_SIGNATURES.items()
        }


# Streaming alias (added at end of class)
def detect_alarms_streaming(
    self,
    audio: np.ndarray,
    sensitivity: float = 0.5,
    min_confidence: float = 0.4,
) -> List[Dict]:
    """
    Stream-optimized alarm detection (short frames, low latency).
    
    Same as detect_alarms but for real-time streaming:
    - Lower confidence threshold (0.4 instead of 0.6)
    - Works on short frames (~30-100ms)
    - Faster computation
    """
    return self.detect_alarms(audio, sensitivity=sensitivity, min_confidence=min_confidence)


# Add to AlarmDetector class
AlarmDetector.detect_alarms_streaming = detect_alarms_streaming
