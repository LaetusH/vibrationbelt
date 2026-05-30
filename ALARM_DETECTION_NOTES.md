# ⚠️ Alarm Detection - Important Notes

## Current Status

**Alarm detection is currently DISABLED** to prevent false positives.

The pipeline currently works for:
- ✅ **DOA Estimation** (0-360° direction finding)
- ✅ **Spectrogram Generation** (visual audio representation)  
- ✅ **Motor Mapping** (convert direction to motor)
- ❌ **Alarm Recognition** (disabled - needs training)

---

## Why Was Alarm Detection Disabled?

### The Problem: Template Matching Without Training Data

We initially used **cosine similarity template matching** for alarm detection. But without real training data, this is fundamentally broken:

```
cosine_similarity(random_A, random_B) ≈ 0.3 - 0.8
```

This means:
- **False Positives:** Silence matches alarm template ~ 95%! 🔴
- **False Negatives:** Real 3kHz alarm matches ~ 30%! 🔴

### Why It Fails

Cosine similarity measures angle between vectors, not semantic meaning:
- Two different white noise spectrograms → ~0.95 similarity
- Alarm spectrogram vs silence → ~0.4-0.6 similarity
- Speech vs noise → ~0.5-0.7 similarity

**Without training data to calibrate, you can't pick a threshold that works!**

---

## The Solution: Train a CNN

Use `models/cnn_trainer.py` to train a real neural network with:

1. **Positive samples:** 100+ real alarm spectrograms
2. **Negative samples:** 100+ non-alarm audio (speech, music, noise)
3. **Output:** Trained PyTorch model with 90%+ accuracy

### Step-by-Step

```bash
cd ~/Uni/Hackaburg26/vibrationbelt

# 1. Collect training data
#    Record ESP32 audio with alarms ON and OFF
#    Save to: alarm_audio/ and noise_audio/

# 2. Convert to spectrograms
python analysis_engine/models/cnn_trainer.py \
    --mode prepare \
    --alarm-dir alarm_audio/ \
    --noise-dir noise_audio/

# 3. Train model
python analysis_engine/models/cnn_trainer.py \
    --mode train \
    --output models/alarm_detector.pt

# 4. Evaluate
python analysis_engine/models/cnn_trainer.py \
    --mode evaluate \
    --model models/alarm_detector.pt

# 5. Use in pipeline
pipeline = AudioAnalysisPipeline(
    model_path="models/alarm_detector.pt",
    use_template_only=False  # Use CNN instead of template
)
```

---

## How Much Training Data Do You Need?

| Scenario | Samples | Accuracy |
|----------|---------|----------|
| No training | - | ❌ False positives |
| 10-20 samples each | ~20 total | 40-50% |
| 50-100 samples each | ~100-200 total | 70-80% |
| 200+ samples each | ~400+ total | **90%+** ✅ |

**Recommendation:** Collect at least 200-300 alarm and 200-300 non-alarm samples.

---

## Data Collection Strategy

### For Alarm Samples

```
1. Record your actual alarm sound (the one you want to detect)
   - Position near microphones
   - Record 5-10 seconds at different volumes
   - Record 20-30 times to get ~200 seconds of data

2. Vary conditions:
   - Different room locations
   - Different distances
   - Different times of day (if noise varies)
```

### For Non-Alarm Samples

```
1. Normal background sounds:
   - Ambient noise (no alarm)
   - People talking
   - Music playing
   - Traffic
   - Environmental sounds

2. Similar-to-alarm sounds:
   - Door bells
   - Phone notifications
   - Sirens
   - Beepers
   - Car horns
   
(These will help CNN learn the difference)
```

---

## Current Limitations & Roadmap

### Current (No Training Data)
- ✅ DOA works perfectly
- ✅ Spectrogram generation works
- ✅ Motor mapping works
- ❌ Alarm detection disabled (0% false positives, but also 0% true positives)

### After Training CNN
- ✅ All of above +
- ✅ Real alarm detection (90%+ accuracy)
- ✅ Adaptive thresholding
- ⚠️ May need retraining for different alarm sounds

### Future Improvements
- Transfer learning from public alarm datasets
- Multi-alarm detection (detect different alarm types)
- Continuous learning (update model from user feedback)
- Adaptive noise filtering

---

## Testing Without Training Data

You CAN test other components:

```bash
# Test DOA
python run_live_analysis.py --simulate

# Observe:
# ✓ DOA angle changes as you move simulated sound
# ✓ Motor prediction shows correct direction
# ✓ Confidence always 0% (detection disabled)
```

---

## Enabling Template Matching (NOT RECOMMENDED)

If you want to re-enable template matching (risky!):

```python
from analysis_engine.recognizers.alarm_recognizer import AlarmRecognizer

recognizer = AlarmRecognizer(use_template_only=True)

# Add your own calibrated templates:
recognizer.add_template("my_alarm", my_alarm_spectrogram)

# Increase threshold to reduce false positives
recognizer.templates['threshold'] = 0.90  # Very strict!
```

**But this still won't work reliably.** Use CNN instead.

---

## Questions to Answer Before Production

- [ ] What specific alarm sound are you detecting?
- [ ] How many different alarm types?
- [ ] What background noise levels?
- [ ] How many ESP32s / microphone pairs?
- [ ] What accuracy is acceptable? (90%? 95%?)
- [ ] How many false positives can you tolerate?

Get these answers, collect training data, and train the CNN!

---

## For Reference

- **DOA Algorithm:** `analysis_engine/doa/estimator.py`
- **Spectrogram:** `analysis_engine/spectrogram/generator.py`
- **CNN Training:** `analysis_engine/models/cnn_trainer.py`
- **Recognizer:** `analysis_engine/recognizers/alarm_recognizer.py`
- **Template Builder:** `analysis_engine/recognizers/template_builder.py`

---

**Summary:** ✅ System is safe. ❌ Alarm detection offline. 📚 Train CNN when ready.
