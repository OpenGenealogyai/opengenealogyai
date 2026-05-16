<#
.SYNOPSIS
  Nightly Postgres backup for OpenGenealogyAI.

.DESCRIPTION
  Runs pg_dump on the opengenealogyai database, compresses, and writes the
  output to D:\Backups\postgres\. BitLocker-encrypted at rest (whole-disk
  encryption on D:).

  Phase 1: local-only. Off-site upload (Backblaze B2 / Dropbox / Drive) is
  added in a future revision once Garlon picks a destination. When off-site
  is added, pg_dump output will be GPG-encrypted before upload.

  Retention: keeps last 14 daily backups, last 8 weekly (Sunday), last 12
  monthly (1st of month). Older files pruned.

.NOTES
  Authentication: silent via %APPDATA%\postgresql\pgpass.conf
  Scheduled via:  Task Scheduler entry "OpenGenealogyAI-Postgres-Backup"
                  runs daily 03:00 under current user (no admin required)
  Test manually:  pwsh -File scripts\backup_postgres.ps1 -Verbose
#>

[CmdletBinding()]
param(
    [string]$BackupDir = "D:\Backups\postgres",
    [string]$Database  = "opengenealogyai",
    [string]$PgUser    = "postgres",
    [string]$PgBin     = "C:\Program Files\PostgreSQL\17\bin",
    [int]$KeepDaily    = 14,
    [int]$KeepWeekly   = 8,
    [int]$KeepMonthly  = 12
)

$ErrorActionPreference = 'Stop'

function Write-Log {
    param([string]$msg)
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-Host "[$stamp] $msg"
}

# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------
$env:PATH = "$PgBin;$env:PATH"

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    Write-Log "Created backup dir: $BackupDir"
}

$logDir = Join-Path $BackupDir "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# ----------------------------------------------------------------------------
# Classification: daily / weekly / monthly
# ----------------------------------------------------------------------------
$now = Get-Date
$tier = "daily"
if ($now.Day -eq 1) { $tier = "monthly" }
elseif ($now.DayOfWeek -eq 'Sunday') { $tier = "weekly" }

$timestamp = $now.ToString("yyyyMMdd-HHmmss")
$basename  = "opengenealogyai-$tier-$timestamp"
$dumpFile  = Join-Path $BackupDir "$basename.dump"
$logFile   = Join-Path $logDir   "$basename.log"

Write-Log "Tier: $tier"
Write-Log "Target: $dumpFile"

# ----------------------------------------------------------------------------
# Backup — custom format (-Fc) for fast parallel restore + native compression
# ----------------------------------------------------------------------------
$start = Get-Date
try {
    & pg_dump -U $PgUser -d $Database -Fc -Z 6 -f $dumpFile 2>&1 | Tee-Object -FilePath $logFile
    if ($LASTEXITCODE -ne 0) { throw "pg_dump exited with code $LASTEXITCODE" }
} catch {
    Write-Log "BACKUP FAILED: $_"
    "FAILED: $_" | Out-File $logFile -Append
    exit 1
}

$elapsed = ((Get-Date) - $start).TotalSeconds
$sizeMB  = [math]::Round((Get-Item $dumpFile).Length / 1MB, 2)
Write-Log ("OK: $sizeMB MB in {0:N1} s" -f $elapsed)

# ----------------------------------------------------------------------------
# Integrity check — verify pg_dump file is restorable (table-of-contents only)
# ----------------------------------------------------------------------------
$toc = & pg_restore -l $dumpFile 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Log "INTEGRITY CHECK FAILED — backup file is unreadable"
    Move-Item $dumpFile "$dumpFile.CORRUPT"
    exit 2
}
$entryCount = ($toc | Where-Object { $_ -match '^\d' }).Count
Write-Log "Integrity OK: $entryCount entries in TOC"

# ----------------------------------------------------------------------------
# Retention pruning
# ----------------------------------------------------------------------------
function Prune-Tier {
    param([string]$Tier, [int]$Keep)
    $files = Get-ChildItem $BackupDir -Filter "opengenealogyai-$Tier-*.dump" | Sort-Object LastWriteTime -Descending
    if ($files.Count -gt $Keep) {
        $toDelete = $files | Select-Object -Skip $Keep
        foreach ($f in $toDelete) {
            Remove-Item $f.FullName -Force
            Write-Log "Pruned: $($f.Name)"
        }
    }
}

Prune-Tier -Tier "daily"   -Keep $KeepDaily
Prune-Tier -Tier "weekly"  -Keep $KeepWeekly
Prune-Tier -Tier "monthly" -Keep $KeepMonthly

# Prune logs older than 60 days
Get-ChildItem $logDir -Filter "*.log" | Where-Object { $_.LastWriteTime -lt $now.AddDays(-60) } | Remove-Item -Force

Write-Log "Done."
exit 0
