using Microsoft.AspNetCore.Mvc;
using DebugClient.Services;

namespace DebugClient.Components;

/// <summary>
/// REST API for external access to audio data (e.g., Python analysis pipeline).
/// </summary>
[ApiController]
[Route("api/audio")]
public class AudioApiController : ControllerBase
{
    private readonly MicReceiver _micReceiver;
    private readonly ILogger<AudioApiController> _logger;

    public AudioApiController(
        MicReceiver micReceiver,
        ILogger<AudioApiController> logger)
    {
        _micReceiver = micReceiver;
        _logger = logger;
    }

    /// <summary>
    /// Get current status of audio reception.
    /// </summary>
    [HttpGet("status")]
    public IActionResult GetStatus()
    {
        return Ok(new
        {
            isReceiving = _micReceiver.IsReceiving,
            packetsReceived = _micReceiver.Packets,
            droppedPackets = _micReceiver.Dropped,
            lastPacketAgoMs = _micReceiver.SinceLastPacket.TotalMilliseconds,
            espIp = _micReceiver.EspIp,
            espPort = _micReceiver.EspPort,
            lastError = _micReceiver.LastError,
        });
    }

    /// <summary>
    /// Get a snapshot of recent audio samples from both channels.
    /// 
    /// Query params:
    ///   samples: number of samples per channel (default: 16000 = 1 second at 16kHz)
    /// </summary>
    [HttpGet("snapshot")]
    public IActionResult GetSnapshot([FromQuery] int samples = 16000)
    {
        if (samples < 100 || samples > 160000)
        {
            return BadRequest(new { error = "samples must be between 100 and 160000" });
        }

        var snapshot = _micReceiver.Snapshot(samples);
        
        if (snapshot == null)
        {
            return StatusCode(503, new { error = "No audio data available yet" });
        }

        // Convert to float32 (normalized -1..+1) for Python
        var channels = new List<float[]>();
        foreach (var channel in snapshot)
        {
            var floats = channel.Select(s => s / 32768f).ToArray();
            channels.Add(floats);
        }

        return Ok(new
        {
            channels = channels,
            sampleCount = snapshot[0].Length,
            sampleRate = 16000,
            channelCount = snapshot.Length,
            timestamp = DateTime.UtcNow.ToString("O"),
        });
    }

    /// <summary>
    /// Get last N milliseconds of audio from both channels.
    /// 
    /// Query params:
    ///   durationMs: duration in milliseconds (default: 500)
    /// </summary>
    [HttpGet("last")]
    public IActionResult GetLastDuration([FromQuery] int durationMs = 500)
    {
        if (durationMs < 10 || durationMs > 5000)
        {
            return BadRequest(new { error = "durationMs must be between 10 and 5000" });
        }

        int samples = (durationMs * 16000) / 1000;
        var snapshot = _micReceiver.Snapshot(samples);
        
        if (snapshot == null)
        {
            return StatusCode(503, new { error = "No audio data available yet" });
        }

        var channels = new List<float[]>();
        foreach (var channel in snapshot)
        {
            var floats = channel.Select(s => s / 32768f).ToArray();
            channels.Add(floats);
        }

        return Ok(new
        {
            channels = channels,
            durationMs = durationMs,
            sampleCount = snapshot[0].Length,
            sampleRate = 16000,
            channelCount = snapshot.Length,
        });
    }

    /// <summary>
    /// Health check endpoint.
    /// </summary>
    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new { status = "ok", timestamp = DateTime.UtcNow });
    }
}
