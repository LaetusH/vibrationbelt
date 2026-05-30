# 🚨 Siren Detector - YAMNet Pipeline

Emergency vehicle siren detection using Google's YAMNet model.

Based on: [Kaggle Notebook by Mustafa Gulhan](https://www.kaggle.com/code/mustafagulhan/emergency-vehicle-siren-detection-using-yamnet)

## Output

**Binary Classification:**
- 🚨 **ALARM** — Emergency vehicle detected (siren, horn, police, ambulance, fire engine)
- 🔇 **QUIET** — Non-alarm sounds (music, speech, ambient, etc.)

---

## 🚀 Quick Start

### Installation

```bash
pip install tensorflow tensorflow-hub librosa sounddevice matplotlib seaborn pandas
```

### Single Test (3 seconds microphone)

```bash
python3 siren_detector.py
```

**Output:**
```
================================================================================
🚨 EMERGENCY VEHICLE SIREN DETECTION - YAMNet Pipeline
================================================================================

📥 Loading YAMNet model...
   ✅ Model loaded! Total classes: 521

🎤 Recording from microphone...
   ✅ Recorded 3s audio

🔍 Running YAMNet inference...

================================================================================
📊 RESULTS
================================================================================

🎯 Classification: ALARM
   Confidence: 92.34%
   Reason: Top class "Siren" is alarm-like

📈 Top 5 YAMNet Predictions:
   1. Siren                                   0.923
   2. Emergency vehicle                       0.891
   3. Police car (siren)                      0.756
   4. Fire engine, fire truck (siren)         0.645
   5. Vehicle horn, car horn, honking         0.534

📊 Generating visualizations...
📊 Saved: analysis_plot.png
📊 Saved: spectrogram.png

================================================================================
```

### Test with Audio File

```bash
python3 siren_detector.py --input /path/to/audio.wav
```

### Live Monitoring (60 seconds)

```bash
python3 siren_detector_live.py --duration 60 --chunk-size 1.0
```

**Live Output:**
```
🚨 LIVE SIREN DETECTION - ALARM or QUIET
================================================================================
Duration: 60s, Chunk: 1.0s

Recording...

[  0.5s] 🚨 ALARM     | 92.34% | Siren                         
[  1.5s] 🔇 QUIET     | 87.56% | Ambient music                 
[  2.5s] 🚨 ALARM     | 95.21% | Police car (siren)            
```

---

## 🎯 Classification Logic

### ALARM Keywords
- Emergency vehicle
- Siren
- Police / Ambulance / Fire engine
- Horn / Honk / Alarm
- Klaxon / Whistle

### QUIET Keywords
- Speech / Music
- Silence / Ambient
- Wind / Rain / Traffic
- Crowd / Applause / Laughter
- Chatter / Conversation

---

## 📊 Options

### siren_detector.py

```bash
--input PATH           Audio file path or 'microphone' (default: microphone)
--duration SECONDS     Recording duration (default: 3)
--no-plot             Skip visualization plots
```

### siren_detector_live.py

```bash
--duration SECONDS     Test duration (default: 60)
--chunk-size SECONDS   Chunk size (default: 1.0)
```

---

## 📈 Output Files

When running `siren_detector.py`, generates:
- `analysis_plot.png` — Waveform + top predictions
- `spectrogram.png` — Audio spectrogram

---

## 🔧 Under the Hood

### Pipeline Steps (from Kaggle notebook)

1. **Load YAMNet Model** — 521-class audio classifier from TensorFlow Hub
2. **Load Audio** — Convert to 16kHz mono (YAMNet requirement)
3. **Inference** — Get predictions for all 521 classes
4. **Top-5 Results** — Extract top 5 predictions with confidence scores
5. **Binary Classification** — Map YAMNet classes to ALARM/QUIET
6. **Visualization** — Plot waveform, predictions, spectrogram

### Key Differences from Kaggle

| Aspect | Kaggle | Our Version |
|--------|--------|------------|
| Input | Audio dataset files | Laptop microphone OR audio file |
| Output | Top-5 predictions | Binary: ALARM or QUIET |
| Visualization | Training plots | Single analysis + spectrogram |
| Use Case | Batch analysis | Real-time detection |

---

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'tensorflow'"

```bash
pip install --upgrade tensorflow tensorflow-hub
```

### "yamnet_class_map.csv" not found

Script automatically downloads on first run. If it fails:

```bash
# Manual download
curl -O https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv
```

### Microphone not detected

```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

### Model download takes too long

TensorFlow Hub (~60MB) downloads on first run. Subsequent runs use cached model.

---

## 💡 Tips

### Adjust Sensitivity

In `classify_alarm_or_quiet()`, change confidence threshold:

```python
if is_alarm and top_conf > 0.3:  # Lower = more sensitive
```

### Add More Keywords

Modify `ALARM_KEYWORDS` or `QUIET_KEYWORDS` lists to fine-tune detection.

### Batch Processing

```bash
for file in *.wav; do
  python3 siren_detector.py --input "$file"
done
```

---

## 📚 References

- **YAMNet Paper**: https://arxiv.org/abs/1810.09050
- **TensorFlow Hub**: https://tfhub.dev/google/yamnet/1
- **AudioSet Classes**: https://research.google.com/audioset/
- **Kaggle Notebook**: https://www.kaggle.com/code/mustafagulhan/emergency-vehicle-siren-detection-using-yamnet

---

**Status**: ✅ Ready for production!
