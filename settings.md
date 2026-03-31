# Turtle Trader Desk — Last Known Good Settings
Last updated: 2026-03-31 (Session 31)
Source: Friday 27 Mar settings export + session 30 manual fix

## How to restore
1. Open indicator settings in TradingView
2. Click import button (⬆ floppy disk icon) and load the CSV below, OR enter manually
3. **Apply the one manual fix noted below**
4. Delete and recreate the TradingView alert (any alert() function call, webhook enabled)

## ✅ No Manual Fixes Required
All defaults in code now match live settings exactly.

## Settings CSV (paste into TradingView import or enter manually)

| Setting | Value |
|---|---|
| My Starting Capital ($) | 865 |
| Contract size ($/point/lot) | 100 |
| Position Size Multiplier | 1 |
| Spread ($) | 0.13 |
| Account Leverage | 500 |
| Require POI zone | false |
| Require POI Touch Before Signal | false |
| Higher Time Frame FVG | false |
| Previous Higher Low | false |
| Broken High / Low | false |
| POI Lookback (bars) | 50 |
| Use this strategy? | true |
| Must candle wick sweep UHV low | false |
| Must breakout candle have lower volume | false |
| UHV Detection: Require percentile rank | false |
| Min volume percentile threshold | 95 |
| Lookback bars for percentile | 20 |
| Bars after UHV before entry | 0 |
| Pre-breakout offset ($) | 5 |
| Post-breakout offset ($) | 0 |
| Also allow signal at actual breakout level | true |
| Risk: Dollar risk per trade ($) | 0 |
| Risk: % of capital per trade | 1 |
| Risk: Fixed lot size | 0.011 |
| Take Profit: R:R Ratio | 2 |
| Take Profit: Fixed $ target | 0.1 |
| Take Profit: Structural offset ($) | 0.5 |
| Stop Loss: Offset from SL level | 0.7 |
| Stop Loss: Closest it can ever be ($) | 0.2 |
| Stop Loss: Volatility width (ATR) | 4 |
| Stop Loss: Fixed $ distance | 2 |
| Stop Loss: Swing lookback bars | 11 |
| Stop Loss: Override with fixed pips | 0 |
| Take Profit: Override with fixed pips | 0 |
| Breakeven: move SL to entry+spread | true |
| Breakeven trigger: % of TP distance | 33 |
| Lock SL at BE trigger price | true |
| Invalidation Exit | true |
| Invalidation Exit: Hard SL (pips) | 50 |
| Invalidation Exit: Tolerance ($) | 0 |
| Cancel on early bounce-back | false |
| Momentum Candle: min body size | false |
| Min body size % | 30 |
| Momentum Candle: max wick size | false |
| Max wick size % | 5 |
| Require volume drop vs UHV | false |
| Volume drop % | 5 |
| Require body breakout | true |
| Cooldown: bars after signal | 0 |
| Alert Gate ($) | -0.05 |
| IOE TP Guard spread multiplier | 1 |
| Min Trend Strength at Signal | 3 |
| Trend Persistence Lookback (bars) | 8 |
| Only trade London + NY sessions | false |
| Cut Low Probability Trades | false |
| Avoid trading when trend shifting | false |
| Apply to UHV Breakout | true |
| Shift Threshold | 53 |
| Require Full Trend Confirmation | false |
| Show Trend MA Line | true |
| Require structural trend | false |
| Avoid ranging market (ADX) | false |
| Ranging threshold (ADX) | 10 |
| No-Trade Window 21:00–23:00 UTC | false |
| No-Trade Window 23:00–03:00 UTC | false |
| No-Trade Window 04:00–07:00 UTC | false |
| No-Trade Window 19:00–21:00 UTC | false |
| Bypass retracement rules | true |
| Wick trigger | true |
| Use Higher Time Frame FVG | false |
| FVG Width Filter (ATR multiple) | 0.3 |
| UHV FVG Width Filter | 0.3 |
| Show Historical FVGs | true |
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
| Trailing stop distance (pips) | 15 |
| Trailing trigger (pips) | 25 |
| Trailing step (pips) | 5 |
| Signal→MT5 latency ms | 200 |
| Apply token corrections | false |
| Maximize Trades | false |
| Developer mode | true |
