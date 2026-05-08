# OpenGenealogyAI — Auto-Restart Pipeline (PowerShell)
# More robust than the .bat version: logs each restart with timestamp,
# skips restart if pipeline ran < 30 seconds (crash loop protection).
#
# Usage:
#   .\start_pipeline.ps1
#   .\start_pipeline.ps1 -RestartDelaySeconds 120

param(
    [int]$RestartDelaySeconds = 60,
    [int]$CrashLoopThresholdSeconds = 30
)

$Host.UI.RawUI.WindowTitle = "OpenGenealogyAI Pipeline"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$RestartLog = Join-Path $ScriptDir "_logs\pipeline_restarts.log"
$null = New-Item -ItemType Directory -Force -Path (Split-Path $RestartLog)

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $Message"
    Write-Host $line
    Add-Content -Path $RestartLog -Value $line
}

Write-Log "=== Pipeline auto-restart supervisor started ==="
Write-Log "Restart delay: ${RestartDelaySeconds}s | Crash-loop threshold: ${CrashLoopThresholdSeconds}s"

$restartCount = 0

while ($true) {
    $startTime = Get-Date
    Write-Log "Starting pipeline (restart #$restartCount)..."

    try {
        $process = Start-Process -FilePath "python" `
            -ArgumentList "-X utf8 -m pipeline.orchestrator" `
            -NoNewWindow -PassThru -Wait
        $exitCode = $process.ExitCode
    } catch {
        $exitCode = -1
        Write-Log "ERROR launching python: $_"
    }

    $elapsed = (Get-Date) - $startTime
    Write-Log "Pipeline stopped (exit=$exitCode, ran for $($elapsed.ToString('hh\:mm\:ss')))"

    # Crash-loop protection: if it died in under threshold, warn loudly
    if ($elapsed.TotalSeconds -lt $CrashLoopThresholdSeconds) {
        Write-Log "WARNING: Pipeline crashed very quickly. Waiting extra 120s before restart."
        Write-Log "Check logs at: $ScriptDir\_logs\"
        Start-Sleep -Seconds 120
    } else {
        Write-Log "Normal stop. Restarting in ${RestartDelaySeconds}s..."
        Start-Sleep -Seconds $RestartDelaySeconds
    }

    $restartCount++
}
