"""Alarm signal detection with FFT-based frequency analysis."""

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
    """Detect and classify alarm signals in audio."""

    # Alarm signatures
    ALARM_SIGNATURES = {
        AlarmType.SIREN_FIRE: {
            "freq_ranges": [(800, 1200)],
            "harmonics": [(1600, 2400)],
            "min_duration_ms": 500,
            "periodicity_hz": (0.5, 2.0),
            "min_amplitude": 0.05,
            "description": "Fire siren (800-1200 Hz pulsing)",
        },
        AlarmType.SMOKE_DETECTOR: {
            "freq_ranges": [(2500, 3500)],
            "harmonics": [(5000, 7000)],
            "min_duration_ms": 2000,
            "periodicity_hz": (2.0, 4.0),
            "min_amplitude": 0.04,
            "description": "Smoke detector (2.5-3.5 kHz chirps)",
        },
        AlarmType.ALARM_BEEP: {
            "freq_ranges": [(800, 1200), (1000, 2000)],
            "harmonics": [],
            "min_duration_ms": 200,
            "periodicity_hz": (1.0, 5.0),
            "min_amplitude": 0.06,
            "description": "Alarm beep (800-2000 Hz)",
        },
        AlarmType.WARNING_TONE: {
            "freq_ranges": [(500, 1500), (1000, 2500)],
            "harmonics": [],
            "min_duration_ms": 300,
            "periodicity_hz": (0.5, 3.0),
            "min_amplitude": 0.05,
            "description": "Warning tone (500-2500 Hz)",
        },
    }

    def __init__(self, sr: int):
        """Initialize detector with sample rate."""
        self.sr = sr

    def detect_alarms(
        self,
        audio: np.ndarray,
        sensitivity: float = 0.5,
        min_confidence: float = 0.6,
    ) -> List[Dict]:
        """Detect alarm signals in audio."""
        detections = []

        # **GATE 1: Overall signal amplitude**
        overall_rms = np.sqrt(np.mean(audio ** 2))
        overall_peak = np.max(np.abs(audio))
        
        if overall_rms < 0.01 and overall_peak < 0.05:
            return []  # Signal too quiet

        # Compute FFT for frequency analysis
        fft_freqs, fft_mags = self._compute_fft(audio)

        # Detect each alarm type
        for alarm_type, sig_params in self.ALARM_SIGNATURES.items():
            matches = self._detect_alarm_type(
                audio, fft_freqs, fft_mags, alarm_type, sig_params, sensitivity
            )
            detections.extend(matches)

        # Filter by confidence
        detections = [d for d in detections if d["confidence"] >= min_confidence]

        # Sort by start time
        detections = sorted(detections, key=lambda x: x["start_time"])

        # Merge overlapping detections
        detections = self._merge_overlapping(detections)

        return detections

    def _detect_alarm_type(
        self,
        audio: np.ndarray,
        fft_freqs: np.ndarray,
        fft_mags: np.ndarray,
        alarm_type: AlarmType,
        sig_params: dict,
        sensitivity: float,
    ) -> List[Dict]:
        """Detect specific alarm type using FFT peaks."""
        matches = []

        # Check if FFT has strong peaks in target frequency ranges
        freq_score = self._score_fft_frequency(fft_freqs, fft_mags, sig_params["freq_ranges"])
        
        # **GATE 1: Frequency must be present in FFT**
        if freq_score < 0.3:  # At least 30% of max peak in target range
            return []

        # **GATE 2: Signal amplitude**
        overall_rms = np.sqrt(np.mean(audio ** 2))
        if overall_rms < sig_params["min_amplitude"]:
            return []

        # **GATE 3: Periodicity check**
        periodicity_score = self._score_periodicity(audio, sig_params["periodicity_hz"])
        if periodicity_score < 0.1:  # Very relaxed
            return []

        # All gates pass: Create detection
        duration = len(audio) / self.sr
        confidence = self._compute_confidence(freq_score, periodicity_score, overall_rms, sig_params)

        if confidence >= 0.5:  # Minimum confidence
            matches.append(
                {
                    "alarm_type": alarm_type,
                    "start_time": 0.0,
                    "end_time": duration,
                    "confidence": confidence,
                    "frequencies": sig_params["freq_ranges"],
                    "features": {
                        "duration_ms": duration * 1000,
                        "freq_score": float(freq_score),
                        "periodicity_score": float(periodicity_score),
                        "rms": float(overall_rms),
                    },
                }
            )

        return matches

    def _score_fft_frequency(
        self,
        fft_freqs: np.ndarray,
        fft_mags: np.ndarray,
        freq_ranges: List[Tuple[float, float]],
    ) -> float:
        """Score FFT match to frequency ranges (0-1)."""
        if fft_mags.size == 0:
            return 0.0

        overall_max = np.max(fft_mags)
        if overall_max < 1e-10:
            return 0.0

        total_energy = 0.0
        for f_min, f_max in freq_ranges:
            mask = (fft_freqs >= f_min) & (fft_freqs <= f_max)
            if np.any(mask):
                band_max = np.max(fft_mags[mask])
                total_energy += band_max

        # Score: how strong the target bands are relative to overall max
        score = min(total_energy / overall_max, 1.0)
        return float(score)

    def _score_periodicity(
        self,
        audio: np.ndarray,
        periodicity_range: Tuple[float, float],
    ) -> float:
        """Score signal periodicity (0-1)."""
        if len(audio) < self.sr // 10:
            return 0.0

        # Compute autocorrelation
        acf = self._autocorrelation(audio, max_lag=self.sr)
        if len(acf) == 0:
            return 0.0

        # Find peaks in ACF
        peaks, properties = signal.find_peaks(acf, height=0.3, distance=self.sr // 100)
        
        if len(peaks) == 0:
            return 0.0

        # Check if peaks are in valid periodicity range
        peak_periods = self.sr / peaks
        peak_heights = properties.get("peak_heights", np.ones(len(peaks)))

        valid_mask = (peak_periods >= periodicity_range[0]) & (peak_periods <= periodicity_range[1])
        valid_heights = peak_heights[valid_mask]

        if len(valid_heights) == 0:
            return 0.0

        # Score based on strongest valid peak
        strongest = np.max(valid_heights)
        score = np.clip((strongest - 0.3) / 0.7, 0, 1)
        return float(score)

    def _compute_confidence(
        self,
        freq_score: float,
        periodicity_score: float,
        rms: float,
        sig_params: dict,
    ) -> float:
        """Compute overall confidence (0-1)."""
        confidence = 0.0

        # Frequency is most important
        confidence += 0.5 * freq_score

        # Periodicity is important for alarms
        confidence += 0.3 * periodicity_score

        # Amplitude matters
        amplitude_score = min(rms / 0.3, 1.0)  # 0.3 is "loud"
        confidence += 0.2 * amplitude_score

        return min(confidence, 1.0)

    def _compute_fft(self, audio: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Compute FFT."""
        n_fft = 2 ** int(np.ceil(np.log2(len(audio))))
        window = signal.get_window("hann", len(audio))
        windowed = audio * window

        fft_result = np.fft.rfft(windowed, n=n_fft)
        magnitudes = np.abs(fft_result)
        frequencies = np.fft.rfftfreq(n_fft, 1 / self.sr)

        return frequencies, magnitudes

    @staticmethod
    def _autocorrelation(signal_data: np.ndarray, max_lag: Optional[int] = None) -> np.ndarray:
        """Compute autocorrelation."""
        if max_lag is None:
            max_lag = len(signal_data) // 2

        signal_data = signal_data - np.mean(signal_data)
        acf = np.correlate(signal_data, signal_data, mode="full")
        acf = acf[len(acf) // 2 :]
        acf = acf / (acf[0] + 1e-10)
        return acf[:max_lag]

    @staticmethod
    def _merge_overlapping(detections: List[Dict]) -> List[Dict]:
        """Merge overlapping detections."""
        if not detections:
            return []

        merged = []
        current = detections[0].copy()

        for next_det in detections[1:]:
            gap = next_det["start_time"] - current["end_time"]
            if gap < 0.5:
                current["end_time"] = max(current["end_time"], next_det["end_time"])
                current["confidence"] = (current["confidence"] + next_det["confidence"]) / 2
            else:
                merged.append(current)
                current = next_det.copy()

        merged.append(current)
        return merged

    def get_alarm_signatures(self) -> Dict:
        """Get all alarm signatures."""
        return {
            alarm_type.value: params for alarm_type, params in self.ALARM_SIGNATURES.items()
        }
