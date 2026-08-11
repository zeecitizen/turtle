$GUID = 'DBE9B8B347D025DD139E103EE3B63FD8'
$MT5_ROOT = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\$GUID"
$EXPERTS  = "$MT5_ROOT\MQL5\Experts"
$SCRIPTS  = "$MT5_ROOT\MQL5\Scripts"
$COMMON   = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\Common\Files"

# Make sure the bad copies (created at wrong path earlier) are removed
$wrongPath = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\MQL5"
if (Test-Path $wrongPath) { Remove-Item -Recurse -Force $wrongPath }

# Create dirs
New-Item -ItemType Directory -Force -Path $EXPERTS, $SCRIPTS, $COMMON | Out-Null

# Refresh from latest GitHub (in case repo was pushed since clone)
Set-Location C:\turtle
git pull --rebase --autostash 2>&1 | Out-Null

# Copy EA + scripts that exist
$mq5Files = @{
    'S1Trader.mq5' = $EXPERTS;
    'ExportRecentTicks.mq5' = $SCRIPTS;
    'ExportTodayTicks.mq5' = $SCRIPTS;
    'ExportFeb11Ticks.mq5' = $SCRIPTS;
}
foreach ($f in $mq5Files.Keys) {
    $src = "C:\turtle\mt5\$f"
    if (Test-Path $src) {
        Copy-Item $src -Destination "$($mq5Files[$f])\$f" -Force
        Write-Host "Copied $f"
    } else {
        Write-Host "SKIP $f (not in repo)"
    }
}

# Runtime config — safe defaults (ASCII only, no em-dashes!)
$rt = @'
{
"auto_close_ms": 0,
"daily_loss_halt": 200,
"daily_profit_target": 0,
"trail_lock_pts": 0,
"trail_rev_pts": 0,
"require_hhhl_m5": false,
"require_h1bias": false,
"require_uhv_neighbor_peak": false,
"uhv_body_min": 0.30,
"max_bars_since_uhv": 0,
"require_breakout_body_close": false,
"allowed_hours_utc": "5,12,15,19",
"min_sweep_depth_pts": 0.30,
"max_breakout_wick_pct": 0.0,
"require_h1_agrees_v2": false,
"max_retracement_wick_pct": 0.45,
"require_breakout_color": true,
"uhv_global_max": true
}
'@
Set-Content -Path "$COMMON\s1_runtime_88005.json" -Value $rt -Encoding ASCII

Write-Host ''
Write-Host '=== Files deployed ==='
Get-ChildItem "$EXPERTS\S1Trader.mq5" | Select-Object FullName, Length
Get-ChildItem "$SCRIPTS\Export*.mq5" -ErrorAction SilentlyContinue | Select-Object Name, Length
Get-ChildItem "$COMMON\s1_runtime_88005.json" | Select-Object FullName, Length
