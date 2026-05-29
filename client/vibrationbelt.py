"""
vibrationbelt — minimal client library for the ESP32 belt-mic node.

Designed so you can drop it into any project and get live audio in three
lines:

    import vibrationbelt as vb

    with vb.MicStream("10.8.5.177") as mic:
        for chunk in mic:
            do_something(chunk.samples)        # numpy int16 array

What it handles for you:
  - UDP socket setup and the subscribe/keepalive handshake.
  - Background receiver thread → bounded queue → your code never blocks
    the network read.
  - AUD1 framing (magic, seq, t_us, n_samp) → numpy int16 arrays.
  - Drop detection from sequence-number jumps (UDP reorders ignored).
  - Auto-resubscribe if the ESP32 expires us (no keepalive for >5 s).

What it deliberately does NOT do:
  - DSP. Gain, DC-block, filters, DoA — bring your own (`scipy.signal`,
    `librosa`, etc.).
  - Network discovery. You pass the ESP32's IP; we don't sniff mDNS.

Wire format is documented in firmware/src/protocol.h. Keep the constants
below in sync with firmware/src/config.h.
"""

from __future__ import annotations

import logging
import queue
import socket
import struct
import threading
import time
import wave
from dataclasses import dataclass
from typing import Iterator, Optional

import numpy as np

__all__ = ["MicStream", "Chunk", "record_wav",
           "SAMPLE_RATE", "CHANNELS", "DEFAULT_PORT"]

log = logging.getLogger("vibrationbelt")

# ─── Wire-format constants (must match firmware/src/config.h) ─────────────

SAMPLE_RATE  = 16000
CHANNELS     = 1
SAMPLE_DTYPE = np.int16
DEFAULT_PORT = 4444

_HEADER_FMT = "<4sIQI"                  # magic, seq, t_us, n_samp
_HEADER_LEN = struct.calcsize(_HEADER_FMT)
_MAGIC = b"AUD1"

# Subscribe/keepalive cadence. Must be < firmware's
# UDP_SUBSCRIBER_TIMEOUT_MS (5 s).
_KEEPALIVE_INTERVAL_S = 1.0
_MAX_DATAGRAM = 2048                    # AUD1 packets are < MTU


@dataclass(frozen=True)
class Chunk:
    """One audio packet."""
    samples: np.ndarray         # shape (n_samp, CHANNELS) for stereo,
                                # (n_samp,) for mono — int16
    timestamp_us: int           # ESP32-side capture time (esp_timer_get_time)
    sequence: int               # monotonic packet counter
    dropped_before: int         # packets lost between previous chunk and this one


class MicStream:
    """
    Live audio stream from the ESP32 belt-mic node.

    Use as a context manager — connect / subscribe is implicit, and the
    background receiver thread is cleaned up on exit:

        with MicStream("10.8.5.177") as mic:
            for chunk in mic:                       # blocks until next packet
                print(chunk.samples.shape, chunk.dropped_before)

    Or use the imperative API directly:

        mic = MicStream("10.8.5.177").start()
        try:
            while True:
                chunk = mic.read()                  # blocks
        finally:
            mic.close()

    Parameters
    ----------
    ip
        ESP32 mic node's IP address.
    port
        UDP port (matches firmware cfg::STREAM_PORT). Default 4444.
    queue_size
        Maximum buffered chunks before the receiver thread starts dropping
        oldest. 200 chunks ≈ 3 s at 16 kHz / 256-frame packets — plenty for
        slow consumers, small enough that you notice if the consumer falls
        behind.
    """

    def __init__(self, ip: str, port: int = DEFAULT_PORT,
                 queue_size: int = 200):
        self._server = (ip, port)
        self._sock: Optional[socket.socket] = None
        self._queue: queue.Queue[Chunk] = queue.Queue(maxsize=queue_size)
        self._rx_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._expected_seq: Optional[int] = None
        self._total_dropped = 0

    # ─── lifecycle ─────────────────────────────────────────────────────

    def start(self) -> "MicStream":
        """Open the socket, send the first subscribe, spawn the rx thread."""
        if self._rx_thread is not None:
            return self
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)
        self._sock.settimeout(2.0)
        self._send_keepalive()
        self._stop_event.clear()
        self._rx_thread = threading.Thread(
            target=self._rx_loop, name="vbelt-rx", daemon=True)
        self._rx_thread.start()
        log.info("subscribed to %s:%d via UDP", *self._server)
        return self

    def close(self) -> None:
        """Stop the rx thread and close the socket. Safe to call twice."""
        self._stop_event.set()
        if self._rx_thread is not None:
            self._rx_thread.join(timeout=2.0)
            self._rx_thread = None
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __enter__(self) -> "MicStream":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.close()

    # ─── public read API ───────────────────────────────────────────────

    def __iter__(self) -> Iterator[Chunk]:
        return self.iter_chunks()

    def iter_chunks(self, timeout: Optional[float] = None) -> Iterator[Chunk]:
        """Yield Chunks until close() is called or `timeout` elapses
        between successive chunks."""
        while not self._stop_event.is_set():
            try:
                yield self._queue.get(timeout=timeout)
            except queue.Empty:
                return

    def read(self, timeout: Optional[float] = None) -> Chunk:
        """Block for the next chunk. Raises queue.Empty on timeout."""
        return self._queue.get(timeout=timeout)

    def read_seconds(self, seconds: float) -> np.ndarray:
        """
        Block until `seconds` of audio have been received and return them
        as a single concatenated numpy array. Dropped packets are zero-
        filled to keep wall-clock duration correct.

        Returned shape: (int(seconds * SAMPLE_RATE), CHANNELS) for stereo
        or (int(seconds * SAMPLE_RATE),) for mono.
        """
        target_frames = int(seconds * SAMPLE_RATE)
        pieces: list[np.ndarray] = []
        accumulated = 0
        while accumulated < target_frames:
            chunk = self.read()
            if chunk.dropped_before > 0:
                # Fill the gap with silence so timings stay aligned.
                pad_frames = chunk.dropped_before * chunk.samples.shape[0]
                pieces.append(np.zeros_like(chunk.samples, shape=(pad_frames,)
                                            if CHANNELS == 1
                                            else (pad_frames, CHANNELS)))
                accumulated += pad_frames
            pieces.append(chunk.samples)
            accumulated += chunk.samples.shape[0]
        out = np.concatenate(pieces)[:target_frames]
        return out

    @property
    def dropped(self) -> int:
        """Total packets dropped since start()."""
        return self._total_dropped

    # ─── internals ─────────────────────────────────────────────────────

    def _send_keepalive(self) -> None:
        assert self._sock is not None
        try:
            self._sock.sendto(b"\x00", self._server)
        except OSError as e:
            log.debug("keepalive send failed: %s", e)

    def _rx_loop(self) -> None:
        """Run on the receiver thread. Pulls UDP, parses, enqueues."""
        assert self._sock is not None
        last_keepalive = time.monotonic()

        while not self._stop_event.is_set():
            now = time.monotonic()
            if now - last_keepalive >= _KEEPALIVE_INTERVAL_S:
                self._send_keepalive()
                last_keepalive = now

            try:
                datagram, _ = self._sock.recvfrom(_MAX_DATAGRAM)
            except socket.timeout:
                continue
            except OSError:
                # socket closed under us → orderly shutdown
                return

            chunk = self._parse(datagram)
            if chunk is None:
                continue

            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                # Consumer is too slow. Drop the OLDEST to make room — for
                # live audio it's better to be late than to fall behind
                # silently.
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                self._queue.put_nowait(chunk)
                log.warning("consumer too slow, dropped oldest chunk")

    def _parse(self, datagram: bytes) -> Optional[Chunk]:
        if len(datagram) < _HEADER_LEN:
            return None
        magic, seq, t_us, n_samp = struct.unpack(
            _HEADER_FMT, datagram[:_HEADER_LEN])
        if magic != _MAGIC:
            return None

        bytes_per_frame = CHANNELS * np.dtype(SAMPLE_DTYPE).itemsize
        payload_len = n_samp * bytes_per_frame
        payload = datagram[_HEADER_LEN:_HEADER_LEN + payload_len]
        if len(payload) < payload_len:
            return None         # truncated datagram

        samples = np.frombuffer(payload, dtype=SAMPLE_DTYPE).copy()
        if CHANNELS == 2:
            samples = samples.reshape(-1, 2)

        dropped = 0
        if self._expected_seq is not None and seq != self._expected_seq:
            missed = (seq - self._expected_seq) & 0xFFFFFFFF
            # Filter out UDP reorderings: huge "jumps" are almost certainly
            # a stale reordered packet, not real loss.
            if 0 < missed < 1000:
                dropped = missed
                self._total_dropped += missed
        self._expected_seq = (seq + 1) & 0xFFFFFFFF

        return Chunk(
            samples=samples,
            timestamp_us=t_us,
            sequence=seq,
            dropped_before=dropped,
        )


# ─── Convenience helpers ──────────────────────────────────────────────────

def record_wav(ip: str, path: str, seconds: float,
               port: int = DEFAULT_PORT) -> int:
    """
    Record `seconds` of audio from the belt mic into a 16-bit PCM WAV file.
    Returns the number of packets dropped during recording.
    """
    target_frames = int(seconds * SAMPLE_RATE)
    with MicStream(ip, port=port) as mic, wave.open(path, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(np.dtype(SAMPLE_DTYPE).itemsize)
        w.setframerate(SAMPLE_RATE)
        written = 0
        for chunk in mic:
            if chunk.dropped_before > 0:
                pad = chunk.dropped_before * chunk.samples.shape[0]
                w.writeframes(b"\x00" * pad
                              * CHANNELS * np.dtype(SAMPLE_DTYPE).itemsize)
                written += pad
            w.writeframes(chunk.samples.tobytes())
            written += chunk.samples.shape[0]
            if written >= target_frames:
                break
        return mic.dropped


# ─── Demo ─────────────────────────────────────────────────────────────────
# Run with:   python -m vibrationbelt <esp32-ip>
# Prints a live VU-meter to the terminal.

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"usage: python {sys.argv[0]} <esp32-ip>", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    print("Press Ctrl-C to stop\n")
    with MicStream("10.8.5.177") as mic:
        try:
            for chunk in mic:
                # RMS → simple ASCII level meter
                rms = float(np.sqrt(np.mean(chunk.samples.astype(np.float32) ** 2)))
                bars = int(min(rms / 500.0, 60.0))
                print(f"\rrms={rms:6.0f}  drops={mic.dropped:4d}  "
                      f"[{'█' * bars:<60}]",
                      end="", flush=True)
        except KeyboardInterrupt:
            print()
