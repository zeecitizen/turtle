@echo off
REM Double-click this to install Turtle Desktop as a Windows application.
REM (Start-menu entry, desktop shortcut, auto-start at logon, uninstaller.)
title Install Turtle Desktop
echo.
echo   Installing Turtle Desktop ...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
echo   Press any key to close.
pause >nul
