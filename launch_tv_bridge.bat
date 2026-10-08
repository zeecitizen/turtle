@echo off
REM One click: TradingView Desktop with the Claude bridge (CDP :9222).
REM Double-click it, or run it from any terminal. Logic lives in bootstrap\launch_tv_bridge.ps1.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap\launch_tv_bridge.ps1"
set "RC=%errorlevel%"
echo.
timeout /t 6 >nul
exit /b %RC%
