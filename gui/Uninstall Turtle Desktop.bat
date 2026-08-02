@echo off
title Uninstall Turtle Desktop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Uninstall
pause >nul
