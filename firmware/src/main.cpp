// VibrationBelt — stereo PDM mic capture + TCP streaming node.
//
// Hardware
//   ESP32-WROOM-32 DevKit
//   1× Infineon IM69D130 Microphone Shield2Go, snapped into 3 pieces;
//   middle (ADAU7002) piece discarded, both mic pieces wired in
//   parallel onto a single PDM clock + single PDM data line.
//
// Wiring (see config.h for pin assignments)
//   All four wires on the LEFT side of the 30-pin ESP32-WROOM-32 DevKit:
//     3V3 (top)                → VDD on each mic piece
//     GND (between pins 12+13) → GND on each mic piece
//     GPIO 26                  → CLK  on each mic piece
//     GPIO 25                  ← DATA on each mic piece (wired in parallel)
//   Top mic   → R channel (factory 0Ω strap on the board)
//   Bot mic   → L channel (factory 0Ω strap on the board)
//
// What this firmware does
//   1. Connects to WiFi (verbose diagnostics in wifi_mgr).
//   2. Starts a TCP server on port 4444.
//   3. Initialises the PDM peripheral via the new ESP-IDF 5 driver
//      (true stereo, accurate sample rate) — see pdm_capture.
//   4. Spawns an audio task pinned to core 1 that continuously reads
//      DMA buffers and pushes them to the connected TCP client with
//      a small framing header (see protocol.h).
//
// Counterpart on the PC side: client/receive.py.

#include <Arduino.h>

#include "audio_streamer.h"
#include "config.h"
#include "pdm_capture.h"
#include "wifi_mgr.h"

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\n=== VibrationBelt mic node ===");
    Serial.printf("[main] %u Hz  %d ch  %d-bit  gain=%.1fx  pkt=%u frames\n",
                  (unsigned)cfg::SAMPLE_RATE_HZ, cfg::CHANNELS,
                  cfg::BITS_PER_SAMPLE, (double)cfg::AUDIO_GAIN,
                  (unsigned)cfg::DMA_FRAME_NUM);

    wifi_mgr::connect();        // blocks until associated or reboots
    pdm::init();                // starts DMA capture (+ warm-up)
    streamer::start();          // listens on TCP + spawns audio task
}

void loop() {
    wifi_mgr::tick();           // reconnect if dropped, otherwise no-op
    streamer::pollAccept();     // accept / clean up TCP clients
    delay(20);
}
