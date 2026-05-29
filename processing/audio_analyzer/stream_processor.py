"""
Live Audio Stream Processor — Real-time analysis pipeline.

Handles:
- Multiple audio input streams (USB, network, etc.)
- Continuous frame buffering (sliding window)
- Real-time alarm + anomaly detection
- Live detection output (callbacks/queues)

Architecture:
- Input: Raw audio chunks from any source (MicStream, device, etc.)
- Processing: Streaming FFT + pattern analysis
- Output: Detection events (alarm/anomaly with confidence)

Multi-mic ready: Each stream gets its own processor + baseline learner.
"""

import numpy as np
import threading
import queue
import logging
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from enum import Enum

from .alarm_detector import AlarmDetector
from .anomaly_detector import AnomalyDetector

log = logging.getLogger("stream_processor")


class DetectionType(Enum):
    """What was detected."""
    ALARM = "alarm"  # Any alarm (siren, smoke detector, etc.)
    LOUD_SOUND = "loud_sound"  # Anomaly (scream, crash, etc.)


@dataclass(frozen=True)
class Detection:
    """Real-time detection output."""
    type: DetectionType  # ALARM or LOUD_SOUND
    confidence: float  # 0-1
    snr_db: float  # Signal-to-noise ratio
    timestamp_sec: float  # When detected (relative to stream start)
    source: str  # Which input (e.g., "mic_0", "usb_1")
    
    # Raw detector info (for debugging/tuning)
    detector_type: Optional[str] = None  # "siren", "scream_shout", etc.
    detector_confidence: Optional[float] = None


class StreamProcessor:
    """
    Real-time audio analysis for a single input stream.
    
    Processes chunks from any source (MicStream, pyaudio device, etc.)
    and outputs detection events (ALARM or LOUD_SOUND) with confidence.
    
    Usage:
        processor = StreamProcessor(source_name="mic_0", sr=16000)
        
        # Optional: set detection callbacks
        processor.on_detection(print_detection)
        
        # Feed chunks (typically from a background thread)
        for chunk in audio_stream:
            processor.process_chunk(chunk.samples)
        
        # Cleanup
        processor.close()
    """

    def __init__(
        self,
        source: str,
        sr: int = 16000,
        frame_size: int = 2048,  # 128ms @ 16kHz (was 512 = 30ms)
        baseline_duration_sec: float = 10.0,
        alarm_sensitivity: float = 0.5,
        anomaly_sensitivity: float = 0.6,
    ):
        """
        Initialize processor for one input stream.
        
        Args:
            source: Stream identifier (e.g., "mic_0", "usb_1")
            sr: Sample rate (Hz)
            frame_size: Frames to accumulate before analysis (2048 = ~128ms @ 16kHz)
            baseline_duration_sec: How long to learn ambient baseline
            alarm_sensitivity: Alarm detection sensitivity (0-1)
            anomaly_sensitivity: Anomaly detection sensitivity (0-1)
        """
        self.source = source
        self.sr = sr
        self.frame_size = frame_size
        
        # Detectors
        self.alarm_detector = AlarmDetector(sr)
        self.anomaly_detector = AnomalyDetector(sr, baseline_duration_sec)
        
        # Sensitivity settings
        self.alarm_sensitivity = alarm_sensitivity
        self.anomaly_sensitivity = anomaly_sensitivity
        
        # Streaming state
        self.buffer = np.array([], dtype=np.float32)
        self.total_frames_processed = 0
        self.is_calibrated = False
        self.calibration_start_time = None
        
        # Callbacks
        self._detection_callbacks: List[Callable[[Detection], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        
        log.info(f"StreamProcessor initialized for {source} @ {sr} Hz")

    def on_detection(self, callback: Callable[[Detection], None]) -> None:
        """Register a callback for detection events."""
        with self._lock:
            self._detection_callbacks.append(callback)

    def process_chunk(self, chunk: np.ndarray) -> None:
        """
        Process one audio chunk from the stream.
        
        This is the main entry point. Call from your audio thread.
        
        Args:
            chunk: Audio data (1D numpy array, float32, -1.0 to 1.0)
        """
        if self._stop_event.is_set():
            return

        with self._lock:
            # Convert to float32 if needed
            if chunk.dtype != np.float32:
                chunk = chunk.astype(np.float32) / np.iinfo(chunk.dtype).max

            # Append to buffer
            self.buffer = np.concatenate([self.buffer, chunk])
            
            # Process when we have enough frames
            while len(self.buffer) >= self.frame_size:
                self._process_frame(self.buffer[:self.frame_size])
                self.buffer = self.buffer[self.frame_size:]

    def _process_frame(self, frame: np.ndarray) -> None:
        """Analyze one frame and emit detections."""
        self.total_frames_processed += len(frame)
        elapsed_sec = self.total_frames_processed / self.sr
        
        # PHASE 1: Calibration (learn ambient baseline)
        if not self.is_calibrated:
            if self.calibration_start_time is None:
                self.calibration_start_time = elapsed_sec
            
            baseline_age = elapsed_sec - self.calibration_start_time
            if baseline_age < 10.0:
                # Still learning baseline
                self.anomaly_detector.learn_baseline(frame)
                if baseline_age > 1.0 and not self.is_calibrated:
                    # Log calibration progress
                    log.debug(f"Calibrating {self.source}: {baseline_age:.1f}s")
            else:
                # Calibration complete
                self.is_calibrated = True
                log.info(f"Calibration complete for {self.source}")
                return
        
        # PHASE 2: Run both detectors in parallel
        alarm_detections = self.alarm_detector.detect_alarms_streaming(
            frame,
            sensitivity=self.alarm_sensitivity,
            min_confidence=0.4,  # Relaxed for streaming
        )
        
        anomaly_detections = self.anomaly_detector.detect_anomalies(
            frame,
            min_snr_db=6.0,
            min_confidence=0.4,
            sensitivity=self.anomaly_sensitivity,
        )
        
        # PHASE 3: Convert to unified output format
        # Priority: ALARM > LOUD_SOUND
        
        # Check alarms first
        if alarm_detections:
            # Any alarm detected
            best_alarm = max(alarm_detections, key=lambda x: x["confidence"])
            detection = Detection(
                type=DetectionType.ALARM,
                confidence=best_alarm["confidence"],
                snr_db=best_alarm.get("snr_db", 0.0),
                timestamp_sec=elapsed_sec,
                source=self.source,
                detector_type=str(best_alarm.get("alarm_type", "unknown")),
                detector_confidence=best_alarm["confidence"],
            )
            self._emit_detection(detection)
        
        # Check anomalies (only if no alarm)
        elif anomaly_detections:
            # Any anomaly detected
            best_anomaly = max(anomaly_detections, key=lambda x: x["confidence"])
            detection = Detection(
                type=DetectionType.LOUD_SOUND,
                confidence=best_anomaly["confidence"],
                snr_db=best_anomaly["snr_db"],
                timestamp_sec=elapsed_sec,
                source=self.source,
                detector_type=best_anomaly["type"].value,
                detector_confidence=best_anomaly["confidence"],
            )
            self._emit_detection(detection)

    def _emit_detection(self, detection: Detection) -> None:
        """Send detection to all registered callbacks."""
        for callback in self._detection_callbacks:
            try:
                callback(detection)
            except Exception as e:
                log.error(f"Detection callback error: {e}")

    def close(self) -> None:
        """Stop processing and cleanup."""
        self._stop_event.set()
        log.info(f"StreamProcessor closed: {self.source}")


class MultiStreamAnalyzer:
    """
    Manage multiple input streams with unified detection output.
    
    Designed for scalability: Add streams on-the-fly, get detections
    from all sources through a single unified queue.
    
    Usage:
        analyzer = MultiStreamAnalyzer()
        
        # Add input stream 1 (ESP32 belt-mic)
        proc1 = analyzer.add_stream("mic_0", sr=16000)
        analyzer.connect_source("mic_0", esp32_stream_chunks)
        
        # Add input stream 2 (USB microphone)
        proc2 = analyzer.add_stream("mic_1", sr=16000)
        analyzer.connect_source("mic_1", usb_stream_chunks)
        
        # Get detections from unified queue
        while True:
            detection = analyzer.read_detection(timeout=1.0)
            if detection:
                print(f"{detection.source}: {detection.type.value}")
    """

    def __init__(self):
        """Initialize multi-stream analyzer."""
        self.processors: Dict[str, StreamProcessor] = {}
        self.detection_queue: queue.Queue[Detection] = queue.Queue(maxsize=1000)
        self._lock = threading.RLock()
        self._source_threads: Dict[str, threading.Thread] = {}
        
        log.info("MultiStreamAnalyzer initialized")


    def _on_detection(self, detection: Detection) -> None:
        """Internal callback: collect detection from any stream."""
        try:
            self.detection_queue.put_nowait(detection)
        except queue.Full:
            # Drop oldest if queue full
            try:
                self.detection_queue.get_nowait()
            except queue.Empty:
                pass
            self.detection_queue.put_nowait(detection)

    def add_stream(
        self,
        source: str,
        sr: int = 16000,
        frame_size: int = 2048,  # 128ms @ 16kHz (was 512 = 30ms)
    ) -> StreamProcessor:
        """
        Add a new input stream.
        
        Args:
            source: Stream identifier (e.g., "mic_0")
            sr: Sample rate (Hz)
            frame_size: Frame size for analysis
            
        Returns:
            StreamProcessor for this source (for advanced usage)
        """
        with self._lock:
            if source in self.processors:
                log.warning(f"Stream {source} already exists, replacing")
                self.processors[source].close()
            
            processor = StreamProcessor(source, sr=sr, frame_size=frame_size)
            processor.on_detection(self._on_detection)
            self.processors[source] = processor
            
            log.info(f"Added stream: {source}")
            return processor

    def connect_source(
        self,
        source: str,
        chunk_iterator,
        name: str = None,
    ) -> None:
        """
        Connect an audio chunk source to a stream (runs in background thread).
        
        Args:
            source: Stream identifier (must have been added with add_stream)
            chunk_iterator: Iterator yielding audio chunks
            name: Optional thread name
        """
        if source not in self.processors:
            raise ValueError(f"Stream {source} not found. Call add_stream first.")
        
        processor = self.processors[source]
        thread_name = name or f"audio-{source}"
        
        def _feed_chunks():
            try:
                for chunk in chunk_iterator:
                    # Handle different chunk formats
                    if hasattr(chunk, 'samples'):
                        # vibrationbelt.Chunk
                        audio = chunk.samples.astype(np.float32) / 32768.0
                    else:
                        # Raw array
                        audio = chunk
                    
                    processor.process_chunk(audio)
            except Exception as e:
                log.error(f"Error feeding chunks to {source}: {e}")
            finally:
                processor.close()
        
        thread = threading.Thread(target=_feed_chunks, name=thread_name, daemon=True)
        self._source_threads[source] = thread
        thread.start()
        log.info(f"Connected source {source} (background thread)")

    def read_detection(self, timeout: Optional[float] = None) -> Optional[Detection]:
        """
        Get next detection from the unified queue.
        
        Args:
            timeout: Timeout in seconds (None = block forever)
            
        Returns:
            Detection or None (on timeout/empty)
        """
        try:
            return self.detection_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def iter_detections(self, timeout: Optional[float] = None):
        """
        Iterate over detections (yields Detection objects).
        
        Args:
            timeout: Timeout between detections (None = wait forever)
                     If timeout expires with no detection, keeps waiting.
        """
        while True:
            detection = self.read_detection(timeout=timeout)
            if detection is not None:
                yield detection
            # If None (timeout), just loop again and keep waiting

