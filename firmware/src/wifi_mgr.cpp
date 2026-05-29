#include "wifi_mgr.h"

#include <Arduino.h>
#include <WiFi.h>

#include "config.h"

namespace wifi_mgr {
namespace {

uint32_t g_last_reconnect_attempt_ms = 0;
constexpr uint32_t RECONNECT_INTERVAL_MS = 5'000;

/// Pretty-print the wl_status_t enum so logs are debuggable without
/// grepping for magic numbers.
const char* statusStr(wl_status_t s) {
    switch (s) {
        case WL_IDLE_STATUS:     return "IDLE";
        case WL_NO_SSID_AVAIL:   return "NO_SSID_AVAIL (SSID not in range)";
        case WL_SCAN_COMPLETED:  return "SCAN_COMPLETED";
        case WL_CONNECTED:       return "CONNECTED";
        case WL_CONNECT_FAILED:  return "CONNECT_FAILED";
        case WL_CONNECTION_LOST: return "CONNECTION_LOST";
        case WL_DISCONNECTED:    return "DISCONNECTED";
        case WL_NO_SHIELD:       return "NO_SHIELD";
        default:                 return "UNKNOWN";
    }
}

/// Background WiFi events. Mostly used so we can see disconnect
/// *reason codes* — much more actionable than `WL_DISCONNECTED`.
void onEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
    switch (event) {
        case ARDUINO_EVENT_WIFI_STA_START:
            Serial.println("[wifi] STA start");
            break;
        case ARDUINO_EVENT_WIFI_STA_CONNECTED:
            Serial.println("[wifi] associated with AP");
            break;
        case ARDUINO_EVENT_WIFI_STA_GOT_IP:
            Serial.printf("[wifi] got IP: %s\n",
                          WiFi.localIP().toString().c_str());
            break;
        case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
            // Common reason codes: 15/202/204 = wrong password,
            // 201 = AP not found, 2/4 = expiry/idle.
            Serial.printf("[wifi] disconnected, reason=%u\n",
                          info.wifi_sta_disconnected.reason);
            break;
        default:
            break;
    }
}

void scanAndLog() {
    Serial.println("[wifi] scanning...");
    int n = WiFi.scanNetworks();
    if (n <= 0) {
        Serial.println("[wifi] no networks visible");
        return;
    }
    Serial.printf("[wifi] %d networks visible:\n", n);
    for (int i = 0; i < n; ++i) {
        Serial.printf("  %2d) %-32s  rssi=%4d dBm  ch=%2d  %s\n",
                      i + 1,
                      WiFi.SSID(i).c_str(),
                      WiFi.RSSI(i),
                      WiFi.channel(i),
                      WiFi.encryptionType(i) == WIFI_AUTH_OPEN ? "OPEN" : "ENC");
    }
}

/// Apply latency- and reliability-oriented WiFi tweaks.
/// Call this once after STA mode is active but before begin().
void tuneForLowLatency() {
    if (cfg::WIFI_DISABLE_POWERSAVE) {
        // Default Arduino mode is WIFI_PS_MIN_MODEM (~150 ms latency
        // spikes). NONE keeps the radio fully active so packets don't
        // queue waiting for the next beacon window.
        WiFi.setSleep(WIFI_PS_NONE);
        Serial.println("[wifi] power save: disabled");
    }
    WiFi.setTxPower(WIFI_POWER_19_5dBm);
    WiFi.setAutoReconnect(true);
}

}  // namespace

void connect() {
    WiFi.disconnect(true, true);          // wipe any stale config
    WiFi.mode(WIFI_STA);
    WiFi.onEvent(onEvent);
    tuneForLowLatency();

    scanAndLog();

    Serial.printf("[wifi] connecting to '%s'...\n", cfg::WIFI_SSID);
    WiFi.begin(cfg::WIFI_SSID, cfg::WIFI_PASS);

    const uint32_t deadline = millis() + cfg::WIFI_TIMEOUT_MS;
    wl_status_t last = static_cast<wl_status_t>(-1);

    while (WiFi.status() != WL_CONNECTED) {
        const wl_status_t s = WiFi.status();
        if (s != last) {
            Serial.printf("\n[wifi] status -> %s\n", statusStr(s));
            last = s;
        } else {
            Serial.print('.');
        }
        if ((int32_t)(millis() - deadline) > 0) {
            Serial.printf("\n[wifi] TIMEOUT, last status: %s. Rebooting...\n",
                          statusStr(WiFi.status()));
            delay(2000);
            ESP.restart();
        }
        delay(250);
    }

    Serial.printf("\n[wifi] OK  IP=%s  RSSI=%d dBm  ch=%d\n",
                  WiFi.localIP().toString().c_str(),
                  WiFi.RSSI(),
                  WiFi.channel());
}

void tick() {
    if (WiFi.status() == WL_CONNECTED) return;

    const uint32_t now = millis();
    if (now - g_last_reconnect_attempt_ms < RECONNECT_INTERVAL_MS) return;
    g_last_reconnect_attempt_ms = now;

    Serial.println("[wifi] link down, reconnecting...");
    WiFi.reconnect();
}

}  // namespace wifi_mgr
