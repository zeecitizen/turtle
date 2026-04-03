# Turtle Trader Desk — Last Known Good Settings
Last updated: 2026-04-03
Source: Screenshot-verified from TradingView settings panel

## How to restore
1. Open indicator settings in TradingView
2. Click "Defaults" to reset, OR enter manually from table below
3. Delete and recreate the TradingView alert (any alert() function call, webhook enabled)

## ✅ No Manual Fixes Required
All defaults in code now match live settings exactly (verified against screenshots).

## Settings

| Setting | Value |
|---|---|
| My Starting Capital ($) | 866 |
| Contract size ($/point/lot) | 100 |
| Position Size Multiplier | 1 |
| Spread ($) | 0.13 |
| Account Leverage | 500 |
| Previous Higher Low | false |
| Broken High / Low | false |
| Use this strategy? | true |
| Must candle wick sweep UHV low | false |
| Must breakout candle have lower volume | **true** |
| UHV Detection: Require percentile rank | false |
| Min volume percentile threshold | 95 |
| Lookback bars for percentile | 20 |
| Bars after UHV before entry | 0 |
| Open trade at | **Candle Close** |
| Pre-breakout offset ($) | **0** |
| Post-breakout offset ($) | 0 |
| Also allow signal at actual breakout level | true |
| Risk: Dollar risk per trade ($) | 0 |
| Risk: % of capital per trade | **4** |
| Risk: Fixed lot size | 0.011 |
| Take Profit: Which method? | R:R Ratio |
| Take Profit: R:R Ratio | **7** |
| Take Profit: Fixed $ target | **1.1** |
| Take Profit: Structural offset ($) | 0.5 |
| Stop Loss: Where to place it? | Breakout Wick |
| Stop Loss: Offset from SL level | **0.4** |
| Stop Loss: Closest it can ever be ($) | 0.2 |
| Stop Loss: Volatility width (ATR) | **1** |
| Stop Loss: Fixed $ distance | 2 |
| Stop Loss: Swing lookback bars | 11 |
| Stop Loss: Override with fixed pips | 0 |
| Take Profit: Override with fixed pips | 0 |
| Breakeven: move SL to entry+spread | true |
| Breakeven trigger: % of TP distance | 10 |
| Lock SL at BE trigger price | false |
| Invalidation Exit | true |
| Invalidation Exit: Hard SL (pips) | **120** |
| Invalidation Exit: Tolerance ($) | 0.3 |
| Invalidation rule | **UHV Midpoint** |
| Emergency MAE stop: pips against entry (0=off) | **60** |
| Emergency MAE stop: max loss $ (0=off) | **40.0** |
| Kill timer: close after X seconds (0=off) | **90** |
| Kill timer (loss only): close if in loss after X seconds (0=off) | 0 |
| Partial TP: enabled | false |
| Partial TP trigger (pips) | 40 |
| Partial TP close % | 50.0 |
| Cancel on early bounce-back | false |
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
| Volatility Blocker | false |
| Volatility Blocker ATR threshold | 4.0 |
| Volatility Blocker: also check spread | false |
| Volatility Blocker spread multiplier | 3.0 |
| Max trades per hour | false |
| Max trades per rolling 60-min window | 3 |
| Min minutes between entries | 5 |
| Drawdown Protection | false |
| Max SL risk per trade (% of current equity) | 50.0 |
| Daily loss limit | false |
| Soft limit (% of capital) | 2.0 |
| Hard limit (% of capital) | 5.0 |
| Momentum Candle: min body size | false |
| Min body size % | **80** |
| Momentum Candle: max wick size | false |
| Max wick size % | **30** |
| Require volume drop vs UHV | false |
| Volume drop % | 5 |
| Require body breakout | true |
| Tick Velocity Filter | **false** |
| Velocity multiplier threshold | 1.2 |
| Velocity baseline lookback (bars) | **5** |
| Cooldown: bars after signal | 0 |
| Alert Gate ($) | -0.05 |
| IOE TP Guard spread multiplier | 1 |
| Min Trend Strength at Signal | 3 |
| Trend Persistence Lookback (bars) | 8 |
| Only trade London + NY sessions | false |
| Cut Low Probability Trades | false |
| Avoid trading when trend shifting | **false** |
| Apply to UHV Breakout (trend shift) | **true** |
| How much can trend weaken before blocking the entry? | 53 |
| Require Full Trend Confirmation | false |
| Apply to UHV Breakout (full trend) | true |
| Show Trend MA Line | true |
| Require structural trend | false |
| Avoid ranging market (ADX) | false |
| Ranging threshold (ADX) | **14** |
| No-Trade Window 21:00–23:00 UTC | false |
| No-Trade Window 23:00–03:00 UTC | false |
| No-Trade Window 04:00–07:00 UTC | false |
| No-Trade Window 19:00–21:00 UTC | **true** |
| Force-close on no-trade window start | false |
| Bypass retracement rules | true |
| Wick trigger | **false** |
| Show Signal Labels | true |
| Show Debug Labels | false |
| Show Stats Panel | true |
| Highlight signal candles | true |
| Send signals to PineConnector | true |
| PineConnector License ID | 8778286989525 |
| MT5 Symbol Name | XAUUSD |
| Minimum lot size | 0.01 |
| MT5 pip size (XAUUSD=0.10) | **0.10** ← critical |
| Broker pip size for PineConnector | **0.10** ← critical |
| Spread filter (broker pips) | 30 |
| Breakeven: move SL after X pips | 0 |
| Breakeven offset (pips) | 0 |
| Trailing stop distance (pips) | **20** |
| Trailing trigger (pips) | **60** |
| Trailing step (pips) | **3** |
| Signal→MT5 latency ms | 200 |
| Apply token corrections | false |
| Stop Loss format sent to MT5 | **Pips** |
| Take Profit format sent to MT5 | **Pips** |
| Maximize Trades | false |
| Developer mode | true |
