# PatternPilot

PatternPilot 是一个原生 Windows 全屏显示图案工具，用于面板测试、图像查看和 Crosstalk 检查。

## 功能特点

- 原生 WinForms 实现，优先关注启动速度和渲染开销
- 支持多显示器全屏显示与快速切换
- 内置灰阶、棋盘格、对齐图、渐变、线条、点阵、Crosstalk、图像模式和 One Third
- 支持将当前画面导出为 PNG
- 内置十字工具，方便像素定位和线位检查

## 软件截图

首页说明页：

![首页说明](docs/screenshots/home.png)

棋盘格画面：

![棋盘格画面](docs/screenshots/checkerboard.png)

更多截图说明见 [docs/screenshots.md](docs/screenshots.md)。

## 快捷键

- `Esc`：退出程序
- `Tab`：切换显示器
- `Ctrl+S`：将当前画面保存为 PNG
- `Ctrl+R`：翻转当前图案
- `Ctrl+F`：开启或关闭十字工具
- `上 / 下`：调整亮度等级
- `Shift + 上 / 下`：快速调整
- `Home / End`：设置等级为 `255 / 0`
- `1-8`：切换颜色模式
- `Ctrl+1 / Ctrl+2`：在 Crosstalk 模式下加载背景图和遮挡图

## 构建方法

环境要求：

- Windows
- .NET 8 SDK

构建：

```powershell
dotnet build PatternPilot\PatternPilot.csproj -c Release
```

发布目录版：

```powershell
powershell -ExecutionPolicy Bypass -File PatternPilot\publish.ps1 -Mode dir
```

发布单文件版：

```powershell
powershell -ExecutionPolicy Bypass -File PatternPilot\publish.ps1 -Mode single
```

## 项目结构

- [PatternPilot/PatternPilot.csproj](PatternPilot/PatternPilot.csproj)：原生项目文件
- [PatternPilot/PatternForm.cs](PatternPilot/PatternForm.cs)：核心窗口、渲染、图案和输入处理
- [PatternPilot/StartupMetrics.cs](PatternPilot/StartupMetrics.cs)：启动时间记录
- [PatternPilot/publish.ps1](PatternPilot/publish.ps1)：发布脚本
- [PatternPilot/measure_startup.ps1](PatternPilot/measure_startup.ps1)：启动测速脚本

## 说明

- 软件默认首页内置了中文使用说明
- `One Third` 画面规则为 `1/3` 白色、`2/3` 黑色
- 仓库中保留了原始 Python 参考实现：[main.py](main.py)
