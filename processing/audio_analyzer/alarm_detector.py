"""Alarm signal detection and pattern matching."""

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

    # Alarm signatures: (freq_min, freq_max, name)
    ALARM_SIGNATURES = {
        AlarmType.SIREN_FIRE: {
            "freq_ranges": [(800, 1200)],  # Main siren frequency
            "harmonics": [(1600, 2400), (2400, 3600)],
            "min_duration_ms": 500,
            "periodicity_hz": (0.5, 2.0),  # Pulsing frequency
            "description": "Fire siren (continuous/pulsing 800-1200 Hz)",
        },
        AlarmType.SMOKE_DETECTOR: {
            "freq_ranges": [(2500, 3500)],  # Chirp frequency
            "harmonics": [(5000, 7000)],
            "min_duration_ms": 2000,  # Usually >2 sec sequences
            "periodicity_hz": (2.0, 4.0),  # Fast chirps
            "description": "Smoke detector (chirps 2.5-3.5 kHz)",
        },
        AlarmType.ALARM_BEEP: {
            "freq_ranges": [(800, 1200), (1000, 2000)],
            "harmonics": [],
            "min_duration_ms": 200,
            "periodicity_hz": (1.0, 5.0),  # Regular beeping
            "description": "Generic alarm beep (800-2000 Hz)",
        },
        AlarmType.WARNING_TONE: {
            "freq_ranges": [(500, 1500), (1000, 2500)],
            "harmonics": [],
            "min_duration_ms": 300,
            "periodicity_hz": (0.5, 3.0),
            "description": "Warning tone (500-2500 Hz sweep/steady)",
        },
    }

    def __init__(self, sr: int):
        """
        Initialize alarm detector.
        
        Args:
            sr: Sample rate (Hz).
        """
        self.sr = sr

    def detect_alarms(
        self,
        audio: np.ndarray,
        sensitivity: float = 0.5,
        min_confidence: float = 0.6,
    ) -> List[Dict]:
        """
        Detect alarm signals in audio.
        
        Args:
            audio: Audio signal.
            sensitivity: Detection sensitivity (0-1). Higher = more detections.
            min_confidence: Minimum confidence score (0-1).
            
        Returns:
            List of detected alarms, each with:
            - alarm_type: AlarmType
            - start_time: seconds
            - end_time: seconds
            - confidence: score 0-1
            - frequencies: detected frequencies
            - features: dict of detection features
        """
        detections = []

        # Compute spectrogram for time-frequency analysis
        spec_db, freqs, times = self._compute_spec(audio)

        # Detect each alarm type
        for alarm_type, sig_params in self.ALARM_SIGNATURES.items():
            matches = self._detect_alarm_type(
                audio, spec_db, freqs, times, alarm_type, sig_params, sensitivity
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
        spec_db: np.ndarray,
        freqs: np.ndarray,
        times: np.ndarray,
        alarm_type: AlarmType,
        sig_params: dict,
        sensitivity: float,
    ) -> List[Dict]:
        """Detect specific alarm type."""
        matches = []
        freq_ranges = sig_params["freq_ranges"]

        # Find time-frequency regions matching alarm signature
        energy_map = self._compute_energy_map(spec_db, freqs, freq_ranges)

        # Detect continuous regions
        threshold = np.percentile(energy_map, (1 - sensitivity) * 100)
        active = energy_map > threshold

        # Find contiguous segments
        segments = self._find_segments(active, times)

        for start_time, end_time, segment_energy in segments:
            duration_ms = (end_time - start_time) * 1000
            if duration_ms < sig_params["min_duration_ms"]:
                continue

            # Compute confidence
            confidence = self._compute_confidence(
                audio,
                spec_db,
                freqs,
                times,
                start_time,
                end_time,
                alarm_type,
                sig_params,
            )

            if confidence > 0:
                matches.append(
                    {
                        "alarm_type": alarm_type,
                        "start_time": start_time,
                        "end_time": end_time,
                        "confidence": confidence,
                        "frequencies": freq_ranges,
                        "features": {
                            "duration_ms": duration_ms,
                            "segment_energy": float(segment_energy),
                        },
                    }
                )

        return matches

    def _compute_confidence(
        self,
        audio: np.ndarray,
        spec_db: np.ndarray,
        freqs: np.ndarray,
        times: np.ndarray,
        start_time: float,
        end_time: float,
        alarm_type: AlarmType,
        sig_params: dict,
    ) -> float:
        """Compute detection confidence (0-1)."""
        confidence = 0.0

        # 1. Energy in target frequency ranges
        energy_score = self._score_frequency_match(
            spec_db, freqs, sig_params["freq_ranges"]
        )
        confidence += 0.3 * energy_score

        # 2. Harmonics presence
        if sig_params["harmonics"]:
            harmonics_score = self._score_frequency_match(
                spec_db, freqs, sig_params["harmonics"]
            )
            confidence += 0.2 * harmonics_score

        # 3. Periodicity (pulsing/chirping)
        periodicity_score = self._score_periodicity(
            audio, start_time, end_time, sig_params["periodicity_hz"]
        )
        confidence += 0.3 * periodicity_score

        # 4. Loudness (alarms are typically loud)
        loudness_score = self._score_loudness(audio, start_time, end_time)
        confidence += 0.2 * loudness_score

        return min(confidence, 1.0)

    def _score_frequency_match(
        self,
        spec_db: np.ndarray,
        freqs: np.ndarray,
        freq_ranges: List[Tuple[float, float]],
    ) -> float:
        """Score how well signal matches frequency ranges (0-1)."""
        if spec_db.size == 0:
            return 0.0

        total_score = 0.0
        for f_min, f_max in freq_ranges:
            mask = (freqs >= f_min) & (freqs <= f_max)
            if np.any(mask):
                band_energy = np.mean(spec_db[mask, :])
                total_score += band_energy

        score = np.clip(total_score / (np.max(spec_db) + 1e-10), 0, 1)
        return float(score)

    def _score_periodicity(
        self,
        audio: np.ndarray,
        start_time: float,
        end_time: float,
        periodicity_range: Tuple[float, float],
    ) -> float:
        """Score signal periodicity (0-1)."""
        # Extract segment
        start_idx = int(start_time * self.sr)
        end_idx = int(end_time * self.sr)
        segment = audio[start_idx:end_idx]

        if len(segment) < self.sr // 10:  # Too short
            return 0.0

        # Compute autocorrelation
        acf = self._autocorrelation(segment)
        if acf.size == 0:
            return 0.0

        # Find peaks in autocorrelation (indicates periodicity)
        peaks, _ = signal.find_peaks(acf, height=0.3)

        if len(peaks) == 0:
            return 0.0

        # Check if peak periods fall within expected range
        peak_periods = self.sr / peaks
        in_range = np.any(
            (peak_periods >= periodicity_range[0])
            & (peak_periods <= periodicity_range[1])
        )

        return 0.7 if in_range else 0.3

    def _score_loudness(
        self,
        audio: np.ndarray,
        start_time: float,
        end_time: float,
    ) -> float:
        """Score segment loudness relative to overall signal (0-1)."""
        start_idx = int(start_time * self.sr)
        end_idx = int(end_time * self.sr)
        segment = audio[start_idx:end_idx]

        segment_rms = np.sqrt(np.mean(segment ** 2))
        overall_rms = np.sqrt(np.mean(audio ** 2))

        if overall_rms < 1e-10:
            return 0.5

        loudness_ratio = segment_rms / overall_rms
        # Alarms are typically >2x louder than average
        score = min(loudness_ratio / 2.0, 1.0)
        return float(score)

    def _compute_energy_map(
        self,
        spec_db: np.ndarray,
        freqs: np.ndarray,
        freq_ranges: List[Tuple[float, float]],
    ) -> np.ndarray:
        """Compute energy over time in target frequency ranges."""
        energy = np.zeros(spec_db.shape[1])

        for f_min, f_max in freq_ranges:
            mask = (freqs >= f_min) & (freqs <= f_max)
            if np.any(mask):
                band_energy = np.mean(spec_db[mask, :], axis=0)
                energy += band_energy

        return energy

    def _find_segments(
        self,
        active: np.ndarray,
        times: np.ndarray,
    ) -> List[Tuple[float, float, float]]:
        """Find contiguous segments in boolean array."""
        segments = []

        # Dilate to merge close-by detections
        dilated = ndimage.binary_dilation(active, structure=np.ones(3))

        # Find connected components
        labeled, n_labels = ndimage.label(dilated)

        for label_id in range(1, n_labels + 1):
            mask = labeled == label_id
            indices = np.where(mask)[0]

            if len(indices) == 0:
                continue

            start_idx = indices[0]
            end_idx = indices[-1]

            start_time = times[start_idx] if start_idx < len(times) else times[-1]
            end_time = times[end_idx] if end_idx < len(times) else times[-1]

            segment_energy = np.mean(active[mask])
            segments.append((start_time, end_time, segment_energy))

        return segments

    def _compute_spec(
        self,
        audio: np.ndarray,
        n_fft: int = 2048,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute spectrogram."""
        f, t, Sxx = signal.spectrogram(
            audio, fs=self.sr, nperseg=n_fft, noverlap=n_fft // 2
        )
        Sxx_db = 10 * np.log10(np.abs(Sxx) + 1e-10)
        return Sxx_db, f, t

    @staticmethod
    def _autocorrelation(signal_data: np.ndarray, max_lag: Optional[int] = None) -> np.ndarray:
        """Compute autocorrelation function."""
        if max_lag is None:
            max_lag = len(signal_data) // 2

        signal_data = signal_data - np.mean(signal_data)
        acf = np.correlate(signal_data, signal_data, mode="full")
        acf = acf[len(acf) // 2 :]
        acf = acf / acf[0]
        return acf[:max_lag]

    @staticmethod
    def _merge_overlapping(detections: List[Dict]) -> List[Dict]:
        """Merge overlapping or adjacent detections."""
        if not detections:
            return []

        merged = []
        current = detections[0].copy()

        for next_det in detections[1:]:
            # Check overlap or proximity
            gap = next_det["start_time"] - current["end_time"]
            if gap < 0.5:  # Overlap or <500ms gap
                # Merge: extend end time, average confidence
                current["end_time"] = max(current["end_time"], next_det["end_time"])
                current["confidence"] = (current["confidence"] + next_det["confidence"]) / 2
            else:
                merged.append(current)
                current = next_det.copy()

        merged.append(current)
        return merged

    def get_alarm_signatures(self) -> Dict:
        """Get all alarm signatures for reference."""
        return {
            alarm_type.value: params for alarm_type, params in self.ALARM_SIGNATURES.items()
        }
