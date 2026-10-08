# bootstrap/launch_tv_bridge.ps1 - one click: TradingView Desktop up with the Claude bridge (CDP :9222)
#
#   1. Already bridged?            -> say so, check the bridge, done.
#   2. Running WITHOUT the bridge?  -> close it (it cannot gain a debug port while running).
#   3. Launch the Store app INSIDE its package with ELECTRON_EXTRA_LAUNCH_ARGS set, then clear it.
#   4. Ask the bridge (tradingview-mcp) whether it can see the chart.
#
# Why this route, measured 2026-10-08 on TradingView 3.4.1.8194 (MSIX):
#   * running a COPY of the exe outside the package crashes ("setErrorHandler" of undefined)
#   * the in-package shell:AppsFolder launch with ELECTRON_EXTRA_LAUNCH_ARGS set AND the flag
#     passed works: CDP up within 5s. (Which of the two carries it was not isolated - both stay.)
# The variable is read by EVERY Electron app (VS Code, Teams, Discord would grab 9222 too),
# so it lives only for the few seconds of the launch.

$ErrorActionPreference = "Continue"
$Port      = 9222
$AppId     = "TradingView.Desktop_n534cwy3pjxzj!TradingView.Desktop"
$BridgeCli = "C:\Users\zeesh\Documents\GitHub\tradingview-mcp\src\cli\index.js"
$Node      = "C:\Program Files\nodejs\node.exe"

function Test-Cdp {
    try { Invoke-RestMethod "http://127.0.0.1:$Port/json/version" -TimeoutSec 2 -ErrorAction Stop | Out-Null; $true }
    catch { $false }
}

function Show-BridgeStatus {
    if (-not (Test-Path $Node) -or -not (Test-Path $BridgeCli)) {
        Write-Host "  [WARN] bridge not found ($BridgeCli) - CDP is up, but the MCP tools cannot use it" -ForegroundColor Yellow
        return
    }
    $env:ELECTRON_RUN_AS_NODE = $null   # VS Code sets this; harmless for node, but keep the shell clean
    Write-Host "  Asking the bridge what it sees..."
    $s = & $Node $BridgeCli status 2>&1 | Out-String
    try {
        $j = $s | ConvertFrom-Json
        if ($j.success) {
            Write-Host "  [OK] bridge connected - chart $($j.chart_symbol) $($j.chart_resolution)m" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] bridge says: $($j.error)" -ForegroundColor Yellow
            Write-Host "         the chart may still be loading; re-run this launcher in a few seconds"
        }
    } catch { Write-Host $s }
}

Write-Host ""
Write-Host "  TradingView + Claude bridge launcher"
Write-Host "  ===================================="

# 1. already bridged
if (Test-Cdp) {
    Write-Host "  [OK] TradingView is already bridged on port $Port" -ForegroundColor Green
    Show-BridgeStatus
    exit 0
}

# 2. running without the bridge -> close it
$running = @(Get-Process TradingView -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    Write-Host "  TradingView is open WITHOUT the bridge - closing it so it can restart bridged..."
    $running | ForEach-Object { if ($_.MainWindowHandle -ne 0) { $_.CloseMainWindow() | Out-Null } }
    for ($i = 0; $i -lt 10 -and @(Get-Process TradingView -ErrorAction SilentlyContinue).Count -gt 0; $i++) { Start-Sleep 1 }
    Get-Process TradingView -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 2
}

# 3. launch inside the package with the flag in the environment, then clear it
if (-not (Get-AppxPackage -Name "TradingView.Desktop" -ErrorAction SilentlyContinue)) {
    Write-Host "  [FAIL] TradingView Desktop (Store version) is not installed" -ForegroundColor Red
    exit 1
}
Write-Host "  Launching TradingView with the debug port..."
$up = $false
try {
    [Environment]::SetEnvironmentVariable('ELECTRON_EXTRA_LAUNCH_ARGS', "--remote-debugging-port=$Port", 'User')
    Start-Process "shell:AppsFolder\$AppId" -ArgumentList "--remote-debugging-port=$Port"
    for ($i = 0; $i -lt 45; $i++) { Start-Sleep 1; if (Test-Cdp) { $up = $true; break } }
}
finally {
    [Environment]::SetEnvironmentVariable('ELECTRON_EXTRA_LAUNCH_ARGS', $null, 'User')
}

if (-not $up) {
    Write-Host "  [FAIL] TradingView started but port $Port never answered (45s)" -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] port $Port is up after ~$($i + 1)s" -ForegroundColor Green

# 4. give the chart a moment to load, then check the bridge
Start-Sleep 6
Show-BridgeStatus
exit 0
