#!/bin/bash

# Schnelle Diagnose in einem Script

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo "🔍 QUICK DIAGNOSTICS - Why is siren_detector_esp32.py not working?"
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""

# Step 1: Netzwerk
echo "STEP 1: Netzwerk Check"
echo "─────────────────────────────────────────────────────────────────────────────────"

ping -c 1 10.8.5.177 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ ESP32 LEFT (10.8.5.177) is online"
else
    echo "❌ ESP32 LEFT (10.8.5.177) NOT reachable"
fi

ping -c 1 10.8.5.178 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ ESP32 RIGHT (10.8.5.178) is online"
else
    echo "❌ ESP32 RIGHT (10.8.5.178) NOT reachable"
fi

echo ""

# Step 2: UDP Stream
echo "STEP 2: UDP Stream Check (port 4444)"
echo "─────────────────────────────────────────────────────────────────────────────────"

echo "Testing UDP stream from ESP32s..."
timeout 3 python3 test_esp32_stream.py 2>&1 | tail -20

echo ""

# Step 3: Python
echo "STEP 3: Python Dependencies"
echo "─────────────────────────────────────────────────────────────────────────────────"

python3 -c "import tensorflow" 2>/dev/null && echo "✅ TensorFlow installed" || echo "❌ TensorFlow missing"
python3 -c "import tensorflow_hub" 2>/dev/null && echo "✅ TensorFlow Hub installed" || echo "❌ TensorFlow Hub missing"
python3 -c "import numpy" 2>/dev/null && echo "✅ NumPy installed" || echo "❌ NumPy missing"

echo ""

# Step 4: MicArray
echo "STEP 4: MicArray Test"
echo "─────────────────────────────────────────────────────────────────────────────────"

python3 test_micarray.py 2>&1 | tail -20

echo ""
echo "════════════════════════════════════════════════════════════════════════════════"
echo ""
