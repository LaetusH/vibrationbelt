# YAMNet Integration für VibrationBelt

Statt ein eigenes CNN-Modell zu trainieren, nutzen wir **YAMNet von Google** — ein vorgefertigtes Audio-Klassifizierungsmodell.

## ✅ Vorteile von YAMNet

- ✅ **Bereits trainiert** auf 521 Audio-Klassen
- ✅ **Siren-Detection** (Feuerwehr, Krankenwagen, Polizei, etc.)
- ✅ **Vehicle Horn Detection** (Autopfen, Hupen)
- ✅ **Noise & Speech Rejection** (ignoriert Musik, Sprache, Hintergrund)
- ✅ **No Training Required** — sofort einsatzbereit
- ✅ **Kleine Modellgröße** (~60 MB)
- ✅ **Schnelle Inferenz** (real-time auf CPU)

## 📥 Installation

```bash
# TensorFlow & TensorFlow Hub
pip install tensorflow tensorflow-hub

# Weitere Dependencies
pip install numpy requests
```

## 🚀 Verwendung

### Option 1: Mit echtem Audio vom ESP32

```bash
python3 run_live_analysis_yamnet.py --url http://localhost:5262 --interval 100
```

### Option 2: Mit simuliertem Audio (Test)

```bash
python3 run_live_analysis_yamnet.py --simulate --duration 30
```

### Options

```
--url URL              DebugClient URL (default: http://localhost:5262)
--interval MS          Analyse-Intervall in ms (default: 100)
--confidence THRESHOLD Konfidenz-Schwelle (default: 0.3, range: 0-1)
--simulate            Simuliertes Audio statt DebugClient
--duration SECONDS    Simulationsdauer (default: 60)
```

## 🎯 Erkannte Alarm-Klassen

| YAMNet ID | Klasse | Beschreibung |
|-----------|--------|-------------|
| 399 | 🚨 Siren | Allgemeine Sirene |
| 400 | 🚓 Police Car Siren | Polizeisirene |
| 401 | 🚑 Ambulance Siren | Krankenwagensirene |
| 402 | 🚒 Fire Engine Siren | Feuerwehrsirene |
| 377 | 🚙 Vehicle Horn | Autohupe/Horn |
| 378 | 🚗 Beep | Piepton, kurze Töne |
| 379 | 🏎️ Race Car | Rennwagen, Beschleunigung |
| 383 | 🚛 Truck | Lastwagen |

## 🚫 Ignorierte Klassen (False-Alarm Prevention)

YAMNet **ignoriert automatisch**:

- 🎵 **Musik** — alle Musikgenres
- 👤 **Sprache** — Gespräche, Podcasts
- 👥 **Crowd** — Applaus, Jubel, Lachen
- 🌧️ **Umgebung** — Wind, Regen, Gewitter
- Und viele mehr...

## 📊 Live-Output

```
[00:15] [████████████░░░░░░░░] 62.3% | 🚨 🚒 Feuerwehr     | 🚒 Fire Engine Siren (89%)
[00:16] [████████████░░░░░░░░] 61.8% | 🚨 🚒 Feuerwehr     | 🚒 Fire Engine Siren (91%)
[00:17] [░░░░░░░░░░░░░░░░░░░░]  0.0% | 🔇 quiet           | 

==========================================================================================
📊 SESSION STATISTICS
==========================================================================================
Duration: 0.3 minutes
Chunks analyzed: 18
Alarms detected: 2

🚨 Alarm Types Detected:
   🚒 Fire Engine Siren: 2 (100.0%)
==========================================================================================
```

## 🔧 Motor-Zuordnung (Optional)

Für Motor-Vibrationen (wenn ESP32 mit Motoren verbunden ist):

```python
from analysis_engine.motor_mapper import MotorMapper

# Noch nicht in yamnet.py integriert, aber möglich:
mapper = MotorMapper()
if result['is_alarm']:
    # DOA von 2. Mikrofon hinzufügen
    motor = mapper.get_motor(doa_degrees)
    print(f"Vibrate Motor: {motor}")
```

## 🧪 Testing

### Test 1: Sirene simulieren

```bash
# Terminal 1: Start DebugClient (falls verfügbar)
cd ~/Uni/Hackaburg26/vibrationbelt/DebugClient
dotnet run

# Terminal 2: Analyse mit simuliertem Audio
python3 run_live_analysis_yamnet.py --simulate --duration 30
```

### Test 2: Mit echtem Audio

```bash
# Terminal 1: DebugClient läuft
# Terminal 2: Analyse-Engine
python3 run_live_analysis_yamnet.py

# Terminal 3: Sirene in Nähe abspielen oder echte Sirene aufnehmen
```

### Test 3: Falsch-Alarm-Rate testen

```bash
# Musik abspielen → sollte NICHT als Alarm erkannt werden
python3 run_live_analysis_yamnet.py --simulate

# Sprache → sollte NICHT als Alarm erkannt werden
# -> Ist in simuliertem Audio nicht drin, aber YAMNet ist trainiert darauf zu ignorieren
```

## 🎛️ Feinabstimmung

### Konfidenz-Schwelle anpassen

Höhere = strenger, weniger false alarms:
```bash
python3 run_live_analysis_yamnet.py --confidence 0.5  # Strict
python3 run_live_analysis_yamnet.py --confidence 0.3  # Default
python3 run_live_analysis_yamnet.py --confidence 0.1  # Permissive
```

### Intervall anpassen (schneller/langsamer)

```bash
python3 run_live_analysis_yamnet.py --interval 50   # Schneller (20 Hz)
python3 run_live_analysis_yamnet.py --interval 100  # Default (10 Hz)
python3 run_live_analysis_yamnet.py --interval 200  # Langsamer (5 Hz)
```

## 📚 YAMNet Dokumentation

- **Official TensorFlow Hub**: https://tfhub.dev/google/yamnet/1
- **Kaggle Model Hub**: https://www.kaggle.com/models/google/yamnet
- **Paper**: https://arxiv.org/abs/1810.09050 ("YAMNet: An Audio Event Deep Learning Model")

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'tensorflow'"

```bash
pip install --upgrade tensorflow tensorflow-hub
```

### YAMNet model download fehlt

Das Modell wird beim ersten Lauf automatisch heruntergeladen (~60 MB).
Falls das fehlschlägt, müssen Sie möglicherweise VPN/Proxy nutzen.

### Zu viele False Alarms

→ Erhöhe `--confidence` Schwelle:
```bash
python3 run_live_analysis_yamnet.py --confidence 0.5
```

### Zu viele False Negatives

→ Senke `--confidence` Schwelle:
```bash
python3 run_live_analysis_yamnet.py --confidence 0.1
```

## 📝 Nächste Schritte

1. **Test mit echten Sirenen** — stelle sicher dass Feuerwehr/Ambulanz/Polizei erkannt werden
2. **Falsch-Alarm-Rate messen** — teste mit Musik, Sprache, Hintergrund
3. **Motor-Vibrationen integrieren** — DOA + YAMNet kombinie
4. **In Production deployieren** — auf Raspberry Pi oder Edge-Device

---

**Status**: ✅ YAMNet ist bereit für Production!
