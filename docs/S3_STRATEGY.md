# S3 Strategy — Effort vs Result (Wicking Green Breakout)

> **File**: `mt5/S3Trader.mq5` | **Magic**: 88003 | **Version**: 2.30 | **Timeframe**: M5

## Origin
S3 is based on the teacher's "effort vs result" concept — when price tries hard (high volume red during pullback) but fails to go down (price holds), and then a green candle with BIGGER volume but smaller range wicks through the red's low and closes back above it, that's exhaustion → the trend resumes.

## Strategy (BUY side — SELL added in v2.30)

1. **Uptrend confirmed** — M5 close is $1+ higher than 24 bars ago
2. **Find a recent green candle** (in last 30 bars) whose low was broken by subsequent reds — this is the "pivot green"
3. **Collect the reds** that broke below the pivot green's low — these are the "retracement reds"
4. **Wicking pattern** — the breakout candle (shift 1, just-closed) must:
   - Be GREEN
   - Have its LOW below a retracement red's LOW (wicked through)
   - Have its CLOSE above that red's LOW (closed back above)
   - Have HIGHER VOLUME than that red
   - Have upper wick ≤ 35% of total range (momentum, not exhaustion)
5. **Entry**: market BUY
6. **SL**: breakout candle's low − $2.00 buffer
7. **TP**: highest high of last 10 M5 bars (structural target)

## SELL Side (added v2.30)
Mirror of buy: downtrend → find a recent red → collect greens that broke above it → red wicking candle breaks below green's high and closes back below → SELL. TP = lowest low of last 10 bars.

## Why These Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Upper wick limit | 35% | Filters exhaustion candles that wick up but close weak. Validated in backtest |
| SL buffer | $2.00 | Same as S1 — wider SL absorbs noise. Improved from 0.10 after sweep showed +17% |
| M5 FVG | **OFF** | 18-day backtest showed FVG makes OOS 5x worse (-$321 vs -$60). Failed on extended data |
| H1 FVG | OFF | Too coarse — reduced to 7 trades/12d |
| 2R Free Roll | ON (default) | breakeven at +1R, partial bank at +1.5R |

## Backtest Results (v2.30, 18 real-tick days, 0.01 lots)

| Metric | Value |
|---|---|
| Trades | 290 |
| Win Rate | **61.0%** |
| Total P&L | **+$298.6** |
| $/day | +$16.6 |
| Max Drawdown | $80.3 |
| Green days | 11/18 |
| BUY side | +$58.3 (59.5% WR) |
| SELL side | +$240.3 (62.2% WR) |
| TRAIN | +$183.7 |
| OOS | +$114.9 |
| Walk-forward | **YES ✅** |

## Current Status
- **Removed from Exness** (2026-05-27) — S1 v2.30 is stronger on every metric
- Could be useful as a diversifier on FTMO alongside S1

## Key Finding: SELL side is 4x stronger than BUY
The sell side (+$240, 62.2% WR) dramatically outperforms the buy side (+$58, 59.5% WR). This is likely because gold had a bearish bias during the test period. On a $126 account, running S3 alongside S1 creates too much drawdown risk.

## Files
- EA: [S3Trader.mq5](file:///C:/Users/zeesh/Documents/GitHub/turtle/mt5/S3Trader.mq5)
- Backtest: [v230_backtest.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/v230_backtest.py)
