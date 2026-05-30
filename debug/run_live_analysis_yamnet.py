#!/usr/bin/env python3
"""
Live Analysis with YAMNet - Classify audio events using Google's audio model

Uses YAMNet to detect:
  - Sirens (Feuerwehr, Krankenwagen, Polizei)
  - Vehicle horns
  - Emergency vehicle sounds
  - Other relevant events

Ignores:
  - Music, speech, ambient noise
  - Applause, laughter, crowd noise
  - Other non-relevant sounds

Usage:
    python3 run_live_analysis_yamnet.py [--url http://localhost:5262] [--interval 100]
"""

import sys
import time
import argparse
from pathlib import Path
from collections import deque
from typing import Dict, List, Tuple

import numpy as np

try:
    import tensorflow as tf
    import tensorflow_hub as hub
except ImportError:
    print("❌ Missing dependencies:")
    print("   pip install tensorflow tensorflow-hub")
    sys.exit(1)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from analysis_engine.motor_mapper import MotorMapper

# ============================================================================
# YAMNet CLASS MAPPING - Alarm-Relevant Classes Only
# ============================================================================

# YAMNet class indices for relevant sounds
YAMNET_ALARM_CLASSES = {
    # Sirens & Emergency Vehicles
    399: "🚨 Siren",                      # Siren
    400: "🚓 Police Car Siren",            # Police car siren  
    401: "🚑 Ambulance Siren",             # Ambulance siren
    402: "🚒 Fire Engine Siren",           # Fire engine/Truck siren
    
    # Vehicle Horns
    377: "🚙 Vehicle Horn",                # Vehicle horn, car horn, honking
    378: "🚗 Beep",                        # Beep, bleep
    
    # Other Vehicles
    379: "🏎️ Race Car",                   # Race car, accelerating
    383: "🚛 Truck",                       # Truck
}

# Classes to IGNORE (return false alarm)
YAMNET_IGNORE_CLASSES = {
    # Speech & Vocalizations
    0: "Speech",
    1: "Child speech, kid speaking",
    # Music
    68: "Music",
    69: "Musical instrument",
    # Crowd & Applause
    117: "Applause",
    118: "Crowd",
    119: "Cheering",
    # Environmental
    146: "Wind",
    147: "Rain",
    148: "Thunderstorm",
}

# Map alarm types for display
ALARM_TYPE_NAMES = {
    399: "🚨 Siren",
    400: "🚓 Polizei",
    401: "🚑 Krankenwagen",
    402: "🚒 Feuerwehr",
    377: "🚙 Hupe",
}


class YAMNetAnalyzer:
    """Analyze audio using Google's YAMNet model."""
    
    def __init__(self, interval_ms: int = 100, confidence_threshold: float = 0.3):
        self.interval_s = interval_ms / 1000.0
        self.confidence_threshold = confidence_threshold
        
        # Load YAMNet model
        print("📥 Loading YAMNet model from TensorFlow Hub...")
        self.model = hub.load('https://www.kaggle.com/models/google/yamnet/TensorFlow2/yamnet/1')
        print("✅ YAMNet model loaded")
        
        # History for smoothing
        self.doa_history = deque(maxlen=5)
        self.confidence_history = deque(maxlen=5)
        self.alarm_history = deque(maxlen=3)
        self.alarm_type_history = deque(maxlen=5)
        
        # Stats
        self.total_chunks = 0
        self.alarms_detected = 0
        self.alarm_type_counts = {}
        self.start_time = time.time()
    
    def analyze_chunk(self, audio_mic1: np.ndarray, audio_mic2: np.ndarray = None) -> Dict:
        """
        Analyze audio chunk with YAMNet.
        
        Args:
            audio_mic1: Primary mic audio (float32, 16kHz)
            audio_mic2: Secondary mic audio for DOA (optional)
            
        Returns:
            {
                'is_alarm': bool,
                'alarm_confidence': float (0-1),
                'alarm_class': int,
                'alarm_name': str,
                'doa_degrees': float or None,
            }
        """
        result = {
            'is_alarm': False,
            'alarm_confidence': 0.0,
            'alarm_class': None,
            'alarm_name': 'Unknown',
            'doa_degrees': None,
        }
        
        # Use mono audio (mix both channels if available)
        if audio_mic2 is not None:
            # Simple averaging for mono
            audio = (audio_mic1 + audio_mic2) / 2
        else:
            audio = audio_mic1
        
        # Ensure correct type and range
        audio = np.clip(audio.astype(np.float32), -1.0, 1.0)
        
        try:
            # YAMNet inference
            scores, embeddings, spectrogram = self.model(audio)
            
            # Get top predictions
            top_class_idx = int(np.argmax(scores[0].numpy()))
            top_confidence = float(scores[0].numpy()[top_class_idx])
            
            # Check if this is an alarm class
            if top_class_idx in YAMNET_ALARM_CLASSES:
                result['is_alarm'] = True
                result['alarm_confidence'] = top_confidence
                result['alarm_class'] = top_class_idx
                result['alarm_name'] = YAMNET_ALARM_CLASSES[top_class_idx]
            
            # Check if it's in ignore list (overrides alarm detection)
            elif top_class_idx in YAMNET_IGNORE_CLASSES:
                result['is_alarm'] = False
                result['alarm_confidence'] = 0.0
            
            # Anything else below confidence threshold
            elif top_confidence < self.confidence_threshold:
                result['is_alarm'] = False
                result['alarm_confidence'] = 0.0
            else:
                # Unknown sound above threshold - be cautious
                result['is_alarm'] = False
                result['alarm_confidence'] = 0.0
        
        except Exception as e:
            print(f"❌ YAMNet analysis error: {e}")
            result['is_alarm'] = False
            result['alarm_confidence'] = 0.0
        
        return result
    
    def run(self, audio_data_generator):
        """
        Main loop: continuously analyze audio chunks.
        
        Args:
            audio_data_generator: yields (mic1_audio, mic2_audio) tuples
        """
        print("\n" + "="*90)
        print("🎤 LIVE ANALYSIS ENGINE (YAMNet)")
        print("="*90)
        print("Listening for alarms using Google YAMNet...")
        print("Relevant: Sirens | Horns | Emergency Vehicles")
        print("Ignored:  Music | Speech | Ambient Noise\n")
        
        try:
            for mic1_audio, mic2_audio in audio_data_generator:
                # Analyze with YAMNet
                result = self.analyze_chunk(mic1_audio, mic2_audio)
                
                # Update history
                self.total_chunks += 1
                self.confidence_history.append(result['alarm_confidence'])
                self.alarm_history.append(result['is_alarm'])
                
                if result['is_alarm']:
                    self.alarms_detected += 1
                    alarm_class = result['alarm_class']
                    self.alarm_type_history.append(alarm_class)
                    
                    if alarm_class not in self.alarm_type_counts:
                        self.alarm_type_counts[alarm_class] = 0
                    self.alarm_type_counts[alarm_class] += 1
                
                # Display
                self._display_result(result)
                
                # Sleep for interval
                time.sleep(self.interval_s)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopped by user")
        except Exception as e:
            print(f"\n❌ ERROR: {e}", file=sys.stderr)
            raise
        finally:
            self._print_stats()
    
    def _display_result(self, result):
        """Pretty-print analysis result."""
        
        # Smoothed values
        conf_smooth = np.mean(self.confidence_history) if self.confidence_history else 0
        alarm_consensus = sum(self.alarm_history) > len(self.alarm_history) / 2
        
        # Alarm indicator & type
        if alarm_consensus and self.alarm_type_history:
            # Most common alarm type in recent history
            most_common_class = max(set(self.alarm_type_history),
                                    key=list(self.alarm_type_history).count)
            alarm_emoji = YAMNET_ALARM_CLASSES.get(most_common_class, "❓")
            alarm_str = f"🚨 {alarm_emoji}"
        else:
            alarm_str = "  🔇 quiet"
        
        # Confidence bar
        bar_len = 20
        filled = int(conf_smooth * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        # Current detection info
        if result['is_alarm']:
            current_class_name = YAMNET_ALARM_CLASSES.get(result['alarm_class'], "?")
            current_conf = f" ({result['alarm_confidence']*100:.0f}%)"
        else:
            current_class_name = ""
            current_conf = ""
        
        # Print
        elapsed = time.time() - self.start_time
        elapsed_min = int(elapsed // 60)
        elapsed_sec = int(elapsed % 60)
        
        print(f"[{elapsed_min:02d}:{elapsed_sec:02d}] "
              f"[{bar}] {conf_smooth*100:5.1f}% | "
              f"{alarm_str:25} | "
              f"{current_class_name}{current_conf}")
    
    def _print_stats(self):
        """Print final statistics."""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*90)
        print("📊 SESSION STATISTICS")
        print("="*90)
        print(f"Duration: {elapsed/60:.1f} minutes")
        print(f"Chunks analyzed: {self.total_chunks}")
        print(f"Alarms detected: {self.alarms_detected}")
        if self.total_chunks > 0:
            print(f"Alarm rate: {self.alarms_detected/self.total_chunks*100:.1f}%")
        
        # Alarm type breakdown
        if self.alarms_detected > 0:
            print(f"\n🚨 Alarm Types Detected:")
            for alarm_class, count in sorted(self.alarm_type_counts.items()):
                name = YAMNET_ALARM_CLASSES.get(alarm_class, "Unknown")
                pct = (count / self.alarms_detected) * 100
                print(f"   {name}: {count} ({pct:.1f}%)")
        
        print("="*90 + "\n")


def simulate_audio_data(duration_s: float = 30):
    """
    Simulate dual-mic audio data for testing.
    
    Yields: (mic1_audio, mic2_audio) tuples
    """
    sample_rate = 16000
    chunk_size = sample_rate // 10  # 100ms chunks
    
    elapsed = 0
    while elapsed < duration_s:
        # Simulate alarm-like sound (sine sweep 2-4 kHz)
        t = np.arange(chunk_size) / sample_rate
        f_start, f_end = 2000, 4000
        freq = f_start + (f_end - f_start) * (elapsed / duration_s)
        
        mic1 = 0.3 * np.sin(2 * np.pi * freq * t).astype(np.float32)
        mic2 = 0.25 * np.sin(2 * np.pi * freq * t).astype(np.float32)
        
        yield mic1, mic2
        
        elapsed += chunk_size / sample_rate
        time.sleep(0.01)


def fetch_audio_from_debugclient(url: str = "http://localhost:5262", interval_ms: int = 100):
    """
    Connect to DebugClient API and fetch audio chunks.
    
    Yields: (mic1_audio, mic2_audio) tuples
    """
    import requests
    
    print(f"📻 Connecting to DebugClient at {url}...")
    
    chunk_size = int(16000 * interval_ms / 1000)
    print(f"   Chunk size: {chunk_size} samples ({interval_ms}ms)")
    
    # Check DebugClient
    try:
        resp = requests.get(f"{url}/api/audio/status", timeout=2)
        if resp.status_code == 200:
            status = resp.json()
            print(f"✅ Connected to DebugClient")
            print(f"   ESP32 IP: {status.get('espIp', 'unknown')}")
            print(f"   Packets received: {status.get('packetsReceived', 0)}")
            
            if not status.get('isReceiving'):
                print(f"\n⚠️  WARNING: DebugClient NOT receiving audio from ESP32!")
                time.sleep(2)
    except Exception as e:
        print(f"❌ Cannot connect to DebugClient: {e}")
        print(f"   Falling back to simulated audio...")
        for audio in simulate_audio_data(duration_s=60):
            yield audio
        return
    
    print(f"\n🎤 Listening for live audio...\n")
    
    chunk_idx = 0
    consecutive_errors = 0
    first_data = True
    
    try:
        while True:
            try:
                resp = requests.get(
                    f"{url}/api/audio/snapshot?samples={chunk_size}",
                    timeout=5
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    if data.get("channels") and len(data["channels"]) >= 2:
                        ch0 = np.array(data["channels"][0], dtype=np.float32)
                        ch1 = np.array(data["channels"][1], dtype=np.float32)
                        
                        if first_data:
                            print(f"✅ Receiving audio!\n")
                            first_data = False
                        
                        yield ch0, ch1
                        chunk_idx += 1
                        consecutive_errors = 0
                    else:
                        time.sleep(0.1)
                        consecutive_errors += 1
                
                elif resp.status_code == 503:
                    time.sleep(0.5)
                    consecutive_errors += 1
                else:
                    time.sleep(0.5)
                    consecutive_errors += 1
                
                if consecutive_errors > 10:
                    print(f"❌ Too many errors, giving up")
                    return
            
            except requests.exceptions.Timeout:
                time.sleep(1)
                consecutive_errors += 1
            except requests.exceptions.ConnectionError as e:
                print(f"❌ Lost connection: {e}")
                return
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)
                consecutive_errors += 1
    
    except KeyboardInterrupt:
        print(f"\n⏹️  Stopped (processed {chunk_idx} chunks)")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Live analysis with YAMNet (Google audio classification)"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:5262",
        help="DebugClient URL (default: http://localhost:5262)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=100,
        help="Analysis interval in ms (default: 100)"
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Use simulated audio instead of DebugClient"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60,
        help="Simulation duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.3,
        help="Confidence threshold (default: 0.3)"
    )
    
    args = parser.parse_args()
    
    # Create analyzer
    analyzer = YAMNetAnalyzer(interval_ms=args.interval, confidence_threshold=args.confidence)
    
    # Get audio source
    if args.simulate:
        print(f"📻 Using SIMULATED audio ({args.duration}s)")
        audio_gen = simulate_audio_data(duration_s=args.duration)
    else:
        print(f"📻 Connecting to DebugClient at {args.url}")
        audio_gen = fetch_audio_from_debugclient(url=args.url, interval_ms=args.interval)
    
    # Run analysis
    analyzer.run(audio_gen)


if __name__ == "__main__":
    main()
