using System.Buffers.Binary;
using System.Net;
using System.Net.Sockets;
using Microsoft.Extensions.Options;

namespace DebugClient.Services;

/// <summary>
/// Background service that subscribes to the ESP32 over UDP, parses AUD1
/// frames, and maintains a 1-second rolling per-channel ring buffer. The
/// Home page snapshots the buffer at ~15 fps for display + DoA.
/// </summary>
public sealed class MicReceiver : BackgroundService
{
    private const int    HeaderLen          = 20;
    private const int    MaxDatagram        = 2048;
    private const double KeepaliveIntervalS = 1.0;
    private static readonly byte[] Magic = "AUD1"u8.ToArray();

    private readonly BeltOptions _opts;
    private readonly ILogger<MicReceiver> _log;

    private readonly object _bufLock = new();
    private readonly short[][] _buffers;
    private int _bufWrite;
    private int _bufLength;

    private long _pkts;
    private long _drops;
    private uint _expectedSeq;
    private bool _haveSeq;
    private int  _lastPacketPeak;
    private DateTime _lastPacketUtc = DateTime.MinValue;
    private string _lastError = "";

    public MicReceiver(IOptions<BeltOptions> opts, ILogger<MicReceiver> log)
    {
        _opts = opts.Value;
        _log = log;
        int cap = _opts.SampleRate;            // 1 s per channel
        _buffers = new short[_opts.Channels][];
        for (int c = 0; c < _opts.Channels; c++)
            _buffers[c] = new short[cap];
    }

    public string EspIp   => _opts.EspIp;
    public int    EspPort => _opts.EspPort;
    public long   Packets => Interlocked.Read(ref _pkts);
    public long   Dropped => Interlocked.Read(ref _drops);
    public int    LastPacketPeak => _lastPacketPeak;
    public bool   IsReceiving => (DateTime.UtcNow - _lastPacketUtc).TotalSeconds < 2.0;
    public string LastError => _lastError;
    public TimeSpan SinceLastPacket =>
        _lastPacketUtc == DateTime.MinValue ? TimeSpan.MaxValue
                                            : DateTime.UtcNow - _lastPacketUtc;

    /// <summary>
    /// Snapshot the most recent samples per channel (chronological order).
    /// Returns whatever is buffered if fewer than requested; null only if
    /// nothing has arrived yet.
    /// </summary>
    public short[][]? Snapshot(int samples)
    {
        lock (_bufLock)
        {
            if (_bufLength == 0) return null;
            int take = Math.Min(samples, _bufLength);
            int cap = _buffers[0].Length;
            int start = (_bufWrite - take + cap) % cap;
            var snap = new short[_opts.Channels][];
            for (int c = 0; c < _opts.Channels; c++)
            {
                snap[c] = new short[take];
                int first = Math.Min(take, cap - start);
                Array.Copy(_buffers[c], start, snap[c], 0, first);
                if (first < take)
                    Array.Copy(_buffers[c], 0, snap[c], first, take - first);
            }
            return snap;
        }
    }

    protected override async Task ExecuteAsync(CancellationToken stop)
    {
        while (!stop.IsCancellationRequested)
        {
            try { await RunOnceAsync(stop); }
            catch (OperationCanceledException) when (stop.IsCancellationRequested) { return; }
            catch (Exception ex)
            {
                _lastError = ex.Message;
                _log.LogError(ex, "receiver loop crashed; restarting in 2 s");
                try { await Task.Delay(TimeSpan.FromSeconds(2), stop); }
                catch (OperationCanceledException) { return; }
            }
        }
    }

    private async Task RunOnceAsync(CancellationToken stop)
    {
        var server = new IPEndPoint(IPAddress.Parse(_opts.EspIp), _opts.EspPort);
        using var udp = new UdpClient();
        udp.Client.ReceiveBufferSize = 256 * 1024;

        await udp.SendAsync(new byte[] { 0 }, server, stop);
        _log.LogInformation("Subscribed to {Server} via UDP", server);

        var lastKeepalive = DateTime.UtcNow;
        while (!stop.IsCancellationRequested)
        {
            if ((DateTime.UtcNow - lastKeepalive).TotalSeconds >= KeepaliveIntervalS)
            {
                await udp.SendAsync(new byte[] { 0 }, server, stop);
                lastKeepalive = DateTime.UtcNow;
            }

            UdpReceiveResult result;
            try
            {
                using var cts = CancellationTokenSource.CreateLinkedTokenSource(stop);
                cts.CancelAfter(TimeSpan.FromSeconds(2));
                result = await udp.ReceiveAsync(cts.Token);
            }
            catch (OperationCanceledException) when (!stop.IsCancellationRequested)
            {
                continue;
            }
            ProcessDatagram(result.Buffer);
        }
    }

    private void ProcessDatagram(byte[] datagram)
    {
        if (datagram.Length < HeaderLen) return;
        if (datagram[0] != Magic[0] || datagram[1] != Magic[1] ||
            datagram[2] != Magic[2] || datagram[3] != Magic[3]) return;

        uint seq   = BinaryPrimitives.ReadUInt32LittleEndian(datagram.AsSpan(4));
        uint nSamp = BinaryPrimitives.ReadUInt32LittleEndian(datagram.AsSpan(16));
        int payload = (int)nSamp * _opts.Channels * sizeof(short);
        if (datagram.Length < HeaderLen + payload) return;

        if (_haveSeq && seq != _expectedSeq)
        {
            uint missed = unchecked(seq - _expectedSeq);
            if (missed is > 0 and < 1000) Interlocked.Add(ref _drops, missed);
        }
        _expectedSeq = unchecked(seq + 1);
        _haveSeq = true;

        var samples = System.Runtime.InteropServices.MemoryMarshal.Cast<byte, short>(
            datagram.AsSpan(HeaderLen, payload));
        int ch = _opts.Channels;
        int peak = 0;
        lock (_bufLock)
        {
            int cap = _buffers[0].Length;
            for (int i = 0; i + ch <= samples.Length; i += ch)
            {
                for (int c = 0; c < ch; c++)
                {
                    short s = samples[i + c];
                    _buffers[c][_bufWrite] = s;
                    int a = s < 0 ? -s : s;
                    if (a > peak) peak = a;
                }
                _bufWrite = (_bufWrite + 1) % cap;
                if (_bufLength < cap) _bufLength++;
            }
        }

        _lastPacketPeak = peak;
        Interlocked.Increment(ref _pkts);
        _lastPacketUtc = DateTime.UtcNow;
    }
}
