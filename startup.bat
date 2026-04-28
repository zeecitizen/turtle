@echo off
REM ─────────────────────────────────────────────────────────────────
REM  Claude Trader — Startup (idempotent, resilient)
REM
REM  Safe to re-run any time:
REM    - Already-running daemons are detected and left alone
REM    - Permission/missing-file errors log a [WARN] and the script continues
REM    - Caches are only cleared when their owner isn't running (fresh start)
REM  Each step is independent. Nothing aborts the script.
REM ─────────────────────────────────────────────────────────────────
setlocal
set "PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
set "ROOT=C:\Users\zeesh\Documents\GitHub\turtle"
set "MON=%ROOT%\monitor"
set "ENSURE=%PY% %MON%\ensure_daemon.py"

echo.
echo  ╔══════════════════════════════════╗
echo  ║     Claude Trader — Startup      ║
echo  ╚══════════════════════════════════╝
echo.

REM ── Sanity: python interpreter present? ─────────────────────────
if not exist "%PY%" (
    echo  [WARN] Python not at %PY% — daemon launches will be skipped
)

REM ── Dashboard server (port-based check) ─────────────────────────
netstat -ano 2>nul | findstr ":3457" >nul 2>&1
if errorlevel 1 (
    if exist "%ROOT%\dashboard\claude_trader\server.js" (
        start "Claude Trader Dashboard" /min node "%ROOT%\dashboard\claude_trader\server.js"
        echo  [OK] Dashboard started -^> http://localhost:3457
    ) else (
        echo  [WARN] Dashboard server.js missing - skipping
    )
) else (
    echo  [OK] Dashboard already running -^> http://localhost:3457
)

REM ── Open Shano dashboard in default browser ─────────────────────
timeout /t 2 /nobreak >nul 2>&1
start "" "http://localhost:3457/shano" 2>nul
echo  [OK] Shano dashboard opened in browser

REM ── Sniper caches: clear ONLY when the sniper isn't running ─────
"%ENSURE%" --check claude_sniper_daemon.py >nul 2>&1
if errorlevel 1 (
    if exist "%MON%\.last_uhv_id"     del /f /q "%MON%\.last_uhv_id"     >nul 2>&1
    if exist "%MON%\sniper_target.json" del /f /q "%MON%\sniper_target.json" >nul 2>&1
    echo  [OK] Sniper caches cleared - fresh start
) else (
    echo  [OK] Sniper caches preserved - daemon already running
)

REM ── Long-running Python daemons (idempotent: skip if running) ───
"%ENSURE%" claude_sniper_daemon.py
"%ENSURE%" intern_hawks.py
"%ENSURE%" silver_hawk_learner.py
"%ENSURE%" sexy_hawk.py --loop
"%ENSURE%" meeting_hawks.py --loop
"%ENSURE%" sheriff_hawk.py --loop
"%ENSURE%" shano_hawk.py

REM ── TradingView Desktop ─────────────────────────────────────────
echo.
echo  Launching TradingView Desktop...
if exist "%ROOT%\bootstrap\launch_tv.ps1" (
    powershell -ExecutionPolicy Bypass -File "%ROOT%\bootstrap\launch_tv.ps1"
    if errorlevel 1 (
        echo  [WARN] TV launch script returned an error - continuing
    ) else (
        echo  [OK] TV launch attempted
    )
) else (
    echo  [WARN] launch_tv.ps1 missing - skipping
)

REM ── EA install (script is itself idempotent) ────────────────────
echo.
echo  Installing Shano EAs into MT5...
if exist "%ROOT%\mt5\install_eas.ps1" (
    powershell -ExecutionPolicy Bypass -File "%ROOT%\mt5\install_eas.ps1"
    if errorlevel 1 (
        echo  [WARN] EA install returned an error - continuing
    ) else (
        echo  [OK] EA install finished - see mt5\install_eas.log
    )
) else (
    echo  [WARN] install_eas.ps1 missing - skipping
)

REM ── MT5 (skip if already running) ───────────────────────────────
tasklist /FI "IMAGENAME eq terminal64.exe" 2>nul | find /I "terminal64.exe" >nul
if errorlevel 1 (
    if exist "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe" (
        start "" "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
        echo  [OK] MT5 launched
    ) else (
        echo  [SKIP] MT5 not at default path - launch manually
    )
) else (
    echo  [OK] MT5 already running
)

echo.
echo  Next: Claude will register the every-minute cron automatically.
echo.
endlocal
