param(
    [ValidateSet("single", "dir", "single-small")]
    [string]$Mode = "single"
)

$project = Join-Path $PSScriptRoot "PatternPilot.csproj"
$common = @(
    "publish",
    $project,
    "-c", "Release",
    "-r", "win-x64"
)

if ($Mode -eq "single") {
    $output = Join-Path $PSScriptRoot "artifacts\\single"
    dotnet @common "-o" $output --self-contained true /p:PublishSingleFile=true /p:IncludeNativeLibrariesForSelfExtract=true
} elseif ($Mode -eq "single-small") {
    $output = Join-Path $PSScriptRoot "artifacts\\single-small"
    dotnet @common "-o" $output --self-contained false /p:PublishSingleFile=true /p:PublishReadyToRun=false /p:IncludeNativeLibrariesForSelfExtract=false /p:DebugType=None /p:DebugSymbols=false
} else {
    $output = Join-Path $PSScriptRoot "artifacts\\dir"
    dotnet @common "-o" $output --self-contained false /p:PublishSingleFile=false
}
