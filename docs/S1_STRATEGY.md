# S1 Strategy — UHV Breakout with Sweep

> **File**: `mt5/S1Trader.mq5` | **Magic**: 88004 | **Version**: 2.30  
> **Chart timeframe**: M5 | **Symbol**: XAUUSD | **Lot size**: 0.01  
> **Attach to**: XAUUSD M5 chart on Exness terminal

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

## Backtest Results (v2.30, 0.01 lots)

> **Data**: 18 real-tick days from Exness (2026-04-29 → 2026-05-26)  
> **Source**: `ticks_for_testing.csv` (70,000 M1 bars) + `shano_ticks_*.csv` (18 tick files)  
> **Method**: bar-close signal detection on M5 + next-tick fill on real tick stream  

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

## Deployment

| Setting | Value |
|---|---|
| Terminal | Exness (or any MT5 broker) |
| Chart | XAUUSD, M5 timeframe |
| Lots | 0.01 (for $126 account) |
| Magic | 88004 |
| All inputs | Use defaults — all parameters are baked into the code |

**Currently live on Exness** since 2026-05-27.

## Combined Portfolio (S1 + S3 + S4)

| EA | OOS $/day | MaxDD | WR | Signals differ? |
|---|---|---|---|---|
| S1 v2.30 | +$13.1 | $56 | 70.6% | Sweep-based entry |
| S3 v2.31 | +$11.0 | $67 | 71.9% | Wicking pattern |
| S4 v2.00 | +$1.5 | $25 | 85.6% | Pure UHV breakout |
| **Combined** | **~$25.6** | ~$148 worst case | — | All different entries |

The three EAs use **different entry signals** (S1=sweep, S3=wick, S4=pure breakout) so their drawdowns are partially uncorrelated. Worst-case simultaneous DD ($148) exceeds the $126 account, but this is statistically unlikely since the signals fire independently.

## Files
- EA: [S1Trader.mq5](file:///C:/Users/zeesh/Documents/GitHub/turtle/mt5/S1Trader.mq5)
- Backtest: [v230_backtest.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/v230_backtest.py)
- S3 deep sweep: [s3_deep_sweep.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/s3_deep_sweep.py)
- S4 deep sweep: [s4_deep_sweep.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/s4_deep_sweep.py)
- Teacher's lessons: [_loom_audio/](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/_loom_audio)
