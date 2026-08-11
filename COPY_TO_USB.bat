@echo off
setlocal EnableDelayedExpansion
title Turtle Trader - copy to USB
color 0B

REM ============================================================================
REM  Zee, 2026-08-11: "Can you create a copy.bat such that if i run it, it
REM  copies all required files to a specified destination path such as for USB
REM  stick -> Creates folder of setup etc at E:/Turtle/setup.exe"
REM
REM  This does the whole job in one run:
REM    1. builds a fresh installer (so the stick never carries stale code)
REM    2. asks where to put it
REM    3. copies it there and names the launcher setup.bat, as he asked
REM
REM  It BUILDS first rather than copying whatever happens to be in dist/, because
REM  a USB stick carrying yesterday's EA is worse than an empty one — you would
REM  install it on another machine and never know it was old.
REM ============================================================================

echo.
echo   ===========================================================
echo      TURTLE TRADER  -  copy to USB stick
echo   ===========================================================
echo.

set "PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
if not exist "%PY%" set "PY=python"

echo   [1/3] Building a fresh installer from the current code...
echo.
"%PY%" "%~dp0make_installer.py"
if errorlevel 1 (
  echo.
  echo   BUILD FAILED - nothing was copied. Fix the error above and run again.
  pause
  exit /b 1
)
if not exist "%~dp0dist\TurtleTrader\INSTALL.bat" (
  echo.
  echo   BUILD produced no INSTALL.bat - stopping rather than copying a broken stick.
  pause
  exit /b 1
)

echo.
echo   [2/3] Where should it go?
echo.
echo         Examples:  E:\Turtle        (a USB stick)
echo                    D:\Turtle
echo                    C:\Users\zeesh\Desktop\Turtle
echo.
set "DEST=E:\Turtle"
set /p DEST=  Destination [%DEST%]:
if "%DEST%"=="" set "DEST=E:\Turtle"

REM --- does the drive actually exist? Better to say so than to create a folder
REM     on C: because the stick was never plugged in.
for %%D in ("%DEST%") do set "DRIVE=%%~dD"
if not exist "%DRIVE%\" (
  echo.
  echo   Drive %DRIVE% is not there. Plug the stick in, or give another path.
  pause
  exit /b 1
)

echo.
echo   [3/3] Copying to %DEST% ...
if not exist "%DEST%" mkdir "%DEST%"
xcopy /E /I /Q /Y "%~dp0dist\TurtleTrader\*" "%DEST%\" >nul
if errorlevel 1 (
  echo   COPY FAILED - the stick may be full or write-protected.
  pause
  exit /b 1
)

REM --- he asked for "setup" as the thing you run. INSTALL.bat is kept too, so
REM     either name works and nobody is left guessing.
copy /Y "%DEST%\INSTALL.bat" "%DEST%\setup.bat" >nul

REM --- prove the copy is complete instead of assuming xcopy told the truth
set "OK=1"
for %%F in ("setup.bat" "INSTALL.bat" "READ_ME_FIRST.txt" "payload\python\python.exe" "payload\node\node.exe" "payload\turtle\mt5\ZeeUHV.mq5") do (
  if not exist "%DEST%\%%~F" (
    echo   MISSING on the stick: %%~F
    set "OK=0"
  )
)

echo.
if "%OK%"=="1" (
  echo   ===========================================================
  echo      DONE - the stick is ready
  echo   ===========================================================
  echo.
  echo   On the new computer:
  echo      1. open %DEST%
  echo      2. run  setup.bat
  echo      3. press Enter to accept the default folder
  echo.
  echo   That is all. Nothing touches the registry, and uninstalling
  echo   is deleting the folder it installs to.
) else (
  echo   ===========================================================
  echo      INCOMPLETE - files are missing, see the list above.
  echo      Do not use this stick until it copies cleanly.
  echo   ===========================================================
)
echo.
pause
