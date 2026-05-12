@echo off
REM ═════════════════════════════════════════════════════════════════════════
REM  UHV SWEEP TRADER — STARTUP & ORIENTATION    (rewritten 2026-05-12)
REM ═════════════════════════════════════════════════════════════════════════
REM
REM  ┌─────────────────────────────────────────────────────────────────────┐
REM  │  CLAUDE: IF YOU ARE READING THIS IN A FRESH SESSION                 │
REM  │  ───────────────────────────────────────────────────                │
REM  │  This file is the entry point for resuming the trading system.      │
REM  │  Do these steps IN ORDER before doing anything else:                │
REM  │                                                                     │
REM  │  1. Your MEMORY.md auto-loads at session start. Look for the entry: │
REM  │     "UhvSweep EA LIVE STATE (2026-05-12)" → read it first.          │
REM  │     File: ~/.claude/projects/c--Users-zeesh-Documents-GitHub-turtle │
REM  │            /memory/project_uhv_sweep_ea_live_state.md               │
REM  │                                                                     │
REM  │  2. Also recommended (related context):                             │
REM  │     - project_mechanical_capture_deficit_solution.md (why the EA)   │
REM  │     - project_zee_feb11_lessons_synth.md (the 10-lesson strategy)   │
REM  │     - feedback_zee_strategy_is_real_capture_it.md (verified edge)   │
REM  │                                                                     │
REM  │  3. The trading engine is now a SINGLE native MQL5 EA:              │
REM  │     mt5/UhvSweepExhaustion.mq5  (Magic 88001)                       │
REM  │     All Python snipers + old EAs are deliberately DISABLED.         │
REM  │     Do NOT re-enable claude_sniper_daemon, shano_hawk, or           │
REM  │     auto_uhv_trader — they would CONFLICT with the EA.              │
REM  │                                                                     │
REM  │  4. To verify everything is alive RIGHT NOW (read-only):            │
REM  │     curl http://localhost:3457/api/uhv-sweep                        │
REM  │     → expects alive:true, heartbeat_age_sec < 10                    │
REM  │     → live dashboard at https://me.claudezeeshan.com/uhv-sweep      │
REM  │                                                                     │
REM  │  5. If dashboard returns "no heartbeat" or EA isn't running:        │
REM  │     a. Run this startup.bat (idempotent — won't duplicate anything) │
REM  │     b. If the user has done the one-time "save default template"    │
REM  │        step (see AUTO-ATTACH SETUP block printed at end of script), │
REM  │        the EA loads itself on every new XAUUSD M1 chart.            │
REM  │        Otherwise: MANUALLY in MT5 → Navigator → Experts → drag      │
REM  │        UhvSweepExhaustion onto XAUUSD M1 chart.                     │
REM  │     c. AutoTrading button GREEN.                                    │
REM  │     d. Smiley face on chart = EA alive.                             │
REM  │     e. uhv_autotrade_watchdog.py will WhatsApp Zee if the heartbeat │
REM  │        file stops updating for >90s — alert-only, never toggles     │
REM  │        AutoTrading state itself (toggle command is unsafe blind).   │
REM  │                                                                     │
REM  │  6. If a previous session was working and you see a stuck position: │
REM  │     UhvSweepExhaustion has OnInit amnesia recovery — re-attach the  │
REM  │     EA and it scans PositionsTotal for Magic 88001 + XAUUSD and     │
REM  │     auto-rebinds trail state (entry, peak, side, lots).             │
REM  │                                                                     │
REM  │  7. For full debugging (entry/exit lifecycle):                      │
REM  │     mt5/UhvSweepDiag.mq5 (Magic 99001, SEPARATE chart) — smoke      │
REM  │     test that exercises OrderSendAsync, DEAL_ADD bind, BE modify,   │
REM  │     and close in 16 seconds. Set InpRunTest=true to fire.           │
REM  │                                                                     │
REM  │  8. Git state:                                                      │
REM  │     `git log --oneline -5` to see recent commits.                   │
REM  │     Latest production commit: "UhvSweepExhaustion: native MQL5 EA"  │
REM  │                                                                     │
REM  │  IF YOU'RE STILL UNSURE: just run this script. It logs every        │
REM  │  step. Then read the manual-steps printed at the end and execute    │
REM  │  them in MT5. The system will be back online within ~30 seconds     │
REM  │  of the EA being dragged onto the chart.                            │
REM  └─────────────────────────────────────────────────────────────────────┘
REM
REM  Full memory directory:
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
REM    │ uhv_autotrade_watchdog.py│ py    │ WhatsApp-alerts if EA heartbeat dies│
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

"%ENSURE%" uhv_autotrade_watchdog.py
REM   Watches Common\Files\uhv_sweep_state.json mtime. If EA heartbeat goes
REM   stale ^>90s, WhatsApp-alerts Zee that the EA detached / AutoTrading off /
REM   MT5 crashed. Alert-only (no auto-toggle — WM_COMMAND 32851 is a toggle,
REM   not a setter, so blind retry could disable a healthy ON state).

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
REM   Boot config: mt5\uhv_sweep_boot.ini sets login=12640543 + Blueberry server
REM   + auto-enables live trading. It does NOT auto-attach the EA — that needs
REM   the one-time chart-template setup described in the "MANUAL STEPS" block
REM   at the end of this script (look for "AUTO-ATTACH SETUP").
tasklist /FI "IMAGENAME eq terminal64.exe" 2>nul | find /I "terminal64.exe" >nul
if errorlevel 1 (
    if exist "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe" (
        if exist "%ROOT%\mt5\uhv_sweep_boot.ini" (
            start "" "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe" /config:"%ROOT%\mt5\uhv_sweep_boot.ini"
            echo  [OK] MT5 launched with uhv_sweep_boot.ini config
        ) else (
            start "" "C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe"
            echo  [OK] MT5 launched (no boot config found)
        )
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
echo  ═══════════════════════════════════════════════════════════════
echo   ONE-TIME AUTO-ATTACH SETUP (do steps 1-4 above, then once)
echo  ═══════════════════════════════════════════════════════════════
echo.
echo   After dragging UhvSweepExhaustion on the chart, save it as the
echo   default template so MT5 auto-attaches the EA on every startup:
echo.
echo     a. Right-click the XAUUSD M1 chart -^> Template -^> Save Template
echo     b. Filename: default     (literally that, lowercase, no .tpl)
echo     c. Click Save. Confirm overwrite if prompted.
echo.
echo   From now on, every new XAUUSD M1 chart will auto-load the EA with
echo   all your inputs preserved. Combined with the /config:uhv_sweep_boot.ini
echo   bootstrap above, this gives you a full cold-start to live-trading
echo   in a single double-click of startup.bat.
echo.
echo   To verify it worked: close the XAUUSD chart, then File -^> New Chart
echo   -^> XAUUSD M1. The EA should appear automatically with smiley icon.
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
echo  ═══════════════════════════════════════════════════════════════
echo   QUICK VERIFICATION (for Claude or human)
echo  ═══════════════════════════════════════════════════════════════
echo.
echo   Once UhvSweepExhaustion is attached, verify it's alive:
echo.
echo     curl -s http://localhost:3457/api/uhv-sweep
echo.
echo   Expect: {"alive":true, "ea":"UhvSweepExhaustion v1.00",
echo            "heartbeat_age_sec":^<10, "position_open":false/true, ...}
echo.
echo   To see signals as they fire, watch the MT5 Experts log:
echo     C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\^<TERMINAL^>\MQL5\Logs\
echo     grep "UhvSweep" YYYYMMDD.log
echo.
echo   Signal lifecycle log markers:
echo     [SIGNAL]         → Entry condition detected
echo     [ENTRY FILLED]   → DEAL_ADD captured, position open
echo     [TRAIL BIND]     → Trail state bound to ticket
echo     [TRAIL tier=1]   → SL moved to break-even at +$2 peak
echo     [TRAIL tier=2]   → ATR×1.5 trail engaged at +$5 peak
echo     [EXHAUST EXIT]   → DOM imbalance/velocity decay triggered close
echo     [HARD SL]        → -$15 catastrophic stop hit
echo     [CLOSE FILLED]   → Position closed cleanly
echo.
echo  ═══════════════════════════════════════════════════════════════

endlocal
