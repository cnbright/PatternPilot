namespace PatternPilot;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        StartupMetrics.Initialize();
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        ApplicationConfiguration.Initialize();
        Application.Run(new PatternForm());
    }
}
