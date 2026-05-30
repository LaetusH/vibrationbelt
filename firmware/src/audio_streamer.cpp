#include "audio_streamer.h"

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <esp_timer.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "config.h"
#include "motoren.h"
#include "pdm_capture.h"
#include "protocol.h"

namespace streamer {
namespace {

WiFiUDP g_udp;

// Current subscriber. Volatile because audioTask reads it on core 1 while
// pollAccept() (core 0) writes it. Single producer / single consumer means
// torn reads of IPAddress are theoretically possible but practically benign
// (worst case: one packet sent to an old destination).
volatile uint32_t g_sub_ip       = 0;       // IPv4 as uint32, 0 = no subscriber
volatile uint16_t g_sub_port     = 0;
volatile uint32_t g_sub_last_ms  = 0;

constexpr size_t BYTES_PER_FRAME = cfg::CHANNELS * sizeof(int16_t);
constexpr size_t AUDIO_BYTES     = cfg::DMA_FRAME_NUM * BYTES_PER_FRAME;
constexpr size_t PACKET_BYTES    = sizeof(proto::PacketHeader) + AUDIO_BYTES;

static_assert(PACKET_BYTES <= 1472,
              "Packet exceeds typical Ethernet MTU minus UDP/IP headers; "
              "reduce cfg::DMA_FRAME_NUM to avoid IP fragmentation.");

/// In-place DC removal followed by saturating int16 gain.
///
/// One-pole IIR high-pass at ≈12 Hz removes the PDM mic's DC bias before
/// gain; without it, even small gain pegs every sample at −32768.
///
/// Filter state is per-channel (CHANNELS independent histories), persists
/// between calls — do NOT reset per buffer. `samples` is interleaved
/// L,R,L,R,… for stereo.
inline void dcBlockAndGain(int16_t* samples, size_t n_samples) {
    constexpr float ALPHA = 0.995f;
    constexpr float GAIN  = cfg::AUDIO_GAIN;

    static float prev_x[cfg::CHANNELS] = {};
    static float prev_y[cfg::CHANNELS] = {};

    for (size_t i = 0; i < n_samples; ++i) {
        const int ch = i % cfg::CHANNELS;
        const float x = static_cast<float>(samples[i]);
        const float y = ALPHA * (prev_y[ch] + x - prev_x[ch]);
        prev_x[ch] = x;
        prev_y[ch] = y;

        float v = y * GAIN;
        if (v >  32767.0f) v =  32767.0f;
        if (v < -32768.0f) v = -32768.0f;
        samples[i] = static_cast<int16_t>(v);
    }
}

[[noreturn]] void audioTask(void*) {
    // [PacketHeader | audio] in one contiguous buffer, sent in one UDP send.
    alignas(4) static uint8_t packet[PACKET_BYTES];
    auto* hdr   = reinterpret_cast<proto::PacketHeader*>(packet);
    auto* audio = reinterpret_cast<int16_t*>(packet + sizeof(proto::PacketHeader));

    uint32_t seq = 0;
    uint64_t last_report_us = esp_timer_get_time();
    uint32_t pkts_since_report = 0;
    uint32_t fails_since_report = 0;

    Serial.printf("[audio] task on core %d  packet=%u B (hdr %u + audio %u)\n",
                  xPortGetCoreID(),
                  (unsigned)PACKET_BYTES,
                  (unsigned)sizeof(proto::PacketHeader),
                  (unsigned)AUDIO_BYTES);

    for (;;) {
        const uint64_t t_us = esp_timer_get_time();
        const size_t got = pdm::read(audio, AUDIO_BYTES);
        if (got == 0) continue;

        dcBlockAndGain(audio, got / sizeof(int16_t));

        // Keep DMA in lock-step with realtime even when nobody's listening.
        // We don't mutate g_sub_ip from here (that's pollAccept's job on
        // the other core); we just gate sending on freshness.
        static bool expired_logged = false;
        const uint32_t sub_ip   = g_sub_ip;
        const uint16_t sub_port = g_sub_port;
        const bool fresh = sub_ip != 0
            && (millis() - g_sub_last_ms) < cfg::UDP_SUBSCRIBER_TIMEOUT_MS;
        if (!fresh) {
            if (sub_ip != 0 && !expired_logged) {
                Serial.println("[udp] subscriber expired (no keepalive)");
                expired_logged = true;
            }
            continue;
        }
        expired_logged = false;

        memcpy(hdr->magic, proto::MAGIC, 4);
        hdr->seq    = seq++;

        const size_t total = sizeof(proto::PacketHeader) + got;
        IPAddress dst(sub_ip);
        g_udp.beginPacket(dst, sub_port);
        g_udp.write(packet, total);
        // endPacket() returns 1 on success, 0 on failure. On a weak link
        // it fails with ENOMEM (lwIP TX buffers exhausted). For live audio
        // that's fine — we drop this packet and keep going; the receiver's
        // sequence numbers show it as a drop. We count failures and report
        // them in the throttled stat line below rather than logging each
        // one (per-failure logging would flood the UART and stall us).
        if (g_udp.endPacket() == 1) {
            pkts_since_report++;
        } else {
            fails_since_report++;
            // ENOMEM: lwIP TX buffers are exhausted (weak/congested link).
            // Yield ~2 ms so the WiFi TX path can drain before the next
            // attempt. Without this we tight-loop re-failing while the
            // buffers stay full, which keeps the link wedged. We're
            // dropping this packet regardless, so the delay is harmless.
            vTaskDelay(pdMS_TO_TICKS(2));
        }

        if (t_us - last_report_us > 1'000'000) {
            const float secs = (t_us - last_report_us) / 1e6f;
            const int rssi = WiFi.RSSI();
            Serial.printf(
                "[audio] seq=%u  %.0f sent/s  %.0f failed/s  RSSI=%d%s  sub=%s:%u\n",
                (unsigned)seq,
                pkts_since_report / secs,
                fails_since_report / secs,
                rssi,
                rssi < -75 ? " (WEAK! move closer to AP)" : "",
                dst.toString().c_str(),
                (unsigned)sub_port);
            pkts_since_report = 0;
            fails_since_report = 0;
            last_report_us = t_us;
        }
    }
}

}  // namespace

void start() {
    if (!g_udp.begin(cfg::STREAM_PORT)) {
        Serial.println("[udp] FAILED to bind socket");
    } else {
        Serial.printf("[udp] listening on %s:%u  (send any UDP packet here "
                      "to subscribe)\n",
                      WiFi.localIP().toString().c_str(), cfg::STREAM_PORT);
    }

    xTaskCreatePinnedToCore(
        audioTask, "audio",
        cfg::AUDIO_TASK_STACK, /*arg*/ nullptr,
        cfg::AUDIO_TASK_PRIORITY, /*handle*/ nullptr,
        cfg::AUDIO_TASK_CORE);
}

void pollAccept() {
    // Drain any incoming UDP packets. Two kinds:
    //   - MOT1-prefixed motor command: dispatch to motoren, DO NOT subscribe
    //     (the controller and the audio listener can be different clients).
    //   - Anything else (incl. the typical 1-byte ping): treat as audio
    //     subscribe / keepalive.
    while (true) {
        int n = g_udp.parsePacket();
        if (n <= 0) break;

        // Capture the first chunk so we can sniff for MOT1; drain the rest.
        uint8_t buf[64];
        size_t read_total = 0;
        if (g_udp.available() > 0) {
            int got = g_udp.read(buf, sizeof(buf));
            if (got > 0) read_total = (size_t)got;
        }
        while (g_udp.available() > 0) {
            uint8_t scratch[64];
            g_udp.read(scratch, sizeof(scratch));
        }

        if (read_total >= 4 + 1 &&
            memcmp(buf, proto::MOTOR_MAGIC, 4) == 0) {
            // MOT1 + per-motor byte (0..100). Extra trailing bytes ignored,
            // missing trailing bytes leave that motor untouched.
            size_t n_vals = read_total - 4;
            if (n_vals > (size_t)MOTOR_COUNT) n_vals = MOTOR_COUNT;
            for (size_t i = 0; i < n_vals; ++i) {
                motor_setzen((int)i, (int)buf[4 + i]);
            }
            continue;
        }

        const IPAddress src = g_udp.remoteIP();
        const uint16_t srcPort = g_udp.remotePort();
        const uint32_t now = millis();

        const uint32_t new_ip = (uint32_t)src;
        const bool new_sub = (new_ip != g_sub_ip) || (srcPort != g_sub_port);

        g_sub_ip = new_ip;
        g_sub_port = srcPort;
        g_sub_last_ms = now;

        if (new_sub) {
            Serial.printf("[udp] subscriber: %s:%u\n", src.toString().c_str(), (unsigned)srcPort);
        }
    }
}

}  // namespace streamer
