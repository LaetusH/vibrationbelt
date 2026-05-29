# Anomaly Detection Guide

## Overview

Anomaly Detection identifies **unusual acoustic events** (screams, crashes, breaking glass, etc.) by comparing against an ambient baseline.

**Key Principle:** Sounds that are **much louder and spectrally different** from the background = anomaly.

---

## How It Works

### 1. **Baseline Learning** (First ~2-10 seconds)
```
Ambient background noise is recorded and analyzed:
- RMS level stored
- Frequency spectrum learned
- This becomes the "normal" reference
```

### 2. **Real-Time Analysis**
For each incoming audio chunk:
1. ✅ Check SNR (Signal-to-Noise Ratio) vs baseline
2. ✅ Analyze frequency content (where is the energy?)
3. ✅ Check for transient spikes (sudden onset)
4. ✅ Match against anomaly patterns

### 3. **Detection Types**

| Anomaly | Pattern | Example |
|---------|---------|---------|
| **SCREAM_SHOUT** | High freq (>2kHz) + high amplitude | "AAHHHHH!" |
| **CRASH_BREAK** | Broad spectrum + transient decay | Breaking glass, door slam |
| **SHARP_NOISE** | Extreme crest factor (peak >> RMS) | Gunshot-like pop |
| **ABNORMAL_SPIKE** | General spike above baseline | Any sudden loud sound |

---

## Quick Start

### Option 1: Live Detection

```bash
cd ~/Uni/Hackaburg26/vibrationbelt/processing

# Detect anomalies in real-time (10 seconds)
python examples/detect_screams.py detect --duration 10
```

**What happens:**
1. Records first 2 sec (baseline/ambient)
2. Records next 8 sec (monitoring)
3. Reports any anomalies detected

### Option 2: Calibration Mode

Find the best thresholds for your environment:

```bash
python examples/detect_screams.py calibrate
```

**Interactive steps:**
1. Learn your background (5 sec silence)
2. Make a test sound (scream, crash, etc.)
3. Gets suggestions for optimal `min_confidence`

### Option 3: In Code

```python
from audio_analyzer.pipeline import AudioAnalysisPipeline

pipeline = AudioAnalysisPipeline()

# Learn baseline from quiet ambient (first 2 sec)
baseline_audio = audio[:2*sr]

# Detect anomalies in the rest
result = pipeline.detect_anomalies(
    audio[2*sr:],  # Test audio
    sr=sr,
    baseline_audio=baseline_audio,
    min_snr_db=6.0,          # 6 dB above ambient (minimum)
    min_confidence=0.5,      # 50% confidence threshold
    sensitivity=0.6,         # 0.1-1.0 multiplier
)

print(result["summary"])
print(result["anomalies"])
```

---

## Understanding Thresholds

### SNR Threshold (min_snr_db)

```
SNR = 20 * log10(signal_RMS / baseline_RMS)

Examples:
- 6 dB  = signal is 2x amplitude of background (good for quiet screams)
- 10 dB = signal is 3x amplitude of background
- 20 dB = signal is 10x amplitude of background (very loud)
```

**Recommendation:**
- Use **6-10 dB** for normal office/home detection
- Use **20 dB** for noisy environments (traffic, machinery)

### Confidence Threshold (min_confidence)

```
Final confidence = 50% Pattern Match + 50% SNR Verification
```

| Value | Meaning |
|-------|---------|
| 0.3 | Very sensitive (many false positives) |
| **0.5** | Balanced (recommended start) |
| 0.7 | Strict (only clear anomalies) |
| 0.9 | Very strict (misses weak signals) |

### Sensitivity Multiplier (sensitivity)

```
sensitivity_param ranges 0.1 - 1.0
- Lower (0.1) = stricter gates, fewer detections
- Higher (0.9) = relaxed gates, more detections
```

---

## Tuning for Your Environment

### Problem: Too Many False Positives

Your anomaly detector keeps triggering on background noise.

**Solution:**
```python
# Increase confidence threshold
result = pipeline.detect_anomalies(
    audio, sr,
    baseline_audio=baseline,
    min_confidence=0.7,      # Was 0.5, now stricter
    sensitivity=0.4,         # Lower sensitivity
)
```

### Problem: Misses Real Anomalies

The detector should catch screams but doesn't.

**Solution:**
```python
# Lower thresholds
result = pipeline.detect_anomalies(
    audio, sr,
    baseline_audio=baseline,
    min_snr_db=3.0,          # Was 6, now more sensitive
    min_confidence=0.3,      # Was 0.5, now relaxed
    sensitivity=0.8,         # Higher sensitivity
)
```

### Problem: Baseline Not Learned Properly

If you have **loud background** (traffic, music):
```python
# Use explicit quiet baseline
quiet_baseline = audio[:5*sr]  # First 5 sec (must be quiet!)
result = pipeline.detect_anomalies(
    audio[5*sr:],
    sr=sr,
    baseline_audio=quiet_baseline,  # Explicitly set
)
```

---

## Real-World Examples

### Scenario 1: Home Office

```python
# Typical home environment
pipeline.detect_anomalies(
    audio, sr,
    min_snr_db=8.0,          # AC humming = ~5dB
    min_confidence=0.5,      # Balanced
    sensitivity=0.6,
)
```

### Scenario 2: Loud Warehouse

```python
# Noisy background (machinery, traffic)
pipeline.detect_anomalies(
    audio, sr,
    min_snr_db=15.0,         # Need much louder
    min_confidence=0.7,      # Stricter pattern match
    sensitivity=0.3,         # Lower sensitivity
)
```

### Scenario 3: Car/Taxi

```python
# Engine noise + traffic
pipeline.detect_anomalies(
    audio, sr,
    min_snr_db=12.0,
    min_confidence=0.6,
    sensitivity=0.5,
)
```

---

## Advanced: Pattern-Specific Tuning

### Optimize for Screams

```python
# Focus on high-freq detection
# Screams have spectral centroid > 2000 Hz

result = pipeline.detect_anomalies(audio, sr)

# Check if SCREAM_SHOUT is in detected anomalies
screams = [a for a in result["anomalies"] if a["type"].value == "scream_shout"]
```

### Optimize for Crashes

```python
# Crashes have high zero-crossing rate
# Broad spectrum noise + quick decay

# Nothing to tune directly, but crashes detected as:
crashes = [a for a in result["anomalies"] if a["type"].value == "crash_break"]
```

---

## Troubleshooting

### "Anomalies Detected: None" on Clear Sound

1. **Check baseline RMS:**
   ```python
   print(pipeline.anomaly_detector.baseline_rms)  # Should be ~0.01-0.05
   ```
   If > 0.1, your "baseline" wasn't quiet!

2. **Check SNR:**
   ```python
   signal_rms = np.sqrt(np.mean(audio ** 2))
   snr_db = 20 * np.log10(signal_rms / baseline_rms)
   print(f"SNR: {snr_db} dB")  # Should be > min_snr_db
   ```

3. **Lower thresholds:**
   ```python
   result = pipeline.detect_anomalies(
       audio, sr,
       min_snr_db=3.0,      # Try lower
       min_confidence=0.2,  # Try lower
   )
   ```

### "Too Many False Positives"

1. **Check that baseline is truly quiet:**
   ```python
   baseline_rms = np.sqrt(np.mean(baseline_audio ** 2))
   if baseline_rms > 0.05:
       print("WARNING: Baseline is loud, learn from quieter audio")
   ```

2. **Raise confidence threshold:**
   ```python
   min_confidence=0.7  # Stricter
   ```

3. **Increase SNR requirement:**
   ```python
   min_snr_db=12.0  # Need louder signal
   ```

---

## API Reference

### Pipeline.detect_anomalies()

```python
result = pipeline.detect_anomalies(
    audio: np.ndarray,              # Audio to analyze
    sr: int,                        # Sample rate
    baseline_audio: Optional[np.ndarray] = None,
    baseline_sr: Optional[int] = None,
    min_snr_db: float = 6.0,        # Min SNR threshold
    min_confidence: float = 0.5,    # Min confidence (0-1)
    sensitivity: float = 0.5,       # Sensitivity multiplier
)

Returns:
{
    "audio": audio_array,
    "sr": sample_rate,
    "duration_sec": duration,
    "anomalies": [
        {
            "type": AnomalyType,
            "confidence": 0.79,
            "snr_db": 29.3,
            "score": 0.65,
            "rms": 0.291,
            "baseline_rms": 0.01,
        },
        ...
    ],
    "summary": "Anomaly Detection Summary\n...",
    "baseline_rms": 0.01,
}
```

### AnomalyDetector.learn_baseline()

```python
baseline_info = detector.learn_baseline(quiet_audio)

Returns:
{
    "baseline_rms": 0.0123,
    "baseline_spectrum_bins": 8049,
    "calibrated": True,
}
```

---

## Performance

- **Latency:** ~100ms for 1 sec of audio (fast!)
- **CPU:** Minimal (spectral analysis + correlation)
- **Memory:** ~10 MB per minute of audio

---

## Summary

1. **Learn baseline** from quiet environment (first 2-10 sec)
2. **Set thresholds** based on your use case:
   - Home: `min_snr_db=8, min_confidence=0.5`
   - Loud: `min_snr_db=15, min_confidence=0.7`
3. **Detect anomalies** that are 6-20 dB above ambient
4. **Calibrate** using `detect_screams.py calibrate` for optimal settings

---

## Related

- `audio_analyzer/anomaly_detector.py` — Core detector implementation
- `examples/detect_screams.py` — Interactive tools
- `DETECTOR_TUNING.md` — Alarm detection guide (different module)
