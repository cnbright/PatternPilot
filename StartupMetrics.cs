using System.Diagnostics;

namespace PatternPilot;

internal static class StartupMetrics
{
    private static readonly Stopwatch Stopwatch = Stopwatch.StartNew();
    private static readonly object Sync = new();
    private static bool shownLogged;
    private static bool firstFrameLogged;

    public static void Initialize()
    {
        _ = Stopwatch.Elapsed;
    }

    public static void MarkShown()
    {
        lock (Sync)
        {
            if (shownLogged)
            {
                return;
            }

            shownLogged = true;
            WriteLine($"shown_ms={Stopwatch.Elapsed.TotalMilliseconds:F2}");
        }
    }

    public static void MarkFirstFrame()
    {
        lock (Sync)
        {
            if (firstFrameLogged)
            {
                return;
            }

            firstFrameLogged = true;
            WriteLine($"first_frame_ms={Stopwatch.Elapsed.TotalMilliseconds:F2}");
        }
    }

    private static void WriteLine(string line)
    {
        try
        {
            var dir = Path.Combine(Path.GetTempPath(), "PatternPilot");
            Directory.CreateDirectory(dir);
            var path = Path.Combine(dir, "startup_metrics.log");
            File.AppendAllText(path, $"{DateTime.UtcNow:O} {line}{Environment.NewLine}");
        }
        catch
        {
        }
    }
}
