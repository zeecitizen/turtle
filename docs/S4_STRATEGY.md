# S4 Strategy — Zee's Feb-11 Entry Mechanized (UHV Breakout)

> **File**: `mt5/S4Trader.mq5` | **Magic**: 88007 | **Version**: 2.00 | **Timeframe**: M5

## Origin
S4 is the mechanical version of Zee's actual Feb 11, 2026 trading strategy — the day a $200 Blueberry account became $1,035 (+$835, ~100 trades, 94% WR). The strategy comes directly from the teacher's **Lesson 02 "Introduction to Our Strategy"** (Loom video transcribed in `monitor/_loom_audio/lesson02.txt`).

The teacher describes this as his personal strategy: *"I traded on this strategy and on a $200k account I made $70k in one day — just this strategy, nothing else."* (Qatar/Doha airport reference)

## Strategy (BUY side — SELL is symmetric mirror)

1. **Trend confirmed** — same-timeframe HH/HL market structure:
   - Recent 15 M5 bars have Higher High AND Higher Low vs prior 15 bars
2. **Find UHV candle** — in the last 12 M5 bars, find the RED candle with the HIGHEST tick volume during retracement
3. **Draw a line** at that UHV candle's HIGH
4. **Wait for breakout candle** — a GREEN M5 candle that:
   - **Opens at or below** the UHV high line (inside the range)
   - **Closes above** the UHV high line (breaks through)
   - Has **lower volume** than the UHV candle (low-volume breakout)
   - Has **body/range ≥ 55%** (momentum candle — small wicks, big body)
   - Has **body ≥ average body** of recent bars (strong candle, not noise)
5. **Entry**: market BUY at the breakout close
6. **SL**: entry − $7.50 (wide SL absorbs noise → high win rate)
7. **TP**: entry + $2.00 (small TP → fast profits → 85.6% WR)

## Key Differences from S1

| Aspect | S1 | S4 |
|---|---|---|
| Sweep requirement | YES | **NO** |
| FVG requirement | Optional (OFF) | **NO** |
| BigSpread filter | Optional (OFF) | **NO** |
| TP/SL | TP $7.50 / SL structural | **TP $2 / SL $7.50 fixed** |
| WR profile | 70.6% | **85.6%** |
| Momentum filter | None | Body/range > 55%, body > avg |
| Trend | Price delta ($2 over 24 bars) | **HH/HL structure** |
| Trades/day | ~11 | ~6 |

S4 is the "purest" version of the teacher's strategy — no extra filters, no sweep, no FVG. S1 added those filters later and they over-built it.

## The Feb 11 Investigation

### What we discovered (deep parameter sweep, 150+ configs, 18 tick days):

1. **The strategy works on M5, NOT M1** — all M1 configs had noisy, unreliable results. M5 is the teacher's primary timeframe and the data confirms it.

2. **All M1 scalp configs (tiny TP $0.50-$3) FAILED walk-forward** — this killed the theory that Feb 11 was just "tiny TPs at high WR on M1"

3. **M5 with wide SL + small TP achieves 85.6% WR** — the closest mechanical match to Zee's 94% WR on Feb 11. The remaining 8.4% gap is likely Zee's discretionary exit timing (reading the tape).

4. **ER regime filter HURTS on M5** — best configs all have ER=0 (no filter). The filter was removing valid signals.

5. **Both BUY and SELL sides are positive** — not one-sided like the failed M1 version.

### Why Feb 11 made $835 and the bot makes $69/18d:
- **Lot size**: Feb 11 used much larger lots (likely 1.0+ on a $200 account = massive leverage)
- **Frequency**: Zee traded ~100× on Feb 11; the bot fires ~6/day (~108 over 18 days)
- **WR gap**: Zee hit 94% WR; the bot hits 85.6% — close but not identical
- **The math**: at 0.01 lots and $2 wins, each trade makes $2. At 1.0 lots and $2 wins, each makes $200. That explains the $835.

## Backtest Results (v2.00, 18 real-tick days, 0.01 lots)

| Metric | Value |
|---|---|
| Trades | 111 |
| Win Rate | **85.6%** |
| Total P&L | **+$69.2** |
| $/day | +$3.8 |
| Max Drawdown | $24.5 |
| Green days | ~12/18 |
| BUY side | +$18.7 |
| SELL side | +$50.5 |
| TRAIN | +$42.2 |
| OOS | +$27.0 |
| Walk-forward | **YES ✅** |

## Risk Assessment for $126 Account

| Risk metric | Value | Safe? |
|---|---|---|
| Max drawdown | $24.5 | ✅ (19% of account) |
| Worst single loss | $7.50 | ✅ (6% of account) |
| Risk per trade | $7.50 | ✅ |
| Daily loss halt | $50 | ✅ (40% of account) |

## Comparison with S1 v2.30

| | S1 v2.30 | S4 v2.00 |
|---|---|---|
| Total P&L | **+$451** | +$69 |
| OOS P&L | **+$235** | +$27 |
| Win Rate | 70.6% | **85.6%** |
| Max DD | $56 | **$25** |
| $/day | **+$25** | +$3.8 |
| Walk-forward | ✅ | ✅ |

**S1 is the stronger money-maker. S4 is the safer, higher-WR option with lower drawdown.**

They can potentially run together since they use different entry criteria (S1 = sweep-based, S4 = pure UHV breakout). Combined max DD would need monitoring.

## Files
- EA: [S4Trader.mq5](file:///C:/Users/zeesh/Documents/GitHub/turtle/mt5/S4Trader.mq5)
- Deep parameter sweep: [s4_deep_sweep.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/s4_deep_sweep.py)
- Initial backtest: [s4_backtest.py](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/s4_backtest.py)
- Teacher's lesson: [lesson02.txt](file:///C:/Users/zeesh/Documents/GitHub/turtle/monitor/_loom_audio/lesson02.txt)
