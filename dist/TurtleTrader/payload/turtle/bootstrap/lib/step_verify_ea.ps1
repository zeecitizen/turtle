# bootstrap/lib/step_verify_ea.ps1
# Checks EA health: turtle_fills.csv exists + was written recently enough.
# Missing/stale fills → degraded mode (not fatal — EA may simply have no trades yet today).

function Invoke-StepVerifyEA {
    $fillsPath   = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"
    $logGlob     = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\*\MQL5\Logs\*.log"
    $flags       = @()
    $details     = @{}

    # 1. Fills CSV
    if (-not (Test-Path $fillsPath)) {
        $flags   += 'EA_NOT_INSTALLED'
        $details.fills = "missing"
        $summary = "EA not installed — turtle_fills.csv not found [EA_NOT_INSTALLED]"
        return @{ success = $true; summary = $summary; flags = $flags; details = $details }
    }

    $fillsAge = [int]([datetime]::UtcNow - (Get-Item $fillsPath).LastWriteTimeUtc).TotalMinutes
    $details.fills_age_min = $fillsAge

    # Only flag stale during market hours (Mon-Fri 06:00-22:00 UTC)
    $h   = [datetime]::UtcNow.Hour
    $dow = [int][datetime]::UtcNow.DayOfWeek
    $isMarketHours = ($dow -ge 1 -and $dow -le 5) -and ($h -ge 6 -and $h -le 22)

    if ($isMarketHours -and $fillsAge -gt 60) {
        $flags += 'FILLS_STALE'
    }

    # 2. EA log file exists?
    $logFiles = Get-ChildItem $logGlob -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($logFiles) {
        $logAge = [int]([datetime]::UtcNow - $logFiles.LastWriteTimeUtc).TotalMinutes
        $details.log_age_min = $logAge
        if ($logAge -gt 30 -and $isMarketHours) {
            $flags += 'MT5_LOG_STALE'
        }
    } else {
        $details.log_age_min = $null
        $flags += 'NO_LOG'
    }

    # 3. Row count sanity
    try {
        $rows = (Import-Csv $fillsPath -ErrorAction SilentlyContinue | Measure-Object).Count
        $details.fill_rows = $rows
    } catch {
        $details.fill_rows = "parse_error"
    }

    $fillsStatus = if ($fillsAge -lt 5) { "fresh" } elseif ($isMarketHours -and $fillsAge -gt 60) { "STALE(${fillsAge}m)" } else { "${fillsAge}m old" }
    $summary = "EA verified: fills=$fillsStatus rows=$($details.fill_rows)"
    if ($flags) { $summary += " [" + ($flags -join ',') + "]" }

    return @{ success = $true; summary = $summary; flags = $flags; details = $details }
}
