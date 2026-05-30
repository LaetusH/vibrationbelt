#!/usr/bin/env python3
"""
Motor Driver Interface - Hardware Abstraction Layer
Supports multiple control methods:
  - Serial (USB to motor driver board)
  - GPIO (Raspberry Pi direct control)
  - Network (ESP32/Arduino over HTTP/Serial)
"""

import serial
import time
import sys
from abc import ABC, abstractmethod
from enum import Enum


class MotorDriverType(Enum):
    """Supported motor driver types."""
    SERIAL_USB = "serial"      # Standard USB serial connection
    RASPBERRY_GPIO = "gpio"    # RPi GPIO pins
    ESP32_SERIAL = "esp_serial"  # ESP32 via Serial


# ============================================================================
# Base Motor Driver
# ============================================================================

class MotorDriver(ABC):
    """Abstract base for motor control."""
    
    def __init__(self, num_motors: int = 3):
        self.num_motors = num_motors
        self.motor_states = [0.0] * num_motors  # 0.0-1.0 intensity
    
    @abstractmethod
    def set_motor(self, motor_id: int, intensity: float):
        """Set motor intensity (0.0-1.0)."""
        pass
    
    @abstractmethod
    def stop_all(self):
        """Stop all motors."""
        pass
    
    def vibrate(self, motor_id: int, intensity: float, duration_ms: int):
        """Vibrate a motor for a duration."""
        if not (0 <= motor_id < self.num_motors):
            raise ValueError(f"Invalid motor ID: {motor_id}")
        if not (0.0 <= intensity <= 1.0):
            raise ValueError(f"Invalid intensity: {intensity}")
        
        self.set_motor(motor_id, intensity)
        time.sleep(duration_ms / 1000.0)
        self.set_motor(motor_id, 0.0)


# ============================================================================
# Serial USB Motor Driver
# ============================================================================

class SerialMotorDriver(MotorDriver):
    """Control motors via USB serial connection to motor driver board.
    
    Protocol (example - adapt to your hardware):
        Command format: M<motor_id>:<intensity>\n
        Example: M0:0.8\n (Motor 0 at 80% intensity)
        Stop: M0:0.0\n
    
    Common motor drivers:
        - PWM relay module (3-channel)
        - L298N H-Bridge (2-motor)
        - Custom Arduino/ESP32 driver
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200, num_motors: int = 3):
        super().__init__(num_motors)
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Wait for serial init
            print(f"✅ Serial motor driver connected on {port} ({baudrate} baud)")
        except serial.SerialException as e:
            print(f"❌ Failed to open serial port {port}: {e}")
            raise
    
    def set_motor(self, motor_id: int, intensity: float):
        """Send motor command over serial.
        
        Args:
            motor_id: 0, 1, 2 (which motor)
            intensity: 0.0-1.0 (PWM duty cycle)
        """
        if not self.ser:
            print("❌ Serial port not open")
            return
        
        if not (0 <= motor_id < self.num_motors):
            raise ValueError(f"Invalid motor ID: {motor_id}")
        if not (0.0 <= intensity <= 1.0):
            raise ValueError(f"Invalid intensity: {intensity}")
        
        self.motor_states[motor_id] = intensity
        
        # Convert to 0-255 PWM value
        pwm_value = int(intensity * 255)
        
        # Send command
        cmd = f"M{motor_id}:{pwm_value}\n"
        try:
            self.ser.write(cmd.encode())
            print(f"   → Motor {motor_id}: {pwm_value}/255 ({intensity:.0%})")
        except serial.SerialException as e:
            print(f"❌ Serial write failed: {e}")
    
    def stop_all(self):
        """Stop all motors."""
        for i in range(self.num_motors):
            self.set_motor(i, 0.0)
    
    def close(self):
        """Close serial connection."""
        if self.ser:
            self.stop_all()
            self.ser.close()
            print("✅ Serial connection closed")


# ============================================================================
# GPIO Motor Driver (Raspberry Pi)
# ============================================================================

class GPIOMotorDriver(MotorDriver):
    """Control motors via GPIO PWM on Raspberry Pi.
    
    Setup:
        - Install: pip install RPi.GPIO
        - Requires root/sudo
        - Wire motors to GPIO pins (with PWM driver)
    
    GPIO mapping example:
        Motor 0 (Left)   → GPIO 17
        Motor 1 (Right)  → GPIO 27
        Motor 2 (Center) → GPIO 22
    """
    
    def __init__(self, pins: list = None, frequency: int = 1000):
        super().__init__(num_motors=len(pins or [17, 27, 22]))
        
        if pins is None:
            pins = [17, 27, 22]  # Default RPi GPIO pins
        
        self.pins = pins
        self.frequency = frequency
        self.pwm = {}
        
        try:
            import RPi.GPIO as GPIO
            self.GPIO = GPIO
            
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            for i, pin in enumerate(pins):
                GPIO.setup(pin, GPIO.OUT)
                pwm = GPIO.PWM(pin, frequency)
                pwm.start(0)
                self.pwm[i] = pwm
            
            print(f"✅ GPIO motor driver initialized on pins {pins}")
        
        except ImportError:
            print("❌ RPi.GPIO not installed")
            print("   pip install RPi.GPIO")
            raise
    
    def set_motor(self, motor_id: int, intensity: float):
        """Set PWM duty cycle."""
        if not (0 <= motor_id < self.num_motors):
            raise ValueError(f"Invalid motor ID: {motor_id}")
        if not (0.0 <= intensity <= 1.0):
            raise ValueError(f"Invalid intensity: {intensity}")
        
        self.motor_states[motor_id] = intensity
        duty_cycle = intensity * 100  # 0-100%
        
        try:
            self.pwm[motor_id].ChangeDutyCycle(duty_cycle)
            print(f"   → Motor {motor_id} (GPIO {self.pins[motor_id]}): {duty_cycle:.0f}%")
        except Exception as e:
            print(f"❌ GPIO write failed: {e}")
    
    def stop_all(self):
        """Stop all motors."""
        for i in range(self.num_motors):
            self.set_motor(i, 0.0)
    
    def close(self):
        """Cleanup GPIO."""
        self.stop_all()
        self.GPIO.cleanup()
        print("✅ GPIO cleanup complete")


# ============================================================================
# Dummy/Testing Motor Driver
# ============================================================================

class DummyMotorDriver(MotorDriver):
    """Fake motor driver for testing without hardware."""
    
    def __init__(self, num_motors: int = 3):
        super().__init__(num_motors)
        print(f"⚠️  Dummy motor driver (no hardware)")
    
    def set_motor(self, motor_id: int, intensity: float):
        if not (0 <= motor_id < self.num_motors):
            raise ValueError(f"Invalid motor ID: {motor_id}")
        if not (0.0 <= intensity <= 1.0):
            raise ValueError(f"Invalid intensity: {intensity}")
        
        self.motor_states[motor_id] = intensity
        
        if intensity > 0:
            bar = "█" * int(intensity * 10) + "░" * (10 - int(intensity * 10))
            print(f"   → Motor {motor_id}: [{bar}] {intensity:.0%}")
        else:
            print(f"   → Motor {motor_id}: [off]")
    
    def stop_all(self):
        for i in range(self.num_motors):
            self.motor_states[i] = 0.0


# ============================================================================
# Factory Function
# ============================================================================

def create_motor_driver(driver_type: str = "dummy", **kwargs) -> MotorDriver:
    """Create appropriate motor driver.
    
    Args:
        driver_type: "dummy", "serial", "gpio"
        **kwargs: driver-specific options
    
    Returns:
        MotorDriver instance
    """
    if driver_type == "dummy":
        return DummyMotorDriver(kwargs.get("num_motors", 3))
    
    elif driver_type == "serial":
        return SerialMotorDriver(
            port=kwargs.get("port", "/dev/ttyUSB0"),
            baudrate=kwargs.get("baudrate", 115200),
            num_motors=kwargs.get("num_motors", 3)
        )
    
    elif driver_type == "gpio":
        return GPIOMotorDriver(
            pins=kwargs.get("pins", [17, 27, 22]),
            frequency=kwargs.get("frequency", 1000)
        )
    
    else:
        raise ValueError(f"Unknown driver type: {driver_type}")


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Test with dummy driver
    print("Testing motor driver...\n")
    
    driver = create_motor_driver("dummy")
    
    # Test each motor
    for i in range(3):
        print(f"\nMotor {i} tests:")
        for intensity in [0.3, 0.6, 1.0, 0.0]:
            driver.set_motor(i, intensity)
            time.sleep(0.5)
    
    print("\n✅ Motor driver test complete")
