# Turtle Trader Desk — Last Known Good Settings
Last updated: 2026-04-18 (Session 43/44)
Source: Live indicator via MCP — `data_get_indicator` on entity_id `PgkQBd`

## Performance (Session 42/43 — Best All-Time)
| Metric | Value |
|---|---|
| Trades | 539 all-time (~22/day) |
| Win rate | **73%** (395/539) |
| EV/trade | **$33.82** |
| Avg win | +$62.97 |
| Avg loss | -$46.16 |
| All-time P&L | **+$18,226** |
| Max loss per trade | -$60 (hard-capped by iExHSL=15) |

## Key optimisation: Kill ALL Timer (uKillSec = 5)
Close ANY open trade 5 seconds after entry, regardless of P&L direction.
- Fires at bar N+1 close in historical sim; at exactly 5 sec in live MT5
- Avg loss drops from -$60 → -$46 by cutting stagnant trades early
- Net EV improves by $2.73/trade vs no kill timer

## How to restore
1. Open indicator settings in TradingView
2. Click "Defaults" to reset — code defaults now match these values exactly
3. Delete and recreate the TradingView alert (any alert() function call, webhook enabled)

## Changes vs previous snapshot (2026-04-03)
| Setting | Old | New |
|---|---|---|
| Pre-breakout offset ($) | 6 | **1** |
| Also allow signal at actual breakout level | true | **false** |
| Risk: % of capital per trade | 1 | **0** |
| Risk: Fixed lot size | 0.011 | **0.4** |
| Take Profit R:R | 9 | **7** |
| Take Profit Fixed $ target | 0.1 | **1.1** |
| Stop Loss: Override with fixed pips | 0 | **15** |
| Take Profit: Override with fixed pips | 0 | **3** |
| Breakeven: move SL to entry+spread | true | **false** |
| Invalidation Exit: Hard SL (pips) | 120 | **15** |
| Invalidation offset ($) | 0 | **1.0** |
| Emergency MAE stop: max loss $ | 40 | **0** |
| Kill timer: close after X seconds | 90 | **5** |
| IOE TP Guard spread multiplier | 0 | **1** |
| Alert Gate ($) | 0 | **-0.05** |
| Min Trend Strength at Signal | 3 | **0** |
| Apply to UHV Breakout (trend shift) | true | **false** |
| Apply to UHV Breakout (full trend) | true | **false** |
| Wick trigger | true | **false** |
| Show Debug Labels | false | **true** |

## Settings (complete — all 140 inputs)

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
| Must breakout candle have lower volume | **false** |
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
| Also allow signal at actual breakout level | **false** |
| Dollar risk per trade ($) | 0 |
| % of capital per trade | 0 |
| Fixed lot size | **0.4** |
| Take Profit: Which method? | R:R Ratio |
| Take Profit R:R | **7** |
| Take Profit Fixed $ target | 1.1 |
| Take Profit Structural offset ($) | 0.5 |
| Stop Loss: Where to place it? | Breakout Wick |
| Stop Loss: Offset from SL level | 0.4 |
| Stop Loss: Closest it can ever be ($) | 0.2 |
| Stop Loss: Volatility width (ATR) | 1 |
| Stop Loss: Fixed $ distance | 2 |
| Stop Loss: Swing lookback bars | 11 |
| Stop Loss: Override with fixed pips | **15** |
| Take Profit: Override with fixed pips | **3** |
| Breakeven: move SL to entry+spread | **false** |
| Breakeven trigger: % of TP distance | 10 |
| Breakeven at R:R ratio | 0 |
| Lock SL at BE trigger price | false |
| Lock SL at X×R profit when BE fires | 0 |
| Invalidation Exit | true |
| Invalidation Exit: Hard SL (pips) | **15** |
| Invalidation Exit: Tolerance ($) | 0.3 |
| Invalidation rule | UHV Midpoint |
| Invalidation offset ($) | **1.0** |
| Emergency MAE stop: pips against entry (0=off) | 60 |
| Emergency MAE stop: max loss $ (0=off) | **0** |
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
| Min Trend Strength at Signal | **0** |
| Trend Persistence Lookback (bars) | 8 |
| Only trade London + NY sessions | false |
| Avoid trading when trend is shifting? | false |
| Apply to UHV Breakout (trend shift) | **false** |
| Trend shift threshold | 53 |
| Require Full Trend Confirmation | false |
| Apply to UHV Breakout (full trend) | **false** |
| Show Trend MA Line | true |
| Require structural trend | false |
| Avoid ranging market (ADX) | false |
| Ranging threshold (ADX) | 14 |
| No-Trade Window 21:00–23:00 UTC | false |
| No-Trade Window 23:00–03:00 UTC | false |
| No-Trade Window 04:00–07:00 UTC | false |
| No-Trade Window 19:00–21:00 UTC | **false** |
| Force-close on no-trade window start | false |
| Bypass retracement rules | true |
| Wick trigger | **false** |
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
| Show Debug Labels | **true** |
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

## SS Snapshot
Paste into indicator_set_inputs to restore all settings at once:
```
SS:900100800201#865#100#1#0.13#500#0#0#0#20#5#1.5#0#1#0#0#0#0#0.4#0#7#1.1#0.5#2#0.4#0.2#1#2#11#15#3#10#0#15#0#0#0.4#0#7#1.1#0.5#2#0.4#0.2#1#2#11#15#3#10#0#15#0.3#1#60#0#5#0#40#50#80#30#30#5#1.2#5#0#-0.05#1#0#8#53#14#4#3#3#5#2#5#50#50#0.6#2#3#5#0.5#3#3#0.01#0.1#0.1#0#0#0
```

To restore kill timer via MCP: `indicator_set_inputs(entity_id="PgkQBd", inputs={"in_52": 5, "in_53": 0})`
