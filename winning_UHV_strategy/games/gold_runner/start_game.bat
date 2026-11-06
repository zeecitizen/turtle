@echo off
rem ==========================================================================================================
rem  Golden Gravity: The $1 Heist  -  LIVE launcher (REAL MONEY: PrimeXBT account L1869984). Double-click to play.
rem  1. If NOTHING answers on 127.0.0.1:9222, start the debug Chrome on its own profile (chrome_profile) with the
rem     PrimeXBT XAU/USD page. Log in there once and keep that window open: it holds the session.
rem     If something already answers on 9222 it is left completely alone - this script never kills, restarts,
rem     reloads or closes an existing Chrome.
rem  2. Start the game server in live mode (python server.py --mode live) in its own window - unless a game server
rem     already runs on port 8790: a LIVE one is reused, a SIM/REPLAY one is reported and nothing is opened.
rem  3. Open http://127.0.0.1:8790/ in the default browser.
rem  Practice without money: start_game_sim.bat
rem ==========================================================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "HERE=%~dp0"
set "PORT=8790"
set "PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe"
if not exist "%PY%" set "PY=python"
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
set "PXURL=https://primexbt.com/my/trade/futures/l1869984/market/XAU%%2FUSD"

rem ---- 0. is a game server already running on the game port, and in which mode?
"%PY%" -c "exec('import socket,json,sys,urllib.request\ns=socket.socket(); s.settimeout(1.0)\nif s.connect_ex((\'127.0.0.1\',%PORT%)): sys.exit(0)\ntry:\n m=json.load(urllib.request.urlopen(\'http://127.0.0.1:%PORT%/api/health\',timeout=3)).get(\'mode\')\nexcept Exception:\n sys.exit(13)\nsys.exit({\'live\':10,\'sim\':11,\'replay\':12}.get(m,13))')"
set "GGMODE=!errorlevel!"
if "!GGMODE!"=="11" goto :wrong_mode
if "!GGMODE!"=="12" goto :wrong_mode
if "!GGMODE!"=="13" goto :port_taken

rem ---- 1. the debug Chrome: probe 9222 with a plain TCP connect (no HTTP, no CDP); start Chrome only if nothing answers
"%PY%" -c "import socket,sys; s=socket.socket(); s.settimeout(1.5); sys.exit(0 if s.connect_ex(('127.0.0.1',9222))==0 else 1)"
if errorlevel 1 (
    echo [Golden Gravity] Nothing on port 9222 - starting the debug Chrome with the PrimeXBT page.
    echo [Golden Gravity] Log in there if asked, then leave that window open.
    start "" "!CHROME!" --remote-debugging-port=9222 --user-data-dir="!HERE!chrome_profile" --no-first-run --no-default-browser-check "!PXURL!"
    ping -n 9 127.0.0.1 >nul
) else (
    echo [Golden Gravity] The debug Chrome is already running on 9222 - leaving it alone.
)

rem ---- 2. the game server in live mode (or reuse the live one that already runs)
if "!GGMODE!"=="10" (
    echo [Golden Gravity] A LIVE game server already runs on port %PORT% - using it.
) else (
    echo [Golden Gravity] Starting the game server in LIVE mode on port %PORT%.
    start "Golden Gravity server (LIVE)" "!PY!" server.py --mode live
)

rem ---- 3. wait for the server (up to 20 s), then open the game
"%PY%" -c "exec('import socket,time,sys\nfor i in range(80):\n s=socket.socket(); s.settimeout(0.5)\n if s.connect_ex((\'127.0.0.1\',%PORT%))==0: sys.exit(0)\n s.close(); time.sleep(0.25)\nsys.exit(1)')"
if errorlevel 1 (
    echo [Golden Gravity] The server did not answer on port %PORT%. Look at the server window for the reason.
    pause
    exit /b 1
)
if not "%GG_NO_BROWSER%"=="1" start "" "http://127.0.0.1:%PORT%/"
echo [Golden Gravity] The game is at http://127.0.0.1:%PORT%/  (LIVE - real money; the kill switch is K)
endlocal
exit /b 0

:wrong_mode
echo [Golden Gravity] A game server in SIM/REPLAY mode is running on port %PORT%. Close its window first, then run this again.
echo [Golden Gravity] Nothing was started and no browser was opened, so you cannot mistake the practice street for the live one.
pause
exit /b 2

:port_taken
echo [Golden Gravity] Port %PORT% is taken by another program. Nothing was started.
pause
exit /b 3
