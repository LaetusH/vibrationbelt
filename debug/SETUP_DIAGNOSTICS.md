# 🔍 Diagnose: Warum läuft das nicht?

## ❌ Problem: Keine Ausgabe / "QUIET" erscheint nicht

```
Du startest: python3 siren_detector_esp32.py
Ergebnis:    Script hängt, keine Output
```

---

## 🔧 Ursachen (von häufig zu selten)

### **1️⃣ ESP32s senden KEINE Daten (WAHRSCHEINLICHSTES)**

```bash
# Check: Lausche auf UDP Port 4444
nc -l -u 4444

# In anderem Terminal:
# Oder starte den Diagnose-Check:
python3 test_esp32_stream.py
```

**Wenn kein Output:**
- ❌ ESP32 Firmware läuft nicht
- ❌ ESP32 Firmware sendet nicht auf Port 4444
- ❌ Firewall/Netzwerk blockiert UDP

---

### **2️⃣ Falsche ESP32 IPs**

```python
# Check in siren_detector_esp32.py:
python3 -c "
import socket
for ip in ['192.168.4.1', '192.168.4.1']:
    try:
        result = socket.gethostbyname(ip)
        print(f'✅ {ip} resolves to {result}')
    except:
        print(f'❌ {ip} cannot be resolved')
"
```

**Wenn ❌:**
- Die IPs sind falsch
- ESP32s sind nicht im Netzwerk
- Netzwerk-Kabel/WiFi down

---

### **3️⃣ MicArray ist kaputt**

```bash
python3 test_micarray.py
```

**Wenn Error:**
- Client Library ist broken
- YAMNet nicht installiert

---

## 📋 Diagnose-Checkliste

Führe diese Checks aus **in dieser Reihenfolge**:

### **Step 1: Netzwerk-Check**

```bash
# Sind ESP32s erreichbar?
ping -c 3 192.168.4.1
ping -c 3 192.168.4.1

# Output sollte sein:
# 64 bytes from 192.168.4.1: icmp_seq=1 ttl=255 time=XX.XXms
# 3 packets transmitted, 3 received, 0.0% packet loss
```

**Wenn ❌ "Network unreachable":**
- ESP32 Power Check
- WiFi Verbindung Check
- Falsche IP?

---

### **Step 2: UDP Stream Check**

```bash
python3 test_esp32_stream.py
```

**Wenn ✅ "Received X bytes from 192.168.4.1":**
- ESP32 sendet! → Gehe zu Step 3

**Wenn ❌ "No data received":**
- ESP32 Firmware Problem
- Port 4444 ist nicht richtig
- Firewall blockiert

---

### **Step 3: MicArray Check**

```bash
python3 test_micarray.py
```

**Wenn ✅ "Connected! Got audio chunks":**
- MicArray funktioniert

**Wenn ❌ "None" oder Error:**
- Stream empfangen aber keine Chunks
- Client Library Problem

---

### **Step 4: YAMNet Check**

```bash
python3 -c "
import tensorflow_hub as hub
print('Loading YAMNet...')
model = hub.load('https://tfhub.dev/google/yamnet/1')
print('✅ YAMNet loaded!')
"
```

**Wenn ✅:**
- YAMNet OK

**Wenn ❌:**
- TensorFlow Problem
- Internet für Download zu langsam

---

### **Step 5: Motor Driver Check**

```bash
python3 -c "
from motor_driver import create_motor_driver
driver = create_motor_driver('dummy')
driver.set_motor(0, 0.8)
driver.set_motor(1, 0.5)
driver.stop_all()
"
```

**Wenn ✅:**
- Motor Driver OK

---

## 🚀 Wenn alle Checks ✅ sind

Dann läuft:

```bash
python3 siren_detector_esp32.py --duration 60
```

---

## 🛠️ Test-Scripts zum Debuggen

### **test_esp32_stream.py** - Höre auf UDP Port 4444

```python
import socket, struct, time

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 4444))
sock.settimeout(5)

print('📡 Listening on UDP:4444...')
try:
    while True:
        data, addr = sock.recvfrom(2048)
        print(f'✅ {len(data)} bytes from {addr[0]}')
except socket.timeout:
    print('❌ No data (timeout)')
finally:
    sock.close()
```

### **test_micarray.py** - Teste MicArray direkt

```python
import sys
sys.path.insert(0, '../client')
from vibrationbelt import MicArray, MicSpec

array = MicArray({
    'left': MicSpec('192.168.4.1'),
    'right': MicSpec('192.168.4.1'),
}, buffer_seconds=1.0)

with array:
    for i in range(5):
        window = array.latest_window(0.5)
        if window:
            print(f'✅ Window {i}: Got data')
        else:
            print(f'❌ Window {i}: None')
```

---

## 💡 Häufige Lösungen

### **Problem: "No data received"**

**Ursache 1: ESP32 Firmware läuft nicht**
```
Lösung: Firmware hochladen
- Arduino IDE öffnen
- sketch_esp32_microphone hochladen
- Warten bis Bootloader fertig
```

**Ursache 2: Falsche Port/IP**
```
Lösung: In Firmware prüfen
- Welcher Port?
- Welche IP?
- Gleich wie in Client?
```

**Ursache 3: Firewall blockiert UDP**
```
Lösung: 
- UFW disable (Ubuntu)
- System Preferences → Security (Mac)
- Windows Firewall Rule hinzufügen
```

---

### **Problem: "latest_window() returns None"**

**Ursache: Daten kommen an, aber MicArray kann nicht dekodieren**

```
Lösung: Prüfe Daten-Format
- Magic bytes OK?
- Sample rate 8kHz?
- 2 Channels?
- int16 format?
```

---

### **Problem: YAMNet lädt nicht**

```
python3 -m pip install --upgrade tensorflow tensorflow-hub
```

---

## 🎯 Schnellste Diagnostik

```bash
cd /Users/nora/Uni/Hackaburg26/vibrationbelt/debug

# 1. Ist ESP32 erreichbar?
ping -c 1 192.168.4.1 && echo "✅ Network OK" || echo "❌ Network FAIL"

# 2. Sendet UDP?
timeout 3 nc -l -u 4444 && echo "✅ UDP OK" || echo "❌ No UDP"

# 3. YAMNet installiert?
python3 -c "import tensorflow_hub" && echo "✅ YAMNet OK" || echo "❌ YAMNet FAIL"

# 4. Versuche Main Script
python3 siren_detector_esp32.py --duration 10
```

---

## 📞 Wenn nichts hilft

1. Prüfe ESP32 Firmware auf GitHub
2. Checke ob MicStream.start() in der Firmware aufgerufen wird
3. Prüfe ob UDP Port 4444 korrekt ist
4. Versuche mit DebugClient statt ESP32

---

**Status**: 🔴 **ESP32 Datenstream nicht aktiv**

Next: Bitte Resultat von `ping 192.168.4.1` posten!
