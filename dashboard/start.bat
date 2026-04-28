@echo off
title Turtle Dashboard
cd /d "%~dp0"

:: Check if server already running on port 3456
netstat -an 2>nul | find "3456" | find "LISTENING" >nul
if %errorlevel%==0 (
    echo Dashboard already running. Opening browser...
    start "" "http://localhost:3456"
    exit /b 0
)

echo Starting Turtle Dashboard server...
start /min "" node "%~dp0server.js"

:: Wait for server to start
timeout /t 2 /nobreak >nul

:: Open Chrome
echo Opening dashboard in Chrome...
start "" "http://localhost:3456"

exit /b 0
