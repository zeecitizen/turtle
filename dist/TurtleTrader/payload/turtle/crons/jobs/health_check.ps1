# crons/jobs/health_check.ps1
# Checks: TV/MT5 process, fills freshness, cron overdue, inbox overflow.
# Pure PowerShell — runs 24/7 via Windows Task Scheduler. No Claude session needed.
param()

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\newsfeed_writer.ps1"
. "$PSScriptRoot\..\lib\newsfeed_reader.ps1"

$cronId      = 'health_check'
$cronName    = 'Health Check'
$cronVersion = '1.0.0'
$startedAt   = [datetime]::UtcNow

try {
    $flags     = @()
    $issues    = @()
    $checks    = @{}

    # 1. TV CDP reachable?
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:9222/json/version" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        $checks.tv_cdp = "ok"
    } catch {
        $checks.tv_cdp = "down"
        $flags += 'TV_DOWN'
        $issues += "TV CDP not reachable (localhost:9222)"
    }

    # 2. MT5 running?
    $mt5Running = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
    $checks.mt5 = if ($mt5Running) { "ok" } else { "down" }
    if (-not $mt5Running) {
        $flags += 'MT5_DOWN'
        $issues += "MT5 terminal64.exe not running"
    }

    # 3. turtle_fills.csv fresh?
    $fillsPath = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"
    if (Test-Path $fillsPath) {
        $fillsAge = [int]([datetime]::UtcNow - (Get-Item $fillsPath).LastWriteTimeUtc).TotalMinutes
        $checks.fills_age_min = $fillsAge
        # Only flag during expected market hours (Mon-Fri, 06:00-22:00 UTC)
        $h = [datetime]::UtcNow.Hour
        $dow = [int][datetime]::UtcNow.DayOfWeek
        $isMarketHours = ($dow -ge 1 -and $dow -le 5) -and ($h -ge 6 -and $h -le 22)
        if ($isMarketHours -and $fillsAge -gt 60) {
            $flags += 'FILLS_STALE'
            $issues += "turtle_fills.csv not updated in ${fillsAge}m"
        }
    } else {
        $checks.fills_age_min = $null
        $flags += 'EA_NOT_INSTALLED'
        $issues += "turtle_fills.csv not found"
    }

    # 4. Inbox overflow?
    $repoRoot    = (Resolve-Path "$PSScriptRoot\..\..\").Path
    $inboxDir    = Join-Path $repoRoot "newsfeed\inbox"
    $inboxCount  = (Get-ChildItem $inboxDir -Filter "*.json" -ErrorAction SilentlyContinue | Measure-Object).Count
    $checks.inbox_count = $inboxCount
    if ($inboxCount -gt 1000) {
        $flags += 'INBOX_OVERFLOW'
        $issues += "inbox has $inboxCount files — consolidation broken"
    }

    # 5. Any session crons overdue? (check INDEX.json last run times vs 3x schedule)
    $manifestPath = Join-Path $repoRoot "crons\manifest.json"
    if (Test-Path $manifestPath) {
        $mf = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($cron in ($mf.crons | Where-Object { $_.enabled })) {
            $latest = Get-LatestEntry -CronId $cron.id
            if ($latest) {
                $lastRan = [datetime]::Parse($latest.finished_at)
                $intervalMin = switch -Wildcard ($cron.schedule) {
                    "* * * * *"   { 1 }
                    "*/5 * * * *" { 5 }
                    "*/10 * * * *"{ 10 }
                    "*/15 * * * *"{ 15 }
                    "*/30 * * * *"{ 30 }
                    "5 0 * * *"   { 1440 }
                    default        { 60 }
                }
                $thresholdMin = $intervalMin * 3
                $agoMin = [int]([datetime]::UtcNow - $lastRan).TotalMinutes
                if ($agoMin -gt $thresholdMin) {
                    $flags += 'CRON_OVERDUE'
                    $issues += "$($cron.id) last ran ${agoMin}m ago (threshold ${thresholdMin}m)"
                }
            }
        }
    }

    $allOk   = $flags.Count -eq 0
    $summary = if ($allOk) {
        "All checks OK — TV:$($checks.tv_cdp) MT5:$($checks.mt5) fills:<$($checks.fills_age_min)m inbox:$inboxCount"
    } else {
        "ISSUES: $($issues -join '; ')"
    }

    Write-NewsfeedEntry `
        -CronId      $cronId `
        -CronName    $cronName `
        -CronVersion $cronVersion `
        -StartedAt   $startedAt `
        -Status      (if ($allOk) { 'success' } else { 'partial' }) `
        -Summary     $summary `
        -Result      @{ checks = $checks; issues = $issues } `
        -Flags       $flags `
        -Actionable  ($flags.Count -gt 0) `
        -Novel       ($flags.Count -gt 0)

    Write-Host ($allOk ? "HEALTH: OK" : "HEALTH: $($flags -join ',') — $($issues -join '; ')")
    exit 0
}
catch {
    Write-NewsfeedEntry `
        -CronId      $cronId `
        -CronName    $cronName `
        -CronVersion $cronVersion `
        -StartedAt   $startedAt `
        -Status      'error' `
        -Summary     "Health check failed: $($_.Exception.Message.Substring(0, [Math]::Min(150, $_.Exception.Message.Length)))" `
        -Result      @{} `
        -ErrorInfo   @{ message = $_.Exception.Message; stack = $_.ScriptStackTrace; retriable = $true }
    Write-Host "ERROR: $_"
    exit 1
}
