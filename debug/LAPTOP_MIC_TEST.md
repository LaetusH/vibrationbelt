# Laptop Microphone Test & Calibration

Da ihr das Gefühl habt, dass die Mikros zu leise Töne aufnehmen, hier sind Tools zum Debuggen.

## 🚀 Quick Start

### 1. Mikrofon-Geräte auflisten

```bash
python3 mic_calibration.py --list
```

**Output:**
```
[0] Built-in Microphone
    Input Channels:  1
    Sample Rate:     48000 Hz

[1] External USB Mic
    Input Channels:  1
    Sample Rate:     48000 Hz
```

### 2. Komplette Kalibrierung

```bash
python3 mic_calibration.py
```

Das Skript wird:
1. Alle Mikrofone auflisten
2. Das beste Mikrofon empfehlen
3. 3 Sekunden Stille aufnehmen
4. 3 Sekunden Sound aufnehmen
5. Die Qualität beurteilen

**Output:**
```
🧪 TESTING DEVICE: Built-in Microphone
========================================

📊 Recording 3 seconds of silence...

📈 Silence Analysis:
   Noise Floor (RMS):  0.000234
   Peak Noise:         0.001543
   ✅ Good device

🔊 Now speak/make noise for 3 seconds...

📈 With Sound:
   Peak Amplitude:     0.0234
   RMS Level:          0.0089
   Dynamic Range:      99.6x

⚠️  PROBLEM: Signal is TOO QUIET
   Solutions:
   1. Increase system microphone level
   2. Speak louder or get closer to mic
   3. Use external microphone
```

### 3. Live-Test mit YAMNet

```bash
# Standard (interne Empfehlung)
python3 live_mic_test.py --duration 30

# Spezifisches Gerät
python3 live_mic_test.py --device 1 --duration 30
```

**Live-Output:**
```
🎤 LIVE MICROPHONE TEST + YAMNet
=====================================
Recording for 30 seconds...
🔊 Speak, play sound, or generate noise near the microphone

📊 Amplitude: [████████████░░░░░░░░░░░░] 0.0234 (avg: 0.0145, peak: 0.1234) | 
RMS: [█░░░░░░░░░░░░░░░░░░] 0.0089 | 🚨 Siren (87%)

📊 Amplitude: [███████████░░░░░░░░░░░░░░] 0.0312 (avg: 0.0156, peak: 0.1234) | 
RMS: [██░░░░░░░░░░░░░░░░] 0.0145 | 🚨 Fire Engine (93%)
```

---

## 🔧 Häufige Probleme & Lösungen

### Problem 1: "Signal is TOO QUIET" (< 0.05)

**Ursachen:**
- Laptop-Mikrofon ist zu empfindlich klein eingestellt
- Mikrofon ist zu weit weg
- Schlechtes internes Mikrofon

**Lösungen (in dieser Reihenfolge):**

#### 🔊 **Schritt 1: System Mikrofon-Level erhöhen**

**macOS:**
```
System Preferences → Sound → Input
→ Wähle Mikrofon → Pegel anpassen
```

**Linux (PulseAudio):**
```bash
# Alle Input-Geräte auflisten
pacmd list-sources

# Lautstärke erhöhen (0-65536)
pacmd set-source-volume <device-index> 50000
```

**Windows:**
```
Settings → System → Sound → Volume mixer
→ App volume and device preferences → Input devices
```

#### 🎤 **Schritt 2: Externer Mikrofon verwenden**

Viel bessere Option! Empfehlung:
- **USB Condenser Mic** (~20-50€)
  - Z.B.: Audio-Technica AT2020USB+, Blue Yeti Nano
  - 10x besser als eingebautes Mikrofon
  - Auto-Setup via USB

#### 📍 **Schritt 3: Näher ans Mikrofon gehen**

```
Optimal: 10-20 cm Abstand
Normal:  30-50 cm Abstand
Problem: > 50 cm Abstand
```

---

### Problem 2: "Signal is clipping" (> 0.7)

**Ursachen:**
- Mikrofon-Level zu hoch eingestellt
- Zu laut neben dem Mikrofon

**Lösungen:**
1. System-Mikrofon-Level senken
2. Weiter weg vom Mikrofon gehen
3. Weniger laut sprechen/spielen

---

### Problem 3: Falsches Mikrofon wird verwendet

```bash
# Alle Geräte anzeigen
python3 mic_calibration.py --list

# Spezifisches Gerät testen
python3 mic_calibration.py --test 1

# In live_mic_test.py verwenden
python3 live_mic_test.py --device 1
```

---

## 📊 Zielwerte für gutes Signal

| Metrik | Zu leise | OK | Optimal | Zu laut |
|--------|---------|----|---------|---------| 
| Peak Amplitude | < 0.05 | 0.05-0.1 | 0.1-0.3 | > 0.7 |
| RMS Level | < 0.01 | 0.01-0.05 | 0.05-0.15 | > 0.3 |
| Dynamic Range | < 10x | 10-50x | 50-200x | > 500x |

---

## 🧪 Workflow zum Debuggen

### Schritt 1: Kalibrieren
```bash
python3 mic_calibration.py
# → Note die empfohlene Device-ID
```

### Schritt 2: Live testen
```bash
python3 live_mic_test.py --device <ID> --duration 60
# → Probiere verschiedene Sounds
# → Überprüfe die Amplitude-Meter
```

### Schritt 3: Mit YAMNet testen
```bash
python3 run_live_analysis_yamnet.py --simulate --duration 30
# → Sollte auch Sirenen-ähnliche Töne erkennen
```

### Schritt 4: Mit echtem Audio testen
```bash
# Terminal 1: DebugClient (falls verfügbar)
cd DebugClient && dotnet run

# Terminal 2: Laptop-Mikrofon statt DebugClient
python3 live_mic_test.py --device <ID> --duration 60
```

---

## 💡 Pro-Tipps

### Externe Mikros testen
```bash
# Nachdem ihr ein USB-Mikrofon verbunden habt
python3 mic_calibration.py --list
# → Neue Device sollte erscheinen
```

### Verschiedene Sample-Rates
```bash
# Standardmäßig 16000 Hz (16 kHz)
python3 live_mic_test.py --sample-rate 16000

# Höhere Qualität (48 kHz, aber größer)
python3 live_mic_test.py --sample-rate 48000
```

### Recording speichern (für später)
```python
# In live_mic_test.py ändern:
# Am Ende des analyze_audio():
import scipy.io.wavfile as wavfile
wavfile.write("test_audio.wav", 16000, audio)
```

---

## 🎙️ ESP32 vs Laptop Mikrofon

**Warum sind die ESP32-Mikrofone leiser?**

| Aspekt | Laptop | ESP32 |
|--------|--------|-------|
| Typ | Kondensator | MEMS |
| Empfindlichkeit | Gut | Sehr gering |
| Rausch | Moderat | Hoch |
| Qualität | Besser | Schlechter |

**Lösung für ESP32:**
- Externe I2S Mikrofone verwenden
- Z.B.: INMP441, PCM1808
- Deutlich besseres Signal

---

## 📝 Debug-Info sammeln

Falls ihr Hilfe braucht, sammelt diese Infos:

```bash
# 1. Geräte-Liste
python3 mic_calibration.py --list > devices.txt

# 2. Kalibrierungs-Ergebnis
python3 mic_calibration.py > calibration.txt

# 3. Live-Test-Output
python3 live_mic_test.py --duration 10 > live_test.txt

# Dann teilt mir die Files!
```

---

**Status**: 🟢 **Ready to debug!**

Viel Erfolg! 🎉
