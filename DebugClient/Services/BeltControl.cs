using System.Net;
using System.Net.Sockets;
using System.Text;
using Microsoft.Extensions.Options;

namespace DebugClient.Services;

/// <summary>
/// Sends per-motor strength commands ("MOT1" + N×u8 in 0..100) to the
/// ESP32 over UDP on the same port as the audio stream. Fire-and-forget;
/// the firmware does not ack and does not subscribe the sender to audio.
/// </summary>
public sealed class BeltControl : IDisposable
{
    private static readonly byte[] Magic = Encoding.ASCII.GetBytes("MOT1");

    private readonly BeltOptions _opts;
    private readonly ILogger<BeltControl> _log;
    private readonly UdpClient _udp;
    private readonly IPEndPoint _server;
    private readonly byte[] _last;

    public BeltControl(IOptions<BeltOptions> opts, ILogger<BeltControl> log)
    {
        _opts = opts.Value;
        _log = log;
        _udp = new UdpClient();
        _server = new IPEndPoint(IPAddress.Parse(_opts.EspIp), _opts.EspPort);
        _last = new byte[2];   // motor count is fixed at 2 on the firmware
    }

    /// <summary>
    /// Read-only snapshot of the most recent values sent (one per motor).
    /// Used by the UI to render slider positions across page reloads.
    /// </summary>
    public IReadOnlyList<byte> LastSent => _last;

    /// <summary>
    /// Send strengths (0..100) for each motor, in order. Pass fewer than
    /// the firmware's motor count to leave the rest unchanged on the device.
    /// </summary>
    public void Set(params int[] strengths)
    {
        var payload = new byte[Magic.Length + strengths.Length];
        Buffer.BlockCopy(Magic, 0, payload, 0, Magic.Length);
        for (int i = 0; i < strengths.Length; i++)
        {
            int v = Math.Clamp(strengths[i], 0, 100);
            payload[Magic.Length + i] = (byte)v;
            if (i < _last.Length) _last[i] = (byte)v;
        }
        try
        {
            _udp.Send(payload, payload.Length, _server);
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex, "motor send to {Server} failed", _server);
        }
    }

    public void Stop() => Set(0, 0);

    public void Dispose() => _udp.Dispose();
}
