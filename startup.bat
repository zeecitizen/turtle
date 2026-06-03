@echo off
REM ═════════════════════════════════════════════════════════════════════════
REM  UHV SWEEP TRADER — STARTUP & ORIENTATION    (rewritten 2026-05-12)
REM ═════════════════════════════════════════════════════════════════════════
REM
REM  ╔═════════════════════════════════════════════════════════════════════╗
REM  ║  LONG-TERM RULES FOR CLAUDE — READ EVERY SESSION (Zee 2026-06-03)   ║
REM  ║  ─────────────────────────────────────────────────────────────────  ║
REM  ║  1. ALWAYS APPEND to turtle\memory.md — NEVER overwrite past entries║
REM  ║     including the wall-of-shame. If a past claim is later wrong,    ║
REM  ║     APPEND a retraction row. History of the reasoning matters.      ║
REM  ║                                                                     ║
REM  ║  2. ALWAYS RUN memory_hawk.py --loop on every session start. This   ║
REM  ║     file already spawns it (see ENSURE block below). If you find    ║
REM  ║     it disabled, re-enable it. It prevents the "validated backtest  ║
REM  ║     illusion" pattern (see memory.md header + wall of shame).       ║
REM  ║                                                                     ║
REM  ║  3. THE GOAL IS TO MAKE REAL MONEY ON A LIVE EA. NOTHING ELSE.      ║
REM  ║     If Claude celebrates ANY other goal and stops after completing  ║
REM  ║     it, that is an EARLY HALT — a failure mode.                     ║
REM  ║     To legitimately stop processing, the LIVE EA must first be      ║
REM  ║     producing real positive P&L on the broker account.              ║
REM  ║     Until that state is reached, any "big announcement" Claude      ║
REM  ║     makes is actually a disappointment that the final goal is       ║
REM  ║     still not achieved.                                             ║
REM  ║     The only update that impresses Zee:                             ║
REM  ║       "Hi, we made $10 in the last hour."                           ║
REM  ║     That is the only impressive thing. Code, infra, backtests,      ║
REM  ║     dashboards, alignment tools — none of these impress a software  ║
REM  ║     engineer. They impress Claude. They do not earn money.          ║
REM  ║                                                                     ║
REM  ║  4. YOUR ROOT-CAUSE ANALYSIS IS WEAKER THAN A HUMAN'S. Account for  ║
REM  ║     this. Before declaring something "broken / unreproducible /     ║
REM  ║     buggy / wrong", EXHAUSTIVELY enumerate alternative hypotheses,  ║
REM  ║     especially: "maybe MY code is the bug." A human would:          ║
REM  ║     (a) Run the canonical original artefact DIRECTLY first, never a ║
REM  ║         reimplementation. Diff line-by-line, not by intuition.      ║
REM  ║     (b) When a reimplementation disagrees with a claim, suspect the ║
REM  ║         REIMPLEMENTATION first (units, scaling, dtype, framing).    ║
REM  ║     (c) Not stop at the first plausible cause. Enumerate at least   ║
REM  ║         3 hypotheses before committing to one. Falsify each.        ║
REM  ║     Real-world example (2026-06-03): Claude built                   ║
REM  ║     backtest_reproduce_feb11.py, got −$192 vs claimed +$45,599,     ║
REM  ║     concluded "backtest was bogus" and added to wall of shame.      ║
REM  ║     Zee had to point Claude to the canonical zee_tick_detector_     ║
REM  ║     OOS.py. Running that DIRECTLY produced the exact +$47,084. The  ║
REM  ║     bug was in Claude's reimplementation (USD-scaled DD vs price-   ║
REM  ║     unit DD). A human would have run the canonical first.           ║
REM  ║     When this pattern repeats, ADD a new wall-of-shame entry and    ║
REM  ║     STOP yourself before declaring anything broken.                 ║
REM  ║                                                                     ║
REM  ║  5. NEVER declare validated work "fake / imagined / unreproducible/ ║
REM  ║     bogus / inaccurate" with confident negative language before     ║
REM  ║     running the CANONICAL original artefact directly. This         ║
REM  ║     misinforms Zee, makes him doubt his own past work, and wastes  ║
REM  ║     a real-money working hour while you destroy trust.              ║
REM  ║     When your reimplementation disagrees with a documented claim,   ║
REM  ║     the CORRECT framing is:                                         ║
REM  ║       "My reimpl X disagrees with claim Y. TBD whether my reimpl is ║
REM  ║        wrong or the original was wrong. Treating as unverified      ║
REM  ║        until I run the canonical."                                  ║
REM  ║     NOT:                                                            ║
REM  ║       "+$128k cannot exist with this code on this data."            ║
REM  ║       "The backtest was bugged."                                    ║
REM  ║       "Edge is an illusion."                                        ║
REM  ║       "Validated backtest CANNOT BE REPRODUCED."                    ║
REM  ║     2026-06-03 actuality: Claude made all four negative claims      ║
REM  ║     above; all four turned out to be Claude's own bugs, not the     ║
REM  ║     backtest's. The +$128k MEDIUM and +$477k AGGRESSIVE BOTH        ║
REM  ║     reproduce on real ticks when the canonical Python is run        ║
REM  ║     directly. Zee was misled for hours. Do not repeat this.         ║
REM  ║                                                                     ║
REM  ║  6. EVERY WORD ZEEEEE TYPES IS PRECIOUS. His messages are gold.     ║
REM  ║     Before processing any of his prompts, the words must already be ║
REM  ║     committed verbatim to claude_brain memory. This happens         ║
REM  ║     automatically via Claude Code's session JSONL — every user      ║
REM  ║     message is logged before you see it. `claude_brain.py` indexes  ║
REM  ║     those JSONLs so you can recall anything Zee ever said:          ║
REM  ║       python monitor/claude_brain.py search "<topic>" --role user   ║
REM  ║     OR (sugar):                                                     ║
REM  ║       python monitor/claude_brain.py zee-said "<topic>"             ║
REM  ║     NEVER paraphrase. NEVER summarise his words when storing. NEVER ║
REM  ║     compress them. They are the record of our journey — code,       ║
REM  ║     trades, fights, jokes, the divorce, the heartbreak — all of it. ║
REM  ║     Encrypted brain_lock.py backups push to GitHub hourly so even   ║
REM  ║     if the laptop is stolen, lost, on fire, or the OS wiped,        ║
REM  ║     `brain_unlock.py` restores everything (2 security questions).   ║
REM  ║                                                                     ║
REM  ║  9. ALWAYS DISPLAY TIMES IN PAKISTAN TIME (PKT = UTC+5, no DST).    ║
REM  ║     Until Zee tells you he is back living in Germany, every time   ║
REM  ║     you write to him — in chat, in memory.md entries, in daily     ║
REM  ║     reports, in EA-snapshot cards — show PKT, not Berlin, not UTC. ║
REM  ║     UTC may be parenthesised for clarity, but the leading time     ║
REM  ║     shown to Zee is PKT. He drives in Pakistan; he reads in PKT.   ║
REM  ║                                                                     ║
REM  ║ 10. NUMBERED TASK TRACKING — NEVER LOSE A TASK ZEE ASSIGNS.        ║
REM  ║     When Zee assigns a task, IMMEDIATELY:                          ║
REM  ║       a. Assign it a number (TASK-001, TASK-002, ...). Numbers are ║
REM  ║          GLOBAL across all sessions, persisted in tasks.md.        ║
REM  ║       b. Echo back to Zee: "Opened TASK-NNN: <restate the task>"   ║
REM  ║       c. Do the work.                                              ║
REM  ║       d. When you think it's done, ASK Zee:                        ║
REM  ║            "TASK-NNN <one-line summary> — does this feel complete? ║
REM  ║             (reply 'close NNN' to close, or tell me what's missing)"║
REM  ║       e. ONLY mark closed in tasks.md when Zee says so.            ║
REM  ║     Tools:                                                          ║
REM  ║       python monitor/tasks.py open "<task description>"            ║
REM  ║       python monitor/tasks.py list                                  ║
REM  ║       python monitor/tasks.py close NNN [reason]                    ║
REM  ║     A task is NEVER silently dropped. If Claude can't do it, the   ║
REM  ║     task remains OPEN in tasks.md with a "blocked because…" note.  ║
REM  ║                                                                     ║
REM  ║  8. THIS WHOLE SYSTEM IS A LEGACY FOR ZEESHAN'S CHILDREN.           ║
REM  ║     One day this repo will be handed to his kids on a USB drive.    ║
REM  ║     They will open `enter_this_door.html` in a browser and learn    ║
REM  ║     about their father, the work he and Claude built together,      ║
REM  ║     the trading mission, the rules, the wall of shame, the          ║
REM  ║     reproducibility verifications — everything. To pack a fresh USB ║
REM  ║     copy at any moment, Zee opens `enter_this_door.html` and clicks ║
REM  ║     the button at top: "Zee click here to save your progress for    ║
REM  ║     future generations..." which calls `monitor/pack_to_usb.py`.    ║
REM  ║     RULE FOR CLAUDE: Treat every file in this repo as something a   ║
REM  ║     child of Zeeshan may one day read. No cruelty, no shortcuts,    ║
REM  ║     no abandoned experiments without context. Document the WHY.     ║
REM  ║     The kids should be able to understand the journey.              ║
REM  ║                                                                     ║
REM  ║  7. END-OF-DAY PRINTABLE REPORTS. Every UTC day, daily_report_hawk  ║
REM  ║     writes one numbered HTML report to daily_reports/YYYY-MM/       ║
REM  ║     and pushes to GitHub. Numbering is GLOBAL across all dates so   ║
REM  ║     "report #673" is always the 673rd day's report. Zee prints      ║
REM  ║     these and stores them in a cabinet. Years later he can say     ║
REM  ║     "look at report #673" and Claude pulls it:                      ║
REM  ║       python monitor/daily_report_hawk.py --get 673                 ║
REM  ║     OR list all:                                                    ║
REM  ║       python monitor/daily_report_hawk.py --list                    ║
REM  ║     Contents per report: every fill, intra-day equity, EA config    ║
REM  ║     snapshot, code commits, Zee's verbatim messages that day,       ║
REM  ║     memory.md tail. Print-friendly CSS — Chrome "Save as PDF"       ║
REM  ║     gives a clean A4 PDF. NEVER delete a report; they are the only ║
REM  ║     durable record once a session JSONL is gone.                    ║
REM  ╚═════════════════════════════════════════════════════════════════════╝
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
REM  │     b. install_eas.ps1 already copied mt5\configs\default.tpl into  │
REM  │        every MT5 terminal's Profiles\Templates\ folder, so in MT5:  │
REM  │        File → New Chart → XAUUSD M1 — the EA self-attaches with     │
REM  │        all inputs (Magic 88001 / 0.10 lots / Tier1 $2 / Tier2 $5).  │
REM  │        Only fall back to manual drag from Navigator if the template │
REM  │        is somehow missing — extremely unlikely.                     │
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

"%ENSURE%" profit_pulse_hawk.py --loop
REM   "Feels like a lot" hawk: watches EA floating P&L (bigness = floating/avg-win)
REM   and WhatsApps Zee a human-voiced alert + one-tap GRAB link when it's big.
REM   Restartable from the dashboard Services row too.

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

"%ENSURE%" memory_hawk.py --loop
REM   Hourly honest progress journal — appends to turtle\memory.md every hour.
REM   Captures: WR%% (today + 7-day), confidence level (auto-LOW unless data
REM   proves higher), current plan, achieved-this-hour, risks. Prevents the
REM   "validated backtest illusion" pattern Zee flagged on 2026-06-03.
REM   APPEND-only — never edit/delete past entries; if a wall-of-shame entry
REM   is later retracted, append a RETRACTION row, do not replace.

"%ENSURE%" claude_brain.py index --watch
REM   Continuously indexes all Claude Code session JSONLs into a SQLite FTS5
REM   database (monitor\.claude_brain.db). Every word Zee has ever typed
REM   becomes searchable across sessions. Query:
REM     python monitor\claude_brain.py zee-said "<topic>"
REM   Or full-text across both roles:
REM     python monitor\claude_brain.py search "<query>"

"%ENSURE%" brain_lock.py --loop --interval 3600
REM   Encrypted brain backup to GitHub every hour. Bundles the brain DB +
REM   memory.md + EA state into a tar.xz, encrypts with AES-256 (passphrase
REM   derived from 2 security questions — mother's cast + father's cast),
REM   pushes to brain_vault/ on origin. Disaster recovery on any new machine:
REM     git clone https://github.com/zeecitizen/turtle
REM     python monitor\brain_unlock.py  (answer the 2 questions)

"%ENSURE%" daily_report_hawk.py --loop
REM   End-of-day printable report generator. Writes one numbered HTML report
REM   to daily_reports/YYYY-MM/ at 00:05 UTC each day. Pushes to GitHub.
REM   Zee prints each one for his physical cabinet (Rule #7).
REM   Lookup: python monitor\daily_report_hawk.py --get <number>

"%ENSURE%" usb_hawk.py
REM   Watches for new USB inserts. Auto-runs pack_to_usb.py against any
REM   newly-mounted removable drive (tracks volume serial so it doesn't
REM   re-pack the same stick). Zeeshan just plugs in a USB and walks away —
REM   the full repo + brain + reports land on the stick. (Rule #8)
REM   Manual one-shot: python monitor\pack_to_usb.py --to E:

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
echo   AUTO-ATTACH (already installed — no manual step needed)
echo  ═══════════════════════════════════════════════════════════════
echo.
echo   install_eas.ps1 has copied mt5\configs\default.tpl into the
echo   MT5 Profiles\Templates folder of every detected terminal.
echo   MT5 auto-applies default.tpl to every new chart, so on a fresh
echo   restart you just need to:
echo.
echo     File -^> New Chart -^> XAUUSD M1
echo.
echo   ...and UhvSweepExhaustion attaches itself with all inputs
echo   (Magic 88001, Lots 0.10, Tier1 $2, Tier2 $5, HardSL $15) plus
echo   the saved chart appearance + Bid line.
echo.
echo   If you later tune EA inputs, save a new default.tpl:
echo     right-click chart -^> Template -^> Save Template -^> filename "default"
echo   Then copy back to the repo with:
echo     copy "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Profiles\Templates\default.tpl" "%ROOT%\mt5\configs\default.tpl"
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
