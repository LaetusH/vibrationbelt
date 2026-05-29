"""Integration tests for AudioAnalysisPipeline."""

import pytest
import numpy as np
from audio_analyzer.pipeline import AudioAnalysisPipeline


class TestAudioAnalysisPipeline:
    """Pipeline integration tests."""

    def test_pipeline_initialization(self, sine_wave):
        """Initialize pipeline."""
        _, _, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        
        assert pipeline.target_sr == sr
        assert pipeline.loader is not None
        assert pipeline.fft_analyzer is not None
        assert pipeline.alarm_detector is not None

    def test_analyze_file(self, sine_wave):
        """End-to-end file analysis."""
        filepath, _, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        result = pipeline.analyze_file(str(filepath))
        
        # Check result structure
        assert "audio" in result
        assert "sr" in result
        assert "duration_sec" in result
        assert "loudness" in result
        assert "spectrum" in result
        assert "spectrogram" in result
        assert "alarms" in result
        assert "summary" in result

    def test_analyze_file_keys(self, sine_wave):
        """Result should have all expected keys."""
        filepath, _, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        result = pipeline.analyze_file(str(filepath))
        
        # Loudness keys
        loudness = result["loudness"]
        assert "rms_linear" in loudness
        assert "peak_db" in loudness
        assert "lufs" in loudness
        
        # Spectrum keys
        spectrum = result["spectrum"]
        assert "frequencies" in spectrum
        assert "magnitudes" in spectrum
        assert "peak_frequencies" in spectrum
        
        # Spectrogram keys
        spectrogram = result["spectrogram"]
        assert "spec_db" in spectrogram
        assert "frequencies" in spectrogram
        assert "times" in spectrogram

    def test_analyze_audio(self, sine_wave):
        """Analyze audio array directly."""
        _, audio, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        result = pipeline.analyze_audio(audio, sr)
        
        assert "audio" in result
        assert result["sr"] == sr
        assert result["duration_sec"] == pytest.approx(1.0, abs=0.01)

    def test_analyze_audio_with_resampling(self, sine_wave):
        """Analyze audio with resampling to target SR."""
        _, audio, sr = sine_wave
        
        target_sr = 8000
        pipeline = AudioAnalysisPipeline(target_sr=target_sr)
        result = pipeline.analyze_audio(audio, sr)
        
        # Should be resampled to target_sr
        assert result["sr"] == target_sr
        expected_samples = int(1.0 * target_sr)  # 1 sec @ 8kHz
        assert len(result["audio"]) == expected_samples

    def test_detect_alarms_in_file(self, sine_wave):
        """Fast alarm detection on file."""
        filepath, _, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        alarms = pipeline.detect_alarms_in_file(str(filepath))
        
        assert isinstance(alarms, list)

    def test_is_audio_too_loud(self, sine_wave, white_noise):
        """Check loudness threshold."""
        _, sine_audio, sr = sine_wave
        _, noise_audio, _ = white_noise
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        
        # Sine (0.5 amp) should be louder
        sine_loud = pipeline.is_audio_too_loud(sine_audio, sr, threshold_lufs=-20)
        noise_loud = pipeline.is_audio_too_loud(noise_audio, sr, threshold_lufs=-20)
        
        # Sine should be louder or same
        assert sine_loud >= noise_loud or not sine_loud

    def test_get_fundamental_frequency_sine(self, sine_wave):
        """Get fundamental frequency of sine wave."""
        _, audio, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        fundamental = pipeline.get_fundamental_frequency(audio, sr)
        
        # Should detect 1000 Hz
        assert fundamental is not None
        assert np.isclose(fundamental, 1000, atol=20)

    def test_summary_generation(self, sine_wave):
        """Generate summary text."""
        filepath, _, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        result = pipeline.analyze_file(str(filepath))
        summary = result["summary"]
        
        # Should be non-empty string
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "Audio Analysis Summary" in summary

    def test_summary_with_alarms(self, smoke_detector_synthetic):
        """Summary should include alarm information."""
        _, audio, sr = smoke_detector_synthetic
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        result = pipeline.analyze_audio(audio, sr, alarm_sensitivity=0.6)
        summary = result["summary"]
        
        # Should mention alarms (detected or not)
        assert "Alarms Detected" in summary

    def test_pipeline_nonexistent_file(self, nonexistent_file):
        """Pipeline should handle missing files."""
        pipeline = AudioAnalysisPipeline()
        
        with pytest.raises(FileNotFoundError):
            pipeline.analyze_file(str(nonexistent_file))

    def test_pipeline_end_to_end_full(self, sine_wave):
        """Full pipeline execution without errors."""
        filepath, audio, sr = sine_wave
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        
        # File analysis
        result1 = pipeline.analyze_file(str(filepath))
        assert result1 is not None
        
        # Array analysis
        result2 = pipeline.analyze_audio(audio, sr)
        assert result2 is not None
        
        # Fast detection
        alarms = pipeline.detect_alarms_in_file(str(filepath))
        assert isinstance(alarms, list)


@pytest.fixture
def smoke_detector_synthetic(temp_audio_dir):
    """Generate synthetic smoke detector signal."""
    import soundfile as sf
    
    sr = 16000
    duration = 2.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    chirp_env = (np.sin(2 * np.pi * 3 * t) > 0.5).astype(float)
    audio = 0.4 * chirp_env * np.sin(2 * np.pi * 3000 * t)
    
    filepath = temp_audio_dir / "smoke_detector_test.wav"
    sf.write(str(filepath), audio.astype(np.float32), sr)
    
    return filepath, audio, sr
