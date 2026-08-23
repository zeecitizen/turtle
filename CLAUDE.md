# ⛔ PYTHON BACKTESTS DO NOT REFLECT REALITY — USE MT5's STRATEGY TESTER

**This is the first thing to know before proposing any strategy change.**

Proven on 2026-08-08 in a single afternoon:
- a Python replay of **163 real entries** predicted **+$876**; those same trades really made **−$657**
- a Python simulation of the tick-door promised **89% WR**; live fills gave **57%**

Python lies no matter how carefully it is written, because it fills at the price it
wants, has no spread, slippage, requotes or latency, and asks "did the low reach my
stop?" using the very candle it is trading inside — the answer is baked into the
question. Our archives also silently mix instruments and revise closed bars.

**THE RULE: Python may GENERATE a hypothesis. Only MT5's Strategy Tester — or live
fills — may PROMOTE one.** Never quote a Python P&L to Zee as evidence. Say
"hypothesis", then go and test it properly.

**How to test properly:** `mt5/CustomSymbolImport.mq5` loads OUR real volume into an
MT5 custom symbol, so the Strategy Tester replays our own data with real spread and
real execution. Full instructions in `BTCUSD/README.md`.

---


## The rule is now CODE, not memory (2026-08-10)

Zee: *"we had a strict rule never to rely on Python backtests, how can you being a
computer, break a rule?"* He was right — I quoted Python win rates and per-trade
expectancies as evidence, set an EA default from them, and predicted +$150-200. MT5
returned -$26.60.

I did not forget the rule. I rationalised past it: "counting detections is not P&L",
then slid into computing which of stop-or-target came first — which IS simulating
trades — while keeping the old label.

**Use .**  is the only sanctioned way to report a
Python win rate; it always prints the haircut and "NOT PROMOTED". 
raises if anything tries to ship a default without an MT5 result behind it.

**THE MEASURED HAIRCUT: Python overstates the win rate by ~16 points.** Three configs,
same setups, same day: 96->83, 88->67, 83->67. Discounted by 16, all three predicted
MT5 within 5 points. A configuration needs MORE THAN 16 points of Python margin to
survive real execution.

# ⛔ LAWS.md IS ZEESHAN'S — READ IT, NEVER EDIT IT

`LAWS.md` is hand-maintained by Zeeshan alone (2026-08-23: *"i'm now modifying the
laws.md myself, and we dont want it edited by anyone but zeeshan manually"*).

**Read it at session start — it is the canonical statement of what makes a setup.
Never write to it, never reformat it, never "helpfully" append to it, not even a
status line or a correction.** If something in it looks stale or wrong against the
code, SAY SO to Zeeshan and let him decide; the divergence is information, and the
document is his voice. Put your own findings in `VERSION_HISTORY.md`, the daily
report, or a new file — never in his.

# 📖 VERSION_HISTORY.md — read it, and KEEP it

`VERSION_HISTORY.md` is the EA version ledger (what shipped, when, why, with which
receipts). **Read it at session start to know where the project stands. Every time
you ship an EA version, append its entry IN THE SAME COMMIT.** Zee reads it from
other computers to catch up; a missing entry = a silent ship = a failed delivery.

# Claude Go Hawking

When Zeeshan says **"Claude go hawking"**, run the full startup sequence below. No questions, no confirmations. Just do it.

## Startup Sequence

**Self-sufficient mode (2026-05-02)**: `startup.bat` now spawns `auto_uhv_trader.py`
(Python replacement for the old Claude-driven UHV cron) and `forward_tester.py`.
Trades flow Claude-free. The old "register the trading cron" step is OBSOLETE —
the Python daemon does it autonomously.

### Step 1: Run startup.bat
Run directly from cmd / VS Code terminal (NOT via `powershell -File` — that flag
only accepts .ps1):
```
c:\Users\zeesh\Documents\GitHub\turtle\startup.bat
```
Launches: dashboard, shano_hawk (signal sniper), auto_uhv_trader (Claude-free UHV
detector), forward_tester (intra-candle diagnostics), Silver Hawk learner, Intern
Hawks, Sheriff Hawk, Sexy Hawk WhatsApp reporter, Meeting Hawks, vscode_watchdog.

### Step 2: Attach EAs in MT5 manually
Drag `ShanoExitManager`, `TurtleTradeLogger`, `ShanoTickLogger` onto XAUUSD chart.
Hot-reload picks up `shano_config.json` every 5s — no reattach needed for config edits.

### Step 3 (optional): Verify everything is alive
```
C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe C:\Users\zeesh\Documents\GitHub\turtle\monitor\sheriff_hawk.py
```
Check the Sheriff output — all components should show ALIVE.

### Step 4 (optional): Confirm
"All hawks are flying. Sniper watching, auto-UHV-trader running, forward-tester collecting, Sheriff patrolling. Trades flow Claude-free."

---

## What Each Hawk Does

| Hawk | File | Schedule | Purpose |
|------|------|----------|---------|
| **Sniper Daemon** | `monitor/claude_sniper_daemon.py` | Always on | Watches price via CDP, fires trades via PineConnector, manages P&L with bid/ask spread |
| **Auto UHV Trader** | `monitor/auto_uhv_trader.py` | Every 60s | Claude-free UHV detector: builds M1 bars from tick CSV, writes sniper_target.json or fires direct |
| **Forward Tester** | `monitor/forward_tester.py` | Every 30s | Intra-candle theory validator: spread/slippage/probe-confirm/burst stats |
| **Calibration Pipeline** | `monitor/strategy_lab/build_slip_calibration.py` + `pdf5_quick_compare.py` | On demand (weekly) | Builds empirical slippage distribution from `turtle_fills.csv`, runs calibrated backtest. Run after each ~50 new fills accumulate. |
| **Open Log (NEW)** | `Common/Files/shano_open_log.csv` | Per main open | Rich open log: send_ts, fill_ts, latency_us, intended_bid/ask, actual_fill, slip_pts. Used by calibration pipeline. |
| **Claude Trader Cron** | `crons/jobs/claude_trader.md` | OBSOLETE | Replaced by auto_uhv_trader.py — kept for reference only |
| **Silver Hawk Learner** | `monitor/silver_hawk_learner.py` | Every 15 min | Takes chart screenshots, learns visual patterns, VSA research |
| **Intern Hawks** | `monitor/intern_hawks.py` | Daily | 3 interns browse internet for trading theories, write journal |
| **Meeting Room** | `monitor/meeting_hawks.py --loop` | 9am + 9pm PKT | Full team standup — every engine presents with personality, Secretary delivers summary |
| **Sexy Hawk** | `monitor/sexy_hawk.py --loop` | Every 2h | Secretary — WhatsApp reports to Zee with sass and attitude |
| **Sheriff Hawk** | `monitor/sheriff_hawk.py --loop` | Every hour | Angry old man QA — BP tracks with losses, dies at 0% hourly WR, revive with `--revive` |

## Critical Settings (DO NOT CHANGE without testing)
- **mTS = 25** (input 72) — minimum tick size filter, blocks Sydney garbage
- **sFilt = true** (input 74) — session filter, blocks Sydney/maintenance
- **Lots = 0.40** — current position size
- **TP = 52 pips, SL = 15 pips** — PineConnector values
- **Spread tracking**: hawk uses BID for sell entry, ASK for buy entry (NEVER last_price)

## Known Mistakes (Sheriff monitors these)
1. **spread_hallucination** — hawk P&L MUST use bid/ask, not chart price
2. **restart_refire** — daemon reads `.last_uhv_id` on startup to avoid duplicate trades
3. **sydney_session** — 0% WR in Sydney, mTS+sFilt filters mandatory
4. **stale_breakout** — don't fire when price is 2+ points past UHV
5. **false_breakout_filter** — candle-close confirmation required before firing

## File Locations
- Python: `C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe`
- Project: `C:\Users\zeesh\Documents\GitHub\turtle\`
- Monitor scripts: `monitor/`
- Cron jobs: `crons/jobs/`
- API key: `monitor/.claude_api_key`
- WhatsApp config: `monitor/.whatsapp_config.json`
- Trade history: `monitor/reflections.json`
- Theories: `monitor/theories.json`
- Patterns: `monitor/silver_hawk_patterns.json`
- Intern journals: `monitor/intern_journal/`

## WhatsApp Contacts
- **Shano (sister)**: 923364863368@c.us — trade alerts in Urdu
- **Zeeshan**: 4915119175329@c.us — Sheriff emergency alerts
