# Live Streaming Integration — What You Now Have

## ✅ What's Ready

### 1. **StreamProcessor** (Core)
- Single audio input stream → Detection events
- Automatic baseline learning (first 10 sec)
- Unified output: **ALARM** or **LOUD_SOUND** (exactly as requested!)
- Background-thread safe

### 2. **MultiStreamAnalyzer** (Multi-Mic Ready)
- Add multiple streams dynamically
- Unified detection queue (all events in one place)
- Perfect for expanding to multiple mics later

### 3. **Live Integration Scripts**
- `client/live_analysis.py` — Ready to run with ESP32
- `examples/demo_stream_simple.py` — Test without hardware

### 4. **Detection Output**
```python
Detection(
    type=DetectionType.ALARM,         # or LOUD_SOUND
    confidence=0.89,                  # 0-1
    snr_db=18.5,                      # Signal-to-noise
    timestamp_sec=145.3,              # When it happened
    source="mic_0",                   # Which input
    detector_type="siren",            # For debugging
)
```

---

## 🚀 Try It Now (3 Steps)

### Step 1: Make Sure ESP32 is Connected
```bash
ping 10.8.5.177
```

### Step 2: Run Live Detection
```bash
cd ~/Uni/Hackaburg26/vibrationbelt/client
python live_analysis.py 10.8.5.177
```

### Step 3: Make Noises
- First 10 sec: Keep quiet (baseline learning)
- Then: Scream, bang things, play alarm sounds
- Watch for `🚨 ALARM` and `⚠️ LOUD_SOUND` in output

---

## 📝 To Integrate Into Your Project

### Simplest Way (Single Stream)

```python
import sys
sys.path.insert(0, "processing")

from audio_analyzer.stream_processor import StreamProcessor, DetectionType

# Create processor
processor = StreamProcessor("mic_0", sr=16000)

# Handle detections
def on_event(detection):
    if detection.type == DetectionType.ALARM:
        print(f"🚨 ALARM! Confidence: {detection.confidence:.0%}")
    elif detection.type == DetectionType.LOUD_SOUND:
        print(f"⚠️ LOUD SOUND! Confidence: {detection.confidence:.0%}")

processor.on_detection(on_event)

# Feed chunks from your audio source
for chunk in audio_stream:
    processor.process_chunk(chunk)
```

### With ESP32 (Using vibrationbelt)

```python
import vibrationbelt as vb
from audio_analyzer.stream_processor import StreamProcessor
import numpy as np

# Connect to ESP32
mic = vb.MicStream("10.8.5.177").start()

# Create processor
processor = StreamProcessor("mic_0", sr=vb.SAMPLE_RATE)
processor.on_detection(print)

# Stream chunks
for chunk in mic:
    audio = chunk.samples.astype(np.float32) / 32768.0
    processor.process_chunk(audio)

mic.close()
processor.close()
```

### With Multiple Mics (Future)

```python
from audio_analyzer.stream_processor import MultiStreamAnalyzer

analyzer = MultiStreamAnalyzer()
analyzer.add_stream("mic_0")
analyzer.add_stream("mic_1")

analyzer.connect_source("mic_0", esp32_stream)
analyzer.connect_source("mic_1", usb_stream)

for detection in analyzer.iter_detections():
    print(f"{detection.source}: {detection.type.value}")
```

---

## 🔧 Key Settings to Know

### Frame Size
- **Default: 2048 samples (~128ms @ 16kHz)**
- Sweet spot for streaming (latency + accuracy)
- Don't change unless you have a reason

### Baseline Duration
- **Default: 10 seconds**
- First 10 sec of stream = learning ambient noise
- After: Full detection starts
- Can adjust in StreamProcessor init

### Sensitivity
```python
processor = StreamProcessor(
    "mic_0",
    alarm_sensitivity=0.5,      # 0.1-1.0 (default: 0.5)
    anomaly_sensitivity=0.6,    # 0.1-1.0 (default: 0.6)
)
```
- **Lower (0.3):** Stricter, fewer false positives
- **Higher (0.9):** More sensitive, catches more events

---

## 🎯 What Happens With Each Detection

### ALARM Events
```
Input:    Siren, beeper, alarm sound
Pattern:  Regular frequency + pulsing
Output:   Detection.type = DetectionType.ALARM
Use for:  Critical alerts, notifications, logging
```

### LOUD_SOUND Events
```
Input:    Scream, crash, breaking glass, etc.
Pattern:  Much louder than ambient + anomalous
Output:   Detection.type = DetectionType.LOUD_SOUND
Use for:  Safety warnings, incident logs, monitoring
```

---

## 📊 Architecture Overview

```
┌─────────────────────────┐
│ Audio Input Source       │  (ESP32, USB, file, etc.)
└────────────┬────────────┘
             │
             ↓
┌─────────────────────────┐
│  StreamProcessor        │  ← YOU ARE HERE
│                         │
│ • Buffers 2048 samples  │
│ • Learns baseline (10s) │
│ • Runs 2 detectors      │
│ • Emits Detection event │
└────────────┬────────────┘
             │
             ↓
┌─────────────────────────┐
│  Detection Event        │
│  .type (ALARM/LOUD...) │
│  .confidence (0-1)      │
│  .snr_db (dB)          │
│  .detector_type (debug) │
└────────────┬────────────┘
             │
             ↓
    ┌───────────────────┐
    │  Your Code        │
    │  (print/log/alert)│
    └───────────────────┘
```

---

## 🚀 For Multiple Mics Later

When you add more microphones:

```python
analyzer = MultiStreamAnalyzer()

# Add first mic (belt)
analyzer.add_stream("belt_mic", sr=16000)
analyzer.connect_source("belt_mic", esp32_stream)

# Add second mic (USB)
analyzer.add_stream("usb_mic_1", sr=44100)
analyzer.connect_source("usb_mic_1", usb_stream)

# Add third mic (ALSA)
analyzer.add_stream("alsa_mic", sr=16000)
analyzer.connect_source("alsa_mic", alsa_stream)

# Single loop for ALL events
for detection in analyzer.iter_detections():
    print(f"{detection.source}: {detection.type.value}")
    # Routes automatically to the right handler
```

**No code changes needed in rest of your app** — just add streams!

---

## ✅ Checklist for Integration

- [ ] Read `LIVE_STREAMING_GUIDE.md` for full docs
- [ ] Try `python client/live_analysis.py 10.8.5.177`
- [ ] Test with synthetic events (scream, bang on table)
- [ ] Copy StreamProcessor code snippet into your project
- [ ] Replace `print` callback with your own handler
- [ ] Test with actual ESP32 audio
- [ ] Tune sensitivity if needed
- [ ] Deploy! 🚀

---

## 📚 Related Docs

1. **LIVE_STREAMING_GUIDE.md** — Full API reference + examples
2. **ANOMALY_DETECTION.md** — Deep dive on anomaly tuning
3. **DETECTOR_TUNING.md** — Alarm detection details
4. **ANOMALY_READY.md** — Quick summary

---

## 💡 Pro Tips

1. **Test first with demo:**
   ```bash
   python examples/demo_stream_simple.py
   ```

2. **Always wait 10 seconds before testing** (baseline learning)

3. **Check SNR in your audio:**
   ```python
   rms = np.sqrt(np.mean(audio**2))
   snr_db = 20 * np.log10(rms / 0.01)  # Typical baseline
   # If < 6 dB, sound is too quiet
   ```

4. **Log detections for tuning:**
   ```python
   def handle(d):
       print(f"{d.timestamp_sec:.1f}s | {d.type.value} | "
             f"Conf: {d.confidence:.0%} | SNR: {d.snr_db:.1f}dB")
   processor.on_detection(handle)
   ```

5. **When adding more mics, test each separately first**

---

**You're ready! Start with `python client/live_analysis.py 10.8.5.177` and it just works! 🎉**
