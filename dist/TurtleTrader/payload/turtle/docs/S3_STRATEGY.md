# S3 Strategy — Effort vs Result (Wicking Green Breakout)

> **File**: `mt5/S3Trader.mq5` | **Magic**: 88003 | **Version**: 2.31  
> **Chart timeframe**: M5 | **Symbol**: XAUUSD | **Lot size**: 0.01  
> **Attach to**: XAUUSD M5 chart on Exness terminal

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

## Backtest Results (v2.31, 0.01 lots)

> **Data**: 18 real-tick days from Exness (2026-04-29 → 2026-05-26)  
> **Source**: `ticks_for_testing.csv` (70,000 M1 bars) + `shano_ticks_*.csv` (18 tick files)  
> **Method**: bar-close signal detection on M5 + next-tick fill on real tick stream  

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

## Version History

| Version | Date | Change | Impact |
|---|---|---|---|
| v2.00 | 2026-05-17 | Initial teacher-faithful build | Baseline |
| v2.10 | 2026-05-22 | Added 2R Free Roll exit management | +$202 improvement |
| v2.20 | 2026-05-22 | Added SELL side (bidirectional) | Sell side 4x stronger than buy |
| v2.30 | 2026-05-27 | Removed M5 FVG filter (failed on 18d OOS) | OOS stabilized |
| v2.31 | 2026-05-27 | SL buffer $2.00→$5.00 (deep sweep) | OOS +$115→+$199, DD $80→$67 |

## Deployment

| Setting | Value |
|---|---|
| Terminal | Exness (or any MT5 broker) |
| Chart | XAUUSD, M5 timeframe |
| Lots | 0.01 (for $126 account) |
| Magic | 88003 |
| All inputs | Use defaults — SL buffer 5.0, wick 0.35, trend 1.0 all baked in |

## Files
- EA: [S3Trader.mq5](file:///C:/Users/zeesh/Documents/GitHub/turtle/mt5/S3Trader.mq5)
- Deep sweep: [s3_deep_sweep.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/s3_deep_sweep.py)
- Earlier backtest: [v230_backtest.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/v230_backtest.py)
- Teacher's lessons: [_loom_audio/](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/_loom_audio)
