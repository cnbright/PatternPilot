param(
    [ValidateSet("single", "dir")]
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
} else {
    $output = Join-Path $PSScriptRoot "artifacts\\dir"
    dotnet @common "-o" $output --self-contained false /p:PublishSingleFile=false
}
