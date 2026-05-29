"""
Analysis Engine - Signal Processing Pipeline for VibrationBelt

High-level orchestration:
  1. DOA (Direction of Arrival) - from 2 microphones
  2. Spectrogram - Visual representation of audio
  3. Alarm Recognition - CNN or Template-based
  4. Motor Mapping - Angle to motor index
"""

from .doa.estimator import DOAEstimator
from .spectrogram.generator import SpectrogramGenerator
from .recognizers.alarm_recognizer import AlarmRecognizer
from .motor_mapper import MotorMapper
from .pipeline import AudioAnalysisPipeline

__all__ = [
    'DOAEstimator',
    'SpectrogramGenerator',
    'AlarmRecognizer',
    'MotorMapper',
    'AudioAnalysisPipeline',
]
