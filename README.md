# Shano Trading System

Automated XAUUSD momentum-scalping system codifying my sister Shano's manual trading pattern. She turned $100 → ~$700 by hand on probe-then-main scalps; this repo automates that approach via TradingView Pine + MetaTrader 5 + Python daemons.

> **Status:** live on Blueberry Markets MT5 demo. Real capital ≤ $500 (live not yet enabled).

---

## Architecture

```
TradingView 1-min XAUUSD chart
  └─ Pine indicator detects 2-candle bigness pattern
        └─ shano_hawk.py polls Pine's signal counter every 5s
              └─ fires 0.01-lot probe via PineConnector webhook
                    └─ MT5 broker opens probe
                          └─ ShanoExitManager EA watches
                                ├─ probe profit ≥ $0.75 → fire 0.30-lot main
                                │      (passes filter funnel: trend, UHV, Setup-1, spread, tick-speed, M15 trend)
                                ├─ main exits via TRAIL ($22 trigger / $6 drop) or fearIdeal ($60)
                                │      or main-no-green timeout (60s + peak<$3)
                                └─ probe-trail catches orphaned probes (filter blocked main):
                                       peak ≥ $3 + drop ≥ $1 → bank profit
```

### Core components
| Component | Role | Source |
|---|---|---|
| **Pine indicator** | Detects 2-candle pattern, increments signal counter | [`pine/turtle-shano.pine`](pine/turtle-shano.pine) |
| **Pine — UHV breakout (legacy)** | Detailed UHV/IOE/baseline engine the strategy is built on | [`docs/PINE_INDICATOR_LEGACY.md`](docs/PINE_INDICATOR_LEGACY.md) |
| **shano_hawk** | Reads Pine counter, fires probes via PineConnector | [`monitor/shano_hawk.py`](monitor/shano_hawk.py) |
| **ShanoExitManager EA** | Probe→main lifecycle on MT5; manages all exits | [`mt5/ShanoExitManager.mq5`](mt5/ShanoExitManager.mq5) |
| **Trade notifier** | WhatsApps Shano on every main open/close so she can mirror-trade | [`monitor/shano_trade_notifier.py`](monitor/shano_trade_notifier.py) |
| **Dashboard** | Live UI on `:3457/shano` with live state, history, win-rate widget | [`dashboard/claude_trader/`](dashboard/claude_trader/) |
| **Forward tester** | Real-time intra-candle theory validator | [`monitor/forward_tester.py`](monitor/forward_tester.py) |
| **Sheriff / Patriarch** | Auto-restarts dead daemons; lockfile-based dedup | [`monitor/sheriff_hawk.py`](monitor/sheriff_hawk.py), [`monitor/patriarch.py`](monitor/patriarch.py) |
| **Strategy lab** | Backtest scripts, slippage calibration, R:R sweeps | [`monitor/strategy_lab/`](monitor/strategy_lab/) |

---

## Strategy: probe → main

Shano's pattern is **fire a tiny scout, escalate when it works**. The probe answers "does this 2-candle bigness setup have actual follow-through?" — if it does, the EA escalates to the real position.

1. **Pine fires a signal** when current 1-min candle is ≥1.5× the previous candle's body, in the same direction.
2. **shano_hawk** sends a 0.01-lot probe to MT5 in that direction.
3. EA waits for probe to reach **+$0.75** profit (`probeConfirm`).
4. If probe confirms AND filter funnel passes (trend EMAs aligned on M2, M15 EMA aligned, UHV breakout context, spread within 1.2× baseline, tick-speed under 15s), EA fires a **0.30-lot main**.
5. If probe confirms but filters block main, the **probe-trail** banks $1.50–$7 of probe profit instead of letting the probe orphan.
6. Mains exit via TRAIL (peak − $6 once peak ≥ $22), CDD-divergence early-exit, fearIdeal (-$60 cap), or main-no-green timeout (60s with peak < $3).

### Filter funnel (live)

| Filter | Purpose | Today's pass rate (typical) |
|---|---|---|
| `trend_2min` | EMA-34/89 alignment on M2 | ~50% pass |
| `uhv_breakout` | Trigger close past last UHV bar by 0.30pt | ~55% pass |
| `setup1_hardgate` | UHV pattern in last 3 M1 bars | ~30% pass |
| `spread` | Current spread ≤ 1.2× baseline | ~75% pass |
| `tick_speed` | UHV cross within 15s of probe | ~75% pass |
| `m15_trend` | Price above M15-21EMA (longs) / below (shorts) | ~95% pass |

Filters earn their keep on choppy days — see [STRATEGY_DEEP_DIVE_2026-05-02.md](STRATEGY_DEEP_DIVE_2026-05-02.md).

---

## Performance (rolling)

Live demo, Blueberry Markets, $5K starting balance. Real capital cap is $500 — config will be scaled by 0.10× before going live.

- **Best day:** +$140 (intra-day 8 mains / 6W 2L)
- **Typical day:** +$25–$80
- **Filter-blocked day floor:** ~+$15–$30 from probe-trail income alone
- **Catastrophic stops** capped at $60 per main (fearIdeal) and $15 per burst (burstSlUsd)

Most recent multi-day report: [`MORNING_REPORT_2026-05-06.md`](MORNING_REPORT_2026-05-06.md)

---

## Repository layout

```
turtle/
├── pine/                          Pine indicator (Shano signal source)
├── mt5/
│   ├── ShanoExitManager.mq5       Main EA: probe→main lifecycle + exits
│   ├── ShanoTickLogger.mq5        Tick-level CSV logger for backtests
│   ├── install_eas.ps1            Compile + deploy EAs to MT5
│   └── configs/                   Snapshot configs (.live-snapshot.json = current tuning)
├── monitor/
│   ├── shano_hawk.py              Signal sniper (Pine counter → probe fire)
│   ├── shano_trade_notifier.py    WhatsApp pings on main open/close
│   ├── ensure_daemon.py           Lockfile-based daemon spawner
│   ├── sheriff_hawk.py            Hourly QA + auto-restart
│   ├── patriarch.py               Watches sheriff
│   ├── silver_hawk_learner.py     Visual pattern learner
│   ├── intern_hawks.py            Daily web research
│   ├── meeting_hawks.py           9am+9pm PKT team standup
│   ├── sexy_hawk.py               WhatsApp report secretary
│   ├── forward_tester.py          Intra-candle theory validator
│   ├── shano_status.py            Read live state for dashboard
│   ├── shano_rules.py             Verify EA matches Shano's interview quotes
│   └── strategy_lab/              Backtests, calibration, deep-mines (~200 files)
├── dashboard/claude_trader/
│   ├── server.js                  Node server (:3457)
│   ├── shano.html                 Live trading dashboard (Apple-style)
│   ├── hub.html                   Landing page
│   └── shadow.html                Shadow experiment viewer
├── docs/
│   └── PINE_INDICATOR_LEGACY.md   Detailed UHV/IOE/baseline engine docs
├── startup.bat                    One-shot: launches all daemons + opens dashboard
├── CLAUDE.md                      "Claude go hawking" startup sequence
├── RESUMING.md                    Fresh-machine / VPS bootstrap guide
└── MORNING_REPORT_*.md            End-of-session writeups
```

---

## Setup

For fresh-machine or VPS deployment, see [`RESUMING.md`](RESUMING.md). TL;DR:

```bash
git clone https://github.com/zeecitizen/turtle.git
cd turtle
# Drop monitor/.whatsapp_config.json + monitor/.claude_api_key (gitignored secrets)
# Install Python 3.13 ARM64 + Blueberry Markets MT5 + TradingView Desktop + cloudflared
powershell -File mt5/install_eas.ps1     # compile & deploy EAs
copy mt5\configs\shano_config.live-snapshot.json %APPDATA%\MetaQuotes\Terminal\Common\Files\shano_config.json
startup.bat                              # launches everything
```

Live config knobs (hot-reloadable from `Common\Files\shano_config.json`):
- `probeConfirm: 0.75` — probe profit needed to trigger main attempt
- `fearIdeal: 60` — main catastrophic stop ($)
- `trailTrigger: 22, trailDrop: 6` — main TRAIL params
- `mainNoGreenSec: 60, mainNoGreenPeakMin: 3` — exit stuck mains
- `burstSlUsd: 15` — burst-only tighter catastrophic stop
- `dailyCap: 500` — daily P&L circuit breaker

---

## Author

M. Zeeshan ([@zeecitizen](https://github.com/zeecitizen)) — strategy automation by Claude (Anthropic).
Strategy origin: my sister Shano's manual scalping pattern, captured via interview transcripts.

## License

Proprietary — for personal use only. Trading carries risk of capital loss.
