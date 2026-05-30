#!/usr/bin/env python3
"""
Live ESP32 Siren Detector with Motor Control
Receives stereo audio from ESP32 nodes via UDP, runs YAMNet classification,
and triggers the corresponding motor when ALARM is detected.

Usage:
    python3 siren_detector_esp32.py --left 192.168.4.1 --right 192.168.4.1
    python3 siren_detector_esp32.py --motor-driver serial --serial-port /dev/ttyUSB0

Options:
    --left IP           Left microphone ESP32 IP (default: 192.168.4.1)
    --right IP          Right microphone ESP32 IP (default: 192.168.4.1)
    --duration          Test duration in seconds (default: 60)
    --motor-driver      Motor driver: dummy, serial, gpio (default: dummy)
    --serial-port       Serial port for motor driver (default: /dev/ttyUSB0)
"""

import sys
import os
import csv
import time
import argparse
import urllib.request
import numpy as np
import threading
import queue
from pathlib import Path
from collections import deque

try:
    import tensorflow as tf
    import tensorflow_hub as hub
    # Add client to path
    sys.path.insert(0, str(Path(__file__).parent.parent / "client"))
    from vibrationbelt import MicArray, MicSpec
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("   pip install tensorflow tensorflow-hub sounddevice numpy")
    sys.exit(1)


# ============================================================================
# YAMNet Setup
# ============================================================================

def setup_yamnet():
    """Setup YAMNet model and load class labels."""
    class_map_path = 'yamnet_class_map.csv'
    if not os.path.exists(class_map_path):
        print("📥 Downloading YAMNet class map...")
        urllib.request.urlretrieve(
            'https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv',
            class_map_path)

    class_names = []
    with open(class_map_path) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            class_names.append(row['display_name'])

    print("📥 Loading YAMNet model...")
    model = hub.load('https://tfhub.dev/google/yamnet/1')
    print(f"✅ Model loaded! Total classes: {len(class_names)}\n")
    
    return model, class_names


# ============================================================================
# Alarm Classification
# ============================================================================

ALARM_KEYWORDS = [
    'emergency vehicle',
    'siren',
    'police',
    'ambulance',
    'fire engine',
    'fire truck',
    'horn',
    'honk',
    'alarm',
    'klaxon',
]

QUIET_KEYWORDS = [
    'speech',
    'music',
    'silence',
    'ambient',
    'wind',
    'rain',
    'traffic',
    'crowd',
    'applause',
]


def classify_alarm_or_quiet(results):
    """Binary classification: ALARM or QUIET."""
    if not results:
        return 'QUIET', 0.0, 'No predictions'
    
    top_class = results[0]['class'].lower()
    top_conf = results[0]['confidence']
    
    is_alarm = any(keyword in top_class for keyword in ALARM_KEYWORDS)
    
    if is_alarm and top_conf > 0.3:
        return 'ALARM', top_conf, results[0]['class']
    else:
        return 'QUIET', 1.0 - top_conf, results[0]['class']


# ============================================================================
# Motor Control
# ============================================================================

class MotorController:
    """Control vibration motors based on alarm detection."""
    
    def __init__(self, driver_type="dummy", **driver_kwargs):
        """Initialize motor controller.
        
        Args:
            driver_type: "dummy", "serial", "gpio"
            **driver_kwargs: Driver-specific options
        """
        from motor_driver import create_motor_driver
        
        self.driver = create_motor_driver(driver_type, **driver_kwargs)
        
        # Motor mapping
        self.motor_map = {
            'left': 0,
            'right': 1,
            'center': 2,
        }
        
        self.vibration_duration_ms = 500  # ms
        self.cooldown = 1.0  # seconds between vibrations
        self.last_alarm = {}  # Per-motor last trigger time
        
        print(f"✅ Motor controller initialized\n")
    
    def trigger(self, motor_name, strength=0.8):
        """Trigger a motor to vibrate.
        
        Args:
            motor_name: 'left', 'right', 'center', or 'all'
            strength: 0.0-1.0 vibration intensity
        """
        now = time.monotonic()
        
        if motor_name == 'all':
            targets = list(self.motor_map.keys())
        else:
            targets = [motor_name] if motor_name in self.motor_map else []
        
        for name in targets:
            motor_id = self.motor_map[name]
            last = self.last_alarm.get(name, 0)
            
            # Cooldown check
            if now - last < self.cooldown:
                continue
            
            self.last_alarm[name] = now
            
            print(f"   🔴 [{name.upper()}] Motor {motor_id} ACTIVATED (strength: {strength:.0%})")
            self.driver.set_motor(motor_id, strength)
    
    def stop_all(self):
        """Stop all motors."""
        self.driver.stop_all()


# ============================================================================
# Live Audio Processing
# ============================================================================

class LiveAlarmDetector:
    """Monitor ESP32 microphones and detect alarms."""
    
    def __init__(self, left_ip, right_ip, model, class_names, motor_controller):
        self.left_ip = left_ip
        self.right_ip = right_ip
        self.model = model
        self.class_names = class_names
        self.motor = motor_controller
        
        # Audio buffer
        self.buffer_ms = 500  # Process 500ms chunks
        self.sample_rate = 8000  # ESP32 stream rate
        self.buffer_samples = int(self.sample_rate * self.buffer_ms / 1000)
        
        # Detection history (for smoothing false positives)
        self.alarm_history = deque(maxlen=5)
        self.alarm_threshold = 3  # 3 out of last 5 must be ALARM
        
        # Setup MicArray
        self.array = MicArray({
            "left": MicSpec(left_ip),
            "right": MicSpec(right_ip),
        }, buffer_seconds=1.0)
    
    def run(self, duration_sec=60):
        """Run the detector."""
        print("="*80)
        print("🚨 LIVE ESP32 ALARM DETECTOR with MOTOR CONTROL")
        print("="*80)
        print(f"\n📡 Left Mic:  {self.left_ip}")
        print(f"📡 Right Mic: {self.right_ip}")
        print(f"⏱️  Duration: {duration_sec}s\n")
        
        start_time = time.monotonic()
        chunk_num = 0
        
        try:
            with self.array:
                print("🎤 Connected to ESP32s. Listening for alarms...\n")
                
                while time.monotonic() - start_time < duration_sec:
                    # Get latest audio window from both mics
                    window = self.array.latest_window(self.buffer_ms / 1000.0)
                    
                    if window is None:
                        time.sleep(0.05)
                        continue
                    
                    chunk_num += 1
                    elapsed = time.monotonic() - start_time
                    
                    # Process left and right channels
                    for mic_name, audio_data in window.items():
                        if audio_data is None or len(audio_data) == 0:
                            continue
                        
                        # Convert int16 to float for YAMNet
                        audio_float = audio_data.astype(np.float32) / 32768.0
                        
                        # Run inference
                        try:
                            scores, _, _ = self.model(audio_float)
                            scores_np = scores.numpy()
                            
                            # Get top-5
                            top_indices = np.argsort(scores_np.mean(axis=0))[-5:][::-1]
                            results = []
                            for idx in top_indices:
                                score = scores_np.mean(axis=0)[idx]
                                if score > 0.1:
                                    results.append({
                                        'class': self.class_names[idx],
                                        'confidence': float(score)
                                    })
                            
                            # Classify
                            classification, confidence, top_class = classify_alarm_or_quiet(results)
                            
                            # Track history for smoothing
                            self.alarm_history.append(classification == 'ALARM')
                            
                            # Decide if we should trigger motor
                            alarm_count = sum(self.alarm_history)
                            should_alarm = alarm_count >= self.alarm_threshold
                            
                            # Print status
                            if classification == 'ALARM':
                                icon = "🚨"
                                color = "RED"
                            else:
                                icon = "🔇"
                                color = "QUIET"
                            
                            status = "▶ MOTOR!" if should_alarm else "   wait"
                            print(f"[{elapsed:6.1f}s] {icon} {mic_name.upper():5} | {color:6} | {confidence:.2%} | {top_class:<30} | {status}")
                            
                            # Trigger motor if we have consistent alarms
                            if should_alarm and len(self.alarm_history) >= 3:
                                self.motor.trigger(mic_name, strength=0.8)
                        
                        except Exception as e:
                            print(f"   ❌ Inference error: {e}")
                    
                    time.sleep(0.01)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped by user")
        
        print("="*80 + "\n")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Live ESP32 Siren Detector with Motor Control"
    )
    parser.add_argument(
        "--left",
        default="192.168.4.1",
        help="Left microphone ESP32 IP (default: 192.168.4.1)"
    )
    parser.add_argument(
        "--right",
        default="192.168.4.1",
        help="Right microphone ESP32 IP (default: 192.168.4.1)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--motor-driver",
        default="dummy",
        choices=["dummy", "serial", "gpio"],
        help="Motor driver type (default: dummy for testing)"
    )
    parser.add_argument(
        "--serial-port",
        default="/dev/ttyUSB0",
        help="Serial port for motor driver (default: /dev/ttyUSB0)"
    )
    
    args = parser.parse_args()
    
    # Setup
    model, class_names = setup_yamnet()
    
    # Setup motor driver with appropriate type
    motor_kwargs = {}
    if args.motor_driver == "serial":
        motor_kwargs["port"] = args.serial_port
    
    motor = MotorController(driver_type=args.motor_driver, **motor_kwargs)
    detector = LiveAlarmDetector(args.left, args.right, model, class_names, motor)
    
    # Run
    try:
        detector.run(duration_sec=args.duration)
    finally:
        motor.stop_all()


if __name__ == "__main__":
    main()
