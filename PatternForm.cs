using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using Microsoft.Win32;
using System.Runtime.InteropServices;
using System.Windows.Forms;

namespace PatternPilot;

internal enum PatternKind
{
    None,
    Grayscale,
    Checkerboard,
    Align,
    Image,
    LinearGrayscale,
    ColorfulGrayscale,
    WrgbColorbar,
    Mux21,
    Mux22,
    GrayCenter,
    VerticalLine,
    HorizontalLine,
    Dot1,
    Dot2,
    SubDot,
    Crosstalk,
    OneThird
}

internal enum FlipMode
{
    None,
    Horizontal,
    Vertical
}

internal enum CrosshairMode
{
    Cross,
    HorizontalLine,
    VerticalLine,
    Point
}

internal enum BarOrientation
{
    Horizontal,
    Vertical
}

internal sealed class PatternForm : Form
{
    private static readonly int[] CheckerSizes = [2, 4, 5, 8, 16, 32, 64];

    private readonly Stopwatch checkerStopwatch = Stopwatch.StartNew();
    private readonly ContextMenuStrip contextMenu = new();
    private readonly System.Windows.Forms.Timer checkerTimer = new() { Interval = 100 };
    private readonly List<Screen> screens = [];
    private readonly System.Windows.Forms.Timer displayChangeTimer = new() { Interval = 300 };

    private Bitmap? backBuffer;
    private bool renderDirty = true;
    private bool firstFrameLogged;
    private Size lastClientSize;

    private PatternKind pattern = PatternKind.None;
    private int grayLevel = 127;
    private string grayMode = "white";
    private string vlineMode = "1line";
    private string hlineMode = "1line";
    private int monitorIndex;
    private DateTime lastMonitorSwitch = DateTime.MinValue;
    private string? preferredMonitorDeviceName;
    private Rectangle preferredMonitorBounds;
    private bool displayEventsRegistered;
    private bool tabDown;
    private bool showHud = true;
    private bool crosshairEnabled;
    private CrosshairMode crosshairMode = CrosshairMode.Cross;
    private int crosshairX;
    private int crosshairY;
    private string crosshairColorMode = "white";
    private FlipMode flipMode = FlipMode.None;
    private int checkerLevel = 255;
    private string checkerMode = "white";
    private int checkerSizeIndex = 3;
    private int gradientSteps = 256;
    private BarOrientation barOrientation = BarOrientation.Horizontal;
    private Rectangle? crosstalkRect;
    private int crosstalkBgLevel = 127;
    private int crosstalkBlockLevel = 0;
    private string? imagePath;
    private string? crosstalkBackgroundPath;
    private string? crosstalkBlockPath;
    private Image? loadedImage;
    private Bitmap? crosstalkBackgroundImage;
    private Bitmap? crosstalkBlockImage;
    private int imageLoadVersion;
    private int crosstalkBgLoadVersion;
    private int crosstalkBlockLoadVersion;

    public PatternForm()
    {
        DoubleBuffered = true;
        KeyPreview = true;
        BackColor = Color.FromArgb(127, 127, 127);
        Text = "PatternPilot";
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.Manual;
        ShowInTaskbar = true;

        var iconPath = Path.Combine(AppContext.BaseDirectory, "app.ico");
        if (File.Exists(iconPath))
        {
            Icon = new Icon(iconPath);
        }
        else
        {
            Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
        }

        BuildMenu();
        displayChangeTimer.Tick += (_, _) =>
        {
            displayChangeTimer.Stop();
            HandleDisplayTopologyChanged();
        };
        RegisterDisplayChangeHandlers();
        RefreshScreens();
        ApplyMonitor(0);

        checkerTimer.Tick += (_, _) =>
        {
            if (pattern == PatternKind.Checkerboard && showHud && !crosshairEnabled)
            {
                MarkDirty();
            }
        };
        checkerTimer.Start();
    }

    protected override void OnShown(EventArgs e)
    {
        base.OnShown(e);
        StartupMetrics.MarkShown();
        Activate();
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        ScaleOverlayRectsForResize(lastClientSize, ClientSize);
        lastClientSize = ClientSize;
        EnsureBackBuffer();
        ClampCrosstalkRect();
        ReloadScaledAssets();
        MarkDirty();
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        if (e.Button is MouseButtons.Right or MouseButtons.Middle)
        {
            contextMenu.Show(this, e.Location);
        }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        base.OnKeyDown(e);

        if (e.KeyCode == Keys.Escape)
        {
            Close();
            return;
        }

        if (e.KeyCode == Keys.Tab)
        {
            if (!tabDown)
            {
                tabDown = true;
                NextMonitor();
            }
            e.Handled = true;
            return;
        }

        HandleKeyInput(e);
    }

    protected override void OnKeyUp(KeyEventArgs e)
    {
        base.OnKeyUp(e);
        if (e.KeyCode == Keys.Tab)
        {
            tabDown = false;
        }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        if (ClientSize.Width <= 0 || ClientSize.Height <= 0)
        {
            return;
        }

        EnsureBackBuffer();
        if (backBuffer is null)
        {
            return;
        }

        if (renderDirty)
        {
            RenderToBackBuffer(backBuffer);
            renderDirty = false;
        }

        e.Graphics.DrawImageUnscaled(backBuffer, 0, 0);
        if (!firstFrameLogged)
        {
            firstFrameLogged = true;
            StartupMetrics.MarkFirstFrame();
        }
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            UnregisterDisplayChangeHandlers();
            checkerTimer.Dispose();
            displayChangeTimer.Dispose();
            contextMenu.Dispose();
            loadedImage?.Dispose();
            crosstalkBackgroundImage?.Dispose();
            crosstalkBlockImage?.Dispose();
            backBuffer?.Dispose();
        }
        base.Dispose(disposing);
    }

    private void BuildMenu()
    {
        AddMenuItem("Grayscale", (_, _) => SetPattern(PatternKind.Grayscale));
        AddMenuItem("Checkerboard", (_, _) => SetPattern(PatternKind.Checkerboard));
        AddMenuItem("Align", (_, _) => SetPattern(PatternKind.Align));
        AddMenuItem("Image", (_, _) => OpenImage());

        var grayscaleBar = new ToolStripMenuItem("Grayscale");
        var colorfulGrayscale = new ToolStripMenuItem("Colorful Grayscale");
        var grayCenter = new ToolStripMenuItem("Center grayscale");
        foreach (var steps in new[] { 9, 64, 256 })
        {
            grayscaleBar.DropDownItems.Add(steps.ToString(), null, (_, _) => SetGradient(PatternKind.LinearGrayscale, steps));
            colorfulGrayscale.DropDownItems.Add(steps.ToString(), null, (_, _) => SetGradient(PatternKind.ColorfulGrayscale, steps));
            grayCenter.DropDownItems.Add(steps.ToString(), null, (_, _) => SetGradient(PatternKind.GrayCenter, steps));
        }
        contextMenu.Items.Add(grayscaleBar);
        contextMenu.Items.Add(colorfulGrayscale);
        AddMenuItem("WRGB Colorbar", (_, _) => SetPattern(PatternKind.WrgbColorbar));
        var muxPattern = new ToolStripMenuItem("MUX Pattern");
        muxPattern.DropDownItems.Add("MUX2-1", null, (_, _) => SetPattern(PatternKind.Mux21));
        muxPattern.DropDownItems.Add("MUX2-2", null, (_, _) => SetPattern(PatternKind.Mux22));
        contextMenu.Items.Add(muxPattern);
        contextMenu.Items.Add(grayCenter);

        var vline = new ToolStripMenuItem("Vertical line");
        vline.DropDownItems.Add("1line", null, (_, _) => SetVerticalLineMode("1line"));
        vline.DropDownItems.Add("2line", null, (_, _) => SetVerticalLineMode("2line"));
        vline.DropDownItems.Add("subline", null, (_, _) => SetVerticalLineMode("subline"));
        contextMenu.Items.Add(vline);

        var hline = new ToolStripMenuItem("Horizontal line");
        hline.DropDownItems.Add("1line", null, (_, _) => SetHorizontalLineMode("1line"));
        hline.DropDownItems.Add("2line", null, (_, _) => SetHorizontalLineMode("2line"));
        contextMenu.Items.Add(hline);

        AddMenuItem("1dot", (_, _) => SetPattern(PatternKind.Dot1));
        AddMenuItem("2dot", (_, _) => SetPattern(PatternKind.Dot2));
        AddMenuItem("sub dot", (_, _) => SetPattern(PatternKind.SubDot));
        AddMenuItem("CrossTalk", (_, _) => SetPattern(PatternKind.Crosstalk));
        AddMenuItem("one third", (_, _) => SetPattern(PatternKind.OneThird));
        AddMenuItem("Save PNG", (_, _) => SavePattern());
    }

    private void AddMenuItem(string label, EventHandler handler)
    {
        contextMenu.Items.Add(label, null, handler);
    }

    private void RefreshScreens()
    {
        screens.Clear();
        screens.AddRange(Screen.AllScreens.OrderByDescending(screen => screen.Primary));
    }

    private void ApplyMonitor(int index)
    {
        ApplyMonitor(index, rememberPreference: true);
    }

    private void ApplyMonitor(int index, bool rememberPreference)
    {
        if (screens.Count == 0)
        {
            RefreshScreens();
        }
        if (screens.Count == 0)
        {
            return;
        }

        monitorIndex = Math.Clamp(index, 0, screens.Count - 1);
        var screen = screens[monitorIndex];
        var bounds = screen.Bounds;
        if (rememberPreference)
        {
            preferredMonitorDeviceName = screen.DeviceName;
            preferredMonitorBounds = bounds;
        }
        Location = bounds.Location;
        Size = bounds.Size;
        Activate();
        MarkDirty();
    }

    private void NextMonitor()
    {
        if ((DateTime.UtcNow - lastMonitorSwitch).TotalMilliseconds < 300)
        {
            return;
        }

        lastMonitorSwitch = DateTime.UtcNow;
        RefreshScreens();
        if (screens.Count == 0)
        {
            return;
        }

        ApplyMonitor((monitorIndex + 1) % screens.Count);
    }

    private void RegisterDisplayChangeHandlers()
    {
        if (displayEventsRegistered)
        {
            return;
        }

        SystemEvents.DisplaySettingsChanged += OnDisplaySettingsChanged;
        displayEventsRegistered = true;
    }

    private void UnregisterDisplayChangeHandlers()
    {
        if (!displayEventsRegistered)
        {
            return;
        }

        SystemEvents.DisplaySettingsChanged -= OnDisplaySettingsChanged;
        displayEventsRegistered = false;
    }

    private void OnDisplaySettingsChanged(object? sender, EventArgs e)
    {
        QueueDisplayTopologyRefresh();
    }

    private void QueueDisplayTopologyRefresh()
    {
        if (IsDisposed)
        {
            return;
        }

        if (InvokeRequired)
        {
            BeginInvoke(QueueDisplayTopologyRefresh);
            return;
        }

        displayChangeTimer.Stop();
        displayChangeTimer.Start();
    }

    private void HandleDisplayTopologyChanged()
    {
        RefreshScreens();
        if (screens.Count == 0)
        {
            return;
        }

        var preferredIndex = FindPreferredMonitorIndex();
        if (preferredIndex >= 0)
        {
            ApplyMonitor(preferredIndex, rememberPreference: false);
            return;
        }

        var fallbackIndex = screens.FindIndex(screen => screen.Primary);
        if (fallbackIndex < 0)
        {
            fallbackIndex = 0;
        }

        ApplyMonitor(fallbackIndex, rememberPreference: false);
    }

    private int FindPreferredMonitorIndex()
    {
        if (!string.IsNullOrWhiteSpace(preferredMonitorDeviceName))
        {
            var deviceMatch = screens.FindIndex(screen => string.Equals(screen.DeviceName, preferredMonitorDeviceName, StringComparison.OrdinalIgnoreCase));
            if (deviceMatch >= 0)
            {
                return deviceMatch;
            }
        }

        if (preferredMonitorBounds != Rectangle.Empty)
        {
            var boundsMatch = screens.FindIndex(screen => screen.Bounds == preferredMonitorBounds);
            if (boundsMatch >= 0)
            {
                return boundsMatch;
            }
        }

        return -1;
    }

    protected override void WndProc(ref Message m)
    {
        const int WM_DISPLAYCHANGE = 0x007E;

        base.WndProc(ref m);

        if (m.Msg == WM_DISPLAYCHANGE)
        {
            QueueDisplayTopologyRefresh();
        }
    }

    private void SetPattern(PatternKind value)
    {
        if ((value is PatternKind.Grayscale or PatternKind.Dot1 or PatternKind.Dot2 or PatternKind.SubDot) && pattern != value)
        {
            grayLevel = 127;
        }
        if (value == PatternKind.Checkerboard && pattern != PatternKind.Checkerboard)
        {
            checkerLevel = 255;
            checkerMode = "white";
            checkerSizeIndex = 3;
            checkerStopwatch.Restart();
        }
        if (value == PatternKind.Crosstalk)
        {
            EnsureCrosstalkRect();
        }
        if (value == PatternKind.WrgbColorbar)
        {
            grayLevel = 127;
            barOrientation = BarOrientation.Horizontal;
        }

        flipMode = FlipMode.None;
        pattern = value;
        MarkDirty();
    }

    private void SetGradient(PatternKind value, int steps)
    {
        gradientSteps = steps;
        flipMode = FlipMode.None;
        barOrientation = BarOrientation.Horizontal;
        pattern = value;
        MarkDirty();
    }

    private void SetVerticalLineMode(string mode)
    {
        vlineMode = mode;
        grayLevel = 127;
        flipMode = FlipMode.None;
        pattern = PatternKind.VerticalLine;
        MarkDirty();
    }

    private void SetHorizontalLineMode(string mode)
    {
        hlineMode = mode;
        grayLevel = 127;
        flipMode = FlipMode.None;
        pattern = PatternKind.HorizontalLine;
        MarkDirty();
    }

    private void OpenImage()
    {
        using var dialog = new OpenFileDialog
        {
            Title = "Open Image",
            Filter = "Image files|*.png;*.jpg;*.jpeg;*.bmp;*.gif|All files|*.*"
        };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }
        loadedImage?.Dispose();
        loadedImage = null;
        pattern = PatternKind.Image;
        flipMode = FlipMode.None;
        MarkDirty();
        imagePath = dialog.FileName;
        StartImageLoad(dialog.FileName);
    }

    private void OpenCrosstalkImage(bool background)
    {
        using var dialog = new OpenFileDialog
        {
            Title = "Open Image",
            Filter = "Image files|*.png;*.jpg;*.jpeg;*.bmp;*.gif|All files|*.*"
        };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }
        if (background)
        {
            crosstalkBackgroundImage?.Dispose();
            crosstalkBackgroundImage = null;
            crosstalkBackgroundPath = dialog.FileName;
        }
        else
        {
            crosstalkBlockImage?.Dispose();
            crosstalkBlockImage = null;
            crosstalkBlockPath = dialog.FileName;
        }
        StartCrosstalkImageLoad(dialog.FileName, background);
    }

    private void StartImageLoad(string path)
    {
        var version = ++imageLoadVersion;
        Task.Run(() =>
        {
            using var source = Image.FromFile(path);
            var bitmap = BuildStretchBitmap(source, Math.Max(ClientSize.Width, 1), Math.Max(ClientSize.Height, 1));
            BeginInvoke(() =>
            {
                if (version != imageLoadVersion || IsDisposed)
                {
                    bitmap.Dispose();
                    return;
                }
                loadedImage?.Dispose();
                loadedImage = bitmap;
                MarkDirty();
            });
        });
    }

    private void StartCrosstalkImageLoad(string path, bool background)
    {
        var version = background ? ++crosstalkBgLoadVersion : ++crosstalkBlockLoadVersion;
        Task.Run(() =>
        {
            using var source = Image.FromFile(path);
            var bitmap = BuildCoverBitmap(source, Math.Max(ClientSize.Width, 1), Math.Max(ClientSize.Height, 1));
            BeginInvoke(() =>
            {
                if (IsDisposed)
                {
                    bitmap.Dispose();
                    return;
                }
                if (background)
                {
                    if (version != crosstalkBgLoadVersion)
                    {
                        bitmap.Dispose();
                        return;
                    }
                    crosstalkBackgroundImage?.Dispose();
                    crosstalkBackgroundImage = bitmap;
                }
                else
                {
                    if (version != crosstalkBlockLoadVersion)
                    {
                        bitmap.Dispose();
                        return;
                    }
                    crosstalkBlockImage?.Dispose();
                    crosstalkBlockImage = bitmap;
                }
                MarkDirty();
            });
        });
    }

    private void SavePattern()
    {
        if (ClientSize.Width <= 0 || ClientSize.Height <= 0)
        {
            return;
        }

        using var dialog = new SaveFileDialog
        {
            Title = "Save Pattern As",
            DefaultExt = "png",
            Filter = "PNG image|*.png"
        };
        if (dialog.ShowDialog(this) != DialogResult.OK)
        {
            return;
        }

        EnsureBackBuffer();
        if (backBuffer is null)
        {
            return;
        }

        var previousShowHud = showHud;
        showHud = true;
        RenderToBackBuffer(backBuffer);
        showHud = previousShowHud;
        backBuffer.Save(dialog.FileName, ImageFormat.Png);
        renderDirty = false;
        Invalidate();
    }

    private void EnsureBackBuffer()
    {
        var width = ClientSize.Width;
        var height = ClientSize.Height;
        if (width <= 0 || height <= 0)
        {
            return;
        }

        if (backBuffer is not null && backBuffer.Width == width && backBuffer.Height == height)
        {
            return;
        }

        backBuffer?.Dispose();
        backBuffer = new Bitmap(width, height, PixelFormat.Format32bppPArgb);
        renderDirty = true;
    }

    private void MarkDirty()
    {
        renderDirty = true;
        Invalidate();
    }

    private void ReloadScaledAssets()
    {
        if (!string.IsNullOrEmpty(imagePath) && pattern == PatternKind.Image)
        {
            StartImageLoad(imagePath);
        }
        if (!string.IsNullOrEmpty(crosstalkBackgroundPath))
        {
            StartCrosstalkImageLoad(crosstalkBackgroundPath, true);
        }
        if (!string.IsNullOrEmpty(crosstalkBlockPath))
        {
            StartCrosstalkImageLoad(crosstalkBlockPath, false);
        }
    }

    private void RenderToBackBuffer(Bitmap bitmap)
    {
        if (!TryRenderRasterPattern(bitmap))
        {
            using var g = Graphics.FromImage(bitmap);
            g.Clear(pattern == PatternKind.None ? Color.FromArgb(127, 127, 127) : Color.White);
            g.SmoothingMode = SmoothingMode.None;
            g.InterpolationMode = InterpolationMode.NearestNeighbor;
            g.PixelOffsetMode = PixelOffsetMode.Half;
            RenderVectorPattern(g, bitmap.Width, bitmap.Height);
            return;
        }

        using var overlay = Graphics.FromImage(bitmap);
        overlay.SmoothingMode = SmoothingMode.None;
        overlay.InterpolationMode = InterpolationMode.NearestNeighbor;
        overlay.PixelOffsetMode = PixelOffsetMode.Half;

        if (pattern == PatternKind.None)
        {
            DrawInstructions(overlay, bitmap.Width, bitmap.Height);
            return;
        }

        if (pattern == PatternKind.Checkerboard)
        {
            if (!crosshairEnabled)
            {
                DrawHud(overlay, $"L{checkerLevel}", bitmap.Width, false);
                DrawHud(overlay, FormatElapsed(), bitmap.Width, true);
            }
        }
        else if (pattern is PatternKind.Grayscale or PatternKind.VerticalLine or PatternKind.HorizontalLine or PatternKind.Dot1 or PatternKind.Dot2 or PatternKind.SubDot or PatternKind.WrgbColorbar)
        {
            if (!crosshairEnabled)
            {
                DrawHud(overlay, $"L{grayLevel}", bitmap.Width, false);
            }
        }

        if (crosshairEnabled)
        {
            DrawCrosshair(overlay, bitmap.Width, bitmap.Height);
            DrawHud(overlay, $"X{crosshairX} Y{crosshairY}", bitmap.Width, false);
        }
    }

    private bool TryRenderRasterPattern(Bitmap bitmap)
    {
        var width = bitmap.Width;
        var height = bitmap.Height;
        var pixels = new int[width * height];
        var white = Color.White.ToArgb();
        var black = Color.Black.ToArgb();
        var grayBackground = Color.FromArgb(127, 127, 127).ToArgb();

        switch (pattern)
        {
            case PatternKind.None:
                Array.Fill(pixels, grayBackground);
                break;
            case PatternKind.Grayscale:
                Array.Fill(pixels, ColorFromMode(grayMode, grayLevel).ToArgb());
                break;
            case PatternKind.Checkerboard:
                RenderCheckerboard(pixels, width, height);
                break;
            case PatternKind.LinearGrayscale:
                Array.Fill(pixels, black);
                RenderLinearGradient(pixels, width, height);
                break;
            case PatternKind.ColorfulGrayscale:
                Array.Fill(pixels, black);
                RenderColorfulGrayscale(pixels, width, height);
                break;
            case PatternKind.WrgbColorbar:
                Array.Fill(pixels, black);
                RenderWrgbColorbar(pixels, width, height);
                break;
            case PatternKind.Mux21:
                Array.Fill(pixels, black);
                RenderMuxPattern(pixels, width, height, false);
                break;
            case PatternKind.Mux22:
                Array.Fill(pixels, black);
                RenderMuxPattern(pixels, width, height, true);
                break;
            case PatternKind.GrayCenter:
                Array.Fill(pixels, black);
                RenderCenterGradient(pixels, width, height);
                break;
            case PatternKind.VerticalLine:
                RenderVerticalLines(pixels, width, height);
                break;
            case PatternKind.HorizontalLine:
                RenderHorizontalLines(pixels, width, height);
                break;
            case PatternKind.Dot1:
                RenderDotPattern(pixels, width, height, 1);
                break;
            case PatternKind.Dot2:
                RenderDotPattern(pixels, width, height, 2);
                break;
            case PatternKind.SubDot:
                RenderSubDotPattern(pixels, width, height);
                break;
            case PatternKind.OneThird:
                Array.Fill(pixels, black);
                if (flipMode == FlipMode.Vertical)
                {
                    FillRectPixels(pixels, width, height, 0, height - (height / 3), width, height, white);
                }
                else
                {
                    FillRectPixels(pixels, width, height, 0, 0, width, height / 3, white);
                }
                break;
            default:
                return false;
        }

        CopyPixelsToBitmap(bitmap, pixels);
        return true;
    }

    private void RenderVectorPattern(Graphics g, int width, int height)
    {
        switch (pattern)
        {
            case PatternKind.Image:
                g.Clear(Color.White);
                DrawImagePattern(g, width, height);
                break;
            case PatternKind.Align:
                DrawAlign(g, width, height);
                break;
            case PatternKind.Crosstalk:
                DrawCrosstalk(g, width, height);
                break;
            default:
                g.Clear(pattern == PatternKind.None ? Color.FromArgb(127, 127, 127) : Color.White);
                break;
        }

        if (crosshairEnabled)
        {
            DrawCrosshair(g, width, height);
            DrawHud(g, $"X{crosshairX} Y{crosshairY}", width, false);
        }
    }

    private void RenderCheckerboard(int[] pixels, int width, int height)
    {
        var onColor = ColorFromMode(checkerMode, checkerLevel).ToArgb();
        var offColor = Color.Black.ToArgb();
        var cells = CheckerSizes[checkerSizeIndex];

        for (var row = 0; row < cells; row++)
        {
            var srcY1 = row * height / cells;
            var srcY2 = (row + 1) * height / cells;
            for (var col = 0; col < cells; col++)
            {
                var srcX1 = col * width / cells;
                var srcX2 = (col + 1) * width / cells;
                var x1 = flipMode == FlipMode.Horizontal ? width - srcX2 : srcX1;
                var x2 = flipMode == FlipMode.Horizontal ? width - srcX1 : srcX2;
                var dy1 = flipMode == FlipMode.Vertical ? height - srcY2 : srcY1;
                var dy2 = flipMode == FlipMode.Vertical ? height - srcY1 : srcY2;
                FillRectPixels(pixels, width, height, x1, dy1, x2, dy2, (row + col) % 2 == 0 ? onColor : offColor);
            }
        }
    }

    private void RenderLinearGradient(int[] pixels, int width, int height)
    {
        if (barOrientation == BarOrientation.Horizontal)
        {
            RenderHorizontalGradient(pixels, width, height);
        }
        else
        {
            RenderVerticalGradient(pixels, width, height);
        }
    }

    private void RenderColorfulGrayscale(int[] pixels, int width, int height)
    {
        var stripeCount = 4;
        var primaryLength = barOrientation == BarOrientation.Horizontal ? width : height;
        var reverse = (barOrientation == BarOrientation.Horizontal && flipMode == FlipMode.Horizontal)
            || (barOrientation == BarOrientation.Vertical && flipMode == FlipMode.Vertical);

        for (var stripe = 0; stripe < stripeCount; stripe++)
        {
            for (var primary = 0; primary < primaryLength; primary++)
            {
                var sourcePrimary = reverse ? primaryLength - 1 - primary : primary;
                var level = QuantizeLevel(primaryLength <= 1 ? 255f : sourcePrimary * 255f / (primaryLength - 1), gradientSteps);
                var color = stripe switch
                {
                    0 => Color.FromArgb(level, level, level).ToArgb(),
                    1 => Color.FromArgb(level, 0, 0).ToArgb(),
                    2 => Color.FromArgb(0, level, 0).ToArgb(),
                    _ => Color.FromArgb(0, 0, level).ToArgb(),
                };

                if (barOrientation == BarOrientation.Horizontal)
                {
                    var y1 = stripe * height / stripeCount;
                    var y2 = (stripe + 1) * height / stripeCount;
                    FillRectPixels(pixels, width, height, primary, y1, primary + 1, y2, color);
                }
                else
                {
                    var x1 = stripe * width / stripeCount;
                    var x2 = (stripe + 1) * width / stripeCount;
                    FillRectPixels(pixels, width, height, x1, primary, x2, primary + 1, color);
                }
            }
        }
    }

    private void RenderWrgbColorbar(int[] pixels, int width, int height)
    {
        var stripeCount = 4;
        for (var stripe = 0; stripe < stripeCount; stripe++)
        {
            var color = stripe switch
            {
                0 => Color.FromArgb(grayLevel, grayLevel, grayLevel).ToArgb(),
                1 => Color.FromArgb(grayLevel, 0, 0).ToArgb(),
                2 => Color.FromArgb(0, grayLevel, 0).ToArgb(),
                _ => Color.FromArgb(0, 0, grayLevel).ToArgb(),
            };

            if (barOrientation == BarOrientation.Horizontal)
            {
                var y1 = stripe * height / stripeCount;
                var y2 = (stripe + 1) * height / stripeCount;
                FillRectPixels(pixels, width, height, 0, y1, width, y2, color);
            }
            else
            {
                var x1 = stripe * width / stripeCount;
                var x2 = (stripe + 1) * width / stripeCount;
                FillRectPixels(pixels, width, height, x1, 0, x2, height, color);
            }
        }
    }

    private static void RenderMuxPattern(int[] pixels, int width, int height, bool swapRows)
    {
        var yellow = Color.FromArgb(255, 255, 0).ToArgb();
        var cyan = Color.FromArgb(0, 255, 255).ToArgb();
        var blue = Color.FromArgb(0, 0, 255).ToArgb();
        var red = Color.FromArgb(255, 0, 0).ToArgb();

        var row0 = new[] { yellow, cyan, blue, red };
        var row1 = new[] { blue, red, yellow, cyan };
        if (swapRows)
        {
            (row0, row1) = (row1, row0);
        }

        for (var y = 0; y < height; y++)
        {
            var row = (y & 1) == 0 ? row0 : row1;
            var offset = y * width;
            for (var x = 0; x < width; x++)
            {
                pixels[offset + x] = row[x & 3];
            }
        }
    }

    private void RenderHorizontalGradient(int[] pixels, int width, int height)
    {
        for (var x = 0; x < width; x++)
        {
            var level = QuantizeLevel(width <= 1 ? 255f : x * 255f / (width - 1), gradientSteps);
            var color = ColorFromMode(grayMode, level).ToArgb();
            var destX = flipMode == FlipMode.Horizontal ? width - 1 - x : x;
            FillRectPixels(pixels, width, height, destX, 0, destX + 1, height, color);
        }
    }

    private void RenderVerticalGradient(int[] pixels, int width, int height)
    {
        for (var y = 0; y < height; y++)
        {
            var level = QuantizeLevel(height <= 1 ? 255f : y * 255f / (height - 1), gradientSteps);
            var color = ColorFromMode(grayMode, level).ToArgb();
            var destY = flipMode == FlipMode.Vertical ? height - 1 - y : y;
            FillRectPixels(pixels, width, height, 0, destY, width, destY + 1, color);
        }
    }

    private void RenderCenterGradient(int[] pixels, int width, int height)
    {
        var bands = gradientSteps >= 256 ? 256 : Math.Max(gradientSteps, 1);
        if (bands <= 1)
        {
            return;
        }

        var insetX = BuildInsets(width / 2, bands);
        var insetY = BuildInsets(height / 2, bands);
        for (var band = 0; band < bands; band++)
        {
            var level = QuantizeLevel((float)band / (bands - 1) * 255f, gradientSteps);
            var color = ColorFromMode(grayMode, level).ToArgb();
            var x1 = insetX[band];
            var y1 = insetY[band];
            var x2 = width - insetX[band];
            var y2 = height - insetY[band];
            var nx1 = insetX[band + 1];
            var ny1 = insetY[band + 1];
            var nx2 = width - insetX[band + 1];
            var ny2 = height - insetY[band + 1];
            FillRectPixels(pixels, width, height, x1, y1, x2, ny1, color);
            FillRectPixels(pixels, width, height, x1, ny2, x2, y2, color);
            FillRectPixels(pixels, width, height, x1, ny1, nx1, ny2, color);
            FillRectPixels(pixels, width, height, nx2, ny1, x2, ny2, color);
        }
    }

    private void RenderVerticalLines(int[] pixels, int width, int height)
    {
        var onColor = ColorFromMode(grayMode, grayLevel).ToArgb();
        var subA = Color.FromArgb(grayLevel, 0, grayLevel).ToArgb();
        var subB = Color.FromArgb(0, grayLevel, 0).ToArgb();
        var black = Color.Black.ToArgb();

        for (var x = 0; x < width; x++)
        {
            var color = vlineMode switch
            {
                "subline" => x % 2 == 0 ? subA : subB,
                "2line" => x % 3 == 0 ? onColor : black,
                _ => x % 2 == 0 ? onColor : black,
            };
            var destX = flipMode == FlipMode.Horizontal ? width - 1 - x : x;
            FillRectPixels(pixels, width, height, destX, 0, destX + 1, height, color);
        }
    }

    private void RenderHorizontalLines(int[] pixels, int width, int height)
    {
        var onColor = ColorFromMode(grayMode, grayLevel).ToArgb();
        var black = Color.Black.ToArgb();

        for (var y = 0; y < height; y++)
        {
            var color = (hlineMode == "2line" ? y % 4 < 2 : y % 2 == 0) ? onColor : black;
            var destY = flipMode == FlipMode.Vertical ? height - 1 - y : y;
            FillRectPixels(pixels, width, height, 0, destY, width, destY + 1, color);
        }
    }

    private void RenderDotPattern(int[] pixels, int width, int height, int size)
    {
        var onColor = ColorFromMode(grayMode, grayLevel).ToArgb();
        var black = Color.Black.ToArgb();

        for (var y = 0; y < height; y++)
        {
            var rowOn = (y / size) % 2 == 0;
            for (var x = 0; x < width; x++)
            {
                var colOn = (x / size) % 2 == 0;
                var destX = flipMode == FlipMode.Horizontal ? width - 1 - x : x;
                var destY = flipMode == FlipMode.Vertical ? height - 1 - y : y;
                pixels[destY * width + destX] = rowOn == colOn ? onColor : black;
            }
        }
    }

    private void RenderSubDotPattern(int[] pixels, int width, int height)
    {
        var magenta = Color.FromArgb(grayLevel, 0, grayLevel).ToArgb();
        var green = Color.FromArgb(0, grayLevel, 0).ToArgb();

        for (var y = 0; y < height; y++)
        {
            var startGreen = y % 2 == 0;
            for (var x = 0; x < width; x++)
            {
                var useGreen = startGreen ? x % 2 == 0 : x % 2 == 1;
                var destX = flipMode == FlipMode.Horizontal ? width - 1 - x : x;
                var destY = flipMode == FlipMode.Vertical ? height - 1 - y : y;
                pixels[destY * width + destX] = useGreen ? green : magenta;
            }
        }
    }

    private void DrawImagePattern(Graphics g, int width, int height)
    {
        if (loadedImage is null)
        {
            return;
        }

        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        Image image = loadedImage;
        if (flipMode != FlipMode.None)
        {
            image = (Image)loadedImage.Clone();
            image.RotateFlip(flipMode == FlipMode.Horizontal ? RotateFlipType.RotateNoneFlipX : RotateFlipType.RotateNoneFlipY);
        }

        g.DrawImage(image, new Rectangle(0, 0, width, height));
        if (!ReferenceEquals(image, loadedImage))
        {
            image.Dispose();
        }
    }

    private void DrawAlign(Graphics g, int width, int height)
    {
        g.Clear(Color.Black);
        var state = g.Save();
        if (flipMode == FlipMode.Horizontal)
        {
            g.TranslateTransform(width, 0);
            g.ScaleTransform(-1, 1);
        }
        else if (flipMode == FlipMode.Vertical)
        {
            g.TranslateTransform(0, height);
            g.ScaleTransform(1, -1);
        }

        using var pen = new Pen(Color.FromArgb(191, 191, 191), 1f);
        var cx = width / 2;
        var cy = height / 2;
        g.DrawLine(pen, 0, cy, width - 1, cy);
        g.DrawLine(pen, cx, 0, cx, height - 1);
        g.DrawLine(pen, 0, 0, width - 1, height - 1);
        g.DrawLine(pen, 0, height - 1, width - 1, 0);
        g.DrawRectangle(pen, 0, 0, Math.Max(width - 1, 1), Math.Max(height - 1, 1));
        foreach (var ratio in new[] { 0.95, 0.75, 0.55, 0.35 })
        {
            var rectW = Math.Max(2, (int)(width * ratio));
            var rectH = Math.Max(2, (int)(height * ratio));
            g.DrawRectangle(pen, (width - rectW) / 2, (height - rectH) / 2, rectW - 1, rectH - 1);
        }
        var radiusBase = Math.Min(cx, cy);
        foreach (var ratio in new[] { 1.0, 2.0 / 3.0, 1.0 / 3.0 })
        {
            var radius = Math.Max(2, (int)(radiusBase * ratio));
            g.DrawEllipse(pen, cx - radius, cy - radius, radius * 2, radius * 2);
        }
        g.Restore(state);
    }

    private void DrawCrosstalk(Graphics g, int width, int height)
    {
        EnsureCrosstalkRect();
        g.Clear(Color.FromArgb(crosstalkBgLevel, crosstalkBgLevel, crosstalkBgLevel));
        if (crosstalkBackgroundImage is not null)
        {
            g.DrawImage(crosstalkBackgroundImage, 0, 0);
        }

        if (crosstalkRect is null)
        {
            return;
        }

        var rect = crosstalkRect.Value;
        using var blockBrush = new SolidBrush(Color.FromArgb(crosstalkBlockLevel, crosstalkBlockLevel, crosstalkBlockLevel));
        g.FillRectangle(blockBrush, rect);
        if (crosstalkBlockImage is not null)
        {
            g.DrawImage(crosstalkBlockImage, rect, rect, GraphicsUnit.Pixel);
        }
    }

    private void DrawInstructions(Graphics g, int width, int height)
    {
        const string text =
            "欢迎使用 PatternPilot。\n" +
            "这是一个用于面板测试、图案显示、图像查看和 Crosstalk 检查的全屏工具。\n\n" +
            "基础操作\n" +
            "右键或中键：打开菜单\n" +
            "Esc：退出程序\n" +
            "Tab：切换显示器\n" +
            "Ctrl+S：将当前画面保存为 PNG\n" +
            "Ctrl+R：翻转当前图案\n" +
            "Ctrl+F：开启或关闭十字工具\n\n" +
            "亮度与颜色\n" +
            "上/下方向键：调整亮度等级\n" +
            "Shift+上/下：快速调整亮度\n" +
            "Home：设置为 255\n" +
            "End：设置为 0\n" +
            "数字键 1-8：切换颜色模式\n\n" +
            "十字工具\n" +
            "方向键：移动十字位置\n" +
            "Shift+方向键：快速移动\n" +
            "Ctrl+1/2/3/4：切换十字形态\n\n" +
            "棋盘格模式\n" +
            "左/右方向键：调整棋盘格尺寸\n" +
            "上/下方向键：调整亮度\n\n" +
            "Crosstalk 模式\n" +
            "Ctrl+1：加载背景图\n" +
            "Ctrl+2：加载遮挡图\n" +
            "方向键：移动遮挡区域\n" +
            "Ctrl+方向键：调整遮挡区域大小\n\n" +
            "图案菜单\n" +
            "支持灰阶、棋盘格、对齐图、全屏图像、渐变、线条、点阵、Crosstalk 和 One Third。";
        using var titleFont = new Font("Segoe UI", 30f, FontStyle.Bold, GraphicsUnit.Pixel);
        using var bodyFont = new Font("Segoe UI", 18f, FontStyle.Regular, GraphicsUnit.Pixel);
        using var titleBrush = new SolidBrush(Color.FromArgb(40, 40, 40));
        using var bodyBrush = new SolidBrush(Color.FromArgb(68, 68, 68));
        var padding = 56f;
        var title = "PatternPilot";
        g.DrawString(title, titleFont, titleBrush, padding, padding);
        var titleHeight = g.MeasureString(title, titleFont).Height;
        var bodyTop = padding + titleHeight + 20f;
        var bodyWidth = Math.Max(width - padding * 2f, 240f);
        g.DrawString(text, bodyFont, bodyBrush, new RectangleF(padding, bodyTop, bodyWidth, Math.Max(height - bodyTop - padding, 200f)));
    }

    private void DrawCrosshair(Graphics g, int width, int height)
    {
        crosshairX = Math.Clamp(crosshairX, 0, width - 1);
        crosshairY = Math.Clamp(crosshairY, 0, height - 1);
        using var pen = new Pen(ColorFromMode(crosshairColorMode, 255), 1f);
        if (crosshairMode is CrosshairMode.Cross or CrosshairMode.VerticalLine)
        {
            g.DrawLine(pen, crosshairX, 0, crosshairX, height - 1);
        }
        if (crosshairMode is CrosshairMode.Cross or CrosshairMode.HorizontalLine)
        {
            g.DrawLine(pen, 0, crosshairY, width - 1, crosshairY);
        }
        if (crosshairMode == CrosshairMode.Point)
        {
            using var brush = new SolidBrush(ColorFromMode(crosshairColorMode, 255));
            g.FillRectangle(brush, crosshairX, crosshairY, 1, 1);
        }
    }

    private void DrawHud(Graphics g, string text, int width, bool alignRight)
    {
        if (!showHud)
        {
            return;
        }

        using var font = new Font("Consolas", 16f, FontStyle.Bold, GraphicsUnit.Pixel);
        var size = g.MeasureString(text, font);
        var x = alignRight ? Math.Max(width - size.Width - 12f, 2f) : 2f;
        var rect = new RectangleF(x, 2f, size.Width + 10f, size.Height + 6f);
        using var bgBrush = new SolidBrush(Color.Black);
        using var fgBrush = new SolidBrush(Color.White);
        g.FillRectangle(bgBrush, rect);
        g.DrawString(text, font, fgBrush, rect.Left + 5f, rect.Top + 3f);
    }

    private void HandleKeyInput(KeyEventArgs e)
    {
        if (e.Control && e.KeyCode == Keys.S)
        {
            SavePattern();
            return;
        }
        if (e.Control && e.KeyCode == Keys.R)
        {
            ToggleFlip();
            return;
        }
        if (e.Control && e.KeyCode == Keys.F)
        {
            ToggleCrosshair();
            return;
        }

        if (pattern == PatternKind.Crosstalk)
        {
            HandleCrosstalkKey(e);
            return;
        }

        if (crosshairEnabled)
        {
            HandleCrosshairKey(e);
            return;
        }

        if (pattern == PatternKind.Checkerboard)
        {
            HandleCheckerboardKey(e);
            return;
        }

        if (pattern is PatternKind.LinearGrayscale or PatternKind.GrayCenter)
        {
            if (TryGetColorMode(e.KeyCode, out var mode))
            {
                grayMode = mode;
                MarkDirty();
            }
            return;
        }

        if (pattern == PatternKind.WrgbColorbar)
        {
            HandleGrayLevelKey(e);
            return;
        }

        if (pattern is not (PatternKind.Grayscale or PatternKind.VerticalLine or PatternKind.HorizontalLine or PatternKind.Dot1 or PatternKind.Dot2 or PatternKind.SubDot))
        {
            return;
        }

        HandleGrayLevelKey(e);
    }

    private void ToggleFlip()
    {
        if (pattern == PatternKind.None)
        {
            return;
        }
        if (pattern == PatternKind.Image)
        {
            flipMode = flipMode switch
            {
                FlipMode.None => FlipMode.Horizontal,
                FlipMode.Horizontal => FlipMode.Vertical,
                _ => FlipMode.None
            };
        }
        else if (pattern is PatternKind.LinearGrayscale or PatternKind.ColorfulGrayscale)
        {
            RotateGradientPattern();
        }
        else if (pattern is PatternKind.WrgbColorbar)
        {
            barOrientation = barOrientation == BarOrientation.Horizontal ? BarOrientation.Vertical : BarOrientation.Horizontal;
            flipMode = FlipMode.None;
        }
        else if (pattern is PatternKind.VerticalLine)
        {
            flipMode = flipMode == FlipMode.Horizontal ? FlipMode.None : FlipMode.Horizontal;
        }
        else
        {
            flipMode = flipMode == FlipMode.Vertical ? FlipMode.None : FlipMode.Vertical;
        }
        MarkDirty();
    }

    private void RotateGradientPattern()
    {
        if (barOrientation == BarOrientation.Horizontal && flipMode == FlipMode.None)
        {
            flipMode = FlipMode.Horizontal;
            return;
        }

        if (barOrientation == BarOrientation.Horizontal && flipMode == FlipMode.Horizontal)
        {
            barOrientation = BarOrientation.Vertical;
            flipMode = FlipMode.None;
            return;
        }

        if (barOrientation == BarOrientation.Vertical && flipMode == FlipMode.None)
        {
            flipMode = FlipMode.Vertical;
            return;
        }

        barOrientation = BarOrientation.Horizontal;
        flipMode = FlipMode.None;
    }

    private void ToggleCrosshair()
    {
        if (pattern == PatternKind.None)
        {
            return;
        }

        crosshairEnabled = !crosshairEnabled;
        if (crosshairEnabled)
        {
            crosshairX = Math.Max(ClientSize.Width / 2, 0);
            crosshairY = Math.Max(ClientSize.Height / 2, 0);
            crosshairMode = CrosshairMode.Cross;
            crosshairColorMode = "white";
        }
        MarkDirty();
    }

    private void HandleCrosstalkKey(KeyEventArgs e)
    {
        EnsureCrosstalkRect();
        if (e.Control && e.KeyCode == Keys.D1)
        {
            OpenCrosstalkImage(true);
            return;
        }
        if (e.Control && e.KeyCode == Keys.D2)
        {
            OpenCrosstalkImage(false);
            return;
        }
        if (crosstalkRect is null)
        {
            return;
        }

        var rect = crosstalkRect.Value;
        var step = e.Shift ? 10 : 1;
        if (e.Control)
        {
            switch (e.KeyCode)
            {
                case Keys.Left:
                    ResizeCrosstalkHorizontally(ref rect, step);
                    break;
                case Keys.Right:
                    ResizeCrosstalkHorizontally(ref rect, -step);
                    break;
                case Keys.Up:
                    ResizeCrosstalkVertically(ref rect, step);
                    break;
                case Keys.Down:
                    ResizeCrosstalkVertically(ref rect, -step);
                    break;
                default:
                    return;
            }
        }
        else
        {
            var width = rect.Width;
            var height = rect.Height;
            switch (e.KeyCode)
            {
                case Keys.Left:
                    rect.X -= step;
                    break;
                case Keys.Right:
                    rect.X += step;
                    break;
                case Keys.Up:
                    rect.Y -= step;
                    break;
                case Keys.Down:
                    rect.Y += step;
                    break;
                default:
                    return;
            }
            if (rect.X < 0)
            {
                rect.X = 0;
            }
            if (rect.Y < 0)
            {
                rect.Y = 0;
            }
            if (rect.X + width > ClientSize.Width)
            {
                rect.X = Math.Max(ClientSize.Width - width, 0);
            }
            if (rect.Y + height > ClientSize.Height)
            {
                rect.Y = Math.Max(ClientSize.Height - height, 0);
            }
            rect.Width = width;
            rect.Height = height;
        }

        crosstalkRect = rect;
        ClampCrosstalkRect();
        MarkDirty();
    }

    private static void ResizeCrosstalkHorizontally(ref Rectangle rect, int delta)
    {
        var centerX = rect.X + (rect.Width / 2f);
        var newWidth = Math.Max(1, rect.Width + (delta * 2));
        rect.Width = newWidth;
        rect.X = (int)Math.Round(centerX - (newWidth / 2f));
    }

    private static void ResizeCrosstalkVertically(ref Rectangle rect, int delta)
    {
        var centerY = rect.Y + (rect.Height / 2f);
        var newHeight = Math.Max(1, rect.Height + (delta * 2));
        rect.Height = newHeight;
        rect.Y = (int)Math.Round(centerY - (newHeight / 2f));
    }

    private void HandleCrosshairKey(KeyEventArgs e)
    {
        if (e.Control)
        {
            var nextMode = e.KeyCode switch
            {
                Keys.D1 => CrosshairMode.HorizontalLine,
                Keys.D2 => CrosshairMode.VerticalLine,
                Keys.D3 => CrosshairMode.Point,
                Keys.D4 => CrosshairMode.Cross,
                _ => crosshairMode
            };
            if (nextMode != crosshairMode || e.KeyCode is Keys.D1 or Keys.D2 or Keys.D3 or Keys.D4)
            {
                crosshairMode = nextMode;
                MarkDirty();
                return;
            }
        }

        var step = e.Shift ? 10 : 1;
        switch (e.KeyCode)
        {
            case Keys.Up when crosshairMode is CrosshairMode.Cross or CrosshairMode.HorizontalLine or CrosshairMode.Point:
                crosshairY -= step;
                break;
            case Keys.Down when crosshairMode is CrosshairMode.Cross or CrosshairMode.HorizontalLine or CrosshairMode.Point:
                crosshairY += step;
                break;
            case Keys.Left when crosshairMode is CrosshairMode.Cross or CrosshairMode.VerticalLine or CrosshairMode.Point:
                crosshairX -= step;
                break;
            case Keys.Right when crosshairMode is CrosshairMode.Cross or CrosshairMode.VerticalLine or CrosshairMode.Point:
                crosshairX += step;
                break;
            default:
                if (TryGetColorMode(e.KeyCode, out var mode))
                {
                    crosshairColorMode = mode;
                }
                else
                {
                    return;
                }
                break;
        }
        MarkDirty();
    }

    private void HandleCheckerboardKey(KeyEventArgs e)
    {
        var step = e.Shift ? 16 : 1;
        switch (e.KeyCode)
        {
            case Keys.Up:
                checkerLevel = Math.Clamp(checkerLevel + step, 0, 255);
                break;
            case Keys.Down:
                checkerLevel = Math.Clamp(checkerLevel - step, 0, 255);
                break;
            case Keys.Left:
                checkerSizeIndex = Math.Clamp(checkerSizeIndex - 1, 0, CheckerSizes.Length - 1);
                break;
            case Keys.Right:
                checkerSizeIndex = Math.Clamp(checkerSizeIndex + 1, 0, CheckerSizes.Length - 1);
                break;
            case Keys.Home:
                checkerLevel = 255;
                break;
            case Keys.End:
                checkerLevel = 0;
                break;
            default:
                if (TryGetColorMode(e.KeyCode, out var mode))
                {
                    checkerMode = mode;
                }
                else
                {
                    return;
                }
                break;
        }
        MarkDirty();
    }

    private void HandleGrayLevelKey(KeyEventArgs e)
    {
        var step = e.Shift ? 16 : 1;
        switch (e.KeyCode)
        {
            case Keys.Up:
                grayLevel = Math.Clamp(grayLevel + step, 0, 255);
                break;
            case Keys.Down:
                grayLevel = Math.Clamp(grayLevel - step, 0, 255);
                break;
            case Keys.Home:
                grayLevel = 255;
                break;
            case Keys.End:
                grayLevel = 0;
                break;
            default:
                if (TryGetColorMode(e.KeyCode, out var mode))
                {
                    grayMode = mode;
                }
                else
                {
                    return;
                }
                break;
        }
        MarkDirty();
    }

    private void EnsureCrosstalkRect()
    {
        if (ClientSize.Width <= 0 || ClientSize.Height <= 0)
        {
            return;
        }

        if (crosstalkRect is null)
        {
            var rectW = Math.Max(1, ClientSize.Width / 3);
            var rectH = Math.Max(1, ClientSize.Height / 3);
            crosstalkRect = new Rectangle((ClientSize.Width - rectW) / 2, (ClientSize.Height - rectH) / 2, rectW, rectH);
        }

        ClampCrosstalkRect();
    }

    private void ScaleOverlayRectsForResize(Size previousSize, Size currentSize)
    {
        if (previousSize.Width <= 0 || previousSize.Height <= 0 || currentSize.Width <= 0 || currentSize.Height <= 0)
        {
            return;
        }

        if (previousSize == currentSize || crosstalkRect is null)
        {
            return;
        }

        var rect = crosstalkRect.Value;
        var scaleX = (float)currentSize.Width / previousSize.Width;
        var scaleY = (float)currentSize.Height / previousSize.Height;
        rect = new Rectangle(
            (int)Math.Round(rect.X * scaleX),
            (int)Math.Round(rect.Y * scaleY),
            Math.Max(1, (int)Math.Round(rect.Width * scaleX)),
            Math.Max(1, (int)Math.Round(rect.Height * scaleY)));
        crosstalkRect = rect;
    }

    private void ClampCrosstalkRect()
    {
        if (crosstalkRect is null || ClientSize.Width <= 0 || ClientSize.Height <= 0)
        {
            return;
        }

        var rect = crosstalkRect.Value;
        rect.X = Math.Clamp(rect.X, 0, Math.Max(ClientSize.Width - 1, 0));
        rect.Y = Math.Clamp(rect.Y, 0, Math.Max(ClientSize.Height - 1, 0));
        rect.Width = Math.Clamp(rect.Width, 1, Math.Max(ClientSize.Width - rect.X, 1));
        rect.Height = Math.Clamp(rect.Height, 1, Math.Max(ClientSize.Height - rect.Y, 1));
        crosstalkRect = rect;
    }

    private static Bitmap BuildCoverBitmap(Image source, int width, int height)
    {
        var scale = Math.Max((float)width / source.Width, (float)height / source.Height);
        var newW = Math.Max((int)Math.Round(source.Width * scale), 1);
        var newH = Math.Max((int)Math.Round(source.Height * scale), 1);
        var bitmap = new Bitmap(width, height, PixelFormat.Format32bppPArgb);
        using var g = Graphics.FromImage(bitmap);
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        var x = (width - newW) / 2;
        var y = (height - newH) / 2;
        g.DrawImage(source, new Rectangle(x, y, newW, newH));
        return bitmap;
    }

    private static Bitmap BuildStretchBitmap(Image source, int width, int height)
    {
        var bitmap = new Bitmap(width, height, PixelFormat.Format32bppPArgb);
        using var g = Graphics.FromImage(bitmap);
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        g.DrawImage(source, new Rectangle(0, 0, width, height));
        return bitmap;
    }

    private static void CopyPixelsToBitmap(Bitmap bitmap, int[] pixels)
    {
        var rect = new Rectangle(0, 0, bitmap.Width, bitmap.Height);
        var data = bitmap.LockBits(rect, ImageLockMode.WriteOnly, PixelFormat.Format32bppPArgb);
        try
        {
            Marshal.Copy(pixels, 0, data.Scan0, pixels.Length);
        }
        finally
        {
            bitmap.UnlockBits(data);
        }
    }

    private static void FillRectPixels(int[] pixels, int width, int height, int x1, int y1, int x2, int y2, int color)
    {
        x1 = Math.Clamp(x1, 0, width);
        x2 = Math.Clamp(x2, 0, width);
        y1 = Math.Clamp(y1, 0, height);
        y2 = Math.Clamp(y2, 0, height);
        if (x2 <= x1 || y2 <= y1)
        {
            return;
        }

        for (var y = y1; y < y2; y++)
        {
            var offset = y * width + x1;
            Array.Fill(pixels, color, offset, x2 - x1);
        }
    }

    private static int[] BuildInsets(int half, int count)
    {
        var values = new int[count + 1];
        var baseSize = half / count;
        var rem = half % count;
        var acc = 0;
        for (var i = 0; i < count; i++)
        {
            acc += baseSize + (i < rem ? 1 : 0);
            values[i + 1] = acc;
        }
        return values;
    }

    private static int QuantizeLevel(float value, int steps)
    {
        if (steps <= 1) return 0;
        if (steps >= 256) return (int)Math.Round(Math.Clamp(value, 0f, 255f));
        var ratio = Math.Clamp(value / 255f, 0f, 1f);
        var idx = (int)Math.Round(ratio * (steps - 1));
        return (int)Math.Round(idx * 255f / (steps - 1));
    }

    private static Color ColorFromMode(string mode, int level) =>
        mode switch
        {
            "red" => Color.FromArgb(level, 0, 0),
            "green" => Color.FromArgb(0, level, 0),
            "blue" => Color.FromArgb(0, 0, level),
            "yellow" => Color.FromArgb(level, level, 0),
            "magenta" => Color.FromArgb(level, 0, level),
            "cyan" => Color.FromArgb(0, level, level),
            _ => Color.FromArgb(level, level, level),
        };

    private static bool TryGetColorMode(Keys key, out string mode)
    {
        mode = key switch
        {
            Keys.D1 or Keys.NumPad1 => "red",
            Keys.D2 or Keys.NumPad2 => "green",
            Keys.D3 or Keys.NumPad3 => "blue",
            Keys.D4 or Keys.NumPad4 => "white",
            Keys.D5 or Keys.NumPad5 => "yellow",
            Keys.D6 or Keys.NumPad6 => "magenta",
            Keys.D7 or Keys.NumPad7 => "cyan",
            Keys.D8 or Keys.NumPad8 => "white",
            _ => "white",
        };
        return (key >= Keys.D1 && key <= Keys.D8) || (key >= Keys.NumPad1 && key <= Keys.NumPad8);
    }

    private string FormatElapsed()
    {
        var elapsed = checkerStopwatch.Elapsed;
        return $"{elapsed.Days}:{elapsed.Hours}:{elapsed.Minutes}";
    }
}
