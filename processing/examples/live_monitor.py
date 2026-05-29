#!/usr/bin/env python3
"""Live monitor: Record from mic and detect alarms in real-time."""

import sys
import numpy as np
import sounddevice as sd
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from audio_analyzer.pipeline import AudioAnalysisPipeline


def monitor_audio(chunk_duration: float = 2.0, sr: int = 16000, verbose: bool = True):
    """
    Continuously monitor audio and detect alarms.
    
    Args:
        chunk_duration: Duration of each analysis chunk (seconds).
        sr: Sample rate (Hz).
        verbose: Print details.
    """
    pipeline = AudioAnalysisPipeline(target_sr=sr)
    chunk_samples = int(sr * chunk_duration)
    
    print("=" * 70)
    print("🎤 Live Audio Monitor (Press Ctrl+C to stop)")
    print("=" * 70)
    print()
    
    chunk_num = 0
    
    try:
        while True:
            chunk_num += 1
            
            # Record chunk
            if verbose:
                print(f"[{chunk_num}] Recording {chunk_duration}s chunk...", end=" ", flush=True)
            
            audio = sd.rec(chunk_samples, samplerate=sr, channels=1, dtype=np.float32)
            sd.wait()
            audio = audio.flatten()
            
            # Quick analysis
            peak = np.max(np.abs(audio))
            rms = np.sqrt(np.mean(audio ** 2))
            
            if verbose:
                print(f"peak={peak:.3f} rms={rms:.4f}", end=" | ")
            
            ################################# HIER ANPASSEN #####################################################
            #####################################################################################################
            # Detect alarms
            alarms = pipeline.alarm_detector.detect_alarms(
                audio,
                sensitivity=0.6,
                min_confidence=0.7  # Higher threshold = fewer false positives
            )
            
            if alarms:
                print(f"🚨 ALARM DETECTED!")
                for alarm in alarms:
                    print(f"     └─ {alarm['alarm_type'].value} ({alarm['confidence']:.0%})")
            else:
                print("✓ Clear")
    
    except KeyboardInterrupt:
        print("\n\n✓ Monitor stopped")


def record_and_save(duration: float = 5.0, sr: int = 16000) -> Path:
    """Record and save to file."""
    print(f"🎤 Recording {duration}s...\n")
    
    audio = sd.rec(int(sr * duration), samplerate=sr, channels=1, dtype=np.float32)
    sd.wait()
    audio = audio.flatten()
    
    import soundfile as sf
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(__file__).parent.parent / "test_audio"
    output_dir.mkdir(exist_ok=True)
    
    filepath = output_dir / f"recording_{timestamp}.wav"
    sf.write(str(filepath), audio, sr)
    
    print(f"✓ Saved to {filepath}")
    return filepath


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python live_monitor.py monitor              # Live monitoring")
        print("  python live_monitor.py record [duration]    # Record and save")
        print("  python live_monitor.py test                 # Test with recording")
        print()
        print("Examples:")
        print("  python live_monitor.py monitor")
        print("  python live_monitor.py record 10")
        print("  python live_monitor.py test")
        sys.exit(1)

    mode = sys.argv[1]
    
    if mode == "monitor":
        monitor_audio(chunk_duration=2.0, verbose=True)
    
    elif mode == "record":
        duration = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
        filepath = record_and_save(duration=duration)
        
        # Analyze
        print("\n" + "=" * 70)
        print("🔍 Analyzing recording...")
        print("=" * 70 + "\n")
        
        import soundfile as sf
        audio, sr = sf.read(str(filepath))
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        pipeline = AudioAnalysisPipeline(target_sr=sr)
        result = pipeline.analyze_audio(audio, sr)
        
        print(result["summary"])
    
    elif mode == "test":
        print("Testing with generated alarm sounds...\n")
        from pathlib import Path
        test_dir = Path(__file__).parent.parent / "test_audio"
        
        if not test_dir.exists():
            print("Generating test audio...")
            import importlib.util
            spec = importlib.util.spec_from_file_location("gen", Path(__file__).parent / "generate_test_alarms.py")
            gen = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gen)
            gen.main()
        
        # Analyze all test files
        import soundfile as sf
        pipeline = AudioAnalysisPipeline()
        
        for audio_file in sorted(test_dir.glob("*.wav")):
            if "recording" in audio_file.name:
                continue
            
            print(f"Testing: {audio_file.name}")
            audio, sr = sf.read(str(audio_file))
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            result = pipeline.analyze_audio(audio, sr)
            alarms = result["alarms"]
            
            if alarms:
                for alarm in alarms:
                    print(f"  ✓ {alarm['alarm_type'].value} ({alarm['confidence']:.0%})")
            else:
                print(f"  ✓ No alarms")
            print()


if __name__ == "__main__":
    main()
