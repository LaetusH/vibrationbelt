# Alarm Detector Tuning Guide

## Problem: Leise Sirenen nicht erkannt?

The detector is now **pattern-based**, not loudness-based. This means it can detect:
- ✅ Loud sirens
- ✅ Quiet sirens (if they have clear periodic pattern)
- ✅ YouTube/phone playback (often quiet but clear pattern)
- ❌ Pure noise/speech (no recognizable pattern)

## Solution: Calibrate for Your Setup

### Step 1: Record Your Alarm

```bash
cd processing

# This will record 5 seconds and test at different thresholds
python examples/calibrate_detector.py
```

**What to do:**
1. Script says "Recording 5s (PLAY YOUR ALARM NOW)..."
2. Play your YouTube fire siren video OR ring your actual alarm
3. Script analyzes and recommends a threshold

### Step 2: Use the Recommended Threshold

Example output:
```
Threshold: 0.3
  ✗ No detection
Threshold: 0.4
  ✓ fire_siren
    Confidence: 67%

RECOMMENDATION: Use: alarm_min_confidence=0.4
```

Then use that in your code:

```python
from audio_analyzer.pipeline import AudioAnalysisPipeline

pipeline = AudioAnalysisPipeline()
result = pipeline.analyze_audio(
    audio, sr,
    alarm_min_confidence=0.4  # ← Use recommended value
)
```

Or in live monitoring:

```bash
python examples/live_monitor.py monitor
```

And modify the confidence check in `live_monitor.py`:
```python
alarms = pipeline.alarm_detector.detect_alarms(
    audio,
    sensitivity=0.6,
    min_confidence=0.4  # ← Your calibrated value
)
```

---

## Understanding the Pattern Score

The detector checks THREE things:

### 1️⃣ **Frequency Content** (40% of score)
- Does audio have energy in alarm frequency ranges?
- Fire siren: 800-1200 Hz
- Smoke detector: 2500-3500 Hz
- Threshold: 15% of maximum FFT peak

### 2️⃣ **Periodicity Pattern** (40% of score)
- Does audio have periodic pulsing/chirping?
- Autocorrelation detects repeating patterns
- Fire siren: 0.3-3 Hz pulsing
- Smoke detector: 1.5-6 Hz chirping
- Threshold: ACF peak > 0.25

### 3️⃣ **Amplitude** (20% of score)
- Bonus for loud signals
- NOT required (quiet OK if pattern is good)
- Used: loudness relative to 0.05 RMS (reference)

---

## Troubleshooting

### "No detection even with calibration"

**Possible causes:**

1. **Alarm too noisy/distorted**
   - YouTube videos compressed over speakers?
   - Try high-quality alarm source

2. **No clear frequency content**
   - Test: `python examples/live_monitor.py record 10`
   - Analyze the saved WAV file with Audacity
   - Check if you see clear peaks at 800-1200 Hz (siren) or 2500-3500 Hz (smoke detector)

3. **No periodic pattern**
   - Steady tone (no pulsing)? = Won't detect
   - Pattern-based detector needs pulsing/chirping
   - Fire sirens usually pulse: ✓ Detectable
   - Car alarm steady tone: ✗ Harder to detect

### "Too many false positives"

Increase `min_confidence`:
```python
detections = detector.detect_alarms(audio, min_confidence=0.7)  # Stricter
```

### "Detects but very low confidence"

Check what's missing:

```python
# From calibrate_detector.py output:
# "Freq match: 0.8"        ← Frequency is good ✓
# "Periodicity: 0.5"       ← Periodicity weak ✗
# "Pattern strength: 0.4"  ← Combined is OK

# Solution: Look for periodic patterns, not steady tones
```

---

## Real-World Patterns

### ✅ **Detectable Alarms:**

| Alarm | Pattern | Frequency | Example |
|-------|---------|-----------|---------|
| Fire Siren | Pulsing 1-2 Hz | 800-1200 Hz | "Woop woop woop" (classic siren) |
| Smoke Detector | Chirping 3-5 Hz | 2.5-3.5 kHz | "Beep beep beep" (rapid chirps) |
| Car Alarm | Pulsing/beeping | 800-1500 Hz | "Wee woo wee woo" (pulsing alarm) |
| Warning Tone | Pulsing | 500-1500 Hz | Alarm clock pulsing |

### ❌ **Not Detectable:**

| Sound | Why |
|-------|-----|
| Speech | No specific frequency, not periodic |
| Music | No recognizable alarm pattern |
| White noise | No frequency concentration |
| Steady hum | No periodicity |

---

## Advanced: Custom Thresholds

Edit `audio_analyzer/alarm_detector.py` in `ALARM_SIGNATURES`:

```python
AlarmType.SIREN_FIRE: {
    "freq_ranges": [(800, 1200)],
    "periodicity_hz": (0.3, 3.0),  # ← Adjust pulsing range
    "min_pattern_strength": 0.4,    # ← Lower = more sensitive (0.2-0.5)
},
```

### When to adjust:

- **Lower `min_pattern_strength`** (0.3 → 0.2): More sensitive, more false positives
- **Raise `periodicity_hz` upper bound** (3 → 5 Hz): Detect faster chirping
- **Lower `min_duration_ms`** (300 → 150 ms): Detect shorter bursts

---

## Summary

1. **Run calibration** on your actual alarm
2. **Note the recommended threshold**
3. **Use it in your code**
4. **If still no detection:** Check if your alarm has clear periodic pattern (pulsing/chirping)

The detector works best when:
- ✓ Clear frequency peaks in alarm range
- ✓ Recognizable pulsing or chirping pattern
- ✓ At least 300ms duration

It **doesn't** care about loudness anymore — just pattern!
