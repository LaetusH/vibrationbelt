namespace DebugClient.Services;

/// Configuration bound from appsettings.json (Belt section).
public sealed class BeltOptions
{
    public string EspIp          { get; set; } = "10.8.5.177";
    public int    EspPort        { get; set; } = 4444;
    public int    SampleRate     { get; set; } = 16000;
    public int    Channels       { get; set; } = 2;
    public double BaselineMeters { get; set; } = 0.20;
}
