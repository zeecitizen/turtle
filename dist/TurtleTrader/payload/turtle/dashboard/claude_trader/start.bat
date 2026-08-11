@echo off
title Claude Trader Dashboard
cd /d "%~dp0"

:: Check if server already running on port 3457
netstat -an 2>nul | find "3457" | find "LISTENING" >nul
if %errorlevel%==0 (
    echo Claude Trader dashboard already running. Opening browser...
    start "" "http://localhost:3457"
    exit /b 0
)

echo Starting Claude Trader Dashboard server...
start /min "" node "%~dp0server.js"

:: Wait for server to start
timeout /t 2 /nobreak >nul

:: Open Chrome
echo Opening Claude Trader dashboard in Chrome...
start "" "http://localhost:3457"

exit /b 0
