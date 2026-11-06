@echo off
rem ==========================================================================================================
rem  Golden Gravity: The $1 Heist  -  SIM launcher (synthetic market + simulated broker; no money, no Chrome).
rem  Starts python server.py --mode sim in its own window and opens http://127.0.0.1:8790/ in the default browser.
rem  If a LIVE game server already runs on port 8790 nothing is opened (so the live street is never mistaken for sim).
rem  Optional: set the environment variables GG_SEED and GG_SPEED before running (defaults 7 and 1.0).
rem ==========================================================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "HERE=%~dp0"
set "PORT=8790"
set "PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\python.exe"
if not exist "%PY%" set "PY=python"
if "%GG_SEED%"=="" set "GG_SEED=7"
if "%GG_SPEED%"=="" set "GG_SPEED=1.0"

"%PY%" -c "exec('import socket,json,sys,urllib.request\ns=socket.socket(); s.settimeout(1.0)\nif s.connect_ex((\'127.0.0.1\',%PORT%)): sys.exit(0)\ntry:\n m=json.load(urllib.request.urlopen(\'http://127.0.0.1:%PORT%/api/health\',timeout=3)).get(\'mode\')\nexcept Exception:\n sys.exit(13)\nsys.exit({\'live\':10,\'sim\':11,\'replay\':12}.get(m,13))')"
set "GGMODE=!errorlevel!"
if "!GGMODE!"=="10" goto :live_running
if "!GGMODE!"=="13" goto :port_taken
if "!GGMODE!"=="0" (
    echo [Golden Gravity] Starting the game server in SIM mode on port %PORT% - seed !GG_SEED!, speed !GG_SPEED!.
    start "Golden Gravity server (SIM)" "!PY!" server.py --mode sim --seed !GG_SEED! --speed !GG_SPEED!
) else (
    echo [Golden Gravity] A SIM/REPLAY game server already runs on port %PORT% - using it.
)

"%PY%" -c "exec('import socket,time,sys\nfor i in range(80):\n s=socket.socket(); s.settimeout(0.5)\n if s.connect_ex((\'127.0.0.1\',%PORT%))==0: sys.exit(0)\n s.close(); time.sleep(0.25)\nsys.exit(1)')"
if errorlevel 1 (
    echo [Golden Gravity] The server did not answer on port %PORT%. Look at the server window for the reason.
    pause
    exit /b 1
)
if not "%GG_NO_BROWSER%"=="1" start "" "http://127.0.0.1:%PORT%/"
echo [Golden Gravity] The game is at http://127.0.0.1:%PORT%/  (SIM - pretend money)
endlocal
exit /b 0

:live_running
echo [Golden Gravity] The LIVE game server (real money) is running on port %PORT%. Close its window first for practice.
echo [Golden Gravity] Nothing was opened.
pause
exit /b 2

:port_taken
echo [Golden Gravity] Port %PORT% is taken by another program. Nothing was started.
pause
exit /b 3
