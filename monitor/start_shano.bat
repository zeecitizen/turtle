@echo off
title Shano Hawk - Autonomous Trader
echo ============================================================
echo   SHANO HAWK STARTUP
echo ============================================================
echo.

set PYTHON=C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe
set SCRIPT_DIR=%~dp0

:: Check Python
%PYTHON% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found at %PYTHON%
    pause
    exit /b 1
)

:: Check requests module
%PYTHON% -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo Installing requests module...
    %PYTHON% -m pip install requests
)

:: Run the hawk
echo Starting Shano Hawk...
echo Press Ctrl+C to stop gracefully.
echo.
%PYTHON% "%SCRIPT_DIR%shano_hawk.py" %*
