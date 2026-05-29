namespace DebugClient.Services;

/// <summary>
/// Direction-of-arrival helpers: time-domain cross-correlation between
/// two channels with parabolic sub-sample interpolation.
/// </summary>
/// <remarks>
/// Time-domain (not FFT) on purpose: at a 20 cm baseline / 16 kHz the
/// max lag is only ±~9 samples, so brute force is trivially cheap and
/// keeps the project dependency-free.
/// </remarks>
public static class Doa
{
    public const double SpeedOfSound = 343.0;   // m/s

    /// <summary>
    /// Cross-correlate <paramref name="l"/> against <paramref name="r"/>
    /// over lags in [-maxLag, +maxLag]. Returns (lagSamples, confidence).
    /// Positive lag = source biased toward the R mic.
    /// </summary>
    public static (double LagSamples, double Confidence) CrossCorrelate(
        ReadOnlySpan<short> l, ReadOnlySpan<short> r, int maxLag)
    {
        if (l.Length != r.Length)
            throw new ArgumentException("l and r must have equal length");
        int n = l.Length;
        if (maxLag < 1 || n <= 2 * maxLag) return (0, 0);

        Span<double> corr = stackalloc double[2 * maxLag + 1];
        for (int lag = -maxLag; lag <= maxLag; lag++)
        {
            int start = Math.Max(0, -lag);
            int end   = Math.Min(n, n - lag);
            double sum = 0;
            for (int i = start; i < end; i++)
                sum += (double)l[i] * r[i + lag];
            corr[lag + maxLag] = sum;
        }

        int peakIdx = 0;
        double peakVal = corr[0];
        for (int i = 1; i < corr.Length; i++)
            if (corr[i] > peakVal) { peakVal = corr[i]; peakIdx = i; }

        double lagSamples = peakIdx - maxLag;
        if (peakIdx > 0 && peakIdx < corr.Length - 1)
        {
            double y0 = corr[peakIdx - 1], y1 = corr[peakIdx], y2 = corr[peakIdx + 1];
            double denom = y0 - 2 * y1 + y2;
            if (denom != 0) lagSamples += 0.5 * (y0 - y2) / denom;
        }

        double second = 0;
        int notchLo = Math.Max(0, peakIdx - 2);
        int notchHi = Math.Min(corr.Length, peakIdx + 3);
        for (int i = 0; i < corr.Length; i++)
            if ((i < notchLo || i >= notchHi) && corr[i] > second) second = corr[i];
        double confidence = peakVal > 0 ? 1.0 - Math.Max(0, second) / peakVal : 0;

        // Positive lagSamples means source toward R; return as +angle → flip sign.
        return (-lagSamples, confidence);
    }

    /// <summary>
    /// Convert TDoA (s) + baseline (m) to broadside-referenced angle in
    /// [-90°, +90°]. 0° = source directly ahead.
    /// </summary>
    public static double TdoaToAngleDeg(double tdoaSeconds, double baselineMeters)
    {
        double sin = tdoaSeconds * SpeedOfSound / baselineMeters;
        if (sin >  1) sin =  1;
        if (sin < -1) sin = -1;
        return Math.Asin(sin) * 180.0 / Math.PI;
    }
}
