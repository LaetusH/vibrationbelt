namespace DebugClient.Services;

/// <summary>
/// Direction-of-arrival helpers: GCC-PHAT (Generalized Cross-Correlation
/// with Phase Transform) sub-sample TDoA estimation between two channels.
/// </summary>
/// <remarks>
/// This is the same estimator the Python <c>vibrationbelt</c> reference
/// (<c>client/vibrationbelt/doa.py</c>) uses, ported 1:1 so the Blazor UI
/// and the Python demo agree.
///
/// Why PHAT and not plain cross-correlation? Plain CC peaks wherever the
/// signals' *energies* align, so a DC offset (the PDM mics have one, ×32
/// by AUDIO_GAIN) or a dominant low-frequency band drowns out the actual
/// timing information, and an unnormalized lag sum is biased toward lag 0.
/// PHAT whitens both spectra before correlating, so the peak depends only
/// on phase — which is what carries the inter-mic delay. The DC bin gets
/// whitened to unit magnitude too, so it can no longer pin the peak at 0.
///
/// Dependency-free on purpose (small radix-2 FFT below): the window is
/// only ~512 samples, so cost is negligible.
///
/// Reference: Knapp &amp; Carter, "The generalized correlation method for
/// estimation of time delay", IEEE TASSP, 1976.
/// </remarks>
public static class Doa
{
    public const double SpeedOfSound = 343.0;   // m/s, dry air ~20°C

    /// <summary>
    /// Estimate the inter-channel delay of <paramref name="l"/> relative to
    /// <paramref name="r"/> via GCC-PHAT, searching lags in
    /// [-maxLag, +maxLag]. Returns (lagSamples, confidence).
    ///
    /// A <em>positive</em> lag means the left channel arrived <em>later</em>
    /// than the right — i.e. the source is on the RIGHT mic's side, which
    /// <see cref="TdoaToAngleDeg"/> maps to a positive angle.
    ///
    /// <paramref name="confidence"/> is in [0, 1]: the peak height relative
    /// to the next-best competing peak in the search window. Below ~0.5 the
    /// estimate is unreliable (noise or no real signal).
    /// </summary>
    public static (double LagSamples, double Confidence) CrossCorrelate(
        ReadOnlySpan<short> l, ReadOnlySpan<short> r, int maxLag)
    {
        if (l.Length != r.Length)
            throw new ArgumentException("l and r must have equal length");
        int n = l.Length;
        if (n < 4 || maxLag < 1) return (0, 0);

        // Zero-pad to the next power of two ≥ 2n so the circular FFT
        // correlation doesn't wrap real lags into each other.
        int nfft = 1;
        while (nfft < 2 * n) nfft <<= 1;
        if (maxLag > nfft / 2) maxLag = nfft / 2;

        var xr = new double[nfft];
        var xi = new double[nfft];
        var yr = new double[nfft];
        var yi = new double[nfft];
        for (int i = 0; i < n; i++) { xr[i] = l[i]; yr[i] = r[i]; }

        Fft(xr, xi, inverse: false);
        Fft(yr, yi, inverse: false);

        // R = X · conj(Y), then PHAT whitening R /= |R|. The result of the
        // inverse FFT (real part) is the phase-only cross-correlation.
        for (int k = 0; k < nfft; k++)
        {
            double re = xr[k] * yr[k] + xi[k] * yi[k];   // Re(X·conj(Y))
            double im = xi[k] * yr[k] - xr[k] * yi[k];   // Im(X·conj(Y))
            double mag = Math.Sqrt(re * re + im * im) + 1e-15;
            xr[k] = re / mag;
            xi[k] = im / mag;
        }
        Fft(xr, xi, inverse: true);   // xr now holds cc indexed by lag

        // cc[0] is lag 0; positive lags are xr[d], negative lags wrap to
        // xr[nfft - d]. Gather the search window [-maxLag, +maxLag] into a
        // contiguous region so peak-finding / interpolation mirror the
        // Python reference exactly.
        int span = 2 * maxLag + 1;
        Span<double> region = span <= 256 ? stackalloc double[span] : new double[span];
        for (int j = 0; j < span; j++)
        {
            int lag = j - maxLag;
            int idx = lag >= 0 ? lag : nfft + lag;
            region[j] = xr[idx];
        }

        int peak = 0;
        double peakVal = region[0];
        for (int j = 1; j < span; j++)
            if (region[j] > peakVal) { peakVal = region[j]; peak = j; }

        double lagSamples = peak - maxLag;

        // Parabolic interpolation for sub-sample resolution.
        if (peak > 0 && peak < span - 1)
        {
            double a = region[peak - 1], b = region[peak], c = region[peak + 1];
            double denom = a - 2 * b + c;
            if (denom != 0) lagSamples += 0.5 * (a - c) / denom;
        }

        // Confidence: peak height vs the next-best peak outside a small notch.
        double second = double.NegativeInfinity;
        int notchLo = Math.Max(0, peak - 2);
        int notchHi = Math.Min(span, peak + 3);
        for (int j = 0; j < span; j++)
            if ((j < notchLo || j >= notchHi) && region[j] > second) second = region[j];
        double confidence = peakVal <= 0 ? 0
            : 1.0 - Math.Max(0, double.IsNegativeInfinity(second) ? 0 : second) / peakVal;

        return (lagSamples, confidence);
    }

    /// <summary>
    /// Convert TDoA (s) + baseline (m) to broadside-referenced angle in
    /// [-90°, +90°]. 0° = source directly ahead; positive = toward R.
    /// </summary>
    public static double TdoaToAngleDeg(double tdoaSeconds, double baselineMeters)
    {
        double sin = tdoaSeconds * SpeedOfSound / baselineMeters;
        if (sin >  1) sin =  1;
        if (sin < -1) sin = -1;
        return Math.Asin(sin) * 180.0 / Math.PI;
    }

    /// <summary>
    /// In-place iterative radix-2 Cooley-Tukey FFT. <paramref name="re"/>
    /// and <paramref name="im"/> must have a power-of-two length. With
    /// <paramref name="inverse"/> the result is scaled by 1/N.
    /// </summary>
    private static void Fft(double[] re, double[] im, bool inverse)
    {
        int n = re.Length;
        if (n <= 1) return;

        // Bit-reversal permutation.
        for (int i = 1, j = 0; i < n; i++)
        {
            int bit = n >> 1;
            for (; (j & bit) != 0; bit >>= 1) j ^= bit;
            j ^= bit;
            if (i < j)
            {
                (re[i], re[j]) = (re[j], re[i]);
                (im[i], im[j]) = (im[j], im[i]);
            }
        }

        // Danielson-Lanczos butterflies.
        for (int len = 2; len <= n; len <<= 1)
        {
            double ang = 2 * Math.PI / len * (inverse ? 1 : -1);
            double wRe = Math.Cos(ang), wIm = Math.Sin(ang);
            for (int i = 0; i < n; i += len)
            {
                double curRe = 1, curIm = 0;
                for (int k = 0; k < len / 2; k++)
                {
                    int a = i + k, b = i + k + len / 2;
                    double tRe = re[b] * curRe - im[b] * curIm;
                    double tIm = re[b] * curIm + im[b] * curRe;
                    re[b] = re[a] - tRe; im[b] = im[a] - tIm;
                    re[a] += tRe;        im[a] += tIm;
                    double nextRe = curRe * wRe - curIm * wIm;
                    curIm = curRe * wIm + curIm * wRe;
                    curRe = nextRe;
                }
            }
        }

        if (inverse)
            for (int i = 0; i < n; i++) { re[i] /= n; im[i] /= n; }
    }
}
