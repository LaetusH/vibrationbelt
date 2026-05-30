# 🚀 START HERE - ESP32 Siren Detector

**Dein Setup:** ESP32 mit Stereo-Mikrofon auf `192.168.4.1` (Standard-IP)

---

## ⚡ Quick Start (3 Schritte)

### **1. Verbinde dich mit ESP32 AP (WiFi)**

```bash
# Dein Mac sollte sich mit dem ESP32 AP verbinden
# WiFi-Netzwerk: "EspAp" oder ähnlich
# IP: 192.168.4.1

# Check:
ping 192.168.4.1
```

**Wenn ✅ Erfolg:**
```
PING 192.168.4.1 (192.168.4.1): 56 data bytes
64 bytes from 192.168.4.1: icmp_seq=0 ttl=255 time=123.456 ms
...
```

**Wenn ❌ Fehler:**
- [ ] ESP32 ist nicht angesteckt
- [ ] Richtige WiFi gewählt?
- [ ] ESP32 Firmware nicht laufend?

---

### **2. Starten des Detektors**

```bash
cd /Users/nora/Uni/Hackaburg26/vibrationbelt/debug

# Mit Default-IPs (192.168.4.1):
python3 siren_detector_esp32.py --duration 120
```

**Das ist alles!** Der Script macht:
- ✅ Verbindet zu ESP32 auf `192.168.4.1`
- ✅ Empfängt Stereo-Audio über UDP:4444
- ✅ Lädt YAMNet (beim 1. Mal: ~30 Sekunden)
- ✅ Klassifiziert Audio in Echtzeit
- ✅ Gibt Output alle ~500ms

---

### **3. Output lesen**

```
================================================================================
🚨 LIVE ESP32 ALARM DETECTOR with MOTOR CONTROL
================================================================================

📡 Left Mic:  192.168.4.1
📡 Right Mic: 192.168.4.1
⏱️  Duration: 120s

🎤 Connected to ESP32s. Listening for alarms...

[  0.5s] 🔇 left  | QUIET  | 87% | Speech                        |    wait
[  0.6s] 🔇 right | QUIET  | 92% | Music                          |    wait
[  1.2s] 🚨 left  | RED    | 91% | Siren                          | ▶ MOTOR!
   🔴 [LEFT] Motor 0 ACTIVATED (strength: 80%)
[  1.3s] 🚨 right | RED    | 88% | Police car (siren)             | ▶ MOTOR!
   🔴 [RIGHT] Motor 1 ACTIVATED (strength: 80%)
```

---

## 📊 Output Erklärung

| Symbol | Bedeutung |
|--------|-----------|
| `[TIME]` | Sekunden seit Start |
| `🔇` | QUIET - normales Geräusch |
| `🚨` | ALARM - Sirene erkannt |
| `RED` / `QUIET` | Klassifizierung |
| `87%` | Confidence (Sicherheit) |
| `wait` | Nicht genug Votes für Motor |
| `▶ MOTOR!` | **Motor aktiviert!** |

---

## 🔧 Mit Custom IPs

Wenn deine ESP32s **nicht** auf der Standard-IP sind:

```bash
python3 siren_detector_esp32.py \
    --left 192.168.100.50 \
    --right 192.168.100.50 \
    --duration 120
```

(Normalerweise sind beide `left` und `right` die **gleiche IP**, da es Stereo-Kanäle vom gleichen ESP32 sind)

---

## 🧪 Erst Diagnostizieren?

Wenn du nicht sicher bist, ob die Verbindung funktioniert:

```bash
# Test 1: Kann ich den ESP32 erreichen?
python3 test_esp32_stream.py

# Test 2: Bekomme ich Audio aus MicArray?
python3 test_micarray.py

# Test 3: Funktioniert YAMNet?
python3 -c "import tensorflow_hub as hub; print('✅ YAMNet OK')"
```

---

## 🎯 Motor-Control

### Dummy (zum Testen, keine Hardware nötig)
```bash
python3 siren_detector_esp32.py --motor-driver dummy --duration 60
```

### Mit USB Motor-Board
```bash
python3 siren_detector_esp32.py \
    --motor-driver serial \
    --serial-port /dev/ttyUSB0 \
    --duration 60
```

### Mit Raspberry Pi GPIO
```bash
sudo python3 siren_detector_esp32.py \
    --motor-driver gpio \
    --duration 60
```

---

## ❓ Häufige Probleme

### **"No data received" oder "latest_window() returns None"**

**Check 1: Ist ESP32 online?**
```bash
ping 192.168.4.1
```

**Check 2: Sendet ESP32 auf Port 4444?**
```bash
python3 test_esp32_stream.py
```

**Check 3: Firmware läuft?**
- [ ] ESP32 hat LED-Blinken?
- [ ] Mit Strom verbunden?
- [ ] Arduino Code hochgeladen?

---

### **"YAMNet nicht installiert"**

```bash
pip install tensorflow tensorflow-hub
```

---

### **"Connection refused"**

```bash
# ESP32 AP verbunden?
ifconfig | grep 192.168.4

# WiFi Check:
airport -s | grep -i esp
```

---

## 📝 Checkliste vor dem Start

- [ ] ESP32 mit Strom versorgt
- [ ] Mac mit ESP32 WiFi verbunden (SSID: "EspAp" oder ähnlich)
- [ ] `ping 192.168.4.1` funktioniert
- [ ] Python Dependencies: `pip install tensorflow tensorflow-hub numpy`
- [ ] Im `/debug` Ordner

---

## 🎬 Komplettes Beispiel

```bash
# Terminal öffnen
cd /Users/nora/Uni/Hackaburg26/vibrationbelt/debug

# Prüfe ob ESP32 erreichbar
ping 192.168.4.1

# Starten
python3 siren_detector_esp32.py --duration 60

# Jetzt siehst du LIVE Output!
# Beende mit Ctrl+C
```

---

## ✨ Das ist alles!

Du brauchst **nur EIN Skript zu starten**:
```bash
python3 siren_detector_esp32.py
```

Alles andere (YAMNet, UDP, Motors) passiert **automatisch** 🚀

---

**Status**: 🟢 Ready to go!

Wenn du noch Fragen hast → siehe `SETUP_DIAGNOSTICS.md`
