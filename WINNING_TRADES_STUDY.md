# Winning Trades Study — anatomy of a clean streak

**Captured 2026-05-20.** Purpose: dissect a real winning sequence to record the
*elements* that made each trade succeed, so we keep reinforcing what works.

## The streak: 8 trades, 8 wins, +$87.18 (all at live lots)
Every winner today was **S3Trader (liquidity-sweep reversal, ID 88003)**. NSND and S1
fired ZERO — their stricter filters stood aside; S3 owned the trending day. All BUYS,
all hit TP, none stopped out.

| # | time (broker) | ref-red→green vol | vol ratio | entry | SL dist | TP dist | result |
|--|--|--|--|--|--|--|--|
| 1 | 03:10 | 724 → 1520 | **2.10×** | 4488.88 | 9.0 | 7.6 | **+$15.18** |
| 2 | 03:20 | 645 → 1581 | **2.45×** | 4492.13 | 12.6 | 4.3 | +$8.68 |
| 3 | 09:35 | 1488 → 1495 | 1.00× | 4467.00 | 7.6 | **11.3** | **+$22.74** |
| 4 | 10:50 | 996 → 1020 | 1.02× | 4479.22 | 6.2 | 6.7 | +$13.54 |
| 5 | 11:00 | 955 → 1174 | 1.23× | 4481.41 | 6.6 | 4.5 | +$9.16 |
| 6 | 11:20 | 1123 → 1413 | 1.26× | 4484.53 | 8.2 | 1.4 | +$3.12 |
| 7 | 13:50 | 902 → 914 | 1.01× | 4494.82 | 6.5 | 2.1 | +$6.51 (0.03) |
| 8 | 14:50 | 976 → 1239 | 1.27× | 4498.33 | 9.4 | 2.7 | +$8.25 (0.03) |

(vol ratio = the wicking-green candle's volume ÷ the retracement red it reclaimed)

## What every winning trade had in common (the winning DNA)

1. **Aligned with the dominant bias.** Gold dipped to ~4460 then trended up to ~4501 all
   day. Every trade was a BUY = *with* the trend. Zero counter-trend trades. (Teacher's
   rule: gold is bullish, favor buys.)
2. **A full confirmation stack, not one signal.** Each fired only when ALL of these lined up:
   uptrend (M5) + a real retracement (reds broke a prior green's low) + a green candle that
   **wicked below the red's low, closed back inside, on higher volume** (absorption) + an
   unfilled **M5 FVG** was tapped + the green's **upper wick ≤ 35%** (no rejection).
3. **Volume confirmed absorption.** The green's volume ≥ the red it reclaimed every time
   (1.00× to 2.45×). Note: even a *barely* higher ratio worked when the trend was clean
   (trades 3, 4, 7 were ~1.0×) — in a strong trend, structure mattered more than a big ratio.
4. **Structure-based TP auto-sized the reward.** TP = the peak of the last 10 M5 bars. The
   biggest winners (T3 +$22.74, T1 +$15.18) had the **largest TP distance** — they entered
   on a *deeper* pullback, leaving more room to the recent peak. Shallow pullbacks (T6) gave
   small wins. **Deeper pullback into the level = bigger reward.**
5. **A wide ($2) SL absorbed the sweep.** Every entry's stop sat well below the wick low, so
   the initial noise/re-test didn't knock them out before the move resumed. None stopped.
6. **Active-session timing.** All fired during London/NY hours (broker 03–15), where there's
   institutional volume to carry price to the structural TP. (The dead Asian hours produced
   nothing — by design.)

## The elements of a winning strategy (the durable lessons)

- **Trade with the higher bias, never against it.** A directional day + with-trend entries = streaks.
- **Stack confirmations.** No single candle is enough. Trend + retracement + volume absorption
  + FVG-at-its-own-timeframe + no-rejection wick = high conviction. Each filter we *kept* (M5
  FVG, upper-wick ≤0.35) is visible in these winners.
- **Let the stop be wide enough to survive the liquidity sweep.** Tight stops die in the noise;
  the sweep IS the setup.
- **Target structure, not a fixed number.** Letting TP = recent peak means reward scales with
  how much room the pullback created — deep pullbacks pay the most.
- **Patience pays.** S3 only took 8 trades all day; NSND/S1 took none. Standing aside in chop
  and only firing the A+ setups is *why* the streak stayed clean.

## Honest caveat (so we don't fool ourselves)
This was a **trending, bullish day** — the ideal regime for with-trend dip-buying. Streaks like
this are real but **regime-dependent**. On a choppy or sharply-reversing day the same rules
will take losses (e.g. 2026-05-19 had a −$45 cluster). The edge is not "8/8 forever"; it's
*positive expectancy over many days* (~65% WR, validated). This file records the **anatomy of
the wins** to reinforce the A+ pattern — not to promise it repeats every session.

— recorded by Claude, 2026-05-20
