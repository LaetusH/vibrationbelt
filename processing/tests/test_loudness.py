"""Tests for LoudnessDetector."""

import pytest
import numpy as np
from audio_analyzer.loudness import LoudnessDetector


class TestLoudnessDetector:
    """Loudness detection unit tests."""

    def test_compute_rms_sine(self, sine_wave):
        """RMS of sine wave should be approximately 0.5 / sqrt(2)."""
        _, audio, _ = sine_wave
        
        rms = LoudnessDetector.compute_rms(audio)
        
        # For 0.5 amplitude sine: RMS = 0.5 / sqrt(2) ≈ 0.3536
        assert rms == pytest.approx(0.5 / np.sqrt(2), rel=0.02)

    def test_compute_peak_amplitude(self, sine_wave):
        """Peak of sine wave should be close to 0.5."""
        _, audio, sr = sine_wave
        
        peak = LoudnessDetector.compute_peak_amplitude(audio)
        
        assert peak == pytest.approx(0.5, abs=0.01)

    def test_rms_to_db(self):
        """RMS to dB conversion."""
        rms = 0.1
        db = LoudnessDetector.rms_to_db(rms, ref=1.0)
        
        # 0.1 → 20*log10(0.1) = -20 dB
        assert db == pytest.approx(-20, abs=0.1)

    def test_peak_to_db(self):
        """Peak to dB conversion."""
        peak = 0.5
        db = LoudnessDetector.peak_to_db(peak, ref=1.0)
        
        # 0.5 → 20*log10(0.5) ≈ -6 dB
        assert db == pytest.approx(-6.02, abs=0.1)

    def test_compute_lufs(self, sine_wave):
        """LUFS computation should return valid values."""
        _, audio, sr = sine_wave
        
        lufs, frame_lufs = LoudnessDetector.compute_lufs(audio, sr)
        
        assert isinstance(lufs, float)
        assert isinstance(frame_lufs, np.ndarray)
        assert len(frame_lufs) > 0
        assert np.all(np.isfinite(frame_lufs))
        # LUFS for 0.5 sine should be negative
        assert lufs < 0

    def test_lufs_frames_consistency(self, sine_wave):
        """Frame LUFS should be roughly consistent for steady sine."""
        _, audio, sr = sine_wave
        
        _, frame_lufs = LoudnessDetector.compute_lufs(audio, sr)
        
        # Sine is steady, so LUFS should have low variance
        std = np.std(frame_lufs)
        assert std < 5  # dB, reasonable for steady tone

    def test_detect_loudness_peaks(self, sine_wave):
        """Detect loudness peaks in sine wave."""
        _, audio, sr = sine_wave
        
        peaks = LoudnessDetector.detect_loudness_peaks(audio, sr, threshold_db=-10)
        
        assert isinstance(peaks, np.ndarray)
        assert peaks.dtype == bool
        assert len(peaks) == len(audio)
        # Should detect at least some peaks in loud signal
        assert np.sum(peaks) > 0

    def test_detect_loudness_peaks_returns_valid_array(self, white_noise):
        """Peak detection signature test — returns bool array."""
        _, audio, sr = white_noise
        
        peaks = LoudnessDetector.detect_loudness_peaks(audio, sr, threshold_db=-3)
        
        # Should return valid boolean array of same length
        assert isinstance(peaks, np.ndarray)
        assert peaks.dtype == bool
        assert len(peaks) == len(audio)

    def test_segment_by_loudness(self, sine_wave):
        """Segment audio into loud/quiet sections."""
        _, audio, sr = sine_wave
        
        segments = LoudnessDetector.segment_by_loudness(audio, sr)
        
        assert isinstance(segments, list)
        assert len(segments) > 0
        
        for seg in segments:
            assert "start" in seg
            assert "end" in seg
            assert "is_loud" in seg
            assert seg["start"] < seg["end"]

    def test_segment_continuous_loud_sine(self, sine_wave):
        """Steady sine should produce mostly one loud segment."""
        _, audio, sr = sine_wave
        
        segments = LoudnessDetector.segment_by_loudness(audio, sr, threshold_db=-30)
        
        # Count loud segments
        loud_segments = [s for s in segments if s["is_loud"]]
        
        # Should mostly be loud (one continuous segment)
        assert len(loud_segments) >= 1

    def test_get_loudness_statistics(self, sine_wave):
        """Get comprehensive loudness statistics."""
        _, audio, sr = sine_wave
        
        stats = LoudnessDetector.get_loudness_statistics(audio, sr)
        
        assert "rms_linear" in stats
        assert "rms_db" in stats
        assert "peak_linear" in stats
        assert "peak_db" in stats
        assert "lufs" in stats
        assert "lufs_mean" in stats
        assert "lufs_std" in stats
        assert "lufs_max" in stats
        assert "lufs_min" in stats
        
        # All values should be finite
        assert all(np.isfinite(v) for v in stats.values())

    def test_loudness_statistics_comparison(self, sine_wave, white_noise):
        """Sine wave should be louder than white noise."""
        _, sine_audio, sr = sine_wave
        _, noise_audio, _ = white_noise
        
        sine_stats = LoudnessDetector.get_loudness_statistics(sine_audio, sr)
        noise_stats = LoudnessDetector.get_loudness_statistics(noise_audio, sr)
        
        # Sine (0.5 amp) should be louder than noise (0.1 amp)
        assert sine_stats["peak_linear"] > noise_stats["peak_linear"]
        assert sine_stats["rms_linear"] > noise_stats["rms_linear"]

    def test_lufs_with_different_block_sizes(self, sine_wave):
        """Different block sizes should give similar (not identical) results."""
        _, audio, sr = sine_wave
        
        lufs1, _ = LoudnessDetector.compute_lufs(audio, sr, block_size=1024)
        lufs2, _ = LoudnessDetector.compute_lufs(audio, sr, block_size=4096)
        
        # Should be similar but not identical
        assert abs(lufs1 - lufs2) < 5  # Within reasonable margin
