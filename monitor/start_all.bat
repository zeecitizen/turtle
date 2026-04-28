@echo off
REM ================================================================
REM  Turtle Trader — Master Startup Script
REM  Run this on computer start / VPS login
REM  Then open Claude Code and say: "initialize monitoring"
REM ================================================================

echo.
echo  ████████╗██╗   ██╗██████╗ ████████╗██╗     ███████╗
echo  ╚══██╔══╝██║   ██║██╔══██╗╚══██╔══╝██║     ██╔════╝
echo     ██║   ██║   ██║██████╔╝   ██║   ██║     █████╗
echo     ██║   ██║   ██║██╔══██╗   ██║   ██║     ██╔══╝
echo     ██║   ╚██████╔╝██║  ██║   ██║   ███████╗███████╗
echo     ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝
echo.
echo  Turtle Trader Auto-Monitor — Starting All Services
echo  ================================================================

REM Create temp folder for screenshots
if not exist "C:\tmp" mkdir "C:\tmp"

REM Allow PowerShell scripts to run (needed for read_mt5_log.ps1 and screenshot.ps1)
powershell -Command "Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force" >nul 2>&1

REM ---- 1. Start MT5 ----
echo [1/2] Starting Blueberry MetaTrader 5...
start "" "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
timeout /t 6 /nobreak >nul
echo       MT5 launched.

REM ---- 2. Start TradingView with CDP debug port ----
echo [2/2] Starting TradingView with CDP port 9222...
powershell -ExecutionPolicy Bypass -File "C:\Users\zeesh\Documents\GitHub\tradingview-mcp\scripts\launch_tv_debug.ps1"
if %errorlevel% neq 0 (
    echo ERROR: TradingView CDP launch failed. Check launch_tv_debug.ps1 output above.
    exit /b 1
)

echo.
echo  ================================================================
echo   All services started!
echo.
echo   NEXT STEP: Open Claude Code terminal and type:
echo     initialize monitoring
echo  ================================================================
