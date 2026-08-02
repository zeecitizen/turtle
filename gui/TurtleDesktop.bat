@echo off
REM Turtle Desktop launcher. Finds Python, checks the few packages it needs, then starts
REM the panel with no console window.
setlocal
cd /d "%~dp0"
set "PYW="
for %%P in (
  "%LOCALAPPDATA%\Programs\Python\Python313-arm64\pythonw.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
) do if exist %%P set "PYW=%%~P"
if not defined PYW for /f "delims=" %%P in ('where pythonw.exe 2^>nul') do set "PYW=%%P"
if not defined PYW (
  echo Python 3.12+ is required.  Install it from https://www.python.org/downloads/
  echo Then run this again.
  pause
  exit /b 1
)
set "PY=%PYW:pythonw.exe=python.exe%"
"%PY%" -c "import websockets, matplotlib" 2>nul || (
  echo Installing the packages Turtle Desktop needs ...
  "%PY%" -m pip install --quiet websockets matplotlib mplfinance pandas
)
start "" "%PYW%" "%~dp0gui\claude_ea_gui.py"
exit /b 0
