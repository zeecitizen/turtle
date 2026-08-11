@echo off
setlocal EnableDelayedExpansion
title Turtle Trader - Setup
color 0B
echo.
echo   ===========================================================
echo      TURTLE TRADER  -  setup
echo   ===========================================================
echo.
echo   This installs everything into ONE folder.
echo   Nothing is written to the registry and nothing is added to PATH.
echo   To uninstall later, delete that folder. That is all.
echo.

set "TARGET=C:\TurtleTrader"
set /p TARGET=  Install to [%TARGET%]:
if "%TARGET%"=="" set "TARGET=C:\TurtleTrader"

echo.
echo   Installing to %TARGET% ...
if not exist "%TARGET%" mkdir "%TARGET%"
xcopy /E /I /Q /Y "%~dp0payload\python"  "%TARGET%\python"  >nul
echo     [1/5] python runtime
xcopy /E /I /Q /Y "%~dp0payload\node"    "%TARGET%\node"    >nul
echo     [2/5] node runtime
xcopy /E /I /Q /Y "%~dp0payload\turtle"  "%TARGET%\turtle"  >nul
echo     [3/5] trading code

set "PY=%TARGET%\python\python.exe"
"%PY%" -m pip install --no-index --find-links "%~dp0payload\wheels" ^
    requests websockets psutil numpy pandas pillow >nul 2>&1
echo     [4/5] python packages (offline)

REM ---- MetaTrader 5 has to come from the broker; we can only check and tell the truth
set "MT5=%ProgramFiles%\Blueberry Markets MetaTrader 5\terminal64.exe"
if exist "%MT5%" (
  echo     [5/5] MetaTrader 5 found
) else (
  echo     [5/5] MetaTrader 5 NOT found
  echo           Download it from Blueberry Markets and log in BEFORE first run.
  echo           The EAs are in %TARGET%\turtle\mt5 - compile them in MetaEditor.
)

REM ---- Credentials are NOT asked for during setup, deliberately.
REM      Install time is the wrong moment to decide about keys, and 'set /p' echoes
REM      what is typed straight onto the screen where a screenshot or anyone behind
REM      you catches it. A separate script does it properly, when the person is
REM      ready, with the typing hidden by PowerShell's SecureString.
set "AK=%TARGET%\ADD_KEYS.bat"
> "%AK%" echo @echo off
>> "%AK%" echo title Turtle Trader - keys
>> "%AK%" echo echo.
>> "%AK%" echo echo   Keys are OPTIONAL. Trading works without them.
>> "%AK%" echo echo   Stored on this machine only, never on the USB stick.
>> "%AK%" echo echo.
>> "%AK%" echo powershell -NoProfile -Command "$k=Read-Host 'Anthropic API key (hidden, Enter to skip)' -AsSecureString; $p=[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k)); if($p){Set-Content -NoNewline -Path '%TARGET%\turtle\monitor\.claude_api_key' -Value $p; Write-Host '   saved'}else{Write-Host '   skipped'}"
>> "%AK%" echo powershell -NoProfile -Command "$k=Read-Host 'Dashboard password (hidden, Enter to skip)' -AsSecureString; $p=[Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($k)); if($p){Set-Content -NoNewline -Path '%TARGET%\turtle\monitor\.dashboard_password' -Value $p; Write-Host '   saved'}else{Write-Host '   skipped'}"
>> "%AK%" echo pause
REM ---- one launcher, absolute paths only
> "%TARGET%\START.bat" echo @echo off
>> "%TARGET%\START.bat" echo title Turtle Trader
>> "%TARGET%\START.bat" echo set "PY=%TARGET%\python\python.exe"
>> "%TARGET%\START.bat" echo set "NODE=%TARGET%\node\node.exe"
>> "%TARGET%\START.bat" echo cd /d "%TARGET%\turtle"
>> "%TARGET%\START.bat" echo start "dashboard" /min "%%NODE%%" "%TARGET%\turtle\dashboard\claude_trader\server.js"
>> "%TARGET%\START.bat" echo start "supervisor" /min "%%PY%%" -u "%TARGET%\turtle\monitor\feed_supervisor.py" --loop 120
>> "%TARGET%\START.bat" echo start "archive"    /min "%%PY%%" -u "%TARGET%\turtle\monitor\tape_archive.py" --loop 60
>> "%TARGET%\START.bat" echo start "cockpit"    "%TARGET%\python\pythonw.exe" "%TARGET%\turtle\gui\camel_gui.py"
>> "%TARGET%\START.bat" echo echo   Started. Dashboard: http://localhost:3457
>> "%TARGET%\START.bat" echo timeout /t 5 ^>nul

powershell -NoProfile -Command ^
  "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Turtle Trader.lnk'); $s.TargetPath='%TARGET%\START.bat'; $s.WorkingDirectory='%TARGET%'; $s.Save()" >nul 2>&1

echo.
echo   ===========================================================
echo      DONE
echo   ===========================================================
echo.
echo   Installed at : %TARGET%
echo   Optional keys: run ADD_KEYS.bat (typing is hidden)
echo   Start it     : desktop shortcut "Turtle Trader", or START.bat
echo   Dashboard    : http://localhost:3457
echo.
echo   BEFORE TRADING: open MetaTrader 5, log in, and drag the
echo   ZeeUHV expert onto an XAUUSD M1 chart.
echo   Read %TARGET%\turtle\THINGS_TO_REMEMBER.md first.
echo.
pause
