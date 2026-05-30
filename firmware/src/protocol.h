// protocol.h — wire format shared between the ESP32 firmware and the
// PC-side receiver. Keep in sync with client/vibrationbelt/stream.py.
//
// One PacketHeader is followed immediately by interleaved stereo int16
// frames (4 bytes each: L then R, little-endian). Sample count is derived
// from the UDP datagram length, so it isn't carried in the header.
//
// All integer fields are little-endian. The ESP32 is little-endian so we
// can just memcpy these structs to the wire.

#pragma once

#include <cstdint>

namespace proto {

inline constexpr char     MAGIC[4]    = {'A', 'U', 'D', '1'};
inline constexpr uint32_t MAGIC_U32   = 0x31'44'55'41u;   // "AUD1" LE

struct __attribute__((packed)) PacketHeader {
    char     magic[4];   // must be "AUD1"
    uint32_t seq;        // monotonic packet counter, wraps at 2^32
};

// Motor control (client → ESP32, UDP on STREAM_PORT).
//
// Wire format:  MOTOR_MAGIC  +  N × uint8_t strength (0..100, one per motor).
// The audio_streamer's UDP receiver distinguishes audio-subscribe packets
// (any other payload, treated as a keepalive) from motor commands by
// checking for this magic. A motor packet does NOT subscribe the sender
// to the audio stream — the controller and the audio listener can be
// different clients.
inline constexpr char MOTOR_MAGIC[4] = {'M', 'O', 'T', '1'};

// static_assert(sizeof(PacketHeader) == 12, "PacketHeader must be 12 bytes");

}  // namespace proto
