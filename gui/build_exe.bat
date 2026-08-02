@echo off
REM Build ClaudeEA.exe — single file, no Python needed on the target PC.
REM One-time: pip install pyinstaller
setlocal
set PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe
echo Building ClaudeEA.exe ...
"%PY%" -m PyInstaller --noconfirm --onefile --windowed ^
  --name ClaudeEA ^
  --distpath "%~dp0dist" --workpath "%~dp0build" --specpath "%~dp0" ^
  "%~dp0claude_ea_gui.py"
echo.
if exist "%~dp0dist\ClaudeEA.exe" (echo DONE: %~dp0dist\ClaudeEA.exe) else (echo FAILED — is pyinstaller installed?  "%PY%" -m pip install pyinstaller)
pause
