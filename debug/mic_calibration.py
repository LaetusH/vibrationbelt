#!/usr/bin/env python3
"""
Microphone Calibration Tool - Optimize audio input levels

Hilft dabei:
  1. Das beste Mikrofon auszuwählen
  2. Die optimale Sample-Rate zu finden
  3. Mikrofon-Level zu kalibrieren
  4. Echte Welt-Pegel zu messen
"""

import sys
import time
import numpy as np
from pathlib import Path

try:
    import sounddevice as sd
except ImportError:
    print("❌ Missing dependency: pip install sounddevice")
    sys.exit(1)


class MicCalibration:
    """Microphone calibration and optimization."""
    
    def __init__(self):
        self.sr = 16000
        self.chunk_duration = 2.0  # 2 second chunks
    
    def list_devices_detailed(self):
        """Show all audio devices with detailed info."""
        print("="*80)
        print("🎤 ALL AUDIO DEVICES")
        print("="*80)
        
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                marker = "📌 DEFAULT" if i == default_input else ""
                print(f"\n[{i}] {device['name']} {marker}")
                print(f"    Input Channels:  {device['max_input_channels']}")
                print(f"    Sample Rate:     {int(device['default_samplerate'])} Hz")
                print(f"    Latency (low):   {device['default_low_input_latency']*1000:.1f} ms")
                print(f"    Latency (high):  {device['default_high_input_latency']*1000:.1f} ms")
                
                input_devices.append(i)
        
        print("\n" + "="*80)
        return input_devices
    
    def test_device(self, device_id):
        """Test a specific device."""
        device_info = sd.query_devices(device_id)
        
        print(f"\n{'='*80}")
        print(f"🧪 TESTING DEVICE: {device_info['name']}")
        print(f"{'='*80}")
        
        print(f"\n📊 Recording 3 seconds of silence...")
        
        try:
            # Record silence
            samples = int(self.sr * 3)
            audio = sd.rec(samples, samplerate=self.sr, channels=1, dtype='float32', device=device_id)
            sd.wait()
            
            audio = audio.flatten()
            
            # Analyze
            noise_floor = float(np.sqrt(np.mean(audio**2)))
            max_amp = float(np.abs(audio).max())
            
            print(f"\n📈 Silence Analysis:")
            print(f"   Noise Floor (RMS):  {noise_floor:.6f}")
            print(f"   Peak Noise:         {max_amp:.6f}")
            
            # Assessment
            if noise_floor < 0.001:
                print(f"   ✅ Very quiet device")
            elif noise_floor < 0.01:
                print(f"   ✅ Good device")
            elif noise_floor < 0.05:
                print(f"   🟡 Noisy device")
            else:
                print(f"   ⚠️  Very noisy device")
            
            # Now record with sound
            print(f"\n🔊 Now speak/make noise for 3 seconds...")
            print(f"   (Spread it out - 1s quiet, 1s loud, 1s quiet)")
            
            time.sleep(1)
            
            audio_with_sound = sd.rec(samples, samplerate=self.sr, channels=1, dtype='float32', device=device_id)
            sd.wait()
            
            audio_with_sound = audio_with_sound.flatten()
            
            max_sound = float(np.abs(audio_with_sound).max())
            rms_sound = float(np.sqrt(np.mean(audio_with_sound**2)))
            
            print(f"\n📈 With Sound:")
            print(f"   Peak Amplitude:     {max_sound:.4f}")
            print(f"   RMS Level:          {rms_sound:.4f}")
            print(f"   Dynamic Range:      {max_sound / max(noise_floor, 0.0001):.1f}x")
            
            # Assessment
            if max_sound < 0.05:
                print(f"\n   ⚠️  PROBLEM: Signal is TOO QUIET")
                print(f"      Solutions:")
                print(f"      1. Increase system microphone level")
                print(f"      2. Speak louder or get closer to mic")
                print(f"      3. Use external microphone")
                return False
            
            elif max_sound < 0.1:
                print(f"\n   🟡 Signal is quiet but usable")
                print(f"      OK for speech, marginal for sirens")
            
            elif max_sound < 0.3:
                print(f"\n   ✅ Signal is GOOD")
                print(f"      Ideal for audio processing")
            
            elif max_sound < 0.7:
                print(f"\n   ✅ Signal is VERY GOOD")
                print(f"      Plenty of headroom")
            
            else:
                print(f"\n   ⚠️  Signal might be clipping")
                print(f"      Reduce microphone level")
                return False
            
            return True
        
        except Exception as e:
            print(f"❌ Error testing device: {e}")
            return False
    
    def find_best_device(self):
        """Automatically find best microphone."""
        print("="*80)
        print("🔍 FINDING BEST MICROPHONE")
        print("="*80)
        
        devices = sd.query_devices()
        best_device = None
        best_score = -1
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                # Score based on channels and latency
                score = device['max_input_channels'] / (1 + device['default_low_input_latency'])
                
                print(f"[{i}] {device['name']:30} Score: {score:.2f}")
                
                if score > best_score:
                    best_score = score
                    best_device = i
        
        print(f"\n✅ Recommended: Device [{best_device}]")
        return best_device
    
    def run_calibration(self):
        """Run full calibration wizard."""
        print("\n" + "="*80)
        print("🎙️  MICROPHONE CALIBRATION WIZARD")
        print("="*80)
        
        # Step 1: List devices
        print("\n📋 Step 1: List available devices")
        input_devices = self.list_devices_detailed()
        
        if not input_devices:
            print("❌ No input devices found!")
            return
        
        # Step 2: Find best device
        print("\n📍 Step 2: Find best device")
        best = self.find_best_device()
        
        # Step 3: Test best device
        print(f"\n🧪 Step 3: Test device {best}")
        success = self.test_device(best)
        
        # Step 4: Recommendations
        print("\n" + "="*80)
        print("💡 RECOMMENDATIONS")
        print("="*80)
        
        if success:
            print(f"\n✅ Device [{best}] is working well!")
            print(f"\n   Use this in your code:")
            print(f"   python3 live_mic_test.py --device {best}")
            print(f"   python3 run_live_analysis_yamnet.py --simulate")
        else:
            print(f"\n⚠️  Device [{best}] has issues")
            print(f"\n   Try these devices instead:")
            for dev_id in input_devices[1:]:
                print(f"   - Device [{dev_id}]")
        
        print("\n" + "="*80 + "\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Microphone calibration tool")
    parser.add_argument("--test", type=int, help="Test specific device ID")
    parser.add_argument("--list", action="store_true", help="List devices")
    
    args = parser.parse_args()
    
    calibrator = MicCalibration()
    
    if args.list:
        calibrator.list_devices_detailed()
    elif args.test is not None:
        calibrator.test_device(args.test)
    else:
        calibrator.run_calibration()


if __name__ == "__main__":
    main()
