@echo off
REM ═════════════════════════════════════════════════════════════════════════
REM  UHV SWEEP TRADER — STARTUP & ORIENTATION    (rewritten 2026-05-12)
REM ═════════════════════════════════════════════════════════════════════════
REM  Reading this in a new session? Welcome. This file is the cheat-sheet
REM  for what's running on this machine. Full memory at:
REM    ~/.claude/projects/c--Users-zeesh-Documents-GitHub-turtle/memory/
REM    → MEMORY.md (index) → project_uhv_sweep_ea_live_state.md (this state)
REM
REM  WHAT THIS SYSTEM DOES (current, post-2026-05-12)
REM    Live XAUUSD trading on Blueberry Markets MT5 demo (5118408/12640543).
REM    Strategy = Zee's UHV-sweep-then-break (from his 10-lesson Loom course
REM    transcribed at monitor/_loom_audio/).
REM
REM    NEW ARCHITECTURE — native MQL5 EA, no Python sniper in the loop:
REM      MT5 chart (M1)
REM        → UhvSweepExhaustion EA detects setup natively
REM        → Path A (sweep-bar) OR Path B (wick-CAB / climactic action bar)
REM        → Validated against M5 FVG zone
REM        → OrderSendAsync entry
REM        → Tier 1 SL→BE at +$2 peak (fixes -$1.09 mechanical capture deficit)
REM        → Tier 2 ATR×1.5 trail at +$5 peak
REM        → Choke (ATR×0.5) on DOM imbalance OR tick velocity decay
REM        → Hard SL at -$15 catastrophic
REM
REM  RUNNING SERVICES (after this script completes)
REM
REM    ┌──────────────────────────┬───────┬────────────────────────────────────┐
REM    │ Service                  │ PID?  │ What it does                       │
REM    ├──────────────────────────┼───────┼────────────────────────────────────┤
REM    │ dashboard server.js      │ node  │ /uhv-sweep (new LIVE dashboard)    │
REM    │ cloudflared_daemon.py    │ py    │ Persistent public tunnel           │
REM    │ sheriff_hawk.py --loop   │ py    │ Hourly health-checks               │
REM    │ silver_hawk_learner.py   │ py    │ Pattern learner (15-min cycle)     │
REM    │ forward_tester.py        │ py    │ Intra-candle theory validator      │
REM    │ shano_trade_notifier.py  │ py    │ WhatsApp fill alerts to Shano      │
REM    │ vsisa_paper_trader.py    │ py    │ Paper-trade research (no real $)   │
REM    │ vscode_watchdog.py       │ py    │ Relaunches VS Code if it dies      │
REM    │ TradingView Desktop      │ exe   │ CDP :9222, UhvSweep Visualizer Pine│
REM    │ MT5 terminal64.exe       │ exe   │ Runs UhvSweepExhaustion + loggers  │
REM    └──────────────────────────┴───────┴────────────────────────────────────┘
REM
REM  EAs TO ATTACH IN MT5 (manual drag after install_eas.ps1 compiles)
REM
REM    PRIMARY (LIVE TRADING):
REM    1. UhvSweepExhaustion.mq5 → XAUUSD M1 chart
REM         Magic 88001 · Lots 0.10 · Tier1 $2 · Tier2 $5 · HardSL $15
REM         Reads M5 FVG + M1 UHV. Writes heartbeat to
REM         Common\Files\uhv_sweep_state.json every 5s.
REM         AutoTrading button MUST be green.
REM
REM    PASSIVE LOGGERS (also attach if not already):
REM    2. TurtleTradeLogger.mq5 → any chart (logs all fills to turtle_fills.csv)
REM    3. ShanoTickLogger.mq5   → optional (saves ticks to shano_ticks CSV)
REM
REM    LEGACY (don't re-attach — replaced by UhvSweepExhaustion):
REM    × ShanoExitManager.mq5   → was managing probe→main exits
REM    × UhvNativeTrader.mq5    → was Python-bridge UHV trader
REM
REM  PINE INDICATOR (optional but recommended for visual verification)
REM    TradingView → Pine Editor → "Turtle v7" slot → Add to chart
REM    Now holds UhvSweep Visualizer (mirrors EA detection logic, plots
REM    BUY-A/BUY-B/SELL-A/SELL-B labels + M5 FVG zones).
REM    Original Shano Momentum Scalper preserved at pine/turtle-shano.pine.
REM
REM  KEY FILES — IF SOMETHING'S WEIRD, CHECK THESE
REM    EA source            mt5\UhvSweepExhaustion.mq5
REM    Diag/smoke-test EA   mt5\UhvSweepDiag.mq5 (Magic 99001, separate chart)
REM    Pine visualizer      pine\uhv_sweep_visualizer.pine
REM    EA live state JSON   Common\Files\uhv_sweep_state.json (5s heartbeat)
REM    EA Experts log       MT5 \MQL5\Logs\YYYYMMDD.log (grep "UhvSweep")
REM    Live dashboard       https://me.claudezeeshan.com/uhv-sweep
REM    Trade fills CSV      Common\Files\turtle_fills.csv
REM    Course transcripts   monitor\_loom_audio\lesson{01-10}.txt
REM    Strategy lab         monitor\strategy_lab\zee_*.py (8 iterations)
REM
REM  WHAT'S DISABLED (deliberately — see commented ensure_daemon lines)
REM    × claude_sniper_daemon.py — replaced by native EA
REM    × shano_hawk.py           — replaced by native EA
REM    × auto_uhv_trader.py      — legacy reversal direction, contradicts Zee
REM    × strategy_lab\intern_lab_runner.py — was overfitting
REM    Sheriff process_map ALSO has shano_hawk + sniper_daemon commented out
REM    (monitor\sheriff_hawk.py:701-706) so it won't auto-revive them.
REM
REM  EA VALIDATION (smoke-tested 2026-05-12 on Blueberry)
REM    Two complete diagnostic cycles confirmed full async lifecycle:
REM    Test 1: entry 4677.74 → BE @ +$0.94 → close 4678.68 (+$0.94 profit)
REM    Test 2: entry 4680.05 → underwater → close 4679.15 (-$0.90 small loss)
REM    Net +$0.04 over 2 test trades — mechanics work end-to-end.
REM    Empirical broker quirk captured: Blueberry MT5 does NOT fire
REM    TRADE_TRANSACTION_POSITION on position open/close, only on SL modify.
REM    EA binds at DEAL_ADD instead. See memory file for full event order.
REM
REM  IDEMPOTENCY GUARANTEES
REM    - Re-running this script never crashes, never duplicates daemons
REM    - ensure_daemon.py does the "alive check + spawn if not" logic
REM    - Each step independent: failure logs [WARN] and the script continues
REM ═════════════════════════════════════════════════════════════════════════
setlocal
set "PY=C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe"
set "ROOT=C:\Users\zeesh\Documents\GitHub\turtle"
set "MON=%ROOT%\monitor"
set "ENSURE=%PY% %MON%\ensure_daemon.py"

echo.
echo  ╔══════════════════════════════════════╗
echo  ║   UhvSweep Trader — Startup          ║
echo  ║   (post-2026-05-12 native EA build)  ║
echo  ╚══════════════════════════════════════╝
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

REM ── Open NEW UhvSweep live dashboard in browser ─────────────────
timeout /t 2 /nobreak >nul 2>&1
start "" "http://localhost:3457/uhv-sweep" 2>nul
echo  [OK] UhvSweep live dashboard opened in browser

REM ── Long-running Python daemons (idempotent: skip if running) ───
REM    Live trading no longer depends on Python — these are research/support only.

REM "%ENSURE%" claude_sniper_daemon.py
REM   ↑ DISABLED 2026-05-12: replaced by native MQL5 EA UhvSweepExhaustion.
REM     Sniper polled Pine signal counter and fired via PineConnector webhook.
REM     EA now owns full entry+exit lifecycle. DO NOT re-enable unless rolling
REM     back to the Python-bridge architecture (would conflict with EA).

REM "%ENSURE%" shano_hawk.py
REM   ↑ DISABLED 2026-05-12: replaced by native EA (same reason as above).
REM     shano_hawk was the Shano-Zee 2-candle signal sniper for probe→main flow.

REM "%ENSURE%" auto_uhv_trader.py
REM   ↑ DISABLED 2026-05-04: legacy reversal direction (Green UHV → SELL) which
REM     contradicts Zee's lesson 6+ (UHV is the climactic action bar IN the
REM     retracement; we trade WITH-trend after the sweep, not reverse).

"%ENSURE%" cloudflared_daemon.py
REM   Persistent named-tunnel daemon for me.claudezeeshan.com. Reads/writes
REM   monitor\cloudflared_heartbeat.json. Sheriff Hawk verifies freshness.

"%ENSURE%" sheriff_hawk.py --loop
REM   Hourly health-check. Its auto-revive process_map has sniper_daemon and
REM   shano_hawk entries commented out (so it won't revive the killed engines).
REM   See monitor\sheriff_hawk.py lines 701-706.

"%ENSURE%" silver_hawk_learner.py
REM   15-min visual pattern learner. Not trading — research only. Keep enabled.

"%ENSURE%" forward_tester.py
REM   Intra-candle theory validator (spread/slippage/probe-confirm stats).
REM   Writes monitor\forward_test_*.json. Useful diagnostic, no real trading.

"%ENSURE%" shano_trade_notifier.py
REM   WhatsApp notifications to Shano (923364863368@c.us) on fills. Reads
REM   turtle_fills.csv tail.

"%ENSURE%" vsisa_paper_trader.py
REM   Separate VSISA paper-trade strategy (no real money). Independent of EA.

"%ENSURE%" vscode_watchdog.py
REM   Restarts VS Code if it crashes. Pure UX nicety.

REM "%ENSURE%" intern_hawks.py
REM   ↑ disabled — was scraping random trading sites; output stale.

REM "%ENSURE%" sexy_hawk.py --loop
REM   ↑ disabled — was WhatsApp report secretary. Replaced by /me chat directly.

REM "%ENSURE%" meeting_hawks.py --loop
REM   ↑ disabled — was 9am+9pm PKT team standup. Not needed for solo EA.

REM "%ENSURE%" strategy_lab\intern_lab_runner.py
REM   ↑ DISABLED 2026-04-28: variant-tester was overfitting to one bad day's
REM     data. Lab code at monitor\strategy_lab\ usable manually:
REM     `python zee_fvg_v3_detector.py` etc.

REM ── TradingView Desktop ─────────────────────────────────────────
echo.
echo  Launching TradingView Desktop with CDP :9222...
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

REM ── EA compile + install (idempotent) ───────────────────────────
echo.
echo  Compiling + installing EAs into MT5...
echo    Will compile: UhvSweepExhaustion, UhvSweepDiag, ShanoExitManager,
echo    TurtleTradeLogger, ShanoTickLogger, UhvNativeTrader.
echo    (Legacy EAs compiled but not used — UhvSweepExhaustion is THE one.)
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
echo  ═══════════════════════════════════════════════════════════════
echo   MANUAL STEPS REMAINING (cannot be automated — MT5 GUI required)
echo  ═══════════════════════════════════════════════════════════════
echo.
echo   1. In MT5 Navigator (Ctrl+N) -^> right-click Experts -^> Refresh
echo   2. Open XAUUSD M1 chart. Drag UhvSweepExhaustion from Navigator.
echo      In input dialog confirm: Magic=88001, Lots=0.10, Tier1=2,
echo      Tier2=5, HardSL=15. Click OK.
echo   3. Click AutoTrading button (top toolbar) - MUST turn GREEN.
echo   4. Verify smiley icon on chart - EA is alive.
echo   5. Watch Experts log for "UhvSweep Init done." line and a
echo      heartbeat update every 5s in dashboard /uhv-sweep tile.
echo.
echo   Optional: drag TurtleTradeLogger onto any chart so all fills
echo   get logged to Common\Files\turtle_fills.csv.
echo.
echo   Optional: TV -^> Pine Editor -^> Turtle v7 slot -^> Add to chart
echo   to see UhvSweep Visualizer labels on the chart in real time.
echo.
echo  Live dashboard: https://me.claudezeeshan.com/uhv-sweep
echo  (Or local: http://localhost:3457/uhv-sweep)
echo.

endlocal
