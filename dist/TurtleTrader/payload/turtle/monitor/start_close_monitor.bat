@echo off
REM start_close_monitor.bat
REM Usage: start_close_monitor.bat [settle_ms]
REM   settle_ms = 10 | 50 | 100 | 1000 | 2000   (default 1500)
REM Reads direction + entry from watch_state.json automatically.
REM
REM Examples:
REM   start_close_monitor.bat 10
REM   start_close_monitor.bat 100
REM   start_close_monitor.bat 1000

set SETTLE=%1
if "%SETTLE%"=="" set SETTLE=1500

echo.
echo  [Close Monitor] settle=%SETTLE%ms
echo.

node "C:\Users\zeesh\Documents\GitHub\tradingview-mcp\scripts\close_on_profit.js" "" "" %SETTLE%
