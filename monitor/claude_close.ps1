# claude_close.ps1
# Book profit / exit trade immediately via PineConnector closelong/closeshort
# Usage: powershell -ExecutionPolicy Bypass -File claude_close.ps1 [-Direction buy|sell] [-Reason "text"]
# If -Direction omitted, reads live_trade_open.json to determine direction automatically.

param(
    [ValidateSet("buy","sell","")]
    [string]$Direction = "",
    [string]$Symbol    = "XAUUSD",
    [string]$Reason    = "manual_close"
)

$SCRIPT_DIR   = $PSScriptRoot
$CONFIG_PATH  = "$SCRIPT_DIR\.alert_config.json"
$LIVE_TRADE   = "$SCRIPT_DIR\live_trade_open.json"

# Auto-detect direction from live trade if not specified
if ($Direction -eq "") {
    if (Test-Path $LIVE_TRADE) {
        $lt = Get-Content $LIVE_TRADE -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($lt.open -eq $true) {
            $Direction = $lt.direction
            Write-Host "AUTO: detected open $Direction trade from live_trade_open.json"
        }
    }
    if ($Direction -eq "") {
        Write-Host "CLOSE_ERROR: no open trade detected and no -Direction given"
        exit 1
    }
}

# Read webhook URL
if (-not (Test-Path $CONFIG_PATH)) {
    Write-Host "CONFIG_MISSING: .alert_config.json not found"
    exit 1
}
$config      = Get-Content $CONFIG_PATH -Raw -Encoding UTF8 | ConvertFrom-Json
$WEBHOOK_URL = $config.pineconnector_webhook_url

if ([string]::IsNullOrEmpty($WEBHOOK_URL) -or $WEBHOOK_URL -like "REPLACE*") {
    Write-Host "CONFIG_MISSING: pineconnector_webhook_url not set"
    exit 1
}

$PC_ID = "8778286989525"

# PineConnector: closelong closes buy positions, closeshort closes sell positions
$closeCmd = if ($Direction -eq "buy") { "closelong" } else { "closeshort" }
$body     = "$PC_ID,$closeCmd,$Symbol"

Write-Host "CLOSING: $closeCmd $Symbol | Reason: $Reason"
Write-Host "Body: $body"

try {
    $response   = Invoke-WebRequest -Uri $WEBHOOK_URL -Method POST -Body $body `
                  -ContentType "text/plain" -TimeoutSec 8 -UseBasicParsing
    $statusCode = $response.StatusCode
} catch {
    Write-Host "WEBHOOK_ERROR: $_"
    exit 1
}

if ($statusCode -eq 200) {
    # Mark trade closed in live_trade_open.json
    $closedAt = (Get-Date).ToUniversalTime().ToString("o")
    [System.IO.File]::WriteAllText(
        $LIVE_TRADE,
        "{`"open`":false,`"closedAt`":`"$closedAt`",`"direction`":`"$Direction`",`"reason`":`"$Reason`"}",
        [System.Text.Encoding]::UTF8
    )
    Write-Host "CLOSE_SENT: $closeCmd $Symbol HTTP=$statusCode"
    Write-Host "CLOSE_SENT"
} else {
    Write-Host "CLOSE_FAILED: HTTP=$statusCode"
    exit 1
}
