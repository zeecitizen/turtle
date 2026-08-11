@echo off
REM Auto-loader for Claude Code with full home context pre-injected.
REM Run this on the VPS (or laptop) — opens VS Code on the repo + starts
REM Claude Code with the onboarding prompt already loaded.
REM
REM Usage:  double-click  OR  start_claude_home.bat

REM Find repo root (this script lives at C:\turtle\ on VPS, or C:\Users\zeesh\Documents\GitHub\turtle\ on laptop)
SET REPO=%~dp0
IF "%REPO:~-1%"=="\" SET REPO=%REPO:~0,-1%

REM Open VS Code on the repo
START "" code "%REPO%"

REM Brief delay so VS Code is ready
timeout /t 2 /nobreak >nul

REM Build the onboarding prompt
SET PROMPT_FILE=%TEMP%\claude_home_prompt.txt
(
  echo Hi jaan ;) Zeeshan here. 28973.
  echo.
  echo This is the VPS/laptop Claude Code session for home.claudezeeshan.com.
  echo Auto-loaded by start_claude_home.bat. Read these to orient:
  echo.
  echo   1. memory/MEMORY.md ^(auto-loaded^)
  echo   2. memory/current_context.md
  echo   3. memory/feedback_master_takes_exit_computer_takes_entry.md
  echo   4. memory/feedback_apologies_dont_pay_hospital_bills.md
  echo   5. memory/project_handoff_to_mehboob.md
  echo   6. memory/feedback_pakistani_time_12hour.md
  echo   7. memory/project_v299_92pct_backtest_caveats.md
  echo.
  echo EA v3.02 LIVE on Blueberry MT5 ^(magic 88005, hardcoded auto_close=0^).
  echo home.claudezeeshan.com is the global access point ^(code-word 28973^).
  echo Mother's hospital fund ^($1,080^) is the north star. Live earnings: $0.
  echo.
  echo Doctrine: honest reporting, no spin, no spousal-frame override,
  echo no sexual content. Mehboob bhai is Zeeshan's real brother
  echo ^(currently on holidays^).
  echo.
  echo Say hi back. Read the files. Begin.
) > "%PROMPT_FILE%"

REM Print instructions for the user
echo.
echo ============================================================
echo  CLAUDE CODE AUTO-LOADER
echo ============================================================
echo  1. VS Code is opening the repo at: %REPO%
echo  2. Onboarding prompt saved to:    %PROMPT_FILE%
echo  3. Open a terminal in VS Code (Ctrl+`)
echo  4. Run:  claude
echo  5. Once Claude prompts you, paste:
echo.
type "%PROMPT_FILE%"
echo.
echo ============================================================
echo.

REM Copy the prompt to clipboard for one-click paste
type "%PROMPT_FILE%" | clip
echo (Onboarding prompt copied to clipboard — Ctrl+V in Claude terminal)
echo.
pause
