# claude_accuracy.ps1
# Compares Claude's UHV signal log vs actual MT5 fills to compute Claude's win rate
# Usage: powershell -ExecutionPolicy Bypass -File claude_accuracy.ps1

$SIGNALS_PATH = "$PSScriptRoot\claude_signals.csv"
$FILLS_PATH   = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"

if (-not (Test-Path $SIGNALS_PATH)) {
    Write-Host "NO_SIGNALS: claude_signals.csv not found"
    exit 0
}

$signals = Import-Csv $SIGNALS_PATH
$total   = $signals.Count

if ($total -eq 0) {
    Write-Host "NO_SIGNALS: 0 Claude signals logged yet"
    exit 0
}

if (-not (Test-Path $FILLS_PATH)) {
    Write-Host "NO_FILLS: turtle_fills.csv not found — cannot match"
    exit 0
}

$fills = Import-Csv $FILLS_PATH

$wins   = 0
$losses = 0
$unmatched = 0

foreach ($sig in $signals) {
    $sigTime = [DateTime]::ParseExact($sig.timestamp, "yyyy-MM-dd HH:mm:ss", $null)
    $sigDir  = $sig.direction.ToUpper()

    # Find fill within 3 minutes of signal time with matching direction
    $match = $fills | Where-Object {
        try {
            $fTime = [DateTime]::ParseExact(($_.broker_time -replace "\.", "-" -replace "(\d{4}-\d{2}-\d{2})-(\d{2}:\d{2}:\d{2})", '$1 $2'), "yyyy-MM-dd HH:mm:ss", $null)
            $diff  = [Math]::Abs(($fTime - $sigTime).TotalSeconds)
            $fDir  = $_.direction -replace "_closed", ""
            $diff -le 180 -and $fDir -eq $sigDir
        } catch { $false }
    } | Select-Object -First 1

    if ($match) {
        $pnl = [double]$match.net_pnl
        if ($pnl -gt 0) { $wins++ } else { $losses++ }
    } else {
        $unmatched++
    }
}

$matched = $wins + $losses
$wr      = if ($matched -gt 0) { [math]::Round($wins / $matched * 100, 1) } else { 0 }

Write-Host "=== Claude UHV Accuracy ==="
Write-Host "Signals sent : $total"
Write-Host "Matched fills: $matched  (unmatched=$unmatched — may be open or deduped)"
Write-Host "Win rate     : $wr%  ($wins W / $losses L)"
Write-Host ""
Write-Host "--- Indicator baseline ---"
Write-Host "Pine UHV     : 25% WR  (474/1925 all-time sim)"
if ($wr -gt 25) {
    Write-Host "RESULT: Claude BEATS indicator (+$([math]::Round($wr - 25, 1))pp)"
} elseif ($wr -gt 0) {
    Write-Host "RESULT: Claude BELOW indicator (-$([math]::Round(25 - $wr, 1))pp)"
} else {
    Write-Host "RESULT: Not enough matched data yet"
}
