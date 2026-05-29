"""
vibrationbelt — Python client library for the ESP32 belt-mic node.

Topologies
----------
A. One ESP32 with N mics on ONE stream (recommended for DoA):
       sample-accurate sync, samples shape = (frames, N).

       with MicStream("10.8.5.177") as mic:
           for chunk in mic:
               left  = chunk.samples[:, 0]
               right = chunk.samples[:, 1]
               ...

B. Multiple ESP32s, one mic each, multiple UDP streams:
       wall-clock-aligned, OK for left/right-hemisphere detection but
       NOT for sub-sample TDoA.

       array = MicArray({
           "left":  MicSpec("10.8.5.177", position=(-0.10, 0)),
           "right": MicSpec("10.8.5.178", position=( 0.10, 0)),
       })
       with array:
           for event in array.events(threshold_rms=2000):
               tdoa, _ = gcc_phat(event.samples["left"],
                                  event.samples["right"])
               angle = tdoa_to_angle(tdoa, baseline_m=0.20)

Wire format and the firmware end live in firmware/src/. Keep the
constants in `stream.py` in sync with firmware/src/config.h.
"""

from .stream  import MicStream, Chunk, SAMPLE_RATE, CHANNELS, DEFAULT_PORT
from .array   import MicArray, MicSpec, Event
from .doa     import gcc_phat, tdoa_to_angle, SPEED_OF_SOUND
from .record  import record_wav

__all__ = [
    "MicStream", "Chunk",
    "MicArray", "MicSpec", "Event",
    "gcc_phat", "tdoa_to_angle", "SPEED_OF_SOUND",
    "record_wav",
    "SAMPLE_RATE", "CHANNELS", "DEFAULT_PORT",
]
