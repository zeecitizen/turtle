@echo off
rem Launch Turtle TV without Claude: http://127.0.0.1:8773
setlocal
set "ROOT=C:\Users\zeesh\turtle"
set "PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python312-arm64\pythonw.exe"
if not exist "%PY%" set "PY=C:\Program Files\Python312\pythonw.exe"
rem (the AWS VM has the x64 Python in Program Files)
set "URL=http://127.0.0.1:8773"

cd /d "%ROOT%" || (echo [FAIL] Cannot open %ROOT% & pause & exit /b 1)

if not exist "%PY%" (
  echo [FAIL] Python not found at %PY%
  echo        Check the Python install path in this file.
  pause & exit /b 1
)
if not exist "monitor\saad_view\server.py" (
  echo [FAIL] monitor\saad_view\server.py is missing. Is the repo complete?
  pause & exit /b 1
)

rem Already running? Just open the page.
curl -s -o nul -w "%%{http_code}" %URL%/ 2>nul | findstr "200" >nul
if not errorlevel 1 (
  echo [OK] Turtle TV is already running at %URL%
  start "" %URL%
  exit /b 0
)

echo Starting Turtle TV server...
start "" "%PY%" monitor\saad_view\server.py

rem Wait up to 60 seconds for the server to answer.
set /a TRIES=0
:wait
timeout /t 2 >nul
set /a TRIES+=1
curl -s -o nul -w "%%{http_code}" %URL%/ 2>nul | findstr "200" >nul
if not errorlevel 1 goto ready
if %TRIES% GEQ 30 goto failed
goto wait

:ready
echo [OK] Turtle TV is running at %URL%
start "" %URL%
exit /b 0

:failed
echo [FAIL] The server did not answer within 60 seconds.
echo        Possible causes:
echo        - Python or NumPy blocked by Windows Security (check Protection history)
echo        - Port 8773 in use by another program (netstat -ano ^| findstr 8773)
echo        - A code error: run monitor\saad_view\server.py in a terminal to see it
pause
exit /b 1
