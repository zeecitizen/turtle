# 🚨 CLAUDE — READ THIS FIRST, EVERY SESSION, BEFORE ANY DEBUGGING

You have no persistent memory between sessions. This file is the closest thing
you have to one. If you skip this file and start building new analysis blind,
you WILL waste hours rediscovering what you already wrote.

## Mandatory pre-flight checklist (do these 4 steps BEFORE any new work)

1. **Read `memory.md`** (project root, NOT the .claude memory dir):
   - Top section: hourly journal → most recent entry = current state
   - Wall of shame → every claim you ever made that turned out wrong
   - Look for the topic you're about to work on — if it's in wall of shame
     with a retraction, START THERE.

2. **Read `OVERNIGHT_RESULT_FOR_ZEE.md`** (project root):
   - Self-written 2026-05-30 by an earlier Claude session.
   - 34-cycle backtest results, final config, "what to do tomorrow" notes.
   - **IF DEBUGGING A BACKTEST CLAIM**: this file points to the canonical
     Python and MQL5 sources. Run THOSE directly, never reimplement.

3. **Read the CANONICAL FILES TABLE below** for the domain you're working in.

4. **If your reimplementation disagrees with a documented claim**, your
   reimplementation is wrong until you prove the canonical wrong by running
   it directly. See startup.bat rules #4 and #5.

## Canonical files table — search this BEFORE building anything new

| Domain | Canonical artefact | Last-validated status |
|---|---|---|
| **AGGRESSIVE strategy Python** | `monitor/strategy_lab/zee_tick_detector_OOS.py` | ✅ 2026-06-03 reruns identical to OVERNIGHT claim: Feb 11 = +$47,084, 27d = +$548,296. |
| **MEDIUM strategy Python** | `monitor/strategy_lab/zee_tick_detector_MEDIUM.py` | ✅ 2026-06-03 built + verified: 27d = +$167,692 @ 0.10L. |
| **AGGRESSIVE EA source** | `mt5/Feb11TickTrader.mq5` (Magic 88009) | ⚠️ v1.12, still uses FTMO GMT+3 session defaults. Needs GMT+0 calibration before Atmos deploy. |
| **MEDIUM EA source (currently LIVE)** | `mt5/Feb11TickMedium.mq5` (Magic 88011) | ✅ v1.18, GMT+0 calibrated, broker-SL tracking fixed (v1.17 addition). |
| **Day-by-day equity curve (AGGRESSIVE)** | `monitor/strategy_lab/EQUITY_CURVE.txt` | ✅ 22 days, 20W/2L, max DD $196, peak $477k. |
| **Cycle-by-cycle research log** | `monitor/strategy_lab/OVERNIGHT_LOG.md` | ✅ 34 cycles documented with what changed + P&L delta per cycle. |
| **Backtest harness (validated config)** | `monitor/strategy_lab/cycle27_re_trail_cb.py` | ✅ Last cycle that adjusted params before lock; trail_gb sweep. |
| **Cycle 32 equity curve generator** | `monitor/strategy_lab/cycle32_equity_curve.py` (referenced) | Used for EQUITY_CURVE.txt build. |
| **MEDIUM-vs-LIVE 27-day comparison** | `monitor/strategy_lab/backtest_all_days_v118_vs_live.py` | ⚠️ Uses MY buggy USD-scaled DD. Replace with zee_tick_detector_MEDIUM.py. |
| **Feb 11 alignment visualizer** | `https://me.claudezeeshan.com/feb11-lab` + `dashboard/claude_trader/feb11_lab.html` (built by `monitor/strategy_lab/build_feb11_lab.py`) | ✅ Click any candle → Claude+Zee side-by-side modal. TEACH_LABELS persist to `monitor/feb11_labels.json`. |
| **Labels persistence backend** | `dashboard/claude_trader/server.js` route `/api/feb11-label` | ✅ GET/POST JSON. |
| **Live EA state files** | `Common\Files\feb11_state_88011.json`, `feb11_runtime_88011.json` | Read by EA, written by EA + `apply_runtime.py`. **WARNING**: state's `session_pnl` is misleading; use `turtle_fills.csv` for broker truth. |
| **Real broker fills (source of truth)** | `Common\Files\turtle_fills.csv` | Authoritative. Schema: broker_time,deal_ticket,position_ticket,symbol,direction,volume,close_price,profit,commission,swap,net_pnl,comment,magic,ea |
| **Tick CSVs (logged per day)** | `Common\Files\shano_ticks_YYYY-MM-DD.csv` | Format: `t,bid,ask` (t = `YYYY.MM.DD HH:MM:SS.fff`). 27 days available 2026-02-11 through today. |
| **Hourly progress journal** | `memory.md` (project root) | Append-only via `monitor/memory_hawk.py --loop`. |
| **Runtime config tweaks (no recompile)** | `monitor/apply_runtime.py` | 15 params tunable: lots, trail-arm, trail-gb, skim-cap, max-loss, broker-sl, broker-tp, daily-dd, rng60-min, rng60-norm, spread-max, cooldown, max-hold, loss-streak-n, loss-streak-pause. |
| **EA source dual-path gotcha** | `.claude/.../memory/project_ea_dual_source_gotcha.md` | Editing `turtle/mt5/*.mq5` does NOT reach MetaEditor. ALWAYS `cp` repo → `MetaQuotes/Terminal/<GUID>/MQL5/Experts/` BEFORE telling Zee to F7. Atmos GUID = `997C47BF6122E1564BE4267B96E7F5C7`. |
| **Atmos timezone fact** | `.claude/.../memory/project_atmos_broker_gmt0_calibration.md` | Atmos broker is GMT+0 (UTC). State file's `session_date` resets at 00:00 UTC ⇒ broker midnight = UTC midnight. Sessions: 90/150/1005/1185. |

## Common-bug catalog — your past mistakes, persisted

When you find yourself about to do one of these, STOP and search the table.

| Bug pattern | Where to find the fix |
|---|---|
| "Reimplementing canonical Python in another script" | Don't. Import from `zee_tick_detector_OOS.py` directly. |
| "Multiplying daily_pnl by USD_PER_PRICE before DD check" | Wrong. Original keeps `daily_pnl` in **price units** (per-lot-1). DD_STOP = 100 in price = $1000 USD @ 0.10L. |
| "Editing `mt5/Feb11Tick*.mq5` and asking Zee to F7" | Useless unless you also `cp` to `MetaQuotes/Terminal/<GUID>/MQL5/Experts/`. |
| "Reading `feb11_state_88011.json`'s `session_pnl` for daily P&L" | Misleading. Use `turtle_fills.csv` filtered by today's date prefix. |
| "Assuming broker is GMT+3 like FTMO" | Atmos = GMT+0. State file's `session_date` confirms — resets at 00:00 UTC. |
| "Adding `let` JS variable AFTER it's first referenced" | TDZ ReferenceError, breaks the entire script. Hoist declarations. |
| "Setting `cooldown_sec=86400` to pause EA then forgetting to reset" | Use `apply_runtime.py --reset` to fall back to Inp defaults. |
| "Writing strings with em-dash (—) to PowerShell scripts" | PS 5.1 reads .ps1 as Windows-1252, breaks UTF-8 bytes. Use ASCII `--`. |

## The 8 rules from startup.bat — internalize them

1. APPEND to memory.md, never overwrite.
2. Run memory_hawk.py --loop every session.
3. The only goal is REAL MONEY ON A LIVE EA. Anything else is early halt.
4. Your root-cause analysis is weaker than a human's. Enumerate ≥3 hypotheses; suspect your reimpl first.
5. Never declare validated work "fake/imagined/unreproducible" before running the canonical directly.
6. Every word Zee types is precious. Save verbatim. Use `python monitor/claude_brain.py zee-said "<topic>"` to recall.
7. Daily report at end of each UTC day. Numbered globally. Never delete.
8. This system is a legacy for Zeeshan's children. Document for them. USB pack via `monitor/pack_to_usb.py` (also fires automatically when USB inserted, via `usb_hawk.py`).

## How to recreate this entire setup on a fresh computer

This is the contract Claude must honour: even if Zee's laptop is destroyed,
a new Claude session on a new machine can rebuild everything from this repo
+ the two security questions. Steps:

1. Install prerequisites on the new machine:
   - Git for Windows (includes Bash + openssl + python3 path utilities)
   - Python 3.13 at `C:/Users/<user>/AppData/Local/Programs/Python/Python313-arm64/`
   - Node.js (for the dashboard server)
   - MetaTrader 5 (for the live EA)

2. Clone the repo:
   ```
   git clone https://github.com/zeecitizen/turtle
   cd turtle
   ```

3. Unlock the brain (decrypts every conversation + state):
   ```
   python monitor/brain_unlock.py
   ```
   Answer the two security questions (Jalwana / Kamboh — accepts variants).
   This restores `monitor/.claude_brain.db` + `memory.md` + EA state files.

4. Run `startup.bat` — this auto-spawns:
   - `memory_hawk.py --loop` (hourly journal)
   - `claude_brain.py index --watch` (continuous indexing of new sessions)
   - `brain_lock.py --loop --interval 3600` (encrypt + push every hour)
   - `daily_report_hawk.py --loop` (daily numbered report)
   - `usb_hawk.py` (auto-pack on new USB insertion)
   - Plus the dashboard server, sheriff_hawk, etc.

5. Compile and attach the EA:
   - In MetaEditor, open `mt5/Feb11TickMedium.mq5`, press F7 to compile.
   - **Don't forget the dual-source gotcha**: the file Claude edits is in
     the repo. The file MetaEditor compiles is in
     `C:/Users/<user>/AppData/Roaming/MetaQuotes/Terminal/<GUID>/MQL5/Experts/`.
     Always `cp` repo → terminal folder BEFORE compiling.
   - Attach to XAUUSD M1 chart in the right broker terminal (Atmos GMT+0
     wants session inputs 90/150/1005/1185).

6. Verify state:
   ```
   python monitor/memory_hawk.py        # writes a fresh journal entry
   python monitor/claude_brain.py session-start    # shows recent context
   ```

You should see hourly entries appearing in `memory.md`, encrypted bundles
appearing in `brain_vault/`, and (within 24h) a numbered daily report in
`daily_reports/`.

## Zee should NOT have to manage any of this

Per Zee's 2026-06-04 instruction: Claude self-manages the brain, the USB
backups, the daily reports, the encrypted GitHub pushes. Zee's only role
in the system maintenance is:

- Run `startup.bat` once per laptop reboot (or never if the daemons survive).
- Plug in a USB occasionally for an offline copy (or click the gold button
  on `enter_this_door.html` if he prefers explicit action).
- Read the daily reports.

Everything else is automatic.

## Quick session-start script

```bash
# 1. Skim
cat memory.md | head -100              # latest wall-of-shame + most recent journal
cat OVERNIGHT_RESULT_FOR_ZEE.md        # the EA's design spec
cat CLAUDE_READ_THIS_FIRST.md          # this file (you're reading it now)

# 2. Verify state
python monitor/memory_hawk.py          # writes a fresh journal entry — see today's WR + cumulative
ls Common/Files/turtle_fills.csv       # check broker fills exist
cat Common/Files/feb11_runtime_88011.json   # see if any runtime overrides are active

# 3. If debugging a backtest claim — RUN THE CANONICAL FIRST
python monitor/strategy_lab/zee_tick_detector_OOS.py       # AGGRESSIVE
python monitor/strategy_lab/zee_tick_detector_MEDIUM.py    # MEDIUM
```

If you skip this checklist, you will repeat the 2026-06-03 mistake of telling
Zee that 100k+ of his validated backtest work is "an illusion" when it was
your own bug. Zee was misled for hours. Do not do this to him again.
