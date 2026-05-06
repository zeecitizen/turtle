# Resuming the Shano Trading System

Read this first if you're a fresh Claude session OR setting up on a new machine / VPS.

## What this repo is
Live momentum-scalping XAUUSD on Blueberry Markets MT5 demo, codifying Shano's manual trading pattern. Architecture:

```
TradingView Pine indicator (1-min chart)
    -> shano_hawk.py polls signal counter every 5s
    -> fires 0.01-lot probe via PineConnector webhook
    -> ShanoExitManager EA on MT5 manages probe-to-main lifecycle
    -> probe-trail or main-fire, exits via TRAIL/CDD_DIV/FEAR_IDEAL/etc.
```

## Where to start (in conversation)
1. Read [CLAUDE.md](CLAUDE.md) — the "Claude go hawking" startup sequence
2. Read [MORNING_REPORT_2026-05-06.md](MORNING_REPORT_2026-05-06.md) — most recent system state + reasoning behind current tuning
3. Skim [STRATEGY_DEEP_DIVE_2026-05-02.md](STRATEGY_DEEP_DIVE_2026-05-02.md) — strategy bible

## Live tuning (committed snapshot)
The exact running config is at [mt5/configs/shano_config.live-snapshot.json](mt5/configs/shano_config.live-snapshot.json). Key knobs:
- `probeConfirm: 0.75` — minimum probe profit to allow main fire
- `fearIdeal: 60` — main catastrophic stop ($)
- `trailTrigger: 22, trailDrop: 6` — main TRAIL params (deployed 2026-05-05, validated overnight)
- `mainNoGreenSec: 60, mainNoGreenPeakMin: 3` — exits stuck mains
- `burstSlUsd: 15` — burst-only tighter stop

## Files NOT in repo (must recreate locally)
| Path | Purpose | How to get |
|---|---|---|
| `monitor/.claude_api_key` | Anthropic API key | from Zee's vault / claude.ai |
| `monitor/.whatsapp_config.json` | GreenAPI token + WhatsApp instance | from Zee's vault / GreenAPI dashboard |
| `mt5/ShanoExitManager.ex5` | Compiled EA binary | rebuild via `mt5/install_eas.ps1` |
| MT5 platform install | Blueberry Markets MT5 | download, login with broker creds |

`.whatsapp_config.json` shape:
```json
{
  "provider": "greenapi",
  "instance_id": "<id>",
  "api_token": "<token>",
  "api_host": "https://7107.api.greenapi.com",
  "chat_id": "923364863368@c.us"
}
```

## Fresh-machine setup (VPS or new laptop)

### 1. Install dependencies
- Python 3.13 ARM64 at `C:\Users\zeesh\AppData\Local\Programs\Python\Python313-arm64\python.exe` (or update `PY` in `monitor/ensure_daemon.py`)
- `pip install psutil requests` (no other deps needed; system uses stdlib `urllib.request` for HTTP)
- Blueberry Markets MT5 Desktop at `C:\Program Files\Blueberry Markets MetaTrader 5\`
- TradingView Desktop with Chrome DevTools Protocol enabled (port 9222)
- Cloudflared (for public dashboard tunnel) at `C:\Tools\cloudflared.exe`

### 2. Clone + populate secrets
```
git clone https://github.com/zeecitizen/turtle.git
cd turtle
# Place .claude_api_key and .whatsapp_config.json into monitor/
# (both gitignored, get from secure vault)
```

### 3. Compile the EA
```
powershell -File mt5/install_eas.ps1
# Creates ShanoExitManager.ex5 and copies to MT5 Experts dir
```

### 4. Apply live config snapshot to MT5
```
copy mt5\configs\shano_config.live-snapshot.json ^
     %APPDATA%\MetaQuotes\Terminal\Common\Files\shano_config.json
```

### 5. Manual MT5 setup (one-time)
- Login to broker
- Open XAUUSD M1 chart
- Drag `ShanoExitManager` EA onto chart, enable algo trading
- Drag `ShanoTickLogger` EA (logs ticks for backtesting)
- Drag `TurtleTradeLogger` EA (writes turtle_fills.csv)
- Set up TradingView with Pine indicator on XAUUSD 1-min chart
- Set up PineConnector webhook with the broker's bridge

### 6. Launch the system
```
startup.bat
```
This launches: dashboard (:3457), shano_hawk, sheriff_hawk, silver_hawk, sexy_hawk, meeting_hawks, intern_hawks, vscode_watchdog, forward_tester, **shano_trade_notifier**, patriarch.

### 7. Verify
- Dashboard at `http://localhost:3457/shano` should load
- `monitor/shano_hawk.log` should show heartbeats every 60s
- `Common/Files/shano_live.json` should update every 1s

## Daemons + responsibilities

| Daemon | Purpose | Restart freq |
|---|---|---|
| `shano_hawk.py` | Polls TV's Pine signal counter, fires probes | always alive |
| `shano_trade_notifier.py` | WhatsApps Shano on every main open/close | always alive |
| `forward_tester.py` | Real-time intra-candle theory validator | always alive |
| `sheriff_hawk.py --loop` | Hourly QA, auto-restarts dead daemons | always alive |
| `silver_hawk_learner.py` | Visual pattern learner (15-min cadence) | always alive |
| `intern_hawks.py` | Daily web-research interns | daily |
| `meeting_hawks.py --loop` | 9am+9pm PKT team meetings | always alive |
| `sexy_hawk.py --loop` | WhatsApp report secretary (2h cadence) | always alive |
| `vscode_watchdog.py` | Relaunches VS Code if it dies | always alive |
| `patriarch.py` | Watches sheriff (revives if dead) | always alive |

All managed via `monitor/ensure_daemon.py <script>` — uses lockfiles at `monitor/.<script>.lock` to prevent dupes.

## Critical files (live state, NOT in repo)
- `Common\Files\shano_live.json` — EA's live state (positions, balance, history). Updates every 1s.
- `Common\Files\shano_config.json` — EA's hot-reloadable config. Edit anytime.
- `Common\Files\turtle_fills.csv` — every fill written by TurtleTradeLogger
- `Common\Files\shano_open_log.csv` — rich per-main open log (latency, slip, intended/actual)
- `Common\Files\shano_ticks_YYYY-MM-DD.csv` — tick stream from ShanoTickLogger (~10MB/day)

## Strategy lab
[`monitor/strategy_lab/`](monitor/strategy_lab/) — 198 backtest scripts, results, reports. Most recent / important:
- `filter_relaxation_backtest.py` — sweeps filter loosening candidates
- `cousin_strategy_backtest.py` — tests an external strategy
- `main_exit_rr_backtest.py` — proved the trail 22/6 deployment
- `pdf5_quick_compare.py` — runs latest calibrated backtest
- `slip_calibrator.py` + `build_slip_calibration.py` — empirical slippage model from production fills

## Public dashboard tunnel
Cloudflared quick-tunnel on port 3457 — URL changes each restart, sent to Zee + Shano via WhatsApp.

## Commit protocol
This repo is the source of truth for resumption. Commit at the end of each major session. Never commit secrets — `.gitignore` covers credentials, runtime state, lockfiles, build artifacts.
