#!/usr/bin/env python3
"""
Test: MicArray - Kann der Client die ESP32 Daten verarbeiten?
"""

import sys
from pathlib import Path

# Add client to path
sys.path.insert(0, str(Path(__file__).parent.parent / "client"))

from vibrationbelt import MicArray, MicSpec

def main():
    print("\n" + "="*80)
    print("🎤 MICARRAY TEST")
    print("="*80 + "\n")
    
    print("Connecting to ESP32s...")
    print("  Left:  192.168.4.1")
    print("  Right: 192.168.4.1\n")
    
    try:
        array = MicArray({
            "left": MicSpec("192.168.4.1"),
            "right": MicSpec("192.168.4.1"),
        }, buffer_seconds=1.0)
        
        print("✅ MicArray created\n")
        
        with array:
            print("✅ Connected to ESP32s\n")
            print("Waiting for audio windows (500ms chunks)...")
            print("Timeout: 5 seconds\n")
            print("-"*80 + "\n")
            
            windows_received = 0
            
            for i in range(10):  # Try 10 times
                window = array.latest_window(0.5)
                
                if window is not None:
                    windows_received += 1
                    print(f"✅ Window #{windows_received}:")
                    
                    for mic_name, audio_data in window.items():
                        if audio_data is not None:
                            print(f"   {mic_name}: {len(audio_data)} samples")
                        else:
                            print(f"   {mic_name}: None")
                    print()
                else:
                    print(f"❌ Window #{i+1}: None (no data)")
                    import time
                    time.sleep(0.1)
            
            print("="*80)
            print("\n📊 RESULTS:\n")
            
            if windows_received == 0:
                print("❌ NO AUDIO DATA RECEIVED")
                print("\nPossible causes:")
                print("  1. ESP32 not sending data (test_esp32_stream.py first!)")
                print("  2. Wrong ESP32 IPs")
                print("  3. Network connectivity issue")
                print("  4. MicArray buffer not filling")
                return False
            
            else:
                print(f"✅ Received {windows_received} audio windows")
                print("Good! Audio is flowing into MicArray!")
                print("Next: Run siren_detector_esp32.py")
                return True
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
