namespace PatternPilot;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        StartupMetrics.Initialize();
        ApplicationConfiguration.Initialize();
        Application.Run(new PatternForm());
    }
}
