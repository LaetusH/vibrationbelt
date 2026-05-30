// pdm_capture.h — stereo PDM-RX capture using the ESP-IDF v5 i2s driver.
//
// Why the new driver and not the legacy driver/i2s.h?
//   The legacy driver on classic ESP32 has two bugs that bit us hard:
//     1. Its PDM clock divider miscomputes for most non-trivial sample
//        rates (we observed 48 kHz becoming ~38.7 kHz, and with APLL
//        disabled, ~12.5 kHz).
//     2. In stereo PDM RX mode it duplicates one mic's data into both
//        channels — effectively giving you mono with a stereo memcpy.
//
//   The new driver (driver/i2s_pdm.h, ESP-IDF v5+) computes the divider
//   correctly and supports real stereo PDM RX on classic ESP32.

#pragma once

#include <cstddef>
#include <cstdint>

namespace pdm {

/// Initialize the PDM RX peripheral. Call once during setup().
/// Aborts on failure (via ESP_ERROR_CHECK) — there is no graceful
/// recovery from a misconfigured I²S peripheral.
void init();

/// Block until `bytes` of interleaved L,R int16 samples have been
/// captured. Returns the number of bytes actually written into `dst`
/// (normally exactly `bytes` unless the peripheral was torn down).
/// Returns 0 immediately if the channel is suspended (see suspend()).
size_t read(void* dst, size_t bytes);

/// Stop the DMA / disable the PDM channel. Used to silence the mics while
/// the vibration motors run — the motor current pulses corrupt the mic
/// rail and can wedge the I²S peripheral. The channel stays initialized;
/// resume() brings it back. No-op if already suspended.
///
/// MUST be called from the same task that calls read() — the driver does
/// not tolerate disabling a channel mid-read from another core.
void suspend();

/// Re-enable the channel after suspend() and discard the startup transient
/// (same warm-up drain as init()). No-op if already running.
/// Same threading rule as suspend().
void resume();

/// True while the channel is enabled and read() will block for samples.
bool isRunning();

}  // namespace pdm
