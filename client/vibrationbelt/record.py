"""Convenience: record live audio straight to WAV."""

from __future__ import annotations

import wave

import numpy as np

from .stream import MicStream, SAMPLE_RATE, CHANNELS, SAMPLE_DTYPE, DEFAULT_PORT


def record_wav(ip: str, path: str, seconds: float,
               port: int = DEFAULT_PORT) -> int:
    """Record `seconds` of audio from one mic node into a 16-bit PCM WAV.

    Returns the number of UDP packets dropped during the recording.
    Gaps (lost packets) are silence-padded so the file length matches
    wall-clock duration.
    """
    target_frames = int(seconds * SAMPLE_RATE)
    sample_bytes = np.dtype(SAMPLE_DTYPE).itemsize
    with MicStream(ip, port=port) as mic, wave.open(path, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(sample_bytes)
        w.setframerate(SAMPLE_RATE)
        written = 0
        for chunk in mic:
            if chunk.dropped_before > 0:
                pad_frames = chunk.dropped_before * chunk.samples.shape[0]
                w.writeframes(b"\x00" * pad_frames * CHANNELS * sample_bytes)
                written += pad_frames
            w.writeframes(chunk.samples.tobytes())
            written += chunk.samples.shape[0]
            if written >= target_frames:
                break
        return mic.dropped
