#!/usr/bin/env python3
"""
Live Analysis - Connect to DebugClient and analyze audio in real-time.

Reads dual-mic audio from the C# DebugClient's MicReceiver service,
runs analysis_engine pipeline, and displays results.

Usage:
    python run_live_analysis.py [--url http://localhost:5000] [--interval 100]
    
Options:
    --url       DebugClient URL (default: http://localhost:5000)
    --interval  Analysis interval in ms (default: 100ms = 10 Hz)
    --no-ui     Disable fancy UI, just print (for SSH/CI)
"""

import sys
import time
import argparse
from pathlib import Path
from collections import deque

import numpy as np

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from analysis_engine import AudioAnalysisPipeline
from analysis_engine.motor_mapper import MotorMapper


class LiveAnalyzer:
    """Monitor DebugClient and analyze audio in real-time."""
    
    def __init__(self, pipeline: AudioAnalysisPipeline, interval_ms: int = 100):
        self.pipeline = pipeline
        self.interval_s = interval_ms / 1000.0
        
        # History for smoothing
        self.doa_history = deque(maxlen=5)
        self.confidence_history = deque(maxlen=5)
        self.alarm_history = deque(maxlen=3)
        
        # Stats
        self.total_chunks = 0
        self.alarms_detected = 0
        self.start_time = time.time()
    
    def run(self, audio_data_generator):
        """
        Main loop: continuously analyze audio chunks.
        
        Args:
            audio_data_generator: yields (mic1_audio, mic2_audio) tuples
        """
        print("\n" + "="*70)
        print("🎤 LIVE ANALYSIS ENGINE")
        print("="*70)
        print("Listening for audio from DebugClient...")
        print("Make sure an alarm is sounding near the microphones!\n")
        
        try:
            for mic1_audio, mic2_audio in audio_data_generator:
                # Analyze
                result = self.pipeline.analyze(
                    audio_mic1=mic1_audio,
                    audio_mic2=mic2_audio,
                    debug=False
                )
                
                # Update history
                self.total_chunks += 1
                if result['doa_degrees'] is not None:
                    self.doa_history.append(result['doa_degrees'])
                self.confidence_history.append(result['alarm_confidence'])
                self.alarm_history.append(result['is_alarm'])
                
                if result['is_alarm']:
                    self.alarms_detected += 1
                
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
        doa_smooth = np.mean(self.doa_history) if self.doa_history else None
        conf_smooth = np.mean(self.confidence_history) if self.confidence_history else 0
        alarm_consensus = sum(self.alarm_history) > len(self.alarm_history) / 2
        
        # Direction indicator
        if doa_smooth is not None:
            direction = self._get_direction_emoji(doa_smooth)
        else:
            direction = "❓"
        
        # Alarm indicator
        alarm_str = "🚨 ALARM" if alarm_consensus else "  quiet"
        
        # Motor prediction
        if result['predicted_motor'] is not None:
            motor_label = MotorMapper.get_sector_label(result['predicted_motor'])
            motor_str = f"🎮 Motor {result['predicted_motor']} ({motor_label})"
        else:
            motor_str = "🎮 Motor None"
        
        # Confidence bar
        bar_len = 20
        filled = int(conf_smooth * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        # Print
        elapsed = time.time() - self.start_time
        elapsed_min = int(elapsed // 60)
        elapsed_sec = int(elapsed % 60)
        
        print(f"[{elapsed_min:02d}:{elapsed_sec:02d}] "
              f"{direction} {doa_smooth:6.1f}° | "
              f"[{bar}] {conf_smooth*100:5.1f}% | "
              f"{alarm_str} | "
              f"{motor_str}")
    
    def _get_direction_emoji(self, doa_degrees):
        """Get emoji for direction."""
        angle = doa_degrees % 360
        
        if angle < 45 or angle >= 315:
            return "⬆️ "
        elif 45 <= angle < 135:
            return "➡️ "
        elif 135 <= angle < 225:
            return "⬇️ "
        else:
            return "⬅️ "
    
    def _print_stats(self):
        """Print final statistics."""
        elapsed = time.time() - self.start_time
        
        print("\n" + "="*70)
        print("📊 SESSION STATISTICS")
        print("="*70)
        print(f"Duration: {elapsed/60:.1f} minutes")
        print(f"Chunks analyzed: {self.total_chunks}")
        print(f"Alarms detected: {self.alarms_detected}")
        if self.total_chunks > 0:
            print(f"Alarm rate: {self.alarms_detected/self.total_chunks*100:.1f}%")
        print("="*70 + "\n")


def simulate_audio_data(duration_s: float = 30):
    """
    Simulate dual-mic audio data for testing (without real DebugClient).
    
    Yields: (mic1_audio, mic2_audio) tuples
    """
    sample_rate = 16000
    chunk_size = sample_rate // 10  # 100ms chunks
    
    elapsed = 0
    while elapsed < duration_s:
        # Simulate alarm-like sound (sine sweep)
        t = np.arange(chunk_size) / sample_rate
        
        # Frequency sweep 2-4 kHz (alarm-like)
        f_start, f_end = 2000, 4000
        freq = f_start + (f_end - f_start) * (elapsed / duration_s)
        
        mic1 = 0.3 * np.sin(2 * np.pi * freq * t).astype(np.float32)
        mic2 = 0.25 * np.sin(2 * np.pi * freq * t).astype(np.float32)  # Slightly delayed
        
        yield mic1, mic2
        
        elapsed += chunk_size / sample_rate
        time.sleep(0.01)  # Simulate processing time


def fetch_audio_from_debugclient(url: str = "http://localhost:5000", interval_ms: int = 100):
    """
    Connect to DebugClient API and fetch audio chunks.
    
    Yields: (mic1_audio, mic2_audio) tuples
    """
    import requests
    
    print(f"Connecting to DebugClient at {url}...")
    
    chunk_size = int(16000 * interval_ms / 1000)  # samples per chunk
    
    # First check that DebugClient is running
    try:
        resp = requests.get(f"{url}/api/status", timeout=2)
        if resp.status_code == 200:
            print(f"✓ Connected to DebugClient")
    except Exception as e:
        print(f"⚠️  Cannot connect to DebugClient at {url}")
        print(f"   Error: {e}")
        print(f"\n   To start DebugClient:")
        print(f"   cd DebugClient && dotnet run")
        print(f"\n   Falling back to simulated audio for testing...")
        
        # Use simulation
        for audio in simulate_audio_data(duration_s=60):
            yield audio
        return
    
    # Fetch audio chunks continuously
    chunk_idx = 0
    try:
        while True:
            try:
                # Get snapshot from DebugClient
                resp = requests.get(
                    f"{url}/api/audio/snapshot?samples={chunk_size}",
                    timeout=5
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # data = {"channels": [ch0_data, ch1_data], ...}
                    if data.get("channels") and len(data["channels"]) >= 2:
                        ch0 = np.array(data["channels"][0], dtype=np.float32)
                        ch1 = np.array(data["channels"][1], dtype=np.float32)
                        
                        yield ch0, ch1
                        chunk_idx += 1
                    else:
                        print("⚠️  Waiting for audio data from ESP32...")
                        time.sleep(0.5)
                else:
                    print(f"⚠️  API error: {resp.status_code}")
                    time.sleep(1)
                    
            except requests.exceptions.Timeout:
                print("⚠️  Request timeout, retrying...")
                time.sleep(1)
            except requests.exceptions.ConnectionError:
                print("❌ Lost connection to DebugClient")
                return
    
    except KeyboardInterrupt:
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Live analysis of audio from VibrationBelt DebugClient"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:5000",
        help="DebugClient URL (default: http://localhost:5000)"
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
    
    args = parser.parse_args()
    
    # Initialize pipeline with CNN model (if available)
    model_path = Path("models/alarm_detector.pt")
    use_cnn = model_path.exists()
    
    if use_cnn:
        print(f"✓ Using CNN model: {model_path}")
        pipeline = AudioAnalysisPipeline(
            model_path=str(model_path),
            use_template_only=False
        )
    else:
        print("ℹ️  No CNN model found, using template matching (disabled)")
        pipeline = AudioAnalysisPipeline(use_template_only=True)
    
    # Create analyzer
    analyzer = LiveAnalyzer(pipeline, interval_ms=args.interval)
    
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
