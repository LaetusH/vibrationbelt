#!/usr/bin/env python3
"""
Live Audio Analysis — Connect ESP32 belt-mic to alarm+anomaly detection.

Usage:
    python live_analysis.py <esp32-ip>
    
Example:
    python live_analysis.py 10.8.5.177
    
    # Then you'll see:
    #   🎤 Connected to 10.8.5.177:4444
    #   ⏳ Calibrating baseline... (10s)
    #   🎙️ Listening for alarms and anomalies...
    #
    #   [16:32:45] 🚨 ALARM (siren) - Confidence: 89% SNR: 18.5dB
    #   [16:32:51] ⚠️ LOUD_SOUND (scream) - Confidence: 76% SNR: 12.3dB
"""

import sys
import logging
import time
from pathlib import Path
from datetime import datetime

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "processing"))

import vibrationbelt as vb
from audio_analyzer.stream_processor import (
    MultiStreamAnalyzer,
    DetectionType,
)


def format_detection(detection):
    """Pretty-print a detection event."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    icon = "🚨" if detection.type == DetectionType.ALARM else "⚠️"
    det_type = detection.type.value
    
    msg = (
        f"[{timestamp}] {icon} {det_type.upper():12} "
        f"({detection.detector_type:15}) - "
        f"Confidence: {detection.confidence:3.0%} "
        f"SNR: {detection.snr_db:5.1f}dB"
    )
    
    return msg


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Live alarm+anomaly detection from ESP32 belt-mic"
    )
    parser.add_argument("esp32_ip", help="ESP32 IP address (e.g., 10.8.5.177)")
    parser.add_argument(
        "--port",
        type=int,
        default=4444,
        help="UDP port (default: 4444)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s: %(message)s",
    )
    
    log = logging.getLogger("live_analysis")
    
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║    Live Audio Analysis — Alarm + Anomaly Detection       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    
    # Connect to ESP32
    print(f"🎤 Connecting to ESP32 @ {args.esp32_ip}:{args.port}...")
    
    try:
        mic_stream = vb.MicStream(args.esp32_ip, port=args.port)
        mic_stream.start()
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return 1
    
    # Setup analyzer
    analyzer = MultiStreamAnalyzer()
    processor = analyzer.add_stream("mic_0", sr=vb.SAMPLE_RATE)
    
    print(f"✓ Connected to {args.esp32_ip}:{ args.port}")
    print()
    print("⏳ Calibrating baseline... (learning first ~10 seconds)")
    print("   (Keep it quiet!)")
    print()
    
    # Feed chunks from MicStream to analyzer (background thread)
    analyzer.connect_source("mic_0", mic_stream, name="esp32-reader")
    
    print("🎙️ Listening for alarms and anomalies...")
    print("   Press Ctrl-C to stop")
    print()
    print("-" * 70)
    print()
    
    try:
        # Main detection loop
        for detection in analyzer.iter_detections(timeout=1.0):
            if not processor.is_calibrated:
                # Still calibrating
                continue
            
            # Print detection
            msg = format_detection(detection)
            print(msg)
            
            # Log to file optionally
            log.info(msg)
    
    except KeyboardInterrupt:
        print()
        print()
        print("✓ Stopped by user")
    
    finally:
        print()
        print("Cleaning up...")
        analyzer.close()
        mic_stream.close()
        print("✓ Closed")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
