# crons/jobs/daily_scorecard.ps1
# Reads last 7 days of newsfeed archive + turtle_fills.csv.
# Computes per-cron usefulness scores and daily trading summary.
# Pure PowerShell — runs via Windows Task Scheduler at 00:05 UTC daily.
param()

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\lib\newsfeed_writer.ps1"
. "$PSScriptRoot\..\lib\newsfeed_reader.ps1"

$cronId      = 'daily_scorecard'
$cronName    = 'Daily Scorecard'
$cronVersion = '1.0.0'
$startedAt   = [datetime]::UtcNow

try {
    $repoRoot  = (Resolve-Path "$PSScriptRoot\..\..\").Path
    $since7d   = [datetime]::UtcNow.AddDays(-7)
    $yesterday = [datetime]::UtcNow.AddDays(-1).ToString("yyyy-MM-dd")

    # ─── Per-cron usefulness scores ───────────────────────────────────────────
    $manifestPath = Join-Path $repoRoot "crons\manifest.json"
    $cronDefs     = @()
    if (Test-Path $manifestPath) {
        $mf       = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $cronDefs = @($mf.crons | Where-Object { $_.enabled })
    }

    $perCron = @{}
    $ranking = @()

    foreach ($cron in $cronDefs) {
        $entries = @(Get-Entries -CronId $cron.id -SinceUtc $since7d -Limit 5000)
        $runs    = $entries.Count
        if ($runs -eq 0) { continue }

        $errors      = @($entries | Where-Object { $_.status -eq 'error' }).Count
        $actEntries  = @($entries | Where-Object { $_.actionable -eq $true }).Count
        $novEntries  = @($entries | Where-Object { $_.novel -eq $true }).Count
        $durations   = @($entries | Where-Object { $_.duration_ms } | ForEach-Object { [int]$_.duration_ms })
        $avgDuration = if ($durations) { [int]($durations | Measure-Object -Average | Select-Object -ExpandProperty Average) } else { 0 }

        $errorRate      = if ($runs -gt 0) { [math]::Round($errors / $runs, 4) } else { 0 }
        $actionableRate = if ($runs -gt 0) { [math]::Round($actEntries / $runs, 4) } else { 0 }
        $novelRate      = if ($runs -gt 0) { [math]::Round($novEntries / $runs, 4) } else { 0 }
        $usefulScore    = [math]::Round(0.4 * $actionableRate + 0.4 * $novelRate + 0.2 * (1 - $errorRate), 4)

        $perCron[$cron.id] = @{
            runs            = $runs
            error_rate      = $errorRate
            actionable_rate = $actionableRate
            novel_rate      = $novelRate
            avg_duration_ms = $avgDuration
            usefulness_score= $usefulScore
        }
        $ranking += [PSCustomObject]@{ id = $cron.id; score = $usefulScore }
    }

    $ranking = $ranking | Sort-Object score -Descending

    # ─── Yesterday's trading summary ─────────────────────────────────────────
    $fillsPath   = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"
    $tradingStats= @{ fills_found = $false }
    if (Test-Path $fillsPath) {
        $fills = Import-Csv $fillsPath -ErrorAction SilentlyContinue
        $yFills= @($fills | Where-Object {
            try { [datetime]::Parse(($_.broker_time -replace '\.', '-' -replace '(\d{4}-\d{2}-\d{2})-(\d{2}:\d{2}:\d{2})','$1 $2')).Date.ToString("yyyy-MM-dd") -eq $yesterday } catch { $false }
        })
        $profits = @($yFills | ForEach-Object { [double]$_.net_pnl })
        $tradingStats = @{
            fills_found = $true
            yesterday   = $yesterday
            trades      = $yFills.Count
            wins        = @($profits | Where-Object { $_ -gt 0 }).Count
            losses      = @($profits | Where-Object { $_ -le 0 }).Count
            net_pnl     = [math]::Round(($profits | Measure-Object -Sum | Select-Object -ExpandProperty Sum), 2)
            spike_sl    = @($profits | Where-Object { $_ -le -40 }).Count
        }
    }

    # ─── Output ───────────────────────────────────────────────────────────────
    $topCron   = if ($ranking) { $ranking[0].id } else { "n/a" }
    $trades    = $tradingStats.trades
    $netPnl    = $tradingStats.net_pnl
    $summary   = "Scorecard $yesterday: trades=$trades net=`$$netPnl | Top cron: $topCron"
    $result    = @{ scorecard_date = $yesterday; period_days = 7; per_cron = $perCron; ranking = @($ranking | ForEach-Object { $_.id }); trading = $tradingStats }

    Write-NewsfeedEntry `
        -CronId      $cronId `
        -CronName    $cronName `
        -CronVersion $cronVersion `
        -StartedAt   $startedAt `
        -Status      'success' `
        -Summary     $summary `
        -Result      $result `
        -Novel       $true

    Write-Host "SCORECARD: $summary"
    Write-Host "Ranking: $($ranking | ForEach-Object { "$($_.id)=$($_.score)" } | Select-Object -First 5 | Join-String -Separator ' > ')"
    exit 0
}
catch {
    Write-NewsfeedEntry `
        -CronId      $cronId `
        -CronName    $cronName `
        -CronVersion $cronVersion `
        -StartedAt   $startedAt `
        -Status      'error' `
        -Summary     "Scorecard failed: $($_.Exception.Message.Substring(0, [Math]::Min(150, $_.Exception.Message.Length)))" `
        -Result      @{} `
        -ErrorInfo   @{ message = $_.Exception.Message; stack = $_.ScriptStackTrace; retriable = $false }
    Write-Host "ERROR: $_"
    exit 1
}
