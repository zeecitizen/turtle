# ================================================================
#  Turtle Trader - MT5 EA Log Parser
#  Reads today's PineConnector log and outputs trading summary
#  Usage: powershell -ExecutionPolicy Bypass -File read_mt5_log.ps1
#         powershell -ExecutionPolicy Bypass -File read_mt5_log.ps1 -Date 20260420
# ================================================================

param(
    [string]$Date = (Get-Date -Format "yyyyMMdd")
)

$LOG_DIR = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs"
$logPath = Join-Path $LOG_DIR "$Date.log"

if (-not (Test-Path $logPath)) {
    Write-Host "NO_LOG: $logPath"
    exit 1
}

# Read while MT5 has it open (use FileShare.ReadWrite)
try {
    $fs      = [System.IO.File]::Open($logPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $reader  = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::Unicode)
    $content = $reader.ReadToEnd()
    $reader.Close(); $fs.Close()
} catch {
    Write-Host "READ_ERROR: $_"
    exit 1
}

# --- Extract all signals ---
$sigMatches = [regex]::Matches($content, '(\d{2}:\d{2}:\d{2})\.\d+.*?Signal ID:\s*([\w.]+)\s*\|\s*Latency:\s*([\d.]+)\s*\|\s*Command:\s*(\w+)\s*\|\s*Symbol:\s*(\w+)\s*\|\s*SL:\s*([\d.]+)\s*\|\s*TP:\s*([\d.]+)')

# --- Extract BE events ---
$beMatches = [regex]::Matches($content, 'Activating BE SL on (\w+) trade #(\d+)')

# --- Build summary ---
$tradeCount = $sigMatches.Count
$beCount    = $beMatches.Count
$buys       = 0
$sells      = 0
$latestTime = "none"
$latestSL   = "?"
$latestCmd  = "?"
$highLat    = @()

foreach ($m in $sigMatches) {
    $cmd = $m.Groups[4].Value
    if ($cmd -eq "BUY")  { $buys++ }
    if ($cmd -eq "SELL") { $sells++ }
    $latestTime = $m.Groups[1].Value
    $latestSL   = $m.Groups[6].Value
    $latestCmd  = $cmd
    $lat = [double]$m.Groups[3].Value
    if ($lat -gt 500) { $highLat += "$($m.Groups[1].Value)(lat=$($lat)ms)" }
}

$slWarning = if ($latestSL -eq "15.0") { " !!! WARN: SL=15 in alerts (iExHSL fix NOT applied!)" } else { "" }

Write-Host "=== MT5 EA Summary - $Date ==="
Write-Host "Signals : $($tradeCount)  (buy=$($buys) / sell=$($sells))"
Write-Host "BE fired: $($beCount)  (these trades became risk-free / likely winners)"
Write-Host "Last sig: $($latestTime) UTC  cmd=$($latestCmd)  SL=$($latestSL) pips$($slWarning)"

if ($highLat.Count -gt 0) {
    Write-Host "HIGH LATENCY: $($highLat -join ' | ')"
}

$likelyLosers  = $tradeCount - $beCount
Write-Host ""
Write-Host "Rough split: ~$($likelyLosers) kill-timer exits | ~$($beCount) went BE (potential wins)"
Write-Host "(Actual P&L requires MT5 History - this is EA signal log only)"
