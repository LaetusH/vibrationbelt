# 🎤 Live Testing Guide - Analysis Engine

Schritt-für-Schritt Anleitung zum Testen der echten Audio-Analyse mit deiner VibrationBelt.

---

## 🎯 Quick Start (2 Minuten)

### Terminal 1: Starten DebugClient (C#)

```bash
cd ~/Uni/Hackaburg26/vibrationbelt/DebugClient
dotnet run
```

**Output:**
```
Now listening on: http://localhost:5262
```

✅ DebugClient läuft jetzt und empfängt Audio von der ESP32 via UDP.

### Terminal 2: Starten Live Analysis (Python)

```bash
cd ~/Uni/Hackaburg26/vibrationbelt

# OPTION A: Mit Simulation (zum Testen)
python run_live_analysis.py --simulate --duration 30

# OPTION B: Mit echtem Audio von DebugClient
python run_live_analysis.py --url http://localhost:5262 --interval 100
```

**Output:**
```
======================================================================
🎤 LIVE ANALYSIS ENGINE
======================================================================
Listening for audio from DebugClient...

[00:00] ⬆️   334.6° | [██████░░░░░░░░░░░░] 33.7% |   quiet | 🎮 Motor None
[00:01] ⬆️   334.6° | [██████░░░░░░░░░░░░] 33.3% |   quiet | 🎮 Motor None
...
```

---

## 📊 Output verstehen

```
[00:15] ⬆️   45.3° | [████████████░░░░░░░░] 61.2% | 🚨 ALARM | 🎮 Motor 1 (Right)
      │        │      │                        │       │        │
      │        │      │                        │       │        └─ Motor Prediction
      │        │      │                        │       └─ Alarm Status
      │        │      │                        └─ Confidence (0-100%)
      │        │      └─ Confidence Bar (20 chars)
      │        └─ Direction Angle (0-360°) + Emoji
      └─ Elapsed Time [mm:ss]
```

### Bedeutung der Outputs:

| Value | Meaning |
|-------|---------|
| **⬆️ 334.6°** | Sound kommt von **Vorne** (0°) |
| **➡️ 90°** | Sound kommt von **Rechts** |
| **⬇️ 180°** | Sound kommt von **Hinten** |
| **⬅️ 270°** | Sound kommt von **Links** |
| **🚨 ALARM** | Alarm erkannt (Confidence > 60%) |
| **quiet** | Kein Alarm erkannt |
| **Motor 0-3** | Welcher Motor würde aktiviert (0=Front, 1=Right, 2=Back, 3=Left) |

---

## 🔌 Setup Übersicht

```
┌─────────────┐
│   ESP32     │  ← Mit 2 Mikrophones
└──────┬──────┘
       │ UDP Port 4444
       ↓
┌──────────────────────┐
│  DebugClient (C#)    │
│  http://localhost:   │
│  5262                │
└──────┬───────────────┘
       │ REST API
       ↓ /api/audio/snapshot
┌──────────────────────┐
│ run_live_analysis.py │
│ (Python Pipeline)    │
└──────────────────────┘
       │
       ↓
   Display Results
```

---

## 💻 Detaillierte Anleitung

### Step 1: DebugClient konfigurieren

Bearbeite `DebugClient/appsettings.json`:

```json
{
  "Belt": {
    "EspIp": "10.8.5.167",     // ← IP deiner ESP32
    "EspPort": 4444,           // ← Port der ESP32 sendet zu
    "SampleRate": 16000,       // ← 16 kHz
    "Channels": 2              // ← Dual-Mic (Mic1, Mic2)
  }
}
```

### Step 2: Starten DebugClient

```bash
cd DebugClient
dotnet run

# Output:
# info: DebugClient.Services.MicReceiver[0]
#       Subscribed to 10.8.5.167:4444 via UDP
# 
# info: Microsoft.Hosting.Lifetime[14]
#       Now listening on: http://localhost:5262
```

✅ DebugClient wartet auf Audio von der ESP32.

### Step 3: ESP32 Audio senden

Die ESP32 sollte bereits UDP-Pakete zu DebugClient senden.

**Check:** Öffne im Browser: `http://localhost:5262`
- Du solltest ein **Dashboard** sehen
- Die Waveform sollte sich bewegen (wenn Sound da ist)

Wenn nicht:
```bash
# Check ob DebugClient Audio empfängt:
curl http://localhost:5262/api/audio/status | jq .
```

Sollte zeigen:
```json
{
  "isReceiving": true,
  "packetsReceived": 1250,
  "lastPacketAgoMs": 45.23
}
```

### Step 4: Live Analysis starten

```bash
cd ~/Uni/Hackaburg26/vibrationbelt
python run_live_analysis.py --url http://localhost:5262
```

**Jetzt:**
1. 🔊 **Stelle einen Alarm in die Nähe der Mikrophones** (z.B. Smartphone Wecker)
2. 📊 **Beobachte die Ausgabe:**
   - DOA sollte sich ändern wenn du den Sound bewegst
   - Confidence sollte steigen wenn der Alarm näher ist
   - Motor Prediction sollte die richtige Richtung anzeigen

### Step 5: Interaktiv testen

**Test 1: Richtung**
```
Stelle Alarm in verschiedene Richtungen:
  - Vorne → ⬆️ 0-45°
  - Rechts → ➡️ 45-135°
  - Hinten → ⬇️ 135-225°
  - Links → ⬅️ 225-315°
```

**Test 2: Alarm-Erkennung**
```
Mit echtem Alarm (Wecker):
  - Confidence sollte 60%+ sein
  - Status sollte 🚨 ALARM zeigen
  - Motor sollte anzeigen welcher aktiviert wird

Mit normalem Lärm (Sprechen, Musik):
  - Confidence sollte unter 60% bleiben
  - Status sollte "quiet" bleiben
```

**Test 3: Motor Response**
```
Motor prediction zeigt welcher Motor aktiv würde:
  - Motor 0 = Vorne (0-45° + 315-360°)
  - Motor 1 = Rechts (45-135°)
  - Motor 2 = Hinten (135-225°)
  - Motor 3 = Links (225-315°)
```

---

## 🔧 Optionen für run_live_analysis.py

```bash
python run_live_analysis.py --help

# Usage:
#   --url TEXT        DebugClient URL (default: http://localhost:5262)
#   --interval INT    Analysis interval in ms (default: 100)
#   --simulate        Use simulated audio instead of DebugClient
#   --duration FLOAT  Simulation duration in seconds (default: 60)
```

### Beispiele:

```bash
# Echtes Audio, schnellere Updates (50ms)
python run_live_analysis.py --interval 50

# Echtes Audio, langsamere Updates (200ms)
python run_live_analysis.py --interval 200

# Simulation für 60 Sekunden
python run_live_analysis.py --simulate --duration 60

# Simulation + nur Text (keine Fancy UI)
python run_live_analysis.py --simulate --no-ui
```

---

## 📈 Debugging Tipps

### DebugClient antwortet nicht

```bash
# Check ob DebugClient läuft:
curl http://localhost:5262/api/audio/health

# Check ob Audio empfangen wird:
curl http://localhost:5262/api/audio/status | jq .

# Check wenn isReceiving: false
# → ESP32 sendet nicht
# → Check IP/Port in appsettings.json
# → Check ob ESP32 Code läuft
```

### Audio wird empfangen aber keine Analyse

```bash
# Check ob Python Script läuft:
ps aux | grep run_live_analysis

# Teste mit Simulation:
python run_live_analysis.py --simulate

# Wenn Simulation funktioniert → Problem mit DebugClient API
# Wenn Simulation nicht funktioniert → Problem mit Python/Pipeline
```

### DOA immer 0° oder konstant

```bash
# DOA-Algorithmus braucht TDOA (Time Delay zwischen Mikes)
# Das funktioniert nur wenn:
# ✓ Beide Mikrophones aktiv sind
# ✓ Sound von außerhalb kommt (nicht monaural)
# ✓ Mikrophones mindestens 5cm auseinander sind

# Test: Stelle Sound direkt neben Mic 1 → sollte ~0-90°
#       Stelle Sound direkt neben Mic 2 → sollte ~180-270°
```

### Confidence immer niedrig (<30%)

```bash
# Template Matching braucht einen trainierten Alarm-Sound
# Derzeit wird ein Baseline-Template benutzt

# Optionen:
# 1. Benutze einen Alarm der ähnlich dem Template ist
# 2. Trainiere ein CNN mit deinem echten Alarm
#    (Siehe analysis_engine/models/cnn_trainer.py)
# 3. Erhöhe Threshold in recognizer (wenn du bereit bist)
```

---

## 🎓 Nächste Schritte

1. ✅ **Teste die Pipeline** mit echtem Audio (jetzt!)
2. 📚 **Sammle Training Data** (20-30 Minuten Audio)
3. 🤖 **Trainiere CNN** mit `analysis_engine/models/cnn_trainer.py`
4. 📊 **Vergleiche** Template vs CNN Accuracy
5. 🚀 **Deploy** mit bestem Model

---

## 📝 Logs speichern

Für später Analyse:

```bash
# Simulation in Datei speichern
python run_live_analysis.py --simulate | tee analysis_log.txt

# Echtes Audio in Datei speichern
python run_live_analysis.py --url http://localhost:5262 | tee analysis_live.txt

# Log später analysieren
tail -100 analysis_live.txt
grep "ALARM" analysis_live.txt | wc -l
```

---

## 🎯 Success Checklist

- [ ] DebugClient läuft (`http://localhost:5262`)
- [ ] DebugClient empfängt Audio (`isReceiving: true`)
- [ ] `run_live_analysis.py --simulate` funktioniert
- [ ] `run_live_analysis.py --url ...` verbindet zu DebugClient
- [ ] DOA ändert sich wenn du Sound bewegst
- [ ] Alarm wird erkannt (Confidence >60%) wenn echter Alarm läuft
- [ ] Motor Prediction zeigt richtige Richtung

---

## 🚨 Troubleshooting

Wenn nichts funktioniert:

1. **Checke ob beide Prozesse laufen:**
   ```bash
   ps aux | grep -E "dotnet run|run_live_analysis"
   ```

2. **Checke Ports:**
   ```bash
   lsof -i :5262  # DebugClient
   ```

3. **Teste API direkt:**
   ```bash
   curl http://localhost:5262/api/audio/health
   curl http://localhost:5262/api/audio/status
   curl http://localhost:5262/api/audio/snapshot?samples=16000
   ```

4. **Logs checken:**
   ```bash
   tail -50 /tmp/debugclient.log
   ```

5. **Frag um Hilfe:**
   - Was sind die exakten Error Messages?
   - Was zeigt `curl http://localhost:5262/api/audio/status`?
   - Läuft die ESP32 und sendet Audio?

---

**Status:** ✅ Ready to test!  
**Time to first results:** ~5 minutes  
**Viel Spaß! 🚀**
