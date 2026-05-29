// config.h — single source of truth for all tunable constants.
//
// Anything a user/developer is likely to change goes here so they
// don't have to dig through the implementation files.

#pragma once

#include <cstdint>

namespace cfg {

// ─── WiFi ──────────────────────────────────────────────────────────────────
// 2.4 GHz WPA2-PSK only. Captive-portal / WPA2-Enterprise networks won't work.

inline constexpr const char* WIFI_SSID = "Techbase Guest";
inline constexpr const char* WIFI_PASS = "verbunden25!";

inline constexpr uint32_t WIFI_TIMEOUT_MS = 20'000;

// Disable WiFi power-save (DTM/Beacon listen-interval idle).
// Power save introduces 100–500 ms latency spikes that are catastrophic
// for live audio. The mic node is mains-powered so we don't care about
// the ~80 mA difference.
inline constexpr bool WIFI_DISABLE_POWERSAVE = true;

// ─── UDP audio stream ──────────────────────────────────────────────────────
// Live audio is sent over UDP. The ESP32 listens on STREAM_PORT for any
// incoming UDP packet; the source becomes the current subscriber and
// receives the audio stream. The client must re-send a keepalive packet
// at least every UDP_SUBSCRIBER_TIMEOUT_MS or it gets dropped.
//
// Why UDP and not TCP?
//   For live audio TCP is the wrong tool. A single packet loss stalls every
//   subsequent packet until retransmit — heard as a multi-second freeze
//   followed by a glitch. UDP just drops the lost packet (one click) and
//   keeps streaming. AUD1 sequence numbers let the receiver detect loss.

inline constexpr uint16_t STREAM_PORT = 4444;
inline constexpr uint32_t UDP_SUBSCRIBER_TIMEOUT_MS = 5'000;

// ─── PDM microphone (IM69D130) capture ─────────────────────────────────────
//
// Wiring (all on the LEFT side of the 30-pin ESP32-WROOM-32 DevKit):
//
//   ESP32 pin              ←→ Mic piece pin
//   ───────────────────────────────────────────────────────
//   3V3 (top of left side)    → VDD
//   GND (between pins 12+13)  → GND
//   GPIO 26                   → CLK   (PDM bit clock, ESP32 output)
//   GPIO 25                   ← DATA  (PDM data, ESP32 input)
//
// When a second mic is wired, both pieces' DATA lines tie to the same
// GPIO 25 wire (wired-OR), and both CLK lines tie to GPIO 26. Note that
// the classic ESP32 only delivers true *mono* PDM RX in hardware —
// see CHANNELS below.

inline constexpr int PDM_CLK_PIN  = 26;
inline constexpr int PDM_DATA_PIN = 25;

// Sample rate per channel.
//
// 16 kHz × 128× oversample (the new-driver default I2S_PDM_DSR_8S) =
// 2.048 MHz PDM clock, which puts the IM69D130 in its NORMAL-POWER mode
// (>1 MHz). Below 1 MHz the mic enters low-power mode and SNR degrades.
//
// Per the IM69D130 datasheet the supported clock range is roughly
// 1.0–3.5 MHz for normal operation. 16 kHz is also the rate the classic
// ESP32 PDM peripheral handles most reliably.
inline constexpr uint32_t SAMPLE_RATE_HZ = 16000;

// CHANNELS:
//   1 = mono PDM RX.
//   2 = stereo PDM RX. Both mic pieces (top = R-channel, bottom = L-channel
//       per the Shield2Go's factory 0Ω strap) wire in parallel onto the
//       same CLK and DATA lines. The ESP32 deinterleaves them via the
//       PDM CLK edges.
//
// Empirical note: classic ESP32 stereo PDM RX was unreliable under the
// LEGACY driver. With the new ESP-IDF 5 i2s_pdm driver and BOTH mics
// physically wired (not just one), it should work. If you see L == R or
// wrong rate after a stereo build, the path forward is the ADAU7002 I²S
// route or an ESP32-S3.
inline constexpr int CHANNELS = 2;
inline constexpr int BITS_PER_SAMPLE = 16;

// Software gain applied to every sample on the ESP32 before sending.
//
// Why gain at all?
//   IM69D130 sensitivity is −36 dBFS @ 94 dB SPL. At conversational
//   speech (~70 dB SPL) raw int16 peaks are only ~±30 LSB out of ±32767.
//   That's almost inaudible without amplification.
//
// Why on the ESP32 and not on the receiver?
//   So *every* downstream consumer (ffplay, sox, Python, C#, the
//   eventual DoA estimator) sees pre-amplified audio without having to
//   re-implement the gain knob.
//
// Saturating int16 multiply happens in audio_streamer.cpp. Set to 1 to
// pass through raw samples (useful for measuring the un-amplified
// signal floor or computing absolute SPL).
inline constexpr float AUDIO_GAIN = 32.0f;

// DMA buffers. `dma_frame_num` is in frames (1 frame = CHANNELS samples).
//
// 256 frames @ 16 kHz = 16 ms per buffer  → low capture-side latency.
// 8 buffers × 16 ms     = 128 ms of slack before the DMA ring overruns,
//                          enough to absorb typical WiFi stalls.
//
// Going below 256 frames starts costing serious CPU on TCP framing
// overhead. Going above 512 frames noticeably worsens live-monitoring
// latency.
inline constexpr uint32_t DMA_FRAME_NUM = 256;
inline constexpr uint32_t DMA_DESC_NUM  = 8;

// How long to wait after init before reading the first audio block.
// The IM69D130 needs a settling period after VDD comes up and the clock
// starts. Datasheet specifies it on the order of tens of ms; we use a
// conservative 100 ms to discard the startup transient (which otherwise
// shows up as a loud "thump" at the start of every recording).
inline constexpr uint32_t MIC_WARMUP_MS = 100;

// ─── Task placement ────────────────────────────────────────────────────────
// WiFi/lwIP run on core 0 (Arduino default). Pin the audio task to core 1
// at a high priority so neither WiFi nor the Arduino loop can preempt it.

inline constexpr int AUDIO_TASK_CORE     = 1;
inline constexpr int AUDIO_TASK_PRIORITY = 10;   // above default (5)
inline constexpr int AUDIO_TASK_STACK    = 8192;

}  // namespace cfg
