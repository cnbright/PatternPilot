param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [int]$Iterations = 5
)

$metricsPath = Join-Path $env:TEMP "PatternPilot\\startup_metrics.log"
if (Test-Path $metricsPath) {
    Remove-Item $metricsPath -Force
}

for ($i = 0; $i -lt $Iterations; $i++) {
    $proc = Start-Process -FilePath $ExePath -PassThru
    Start-Sleep -Milliseconds 800
    if (!$proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
    Start-Sleep -Milliseconds 200
}

if (Test-Path $metricsPath) {
    Get-Content $metricsPath
} else {
    Write-Error "No startup metrics log found: $metricsPath"
}
