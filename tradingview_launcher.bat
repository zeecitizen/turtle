@echo off
REM ─────────────────────────────────────────────────────────────────────
REM  tradingview_launcher.bat — standalone TV launcher with CDP bridge
REM  Use this when you need to bring TradingView up bridged to Claude
REM  WITHOUT running the full startup.bat (which spawns 10+ hawks).
REM
REM  What it does:
REM    1. Checks if CDP is already alive on port 9222 → exits success if so
REM    2. Launches TV Desktop (UWP or installer fallback) with CDP enabled
REM    3. Waits up to 30s for CDP handshake
REM    4. Reports status
REM
REM  Run: just double-click, OR from any cmd/PowerShell terminal
REM       (admin not required — UWP activation works as user)
REM ─────────────────────────────────────────────────────────────────────

setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo.
echo  TradingView Launcher (CDP bridge for Claude MCP)
echo  ================================================
echo.

REM Sanity: does the launch script exist?
if not exist "%ROOT%\bootstrap\launch_tv.ps1" (
    echo  [ERROR] %ROOT%\bootstrap\launch_tv.ps1 not found.
    echo  Cannot launch TV without it. Repo is corrupt or moved.
    pause
    exit /b 1
)

REM Pre-flight: is CDP already up?
powershell -NoProfile -ExecutionPolicy Bypass -Command "$r = try { Invoke-WebRequest 'http://localhost:9222/json/version' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop } catch { $null }; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 }"
if %errorlevel% equ 0 (
    echo  [OK] CDP already alive on localhost:9222 — TV is already bridged
    echo  Run Claude's pine_smart_compile and you're good
    echo.
    timeout /t 4 /nobreak >nul
    exit /b 0
)

echo  CDP not yet up — launching TV Desktop...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\bootstrap\launch_tv.ps1"
set "LAUNCH_RC=%errorlevel%"

echo.
if %LAUNCH_RC% equ 0 (
    echo  [SUCCESS] TradingView is now bridged to Claude on port 9222
    echo.
    echo  Next steps:
    echo    1. Wait for TV to finish loading the chart
    echo    2. Tell Claude: "compile turtle.pine" — Claude can now drive TV via MCP
) else (
    echo  [FAILED] TV launch returned error code %LAUNCH_RC%
    echo.
    echo  Common fixes:
    echo    - If you have TV already open: close it fully then re-run this script
    echo    - If "appears running but CDP not reachable": kill all chrome.exe + TradingView.exe
    echo      processes via Task Manager, then retry
    echo    - As last resort: open TV manually, then run this script again — it will detect CDP
)

echo.
pause
endlocal
exit /b %LAUNCH_RC%
