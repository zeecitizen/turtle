# CLAUDE_RECOVERY.md

> A bottle-message to future-Claude (or future-Zeeshan with a new Claude)
> who finds this repo years from now and needs to bring it back to life.

If you are reading this in 2036 and the system is dead, **start here**.
This file is the index. Every fact below is reproducible from the code; this
document just explains *which code matters and why*.

---

## 1 · The story (so you understand the why)

In April 2026, Zeeshan's sister **Shano** turned a $100 deposit into ~$700 over
a few weeks scalping XAUUSD on a Blueberry Markets MT5 demo. She had no
indicators, no SL, no plan written down — just a method she'd developed by
feel, watching candle shapes on the 1-minute chart.

We interviewed her over WhatsApp and in-person on **2026-04-25** and
**2026-04-26**. The full transcripts (Urdu Q&A + English glosses) are in:

- [`monitor/interview_shano.md`](monitor/interview_shano.md) — primary source, her actual words
- [`monitor/shano_strategy_complete.md`](monitor/shano_strategy_complete.md) — extracted rules

Read both before changing anything. Her words are the source of truth.

The compressed version of her strategy:

| Step | Trigger | Action |
|------|---------|--------|
| 1 | First big red candle | **WATCH ONLY** — do not trade |
| 2 | Second big red candle (body > 1.25× the prev 2) | Open **0.01 lot probe** SELL |
| 3 | Probe profit > **+$0.58** within ~50s | Open **0.40 lot** main SELL immediately ("FORAN") |
| 3a | Probe loss reaches **−$3** | Skip — momentum dead |
| 4 | Main +$10 (peak), or peak drops by $2 | Close 0.40 first, then 0.01 |
| 5 | After close | Burst can repeat up to 5× while momentum holds |
| 6 | After loss | Cooldown ~8 bars, then look again |

Why probe-then-main? She tried 0.40 cold and got washed out. The 0.01
probe is a cheap (max −$2) test of whether momentum is real. If the probe
turns +$0.58 in under a minute, the move has legs — fire the real size.

She originally only sold (couldn't switch buy/sell context fast enough as a
human). The system enables both directions because AI can.

---

## 2 · System map

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  TradingView    │     │   Pine indicator │     │  PineConnector│
│  Desktop (CDP)  │────►│  turtle-shano    │────►│  webhook      │
│  port 9222      │     │  (1m XAUUSD)     │     │  → MT5        │
└─────────────────┘     └──────────────────┘     └──────┬───────┘
        ▲                                                │
        │ ticks                                          ▼
        │                                       ┌──────────────────┐
┌───────┴────────┐    polls TV     ┌────────────┤ MT5 (Blueberry)  │
│  shano_hawk.py │◄────────────────│  EAs:      │  EA reads        │
│  (sniper       │                 │  Shano     │  shano_config    │
│  daemon)       │ writes signals  │  Exit      │  .json every 5s  │
│                ├────────────────►│  Manager   │                  │
└────────────────┘                 │  +Logger   └──────────────────┘
                                   └────────────┘
```

### Components

| File | Role | Survives restart? |
|------|------|-------------------|
| [`pine/turtle-shano.pine`](pine/turtle-shano.pine) | Pine Script v6 indicator. Detects 1.25× momentum candles, runs the probe→confirm→main state machine, fires PineConnector webhooks. | n/a (chart-side) |
| [`mt5/ShanoExitManager.mq5`](mt5/ShanoExitManager.mq5) | MT5 EA. Manages exits, breakeven, trailing peak-drop, machine-gun bursts, daily cap. **Reads `shano_config.json` every 5s** — no reattach needed for runtime tweaks. | yes |
| [`mt5/TurtleTradeLogger.mq5`](mt5/TurtleTradeLogger.mq5) | MT5 EA. Writes every fill to `Common/Files/turtle_fills.csv`. Source of truth for trade history. | yes |
| [`monitor/shano_hawk.py`](monitor/shano_hawk.py) | Autonomous trader. Polls TV via Node CLI, fires trades via PineConnector, monitors P&L. Has live config too. PID file at `.shano_hawk.pid`. | yes |
| [`monitor/sheriff_hawk.py`](monitor/sheriff_hawk.py) | Hourly QA daemon. Watches the other hawks for liveness, dies and asks for revive on failure. | yes |
| [`monitor/silver_hawk_learner.py`](monitor/silver_hawk_learner.py) | Pattern learner. Screenshots TV, learns visual patterns. Self-rewrites on 3 consecutive failed predictions. | yes |
| [`monitor/intern_hawks.py`](monitor/intern_hawks.py) | Three "interns" that browse the web for trading theories and append findings to `intern_journal/`. | yes |
| [`monitor/sexy_hawk.py`](monitor/sexy_hawk.py) | Secretary daemon. Sends WhatsApp reports to Zeeshan every 2h. | yes |
| [`monitor/meeting_hawks.py`](monitor/meeting_hawks.py) | 9am + 9pm PKT standups. Each hawk presents in character. | yes |
| [`monitor/claude_sniper_daemon.py`](monitor/claude_sniper_daemon.py) | UHV breakout sniper (legacy from the Old-Turtle-Volume-Based era). Still runs, complements Shano. | yes |
| [`dashboard/claude_trader/server.js`](dashboard/claude_trader/server.js) | Node Express dashboard on port 3457. Serves `/shano` UI, `/api/*` endpoints. | yes |
| [`dashboard/claude_trader/shano.html`](dashboard/claude_trader/shano.html) | Single-page Shano dashboard. Mechanical odometer P&L, stage indicator, win rates, rule-compliance gauge. | n/a |
| [`monitor/ensure_daemon.py`](monitor/ensure_daemon.py) | Idempotent process launcher used by `startup.bat`. Detects already-running daemons by cmdline match; spawns with `CREATE_NO_WINDOW \| CREATE_NEW_PROCESS_GROUP` so children don't flash console windows. | n/a (launcher) |
| [`startup.bat`](startup.bat) | Top-level launcher. **Idempotent and resilient** — re-runnable any time. | n/a |

### Live config that the EA hot-reads every 5s

`%APPDATA%\MetaQuotes\Terminal\Common\Files\shano_config.json`

```json
{
  "probeConfirm": 0.58,   "probeFail": 3.0,    "probeLots": 0.01,
  "probeTimeout": 50,     "trailTrigger": 8.0, "trailDrop": 2.0,
  "holdLotMax": 0.1,      "fearIdeal": 70.0,   "fearWashout": 180.0,
  "maxBurst": 5,          "burstCooldown": 0,  "maxPositions": 3,
  "dailyCap": 500.0,      "sellOnly": false
}
```

Edit this file → the EA picks it up within 5 seconds. **No reattach.** This
was a hard-won feature; respect it.

---

## 3 · How to wake the system up (cold start)

Prereqs (verify first if anything fails):

- Windows 11 with PowerShell 5.1+
- Python 3.13 ARM64 at `C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe` (or update the path in `monitor/ensure_daemon.py` and `startup.bat`)
- Node.js at `C:\Program Files\nodejs\node.exe`
- TradingView Desktop installed
- Blueberry Markets MT5 at `C:\Program Files\Blueberry Markets MetaTrader 5\terminal64.exe` (or another broker — update path in `startup.bat`)
- `pip install psutil anthropic requests`
- Repo cloned to `C:\Users\zeesh\Documents\GitHub\turtle\` (or update paths)

**Secrets that are NOT in this repo (gitignored). Recreate them:**

| Path | Format | Purpose |
|------|--------|---------|
| `monitor/.claude_api_key` | single line: `sk-ant-api03-...` | Claude API key for the AI hawks |
| `monitor/.whatsapp_config.json` | `{"provider":"greenapi","instance_id":"...","api_token":"...","api_host":"https://NNNN.api.greenapi.com","chat_id":"...@c.us"}` | WhatsApp via GreenAPI |
| `.mcp.json` | MCP server config — see project docs | TradingView MCP integration |

Once those exist:

```cmd
startup.bat
```

That's the whole startup. The bat is **idempotent** — re-running it never
crashes anything that's already up. Each step is independent; failures log
`[WARN]` and the script continues.

After it finishes, verify with the Sheriff:

```cmd
python monitor\sheriff_hawk.py
```

All components should report ALIVE.

### MT5 manual step (one-time)

`startup.bat` calls `mt5/install_eas.ps1` which copies + compiles the EAs
into every MT5 terminal it finds. But **attaching** them to charts requires
a GUI step:

1. In MT5: Ctrl+N → Navigator → right-click "Expert Advisors" → Refresh
2. Drag `TurtleTradeLogger` onto any XAUUSD chart
3. Drag `ShanoExitManager` onto a separate XAUUSD 1-min chart
4. In the input dialog: verify `InpSymbolFilter = XAUUSD`, click OK
5. Enable AutoTrading (the green button in the toolbar)

The EA writes `shano_live.json` every second and reads `shano_config.json`
every 5s.

### Claude trader cron (one-time per session)

`crons/jobs/claude_trader.md` contains the prompt. Register it via the
Claude Code CLI or whatever cron mechanism exists at the time:

```
CronCreate(cron="* * * * *", recurring=true, durable=true, prompt=<contents of claude_trader.md>)
```

---

## 4 · Maintenance runbook

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Dashboard at `:3457` not responding | Node server died | `startup.bat` (idempotent — only respawns dead daemons) |
| `shano_hawk` shows stale state | Daemon died | `python monitor\ensure_daemon.py shano_hawk.py` |
| EA not picking up config changes | mtime stuck or EA detached | Verify EA face is on chart with smiley, then check `Common\Files\shano_config.json` is being written |
| CMD windows flashing every few seconds | Daemon spawned without `CREATE_NO_WINDOW` | Restart daemon via `ensure_daemon.py` (the helper sets it correctly) |
| `direction=sell_only` sticks even after edit | Daemon has stale state in memory; file is being overwritten by daemon's `save_state` | Stop daemon, edit `monitor/.shano_state.json`, restart |
| Sydney session 0% win rate | Sydney session known dead zone | Verify `mTS=25` and `sFilt=true` on the (legacy UHV) Pine indicator. Shano EA's `holdLotMax` and timing filters serve same purpose for Shano flow. |
| Spread phantom profit | Old hawk used `last_price` for both sides | Verify hawk uses `bid` for sell entry, `ask` for buy entry (see CLAUDE.md spread bug section) |
| EA reattach asked for | Pre-2026-04-28: every input change needed reattach. Post: no, EA hot-reads `shano_config.json`. | If the doc you're reading still says "reattach to apply", the live-config is broken — investigate `LoadRuntimeConfig()` in the EA |

---

## 5 · Critical settings (do not change without testing)

These were derived from real money / real losses. Each one has a story.

| Setting | Value | Why |
|---------|-------|-----|
| Probe lot | 0.01 | Max −$2 if probe fails (Shano's threshold) |
| Probe confirm | +$0.58 | Empirical: above this, momentum has > 70% follow-through |
| Probe fail | −$3.00 | Shano: "minus 3 loss tak janay deti hun" |
| Main lot | 0.40 | Standard size when capital ≥ $500 |
| TP | $10 (trailing peak−$2) | Shano: "$8 to $12+, not fixed" — trail captures the range |
| Daily cap | $500 | Shano: "500 USD hojaey profit khatam kar do" |
| Max burst | 5 | "unusual cases mein 5 tak bhi gayi hun" |
| Skip reopen | 20 min | "first 20 minutes after market open Monday absolutely no trade" |
| Stop before close | 60 min | Avoid Friday-close chop |
| Sell-only | false (was true) | Shano can't switch buy/sell fast; AI can. Enabled both 2026-04-28. |
| Pullback reds required | 2 | Shano: "doosri red candle pe 0.01 lot" |

The legacy UHV settings (`mTS=25`, `sFilt=true`, TP=52 pips, SL=15 pips,
0.40 lots) belong to the OLD-TURTLE-VOLUME-BASED system. They are
preserved on the `Old-Turtle-Volume-Based` branch.

---

## 6 · Known failure modes (read these before debugging)

1. **`spread_hallucination`** — hawk P&L MUST use bid/ask, not chart price. Phantom $14 profit per trade if you confuse them.
2. **`restart_refire`** — sniper reads `.last_uhv_id` on startup to avoid duplicate trades. Don't delete this file unless you know why.
3. **`sydney_session`** — 0% WR in Sydney empirically. Filters are mandatory.
4. **`stale_breakout`** — don't fire when price is already 2+ points past the trigger.
5. **`false_breakout_filter`** — candle-close confirmation required before firing in some flows.
6. **TV CSV dropdowns inaccurate** — TV's settings export CSV does not list dropdown/select inputs correctly. Cross-reference with `settings-latest.md`.
7. **TV OOM crash** — heavy MCP polling crashes TV Desktop. Limit to 1–2 calls per cycle. Recovery: reload TV via `ui_evaluate`, reapply `mTS+sFilt` (legacy) or reattach Shano EA.
8. **Modern Standby disconnects WiFi** — when display sleeps, S0 Low Power Idle drops the network even though `sleep=Never`. Workarounds: display=Never on AC, disable WiFi adapter power management, or registry-disable Modern Standby.
9. **PowerShell permission prompts** — prefer Python over PowerShell in automation; PS triggers permission prompts the user can't pre-grant.

---

## 7 · How the dashboard's "rule compliance" gate works

[`monitor/shano_rules.py`](monitor/shano_rules.py) reads:
- `pine/turtle-shano.pine` (source defaults)
- `monitor/.tv_indicator_snapshot.json` (live chart-override values)
- `mt5/ShanoExitManager.mq5` (EA defaults)
- `monitor/shano_config.json` mirror

…then asserts each rule against Shano's actual interview-stated values.
Any drift surfaces on the dashboard at `/shano` under "Shano Rule Compliance".

If a rule starts failing because *Shano's strategy itself evolved* (e.g.,
the sell-only flip on 2026-04-28), update `shano_rules.py` to match the new
truth. Don't silence the check — fix the source of truth.

---

## 8 · Branch model

- **`main`** — current Shano trading system, post-2026-04-28
- **`Old-Turtle-Volume-Based`** — legacy UHV breakout system (sessions 44–48). Preserved as-is so future readers can still learn from / revive it.
- Other branches (`Code-with-FVGs`, `with-all-3-strategies`) — historical experiments

The legacy commits are still in `main`'s history (gentle split — no force
push). The `Old-Turtle-Volume-Based` branch is the named pointer for
discoverability.

---

## 9 · If the strategy stops working

The market changes. If after a year the Shano strategy stops earning,
the right move is **not** to tweak parameters. The right move is to:

1. Re-interview Shano (or whoever the new domain expert is)
2. Compare her current method to `monitor/interview_shano.md`
3. Codify the deltas as new rules in `shano_rules.py`
4. Update `monitor/shano_strategy_complete.md` to the new truth
5. Add the date and the source quote inline so the next Claude knows when and why

The process matters more than any specific parameter.

---

## 10 · Contacts (as of 2026-04-28)

- **Zeeshan**: `4915119175329@c.us` (WhatsApp) — system owner
- **Shano**: `923364863368@c.us` — strategy source, lives in Pakistan, trades XAUUSD
- **Anthropic**: Claude API key in `monitor/.claude_api_key`

If contacts are stale, don't try to message strangers — find Zeeshan via
GitHub (`zeecitizen`) or rebuild trust before reaching out to Shano.

---

*Written 2026-04-28 by Claude Opus 4.7 working with Zeeshan, on the day we
flipped the system from sell-only to both-sides because the AI can switch
context faster than a human can.*
