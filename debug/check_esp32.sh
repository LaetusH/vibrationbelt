#!/bin/bash

# Schneller Check ob ESP32 erreichbar ist

echo ""
echo "🔍 Checking ESP32 at 192.168.4.1..."
echo ""

if ping -c 1 192.168.4.1 > /dev/null 2>&1; then
    echo "✅ ESP32 is ONLINE at 192.168.4.1"
    echo ""
    echo "You can now run:"
    echo "  python3 siren_detector_esp32.py --duration 120"
    echo ""
else
    echo "❌ ESP32 NOT REACHABLE at 192.168.4.1"
    echo ""
    echo "Checklist:"
    echo "  [ ] ESP32 has power?"
    echo "  [ ] Mac connected to ESP32 WiFi? (EspAp or similar)"
    echo "  [ ] Try: ifconfig | grep 192.168.4"
    echo ""
fi
