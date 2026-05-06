@echo off
REM ═════════════════════════════════════════════════════════════════════════
REM  CLAUDE TRADER — STARTUP & ORIENTATION
REM ═════════════════════════════════════════════════════════════════════════
REM  Reading this in a new session? Welcome. This file is also the cheat-sheet
REM  for what's running on this machine. See CLAUDE_RECOVERY.md for the full
REM  story (Shano interview transcripts, system map, branch model).
REM
REM  WHAT THIS SYSTEM DOES
REM    Live momentum-scalping XAUUSD on Blueberry Markets MT5 demo, codifying
REM    Shano's (Zeeshan's sister) probe→main pattern. She turned $100 → ~$700
REM    by hand; we're trying to automate it.
REM
REM    Flow:  TradingView Pine indicator detects a 2-candle setup
REM        →  Sniper polls Pine's signal counter every 5s
REM        →  Sniper fires 0.01 probe via PineConnector webhook → MT5
REM        →  EA (ShanoExitManager) watches probe; if profit > $0.58 → main 0.40
REM        →  EA exits main on trail / fearIdeal / fearWashout / dailyCap
REM
REM  RUNNING SERVICES (after this script completes)
REM
REM    ┌──────────────────────────┬───────┬────────────────────────────────────┐
REM    │ Service                  │ PID?  │ What it does                       │
REM    ├──────────────────────────┼───────┼────────────────────────────────────┤
REM    │ dashboard server.js      │ node  │ /shano dashboard on :3457          │
REM    │ shano_hawk.py            │ py    │ THE live signal sniper (probes)    │
REM    │ sheriff_hawk.py --loop   │ py    │ 5-min health-checks, auto-restarts │
REM    │ silver_hawk_learner.py   │ py    │ Visual pattern learner (15-min)    │
REM    │ intern_hawks.py          │ py    │ 3 web-research interns (daily)     │
REM    │ sexy_hawk.py --loop      │ py    │ WhatsApp report secretary (2h)     │
REM    │ meeting_hawks.py --loop  │ py    │ 9am+9pm PKT team meetings          │
REM    │ vscode_watchdog.py       │ py    │ Relaunches VS Code if it dies      │
REM    │ patriarch.py             │ py    │ Watches sheriff (revives if dead)  │
REM    │ TradingView Desktop      │ exe   │ CDP :9222, runs Shano Pine         │
REM    │ MT5 terminal64.exe       │ exe   │ Runs the EAs (see below)           │
REM    └──────────────────────────┴───────┴────────────────────────────────────┘
REM
REM  EAs LOADED IN MT5 (drag-attached manually after install_eas.ps1 compiles)
REM    - ShanoExitManager.mq5  → manages probe→main flow + exits
REM                              hot-reads %APPDATA%\MetaQuotes\..\Common\Files\
REM                              shano_config.json every 5s (no reattach needed)
REM    - TurtleTradeLogger.mq5 → writes every fill to turtle_fills.csv
REM    - ShanoTickLogger.mq5   → records every tick to shano_ticks_YYYY-MM-DD.csv
REM                              (for tick-level backtesting)
REM
REM  KEY FILES — IF SOMETHING'S WEIRD, CHECK THESE
REM    Live state           shano_live.json (Common\Files; EA writes every 1s)
REM    Hot-reload config    shano_config.json (Common\Files; edit any time)
REM    Sniper state         monitor\.shano_state.json (last_fired counter, dir)
REM    Sniper log           monitor\shano_hawk.log ([HB] every 60s = healthy)
REM    Tick history         Common\Files\shano_ticks_YYYY-MM-DD.csv
REM    Trade fills CSV      Common\Files\turtle_fills.csv
REM    Strategy lab         monitor\strategy_lab\lab.py + RESULTS.md
REM    Pine source          pine\turtle-shano.pine
REM    EA source            mt5\ShanoExitManager.mq5
REM
REM  CRITICAL RULES (codified, do not change without re-asking Shano)
REM    - "Big candle"    body[N] > 1.5x body[N-1] (body1 ONLY, not body2)
REM    - 2-candle pattern: 1st bar big, 2nd bar same direction (any size)
REM    - Probe lots = 0.01, confirm = +$0.58, fail = -$3, timeout = 50s
REM    - Main lots = 0.40, trail at +$8 / drop $2, fearIdeal -$70
REM    - probe and main MUST be same direction (EA OpenMainTrade reads probe type)
REM    - Both buy + sell enabled (sellOnly: false — AI can switch context)
REM    - Daily cap = $500, max burst = 5, max positions = 3
REM
REM  WHAT'S DISABLED (deliberately) — see "REM" prefixed lines below
REM    - claude_sniper_daemon.py (legacy UHV strategy, lives on
REM      Old-Turtle-Volume-Based branch — uncomment to revive)
REM    - strategy_lab\intern_lab_runner.py (auto-tester was over-fitting)
REM
REM  IDEMPOTENCY GUARANTEES
REM    - Re-running this script never crashes, never duplicates daemons
REM    - ensure_daemon.py does the "alive check + spawn if not" logic
REM    - Sheriff also delegates spawning to ensure_daemon (no race conditions)
REM    - Each step independent: failure logs [WARN] and the script continues
REM ═════════════════════════════════════════════════════════════════════════
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

REM ── Long-running Python daemons (idempotent: skip if running) ───
REM "%ENSURE%" claude_sniper_daemon.py
REM   ↑ disabled 2026-04-28: legacy UHV breakout sniper, lives on
REM     Old-Turtle-Volume-Based branch. Re-enable here to revive UHV trading.
"%ENSURE%" intern_hawks.py
"%ENSURE%" silver_hawk_learner.py
"%ENSURE%" sexy_hawk.py --loop
"%ENSURE%" meeting_hawks.py --loop
"%ENSURE%" sheriff_hawk.py --loop
"%ENSURE%" shano_hawk.py
"%ENSURE%" shano_trade_notifier.py
"%ENSURE%" vscode_watchdog.py
REM "%ENSURE%" auto_uhv_trader.py
REM   ↑ DISABLED 2026-05-04: implements LEGACY reversal direction (Green UHV → SELL,
REM     Red UHV → BUY) which CONTRADICTS the live Shano-Zee strategy (Green UHV → BUY
REM     continuation per Setup 1). Was firing trades against our validated edge.
REM     Trade flow now relies entirely on: Pine alert → PineConnector → EA (Setup 1).
REM     Re-enable only after rewriting direction logic to match Shano-Zee
REM     and adding the LIVE filter stack (UHV+effort+trend+Setup 1+spread+tick-speed).
"%ENSURE%" forward_tester.py
REM   ↑ added 2026-05-02: real-time intra-candle theory validator.
REM     Per-bar diagnostics (spread/slippage), probe-every-candle backtest,
REM     consensus-burst test, main-after-confirm WR. Output: monitor/forward_test_*.
REM "%ENSURE%" strategy_lab/intern_lab_runner.py
REM   ↑ disabled 2026-04-28: variant-tester was over-fitting to one bad day's data and
REM   making config worse. Lab code at monitor/strategy_lab/ is still usable manually
REM   ('python lab.py' to see rankings, '--apply VX' to apply). Re-enable here if/when
REM   you want autonomous iteration again.

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
