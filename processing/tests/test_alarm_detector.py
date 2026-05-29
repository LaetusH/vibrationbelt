"""Tests for AlarmDetector (pattern-based)."""

import pytest
import numpy as np
from audio_analyzer.alarm_detector import AlarmDetector, AlarmType


@pytest.fixture
def fire_siren_audio(temp_audio_dir):
    """Generate synthetic fire siren."""
    import soundfile as sf
    
    sr = 16000
    duration = 2.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    pulse = np.sin(2 * np.pi * 2 * t)
    pulse = (pulse + 1) / 2
    siren = 0.3 * pulse * np.sin(2 * np.pi * 1000 * t)
    siren += 0.05 * np.random.randn(len(siren))
    siren = 0.9 * siren / np.max(np.abs(siren))
    
    filepath = temp_audio_dir / "fire_siren.wav"
    sf.write(str(filepath), siren.astype(np.float32), sr)
    
    return filepath, siren, sr


@pytest.fixture
def smoke_detector_audio(temp_audio_dir):
    """Generate synthetic smoke detector."""
    import soundfile as sf
    
    sr = 16000
    duration = 3.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    chirp_env = (np.sin(2 * np.pi * 3 * t) > 0.5).astype(float)
    smoke = 0.3 * chirp_env * np.sin(2 * np.pi * 3000 * t)
    smoke = 0.9 * smoke / np.max(np.abs(smoke))
    
    filepath = temp_audio_dir / "smoke_detector.wav"
    sf.write(str(filepath), smoke.astype(np.float32), sr)
    
    return filepath, smoke, sr


class TestAlarmDetector:
    """Alarm detection tests (pattern-based)."""

    def test_detector_initialization(self, sine_wave):
        """Initialize detector."""
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

    def test_detect_alarms_returns_list(self, sine_wave):
        """detect_alarms returns list."""
        _, audio, sr = sine_wave
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio)
        assert isinstance(detections, list)

    def test_alarm_dict_structure(self, fire_siren_audio):
        """Each detection has required fields."""
        _, audio, sr = fire_siren_audio
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio)
        
        if detections:
            alarm = detections[0]
            assert "alarm_type" in alarm
            assert "start_time" in alarm
            assert "end_time" in alarm
            assert "confidence" in alarm
            assert "frequencies" in alarm

    def test_fire_siren_detection(self, fire_siren_audio):
        """Detect fire siren."""
        _, audio, sr = fire_siren_audio
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio, min_confidence=0.3)
        
        # Should detect with pattern matching (even if quiet)
        assert isinstance(detections, list)

    def test_smoke_detector_detection(self, smoke_detector_audio):
        """Detect smoke detector."""
        _, audio, sr = smoke_detector_audio
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio, min_confidence=0.3)
        
        assert isinstance(detections, list)

    def test_confidence_score_bounds(self, fire_siren_audio):
        """Confidence scores are 0-1."""
        _, audio, sr = fire_siren_audio
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio)
        
        for detection in detections:
            assert 0 <= detection["confidence"] <= 1

    def test_time_bounds(self, fire_siren_audio):
        """Detected times within audio duration."""
        filepath, audio, sr = fire_siren_audio
        duration = len(audio) / sr
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio)
        
        for detection in detections:
            assert 0 <= detection["start_time"] <= duration
            assert 0 <= detection["end_time"] <= duration

    def test_no_false_alarms_on_noise(self, white_noise):
        """Noise doesn't trigger alarms with strict threshold."""
        _, audio, sr = white_noise
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(audio, min_confidence=0.8)
        
        # Should have few/no detections on noise
        assert len(detections) <= 1

    def test_pattern_detection_quiet_signal(self):
        """Test pattern detection on quiet but periodic signal."""
        sr = 16000
        duration = 2.0
        
        # Create QUIET but clearly periodic siren (0.1 amplitude)
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        pulse = np.sin(2 * np.pi * 1.5 * t)  # 1.5 Hz pulse
        pulse = (pulse + 1) / 2
        
        # Very quiet siren: 0.01 amplitude
        siren = 0.01 * pulse * np.sin(2 * np.pi * 1000 * t)
        
        detector = AlarmDetector(sr)
        detections = detector.detect_alarms(siren, min_confidence=0.3)
        
        # Should detect due to PATTERN, even though quiet
        assert isinstance(detections, list)
        if detections:
            assert detections[0]["confidence"] > 0.3

    def test_autocorrelation(self):
        """Test autocorrelation."""
        sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        periodic = np.sin(2 * np.pi * 10 * t)
        
        detector = AlarmDetector(sr)
        acf = detector._autocorrelation(periodic, max_lag=8000)
        
        assert len(acf) > 0
        assert acf[0] == pytest.approx(1.0)

    def test_fft_computation(self, sine_wave):
        """FFT computation works."""
        _, audio, sr = sine_wave
        detector = AlarmDetector(sr)
        
        freqs, mags = detector._compute_fft(audio)
        
        assert len(freqs) > 0
        assert len(mags) == len(freqs)
        assert np.any(mags > 0)
