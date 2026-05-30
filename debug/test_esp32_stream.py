#!/usr/bin/env python3
"""
Test: Sind die ESP32s online und senden Audio?
Lauscht auf UDP Port 4444 und zeigt eingehende Pakete.
"""

import socket
import struct
import sys

def main():
    print("\n" + "="*80)
    print("📡 ESP32 UDP STREAM TEST")
    print("="*80 + "\n")
    
    # Socket erstellen
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 4444))
    sock.settimeout(10)  # 10 Sekunden Timeout
    
    print("🎤 Listening on UDP:4444 for ESP32 audio packets...")
    print("⏱️  Timeout: 10 seconds\n")
    print("Expected: Pakete von 192.168.4.1 und/oder 192.168.4.1")
    print("-"*80 + "\n")
    
    packet_count = 0
    ips_seen = set()
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(2048)
                packet_count += 1
                ip = addr[0]
                ips_seen.add(ip)
                
                # Parse header if possible
                if len(data) >= 16:
                    try:
                        magic, seq, ts, nsamp = struct.unpack('<4sIQI', data[:16])
                        print(f"✅ Packet #{packet_count}")
                        print(f"   From: {ip}:{addr[1]}")
                        print(f"   Size: {len(data)} bytes")
                        print(f"   Magic: {magic}")
                        print(f"   Seq: {seq}")
                        print(f"   Samples: {nsamp}")
                        print()
                    except:
                        print(f"✅ Packet #{packet_count} from {ip} ({len(data)} bytes)")
                        print()
                else:
                    print(f"✅ Packet #{packet_count} from {ip} ({len(data)} bytes - too small)")
                    print()
            
            except socket.timeout:
                break
    
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user")
    
    finally:
        sock.close()
    
    # Summary
    print("="*80)
    print("\n📊 RESULTS:\n")
    
    if packet_count == 0:
        print("❌ NO PACKETS RECEIVED")
        print("\nPossible causes:")
        print("  1. ESP32 firmware not running")
        print("  2. ESP32 not sending on port 4444")
        print("  3. UDP blocked by firewall")
        print("  4. ESP32 not online (ping 192.168.4.1)")
        print("\nNext step: Check ESP32 firmware!")
        return False
    
    else:
        print(f"✅ Received {packet_count} packets")
        print(f"✅ From: {', '.join(sorted(ips_seen))}")
        print("\nGood! ESP32 is streaming!")
        print("Next: Run test_micarray.py")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
