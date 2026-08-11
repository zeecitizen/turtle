# Turtle Trader Desk — Feature Documentation

**Pine Script v5 | TradingView 1m Chart | PineConnector → MT5 Automation**
**Symbol: XAUUSD (Gold) | Strategy: UHV Breakout | Author: M. Zeeshan**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Feature Summary](#2-feature-summary)
3. [Ultra High Volume Candle (UHVC) Detection](#3-ultra-high-volume-candle-uhvc-detection)
4. [Retracement Validation Engine](#4-retracement-validation-engine)
5. [Breakout Confirmation Module](#5-breakout-confirmation-module)
6. [Tick-Velocity Filter (Participation Density Gate)](#6-tick-velocity-filter-participation-density-gate)
7. [Dynamic Baseline Engine](#7-dynamic-baseline-engine)
8. [Real-Time Execution Logic (IOE-Safe)](#8-real-time-execution-logic-ioe-safe)
9. [Risk Management Layer](#9-risk-management-layer)
10. [Breakeven & Trailing System](#10-breakeven--trailing-system)
11. [Invalidation Exit Engine](#11-invalidation-exit-engine)
12. [Session-Aware Behavior Controls](#12-session-aware-behavior-controls)
13. [PineConnector Automation](#13-pineconnector-automation)
14. [Stats Panel & Optimizer](#14-stats-panel--optimizer)
15. [Parameter Sensitivity Framework](#15-parameter-sensitivity-framework)
16. [Recommended Defaults (XAUUSD, 1m)](#16-recommended-defaults-xauusd-1m)
17. [Settings Export & Restore](#17-settings-export--restore)
18. [Alert Condition Bitmask](#18-alert-condition-bitmask)

---

## 1. Overview

Turtle Trader Desk implements a single institutional-grade trading strategy: the **Ultra High Volume Breakout (UHV)**. The system detects candles exhibiting abnormal volume (institutional footprints), waits for a retracement, then enters on confirmed breakout of that retracement structure.

Signals fire via `alert()` → TradingView webhook → PineConnector EA → MetaTrader 5 broker.

**Pipeline:**
```
TradingView 1m chart
  → Pine Script detects UHV setup
  → Breakout confirmed (IOE or bar-close)
  → alert() fires webhook
  → PineConnector receives signal
  → MT5 places order with SL/TP/BE/Trail
  → Pine monitors trade (invalidation, BE, hard SL simulation)
  → closelong / closeshort sent on exit
```

**Live configuration (as of Session 31, 2026-04-01):**
- Broker: Exness / Blueberry Markets, MT5, demo → live
- Symbol: XAUUSD
- PineConnector License: `8778286989525`
- Timeframe: 1m chart

---

## 2. Feature Summary

| Module | Status | Purpose |
|---|---|---|
| UHVC Detection | Active | Identify institutional-level volume candles |
| Retracement Validation | Active | Confirm controlled pullback into UHVC range |
| Breakout Confirmation | Active | Detect breakout from retracement structure |
| Tick-Velocity Filter | Optional (OFF by default) | Participation density gate — filters lazy drift |
| Dynamic Baseline Engine | Active | Adaptive velocity / volume normalisation |
| IOE Execution | Active | Mid-candle real-time entry |
| Invalidation Exit | Active | Close trade when bar closes back inside UHVC range |
| Hard SL Simulation | Active | Pine mirrors MT5 hard SL for accurate P&L stats |
| Breakeven System | Active | Move SL to protect profit at configurable trigger % |
| Trailing Stop | Active (via PineConnector) | Ride runners beyond fixed TP |
| Session Windows | Optional | Block signals during low-liquidity UTC periods |
| Stats Panel | Active | 16-row live dashboard: P&L, EV, streaks, optimizer |
| PineConnector Bridge | Active | Full signal + close command automation to MT5 |

---

## 3. Ultra High Volume Candle (UHVC) Detection

### Purpose
Identify candles exhibiting institutional-level activity, forming the foundation of the VSA-based continuation model.

### Behavior
- Scans each candle's volume against a rolling baseline of the retracement window.
- Selects the highest-volume candle within the current retracement as the UHVC.
- Optionally requires the UHVC to rank in the top N-th percentile of the last `uVLB` bars (configurable via `UHV Detection: Require percentile rank`).
- Marks the UHVC high and low as the breakout reference levels.
- Stores UHVC bar index and volume for downstream filters.

### Key Inputs
| Input | Default | Description |
|---|---|---|
| `UHV Detection: Require percentile rank` | OFF | Require UHVC to be top-N% volume vs lookback |
| `Min volume percentile threshold` | 95 | Percentile floor when rank mode is ON |
| `Lookback bars for percentile` | 20 | Rolling window for percentile calculation |

### Notes
The UHVC is re-evaluated on every bar during the retracement phase. If a higher-volume candle appears, it replaces the previous UHVC candidate. Only the final candidate at breakout time is used.

---

## 4. Retracement Validation Engine

### Purpose
Confirm that price retraces into the UHVC range in a controlled manner before breakout entry is armed.

### Behavior
- Monitors for a retracement phase following the UHVC candle.
- Two modes:
  - **Standard**: requires IB (Institutional Buildup) phase — trend confirmation, then retracement into structure.
  - **Bypass mode** (`bRW = true`): retracement starts whenever a red candle closes below the prior green candle's low. Removes trend/IB phase requirements.
- Wick trigger (`bRWW = true`): a wick piercing below the prior green low is sufficient (no close required).
- Validates that retracement does not fully invalidate the UHVC structure.

### Key Inputs
| Input | Default | Description |
|---|---|---|
| `Bypass retracement rules` | ON | Simplified retracement detection |
| `Wick trigger` | ON | Wick pierce sufficient (no close required) |
| `POI Lookback (bars)` | 50 | Bars to search for Points of Interest |

### Notes
Bypass + Wick mode maximises signal frequency on XAUUSD 1m. Standard mode adds structure requirements but significantly reduces signal count.

---

## 5. Breakout Confirmation Module

### Purpose
Detect breakouts from validated retracement structures and trigger entry logic.

### Behavior
- Monitors price relative to `_bL` (breakout level = UHVC high for bull, UHVC low for bear).
- Supports pre-breakout offset (`uPBsD`): signal fires N dollars before the breakout level for better fill.
- `uPBCo` (Co-exist): if price breaks through without reaching the pre-offset level, fires at actual breakout price instead of missing the trade.
- Body breakout mode (`uBrkBody`): in IOE mode, requires candle body (close) to cross the trigger, not just a wick.
- Cooldown (`uCd`): minimum bars between consecutive signals.

### Key Inputs
| Input | Default | Description |
|---|---|---|
| `Pre-breakout offset ($)` | 5 | Fire signal $5 before breakout level (better fill) |
| `Post-breakout offset ($)` | 0 | Wait for price to move past breakout before entry |
| `Also allow signal at actual breakout level` | ON | Co-exist fallback if pre-offset level not reached |
| `Require body breakout` | ON | Close must cross trigger (IOE mode only) |
| `Cooldown: bars after signal` | 0 | Minimum bars between signals |
| `Alert Gate ($)` | -0.05 | Min gap from price to TP before alert fires |

### Notes
Breakout detection is event-driven and optimised for low latency. IOE mode evaluates on every tick; bar-close mode only evaluates on confirmed candle close (`barstate.isconfirmed`).

---

## 6. Tick-Velocity Filter (Participation Density Gate)

### Purpose
Ensure breakout candles exhibit above-normal market participation, filtering out lazy drift breakouts and keeping only institutional-pressure moves.

### Concept
Tick-velocity measures **ticks per unit of price movement** — the density of market activity:

```
velocity = tickVolume / max(high - low, syminfo.mintick)
```

- **High velocity** → many ticks concentrated in a small range → strong participation → institutional pressure
- **Low velocity** → few ticks across a wide range → weak participation → thin or drift breakout

This aligns with VSA's *effort vs result* principle.

### Behavior
- Computes `_tvVel = volume / max(high - low, mintick)` on the breakout candle.
- Computes `_tvBase = ta.sma(_tvVel, uTVN)` as the dynamic baseline.
- Gate condition: `_tvVel > uTVK * _tvBase`
- **IOE protection**: in Instant at Breakout mode, velocity is evaluated on the **previous completed bar** to avoid partial-candle noise. Current bar volume and range are still accumulating mid-candle — using them would produce unreliable readings.
- Applied to both bull (`_bBrk`) and bear (`_beBrk`) signal conditions.
- Default OFF — zero impact on existing behavior until enabled.

### Key Inputs
| Input | Default | Description |
|---|---|---|
| `Tick Velocity Filter` | OFF | Enable/disable participation density gate |
| `Velocity multiplier threshold (k)` | 1.2 | Must exceed k× baseline; 1.2 preserves most signals |
| `Velocity baseline lookback (N)` | 20 | SMA window for average participation density |

### Recommended Settings
| Parameter | Value | Notes |
|---|---|---|
| k (multiplier) | 1.2 | Best starting point — preserves signals, improves quality |
| N (baseline) | 20 | Stable across London/NY/Asia sessions |
| Mode | IOE-safe (prev bar) | Avoids partial-candle noise on 1m IOE execution |

### Expected Impact
Any filter reduces signals. Empirical testing on this system showed:
- Momentum body filter (40%): signals reduced from 88/day → 34/day, daily EV $1085 → $290
- Velocity filter at k=1.2 is expected to have a smaller impact than body size filters

**Validation plan before enabling in production:**
1. Baseline: run 1 session with filter OFF, record EV and signal count
2. Filter ON at k=1.2: compare win rate, avg win, avg loss, daily signal count
3. Sweep k = 1.1, 1.2, 1.3, 1.4 across London + NY sessions
4. Decision criterion: filter is beneficial only if `EV_filter × signals_filter > EV_base × signals_base`

### Notes
This filter is a **participation confirmation layer**, not a momentum filter. It does not measure the size of the move — it measures the density of activity behind the move. A large candle with low tick density may be a thin liquidity spike; a smaller candle with high tick density indicates real institutional participation.

---

## 7. Dynamic Baseline Engine

### Purpose
Adapt velocity and volume expectations to current market conditions, ensuring the EA remains robust across sessions and volatility regimes.

### Behavior
- Maintains rolling SMA of tick-velocity over the last N bars (`uTVN`).
- Baseline updates on every bar, automatically adjusting for London open spikes, NY session volume, and Asian quiet periods.
- The same SMA approach is used for UHV volume baseline in percentile mode.

### Notes
Session-relative baselines prevent false triggers during quiet markets and avoid over-filtering during high-activity periods. The N=20 default is stable across all major gold sessions.

---

## 8. Real-Time Execution Logic (IOE-Safe)

### Purpose
Ensure all filters and signals operate correctly in mid-candle execution environments.

### Behavior
- **IOE mode** (`uOE = "Instant at Breakout"`): signal fires on the tick when price crosses the breakout level, without waiting for bar close.
- All filters that use current-bar data (`volume`, `high`, `low`, `close`) have IOE-safe variants that use `[1]` (previous confirmed bar) to avoid partial-candle noise.
- `barstate.isconfirmed` guard in bar-close mode prevents double-firing on the same candle.
- `varip` variables track IOE-specific state that must persist across ticks within the same bar.

### IOE vs Bar-Close Comparison
| Dimension | Instant at Breakout (IOE) | Candle Close |
|---|---|---|
| Entry timing | Mid-bar tick | On bar close |
| Fill quality | Better (earlier) | Standard |
| False breakout risk | Higher | Lower |
| Velocity filter | Uses previous bar | Uses current bar |
| Body breakout check | Close > trigger on current tick | Bar close > trigger |

### Notes
IOE mode is recommended for XAUUSD 1m. Gold moves rapidly and waiting for bar close can result in entries $3–$8 worse than the breakout level.

---

## 9. Risk Management Layer

### Purpose
Provide multi-layered position protection with a clear separation between Pine-side logical risk and broker-side disaster protection.

### Architecture

```
Entry
  │
  ├─ Pine Logical SL (Breakout Wick mode)
  │    Calculated from breakout candle wick + offset
  │    Used for lot sizing and Pine P&L simulation
  │
  ├─ Invalidation Exit (primary exit)
  │    Fires when 1m bar CLOSES back inside UHVC range
  │    Sends closelong / closeshort to MT5 via PineConnector
  │
  ├─ Hard SL Simulation (Pine mirrors MT5)
  │    Pine checks if price hits entry ± iExHSL × pPip
  │    Records as loss in stats (🔴 Hard SL label)
  │    Keeps Pine stats aligned with MT5 reality
  │
  └─ Broker Hard SL (MT5 disaster backstop)
       iExHSL pips wide — only fires if:
       - Connection fails and Pine cannot send closelong
       - Price spikes > iExHSL pips in < 1 bar (flash event)
```

### Components

**Logical Stop-Loss (Pine-side)**
- Method: `Breakout Wick` — SL placed below the breakout candle's wick
- Offset: `uSBf = 0.7` ($0.70 below the wick)
- Minimum: `uSMn = 0.2` (SL can never be closer than $0.20 to entry)
- Used for lot sizing: `lots = dollar_risk / (SL_distance × contract_size)`

**Broker Hard SL (MT5-side)**
- `iExHSL = 50` pips → ~$5.00 per pip × lots
- At 0.04 lots: max disaster loss ≈ $20
- Sent as `sl_pips=50` in PineConnector alert string
- Not used for lot sizing — purely disaster protection

**Hard SL Simulation (Pine-side)**
- Added Session 31 to close the Pine vs MT5 stats gap
- Activates only when `useInvalidation = true`
- Formula: `_hardSLPrice = entry ± iExHSL × pPip`
- If `low <= _hardSLPrice` (bull) or `high >= _hardSLPrice` (bear): marks trade as closed, records P&L, appends 🔴 Hard SL label

### Key Inputs
| Input | Default | Description |
|---|---|---|
| `Stop Loss: Offset from SL level` | 0.7 | Buffer below breakout wick |
| `Stop Loss: Closest it can ever be ($)` | 0.2 | Hard floor on SL distance |
| `Invalidation Exit: Hard SL sent to MT5 (pips)` | 50 | Disaster backstop width |
| `Risk: % of capital per trade` | 1 | Lot sizing method (active when $Risk = 0) |
| `Risk: Fixed lot size` | 0.011 | Fixed fallback when both % and $ = 0 |

### Notes
The decoupling of Pine logical SL from broker hard SL is critical. Using the same value for both would eliminate the invalidation exit's role and result in either over-tight disaster SLs (MT5 stops trades that Pine would have managed) or over-wide logical SLs (poor R:R).

---

## 10. Breakeven & Trailing System

### Purpose
Protect profits on winning trades while allowing runners to extend to maximum capture.

### Breakeven Behavior
- Trigger: when price reaches `uBEPct`% of the TP distance from entry
- With `uBELkTP = false` (current default): SL moves to `entry + spread` (~$0.13 profit lock)
- With `uBELkTP = true`: SL moves to exact trigger price (locks in uBEPct% of TP)
- Once BE fires: invalidation exit is disabled (trade is protected, no need for early exit)

**Current setting rationale (uBELkTP = false):**
At 10R TP (e.g. 161 pips), BE at 10% = 16 pips. Gold breathes 15–20 pips continuously. Locking SL at +16 pips means any normal retracement stops out the trade before the trail can activate. Setting Lock OFF moves SL to entry+spread only — the trade is risk-free but the trail handles the real profit lock.

### Trailing Stop Behavior (MT5 via PineConnector)
| Phase | What happens |
|---|---|
| Entry → +10% TP | SL at entry+spread (BE zone), no trailing |
| +100 pips profit | PineConnector activates trailing stop |
| Trailing active | SL = current price − 40 pips, moves every 10 pips gained |
| Market reverses 40 pips from peak | Trade exits at trail SL |
| TP ceiling (10R) reached | Trade exits at TP |

### Key Inputs
| Input | Default | Description |
|---|---|---|
| `Breakeven: move SL to entry+spread` | ON | Enable BE system |
| `Breakeven trigger: % of TP distance` | 10 | BE fires at 10% of TP distance from entry |
| `Lock SL at BE trigger price` | OFF | Move to entry+spread only (not locked at trigger) |
| `Trailing stop distance (pips)` | 40 | SL trails price by 40 pips |
| `Trailing: activate after X pips profit` | 100 | Trail only starts once confirmed runner |
| `Trailing: move SL every X pips gained` | 10 | Step size for trail advancement |

---

## 11. Invalidation Exit Engine

### Purpose
Close losing trades early when the breakout fails — before the Pine logical SL or broker hard SL is reached.

### Behavior
- On every bar close: checks if the close price re-enters the UHVC range.
- Invalidation condition (bull): `close < _iLvl - iExOff` where `_iLvl = UHVC high`
- Tolerance `iExOff = 0.3`: close must be $0.30 past the level to trigger (avoids false exits on shaved levels)
- On invalidation: sets `_tSH[i] = true`, sends `closelong` or `closeshort` via `alert()`
- Label updated: ⚡ for loss, ✅ for profit
- **Post-BE deactivation**: once `_tBE[i] = true`, invalidation is permanently disabled for that trade

### Key Inputs
| Input | Default | Description |
|---|---|---|
| `Invalidation Exit` | ON | Enable engine |
| `Invalidation Exit: Hard SL sent to MT5 (pips)` | 50 | Broker disaster backstop |
| `Invalidation Exit: Tolerance ($)` | 0.3 | Buffer to avoid noise exits |

### Notes
Invalidation fires at **bar close**, not on tick. This prevents exit on intrabar wicks that briefly re-enter the UHVC range before recovering. The tolerance of $0.30 adds a second layer of noise protection. Typical invalidation loss: $3–$5.

---

## 12. Session-Aware Behavior Controls

### Purpose
Prevent entries during low-liquidity UTC periods where spread cost exceeds potential TP or fakeout rates spike.

### No-Trade Windows
| Window | UTC Hours | Reason |
|---|---|---|
| ntW1 | 21:00–23:00 | NY Rollover — spreads spike 5–10× |
| ntW2 | 23:00–03:00 | Late Asia lull — slow drift, high fakeout risk |
| ntW3 | 04:00–07:00 | Pre-London trap — thin liquidity |
| ntW4 | 19:00–21:00 | Volume fade / Friday profit-taking |

All OFF by default. London (08:00–12:00) and NY (13:00–17:00) sessions are unaffected.

### Trend Filters
| Input | Default | Description |
|---|---|---|
| `Min Trend Strength at Signal` | 3 | Minimum trend strength score (0–5 scale) |
| `Trend Persistence Lookback (bars)` | 8 | Bars to evaluate trend consistency |
| `Avoid trading when trend is shifting` | OFF | Block signals during trend transitions |
| `Shift Threshold` | 53 | Strength drop % to classify as shifting |
| `Require structural trend` | OFF | HH+HL for buys, LH+LL for sells |
| `Avoid signals during ranging market (ADX)` | OFF | ADX-based ranging filter |

---

## 13. PineConnector Automation

### Signal Format
```
{licenseID},buy,XAUUSD,vol_lots={lots},sl_pips=50,tp_pips={tp},
spread=30,betrigger={bt},beoffset={bo},traildist=40,trailtrig=100,trailstep=10,
comment={lots}#sl=50#tp={tp}#sd=30#bt={bt}#bo={bo}#td=40#tt=100#ts=10
```

### Close Command Format
```
{licenseID},closelong,XAUUSD    ← close buy position
{licenseID},closeshort,XAUUSD   ← close sell position
```

### Parameter Breakdown
| Parameter | Value | Source |
|---|---|---|
| `vol_lots` | Dynamic | Pine lot sizing (% risk or fixed) |
| `sl_pips=50` | Fixed | Hard disaster SL — NOT Pine logical SL |
| `tp_pips` | Dynamic | Calculated from R:R ratio × SL distance |
| `spread=30` | Fixed | Broker pip spread filter |
| `betrigger` | Dynamic | `tp_pips × 0.10` (10% of TP) |
| `beoffset` | = betrigger | When `uBELkTP = false`, beoffset = betrigger |
| `traildist=40` | Fixed | Trail distance in broker pips |
| `trailtrig=100` | Fixed | Trail activates after 100 pips profit |
| `trailstep=10` | Fixed | Trail moves every 10 pips gained |

### Critical Parameters
| Parameter | Value | Warning |
|---|---|---|
| `pPip` | 0.10 | XAUUSD pip size — MUST be 0.10, not 0.01 |
| `pcBrkPip` | 0.10 | Broker pip size for PineConnector |
| `pSym` | XAUUSD | Must match MT5 symbol name exactly |

### Known Issues (Fixed)
- `closebuy`/`closesell` are invalid PineConnector v3 commands — use `closelong`/`closeshort`
- TradingView alert webhooks cache at creation time — must delete and recreate alert after any settings change
- `pPip = 0.01` causes SL calculation error: `sl_pips = round(50 × 0.01 / 0.10) = 5` → instant stop-outs

---

## 14. Stats Panel & Optimizer

### Panel Layout (16 rows)
| Row | Content |
|---|---|
| 0 | Header: ticker, timeframe, session, signal integrity |
| 1 | Status: STANDING BY / SETUP IN PROGRESS / SIGNAL FIRED |
| 2 | Trend direction, strength bar, next signal ETA |
| 3 | TODAY divider |
| 4 | Today P&L + current balance (large, green) |
| 5 | UHV subtotals + avg trade duration |
| 6 | Trade count + win streak |
| 7 | Last hour P&L + next hour EV projection |
| 8 | STRATEGIES divider |
| 9–10 | UHV W/L%, all-time, today, avg win/loss |
| 11 | ALL-TIME divider |
| 12 | All-time P&L + accuracy + EV per trade |
| 13 | To-double + washout + yesterday % |
| 14 | OPTIMIZER & TOOLS divider |
| 15 | Top 2 optimizer recommendations |

### Optimizer Recommendations
| Icon | Priority | Trigger |
|---|---|---|
| 🚨 | Critical | Negative EV or >10% daily drawdown |
| ⚠️ | Warning | Win rate below break-even for strategy |
| 💡 | Optimize | Data-driven R:R or filter suggestion |
| 🔓 | Unlock | Filter blocking signals — estimate of lost P&L |

---

## 15. Parameter Sensitivity Framework

### Velocity Filter Sweep (recommended before enabling uTVOn)
| k value | Expected signal retention | Use case |
|---|---|---|
| 1.1 | ~85% | Very loose — minimal filtering |
| 1.2 | ~70% | Recommended starting point |
| 1.3 | ~55% | Moderate filtering |
| 1.5+ | <40% | Aggressive — significant signal loss |

### R:R and Trailing Interaction
| TP R:R | BE trigger | Trail trigger | Expected behavior |
|---|---|---|---|
| 2R | 33% | 25 pips | BE fires at ~8 pips, trail conflicts |
| 10R | 10% | 100 pips | BE fires at ~16 pips, trail runs freely |
| 10R | 10% | 100 pips, dist=40 | Optimal runner config (current) |

### Daily EV Impact of Filters
| Filter | Signals/day | Avg EV/trade | Daily EV |
|---|---|---|---|
| No filters | 88 | $9.20 | $810 |
| Momentum body 40% | 34 | $10.03 | $341 |
| Tick velocity k=1.2 | ~60 (est.) | TBD | TBD |

### Notes
Always evaluate filters by `EV_per_trade × signals_per_day`, not by win rate alone. A filter that raises win rate but cuts signal count 60% will reduce total daily P&L.

---

## 16. Recommended Defaults (XAUUSD, 1m)

> **Session 42/43 optimal configuration** — 539 trades, 73% WR, $33.82 EV/trade, +$18,226 all-time P&L.
> These are the code defaults. Click "Defaults" in settings to restore them instantly.

### Account & Risk
| Setting | Value | Notes |
|---|---|---|
| My Starting Capital ($) | 865 | Update to current equity |
| Contract size ($/point/lot) | 100 | Exness standard |
| Position Size Multiplier | 1 | |
| Spread ($) | 0.13 | |
| Account Leverage | 500 | |
| Risk: Fixed lot size | **0.4** | Gives -$60 max loss on 15-pip SL |

### Strategy: UHV Breakout
| Setting | Value | Notes |
|---|---|---|
| Use this strategy? | ON | |
| Must breakout candle have lower volume | **OFF** | Removing this filter increases trade count |
| Open trade at | **Instant at Breakout** | IOE mode — enters at exact trigger |
| Pre-breakout offset ($) | **1.0** | Fires $1 before level for better fill |
| Also allow signal at actual breakout level | **OFF** | Pre-offset fires or trade is skipped |
| Require body breakout | ON | Prevents wick-only false entries |
| Stop Loss method | Breakout Wick | |
| SL Offset from level | 0.4 | |
| SL minimum distance ($) | 0.2 | |
| **Stop Loss: Override with fixed pips** | **15** | Fixed 15-pip SL = -$60 max at 0.4 lots |
| **Take Profit: Override with fixed pips** | **3** | Fixed 3-pip TP (IOE guard often extends to ~8 pips) |
| Take Profit method | R:R Ratio (R:R = 7) | Backup when pip override = 0 |

### Kill Timer (key optimisation)
| Setting | Value | Notes |
|---|---|---|
| **Kill timer: close after X seconds** | **5** | Close ANY open trade 5 sec after entry |
| Kill timer (loss only) | 0 | OFF — kill-ALL outperforms kill-loss-only |

Kill ALL at 5 sec: avg loss -$60 → -$46, net EV +$2.73/trade vs no timer.

### Invalidation Exit
| Setting | Value | Notes |
|---|---|---|
| Invalidation Exit | ON | |
| Invalidation Exit: Hard SL (pips) | **15** | Matches uSLPips — no gap between Pine sim and MT5 hard SL |
| Invalidation Exit: Tolerance ($) | 0.3 | |
| Invalidation rule | UHV Midpoint | VSA absorption rule |
| Invalidation offset ($) | **1.0** | Close must be $1 past midpoint before invalidating |

### Trend & Filters (all disabled for maximum trade count)
| Setting | Value | Notes |
|---|---|---|
| Min Trend Strength at Signal | **0** | No trend strength requirement |
| Avoid trend shifting | OFF | |
| Apply trend shift to UHV | **OFF** | |
| Require Full Trend Confirmation | OFF | |
| Apply full trend to UHV | **OFF** | |
| No-Trade Window 19:00–21:00 UTC | **OFF** | Trade all hours |
| Bypass retracement rules | ON | |
| Wick trigger | **OFF** | Body close required for bRW trigger |

### IOE Guard
| Setting | Value | Notes |
|---|---|---|
| IOE TP Guard spread multiplier | **1** | Guards against TP being too close at entry bar close |
| Alert Gate ($) | -0.05 | Small tolerance for fast candles |

### PineConnector
| Setting | Value | Notes |
|---|---|---|
| MT5 pip size (XAUUSD) | **0.10** | Critical — wrong value breaks all pip calculations |
| Broker pip size | **0.10** | Critical |
| Spread filter (pips) | 30 | |
| Trailing stop | **OFF** (0) | No trailing — kill timer handles exit timing |
| Stop Loss format | Pips | |
| Take Profit format | Pips | |

---

## 17. Settings Export & Restore

The **SETTINGS EXPORT** row at the bottom of the stats panel outputs a full `T1|...` encoded string of all settings. Copy this string and save externally — TradingView does not persist indicator settings across devices.

### String Format
```
T1|{Account}|{POI}|{UHV}|{Trend}|{HTF}|{PC}
```

Each section is pipe-delimited. Booleans are 0/1. Enums are integer-encoded:
- Direction: `0=Both`, `1=Bull only`, `2=Bear only`
- Entry mode: `0=Candle Close`, `1=Instant at Breakout`
- TP method: `0=R:R Ratio`, `1=Structural High/Low`, `2=Dollar Amount`
- SL method: `0=UHV`, `1=ATR`, `2=Breakout Wick`, `3=SwingLow`, `4=Dollar`, `5=Retracement Min/Max`, `6=Prev Candle`

### Restore Procedure
1. Copy the T1 export string from the stats panel
2. Paste to Claude: "restore my settings from this export string"
3. Claude decodes every field and provides the exact value for each setting
4. After restoring: delete and recreate the TradingView alert (webhooks cache at creation time)

---

## 18. Alert Condition Bitmask

Every signal `comment=` field includes a 16-bit binary string encoding the exact conditions at entry.

### Format
```
comment=0.04#sl=50#tp=161#sd=30#bt=16#bo=16#td=40#tt=100#ts=10
```

The label on-chart also shows the full condition bitmask in Developer mode.

### Bit Reference
| Bit | Position | Meaning when 1 |
|---|---|---|
| 0 | 1 | Direction: SELL (0 = BUY) |
| 1 | 2 | Entry mode: IOE (0 = Candle Close) |
| 2–3 | 3–4 | Strategy: 00=UHV, 01=2BR, 10=EVR, 11=EVR-W |
| 4 | 5 | Strict trend mode ON |
| 5 | 6 | Strict trend condition MET |
| 6 | 7 | Sweep requirement ON |
| 7 | 8 | Sweep confirmed |
| 8 | 9 | Pre-breakout offset ON |
| 9 | 10 | Co-exist path used |
| 10 | 11 | Trend direction: uptrend |
| 11 | 12 | In allowed session window |
| 12 | 13 | Volume filter ON |
| 13 | 14 | Volume filter condition MET |
| 14 | 15 | Opposing candle filter ON |
| 15 | 16 | Opposing candle condition MET |

**To decode any trade:** paste the alert string to Claude and say "decode the bitmask".

---

*Documentation version: 2026-04-18 (Session 44)*
*Architecture: ~2730 lines Pine Script v5*
*Last major changes: Kill ALL timer (uKillSec=5), fixed pip SL/TP (15/3), all defaults updated to match Session 42/43 optimal config*
