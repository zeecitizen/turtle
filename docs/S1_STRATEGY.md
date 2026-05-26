# S1 Strategy — UHV Breakout with Sweep

> **File**: `mt5/S1Trader.mq5` | **Magic**: 88004 | **Version**: 2.30 | **Timeframe**: M5

## Origin
S1 is derived from the teacher's Lesson 02 "Our Strategy" but with additional filters:
- **Sweep requirement**: price must wick below the UHV candle's low before breaking above (trapping sellers)
- Originally also required BigSpread + H1 FVG filters, but these were **removed in v2.30** because they blocked 100% of live trades for 5 consecutive days

## Strategy (BUY side — SELL is symmetric mirror)

1. **Uptrend confirmed** — M5 close is $2+ higher than 24 bars ago (~2 hours)
2. **Retracement** — red candles appear in last 15 M5 bars
3. **Find UHV red** — the highest-volume red candle in that retracement (the "climax" — big sellers trying to push price down)
4. **Sweep** — a subsequent candle's low goes below the UHV candle's low (trapping those sellers)
5. **Breakout** — a green candle closes above the UHV candle's high, with its open at or below it (fresh transition, not continuation)
6. **Entry**: market BUY at the breakout close
7. **SL**: UHV candle's low − $2.00 buffer
8. **TP**: entry + $7.50

## Why These Parameters

| Parameter | Value | Rationale |
|---|---|---|
| SL buffer | $2.00 | Walk-forward winner. Tighter configs (0.10) all broke OOS — wider SL absorbs tick noise |
| TP | $7.50 | Walk-forward winner. $10 broke, $5 was weaker. $7.50 gave best OOS hold |
| BigSpread | **OFF** | Was blocking 100% of signals in live (zero trades in 5 days). The validated backtest ran without it |
| H1 FVG | **OFF** | The +$2166 backtest that validated S1 ran without H1 FVG. Stacking it with BigSpread killed all signals |
| 2R Free Roll | OFF | Structurally inert on S1: the SL sits at UHV low (often $5-15 below entry), so +1R can't arm before the $7.50 TP resolves |

## Backtest Results (v2.30, 18 real-tick days, 0.01 lots)

| Metric | Value |
|---|---|
| Trades | 197 |
| Win Rate | **70.6%** |
| Total P&L | **+$451.2** |
| $/day | +$25.1 |
| Max Drawdown | $55.9 |
| Green days | 15/18 |
| BUY side | +$182.6 (69.2% WR) |
| SELL side | +$268.6 (71.7% WR) |
| TRAIN | +$216.2 |
| OOS | +$235.1 |
| Walk-forward | **YES ✅** |

## Key Differences from Teacher's Strategy
- S1 adds a **sweep** requirement (teacher doesn't mention this)
- S1 uses M5 price-delta trend (not multi-timeframe HH/HL)
- S1 uses fixed TP ($7.50) not 1:1 R:R

## Live History
- v2.22 and earlier: **zero trades in 5+ days** due to BigSpread + H1 FVG stacked filters
- v2.30 (2026-05-27): filters removed, deployed on Exness @ 0.01 lots

## Files
- EA: [S1Trader.mq5](file:///C:/Users/zeesh/Documents/GitHub/turtle/mt5/S1Trader.mq5)
- Backtest: [v230_backtest.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/v230_backtest.py)
