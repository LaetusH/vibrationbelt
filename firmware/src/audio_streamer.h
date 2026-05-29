// audio_streamer.h — UDP audio sender.
//
// Why UDP and not TCP?
//   For live audio, TCP is the wrong tool. A single dropped frame stalls
//   every subsequent frame until the retransmit arrives, which sounds
//   like a multi-second freeze followed by a glitch. UDP just drops the
//   one frame — a tiny click — and keeps streaming. With AUD1 sequence
//   numbers the receiver can spot drops and fill / skip as it likes.
//
// Subscription model:
//   - ESP32 binds UDP on cfg::STREAM_PORT.
//   - A client announces itself by sending ANY UDP packet (even 1 byte)
//     to that port. The source IP+port becomes the current subscriber.
//   - The ESP32 streams audio to that subscriber.
//   - Client must re-send a keepalive at least every
//     cfg::UDP_SUBSCRIBER_TIMEOUT_MS or it gets dropped.
//   - One subscriber at a time, last writer wins.

#pragma once

namespace streamer {

void start();        // call once after wifi_mgr::connect() and pdm::init().
void pollAccept();   // call periodically from loop(); drains subscribe packets.

}  // namespace streamer
