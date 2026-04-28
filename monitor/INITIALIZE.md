# Turtle Trader Monitor — Startup Guide

## On every computer start / VPS restart:

### Step 1 — Run start_all.bat
```
C:\Users\zeesh\Documents\GitHub\turtle\monitor\start_all.bat
```
This starts: MT5 (Blueberry) + TradingView (with CDP debug port 9222)

### Step 2 — Open Claude Code in this folder
```
cd C:\Users\zeesh\Documents\GitHub\turtle
claude
```

### Step 3 — Say this ONE phrase:
```
initialize monitoring
```

Claude will recreate the 5-minute monitoring cron. That's it.  
You can now minimize the terminal and walk away.

---

## Why "initialize monitoring" is needed after each restart:

The 5-minute cron job lives inside the Claude Code session.  
When Claude exits (computer restart), the cron dies with it.  
Saying "initialize monitoring" takes ~5 seconds to restart.

The cron itself is lightweight — it reads a text log file and calls  
2 TradingView MCP queries. It does NOT change any settings.

---

## What the monitor checks every 5 minutes:

| Check | Source | What triggers a flag |
|---|---|---|
| Signal count | MT5 EA log (MQL5\Logs\YYYYMMDD.log) | No signals for 90+ min during trading hours |
| BE count | MT5 EA log | Informational only |
| SL pips in alerts | MT5 EA log | SL=15 found (iExHSL fix not applied) |
| Sim P&L today | TradingView pine tables | — |
| Consecutive losses | TradingView pine tables | >30 in a row |
| Alert active | TradingView alert_list | 0 alerts = CRITICAL |

---

## Log file locations (text — no screenshot needed):

| What | Path |
|---|---|
| MT5 EA signals | `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Logs\YYYYMMDD.log` |
| MT5 terminal journal | `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\Logs\YYYYMMDD.log` |
| Screenshot (manual) | Run `powershell -File monitor\screenshot.ps1` → C:\tmp\mt5_monitor.png |
| Manual log parse | Run `powershell -File monitor\read_mt5_log.ps1` |

---

## Manual commands (ask Claude anytime):

- `"show me today's MT5 log summary"` — Claude reads and parses the EA log
- `"take a screenshot of MT5"` — Claude runs screenshot.ps1 and reads the image
- `"check the alert"` — Claude calls alert_list
- `"what's our EV today"` — Claude reads pine tables

---

## Alert recreation (after code changes):

After pushing new Pine code (pine_set_source + pine_save), the alert  
inputs update automatically via TradingView's sync.  
Confirmed 2026-04-20: iExHSL changed from 15→10, next signal showed SL=10.0.  
No manual alert recreation needed for settings changes.

If the alert is completely gone (alert_count=0), ask Claude:  
`"recreate the turtle alert"` — Claude will guide you through it.
