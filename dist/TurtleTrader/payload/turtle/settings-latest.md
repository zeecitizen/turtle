# Turtle Trader Desk — Last Known Good Settings
Last updated: 2026-04-19 (Session 49)
Source: Session 48 exhaustive sweep (TP, BE, kill, SL); Session 49 spike protection (iExHSL 15→10)

---

## Strategy Mode Comparison — Choose Your Style

| Metric | High-WR Mode | High-EV Mode (CURRENT) |
|---|---|---|
| **uTPPips** | 10 | **52** |
| **uBERR** | 0.2 | **0.1** |
| betrigger sent to MT5 | 3 pips | **2 pips** |
| Win rate | **64%** (348/544) | 29% (158/544) |
| EV/trade | $17.15 | **$53.94** |
| Avg win | +$39 | **+$204** |
| Avg loss | -$22 | **-$7.53** |
| All-time P&L | $9,344 | **$29,343** |
| Washout threshold | 39 losses | **114 losses** |
| To double balance | 51 trades | **17 trades** |
| Max loss/trade | -$60 | -$60 |
| Trades/day | ~23 | ~23 |
| Feel | Many small wins | Fewer but large wins |

> **Why EV triples despite lower WR**: BE fires at 1.5 pips (uBERR=0.1) instead of 3 pips.
> Losers exit near $0 via 5s kill timer. Winners that trigger BE run freely to 52-pip TP (+$208).
> The wide TP captures the full extension of real UHV moves instead of capping early.

**To switch back to High-WR mode:**
```
indicator_set_inputs(entity_id="<from chart_get_state>", inputs={"in_39": 10, "in_42": 0.2})
```

---

## Current Performance (Session 48 — High-EV Mode)
| Metric | Value |
|---|---|
| Trades | 544 all-time (~23/day) |
| Win rate | **29%** (158/544) |
| EV/trade | **$53.94** |
| Avg win | +$204.11 |
| Avg loss | -$7.53 |
| All-time P&L | **+$29,343** |
| Max loss per trade | -$60 (hard-capped by iExHSL=15) |
| To double balance | **17 trades (~13.6 hrs)** |
| Washout threshold | **114 consecutive losses** |

## Key Optimisations

### 1. Kill ALL Timer (uKillSec = 5)
Close ANY open trade 5 seconds after entry, regardless of P&L direction.
- Fires at bar N+1 close in historical sim; at exactly 5 sec in live MT5
- Exit price ≈ entry → avg loss only -$7.53 (not -$60)
- Disabled once breakeven fires (trade is protected)

### 2. BE + Wide Runner (uBEon = true, uBERR = 0.1, uTPPips = 52)
Once price moves **1.5 pips** in profit (uBERR=0.1 × uSLPips=15), SL moves to entry+spread.
- Trade is now risk-free; kill timer disabled; TP target extends to **52 pips (+$208)**
- PineConnector alert includes `betrigger=2` — instructs MT5 to move SL after 2 pips
- Asymmetric payout: losers ≈ $0 (kill timer), winners ≈ $204 (TP hit)

## How to restore
1. Open indicator settings in TradingView
2. Click "Defaults" to reset — code defaults now match these values exactly
3. Delete and recreate the TradingView alert (any alert() function call, webhook enabled)

## Changes vs Session 48 (2026-04-19)
| Setting | Session 48 | Session 49 |
|---|---|---|
| Invalidation Exit: Hard SL (pips) — MT5 spike stop | 15 | **10** |

> **Why**: A spike event (Trade 5, Apr 20 08:27 Moscow) moved 15 pips against entry in <5 seconds,
> triggering iExHSL=15 → **-$62** before the 5s kill timer could exit. iExHSL=10 caps this at **~-$40**.
> Pine sim EV is UNCHANGED (iExHSL does not affect lot sizing or Pine stats per code design).

## Changes vs Session 47 (2026-04-18)
| Setting | Session 47 | Session 48 |
|---|---|---|
| Take Profit: Override with fixed pips | 10 | **52** |
| Breakeven at R:R ratio | 0.2 | **0.1** |
| betrigger (MT5 alert) | 3 | **2** |

## Session 48 — What Was Tested
All tests used kill=5s, SL=15, XAUUSD 1m OANDA, 544 all-time trades.

**TP pips sweep** (uBERR=0.2 baseline):
10→$17 | 20→$33 | 30→$38 | 40→$42 | 50→$48 | **52→$53** | 55→$52 | 60→$52 | 75→$50 | 100→$49

**BE trigger sweep** (TP=52):
uBERR=0.2→$53.05 | **uBERR=0.1→$53.94** | uBERR=0.05→$53.97 (betrigger=1, risky)

**Kill timer sweep** (TP=52, uBERR=0.1): 5s/10s/20s/30s all within $0.10 — neutral, keep at 5s

**SL pips sweep** (TP=52, uBERR=0.1): 10/15/20 pips all within $0.04 — neutral, keep at 15

## Settings (complete — all inputs)

### 💼 My Account
| Setting | Value |
|---|---|
| My Starting Capital ($) | **865** |
| Contract size ($/point/lot) | 100 |
| Position Size Multiplier | 1 |
| Spread ($) | 0.13 |
| Account Leverage | 500 |

### 📊 Strategy: Ultra High Volume Breakout
| Setting | Value |
|---|---|
| Use this strategy? | true |
| Trade direction? | Both |
| Must candle wick sweep UHV low | false |
| Must breakout candle have lower volume | false |
| Align direction to higher timeframe | Off |
| UHV Detection: Require percentile rank | false |
| Lookback bars for percentile | 20 |
| Require background context | false |
| Background lookback (bars) | 5 |
| Require wide-spread UHV candle | false |
| Wide spread multiplier | 1.5 |
| UHV Candle: Limit max wick size | false |
| Max combined wick % of candle range | 60 |
| UHV Candle: Require minimum body strength | false |
| Min body strength % | 40 |
| Bars after UHV before entry | 0 |
| Open trade at | **Instant at Breakout** |
| Pre-breakout offset ($) | **1.0** |
| Post-breakout offset ($) | 0 |
| Also allow signal at actual breakout level | false |
| Dollar risk per trade ($) | 0 |
| % of capital per trade | 0 |
| Fixed lot size | **0.4** |
| Take Profit: Which method? | R:R Ratio |
| Take Profit R:R | 7 |
| Take Profit Fixed $ target | 1.1 |
| Take Profit Structural offset ($) | 0.5 |
| Stop Loss: Where to place it? | Breakout Wick |
| Stop Loss: Offset from SL level | 0.4 |
| Stop Loss: Closest it can ever be ($) | 0.2 |
| Stop Loss: Volatility width (ATR) | 1 |
| Stop Loss: Fixed $ distance | 2 |
| Stop Loss: Swing lookback bars | 11 |
| Stop Loss: Override with fixed pips | **15** |
| Take Profit: Override with fixed pips | **52** ← changed from 10 |
| Breakeven: move SL to entry+spread | **true** |
| Breakeven trigger: % of TP distance | 10 |
| Breakeven at R:R ratio | **0.1** ← changed from 0.2 |
| Lock SL at BE trigger price | false |
| Lock SL at X×R profit when BE fires | 0 |
| Invalidation Exit | true |
| Invalidation Exit: Hard SL (pips) | **10** ← changed from 15 (spike protection: caps MT5 loss at ~-$40 vs -$62; zero sim impact) |
| Invalidation Exit: Tolerance ($) | 0.3 |
| Invalidation rule | UHV Midpoint |
| Invalidation offset ($) | **1.0** |
| Emergency MAE stop: pips against entry (0=off) | 60 |
| Emergency MAE stop: max loss $ (0=off) | 0 |
| Kill timer: close after X seconds (0=off) | **5** |
| Kill timer (loss only): close if in loss after X seconds (0=off) | 0 |
| Partial TP: enabled | false |
| Partial TP trigger (pips) | 40 |
| Partial TP close % | 50 |
| Cancel on early bounce-back | false |
| Momentum Candle: min body size | false |
| Min body size % | 80 |
| Momentum Candle: max wick size | false |
| Max wick in breakout direction % | 30 |
| Max wick opposite direction % | 30 |
| Require volume drop vs UHV | false |
| Volume drop % | 5 |
| Require body breakout | true |
| Tick Velocity Filter | false |
| Velocity multiplier threshold | 1.2 |
| Velocity baseline lookback (bars) | 5 |
| Cooldown: bars after signal | 0 |
| Alert Gate ($) | **-0.05** |
| IOE TP Guard spread multiplier | **1** |

### 📈 Trend & Filters
| Setting | Value |
|---|---|
| Min Trend Strength at Signal | 0 |
| Trend Persistence Lookback (bars) | 8 |
| Only trade London + NY sessions | false |
| Avoid trading when trend is shifting? | false |
| Apply to UHV Breakout (trend shift) | false |
| Trend shift threshold | 53 |
| Require Full Trend Confirmation | false |
| Apply to UHV Breakout (full trend) | false |
| Show Trend MA Line | true |
| Require structural trend | false |
| Avoid ranging market (ADX) | false |
| Ranging threshold (ADX) | 14 |
| No-Trade Window 21:00–23:00 UTC | false |
| No-Trade Window 23:00–03:00 UTC | false |
| No-Trade Window 04:00–07:00 UTC | false |
| No-Trade Window 19:00–21:00 UTC | false |
| Force-close on no-trade window start | false |
| Bypass retracement rules | true |
| Wick trigger | false |
| bRW lookback (bars) | 3 |

### 🛡️ Risk Management
| Setting | Value |
|---|---|
| Volatility Blocker | false |
| Volatility Blocker ATR threshold | 4.0 |
| Also block on synthetic spread | false |
| Synthetic spread multiplier | 3.0 |
| Max trades per hour | false |
| Max trades per rolling 60-min window | 3 |
| Min minutes between entries | 5 |
| Daily loss limit | false |
| Soft limit (% of capital) | 2.0 |
| Hard limit (% of capital) | 5.0 |
| Drawdown Protection | false |
| Max SL risk per trade (% of current equity) | 50.0 |
| Spread Spike Filter | false |
| Max candle range (pips) | 50.0 |
| Volatility Collapse Exit | false |
| Collapse factor | 0.6 |
| Opposite UHV Exit | false |
| Volume multiple | 2.0 |
| Breakout Failure Exit | false |
| Failure window (bars) | 3 |
| Extension threshold (pips) | 5.0 |
| Volume Drop Exit | false |
| Drop factor | 0.5 |
| Micro-Structure Break Exit | false |
| Buffer pips beyond swing | 3.0 |
| Micro swing lookback bars | 3 |

### 🖥️ Display
| Setting | Value |
|---|---|
| Show Signal Labels | true |
| Show Debug Labels | true |
| Show Stats Panel | true |
| Highlight signal candles | true |

### 🤖 PineConnector Automation
| Setting | Value |
|---|---|
| Send signals to PineConnector | true |
| PineConnector License ID | 8778286989525 |
| MT5 Symbol Name | XAUUSD |
| Minimum lot size | 0.01 |
| MT5 pip size (XAUUSD=0.10) | **0.10** ← critical |
| Broker pip size for PineConnector | **0.10** ← critical |
| Spread filter (broker pips) | 30 |
| Breakeven: move SL after X pips | 0 |
| Breakeven offset (pips) | 0 |
| Trailing stop distance (pips) | 0 |
| Trailing trigger (pips) | 0 |
| Trailing step (pips) | 3 |
| Signal→MT5 latency ms | 200 |
| Slippage (USD) | 0 |
| Stop Loss format sent to MT5 | Pips |
| Take Profit format sent to MT5 | Pips |
| Order type sent to MT5 | Market |

### ⚡ Optimize
| Setting | Value |
|---|---|
| Developer mode | true |

## Restore via MCP
```
indicator_set_inputs(entity_id="<get from chart_get_state>", inputs={"in_39": 52, "in_42": 0.1, "in_46": 10})
```

To switch to High-WR mode (TP=10, 64% WR):
```
indicator_set_inputs(entity_id="<get from chart_get_state>", inputs={"in_39": 10, "in_42": 0.2})
```
