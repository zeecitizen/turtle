@echo off
REM ================================================================
REM  TurtleTradeLogger — Headless installer
REM  Compiles EA, attaches to XAUUSD M5 chart, restarts MT5.
REM  Zero manual steps required.
REM ================================================================
echo Running headless TurtleTradeLogger install...
powershell -ExecutionPolicy Bypass -File "%~dp0install_logger.ps1"
