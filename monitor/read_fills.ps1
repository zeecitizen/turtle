# Turtle Trader - Live Trade Fills Reader
# Reads turtle_fills.csv written by TurtleTradeLogger.mq5
# Usage: powershell -ExecutionPolicy Bypass -File read_fills.ps1

param(
    [string]$Date = (Get-Date -Format "yyyy.MM.dd")
)

$CSV_PATH = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"

if (-not (Test-Path $CSV_PATH)) {
    Write-Host "NO_CSV: TurtleTradeLogger not installed yet or no trades closed."
    exit 0
}

try {
    $rows = Import-Csv -Path $CSV_PATH -ErrorAction Stop
} catch {
    Write-Host "READ_ERROR: $_"
    exit 1
}

$today = $rows | Where-Object { $_.broker_time -like "$Date*" }

if ($today.Count -eq 0) {
    Write-Host "NO_TRADES_TODAY: No closed trades for $Date"
    exit 0
}

$totalNet  = 0.0
$wins      = 0
$losses    = 0
$spikes    = 0

foreach ($row in $today) {
    $net = [double]$row.net_pnl
    $totalNet += $net
    if ($net -gt 0) { $wins++ } else { $losses++ }
    if ($net -le -40) { $spikes++ }
}

$count   = $today.Count
$wr      = [math]::Round(($wins / $count) * 100, 1)
$netRnd  = [math]::Round($totalNet, 2)

Write-Host "=== Live Fills - $Date ==="
Write-Host "Trades : $count  (wins=$wins losses=$losses WR=$wr pct)"
Write-Host "Net PnL: $netRnd"
Write-Host "Spikes : $spikes trades at or below -40 USD"
Write-Host "--- Last 10 ---"

$last10 = $today | Select-Object -Last 10
foreach ($row in $last10) {
    $net   = [double]$row.net_pnl
    $netR  = [math]::Round($net, 2)
    $t     = ($row.broker_time -split " ")[1]
    $dir   = ($row.direction -split "_")[0]
    $tag   = ""
    if ($net -le -40) { $tag = " SPIKE" }
    if ($net -ge 150) { $tag = " WIN" }
    Write-Host "  $t  $($row.symbol)  $dir  net=$netR$tag"
}
