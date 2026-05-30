#!/usr/bin/env -S dotnet run
// Receive.cs — .NET 10 file-based script that subscribes to the ESP32 mic
// node over UDP, strips AUD1 framing, and either writes a WAV file or
// pipes raw PCM to stdout for live playback through ffplay.
//
// Why UDP? See firmware/src/audio_streamer.h. TL;DR: TCP head-of-line
// blocking stalls live audio for seconds when WiFi loses a packet.
//
// Subscribe protocol:
//   Send any UDP datagram to the ESP32's STREAM_PORT — our source ip:port
//   becomes the subscriber. Resend every ~1 s as keepalive (ESP32 drops
//   subscribers idle for 5 s).
//
// Usage:
//   dotnet run client/Receive.cs -- <ip>                                # → test.wav
//   dotnet run client/Receive.cs -- <ip> --out belt.wav --seconds 30
//   dotnet run client/Receive.cs -- <ip> --stdout | \
//       ffplay -f s16le -ar 16000 -ch_layout mono -nodisp -autoexit \
//              -fflags nobuffer -flags low_delay -framedrop \
//              -probesize 32 -analyzeduration 0 -

using System;
using System.Buffers.Binary;
using System.IO;
using System.Net;
using System.Net.Sockets;

const int SAMPLE_RATE       = 16000;
const int CHANNELS          = 2;     // must match firmware cfg::CHANNELS
const int BYTES_PER_SAMPLE  = 2;
const int BYTES_PER_FRAME   = CHANNELS * BYTES_PER_SAMPLE;
const int KEEPALIVE_INTERVAL_MS = 1000;

// ─── CLI ──────────────────────────────────────────────────────────────────

if (args.Length == 0 || args[0] is "-h" or "--help")
{
    Console.Error.WriteLine(
        "usage: dotnet run Receive.cs -- <esp32-ip> [options]\n" +
        "  --port <n>      UDP port (default 4444)\n" +
        "  --out <path>    output WAV (default test.wav, ignored with --stdout)\n" +
        "  --stdout        write raw PCM to stdout instead of a WAV\n" +
        "  --seconds <s>   record for s seconds (default 10; 0 = until Ctrl-C)\n" +
        "  --gain <x>      additional client-side gain on top of cfg::AUDIO_GAIN\n");
    return 1;
}

string ip = args[0];
int    port = 4444;
string outPath = "test.wav";
bool   toStdout = false;
double seconds = 10.0;
double gain    = 1.0;

for (int i = 1; i < args.Length; i++)
{
    var inv = System.Globalization.CultureInfo.InvariantCulture;
    switch (args[i])
    {
        case "--port":     port     = int.Parse(args[++i]); break;
        case "--out":      outPath  = args[++i]; break;
        case "--stdout":   toStdout = true; break;
        case "--seconds":  seconds  = double.Parse(args[++i], inv); break;
        case "--gain":     gain     = double.Parse(args[++i], inv); break;
        default:
            Console.Error.WriteLine($"unknown arg: {args[i]}");
            return 2;
    }
}

// ─── Subscribe ────────────────────────────────────────────────────────────

var server = new IPEndPoint(IPAddress.Parse(ip), port);
using var udp = new UdpClient();
udp.Client.ReceiveBufferSize = 256 * 1024;
udp.Client.ReceiveTimeout = 2000;          // ms
udp.Send(new byte[] { 0 }, 1, server);
Log($"subscribed to {server} via UDP");

var keepaliveTimer = System.Diagnostics.Stopwatch.StartNew();

// ─── Output sink ──────────────────────────────────────────────────────────

Stream sink;
FileStream? wavFile = null;
if (toStdout)
{
    sink = Console.OpenStandardOutput();
}
else
{
    wavFile = File.Create(outPath);
    WriteWavHeader(wavFile, dataLen: 0);   // patched at the end
    sink = wavFile;
}

// ─── Receive loop ─────────────────────────────────────────────────────────

int[]  peaks = new int[CHANNELS];
long[] ssqs  = new long[CHANNELS];

uint  expectedSeq = 0;
bool  haveSeq = false;
long  totalFrames = 0;
int   pkts = 0, drops = 0;
long  totalAudioBytes = 0;

var start = DateTime.UtcNow;
var lastReport = start;

using var cts = new System.Threading.CancellationTokenSource();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; cts.Cancel(); };

try
{
    while (!cts.IsCancellationRequested)
    {
        // Keepalive
        if (keepaliveTimer.ElapsedMilliseconds >= KEEPALIVE_INTERVAL_MS)
        {
            udp.Send(new byte[] { 0 }, 1, server);
            keepaliveTimer.Restart();
        }

        byte[] datagram;
        try
        {
            IPEndPoint? remote = null;
            datagram = udp.Receive(ref remote);
        }
        catch (SocketException ex) when (ex.SocketErrorCode == SocketError.TimedOut)
        {
            if (pkts == 0) Log("no data yet... is the ESP32 reachable?");
            else            Log("no packet for 2 s — link stalled?");
            if (seconds > 0 && (DateTime.UtcNow - start).TotalSeconds >= seconds) break;
            continue;
        }

        const int HEADER_LEN = 8;
        if (datagram.Length < HEADER_LEN) continue;
        if (datagram[0] != (byte)'A' || datagram[1] != (byte)'U' ||
            datagram[2] != (byte)'D' || datagram[3] != (byte)'1') continue;

        uint seq        = BinaryPrimitives.ReadUInt32LittleEndian(datagram.AsSpan(4));
        int  payloadLen = ((datagram.Length - HEADER_LEN) / BYTES_PER_FRAME) * BYTES_PER_FRAME;
        if (payloadLen <= 0) continue;
        uint nSamp      = (uint)(payloadLen / BYTES_PER_FRAME);

        if (haveSeq && seq != expectedSeq)
        {
            uint missed = unchecked(seq - expectedSeq);
            // UDP can reorder; treat huge jumps as reordered stale packets.
            if (missed > 0 && missed < 1000) drops += (int)missed;
        }
        expectedSeq = unchecked(seq + 1);
        haveSeq = true;

        var payload = new byte[payloadLen];
        Buffer.BlockCopy(datagram, HEADER_LEN, payload, 0, payloadLen);

        if (gain != 1.0)
        {
            // `.AsSpan()` is required: passing `payload` directly resolves
            // to the ReadOnlySpan overload on .NET 10, which makes the
            // span[i] = ... assignment below a compile error.
            var span = System.Runtime.InteropServices.MemoryMarshal.Cast<byte, short>(
                payload.AsSpan());
            for (int i = 0; i < span.Length; i++)
            {
                int v = (int)(span[i] * gain);
                if (v >  32767) v =  32767;
                else if (v < -32768) v = -32768;
                span[i] = (short)v;
            }
        }

        sink.Write(payload, 0, payloadLen);
        if (toStdout) sink.Flush();

        totalFrames += nSamp;
        totalAudioBytes += payloadLen;
        pkts++;

        var now = DateTime.UtcNow;
        if ((now - lastReport).TotalSeconds >= 0.5)
        {
            Array.Clear(peaks);
            Array.Clear(ssqs);
            var pcm = System.Runtime.InteropServices.MemoryMarshal.Cast<byte, short>(
                payload.AsSpan());
            int frames = pcm.Length / CHANNELS;
            for (int i = 0; i < pcm.Length; i += CHANNELS)
                for (int ch = 0; ch < CHANNELS; ch++)
                {
                    int v = pcm[i + ch];
                    int a = v < 0 ? -v : v;
                    if (a > peaks[ch]) peaks[ch] = a;
                    ssqs[ch] += (long)v * v;
                }
            double kbps = totalAudioBytes / (now - start).TotalSeconds / 1024 * 8;
            var sb = new System.Text.StringBuilder();
            for (int ch = 0; ch < CHANNELS; ch++)
            {
                if (ch > 0) sb.Append("  ");
                char tag = CHANNELS == 2 ? "LR"[ch] : 'M';
                double rms = Math.Sqrt(ssqs[ch] / (double)frames);
                sb.Append($"{tag} peak={peaks[ch],5} rms={rms,6:0}");
            }
            Log($"pkt={pkts,5} seq={seq,6} drops={drops,3}  {sb}  {kbps,5:0} kbps");
            lastReport = now;
        }

        if (seconds > 0 && (now - start).TotalSeconds >= seconds) break;
    }
}
catch (OperationCanceledException) { Log("interrupted"); }
catch (IOException ex)              { Log($"io: {ex.Message}"); }
finally
{
    sink.Flush();
    if (wavFile is not null)
    {
        long dataLen = wavFile.Position - 44;
        wavFile.Position = 0;
        WriteWavHeader(wavFile, dataLen);
        wavFile.Dispose();
    }
}

var elapsed = (DateTime.UtcNow - start).TotalSeconds;
Log($"done: {pkts} packets, {totalAudioBytes / 1024.0:0.0} KB audio in {elapsed:0.0}s, drops={drops}");
if (elapsed > 0 && pkts > 1)
{
    // Wall-clock based: includes link jitter, so it's coarser than the
    // old esp_timer_get_time() measurement but doesn't need a header field.
    double rate = totalFrames / elapsed;
    Log($"*measured* capture rate: {rate:0.0} Hz (configured {SAMPLE_RATE} Hz, ratio {rate / SAMPLE_RATE:0.0000})");
}
return 0;

// ─── Helpers ──────────────────────────────────────────────────────────────

void Log(string s) => Console.Error.WriteLine($"[recv] {s}");

static void WriteWavHeader(Stream s, long dataLen)
{
    int byteRate     = SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE;
    short blockAlign = (short)(CHANNELS * BYTES_PER_SAMPLE);
    int chunkSize    = (int)(36 + dataLen);

    Span<byte> h = stackalloc byte[44];
    System.Text.Encoding.ASCII.GetBytes("RIFF").CopyTo(h.Slice(0, 4));
    BinaryPrimitives.WriteInt32LittleEndian(h.Slice(4, 4), chunkSize);
    System.Text.Encoding.ASCII.GetBytes("WAVE").CopyTo(h.Slice(8, 4));
    System.Text.Encoding.ASCII.GetBytes("fmt ").CopyTo(h.Slice(12, 4));
    BinaryPrimitives.WriteInt32LittleEndian(h.Slice(16, 4), 16);
    BinaryPrimitives.WriteInt16LittleEndian(h.Slice(20, 2), 1);            // PCM
    BinaryPrimitives.WriteInt16LittleEndian(h.Slice(22, 2), (short)CHANNELS);
    BinaryPrimitives.WriteInt32LittleEndian(h.Slice(24, 4), SAMPLE_RATE);
    BinaryPrimitives.WriteInt32LittleEndian(h.Slice(28, 4), byteRate);
    BinaryPrimitives.WriteInt16LittleEndian(h.Slice(32, 2), blockAlign);
    BinaryPrimitives.WriteInt16LittleEndian(h.Slice(34, 2), (short)(BYTES_PER_SAMPLE * 8));
    System.Text.Encoding.ASCII.GetBytes("data").CopyTo(h.Slice(36, 4));
    BinaryPrimitives.WriteInt32LittleEndian(h.Slice(40, 4), (int)dataLen);
    s.Write(h);
}
