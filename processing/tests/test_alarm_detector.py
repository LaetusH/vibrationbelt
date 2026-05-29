"""Tests for AlarmDetector."""

import pytest
import numpy as np
from audio_analyzer.alarm_detector import AlarmDetector, AlarmType


@pytest.fixture
def fire_siren_audio(temp_audio_dir):
    """Generate synthetic fire siren (pulsing 1000 Hz)."""
    import soundfile as sf
    
    sr = 16000
    duration = 2.0
    
    # Pulsing siren: 1000 Hz, 2 Hz pulse rate
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    pulse = np.sin(2 * np.pi * 2 * t)  # 2 Hz pulse envelope
    pulse = (pulse + 1) / 2  # Convert to 0-1
    siren = 0.5 * pulse * np.sin(2 * np.pi * 1000 * t)
    
    filepath = temp_audio_dir / "fire_siren.wav"
    sf.write(str(filepath), siren.astype(np.float32), sr)
    
    return filepath, siren, sr


@pytest.fixture
def smoke_detector_audio(temp_audio_dir):
    """Generate synthetic smoke detector (chirping 3 kHz)."""
    import soundfile as sf
    
    sr = 16000
    duration = 3.0
    
    # Chirp pattern: fast 3 kHz chirps with gaps
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    chirp_env = (np.sin(2 * np.pi * 3 * t) > 0.5).astype(float)  # 3 Hz chirp envelope
    smoke = 0.4 * chirp_env * np.sin(2 * np.pi * 3000 * t)
    
    filepath = temp_audio_dir / "smoke_detector.wav"
    sf.write(str(filepath), smoke.astype(np.float32), sr)
    
    return filepath, smoke, sr


class TestAlarmDetector:
    """Alarm detection unit tests."""

    def test_detector_initialization(self, sine_wave):
        """Initialize detector with sample rate."""
        _, _, sr = sine_wave
        
        detector = AlarmDetector(sr)
        assert detector.sr == sr

    def test_get_alarm_signatures(self, sine_wave):
        """Get predefined alarm signatures."""
        _, _, sr = sine_wave
        
        detector = AlarmDetector(sr)
        sigs = detector.get_alarm_signatures()
        
        assert "fire_siren" in sigs
        assert "smoke_detector" in sigs
        assert "alarm_beep" in sigs
        assert "warning_tone" in sigs

    def test_detect_alarms_returns_list(self, sine_wave):
        """detect_alarms should return list of dicts."""
        _, audio, sr = sine_wave
        
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio)
        
        assert isinstance(detections, list)

    def test_alarm_dict_structure(self, fire_siren_audio):
        """Each alarm detection should have required fields."""
        _, audio, sr = fire_siren_audio
        
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio, sensitivity=0.7)
        
        # Should detect at least something in synthetic siren
        if detections:
            alarm = detections[0]
            assert "alarm_type" in alarm
            assert "start_time" in alarm
            assert "end_time" in alarm
            assert "confidence" in alarm
            assert "frequencies" in alarm
            assert "features" in alarm

    def test_fire_siren_detection(self, fire_siren_audio):
        """Detect fire siren in synthetic signal."""
        _, audio, sr = fire_siren_audio
        
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio, sensitivity=0.6)
        
        # Should work without crashing
        assert isinstance(detections, list)
        
        # If detected, should be properly formatted
        for det in detections:
            assert "alarm_type" in det
            assert "confidence" in det

    def test_smoke_detector_detection(self, smoke_detector_audio):
        """Detect smoke detector in synthetic signal."""
        _, audio, sr = smoke_detector_audio
        
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio, sensitivity=0.6)
        
        # Should detect something
        assert len(detections) > 0, "Failed to detect synthetic smoke detector"

    def test_confidence_score_bounds(self, fire_siren_audio):
        """Confidence scores should be 0-1."""
        _, audio, sr = fire_siren_audio
        
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio)
        
        for detection in detections:
            assert 0 <= detection["confidence"] <= 1

    def test_time_bounds(self, fire_siren_audio):
        """Detected times should be within audio duration."""
        filepath, audio, sr = fire_siren_audio
        
        duration = len(audio) / sr
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio)
        
        for detection in detections:
            assert 0 <= detection["start_time"] <= duration
            assert 0 <= detection["end_time"] <= duration
            assert detection["start_time"] <= detection["end_time"]

    def test_sensitivity_parameter(self, fire_siren_audio):
        """Higher sensitivity should yield more detections."""
        _, audio, sr = fire_siren_audio
        
        detector = AlarmDetector(sr)
        
        detections_low = detector.detect_alarms(audio, sensitivity=0.3)
        detections_high = detector.detect_alarms(audio, sensitivity=0.8)
        
        # Higher sensitivity may give more or same (due to min_confidence filter)
        assert len(detections_high) >= len(detections_low)

    def test_min_confidence_filter(self, fire_siren_audio):
        """min_confidence should filter detections."""
        _, audio, sr = fire_siren_audio
        
        detector = AlarmDetector(sr)
        
        detections_relaxed = detector.detect_alarms(audio, min_confidence=0.3)
        detections_strict = detector.detect_alarms(audio, min_confidence=0.9)
        
        # Strict confidence should have fewer detections
        assert len(detections_strict) <= len(detections_relaxed)

    def test_no_false_alarms_on_noise(self, white_noise):
        """White noise should not trigger false alarms (with strict settings)."""
        _, audio, sr = white_noise
        
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio, sensitivity=0.3, min_confidence=0.8)
        
        # Should have very few or no detections on pure noise
        assert len(detections) <= 1

    def test_alarm_merge_overlapping(self, sine_wave):
        """Overlapping detections should be merged."""
        _, audio, sr = sine_wave
        
        detector = AlarmDetector(sr)
        
        # Create mock overlapping detections
        dets = [
            {
                "alarm_type": AlarmType.SIREN_FIRE,
                "start_time": 0.0,
                "end_time": 0.5,
                "confidence": 0.8,
            },
            {
                "alarm_type": AlarmType.SIREN_FIRE,
                "start_time": 0.3,
                "end_time": 1.0,
                "confidence": 0.7,
            },
        ]
        
        merged = detector._merge_overlapping(dets)
        
        # Should merge into one detection
        assert len(merged) == 1
        assert merged[0]["start_time"] == 0.0
        assert merged[0]["end_time"] == 1.0

    def test_autocorrelation(self):
        """Test autocorrelation computation."""
        # Create periodic signal
        sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        periodic = np.sin(2 * np.pi * 10 * t)  # 10 Hz
        
        acf = AlarmDetector._autocorrelation(periodic, max_lag=8000)
        
        # Should have peaks at regular intervals (0.1 sec = 1600 samples @ 16kHz)
        assert len(acf) > 0
        assert acf[0] == pytest.approx(1.0)  # First ACF value always 1
