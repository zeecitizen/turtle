# S3 Strategy — Effort vs Result (Wicking Green Breakout)

> **File**: `mt5/S3Trader.mq5` | **Magic**: 88003 | **Version**: 2.31 | **Timeframe**: M5

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
6. **SL**: breakout candle's low − $5.00 buffer
7. **TP**: highest high of last 10 M5 bars (structural target)

## SELL Side (added v2.30)
Mirror of buy: downtrend → find a recent red → collect greens that broke above it → red wicking candle breaks below green's high and closes back below → SELL. TP = lowest low of last 10 bars.

## Why These Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Upper wick limit | 35% | Filters exhaustion candles that wick up but close weak. Validated in backtest |
| SL buffer | **$5.00** | v2.31: raised from $2.00 after deep sweep (s3_deep_sweep.py, 150+ configs). OOS +$115→+$199, DD $80→$67. Wider SL absorbs noise |
| M5 FVG | **OFF** | 18-day backtest showed FVG makes OOS 5x worse (-$321 vs -$60). Failed on extended data |
| H1 FVG | OFF | Too coarse — reduced to 7 trades/12d |
| 2R Free Roll | ON (default) | breakeven at +1R, partial bank at +1.5R |
| Trend threshold | $1.00 | Minimum price movement over 24 M5 bars for trend confirmation |
| Retrace lookback | 30 bars | M5 bars to search for pivot candle |
| TP peak lookback | 10 bars | M5 bars for structural peak TP target |

## Backtest Results (v2.31, 18 real-tick days, 0.01 lots)

| Metric | v2.30 (SL $2) | v2.31 (SL $5) |
|---|---|---|
| Trades | 290 | 331 |
| Win Rate | 61.0% | **71.9%** |
| Total P&L | +$298.6 | **+$503.5** |
| $/day | +$16.6 | **+$28.0** |
| Max Drawdown | $80.3 | **$66.6** |
| Green days | 11/18 | **13/5** |
| BUY side | +$58.3 | +$12.2 |
| SELL side | +$240.3 | **+$491.4** |
| TRAIN | +$183.7 | **+$304.7** |
| OOS | +$114.9 | **+$198.8** |
| Walk-forward | YES ✅ | **YES ✅** |

## Deep Sweep Summary (2026-05-27)

150+ configs tested. Key findings:
- **Fixed TP configs** (TP12/SL7.5) had highest OOS (+$327) but with $144 drawdown — too risky for $126 account
- **Peak-based TP with wide SL** ($5.00) is the best balance: high OOS + low DD
- **SL buffer 0.10→2.00→5.00**: each step up improved results. The pattern is clear — wider SL lets trades breathe
- **Upper wick filter** (0.35) is validated — removing it (1.0) adds noise trades but doesn't help OOS
- **Trend threshold** $1.0 is sweet spot — $0.5 adds noise, $3.0 cuts too many valid signals

## Current Status
- **Ready to re-attach to Exness** alongside S1 v2.30 and S4 v2.00
- Risk per trade at 0.01 lots: max loss = SL $5 + buffer = ~$7-10 depending on structure

## Key Finding: SELL side dominates
The sell side (+$491, ~75% WR) is 40x stronger than BUY (+$12). This is consistent across all configs and appears structural during the test period (gold bearish bias). Both sides remain enabled because the buy side is still slightly positive and may perform differently in other market conditions.

## Files
- EA: [S3Trader.mq5](file:///C:/Users/zeesh/Documents/GitHub/turtle/mt5/S3Trader.mq5)
- Deep sweep: [s3_deep_sweep.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/s3_deep_sweep.py)
- Earlier backtest: [v230_backtest.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/v230_backtest.py)
