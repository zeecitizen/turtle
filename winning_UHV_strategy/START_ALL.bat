@echo off
rem =====================================================================================================
rem  UHV winning game - one-click start: Turtle TV UHV (8774) + debug Chrome with PrimeXBT (9222) + game LIVE (8790)
rem  Practice without money instead: games\gold_runner\start_game_sim.bat
rem =====================================================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "HERE=%~dp0"
set "PY=py"
where py >nul 2>nul || set "PY=python"
set "NUMBA_CPU_NAME=generic"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
set "PXURL=https://primexbt.com/my/trade/futures/l1869984/market/EUR%%2FUSD"

echo [1/3] Turtle TV UHV on http://127.0.0.1:8774/
start "Turtle TV UHV (8774)" /D "%HERE%monitor\TurtleTVUHV" %PY% server.py

"%PY%" -c "import socket,sys; s=socket.socket(); s.settimeout(1.5); sys.exit(0 if s.connect_ex(('127.0.0.1',9222))==0 else 1)"
if errorlevel 1 (
    echo [2/3] Starting the debug Chrome with PrimeXBT EUR/USD - log in once, keep the tab VISIBLE in its own window
    start "" "!CHROME!" --remote-debugging-port=9222 --user-data-dir="!HERE!games\gold_runner\chrome_profile" --no-first-run --no-default-browser-check "!PXURL!"
    ping -n 9 127.0.0.1 >nul
) else (
    echo [2/3] A debug Chrome already answers on 9222 - leaving it alone
)

echo [3/3] Golden Gravity game server LIVE on http://127.0.0.1:8790/  (real money - kill switch K)
start "Golden Gravity LIVE (8790)" /D "%HERE%games\gold_runner" %PY% server.py --mode live
ping -n 12 127.0.0.1 >nul
start "" "http://127.0.0.1:8774/"
start "" "http://127.0.0.1:8790/"
echo Done. Optional bot:  cd bot  ^&^&  py u97_bot.py
endlocal
