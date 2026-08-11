# claude_s3_exec.ps1 — S3 ("Effort vs Result") signal executor
#
# Fires a market order via PineConnector with DYNAMIC SL/TP computed
# per-signal by the auto_s3_trader daemon (not fixed pips like UHV exec).
#
# SL and TP are passed as PRICE LEVELS; this script converts them to pips
# for PineConnector. Assumes XAUUSD where 1 pip = 0.10 price units.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File claude_s3_exec.ps1 `
#     -Direction buy -EntryPrice 5070.30 -SLPrice 5068.10 -TPPrice 5075.50 `
#     -Lots 0.40 -SignalKey "S3_buy_20260515_1430"

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("buy","sell")]
    [string]$Direction,

    [Parameter(Mandatory=$true)]
    [double]$EntryPrice,

    [Parameter(Mandatory=$true)]
    [double]$SLPrice,

    [Parameter(Mandatory=$true)]
    [double]$TPPrice,

    [string]$Lots       = "0.40",
    [string]$Symbol     = "XAUUSD",
    [string]$SignalKey  = "",
    [string]$Reason     = "S3_effort_vs_result",
    [string]$Comment    = "S3_Trader_v1"
)

$SCRIPT_DIR  = $PSScriptRoot
$CONFIG_PATH = "$SCRIPT_DIR\.alert_config.json"
$LOG_PATH    = "$SCRIPT_DIR\s3_signals.csv"
$DEDUP_PATH  = "$SCRIPT_DIR\.s3_last_signal"

$PC_ID  = "87782869895251"
$SPREAD = "30"

# Compute SL/TP pips from price levels (1 pip = 0.10 price on XAU)
if ($Direction -eq "buy") {
    $slPips = [Math]::Round(($EntryPrice - $SLPrice) * 10, 0)
    $tpPips = [Math]::Round(($TPPrice - $EntryPrice) * 10, 0)
} else {
    $slPips = [Math]::Round(($SLPrice - $EntryPrice) * 10, 0)
    $tpPips = [Math]::Round(($EntryPrice - $TPPrice) * 10, 0)
}
if ($slPips -le 0 -or $tpPips -le 0) {
    Write-Host "SL_TP_INVALID: slPips=$slPips tpPips=$tpPips (entry=$EntryPrice sl=$SLPrice tp=$TPPrice)"
    exit 1
}

# Dedup by signal key
if ($SignalKey -ne "" -and (Test-Path $DEDUP_PATH)) {
    $lastKey = (Get-Content $DEDUP_PATH -Encoding UTF8).Trim()
    if ($lastKey -eq $SignalKey) {
        Write-Host "DEDUP: already fired $SignalKey"
        exit 0
    }
}

if (-not (Test-Path $CONFIG_PATH)) {
    Write-Host "CONFIG_MISSING: .alert_config.json not found"
    exit 1
}
$config = Get-Content $CONFIG_PATH -Raw -Encoding UTF8 | ConvertFrom-Json
$WEBHOOK_URL = $config.pineconnector_webhook_url
if ([string]::IsNullOrEmpty($WEBHOOK_URL) -or $WEBHOOK_URL -like "REPLACE*") {
    Write-Host "CONFIG_MISSING: pineconnector_webhook_url not set"
    exit 1
}

$body = "$PC_ID,$Direction,$Symbol,vol_lots=$Lots,sl_pips=$slPips,tp_pips=$tpPips,spread=$SPREAD,comment=$Comment"

try {
    $response = Invoke-WebRequest -Uri $WEBHOOK_URL -Method POST -Body $body `
                -ContentType "text/plain" -TimeoutSec 8 -UseBasicParsing
    $statusCode = $response.StatusCode
} catch {
    Write-Host "WEBHOOK_ERROR: $_"
    exit 1
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
if (-not (Test-Path $LOG_PATH)) {
    "timestamp,direction,symbol,signal_key,entry,sl,tp,sl_pips,tp_pips,http,lots,comment" | Out-File $LOG_PATH -Encoding UTF8
}
"$timestamp,$Direction,$Symbol,$SignalKey,$EntryPrice,$SLPrice,$TPPrice,$slPips,$tpPips,$statusCode,$Lots,$Comment" | Out-File $LOG_PATH -Encoding UTF8 -Append

if ($statusCode -eq 200 -and $SignalKey -ne "") {
    $SignalKey | Out-File $DEDUP_PATH -Encoding UTF8 -NoNewline
}

Write-Host "S3_SIGNAL_SENT: $Direction lots=$Lots SL=$slPips TP=$tpPips HTTP=$statusCode key=$SignalKey"
