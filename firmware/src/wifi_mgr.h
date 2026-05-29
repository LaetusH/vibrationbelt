// wifi_mgr.h — bring up and maintain STA-mode WiFi with verbose
// diagnostics. After connect(), call tick() periodically from the
// Arduino loop() to handle reconnects without rebooting.

#pragma once

namespace wifi_mgr {

/// Scan + connect to the SSID configured in config.h. Reboots the chip
/// if the *initial* association times out.
void connect();

/// Cheap health-check + auto-reconnect. Call from loop().
/// If WiFi has dropped, kicks off a reconnect attempt; otherwise no-op.
void tick();

}  // namespace wifi_mgr
