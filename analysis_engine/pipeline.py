"""
Audio Analysis Pipeline - Orchestrate all components

High-level interface for complete signal analysis:
  1. DOA estimation
  2. Spectrogram generation
  3. Alarm recognition
  4. Motor mapping
"""

import numpy as np
from typing import Optional, Dict, Tuple

from .doa import DOAEstimator
from .spectrogram import SpectrogramGenerator
from .recognizers import AlarmRecognizer
from .motor_mapper import MotorMapper


class AudioAnalysisPipeline:
    """
    Complete signal processing pipeline.
    
    Takes dual-microphone audio and returns:
    - Direction of arrival (degrees)
    - Alarm detection (confidence)
    - Motor prediction (0-3)
    - Spectrogram visualization
    """

    def __init__(
        self,
        mic_distance: float = 0.05,
        sample_rate: int = 16000,
        model_path: Optional[str] = None,
        use_template_only: bool = True,
    ):
        """
        Args:
            mic_distance: Distance between microphones in meters
            sample_rate: Audio sample rate in Hz
            model_path: Path to trained CNN model (optional)
            use_template_only: Use template matching instead of CNN
        """
        self.sr = sample_rate
        
        # Initialize components
        self.doa = DOAEstimator(mic_distance=mic_distance, sample_rate=sample_rate)
        self.spec_gen = SpectrogramGenerator(sr=sample_rate)
        self.alarm_rec = AlarmRecognizer(
            model_path=model_path,
            use_template_only=use_template_only,
        )
        self.motor_map = MotorMapper()

    def analyze(
        self,
        audio_mic1: np.ndarray,
        audio_mic2: Optional[np.ndarray] = None,
        confidence_threshold: float = 0.3,
        debug: bool = False,
    ) -> Dict:
        """
        Full pipeline analysis.
        
        Args:
            audio_mic1: Audio from microphone 1
            audio_mic2: Audio from microphone 2 (if None, use mic1 for DOA)
            confidence_threshold: Minimum alarm confidence for motor prediction
            debug: Return detailed debug information
            
        Returns:
            {
                'doa_degrees': float or None,
                'alarm_confidence': float,
                'is_alarm': bool,
                'predicted_motor': int or None,
                'motor_intensities': dict,
                'spectrogram': np.ndarray (224, 224),
                'spectrogram_dataurl': str,
                'debug': dict (if debug=True)
            }
        """
        result = {
            'doa_degrees': None,
            'alarm_confidence': 0.0,
            'is_alarm': False,
            'predicted_motor': None,
            'motor_intensities': {},
            'spectrogram': None,
            'spectrogram_dataurl': None,
        }
        
        # ===== STEP 1: DOA ESTIMATION =====
        if audio_mic2 is not None:
            doa_result = self.doa.estimate(audio_mic1, audio_mic2)
            result['doa_degrees'] = doa_result
        
        # ===== STEP 2: SPECTROGRAM GENERATION =====
        try:
            spectrogram = self.spec_gen.generate(audio_mic1)
            result['spectrogram'] = spectrogram
            result['spectrogram_dataurl'] = self.spec_gen.spectrogram_to_dataurl(spectrogram)
        except Exception as e:
            if debug:
                result['debug'] = {'spectrogram_error': str(e)}
        
        # ===== STEP 3: ALARM RECOGNITION =====
        try:
            alarm_result = self.alarm_rec.recognize(result['spectrogram'], debug=debug)
            result['alarm_confidence'] = alarm_result.get('confidence', 0.0)
            result['is_alarm'] = alarm_result.get('is_alarm', False)
            
            if debug:
                result['alarm_debug'] = alarm_result.get('details', {})
        except Exception as e:
            if debug:
                result['alarm_error'] = str(e)
        
        # ===== STEP 4: MOTOR PREDICTION =====
        if (result['is_alarm'] and 
            result['alarm_confidence'] >= confidence_threshold and 
            result['doa_degrees'] is not None):
            
            predicted_motor = self.motor_map.get_motor(result['doa_degrees'])
            result['predicted_motor'] = predicted_motor
            
            # Also compute gradual motor intensities
            result['motor_intensities'] = self.motor_map.angle_to_motor_intensity(
                result['doa_degrees']
            )
        
        return result

    def analyze_batch(
        self,
        audio_mic1_batch: np.ndarray,
        audio_mic2_batch: Optional[np.ndarray] = None,
        **kwargs
    ) -> list:
        """
        Analyze multiple audio chunks.
        
        Args:
            audio_mic1_batch: Array of audio chunks (N, samples)
            audio_mic2_batch: Array of audio chunks (N, samples)
            
        Returns:
            List of analysis results
        """
        results = []
        for i in range(len(audio_mic1_batch)):
            chunk1 = audio_mic1_batch[i]
            chunk2 = audio_mic2_batch[i] if audio_mic2_batch is not None else None
            
            result = self.analyze(chunk1, chunk2, **kwargs)
            results.append(result)
        
        return results

    def get_config(self) -> dict:
        """Return pipeline configuration"""
        return {
            'sample_rate_hz': self.sr,
            'doa': self.doa.get_config(),
            'spectrogram': self.spec_gen.get_config(),
            'recognizer': self.alarm_rec.get_config(),
            'motor_map': self.motor_map.get_config(),
        }

    def get_status(self) -> Dict:
        """Get runtime status of all components"""
        return {
            'doa_estimator': 'ready',
            'spectrogram_generator': 'ready',
            'alarm_recognizer': self.alarm_rec.get_config()['method'],
            'motor_mapper': 'ready',
        }
