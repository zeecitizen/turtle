# claude_uhv_exec.ps1
# Claude's independent UHV signal executor
# Sends trade to MT5 via PineConnector webhook, logs to claude_signals.csv, handles dedup
# Usage: powershell -ExecutionPolicy Bypass -File claude_uhv_exec.ps1 -Direction buy -UhvBarTime "16:05:00" -Reason "BRK above 4805.5"

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("buy","sell")]
    [string]$Direction,

    [string]$UhvBarTime = "",
    [string]$Symbol     = "XAUUSD",
    [string]$Reason     = "",
    [string]$Lots       = "0.40",           # live default — 0.40 lots same as indicator
    [string]$Comment    = "Claude_Trader_v1", # tag used by Claude Trader dashboard filter
    [double]$CandleHigh = 0,                 # UHV candle high — passed to WhatsApp alert
    [double]$CandleLow  = 0                  # UHV candle low  — passed to WhatsApp alert
)

$SCRIPT_DIR  = $PSScriptRoot
$CONFIG_PATH = "$SCRIPT_DIR\.alert_config.json"
$LOG_PATH    = "$SCRIPT_DIR\claude_signals.csv"
$DEDUP_PATH  = "$SCRIPT_DIR\.claude_last_uhv"

$PC_ID      = "87782869895251"
$SL_PIPS    = "15"   # increased from 10 — gives room past spread noise on XAUUSD
$TP_PIPS    = "52"   # Session 49 optimised value: 52 pips = ~$208 target at 0.40 lots
$SPREAD     = "30"
$BETRIGGER  = "8"    # raised from 2 — gives close monitor time to act before BE triggers
$COMMENT    = $Comment   # passed via -Comment param; default = Claude_Trader_v1

# Dedup check
if ($UhvBarTime -ne "" -and (Test-Path $DEDUP_PATH)) {
    $lastUhv = (Get-Content $DEDUP_PATH -Encoding UTF8).Trim()
    if ($lastUhv -eq $UhvBarTime) {
        Write-Host "DEDUP: already traded UHV bar @ $UhvBarTime -- skipping"
        exit 0
    }
}

# Read webhook URL from config
if (-not (Test-Path $CONFIG_PATH)) {
    Write-Host "CONFIG_MISSING: .alert_config.json not found"
    exit 1
}
$config = Get-Content $CONFIG_PATH -Raw -Encoding UTF8 | ConvertFrom-Json
$WEBHOOK_URL = $config.pineconnector_webhook_url

if ([string]::IsNullOrEmpty($WEBHOOK_URL) -or $WEBHOOK_URL -like "REPLACE*") {
    Write-Host "CONFIG_MISSING: pineconnector_webhook_url not set in .alert_config.json"
    exit 1
}

# Build and send signal
$body = "$PC_ID,$Direction,$Symbol,vol_lots=$Lots,sl_pips=$SL_PIPS,tp_pips=$TP_PIPS,spread=$SPREAD,betrigger=$BETRIGGER,comment=$COMMENT"

try {
    $response = Invoke-WebRequest -Uri $WEBHOOK_URL -Method POST -Body $body `
                -ContentType "text/plain" -TimeoutSec 8 -UseBasicParsing
    $statusCode = $response.StatusCode
} catch {
    Write-Host "WEBHOOK_ERROR: $_"
    exit 1
}

# Log signal
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
if (-not (Test-Path $LOG_PATH)) {
    "timestamp,direction,symbol,uhv_bar_time,reason,http_status,lots,comment" | Out-File $LOG_PATH -Encoding UTF8
}
"$timestamp,$Direction,$Symbol,$UhvBarTime,`"$Reason`",$statusCode,$Lots,$COMMENT" | Out-File $LOG_PATH -Encoding UTF8 -Append

# Write live trade state (read by Claude Trader dashboard per-trade analyzer)
if ($statusCode -eq 200) {
    $liveState = [ordered]@{
        open          = $true
        direction     = $Direction
        symbol        = $Symbol
        lots          = $Lots
        entryTime     = (Get-Date).ToUniversalTime().ToString("o")
        uhvBarTime    = $UhvBarTime
        reason        = $Reason
        slPips        = [int]$SL_PIPS
        tpPips        = [int]$TP_PIPS
        beTriggerPips = [int]$BETRIGGER
        comment       = $COMMENT
    }
    $liveState | ConvertTo-Json | Out-File "$SCRIPT_DIR\live_trade_open.json" -Encoding UTF8 -Force
}

# Mark dedup
if ($UhvBarTime -ne "") {
    $UhvBarTime | Out-File $DEDUP_PATH -Encoding UTF8 -NoNewline
}

Write-Host "SIGNAL_SENT: $Direction $Symbol (UHV@$UhvBarTime) HTTP=$statusCode lots=$Lots comment=$COMMENT"
Write-Host "Body: $body"

# Send WhatsApp breakout alert (non-blocking)
if ($statusCode -eq 200) {
    $PYTHON_WA  = "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
    $WA_SCRIPT  = "$SCRIPT_DIR\whatsapp_alert.py"
    if ((Test-Path $PYTHON_WA) -and (Test-Path $WA_SCRIPT)) {
        $uhvLevel = if ($UhvBarTime -match '_(.+)$') { $Matches[1] } else { "0" }
        $waArgs = "$WA_SCRIPT --direction $Direction --price $uhvLevel --uhv-key `"$UhvBarTime`" --candle-high $CandleHigh --candle-low $CandleLow"
        Start-Process -FilePath $PYTHON_WA -ArgumentList $waArgs `
                      -WindowStyle Hidden -RedirectStandardOutput "$SCRIPT_DIR\whatsapp.log"
        Write-Host "WHATSAPP_ALERT_SENT"
    }
}

# Launch Claude Hawk — monitors P&L every 200ms, closes on profit/trail/loss-cut
if ($statusCode -eq 200) {
    $PYTHON  = "C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
    $HAWK    = "$SCRIPT_DIR\claude_hawk.py"
    if ((Test-Path $PYTHON) -and (Test-Path $HAWK)) {
        $hawkArgs = "$HAWK --min-profit 15 --trail-drop 12 --max-loss 30 --timeout 25"
        Start-Process -FilePath $PYTHON -ArgumentList $hawkArgs `
                      -WindowStyle Hidden -RedirectStandardOutput "$SCRIPT_DIR\hawk.log" `
                      -RedirectStandardError "$SCRIPT_DIR\hawk_err.log"
        Write-Host "HAWK_LAUNCHED"
    }
}
