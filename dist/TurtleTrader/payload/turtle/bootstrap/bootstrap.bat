@echo off
REM Turtle Trader bootstrap — one command brings the full stack up.
REM Safe to re-run. Running after a crash restores steady state.
REM Usage: double-click, or run from cmd: bootstrap.bat
REM        With args: bootstrap.bat --skip-tv  (skip TV launch if already up)

cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" %*
if %errorlevel% neq 0 (
    echo.
    echo ============================================================
    echo  BOOTSTRAP FAILED. See output above for the phase that failed.
    echo  Re-running is safe after addressing the error.
    echo ============================================================
    pause
    exit /b %errorlevel%
)
exit /b 0
