# PatternPilot

PatternPilot is a native Windows fullscreen display-pattern utility for panel validation, image review, and Crosstalk testing.

## Highlights

- Native WinForms implementation focused on fast startup and low rendering overhead
- Fullscreen pattern presentation across multiple monitors
- Built-in grayscale, checkerboard, align, gradients, lines, dot patterns, Crosstalk, image mode, and One Third
- PNG export of the current view
- Crosshair tool for pixel and line positioning

## Screenshots

Home screen:

![Home Screen](docs/screenshots/home.png)

Checkerboard pattern:

![Checkerboard](docs/screenshots/checkerboard.png)

More screenshots: [docs/screenshots.md](docs/screenshots.md)

## Keyboard Shortcuts

- `Esc`: exit
- `Tab`: switch monitor
- `Ctrl+S`: save current screen as PNG
- `Ctrl+R`: flip current pattern
- `Ctrl+F`: toggle crosshair
- `Up` / `Down`: change level
- `Shift + Up` / `Shift + Down`: fast level step
- `Home` / `End`: set level to `255` / `0`
- `1-8`: switch color mode
- `Ctrl+1` / `Ctrl+2`: load Crosstalk images in Crosstalk mode

## Build

Requirements:

- Windows
- .NET 8 SDK

Build:

```powershell
dotnet build PatternPilot\PatternPilot.csproj -c Release
```

Publish directory build:

```powershell
powershell -ExecutionPolicy Bypass -File PatternPilot\publish.ps1 -Mode dir
```

Publish single-file build:

```powershell
powershell -ExecutionPolicy Bypass -File PatternPilot\publish.ps1 -Mode single
```

## Project Structure

- [PatternPilot/PatternPilot.csproj](PatternPilot/PatternPilot.csproj): native project file
- [PatternPilot/PatternForm.cs](PatternPilot/PatternForm.cs): core UI, rendering, patterns, input handling
- [PatternPilot/StartupMetrics.cs](PatternPilot/StartupMetrics.cs): startup timing logger
- [PatternPilot/publish.ps1](PatternPilot/publish.ps1): publish helper
- [PatternPilot/measure_startup.ps1](PatternPilot/measure_startup.ps1): startup measurement helper

## Notes

- The default home screen contains a built-in Chinese usage guide.
- `One Third` now renders as `1/3` white and `2/3` black.
- The repository also keeps the original Python reference implementation in [main.py](main.py).
