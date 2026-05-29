"""Single-endpoint UDP audio stream from one ESP32 mic node."""

from __future__ import annotations

import logging
import queue
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Iterator, Optional

import numpy as np

log = logging.getLogger("vibrationbelt")

# ─── Wire-format constants (must match firmware/src/config.h) ─────────────

SAMPLE_RATE  = 8000                     # must match firmware cfg::SAMPLE_RATE_HZ
CHANNELS     = 2                        # must match firmware cfg::CHANNELS
SAMPLE_DTYPE = np.int16
DEFAULT_PORT = 4444

_HEADER_FMT = "<4sIQI"                  # magic, seq, t_us, n_samp
_HEADER_LEN = struct.calcsize(_HEADER_FMT)
_MAGIC = b"AUD1"

# Must be < firmware's UDP_SUBSCRIBER_TIMEOUT_MS (5 s).
_KEEPALIVE_INTERVAL_S = 1.0
_MAX_DATAGRAM = 2048


@dataclass(frozen=True)
class Chunk:
    """One audio packet.

    samples
        np.int16 array; shape (n,) for mono or (n, CHANNELS) for multi-channel.
    timestamp_us
        ESP32-side capture time (esp_timer_get_time, monotonic per chip).
    sequence
        Monotonic packet counter from the ESP32.
    dropped_before
        Packets lost between previous chunk and this one (UDP reorders ignored).
    received_at
        time.monotonic() on the *receiver* when the datagram arrived. Useful
        for wall-clock alignment across multiple ESP32 nodes.
    """
    samples: np.ndarray
    timestamp_us: int
    sequence: int
    dropped_before: int
    received_at: float


class MicStream:
    """Live UDP audio stream from a single ESP32 mic node.

    Use as a context manager:

        with MicStream("10.8.5.177") as mic:
            for chunk in mic:
                process(chunk.samples)

    Or imperative:

        mic = MicStream("10.8.5.177").start()
        try:
            chunk = mic.read(timeout=2.0)
        finally:
            mic.close()
    """

    def __init__(self, ip: str, port: int = DEFAULT_PORT,
                 queue_size: int = 200, name: Optional[str] = None):
        self.name = name or f"{ip}:{port}"
        self._server = (ip, port)
        self._sock: Optional[socket.socket] = None
        self._queue: queue.Queue[Chunk] = queue.Queue(maxsize=queue_size)
        self._rx_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._expected_seq: Optional[int] = None
        self._total_dropped = 0

    # ─── lifecycle ─────────────────────────────────────────────────────

    def start(self) -> "MicStream":
        if self._rx_thread is not None:
            return self
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256 * 1024)
        self._sock.settimeout(2.0)
        self._send_keepalive()
        self._stop_event.clear()
        self._rx_thread = threading.Thread(
            target=self._rx_loop, name=f"vbelt-rx-{self.name}", daemon=True)
        self._rx_thread.start()
        log.info("[%s] subscribed to %s:%d via UDP",
                 self.name, *self._server)
        return self

    def close(self) -> None:
        self._stop_event.set()
        if self._rx_thread is not None:
            self._rx_thread.join(timeout=2.0)
            self._rx_thread = None
        if self._sock is not None:
            try: self._sock.close()
            except OSError: pass
            self._sock = None

    def __enter__(self) -> "MicStream": return self.start()
    def __exit__(self, *exc) -> None:   self.close()

    # ─── reading ──────────────────────────────────────────────────────

    def __iter__(self) -> Iterator[Chunk]: return self.iter_chunks()

    def iter_chunks(self, timeout: Optional[float] = None) -> Iterator[Chunk]:
        while not self._stop_event.is_set():
            try:
                yield self._queue.get(timeout=timeout)
            except queue.Empty:
                return

    def read(self, timeout: Optional[float] = None) -> Chunk:
        """Block for the next chunk; raises queue.Empty on timeout."""
        return self._queue.get(timeout=timeout)

    @property
    def dropped(self) -> int:
        return self._total_dropped

    # ─── internals ────────────────────────────────────────────────────

    def _send_keepalive(self) -> None:
        assert self._sock is not None
        try:
            self._sock.sendto(b"\x00", self._server)
        except OSError as e:
            log.debug("[%s] keepalive send failed: %s", self.name, e)

    def _rx_loop(self) -> None:
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
                return
            chunk = self._parse(datagram, time.monotonic())
            if chunk is None:
                continue
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                # Drop oldest to make room — better to be a bit stale than
                # silently fall behind.
                try: self._queue.get_nowait()
                except queue.Empty: pass
                self._queue.put_nowait(chunk)
                log.warning("[%s] consumer slow, dropped oldest", self.name)

    def _parse(self, datagram: bytes, received_at: float) -> Optional[Chunk]:
        if len(datagram) < _HEADER_LEN: return None
        magic, seq, t_us, n_samp = struct.unpack(
            _HEADER_FMT, datagram[:_HEADER_LEN])
        if magic != _MAGIC: return None

        bytes_per_frame = CHANNELS * np.dtype(SAMPLE_DTYPE).itemsize
        payload_len = n_samp * bytes_per_frame
        payload = datagram[_HEADER_LEN:_HEADER_LEN + payload_len]
        if len(payload) < payload_len: return None

        samples = np.frombuffer(payload, dtype=SAMPLE_DTYPE).copy()
        if CHANNELS > 1:
            samples = samples.reshape(-1, CHANNELS)

        dropped = 0
        if self._expected_seq is not None and seq != self._expected_seq:
            missed = (seq - self._expected_seq) & 0xFFFFFFFF
            if 0 < missed < 1000:
                dropped = missed
                self._total_dropped += missed
        self._expected_seq = (seq + 1) & 0xFFFFFFFF

        return Chunk(
            samples=samples,
            timestamp_us=t_us,
            sequence=seq,
            dropped_before=dropped,
            received_at=received_at,
        )
