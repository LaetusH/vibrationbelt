"""
DOA Estimator - Time Difference of Arrival (TDOA)

Estimates the direction a sound is coming from using 2+ microphones.
Returns angle in degrees (0-360°).

Coordinate system:
  0°   = Front
  90°  = Right
  180° = Back
  270° = Left
"""

import numpy as np
from typing import Tuple


class DOAEstimator:
    """
    TDOA-based Direction of Arrival estimation.
    
    Works with 2 microphones separated by a known distance.
    Uses cross-correlation to find time delay, then converts to angle.
    """

    def __init__(self, mic_distance: float = 0.05, sample_rate: int = 16000):
        """
        Args:
            mic_distance: Distance between microphones in meters (default: 5cm)
            sample_rate: Audio sample rate in Hz
        """
        self.mic_distance = mic_distance
        self.sr = sample_rate
        self.speed_of_sound = 343.0  # m/s at ~20°C
        
        # Clamp angle estimates to valid range
        self.max_angle = np.arcsin(self.speed_of_sound * mic_distance / self.sr)

    def estimate(self, audio_mic1: np.ndarray, audio_mic2: np.ndarray) -> float:
        """
        Estimate direction of arrival.
        
        Args:
            audio_mic1: Audio samples from microphone 1
            audio_mic2: Audio samples from microphone 2
            
        Returns:
            DOA angle in degrees (0-360), or None if estimate failed
        """
        if len(audio_mic1) == 0 or len(audio_mic2) == 0:
            return None
        
        # Ensure float32
        audio_mic1 = np.asarray(audio_mic1, dtype=np.float32)
        audio_mic2 = np.asarray(audio_mic2, dtype=np.float32)
        
        # Skip if too quiet (no signal)
        rms1 = np.sqrt(np.mean(audio_mic1 ** 2))
        rms2 = np.sqrt(np.mean(audio_mic2 ** 2))
        
        if rms1 < 1e-5 or rms2 < 1e-5:
            return None
        
        # Normalize to prevent numerical issues
        audio_mic1 = audio_mic1 / (rms1 + 1e-10)
        audio_mic2 = audio_mic2 / (rms2 + 1e-10)
        
        # Cross-correlation to find TDOA
        tdoa_samples = self._estimate_tdoa(audio_mic1, audio_mic2)
        
        if tdoa_samples is None:
            return None
        
        # Convert TDOA to angle
        angle_degrees = self._tdoa_to_angle(tdoa_samples)
        
        return angle_degrees

    def _estimate_tdoa(self, audio1: np.ndarray, audio2: np.ndarray) -> int:
        """
        Estimate Time Difference of Arrival using cross-correlation.
        
        Returns:
            Time delay in samples (positive = audio2 is delayed)
        """
        # Cross-correlation
        correlation = np.correlate(audio1, audio2, mode='full')
        
        # Find peak (avoid edges)
        center = len(audio1)
        search_range = min(center, int(self.sr * 0.01))  # ±10ms
        
        search_start = max(0, center - search_range)
        search_end = min(len(correlation), center + search_range)
        
        peak_idx = np.argmax(correlation[search_start:search_end]) + search_start
        tdoa = peak_idx - center
        
        return tdoa

    def _tdoa_to_angle(self, tdoa_samples: int) -> float:
        """
        Convert Time Difference of Arrival to angle in degrees.
        
        Args:
            tdoa_samples: Time delay in samples
            
        Returns:
            Angle in degrees (0-360)
        """
        # Convert samples to time
        tdoa_time = tdoa_samples / self.sr
        
        # Limit to physical bounds
        max_tdoa_time = self.mic_distance / self.speed_of_sound
        tdoa_time = np.clip(tdoa_time, -max_tdoa_time, max_tdoa_time)
        
        # Calculate angle
        # sin(theta) = (c * tdoa) / d
        # where c = speed of sound, d = mic distance
        sin_theta = (self.speed_of_sound * tdoa_time) / self.mic_distance
        sin_theta = np.clip(sin_theta, -1.0, 1.0)
        
        angle_rad = np.arcsin(sin_theta)
        angle_deg = np.degrees(angle_rad)
        
        # Convert to 0-360 range
        # Negative angle = from left, positive = from right
        # Map: -90 to 90 degrees into 0-360 degrees
        if angle_deg < 0:
            # Left side: -90 to 0 → 270 to 360
            angle_deg = 360 + angle_deg
        
        return float(angle_deg)

    def get_config(self) -> dict:
        """Return configuration for debugging"""
        return {
            'mic_distance_m': self.mic_distance,
            'sample_rate_hz': self.sr,
            'speed_of_sound_ms': self.speed_of_sound,
            'max_angle_rad': float(self.max_angle),
        }
