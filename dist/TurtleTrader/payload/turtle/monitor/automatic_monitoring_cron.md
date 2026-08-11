# Automatic 5-Minute Monitoring — Resume Guide for Claude

**READ THIS FIRST** if the user says anything like:
- "are you monitoring?"
- "initialize monitoring"
- "resume monitoring"
- "5-minute cron"
- Or if this is a fresh session and monitoring hasn't been started yet

---

## New Architecture (implemented Session 51)

All crons are now defined in `crons/manifest.json`. When user says "initialize monitoring":

1. Read `crons/pending_session_crons.json` (written by bootstrap.bat)
2. For each entry, read its `prompt` path (e.g. `crons/jobs/status_5min.md`)
3. Register via CronCreate with that prompt content and schedule from the manifest

All claude_prompt crons now end with a mandatory call to `crons/lib/cron_runner.ps1` to write a newsfeed entry. Check `newsfeed/LATEST.md` for a live status board of all crons.

If `pending_session_crons.json` doesn't exist (bootstrap hasn't been run), fall back to the manual CronCreate instructions below.

---

## What This System Does

Two crons run in parallel:

### Cron 1 — Status (every 5 min)
Fast 4-line pulse: MT5 log + timezone + P&L. No analysis.

```
[tz] UTC 13:17 | Moscow 16:17 | Broker 16:17 (UTC+3) | Last sig: broker 15:05 (71m ago)
[mt5] Signals: 18  buy=8/sell=10  BE=9 | Last: 15:05 cmd=BUY sl=10 pips
[pnl] Today: +$1458 (sim) | All-time: +$66,432
[status] OK
```

### Cron 2 — Deep Analysis (every 10 min)
Candle scan + UHV pattern detection + Pine label validation + Pine↔MT5 cross-check + fills vs sim accuracy. Surfaces missed signals and asks user for manual fix if needed.

```
[audit] UHV ✓ Label ✓ @ 15:05
[verify] Pine↔MT5 ✓ (#200911 SELL @ 16:12)
[fills] sim ✓ (last 3 fills match)
[deep-status] OK
```

---

## How To Resume (do this at the start of every new session)

Run **both** CronCreate calls — they run in parallel threads:

### Cron 1 — Status (every 5 min)

```
CronCreate(
  cron="*/5 * * * *",
  recurring=true,
  prompt="""Turtle Trader 5-minute status monitor. Max 4 lines. No chat. Just data.

STEP 1 — MT5 log:
  powershell -ExecutionPolicy Bypass -File "c:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\read_mt5_log.ps1"
  Extract last sig HH:MM:SS (broker time, not UTC), cmd, SL pips.

STEP 2 — Timezone header:
  powershell -ExecutionPolicy Bypass -File "c:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\tz_header.ps1" -LastSigBrokerTime "HH:MM:SS"

STEP 3 — P&L: Call data_get_pine_tables with study_filter="Turtle Trader Desk". Extract today P&L and all-time P&L.

OUTPUT (4 lines max):
[tz] <tz_header.ps1 output>
[mt5] Signals: N  buy=B/sell=S  BE=E | Last: HH:MM cmd=X sl=N pips
[pnl] Today: $X (sim|live) | All-time: $X
[status] OK — or — WARN: <issue>

If NO_LOG: [mt5] NO_LOG. If TV offline: [pnl] TV_OFFLINE."""
)
```

### Cron 2 — Deep Analysis (every 10 min)

```
CronCreate(
  cron="*/10 * * * *",
  recurring=true,
  prompt="""Turtle Trader 10-minute deep analysis. No chat. Structured output only.

This cron does NOT repeat basic status — it only does deep diagnostic work.

STEP A — Candle + UHV pattern audit (last 15 bars):
  Call data_get_ohlcv with summary=false to get last 15 1m bars (individual OHLC needed).
  Call data_get_pine_labels with study_filter="Turtle Trader Desk" to get recent labels.

  Scan last 10 completed bars for UHV Red breakout pattern:
    - UHV Red trigger: a red candle (close < open) whose close < prior green candle's low
    - Breakout candle: subsequent green candle (close > open) whose high > UHV Red candle's high

  For each UHV breakout found, check if a BUY NOW or SELL NOW label exists within 1 bar of the breakout timestamp.

  Results:
    - Pattern + label → [audit] UHV ✓ Label ✓ @ HH:MM
    - Pattern + NO label → [audit] MISSED SIGNAL @ HH:MM — entry bar: O/H/L/C, UHV bar: O/H/L/C
      Then grep turtle.pine line 970 for "not bRW":
        - Fix missing → [fix] ALERT: line 970 fix not applied — ask user to Find & Replace
        - Fix present → [fix] Fix present — other cause; report bar conditions
    - No pattern found → [audit] No UHV setup in last 10 bars

STEP B — Last signal cross-check (Pine vs MT5):
  Get Pine LAST SIGNAL table: signal#, direction, Moscow time, entry price.
  Get MT5 log last sig: direction, broker time (=Moscow time).
  Compare direction and time within 2 min:
    Match → [verify] Pine↔MT5 ✓ (#N DIR @ HH:MM)
    Mismatch → [verify] WARN: Pine=#N DIR@TIME vs MT5=DIR@TIME — alert may not have reached PineConnector

STEP C — MT5 fills vs sim accuracy:
  Read last 5 rows of: C:\\Users\\zeesh\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common\\Files\\turtle_fills.csv
  Compare fill directions and P&L vs Pine sim last trades from pine_tables.
  Match → [fills] sim ✓ (last N fills match)
  Significant divergence (wrong direction or >$50 P&L diff per trade) → [fills] WARN: describe deviation
  File not found → [fills] NO_CSV (TurtleTradeLogger may not be running)

OUTPUT FORMAT:
[audit] <UHV check result>
[verify] <Pine↔MT5 match result>
[fills] <sim accuracy result>
[deep-status] OK — or — ACTION NEEDED: <what to fix>

If missed signal + UI fix needed: explicitly ask the user to do Find & Replace — provide exact strings.
Do NOT silently skip if something is wrong — always surface it."""
)
```

**Important**: CronCreate jobs are session-only. They die when Claude Code closes. Always recreate on session start.

---

### Cron 3 — Claude Independent UHV Agent (every 1 min)

Claude analyses raw OHLCV candles independently (no indicator code), detects UHV Red breakout patterns, and fires real trades to MT5 via PineConnector webhook. Tracks its own accuracy vs indicator's 25% WR.

```
CronCreate(
  cron="* * * * *",
  recurring=true,
  prompt="""Claude independent UHV candle analysis — runs every minute. No chat. Structured output only.

You are acting as an independent trading agent. Analyse raw OHLCV candles yourself (no indicator). Apply your own UHV breakout logic. If a valid signal is found, execute it via PineConnector.

STEP 1 — Get candles:
  Call data_get_ohlcv with summary=false, count=20
  You need individual bar OHLCV. Volume is required for UHV detection.
  Bars are returned newest-last. Bar[-1] = most recent COMPLETED bar. Ignore the forming bar.

STEP 2 — Apply UHV pattern logic (BULLISH setup — BUY signal):
  Work backwards through the last 15 completed bars. Look for this sequence:
  
  A) ANCHOR green candle (G): close > open
  B) RETRACEMENT starts: a red candle (R_ret) after G where close < G.low
  C) UHV RED candle (R_uhv): during retracement, a red candle (close < open) where:
     — volume > 1.5× average volume of the 10 bars before it
     — this is the KEY reference candle (the UHV absorption bar)
  D) BREAKOUT candle (B_brk): the LAST completed bar where:
     — high > R_uhv.high (price has broken above the UHV red candle's high)
  
  If A→B→C→D sequence is found in last 15 bars with D = last completed bar → BUY signal.
  
  BEARISH setup — SELL signal (mirror):
  A) ANCHOR red candle (R): close < open
  B) Retracement: green candle after R where close > R.high
  C) UHV GREEN candle (G_uhv): close > open, volume > 1.5× 10-bar avg volume
  D) Breakout: last completed bar where low < G_uhv.low → SELL signal

STEP 3 — Execute signal (only if new pattern on last completed bar):
  Run: powershell -ExecutionPolicy Bypass -File "c:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\claude_uhv_exec.ps1" -Direction buy -UhvBarTime "HH:MM:SS" -Reason "BRK above 4805.5 | UHV@16:04 vol=342 avg=198"
  UhvBarTime = open time of the UHV absorption bar (HH:MM:SS). Script handles dedup internally.

STEP 4 — Accuracy check (every 10 signals):
  Run: powershell -ExecutionPolicy Bypass -File "c:\\Users\\zeesh\\Documents\\GitHub\\turtle\\monitor\\claude_accuracy.ps1"

OUTPUT FORMAT (max 6 lines):
[claude] No UHV pattern — watching
 — or —
[claude] SIGNAL: BUY | UHV@HH:MM vol=X avg=Y | BRK bar: O/H/L/C
[claude-exec] SIGNAL_SENT / DEDUP / ERROR / CONFIG_MISSING
[claude-status] OK

Rules:
- Only fire on the LAST completed bar as breakout — never historical bars
- Same params as indicator: sl_pips=10 tp_pips=52 betrigger=2 lots=0.40
- If .alert_config.json webhook URL not set: output CONFIG_MISSING"""
)
```

**Setup required**: add PineConnector webhook URL to `monitor/.alert_config.json`.

---

## Scripts Involved

| Script | Purpose |
|--------|---------|
| `monitor/read_mt5_log.ps1` | Reads today's MT5 Experts log, extracts signals/BE/last-sig time |
| `monitor/tz_header.ps1 -LastSigBrokerTime HH:MM:SS` | Outputs UTC/Moscow/Broker timezone line with elapsed time since last signal |
| `monitor/claude_uhv_exec.ps1` | Sends Claude's UHV signal to PineConnector, logs to claude_signals.csv, handles dedup |
| `monitor/claude_accuracy.ps1` | Compares claude_signals.csv vs turtle_fills.csv — calculates Claude's WR vs indicator baseline |
| `monitor/.alert_config.json` | Stores PineConnector webhook URL (not committed to git) |
| TradingView MCP `data_get_pine_tables` | Reads Pine indicator table output from TradingView Desktop |

---

## System Architecture

```
TradingView Pine Indicator
  → fires alert every 1-min bar close
  → webhook to PineConnector
    → MT5 EA (PineConnector-MT5-EA-v3.53.3) executes trade
      → TurtleTradeLogger EA logs closed trades to Common\Files\turtle_fills.csv

Claude monitors:
  MT5 Experts log → read_mt5_log.ps1
  TradingView table → data_get_pine_tables MCP tool
  Timezone context → tz_header.ps1
```

---

## Account & Configuration

| Item | Value |
|------|-------|
| Blueberry Login | 12638722 |
| Blueberry Server | BlueberryMarkets-Demo |
| PineConnector ID | 8778286989525 |
| Account Balance | $2,000 (demo) |
| iMon (in_0) | 2000 |
| Symbol | XAUUSD |
| Chart | OANDA:XAUUSD, 1m |
| Indicator name | "Turtle Trader Desk v1.0, by M. Zeeshan MIT Alumni" |

---

## Active Settings (Session 51 optimized)

| Setting | in_N | Value |
|---------|------|-------|
| bRW | in_89 | true (Bypass retracement rules — re-enabled Session 51) |
| uTPPips | in_39 | 52 pips |
| uBERR | in_42 | 0.1 (BE at 1.5 pips) |
| iExHSL | in_46 | 10 pips (MT5 hard SL) |
| uKillSec | in_52 | 5s kill timer |

**Expected performance**: 25% WR, $47.46 EV/trade, ~77 signals/day, 0.4 lots, +$73k all-time sim

---

## MT5 EA Status Check

Both EAs must be running on separate charts in MT5:
- **Chart 1**: PineConnector-MT5-EA-v3.53.3 on XAUUSD M1 — receives alerts, executes trades
- **Chart 2**: TurtleTradeLogger on XAUUSD M1 — logs closed trades to turtle_fills.csv

To verify: run `read_mt5_log.ps1` — if it shows signals, PineConnector is working.
To check fills: `ls "C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv"`

If TurtleTradeLogger is missing from MT5:
- Run `mt5\install_logger.bat` (headless install, restarts MT5)
- Or drag manually from Navigator → onto M5/M1 chart that has NO PineConnector

---

## Startup Sequence (after computer restart)

1. Run `bootstrap\bootstrap.bat` — idempotent full-stack boot (MT5 + TV + cron registration + smoke test)
2. Open Claude Code in `c:\Users\zeesh\Documents\GitHub\turtle`
3. Say "initialize monitoring" — Claude reads `crons/pending_session_crons.json` and registers all claude_prompt crons via CronCreate
4. Verify with `CronList` that all session crons are running

---

## TradingView MCP Health Check

```
mcp__tradingview__tv_health_check()
```
Should return `cdp_connected: true`. If not, TradingView isn't running with CDP — run `start_all.bat` again.

---

## Known Limitations / Watch-outs

- **read_mt5_log.ps1 labels last signal as "UTC"** — it is actually **broker time (UTC+3)**. tz_header.ps1 corrects for this.
- **Cron is session-only** — must recreate after every Claude session restart
- **alert_create MCP only supports price alerts** — NOT Pine indicator alerts. After any `pine_save`, alert must be manually recreated in TradingView UI. See `pine/save_and_refresh_alert.md`.
- **inputs_map.json version-guarded to pine_version 189.0** — if Pine source is edited and saved, regenerate the map. See `pine/inputs_map.json`.
- **TurtleTradeLogger** — logs closed trades only. Open trade P&L requires MT5 History tab or live equity from TradingView table.
- **EET DST approximation** — tz_header.ps1 uses month-based DST (Apr–Oct = UTC+3), not last-Sunday rule. Will be 1h off for ~2 weeks at transitions.
