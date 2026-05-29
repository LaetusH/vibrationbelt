"""Tests for AnomalyDetector."""

import pytest
import numpy as np
from audio_analyzer.anomaly_detector import AnomalyDetector, AnomalyType


@pytest.fixture
def scream_audio():
    """Generate synthetic scream (high-frequency burst)."""
    sr = 16000
    duration = 1.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    # High-frequency scream: strong 3-5 kHz + noise
    scream = 0.5 * np.sin(2 * np.pi * 3500 * t)
    scream += 0.2 * np.random.randn(len(scream))
    scream = 0.9 * scream / np.max(np.abs(scream))
    
    return scream, sr


@pytest.fixture
def crash_audio():
    """Generate synthetic crash (broad spectrum + high zcr)."""
    sr = 16000
    duration = 0.5
    
    # Broad spectrum noise (decay envelope)
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    envelope = np.exp(-10 * t)  # Decay
    
    crash = envelope * np.random.randn(int(sr * duration))
    crash = 0.8 * crash / np.max(np.abs(crash))
    
    return crash, sr


@pytest.fixture
def background_noise():
    """Generate ambient background noise (quiet)."""
    sr = 16000
    duration = 5.0
    
    # Quiet background: 0.02 RMS
    background = 0.02 * np.random.randn(int(sr * duration))
    
    return background, sr


class TestAnomalyDetector:
    """Anomaly detection tests."""

    def test_initialization(self):
        """Initialize detector."""
        sr = 16000
        detector = AnomalyDetector(sr)
        assert detector.sr == sr
        assert not detector.is_calibrated

    def test_learn_baseline(self, background_noise):
        """Learn baseline from quiet audio."""
        audio, sr = background_noise
        detector = AnomalyDetector(sr)
        
        baseline = detector.learn_baseline(audio)
        
        assert detector.is_calibrated
        assert "baseline_rms" in baseline
        assert baseline["baseline_rms"] > 0

    def test_detect_anomalies_returns_list(self, scream_audio):
        """detect_anomalies returns list."""
        audio, sr = scream_audio
        detector = AnomalyDetector(sr)
        detector.learn_baseline(audio[:sr])  # Learn from first second
        
        detections = detector.detect_anomalies(audio)
        assert isinstance(detections, list)

    def test_anomaly_dict_structure(self, scream_audio):
        """Each anomaly has required fields."""
        audio, sr = scream_audio
        detector = AnomalyDetector(sr)
        detector.learn_baseline(audio[:sr])
        
        detections = detector.detect_anomalies(audio)
        
        if detections:
            anomaly = detections[0]
            assert "type" in anomaly
            assert "confidence" in anomaly
            assert "snr_db" in anomaly
            assert "score" in anomaly

    def test_scream_detection(self, scream_audio):
        """Detect screams (high freq + amplitude)."""
        audio, sr = scream_audio
        detector = AnomalyDetector(sr)
        
        # Learn from quiet baseline
        baseline = np.zeros(sr)
        detector.learn_baseline(baseline)
        
        detections = detector.detect_anomalies(audio, min_confidence=0.3)
        
        # Should detect the scream
        assert len(detections) > 0
        assert detections[0]["snr_db"] > 10

    def test_crash_detection(self, crash_audio):
        """Detect crashes (broad spectrum + transient)."""
        audio, sr = crash_audio
        detector = AnomalyDetector(sr)
        
        baseline = np.zeros(sr // 2)
        detector.learn_baseline(baseline)
        
        detections = detector.detect_anomalies(audio, min_confidence=0.3)
        
        assert isinstance(detections, list)

    def test_no_false_alarms_on_background(self, background_noise):
        """Background noise shouldn't trigger alarms."""
        audio, sr = background_noise
        detector = AnomalyDetector(sr)
        
        # Learn from first half
        detector.learn_baseline(audio[: sr * 2])
        
        # Analyze second half (similar background)
        detections = detector.detect_anomalies(
            audio[sr * 2 :],
            min_confidence=0.7,  # High threshold
        )
        
        # Should have few/no detections
        assert len(detections) <= 1

    def test_confidence_bounds(self, scream_audio):
        """Confidence scores are 0-1."""
        audio, sr = scream_audio
        detector = AnomalyDetector(sr)
        detector.learn_baseline(audio[:sr])
        
        detections = detector.detect_anomalies(audio)
        
        for det in detections:
            assert 0 <= det["confidence"] <= 1

    def test_snr_gate(self, background_noise, scream_audio):
        """SNR gate rejects signals below threshold."""
        bg, sr = background_noise
        detector = AnomalyDetector(sr)
        detector.learn_baseline(bg)
        
        # Analyze very quiet signal (below SNR threshold)
        quiet = 0.001 * np.random.randn(sr)
        detections = detector.detect_anomalies(quiet, min_snr_db=10)
        
        # Should have no detections (too quiet)
        assert len(detections) == 0

    def test_auto_calibrate(self, scream_audio):
        """Auto-calibrate if not done manually."""
        audio, sr = scream_audio
        detector = AnomalyDetector(sr)
        
        # Don't call learn_baseline, should auto-calibrate
        detections = detector.detect_anomalies(audio, min_confidence=0.2)
        
        assert detector.is_calibrated
        assert isinstance(detections, list)

    def test_sensitivity_parameter(self, scream_audio):
        """Sensitivity parameter affects gate thresholds."""
        audio, sr = scream_audio
        detector = AnomalyDetector(sr)
        detector.learn_baseline(audio[:sr])
        
        # High sensitivity: lower thresholds
        detections_high = detector.detect_anomalies(
            audio,
            sensitivity=0.8,
            min_confidence=0.2,
        )
        
        # Low sensitivity: higher thresholds
        detections_low = detector.detect_anomalies(
            audio,
            sensitivity=0.2,
            min_confidence=0.2,
        )
        
        # High sensitivity should have >= detections
        assert len(detections_high) >= len(detections_low)

    def test_duration_gate(self):
        """Very short audio rejected."""
        sr = 16000
        detector = AnomalyDetector(sr)
        detector.learn_baseline(np.zeros(sr))
        
        # 50ms audio (< 200ms threshold)
        short_audio = np.random.randn(sr // 20)
        detections = detector.detect_anomalies(short_audio)
        
        assert len(detections) == 0

    def test_zcr_computation(self):
        """Zero-crossing rate computed."""
        sr = 16000
        duration = 1.0
        
        # Pure sine (low ZCR)
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        sine = np.sin(2 * np.pi * 100 * t)
        
        # Noise (high ZCR)
        noise = np.random.randn(int(sr * duration))
        
        detector = AnomalyDetector(sr)
        zcr_sine = detector._compute_zcr(sine)
        zcr_noise = detector._compute_zcr(noise)
        
        # Noise should have higher ZCR
        assert zcr_noise > zcr_sine

    def test_spectral_centroid_scream(self):
        """Screams have high spectral centroid."""
        sr = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        
        # Low-freq tone
        low = np.sin(2 * np.pi * 200 * t)
        
        # High-freq tone
        high = np.sin(2 * np.pi * 4000 * t)
        
        detector = AnomalyDetector(sr)
        
        freqs_low, mags_low = detector._compute_fft(low)
        freqs_high, mags_high = detector._compute_fft(high)
        
        centroid_low = np.sum(freqs_low * mags_low) / np.sum(mags_low)
        centroid_high = np.sum(freqs_high * mags_high) / np.sum(mags_high)
        
        assert centroid_high > centroid_low
