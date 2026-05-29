#!/usr/bin/env python3
"""Generate synthetic test audio files (fire siren, smoke detector, etc)."""

import numpy as np
import soundfile as sf
from pathlib import Path

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / "test_audio"
OUTPUT_DIR.mkdir(exist_ok=True)


def generate_fire_siren():
    """Generate fire siren (pulsing 1000 Hz, 2 Hz pulse rate)."""
    sr = 16000
    duration = 3.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    # Pulsing envelope (2 Hz)
    pulse = np.sin(2 * np.pi * 2 * t)
    pulse = (pulse + 1) / 2  # Convert to 0-1
    
    # Main tone: 1000 Hz
    siren = 0.6 * pulse * np.sin(2 * np.pi * 1000 * t)
    
    # Add some noise (real sirens aren't perfect sine waves)
    noise = 0.05 * np.random.randn(len(siren))
    siren = siren + noise
    
    # Normalize
    siren = 0.9 * siren / np.max(np.abs(siren))
    
    filepath = OUTPUT_DIR / "fire_siren.wav"
    sf.write(str(filepath), siren.astype(np.float32), sr)
    print(f"✓ {filepath}")


def generate_smoke_detector():
    """Generate smoke detector (chirping 3 kHz)."""
    sr = 16000
    duration = 4.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    # Chirp envelope: 3 Hz (fast chirps)
    chirp_env = (np.sin(2 * np.pi * 3 * t) > 0.5).astype(float)
    
    # Main tone: 3000 Hz
    smoke = 0.6 * chirp_env * np.sin(2 * np.pi * 3000 * t)
    
    # Add harmonics (smoke detectors have complex tones)
    smoke += 0.2 * chirp_env * np.sin(2 * np.pi * 6000 * t)
    
    # Normalize
    smoke = 0.9 * smoke / np.max(np.abs(smoke))
    
    filepath = OUTPUT_DIR / "smoke_detector.wav"
    sf.write(str(filepath), smoke.astype(np.float32), sr)
    print(f"✓ {filepath}")


def generate_alarm_beep():
    """Generate generic alarm beep (repeating 1200 Hz beep)."""
    sr = 16000
    duration = 2.0
    
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    # Beep envelope: 4 Hz (fast beeping)
    beep_env = (np.sin(2 * np.pi * 4 * t) > 0.5).astype(float)
    
    # Main tone: 1200 Hz
    beep = 0.7 * beep_env * np.sin(2 * np.pi * 1200 * t)
    
    # Normalize
    beep = 0.9 * beep / np.max(np.abs(beep))
    
    filepath = OUTPUT_DIR / "alarm_beep.wav"
    sf.write(str(filepath), beep.astype(np.float32), sr)
    print(f"✓ {filepath}")


def generate_white_noise():
    """Generate white noise (negative test case)."""
    sr = 16000
    duration = 3.0
    
    noise = 0.1 * np.random.randn(int(sr * duration))
    
    filepath = OUTPUT_DIR / "white_noise.wav"
    sf.write(str(filepath), noise.astype(np.float32), sr)
    print(f"✓ {filepath}")


def generate_silent():
    """Generate silent audio (negative test case)."""
    sr = 16000
    duration = 3.0
    
    silent = np.zeros(int(sr * duration))
    
    filepath = OUTPUT_DIR / "silent.wav"
    sf.write(str(filepath), silent.astype(np.float32), sr)
    print(f"✓ {filepath}")


def main():
    """Generate all test files."""
    print(f"Generating test audio files in {OUTPUT_DIR}\n")
    
    generate_fire_siren()
    generate_smoke_detector()
    generate_alarm_beep()
    generate_white_noise()
    generate_silent()
    
    print(f"\n✓ Generated 5 test audio files in {OUTPUT_DIR}")
    print("\nRun analysis:")
    print(f"  python examples/analyze_file.py {OUTPUT_DIR}/fire_siren.wav")
    print(f"  python examples/batch_detect.py {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
