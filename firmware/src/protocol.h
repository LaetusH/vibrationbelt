// protocol.h — wire format shared between the ESP32 firmware and the
// PC-side receiver. Keep in sync with client/receive.py.
//
// One PacketHeader is followed immediately by `n_samp` stereo
// int16 frames (4 bytes each, L then R, little-endian).
//
// Total bytes on the wire per packet:
//   sizeof(PacketHeader) + n_samp * 2 channels * 2 bytes
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
    uint32_t seq;        // monotonic packet counter
    uint64_t t_us;       // esp_timer_get_time() captured just before
                         // i2s_channel_read() returned this buffer
    uint32_t n_samp;     // number of stereo frames (L+R pairs)
};

static_assert(sizeof(PacketHeader) == 20, "PacketHeader must be 20 bytes");

}  // namespace proto
