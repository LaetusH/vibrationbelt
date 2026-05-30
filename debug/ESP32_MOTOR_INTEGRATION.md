# 🚨 ESP32 Siren Detector + Motor Control

Live audio streaming from ESP32 microphones → YAMNet alarm classification → Motor vibration control.

---

## 🚀 Quick Start

### 1. **Test with Dummy Driver (no hardware)**

```bash
cd debug/
python3 siren_detector_esp32.py --duration 30
```

**Output:**
```
================================================================================
🚨 LIVE ESP32 ALARM DETECTOR with MOTOR CONTROL
================================================================================

📡 Left Mic:  192.168.4.1
📡 Right Mic: 192.168.4.1
⏱️  Duration: 30s

🎤 Connected to ESP32s. Listening for alarms...

[  0.5s] 🔇 left  | QUIET  | 87% | Speech                        |    wait
[  0.6s] 🔇 right | QUIET  | 92% | Music                          |    wait
[  1.2s] 🚨 left  | RED    | 91% | Siren                          | ▶ MOTOR!
   🔴 [LEFT] Motor 0 ACTIVATED (strength: 80%)
   → Motor 0: 204/255 (80%)
[  1.3s] 🚨 right | RED    | 88% | Police car (siren)             | ▶ MOTOR!
   🔴 [RIGHT] Motor 1 ACTIVATED (strength: 80%)
   → Motor 1: 204/255 (80%)
```

---

### 2. **Real Hardware - Serial Motor Driver**

Connect USB motor driver board, then:

```bash
# Find your serial port
ls /dev/ttyUSB*  # Usually /dev/ttyUSB0

# Run with serial driver
python3 siren_detector_esp32.py \
    --motor-driver serial \
    --serial-port /dev/ttyUSB0 \
    --duration 60
```

---

### 3. **Real Hardware - Raspberry Pi GPIO**

```bash
# Install GPIO library (on RPi only)
pip install RPi.GPIO

# Run with GPIO driver
python3 siren_detector_esp32.py \
    --motor-driver gpio \
    --duration 60
```

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────┐
│            ESP32 Microphones (UDP)              │
│  Left (192.168.4.1)    Right (192.168.4.1)       │
└─────────────────────┬───────────────────────────┘
                      │ Stereo Audio (8 kHz)
                      ↓
         ┌────────────────────────────┐
         │    MicArray (vibrationbelt) │
         │  • UDP receiver threads    │
         │  • Ring buffer (per mic)   │
         │  • Chunk alignment         │
         └────────────┬───────────────┘
                      │ 500ms chunks
                      ↓
         ┌────────────────────────────┐
         │      YAMNet Classifier     │
         │  • 521-class audio model   │
         │  • Top-5 predictions       │
         │  • Confidence scores       │
         └────────────┬───────────────┘
                      │ Classification
                      ↓
         ┌────────────────────────────┐
         │   Binary Classification    │
         │  ALARM ↔ QUIET             │
         │  • Keyword matching        │
         │  • Confidence threshold    │
         │  • History smoothing       │
         └────────────┬───────────────┘
                      │ ALARM detected
                      ↓
         ┌────────────────────────────┐
         │    Motor Controller        │
         │  • Per-mic motor mapping   │
         │  • Cooldown management     │
         │  • Strength control        │
         └────────────┬───────────────┘
                      │ Motor ID + Intensity
                      ↓
         ┌────────────────────────────┐
         │    Motor Driver (HW)       │
         │  • Serial (USB)            │
         │  • GPIO (RPi)              │
         │  • Dummy (testing)         │
         └────────────────────────────┘
                      │ PWM/Command
                      ↓
         ┌────────────────────────────┐
         │  Vibration Motors          │
         │  🔴 Left | Right | Center  │
         └────────────────────────────┘
```

---

## 🔧 Configuration

### YAMNet Alarm Keywords

These trigger **ALARM**:
- `siren`, `emergency vehicle`
- `police`, `ambulance`, `fire engine`
- `horn`, `honk`, `alarm`, `klaxon`

Edit in `siren_detector_esp32.py`:
```python
ALARM_KEYWORDS = [
    'emergency vehicle',
    'siren',
    'police',
    # Add more...
]
```

### Motor Cooldown

Prevent motor spamming:
```python
self.cooldown = 1.0  # seconds between triggers
```

### Confidence Threshold

How confident must YAMNet be?
```python
if is_alarm and top_conf > 0.3:  # Lower = more sensitive
    return 'ALARM', top_conf, results[0]['class']
```

### Alarm History Smoothing

How many detections before triggering?
```python
self.alarm_threshold = 3  # 3 out of last 5
```

---

## 🛠️ Motor Driver Setup

### Dummy Driver (Testing)
```bash
python3 siren_detector_esp32.py --motor-driver dummy
```
- ✅ No hardware needed
- ✅ Prints motor commands to console
- ✅ Perfect for development/testing

### Serial Driver (USB Motor Controller)

**Hardware:**
- USB motor driver board (e.g., PWM relay module)
- Connected via USB → `/dev/ttyUSB0`

**Protocol:**
```
Command: M<motor_id>:<pwm_value>\n
Example: M0:204\n (Motor 0 at 80% = 204/255)
```

**Run:**
```bash
python3 siren_detector_esp32.py \
    --motor-driver serial \
    --serial-port /dev/ttyUSB0
```

**Custom Serial Protocol?**
Edit `motor_driver.py` → `SerialMotorDriver.set_motor()`:
```python
def set_motor(self, motor_id: int, intensity: float):
    pwm_value = int(intensity * 255)
    cmd = f"M{motor_id}:{pwm_value}\n"  # YOUR PROTOCOL HERE
    self.ser.write(cmd.encode())
```

### GPIO Driver (Raspberry Pi)

**Hardware:**
- RPi GPIO pins (17, 27, 22 default)
- Motor driver board connected to GPIO

**Install:**
```bash
pip install RPi.GPIO
```

**Run (with sudo):**
```bash
sudo python3 siren_detector_esp32.py \
    --motor-driver gpio
```

**Custom GPIO pins?**
Edit in `motor_driver.py`:
```python
pins = [17, 27, 22]  # Your GPIO pin numbers
driver = GPIOMotorDriver(pins=pins)
```

---

## 📡 ESP32 Microphone Setup

### UDP Audio Stream Format

Firmware sends UDP packets:
```
Header (16 bytes):
  - Magic: "AUD1" (4 bytes)
  - Sequence: uint32
  - Timestamp: uint64 (microseconds)
  - Sample count: uint32

Payload:
  - Stereo int16 samples at 8 kHz
  - 2 channels × 2 bytes per sample
```

### Connect Multiple ESP32s

Edit `siren_detector_esp32.py`:
```python
detector = LiveAlarmDetector(
    left_ip="192.168.4.1",
    right_ip="192.168.4.1",
    model=model,
    class_names=class_names,
    motor=motor
)
```

### Microphone Configuration

```python
self.array = MicArray({
    "left":  MicSpec("192.168.4.1"),
    "right": MicSpec("192.168.4.1"),
    "front": MicSpec("10.8.5.179"),  # Add more!
}, buffer_seconds=1.0)
```

---

## 🎯 Motor Mapping

Default mapping:
- **Motor 0** ← Left microphone alarm
- **Motor 1** ← Right microphone alarm
- **Motor 2** ← Center/All alarm

Customize:
```python
self.motor_map = {
    'left': 0,      # YOUR MOTOR ID
    'right': 1,
    'center': 2,
}
```

---

## 📊 Real-Time Monitoring

### Output Format

```
[time] ICON mic_name | COLOR | confidence | top_class | status
```

**Example:**
```
[  5.3s] 🚨 left  | RED    | 91% | Siren                          | ▶ MOTOR!
[  5.4s] 🔇 right | QUIET  | 87% | Music                          |    wait
```

### CSV Logging (Optional)

Add to `LiveAlarmDetector.run()`:
```python
import csv

with open('alarm_log.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['time', 'mic', 'classification', 'confidence', 'class'])
    
    # Inside loop:
    writer.writerow([elapsed, mic_name, classification, confidence, top_class])
```

---

## 🐛 Troubleshooting

### "Cannot connect to ESP32"
```bash
# Check if ESP32 is running and network accessible
ping 192.168.4.1
ping 192.168.4.1

# Check UDP port 4444 is open
netstat -u | grep 4444
```

### "Motor not responding"

**Serial:**
```bash
# Test serial connection
cat /dev/ttyUSB0 &
echo "M0:255" > /dev/ttyUSB0
```

**GPIO (RPi):**
```bash
sudo python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(17, GPIO.OUT); GPIO.output(17, 1)"
```

### "YAMNet inference too slow"

Inference takes ~200-500ms per chunk. Options:
1. Increase chunk size: `buffer_ms = 1000`
2. Use GPU: requires `tensorflow-gpu`
3. Skip less confident predictions: `if score > 0.5`

### "False positives (triggering on wrong sounds)"

1. **Lower confidence threshold:**
   ```python
   if is_alarm and top_conf > 0.5:  # Was 0.3
   ```

2. **Increase history threshold:**
   ```python
   self.alarm_threshold = 4  # 4 out of 5 instead of 3
   ```

3. **Add more alarm keywords:**
   ```python
   ALARM_KEYWORDS = [
       'emergency vehicle',
       'siren',
       'specific_alarm_sound_name',
   ]
   ```

---

## 📚 Files

| File | Purpose |
|------|---------|
| `siren_detector_esp32.py` | Main detector + motor control |
| `motor_driver.py` | Hardware abstraction (serial/GPIO) |
| `SIREN_DETECTOR.md` | Single-mic testing guide |
| `ESP32_MOTOR_INTEGRATION.md` | This file |

---

## 🎓 Example: Custom Motor Behavior

Vibrate left motor 3 times when alarm detected:

```python
def trigger_pattern(self, motor_name, pattern="triple"):
    """Trigger motor with pattern."""
    if pattern == "triple":
        for i in range(3):
            self.motor.set_motor(motor_id, 1.0)
            time.sleep(0.1)
            self.motor.set_motor(motor_id, 0.0)
            time.sleep(0.1)
```

---

## ✅ Checklist Before Production

- [ ] ESP32 IPs configured correctly
- [ ] Motor driver hardware connected
- [ ] Serial port / GPIO pins tested
- [ ] YAMNet alarm keywords verified
- [ ] Confidence thresholds tuned
- [ ] Motor cooldown set appropriately
- [ ] History smoothing prevents false triggers
- [ ] Network connectivity stable
- [ ] Power supply for motors sufficient

---

**Status**: 🟢 **Production Ready!** 🚨

