# install_logger.ps1 — Headless install + auto-attach of TurtleTradeLogger EA
# Compiles the EA, writes a XAUUSD M5 chart profile entry, restarts MT5, and
# verifies the "ready" line appears in the Experts log.
#
# Usage: powershell -ExecutionPolicy Bypass -File mt5\install_logger.ps1
# Run from the turtle repo root.

$ErrorActionPreference = 'Stop'

$TERMINAL_HASH = "DBE9B8B347D025DD139E103EE3B63FD8"
$MT5_DATA      = "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\$TERMINAL_HASH"
$MT5_EXE       = "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
$METAEDITOR    = "C:\Program Files\Blueberry Markets MetaTrader 5\metaeditor64.exe"
$SRC_MQ5       = "$PSScriptRoot\TurtleTradeLogger.mq5"
$DST_MQ5       = "$MT5_DATA\MQL5\Experts\TurtleTradeLogger.mq5"
$DST_EX5       = "$MT5_DATA\MQL5\Experts\TurtleTradeLogger.ex5"
$PROFILE_DIR   = "$MT5_DATA\MQL5\Profiles\Charts\Default"
$CHART_FILE    = "$PROFILE_DIR\chart02.chr"
$LOG_DATE      = (Get-Date -Format "yyyyMMdd")
$MT5_LOG       = "$MT5_DATA\MQL5\Logs\$LOG_DATE.log"

# ── STEP 1: Copy source ──────────────────────────────────────────────────────
Write-Host "[1/6] Copying TurtleTradeLogger.mq5 to Experts folder..."
if (-not (Test-Path $SRC_MQ5)) {
    Write-Error "Source not found: $SRC_MQ5"
    exit 1
}
Copy-Item $SRC_MQ5 $DST_MQ5 -Force
Write-Host "      Copied to: $DST_MQ5"

# ── STEP 2: Compile headless ─────────────────────────────────────────────────
Write-Host "[2/6] Compiling with MetaEditor (headless)..."
$compileLog = $DST_MQ5 -replace '\.mq5$', '.log'
$proc = Start-Process -FilePath $METAEDITOR `
    -ArgumentList "/compile:`"$DST_MQ5`"", "/log:`"$compileLog`"" `
    -Wait -PassThru -NoNewWindow
Start-Sleep -Seconds 3

# ── STEP 3: Check compile result ─────────────────────────────────────────────
Write-Host "[3/6] Checking compilation result..."
if (-not (Test-Path $DST_EX5)) {
    Write-Error "Compile FAILED: $DST_EX5 not found."
    if (Test-Path $compileLog) {
        Write-Host "--- Compile log ---"
        Get-Content $compileLog -Encoding Unicode | Write-Host
    }
    exit 1
}
if (Test-Path $compileLog) {
    $logContent = Get-Content $compileLog -Encoding Unicode -Raw
    if ($logContent -match '(\d+) error') {
        $errCount = $matches[1]
        if ([int]$errCount -gt 0) {
            Write-Error "Compile FAILED with $errCount errors:"
            Write-Host $logContent
            exit 1
        }
    }
}
Write-Host "      Compile OK. $DST_EX5 exists."

# ── STEP 4: Write XAUUSD M5 chart file to Default profile ───────────────────
Write-Host "[4/6] Writing XAUUSD M5 chart file with TurtleTradeLogger..."

# Backup existing chart02 if present
if (Test-Path $CHART_FILE) {
    $backup = $CHART_FILE -replace '\.chr$', '.chr.bak'
    Copy-Item $CHART_FILE $backup -Force
    Write-Host "      Backed up existing chart02.chr"
}

# MT5 chart file format (Unicode/UTF-16LE, Windows line endings)
# period_type=0, period_size=5 = XAUUSD M5
# <expert> block inside <window> enables auto-attach on terminal start
$chartContent = @"
<chart>
id=0
symbol=XAUUSD
description=Gold - US Dollar
period_type=0
period_size=5
digits=2
tick_size=0.000000
position_time=0
scale_fix=0
scale_fixed_min=0.000000
scale_fixed_max=0.000000
scale_fix11=0
scale_bar=0
scale_bar_val=1.000000
scale=16
mode=1
fore=0
grid=1
volume=3
scroll=1
shift=0
shift_size=20.000000
fixed_pos=0.000000
ticker=1
ohlc=0
one_click=0
one_click_btn=1
bidline=1
askline=0
lastline=0
days=0
descriptions=0
tradelines=1
tradehistory=1
window_left=0
window_top=0
window_right=0
window_bottom=0
window_type=1
floating=0
floating_left=0
floating_top=0
floating_right=0
floating_bottom=0
floating_type=1
floating_toolbar=1
floating_tbstate=
background_color=0
foreground_color=16777215
barup_color=65280
bardown_color=65280
bullcandle_color=0
bearcandle_color=16777215
chartline_color=65280
volumes_color=3329330
grid_color=10061943
bidline_color=10061943
askline_color=255
lastline_color=49152
stops_color=255
windows_total=1

<window>
height=100.000000
objects=0

<indicator>
name=Main
path=
apply=1
show_data=1
scale_inherit=0
scale_line=0
scale_line_percent=50
scale_line_value=0.000000
scale_fix_min=0
scale_fix_min_val=0.000000
scale_fix_max=0
scale_fix_max_val=0.000000
expertmode=0
fixed_height=-1
</indicator>

<expert>
name=TurtleTradeLogger
path=Experts\TurtleTradeLogger.ex5
expertmode=5
<inputs>
InpFileName=turtle_fills.csv
InpLogOpens=0
</inputs>
</expert>

</window>
</chart>
"@

# Write as UTF-16LE with BOM (same encoding MT5 uses for .chr files)
$enc = New-Object System.Text.UnicodeEncoding($false, $true)  # little-endian, include BOM
[System.IO.File]::WriteAllText($CHART_FILE, $chartContent, $enc)
Write-Host "      Written: $CHART_FILE"

# ── STEP 5: Restart MT5 ──────────────────────────────────────────────────────
Write-Host "[5/6] Restarting MetaTrader 5..."
Get-Process -Name "terminal64" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Start-Process $MT5_EXE
Write-Host "      MT5 relaunched. Waiting up to 20s for TurtleTradeLogger ready..."

# ── STEP 6: Verify in Experts log ────────────────────────────────────────────
Write-Host "[6/6] Watching MT5 Experts log for 'TurtleTradeLogger v1.01 ready'..."
$deadline = (Get-Date).AddSeconds(20)
$found = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (Test-Path $MT5_LOG) {
        try {
            $fs = [System.IO.File]::Open($MT5_LOG, [System.IO.FileMode]::Open,
                  [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $reader = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::Unicode)
            $content = $reader.ReadToEnd()
            $reader.Close(); $fs.Close()
            if ($content -match "TurtleTradeLogger v1\.01 ready") {
                $found = $true
                break
            }
        } catch { }
    }
}

if ($found) {
    Write-Host ""
    Write-Host "SUCCESS: TurtleTradeLogger is running and logging to Common\Files\turtle_fills.csv"
    Write-Host "After the next trade closes, run:"
    Write-Host "  powershell -ExecutionPolicy Bypass -File monitor\read_fills.ps1"
    exit 0
} else {
    Write-Host ""
    Write-Host "WARNING: Did not see 'TurtleTradeLogger v1.01 ready' within 20s."
    Write-Host "Possible causes:"
    Write-Host "  1. MT5 is still loading (check Experts tab manually)"
    Write-Host "  2. The chart02.chr period encoding is wrong for your MT5 build"
    Write-Host "     (try period_type=1 period_size=5 if M5 doesn't appear)"
    Write-Host "  3. The active profile changed from 'Default'"
    Write-Host "     (verify in MT5: File > Open Profile > Default)"
    Write-Host ""
    Write-Host "To manually attach: drag TurtleTradeLogger from Navigator onto any chart"
    Write-Host "that does NOT already have PineConnector running."
    exit 2
}
