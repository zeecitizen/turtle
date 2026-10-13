# Saad Strategy EA — Optimisation Report

*12 October 2026 · EA: `mt5/Saad_strategy_15min.mq5` (gold, 15-minute chart) · all tests in the MT5
Strategy Tester on Axi's real tick history, Jan 6 – Oct 8 2026*

> **Backtests are not guarantees.** Every number here comes from the past. Run any new version on
> demo first, and never trade money you can't afford to lose.

---

## 0. What changed from v1.09 to v1.14

### Settings that changed (these make the trading difference)

| Setting | v1.09 | **v1.14** | What it means |
|---|---|---|---|
| `InpSlPips` | 30 | **35** | Stop 35 pips ($3.50) beyond the setup candle instead of 30: a little more room for noise |
| `InpHamRatio` | 3.0 | **2.5** | A hammer / shooting star counts when its long wick is ≥ 2.5 × the body (was 3): a few more hammers accepted |
| `InpWickMin` | 0.35 | **0.45** | A pin bar's long wick must be ≥ 45% of the candle (was 35%): only clearer pin bars |
| `InpMinRangeAtr` | 0.50 | **0.55** | The setup candle must be ≥ 0.55 × ATR(14) tall (was 0.50): tiny candles skipped |
| `InpMaruBody` | 0.50 | **0.53** | A marubozu's body must be ≥ 53% of the candle (was 50%): only firmer push candles |
| `InpChopEr` | 0.10 | **0.11** | Choppy-market filter slightly stricter: skip when the efficiency ratio < 0.11 |

v1.13 brought the first three, which beat v1.09 on Jan–Jun, on the unseen Jul–Oct period and over
all 9 months. v1.14 added the last three: tuned on Jan–Jun only, then confirmed on Jul–Oct.

### Code that changed (no effect on trading unless switched on)

| Version | Change |
|---|---|
| v1.10 | **Trade log:** every setup, entry, CTC, TP1/TP2/TP3, stop move, day-close and exit is printed to the Experts tab, plus one CSV row per trade in `Common\Files` |
| v1.11 | Long rule "TP1 = next resistance when the 50 EMA is below the entry". It had a bug (set then reset), which v1.12 fixed. Fixed, the rule loses −$70k, so it is **off** (`InpLongResTp1 = false`) |
| v1.12 | **Retry back-off:** after the broker refuses a stop change, wait 3 s (60 s if the market is closed) instead of retrying on every tick. **Quiet tester logs**, which fixed the hung tests. New **test switches**, all off: entry modes (wait for the dip, liquidity sweep), stop modes (ATR, fixed $), partial close at TP1, risk-% sizing, daily loss %. |
| v1.13–v1.14 | Only the default settings above |

### Unchanged (same as v1.09)

- the setups: pin bar, marubozu and hammer on the 9 / 50 EMA, then a break of the candle within one candle
- the 75% CTC breakeven
- TP1 → $2 trailing stop → TP2 / TP3 ladder
- shutting losers 3 minutes before the daily close
- magic number 88302

### The effect (1 lot, real ticks, Jan 6 – Oct 8)

| | v1.09 | v1.14 |
|---|---|---|
| Net profit | +$150,893 | **+$206,705** (+37%) |
| Profit factor | 1.36 | **1.62** |
| Win rate | 44.6% | **47.8%** |
| Max drawdown | 10.0% | **5.5%** |
| Losing months | 1 | **0** |
| Trades | 1,007 | 867 (fewer, cleaner) |

---

## 1. Summary

| | Before (v1.09) | **Now (v1.14)** |
|---|---|---|
| Net profit at 1 lot (9 months) | +$151,473 | **+$205,259** |
| Net profit at 0.10 lot | about +$15,000 | **+$20,345** |
| Profit factor | 1.36 | **1.61** |
| Max drawdown | 10.0% | **5.6%** |
| Win rate | 44.6% | **47.3%** |
| Losing months (Jan–Oct) | 1 | **0** |
| Trades per day | 5.4 | 4.7 |

**At 0.10 lot (right for a $5,000 account), v1.14 makes about $110 on an average day, worst day
−$456, max drawdown 1.1%.**

---

## 2. Today's −$1,475.70 on the Axi demo — what happened

| # | Trade | Risk (1 lot) | Result |
|---|---|---|---|
| 1 | SELL 4204.36 → reached TP1 → trailed out at 4200.22 | $1,106 | **+$369.29** |
| 2 | SELL 4183.27 → reached TP1 → trailed out at 4182.06 | $1,242 | **+$117.84** |
| 3 | BUY 4179.80 → stop at 4171.06 (best was only +$0.39) | $874 | **−$782.03** |
| 4 | BUY 4173.08 → stop at 4159.84 (best was only +$2.39) | $1,324 | **−$1,180.80** |

### Trade by trade: why the losses outweighed the wins

| # | Stop distance (risk) | TP1 distance at entry | TP1 ÷ risk | Best move our way | Result |
|---|---|---|---|---|---|
| 1 SELL | $11.06 | $4.16 | 0.38 | +$6.23 | +$369 |
| 2 SELL | $12.42 | $2.54 | 0.20 | +$3.32 | +$118 |
| 3 BUY | $8.74 | $7.11 | 0.81 | **+$0.39** | −$782 |
| 4 BUY | $13.24 | $7.70 | 0.58 | **+$2.39** | −$1,181 |

- The win rate was 50%, but every trade **risked more than its first target**. Wins were therefore
  small and losses full-size.
- **Both losers never moved our way** and still ran to the full stop.
- Over the whole test period the EA profits because a few winners run far: the biggest was +$19k at
  1 lot. Today had no runner.

### Did the stop losses work?

**Yes, exactly.** Both losing trades closed at their stop price with no slippage. A stop loss limits
how much a trade can lose; it can't make the loss small if the trade is big.

### Why were the losses so big?

1. **The lot size, mainly.** 1 lot on a $5,000 account means each stop costs $870–1,320, which is
   17–26% of the account. At **0.10 lot**, today's losses would have been −$79 and −$118, and the
   day **−$148**.
2. **Both losses were longs bought into a falling day.** Gold fell from 4213 to 4160 during the
   session. Both trades bought a bounce at the 9 EMA against the bigger downtrend, and neither
   bounce came.
3. **The terminal is still running v1.11** (its log says `v1.11`). It has the older settings and a
   broken long rule. v1.14 is compiled in the terminal but not attached yet.

### How to prevent this

| Fix | What it does | Status |
|---|---|---|
| **1 lot needs a big enough account** | Zee's choice is 1 lot on $25,000. v1.14's worst drawdown at 1 lot was $13,794, which is 55% of $25k. Cutting the loss per trade is the priority | — |
| **Attach v1.14** | Bigger-candle and less-choppy filters skip weaker setups; drawdown halves (10% → 5.6%) | Ready in your terminal |
| **Higher-timeframe trend filter** | Only buy when the 1-hour (or 4-hour) trend is up; only sell when it's down. Both of today's losers were buys in a 1-hour downtrend | Built (v1.15), **testing now** |
| **Daily loss limit** (`InpDayLossPct`) | Stop for the day after losing X% of the day's starting balance | Built, **testing now** |
| Smaller risk cap (skip trades with a far stop) | Would have skipped #4 ($13.24 stop) | Tested: costs more profit than it saves (−$56k at a $12 cap) |
| **Minimum reward:risk** (`InpMinRR`) | Skip a trade whose TP1 is closer than X × its risk. At 1.0 it would have skipped all four of today's trades | Built (`Saad_guard`), **testing at 1 lot / $25k** |
| **Failure exit** (`InpFailBars`) | Close a trade still losing after N candles, before CTC/TP1. Today's losers never moved our way | Built, **testing** |
| **Structure exit** (`InpInvalid`) | Close when a candle closes back through the setup candle (its far side or its middle) before CTC/TP1 | Built, **testing** |

---

## 3. What was tested (about 330 Strategy Tester runs)

### 3.1 The data problem, found first
- Around Oct 10–11, Axi revised its stored gold history. Since then the MT5 tester throws away the
  real ticks for **about half of all minutes** (Jan–Jul: 48–68%) and invents smooth replacement
  ticks. This happens in your terminal too: your Oct 9–10 test logs were clean, your later ones
  aren't.
- Invented ticks flattered the EA, which is where the earlier "+$207k" came from. On real ticks the
  same EA made +$151k.
- **Fix:** I built a test symbol, `XAUUSD_TK`, from all 60.4 million real Axi ticks, with Axi's
  trading hours and costs. Every result in this report uses it, including Axi's $4/lot commission.

### 3.2 Your ideas, tested properly

| Idea | Versions tested | Result |
|---|---|---|
| **Tighter stop loss** (better reward:risk) | 18 (5–25 pips, ATR 0.5–1.5, fixed $2–10) | ❌ All worse. Gold's normal noise knocks out tight stops before the move. |
| **Wait for the dip after the breakout** | 15 (retest, 25/50/75/100% into the candle, 1–3 candles) | ❌ All worse. Strong breakouts don't come back; the ones that dip deep are mostly failing. |
| **Wait for the stop hunt (liquidity sweep), then enter** | 20 | ❌ All lost money. A sweep below the candle usually starts a real move against us. |
| **Partial close at TP1** | 3 | ❌ No gain |
| **2×ATR stop** | 1 | Looked great on Jan–Jun (PF 2.04), failed on Jul–Oct |
| **TP1 = next resistance for longs** (v1.11 rule) | 3 | ❌ −$70k. Off. |

**Research:** the published backtests I found point the same way.
- A study on NIFTY futures found that waiting for a retest doesn't beat taking the break.
- A US30 liquidity-sweep backtest worked only with a fixed 1:3 target on a different market.
- Sources are at the end.

### 3.3 Parameter tuning (what actually helped)

Method: tune on **Jan–Jun only**, then accept a change only if it also wins on **Jul–Oct**, data it
has never seen. That's what separates real improvements from luck.

| Version | Changes | Jul–Oct (unseen) | Full 9 months (1 lot) |
|---|---|---|---|
| v1.09 | — | +$37,958 | +$150,893 |
| v1.13 | stop 35 pips (was 30), hammer wick ratio 2.5 (was 3), pin wick ≥ 45% (was 35%) | +$48,220 | +$167,534 |
| **v1.14** | + minimum candle 0.55×ATR, marubozu body ≥ 53%, choppy filter 0.11 | **+$68,638** | **+$206,705** |

Rejected because they failed the unseen-data test:
- shorts with the old exit
- breaking by 0 pips
- risk cap $20 (more profit, but worst day −$8,451)

**Monthly at 1 lot (v1.14):**

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct 1–8 |
|---|---|---|---|---|---|---|---|---|---|
| +29.5k | +14.2k | +20.6k | +44.7k | +16.8k | +12.4k | +4.1k | +35.0k | +22.6k | +6.9k |

**Execution delay:** random delay barely changed it (+$205.3k / +$205.4k), so the result doesn't
depend on perfect fills.

**PrimeXBT check** (its own data, Sep 1–Oct 8): v1.13 made +$30.3k at 1 lot (+$3.0k at 0.10),
PF 1.52.

---

## 4. Small-account EAs (EA_20USD … EA_200USD)

Same strategy (v1.14) at the smallest trade size, 0.01 lot, at 1:1000 leverage. Each account size
was started at the beginning of 9 different months and run for a month.

| EA | Months losing more than half | Worst month end | Typical month end | Verdict |
|---|---|---|---|---|
| EA_20USD | 6 of 9 | $0.24 | $2.13 | ❌ Not viable |
| EA_40USD | 3 of 9 | −$0.42 | $220 | ⚠️ High risk |
| **EA_80USD** | **0 of 9** | $121 | $286 | ✅ Survived all 9 |
| **EA_100USD** | **0 of 9** | $100 | $280 | ✅ Survived all 9 |
| **EA_200USD** | **0 of 9** | $241 | $406 | ✅ Survived all 9 |

**Why $20 can't work:**
- The smallest trade on Axi and PrimeXBT is 0.01 lot.
- One stop at 0.01 lot costs $8–15, so two or three losses empty a $20 account.
- **Leverage doesn't make a loss smaller.** It only lowers the margin needed to open the trade.

**Doubling $20 to $40 in a day:** it happens occasionally by luck, but most attempts end at $0.

---

## 5. A version that trades more often (M5 / M1)

| Test | Trades per day | Result |
|---|---|---|
| 15-minute EA run on M5, 24 versions | 6–26 | ❌ Best profit factor 1.04; most lost money. Spread + commission eat the small moves. |
| **"Saad_mini" on M5/M1 with a 1-hour/4-hour trend filter**, 24 versions | — | ⏳ **Testing now** |

The 15-minute EA already earns daily on most days: at 0.10 lot about **4.7 trades a day, average
day +$110, typical day +$49**, about 55% green days.

---

## 6. What you should do now

1. **Remove v1.11 from the chart** (close or note any open trade first).
2. **Attach `Saad_strategy_15min` v1.14.** Inputs tab → **Reset**. Check the Experts tab says
   `v1.14`.
3. **1 lot needs at least $25,000** (Zee's plan). With less, use 0.10 lot per $2,500.
4. Keep **Algo Trading** on.
5. For small accounts: **EA_80USD or above only**, and on demo first.

## 7. Still being tested

- Saad_mini (M5/M1 with a trend filter): the frequent-trading goal
- The trend filter and daily loss limit on the 15-minute EA: aimed at days like today
- Tuning round 3 around v1.14

The results and full receipts are in `VERSION_HISTORY.md`. The raw data is in
`monitor/strategy_lab/zee_*.jsonl`.

### Sources
- [Break vs Retest study (TradingView)](https://fr.tradingview.com/script/SA4YoyNF-Breakout-Retest-Entry-Signals-the-Break-vs-Retest/)
- [Backrex liquidity-sweep backtest (US30)](https://backtrex.com/en/backtests/liquidity-sweep-dow-jones)
- [LuxAlgo: breakout-pullback](https://www.luxalgo.com/library/concept/breakout-pullback-continuation/)
- [LuxAlgo: Turtle Soup](https://www.luxalgo.com/library/concept/turtle-soup/)
- [Oxford Strat: Turtle Soup](https://oxfordstrat.com/?p=5614)

---

## 8. Take 50% profit at TP1 and move the rest to breakeven (Zee's rule, 12 Oct)

**The setting:** when the first target (TP1) is reached:
- close **half** the position (0.5 of 1 lot), with `InpPartialPct = 0.5`
- move the stop on the remaining half to **breakeven**, the entry price, with `InpTp1Be = true`

The rest then trails behind the price ($2 by default) and can never turn into a loss.

It is built into the test EA `Saad_guard` and is tested at **1 lot on a $25,000 balance**, Jan 6 –
Oct 8, real ticks, 200 ms delay.

| Version | Net | Win rate (deals) | PF | Biggest loss | Worst day | Max DD |
|---|---|---|---|---|---|---|
| v1.14 (current) | **+$206,705** | 47.8% | 1.62 | −$2,570 | −$3,966 | $13,271 (8.1%) |
| 50% at TP1, no breakeven | +$201,750 | 61.3% | 1.60 | −$2,570 | −$3,806 | $13,422 (8.4%) |
| **50% at TP1 + breakeven (Zee's rule)** | **+$202,222** | **61.3%** | 1.60 | −$2,570 | **−$3,806** | $13,422 (8.4%) |
| Breakeven at TP1 only | +$207,130 | 47.6% | 1.62 | −$2,570 | −$3,966 | $13,271 (8.1%) |
| 50% + breakeven + $3 trail on the rest | +$199,263 | 60.6% | 1.59 | −$2,570 | −$3,716 | $14,261 (8.3%) |
| 50% + breakeven + $5 trail on the rest | +$191,182 | 58.4% | 1.57 | −$2,570 | −$3,716 | $14,849 (9.5%) |

**What it does:**

- **Profit −$4,483 (−2%)** over 9 months. Half of every trade that reaches TP1 is banked there
  instead of riding the trail, and occasionally that half would have run much further.
- **The win rate jumps to 61%.** MT5 counts the TP1 half as its own winning deal, so most trades
  now show a win. Per position nothing changes: the same trades still lose.
- **Worst day improves a little:** −$3,806 vs −$3,966.
- **The biggest single loss does not change (−$2,570).** Losses happen *before* TP1, while the full
  lot is still open with the original stop. Banking half at TP1 cannot touch them.
- **Breakeven adds almost nothing.** At TP1 the $2 trail usually puts the stop past the entry
  already; breakeven matters only when TP1 is less than $2 from the entry.

**Verdict:** this rule makes days feel smoother (more wins, slightly smaller bad days) for about
2% of the profit. **It does not reduce the big losses like today's**, which all hit the stop
before TP1. To shrink those, the trade itself must be smaller:
- size by risk (`InpRiskUsd`, section 2)
- or cut trades whose first target is too close to the risk (minimum reward:risk)

### Confirmation backtests on Axi (1 lot, $25,000 start)

| Test | Data | Net | Trades (deals) | Win rate | PF | Biggest loss | Worst day | Green days | Max DD | Losing months |
|---|---|---|---|---|---|---|---|---|---|---|
| **Zee's rule**, random delay, run 1 | Axi real ticks, Jan 6–Oct 8 | **+$201,922** | 1,164 | 59.5% | 1.60 | −$2,556 | −$4,186 | 103 / 185 | $12,488 | 0 |
| **Zee's rule**, random delay, run 2 | Axi real ticks, Jan 6–Oct 8 | **+$207,971** | 1,164 | 59.9% | 1.62 | −$2,576 | −$3,967 | 107 / 185 | $12,736 | 0 |
| **Zee's rule**, 200 ms delay | XAUUSD.pro, Jan 1–Oct 11 | +$208,441 | 1,199 | 61.4% | 1.59 | −$2,546 | −$3,764 | 108 / 190 | $14,238 | 0 |
| v1.14 (no half close), 200 ms | XAUUSD.pro, Jan 1–Oct 11 | +$219,046 | 894 | 48.2% | 1.62 | −$2,546 | −$3,924 | 107 / 190 | $13,703 | 0 |

**Notes:**
- **Two data sets.** XAUUSD.pro is what you trade and test on. Its history currently contains
  invented ticks for about half the minutes (section 3.1), so its numbers run a little higher. The
  real-tick rows are the honest ones.
- **Win rate counts deals.** "Trades" are deals: each half close counts as its own deal. That is why
  the win rate shows about 60% for Zee's rule.
- **Same story on both data sets.** Zee's rule gives up about 2–5% of the profit, nudges the worst
  day down slightly, and leaves the biggest single loss unchanged.

**The MT5 reports, to open yourself:**
- `testing/ZeeRule_50pct_TP1_BE_realticks_1lot.htm`
- `testing/ZeeRule_50pct_TP1_BE_XAUUSDpro_1lot.htm`

**If you want it anyway:** set `InpPartialPct = 0.5` and `InpTp1Be = true`. Both are in the test EA
`Saad_guard` now and can be added to the main EA on request.

---

## 9. FVG tap "safe zone" (Zee's idea, 12 Oct)

**The idea:** a Fair Value Gap (FVG) is a three-candle gap. For a bullish FVG, candle 1's high and
candle 3's low don't overlap. Price often comes back to **tap** the gap, collecting the stops resting
there, before continuing. Once a large FVG has been tapped and has **held** (no candle closes
through it), the stop hunt has happened, so the area is treated as a **safe zone** for setups in the
same direction.

**Variants** (test EA `Saad_fvg`; 1 lot, $25,000, Jan 6 – Oct 8, real ticks):
- `InpFvgMode` 1: trade only within N candles after a same-side FVG was tapped and held.
  `InpFvgMode` 2: the setup candle itself taps the FVG.
- `InpFvgMinAtr`: only "large" FVGs, 0.3 / 0.5 / 1.0 × ATR.
- `InpFvgWin`: safe-zone length, 4 / 8 / 16 candles.
- `InpFvgTf`: FVGs from the 15-minute or the 1-hour chart.
- `InpFvgSl`: stop just beyond the FVG's far edge (5 / 10 / 20 pips), or the tighter of that and
  the normal stop.

| Variant | Trades | Win rate | Net | PF | Biggest loss | Worst day | Max DD |
|---|---|---|---|---|---|---|---|
| **v1.14 (no FVG filter)** | 867 | **47.8%** | **+$206,705** | **1.62** | −$2,570 | −$3,966 | $13,271 |
| FVG ≥ 0.3×ATR, safe 4 / 8 / 16 candles | 399–486 | 44.2–45.4% | +$41k / +$43k / +$46k | 1.24–1.27 | −$1,536 | −$3,258 to −$4,242 | $15.6k–16.9k |
| FVG ≥ 0.5×ATR, safe 4 / 8 / 16 candles | 311–382 | 44.0–47.6% | +$31k / +$31k / +$19k | 1.13–1.27 | −$1,536 | −$3,176 to −$3,258 | $13.3k–17.4k |
| FVG ≥ 1.0×ATR, safe 4 / 8 / 16 candles | 126–168 | 43.5–48.4% | +$18k / +$14k / +$12k | 1.17–1.36 | −$1,483 | −$3,832 | $8.8k–11.3k |
| Setup candle itself taps the FVG (0.3 / 0.5) | 225–280 | 43.9–45.3% | +$16k / +$9k | 1.11–1.15 | −$1,517 | −$3,258 | $15.9k–16.6k |
| 1-hour FVGs, safe 16 candles | 205 | 46.8% | +$19k | 1.25 | −$1,504 | −$2,987 | $15.3k |
| Stop beyond the FVG edge (5 / 10 / 20 pips) | 137–167 | 40.6–41.9% | **−$5k to −$7k** | 0.90–0.93 | −$1,587 | | |
| Tighter of normal / FVG stop | 341–501 | 42.3–44.3% | +$18k to +$30k | 1.13–1.15 | | | |

*(1-hour FVGs with an 8-candle window made 0 trades.)*

**Verdict: the FVG safe zone doesn't help this strategy.**
- It blocks 40–85% of the trades **without raising the win rate** (43–48% vs 47.8%).
- Profit collapses from +$207k to at most +$46k, and the drawdown is about as big.
- A stop beyond the FVG edge turns the strategy into a loser.
- Our setups' edge isn't "after the hunt": the EA's own break-of-the-candle entry already acts
  after a pullback to the EMA, and adding the FVG condition mostly removes good trades.

---

## 10. 200 EMA side filter (Zee's idea, 12 Oct)

**The rule:** on the 15-minute chart, **buy only when price is above the 200 EMA, sell only when it
is below.** Setting: `InpSideEma = 200` in the test EA `Saad_guard`; 100 / 150 / 300 are also
tested. 1 lot, $25,000, Jan 6 – Oct 8, real ticks.

The question is whether it raises the win rate (v1.14: 47.8%, +$206,705).

| Rule | Trades | Win rate | Net | PF | Biggest loss | Worst day | Max DD | Losing months |
|---|---|---|---|---|---|---|---|---|
| **No filter (v1.14)** | 867 | **47.8%** | **+$206,705** | **1.62** | −$2,570 | **−$3,966** | **$13,271** | **0** |
| **Buy above / sell below the 200 EMA** | 611 | 43.7% | +$53,271 | 1.21 | −$1,496 | −$5,313 | $19,226 | 3 |
| Same with the 100 EMA | 634 | 43.5% | +$64,740 | 1.25 | −$1,504 | −$5,313 | $19,616 | 6 |
| Same with the 150 EMA | 622 | 44.5% | +$67,777 | 1.27 | −$1,496 | −$5,313 | $13,190 | 4 |
| Same with the 300 EMA | 593 | 43.5% | +$65,645 | 1.26 | −$2,570 | −$5,313 | $21,235 | 3 |

**Verdict: no, it doesn't raise the win rate. It lowers it (47.8% → 43.7%)**, cuts profit by about
three quarters, and makes the worst day and the drawdown *worse*.

This strategy earns a lot of its money on the **first trades of a new trend**: buying the dip at the
EMA while price is still below the 200 EMA as a downtrend turns up (and the mirror image for sells).
The 200 EMA rule blocks exactly those trades and keeps the later ones, after the move has matured.
The earlier 1-hour / 4-hour trend filter failed for the same reason (section 2).

---

## 11. 5-minute variant: `Saad_strategy_5min` (13 Oct)

**What it is:** the 15-minute EA v1.17, including the half-at-TP1 + breakeven rule, rescaled for
5-minute candles:
- risk cap $9
- stop 20 pips beyond the candle
- choppy-filter window 48 candles (the same 4 hours as 16 on M15)

It has its own magic number (88320), so it can run beside the 15-minute EA.

**Testing:** 30 variants, 1 lot, real Axi ticks. Tuned on Jan–Jun, checked on Jul–Oct.

| Version | Jan–Jun | Jul–Oct (unseen) |
|---|---|---|
| v1.17 settings unchanged, on M5 | −$32,853 | −$20,853 |
| Rescaled (risk $9, stop 20 pips) | −$41,448 | +$2,569 |
| **Best on Jan–Jun: + 48-candle choppy window (the EA's defaults)** | **+$16,243** (PF 1.06) | **−$27,816** |
| Other 27 variants | −$60k to +$16k | — |

**Verdict: not profitable. Demo only.** On 5-minute candles each trade is small, and Axi's spread
plus $4/lot commission eat the edge. Results flip between periods, which is noise, not an edge. The
15-minute EA (v1.17) remains the one to trade.

## 12. Cutting the losing trades — 50 tests of the pasted suggestions (13 Oct)

**Why:** on 12 Oct, two winners made **+$365** and **+$114**, then two losers took **−$786** and
**−$1,185**. Both losers were LONGs that never moved in our favour (best price after entry +$0.39
and +$2.39).

**Setup:**
- v1.17 at 1 lot, $25k, Jan 6 – Oct 8, Axi real ticks (XAUUSD_TK + $4/lot), 200 ms delay
- test copy `mt5/Saad_cut.mq5` (built by `monitor/strategy_lab/patch_cut.py`)
- its baseline reproduces v1.17 to the cent (**+$202,221.80**)
- raw results: `monitor/strategy_lab/zee_cut.jsonl`

**Baseline:** +$202,222 · 867 trades · win rate 61.3% · PF 1.60 · average loss −$757 ·
biggest loss −$2,570 · worst day −$3,806.

### First list (stops, exits, filters)

| Idea | Net | Win rate | Average loss | Worst day |
|---|---|---|---|---|
| Stop cap `InpMaxRiskUsd` 3.5 / 4 / 5 / 6 | **0 trades** | – | – | – |
| Stop cap 8 / 10 | +$21k / +$40k | 56% / 53% | −$496 / −$655 | −$1.5k / −$2.9k |
| Hard $ cut −$300 / −$400 / −$600 / −$800 | **−$13k** / +$5k / +$41k / +$88k | 34–54% | −$293 to −$638 | −$4.4k to −$5.8k |
| Close after 4 / 6 / 8 / 12 candles (`InpMaxBars`) | +$77k / $105k / $119k / $134k | ~61% | −$656 to −$755 | −$4.4k to −$5.9k |
| Close if still losing after 4 / 6 / 8 candles | +$151k / $155k / $166k | 56–59% | ~−$680 | −$5.6k |
| Exit on a candle closing beyond the 9 EMA | +$96k | 54% | −$615 | −$4.7k |
| Cooldown after a loss, 2 / 3 / 4 candles | +$166k / $161k / $166k | 60–61% | ~−$770 | −$4.9k |
| Daily loss limit $600 / $800 / $1,500 | +$85k / $96k / $141k | 60% | ~−$790 | **−$2.6k / −$2.6k / −$2.8k** |
| Spread filter 25 / 35 points | +$193k / **+$203k** | 61% | −$761 | −$4.6k / −$3.8k |
| Choppy filter 0.14 / 0.16 / 0.18 | +$144k / $114k / $106k | 58–60% | ~−$770 | −$3.4k to −$4.7k |
| H1 / H4 trend filter | +$64k / +$83k | 57–58% | ~−$780 | −$4.7k / −$4.9k |
| 9 EMA above / below the 50 EMA (`InpTrendAlign`) | +$69k | 54% | −$752 | −$5.2k |
| Close above / below the 50 EMA (`InpPriceSide`) | +$73k | 55% | −$752 | −$4.3k |
| Full "recommended plan" (cap 4, 6 candles, cooldown 3, $600/day, align, H1) | **0 trades** | – | – | – |

### Second list (runner trail, pin bars, longs vs shorts)

| Idea | Net | Win rate | Worst day |
|---|---|---|---|
| Wider runner trail after TP1: $3 / $4 / $5 / $7 | +$199k / $194k / $191k / $197k | 57–61% | ~−$3.7k |
| Widen the trail $1 at each later TP (`InpTrailStepUsd=1`) | +$201k | 61% | −$3.8k |
| Old exit (ATR trail, `InpLongTouch=0, InpShortTouch=0`) | +$210k | **40%** | −$4.8k |
| Choppy filter 0.20 / 0.25 / 0.30 / 0.40 | +$84k / +$8k / +$8k / **−$10k** | 54–57% | |
| Pin bar body ≤ 0.3 / wick ≥ 0.6 / both | +$150k / $160k / $147k | 60% | −$3.4k to −$3.5k |
| Shorts only | +$102k | **65%** | −$3.9k |
| Longs only | +$53k | 52% | −$4.7k |

### Weekend gap

| Idea | Net | Biggest loss | Worst day |
|---|---|---|---|
| Close every trade, winners included, 3 min before every day's close | +$155k | −$1,565 | −$5.9k |
| **Close every trade 3 min before the FRIDAY close only** | **+$178.5k** | **−$1,565** | −$3.8k |

### What we learned

1. **The stop can't be shrunk.** It sits 35 pips beyond the setup candle, and gold's M15 candles are
   big. All 4,567 setups had a stop more than $6 away; yesterday's four trades were $9–13 away,
   winners included. A $3.5–6 cap means **no trades at all**.
2. **Cutting losers early cuts winners too.** The hard $ cut, time exits, fail-bars and the 9 EMA
   exit all made the average loss smaller. But they also closed trades that would have come back,
   so profit fell by $36k to $215k and the worst day got *worse*. The strategy needs room to
   breathe.
3. **No filter raised the win rate.** Every entry filter (trend, EMA alignment, price side,
   choppy, H1/H4, stricter pins) lowered it or kept it the same, and all cost profit.
4. **The quick runner exit isn't a bug.** 80% of runners close within 3 minutes of the 50%
   partial, on the $2 trail. They still made **+$161k in total (+$568 each)**. A wider trail made
   slightly less.
5. **The biggest loss of the year (−$2,612) was a weekend gap.** A short already at breakeven on
   Friday 24 Jul gapped $26 against us at Monday's open. The **Friday-close rule removes it**:
   biggest loss −$2,570 → −$1,565. It costs about $24k a year, because weekend gaps sometimes pay us
   too.
6. **The only real "bad day cap" is the daily loss limit.** At $1,500 it caps the worst day near
   −$2.8k for −$61k of profit.

### Options for Zee (none shipped yet — your choice)

| Option | What it buys | What it costs (Jan–Oct) |
|---|---|---|
| Keep v1.17 as is | most profit, +$202k | worst day −$3.8k, a rare weekend gap −$2.6k |
| + Friday flat (needs a new version) | no weekend gap, biggest loss −$1,565 | −$24k |
| + `InpDayLossUsd=1500` (an input, no new version) | worst day about −$2.8k | −$61k |
| + `InpMaxSpreadPts=35` (an input) | blocks news-spike entries | none measured |

**Not used:** the pasted "Python slippage model" step. Only MT5's tester can promote a change
(CLAUDE.md). All these runs already include a 200 ms delay.

## 13. Meta-labeling (XGBoost "second opinion" on each trade) — built and tested (13 Oct)

**What:** your two Meta-Labeling PDFs, implemented in `meta_labeling_system/` (see its README) and
`mt5/Saad_meta.mq5`. Before each entry, the EA computes 15 market features. An XGBoost model then
estimates the chance the trade ends in profit, and the trade is skipped if that chance is below a
threshold.

**Changes from the PDFs:**
- The model is **compiled into the EA** (`mt5/SaadMetaModel.mqh`), so MT5's tester can judge it.
  The tester can't call a web server.
- The PDF's FastAPI server + WebRequest gate is also built (`InpMetaMode=2`, `run_server.bat`), for
  live use.
- No mock data.
- Label = the trade's real final net, counting the 50% partial, runner and $4/lot.

**How it was tested (walk-forward):**
1. The EA logged all 867 trades of Jan 6 – Oct 8 from an unfiltered run (its total equals v1.17's
   +$202,221.80 to the cent).
2. The model trained on **Jan–Jun only** (502 trades).
3. MT5 then ran the gated EA on **Jul 1 – Oct 8, which the model never saw**.

The EA's in-tester probabilities match Python's to 1e-7 on all 469 entries.

| Jul 1 – Oct 8, 1 lot, real ticks | Net | Trades | Win rate | Worst day |
|---|---|---|---|---|
| **No filter (v1.17)** | **+$67,681** | 365 | 60% | −$3,806 |
| model ≥ 0.40 | +$33,169 | 321 | 64% | −$5,092 |
| model ≥ 0.45 | −$1,723 | 284 | 63% | −$4,415 |
| model ≥ 0.50 | −$25,502 | 182 | 63% | −$4,415 |
| model ≥ 0.55 | −$13,996 | 172 | 67% | −$3,578 |
| model ≥ 0.60 | −$4,151 | 116 | 68% | −$3,324 |
| model ≥ 0.65 | −$2,090 | 65 | **70%** | −$1,660 |

(Trades = positions. The win rate is MT5's, counted per deal.)

**Verdict: REJECTED.**
- **The win rate does go up, from 60% to 70%, but profit collapses.** The model learns to skip the
  trades that look risky, and those include the rare big winners that pay for everything (the
  largest single win was +$19k).
- **Even inside the training months, every threshold made less than taking every trade.**
- Same lesson as §12: on this strategy, filtering for win rate costs money.

`Saad_strategy_15min` v1.17 is untouched. The meta-labeling system stays in the repo, ready to
retrain on more data later: `py meta_labeling_system\src\train_metalabel.py`.

## 14. Meta-labeling, regression version (predict the trade's net $) — tested (13 Oct)

**The idea:** the §13 classifier treated a +$50 trade the same as a +$19k runner, so it cut the
big winners. This version predicts each trade's **net dollars** instead (XGBoost
`reg:squarederror`) and skips a trade when the prediction is below a $ threshold. Optionally,
trades are weighted by |net $| so the big ones count more.

**Files:** `meta_labeling_system/src/train_metalabel_reg.py`; models `models/meta_model_xauusd_reg_*.pkl`
and `mt5/SaadMetaModel_reg_*.mqh`. `api_server.py --model <pkl>` serves it live.

**Method:** same data and walk-forward as §13.
1. Train on Jan–Jun (502 trades).
2. Pick the threshold inside Jan–Jun.
3. MT5 runs the gated EA on the unseen **Jul 1 – Oct 8**.

Exported trees match XGBoost to under 1 cent.

| Jul 1 – Oct 8, 1 lot, real ticks | Net | Trades | Win rate | Biggest win | Worst day |
|---|---|---|---|---|---|
| **No filter (v1.17)** | **+$67,681** | 365 | 60.1% | +$11,511 | −$3,806 |
| weighted by \|$\|, depth 3, skip if predicted < $0 (the pasted spec) | +$48,420 | 276 | 61.0% | +$11,511 | −$4,659 |
| same, skip if < −$250 (picked on Jan–Jun) | +$53,041 | 308 | 59.3% | +$11,511 | −$4,659 |
| unweighted, depth 3, < $0 | +$40,437 | 275 | 61.3% | **+$8,412** (the $11.5k runner was skipped) | −$4,659 |
| unweighted, depth 3, < −$250 | +$63,386 | 319 | 60.6% | +$11,511 | −$4,659 |
| weighted, depth 2, < $0 | +$67,961 | 359 | 59.7% | +$11,511 | −$3,989 |
| weighted, depth 2, < −$500 (picked on Jan–Jun) | +$67,681 | 365 | 60.1% | +$11,511 | −$3,806 |
| unweighted, depth 2, < $0 | +$58,363 | 298 | 60.8% | +$11,511 | **−$2,875** |
| unweighted, depth 2, < −$250 | +$66,832 | 364 | 60.0% | +$11,511 | −$3,806 |

**Verdict: REJECTED. No regression model beats taking every trade.**
- **Weighting by $ does keep the big runners**, so the losses are much smaller than the
  classifier's in §13. But no variant made more money.
  - The best, weighted depth 2 at $0, made +$280 more by skipping 6 trades, with a worse worst
    day. That's noise.
  - The threshold picked on Jan–Jun (−$500) skipped nothing at all.
- **The pasted spec** (weighted, depth 3, $0) made **−$19k** less than no filter.
- **One interesting row:** unweighted depth 2 at $0 cut the worst day to −$2,875 for −$9k of
  profit. That's about the same trade-off as the `InpDayLossUsd` daily limit (§12), which is simpler
  and needs no model.

**Why:** with only about 500 trades to learn from, there isn't enough information in these 15
features to tell, at entry, which trades will lose. The same lesson came from the 50 filter tests in
§12.

v1.17 stays untouched.

## 15. Market-regime detection (GMM) — built and tested (13 Oct)

**The idea:** don't veto trades. Classify the market's state each candle, then adapt the EA's
settings to it:

| Regime | Settings |
|---|---|
| **TREND** | no breakeven at TP1; after TP1, trail by 2.5× ATR instead of the $2 trail; choppy filter 0.10 |
| **CHOP** | choppy filter 0.35 |
| **NORMAL** | choppy filter 0.15 |

**Files:**
- `mt5/Saad_regime.mq5` (built by `monitor/strategy_lab/patch_regime.py`)
- `meta_labeling_system/src/train_regime_gmm.py`
- `mt5/SaadRegimeModel.mqh` (the GMM compiled into the EA)
- `regime_server.py` (optional)

**How:**
1. Every closed M15 candle, the EA computes ER(14), ATR14/ATR200 and 14-candle realized volatility.
   With logging on, its trades match v1.17 to the cent.
2. A 3-cluster Gaussian Mixture is fitted on **Jan–Jun candles only** (11,435).
3. MT5 runs the adaptive EA on the unseen **Jul 1 – Oct 8**.

The EA's regime matches scikit-learn's on all 17,940 candles, and on 6,506 out of 6,506 candles
inside the tester.

**What the clusters turned out to be:**

| Cluster | ER | ATR14/ATR200 | Realized vol | Share of candles |
|---|---|---|---|---|
| TREND | 0.42 | 1.46 | 0.0044 | 9% |
| CHOP | 0.21 | 1.13 | 0.0021 | 27% |
| NORMAL | 0.27 | 0.85 | 0.0011 | 64% |

"TREND" is really **high-volatility spikes**, and v1.17 almost never trades in them (6 trades all
year). The CHOP trades are profitable: +$22.5k in Jan–Jun, +$13.1k in Jul–Oct.

| Jul 1 – Oct 8, 1 lot, real ticks | Net | Trades | Win rate | Biggest loss | Worst day |
|---|---|---|---|---|---|
| **v1.17, no regimes** | **+$67,681** | 365 | 60.1% | −$2,570 | −$3,806 |
| Full mapping as pasted | +$23,206 | 302 | 57.5% | −$1,516 | −$2,782 |
| Only CHOP choppy filter 0.35 | +$50,104 | 340 | 59.2% | −$1,516 | −$3,989 |
| Only NORMAL choppy filter 0.15 | +$40,847 | 332 | 58.7% | −$2,570 | −$2,788 |
| Only TREND exits (no breakeven, 2.5× ATR trail) | +$67,427 | 365 | 60.1% | −$2,570 | −$3,806 |

**Verdict: REJECTED.**
- **The regime-based exits in TREND change almost nothing (−$254),** because the EA barely trades
  in that state.
- **All the damage comes from the stricter choppy filter.** It blocks good CHOP and NORMAL trades.
  Even blocking only the CHOP ones costs $17.6k.
- **The full mapping cuts the worst day** (−$2.8k) at a cost of **−$44k in 3 months**, a much worse
  trade-off than the simple `InpDayLossUsd` limit.

**Same lesson as §12–14:** v1.17's setups are profitable in every market state these features can
tell apart, so switching behaviour by state removes good trades.

v1.17 stays untouched.

## 16. "v1.18" macro risk controls — TESTED ONLY, not shipped (13 Oct)

Zee: *"don't ship v1.18.. just test.."*. The code lives in a test copy, `mt5/Saad_v118test.mq5`
(built by `monitor/strategy_lab/patch_v118.py`). `Saad_strategy_15min.mq5` is still v1.17.

**What was built (the pasted spec, with two safety changes):**
- **Daily loss circuit breaker:** when today's equity (including open trades) is **$1,500** below the
  day's start, close this EA's trades and take no new ones until the next server day.
- **Friday close:** from **21:30 server time** on Friday, close this EA's trades and take no new
  ones. Optionally, the time can instead be 3 min before the broker's own close.
- **Change 1:** only this EA's positions (its magic and symbol) are closed, never manual trades or
  another EA's.
- **Change 2:** trade management keeps running after a trigger. The spec's early `return` from
  `OnTick` would freeze trailing stops.

With both off, the test copy reproduces v1.17 to the cent.

| Jan 6 – Oct 8, 1 lot, real ticks, 200 ms | Net | Trades | Win rate | Biggest loss | Worst day | Max DD | Losing months |
|---|---|---|---|---|---|---|---|
| **v1.17 (both off)** | **+$202,222** | 867 | 61.3% | −$2,570 | −$3,806 | $13.4k | 0 |
| **v1.18 as pasted** ($1,500 close-all + Friday 21:30) | +$82,522 | 708 | 57.6% | −$1,565 | **−$1,826** | $23.1k | 2 |
| $1,500 close-all daily limit only | +$93,981 | 708 | 57.8% | −$2,570 | −$2,570 | $18.6k | 2 |
| Old daily limit $1,500 (stops new trades only, §12) | +$140,900 | 770 | 60.3% | −$2,570 | −$2,821 | $17.6k | 1 |
| Friday close 21:30 only | +$175,244 | 859 | 61.0% | −$1,565 | **−$4,377** | $16.9k | 0 |
| Friday close 3 min before the broker's close only | +$178,517 | 874 | 61.3% | −$1,565 | −$3,806 | $15.2k | 0 |

**What it shows:**
1. **The pasted v1.18 does cap the bad day** (−$3,806 → −$1,826), but it costs **$120k of $202k (59%)**.
   It also makes the account's drawdown *bigger* ($13.4k → $23.1k) and adds 2 losing months.
   - The close-all limit shuts trades that were down but would have recovered, often runners that
     were going to come back. It then sits out the rest of the day.
2. **"Stop new trades only" is much cheaper than "close everything":** +$141k vs +$94k, for nearly the
   same worst day (−$2.8k vs −$2.6k).
3. **Friday 21:30 is worse than closing at the broker's close.** It cuts trades 2½ hours early,
   which gave a *new* worst day (−$4,377, a Friday trade closed at a loss). Closing 3 min before
   the real close removes the weekend gap (biggest loss −$1,565) with the worst day unchanged.

**If Zee wants protection, the cheapest combination measured:**

| Setting | Cost (Jan–Oct) | Buys |
|---|---|---|
| Friday close 3 min before the broker's close | −$24k | no weekend gap: biggest loss −$2,570 → −$1,565 |
| + daily limit that only stops new trades (`InpDayLossClose=false`) | about −$61k more | worst day about −$2.8k |

Not shipped. Waiting for Zee's decision.

## 17. In-trade exhaustion classifier (close a winning trade when "momentum is dying") — tested (13 Oct)

**What:** at every M15 candle close, an XGBoost model looks at each open, profitable position and
closes it when its probability is at least the threshold (0.85 in the paste).

**Files:**
- `mt5/Saad_exhaust.mq5` (built by `patch_exhaust.py`)
- `meta_labeling_system/src/train_exhaustion.py`
- `mt5/SaadExhaustModel.mqh` (the model compiled into the EA; matches XGBoost to 2e-7)
- `exhaustion_server.py` (optional, live)

**Changes from the paste:**
- **No synthetic data.** The EA logged every open position at every candle of the year: 5,392
  position-candles from 867 trades, with totals equal to v1.17's +$202,221.80.
- **A different label.** The paste asked "does price reverse within 3 bars?". This one asks **"would
  closing at this candle have booked more than the way v1.17 really closed the trade?"**
  (realized so far + open profit now vs the trade's final profit). That's the question that
  matters for money.

**Features:** side, candles held, open profit in R, best so far in R, giveback from best, ER now,
distances to the 9/50 EMA, ATR ratio, stage (before TP1 / after TP1 / riding), room to the stop,
last candle body, hour, share of the position still open.

**Training:** Jan–Jun only. Even there, closing early at every threshold made **less** than holding
(−$71k at 0.55, −$21k at 0.85, −$5k at 0.95).

| Jul 1 – Oct 8 (unseen), 1 lot, real ticks | Net | Trades | Win rate | Early closes | Biggest win | Worst day |
|---|---|---|---|---|---|---|
| **v1.17** | **+$67,681** | 365 | 60.1% | – | +$11,511 | −$3,806 |
| model ≥ 0.85 (the paste) | +$68,020 | 378 | 62.1% | 44 | +$11,511 | −$3,611 |
| model ≥ 0.75 | +$47,189 | 398 | 65.3% | 86 | +$8,412 | −$3,611 |
| model ≥ 0.95 | +$66,600 | 365 | 60.1% | 1 | +$11,511 | −$3,806 |

**Verdict: no real improvement. Not adopted.**
- **0.85 made +$339 more over 3 months (+0.5%) by closing 44 trades early.** That's within noise,
  and in Jan–Jun the same rule *lost* $21k.
- **At 0.75 the win rate rises to 65%, but profit falls by $20k.** The model cut the $11.5k runner,
  the same "higher win rate, less money" pattern as §13.
- **The data explains why:** in Jan–Jun, closing at a given candle beat holding only **50.2%** of
  the time, a coin flip. The features can't tell which runners are about to die.

### 17b. "65% win rate": does it mean fewer losing trades? Trade by trade (Zee's question)

Jul 1 – Oct 8. v1.17 and the 0.75 exhaustion exit were both re-run with every trade's full result
logged (the 50% partial and the runner counted as **one** trade), then matched trade by trade.

| Jul–Oct, per TRADE | Trades | Winners | **Losers** | Trade win rate | Avg win | Avg loss | All wins | All losses | Net |
|---|---|---|---|---|---|---|---|---|---|
| **v1.17** | 365 | 171 | **194** | 46.8% | $1,201 | −$710 | $205,359 | −$137,678 | **+$67,681** |
| exhaustion ≥ 0.75 | 398 | 216 | **182** | 54.3% | $892 | −$800 | $192,760 | −$145,571 | +$47,189 |

**Why MT5 says 60% / 65% but this table says 47% / 54%:** MT5's win rate counts *deals*, and the
50% partial at TP1 is a separate winning deal. Per whole trade, v1.17 wins 47% of the time and makes
its money because the average win ($1,201) is much bigger than the average loss ($710).

**What the exit really did:**
1. **It saved some losers.** It closed 86 trades early. Of the 72 that also exist in v1.17,
   **27 would have ended as losses** and were closed in profit instead. On 52 of the 72, closing
   early beat holding.
2. **It killed the big winners.** The other 20 were runners cut short:
   - **$11,511 → $194**
   - $5,721 → $1,113
   - $5,267 → $768
   - $4,877 → $290
   - $3,153 → $222

   The 52 small wins don't pay for these.
3. **Losing trades fell only from 194 to 182 (−12), not −27.** Closing trades early frees the EA to
   take setups it used to skip while busy. That added 50 new trades (net −$1,932), with their own
   losers.
4. **The average loss got *bigger*** (−$710 → −$800), while the average win shrank ($1,201 → $892).

**Answer:** the higher win rate is real, and there are slightly fewer losing trades (−12 in 3
months). But it comes from booking many small wins early and cutting the few big runners that pay
for the strategy, so net profit falls by **$20,492 (−30%)** in 3 months. More winning trades
doesn't mean more money: what decides profit is (win rate × average win) − (loss rate ×
average loss).

## 18. Optuna (Bayesian optimisation over 10 settings) — 92 real MT5 runs (13 Oct)

**What:** your Optuna pipeline, `monitor/strategy_lab/optuna_mt5.py`. Every trial is a real
Strategy Tester run.

**Changes from the paste:**
- **Rigs, not your live terminal:** it ran on the test rigs (3 in parallel, one shared study), never
  the terminal you trade on.
- **No `OnTester()` edit:** metrics come from MT5's own report.
- **Same data as everything else:** XAUUSD_TK real ticks + $4/lot, 1 lot, $25k, 200 ms delay.

**Search space:**
- the pasted six: EMA fast 5–15, EMA slow 30–80, chop ER 0.05–0.25, ATR trail 1–4, pin wick 0.30–0.60,
  pin body 0.20–0.60
- plus four already-tuned settings: stop 20–50 pips, marubozu body 0.40–0.70, minimum range
  0.30–0.80 ATR, hammer ratio 1.5–3.5

**Fitness:** the paste's own: net × win rate, minus 3 × max drawdown above $2,500.
**Tuned on:** Jan 6 – Jun 30 only. Trial 0 = v1.17's settings.

**Result on Jan–Jun:** after 92 trials, **no setting beat v1.17**, on fitness or on net. v1.17 made
+$134,541; the best alternative made +$99,598.

**The 5 best alternatives on the unseen Jul 1 – Oct 8:**

| Settings | Jan–Jun net | **Jul–Oct net** | Win rate | Max DD | Worst day |
|---|---|---|---|---|---|
| **v1.17** | **+$134,541** | **+$67,681** | 60.1% | $13.3k | −$3,806 |
| trial 83 (EMA 9/34, trail 1.0, range 0.65) | +$99,598 | +$24,213 | 62.0% | $14.0k | −$3,470 |
| trial 46 (EMA 9/33, trail 1.1) | +$92,194 | +$34,481 | 60.2% | $13.5k | −$3,470 |
| trial 51 (EMA 8/34, trail 1.5, range 0.70) | +$94,276 | +$52,717 | 62.5% | $9.9k | −$3,789 |
| trial 38 (EMA 10/37, trail 1.2) | +$86,547 | +$31,029 | 60.5% | $10.7k | −$3,896 |
| trial 88 (EMA 6/40, wick 0.55, ham 3.25) | +$88,915 | +$10,797 | 58.6% | $20.6k | −$4,699 |

**Verdict:** v1.17 already sits at the top of this 10-setting space, on both the tuning months and
the unseen months.
- Optuna kept circling back to v1.17's stop (35), chop ER (0.11) and pin wick (0.45).
- Every alternative it found made **less** on the unseen months, by 22–84%.

Nothing to change. The study is saved in `monitor/strategy_lab/optuna_saad.db`; every trial is in
`zee_optuna.jsonl`.

## 19. Deep reinforcement learning position sizing (PPO) — 4 agents, MT5 holdout (13 Oct)

**What:** your PPO pipeline. Before each entry, an agent chooses a lot multiplier from **0 to 2**
(Zee: up to 2 lots is fine). Its reward is log wealth growth, the Kelly objective.

**Files:**
- `meta_labeling_system/src/drl_train.py` (Stable-Baselines3 PPO, PyTorch 2.14)
- `mt5/Saad_drl.mq5` (built by `patch_drl.py`)
- `mt5/SaadDrlPolicy*.mqh`: the policy network compiled into the EA. It matches PyTorch to 5e-7 on
  every MT5 entry.

**How:**
1. The EA logged, at every entry, the observation it will use: ER(14), ATR14/ATR200, realized
   volatility, distance to the 50 EMA, and side. It also logged the trade's final net at 1 lot. The
   logging run equals v1.17 to the cent.
2. PPO trained on **Jan–Jun trades only**.
3. MT5 ran the sized EA on **Jul 1 – Oct 8**.

**The fair benchmark** is a **constant lot equal to the agent's own average size**. That separates
smart timing from simply betting bigger.

| Jul 1 – Oct 8 (unseen), MT5, real ticks | Agent avg size | **PPO net** | Constant-lot net | PPO max DD | Constant DD | PPO worst day | Constant worst day | Net÷DD PPO / constant |
|---|---|---|---|---|---|---|---|---|
| seed 0 | 1.77 | **+$126,025** | +$119,810 | $18.9k | $23.5k | −$7,563 | −$6,736 | **6.7** / 5.1 |
| seed 1 | 1.34 | **+$115,080** | +$90,693 | $18.4k | $17.8k | −$5,934 | −$5,099 | **6.3** / 5.1 |
| seed 2 | 1.53 | +$87,808 | **+$103,567** | $28.9k | $20.3k | −$7,437 | −$5,823 | 3.0 / **5.1** |
| seed 3 | 1.59 | +$109,356 | +$107,628 | $25.4k | $21.1k | −$6,792 | −$6,051 | 4.3 / **5.1** |
| (1 lot, v1.17) | 1.00 | | +$67,681 | | $13.3k | | −$3,806 | 5.1 |

**Verdict: interesting, but NOT reliable enough to use.**
- **2 of 4 agents beat their benchmark clearly** (seeds 0 and 1: +$6k and +$24k, net÷DD 6.3–6.7 vs
  5.1).
- **The other 2 were worse** (seed 2: −$16k and a bigger drawdown) or no better (seed 3).
- **The worst day was worse than the benchmark in all 4.** The agents bet near 2 lots on the days
  that went badly.
- With identical data and settings, only the random seed decides whether the agent helps or hurts.
  That's the signature of noise, not a learned edge. In Python on Jan–Jun, every agent "made"
  $272–291k vs $136k at 1 lot: heavy overfitting.

**Simple, honest alternative now that 2 lots is allowed:** constant sizing scales profit and
drawdown together (net÷DD stays 5.1). At **2 lots constant**, Jul–Oct would be roughly +$135k with
about $26.6k max DD and about a −$7.6k worst day. That's simply v1.17 × 2, with no model to trust.

## 20. "Mature runner" exit: hand long-running winners to H1/H4 structure — tested (13 Oct)

**What:** `mt5/Saad_mature.mq5` (built by `patch_mature.py`).
- **When a trade becomes MATURE:** after 20 candles open while in profit, and/or at +3R.
- **What changes:** the EA stops all M15 management of it ($ trail, ATR trail, EMA exits,
  breakeven). Once per candle, the stop goes to the previous **H1** or **H4** swing low/high minus
  10 pips, or to a **3–4× ATR** trail from the best price.
- **Rules for the stop:** never worse than the entry, and it only tightens after the switch.
- **Not modelled:** swap (Zee: "we're not worried about swap").

Every run: 1 lot, $25k, Jan 6 – Oct 8, real ticks, 200 ms.

| Version | Net | Jan–Jun | Jul–Oct | Max DD | Biggest win | Worst day | Losing months |
|---|---|---|---|---|---|---|---|
| **v1.17** | **+$202,222** | +$134,541 | +$67,681 | **$13.4k** | +$19,088 | **−$3,806** | 0 |
| H4 swing, mature by time or +3R | +$211,408 | +$131,108 | +$80,301 | $44.4k | **+$55,237** | −$5,926 | 1 |
| H4 swing, mature by time only | **+$225,839** | +$158,303 | +$67,536 | $44.4k | +$55,237 | −$5,264 | 1 |
| H1 swing, mature at +3R only | +$203,525 | +$124,748 | +$78,778 | $18.6k | +$18,595 | −$5,926 | 0 |
| H1 swing, time or +3R | +$176,454 | +$99,887 | +$76,567 | $22.2k | +$18,595 | −$5,926 | 0 |
| H1 swing, time only | +$161,396 | +$98,393 | +$63,003 | $22.2k | +$15,676 | −$5,264 | 0 |
| H1 swing, 20-pip buffer | +$174,095 | +$98,690 | +$75,405 | $22.3k | +$18,475 | −$5,926 | 0 |
| 3× ATR trail | +$173,731 | +$106,672 | +$67,059 | $20.4k | +$17,814 | −$5,264 | 1 |
| 4× ATR trail | +$177,744 | +$108,205 | +$69,538 | $22.0k | +$16,428 | −$5,264 | 1 |
| 3× ATR, time only | +$168,157 | +$102,844 | +$65,313 | $20.4k | +$17,814 | −$5,264 | 1 |

**What it shows:**
1. **The H4 exit does catch a monster.** One trade made **+$55,237** (v1.17's biggest is $19k). But
   the max drawdown **triples** ($13.4k → $44.4k, 37% of the account), May turns negative, and it
   trades on fewer days, because a held runner blocks new setups (one position at a time).
2. **No version is better in both halves of the year:**
   - "H4, time only" wins Jan–Jun (+$24k) and ties Jul–Oct.
   - "H4, time or +3R" loses Jan–Jun and wins Jul–Oct (+$13k).
   - "H1 at +3R" is −$10k then +$11k, about the same as v1.17 in total, with a bigger drawdown.

   An edge that flips between halves is mostly the luck of which trends happened.
3. **Every version makes the worst day worse** (−$5.3k to −$5.9k vs −$3.8k). Wider stops give back
   more on reversal days, the "+$12k collapsing" risk the paste itself warned about.
4. **The H1 and ATR versions lose $25–41k.** The quick $2 trail after TP1 really is better for M15
   setups than wide structure stops (same finding as §12's wider-trail test).

**Verdict: not adopted.** The only version with more profit (H4) buys it with 3× the drawdown and
relies on one huge trade. If Zee wants more profit and accepts bigger drawdowns, **2 lots on plain
v1.17** gives about 2× the profit for 2× the drawdown, which is a better deal than the H4 exit
(+12% profit for 3.3× the drawdown).

## 21. Scale-in pyramiding (anti-martingale "grid") — tested (13 Oct)

**What:** `mt5/Saad_pyramid.mq5` (built by `patch_pyramid.py`).
- While v1.17's trade is open and price has moved **X pips beyond the last entry**, add a position of
  **0.5×** the last one's size, up to 3 positions in total.
- **Breakeven lock** (the spec's step): when an add-on fills, every stop moves to the basket's
  average entry + 20 points.
- **One change from the paste:** add-ons are tracked as add-ons. They always carry at least the base
  trade's stop and close with the base trade, so the EA doesn't "adopt" them as new trades with their
  own exits.

Every run: base 1 lot, $25k, Jan 6 – Oct 8, real ticks, 200 ms.

| Version | Net | Jan–Jun | Jul–Oct | Max DD | Net ÷ DD | Worst day | Losing months |
|---|---|---|---|---|---|---|---|
| **v1.17 (1 lot)** | **+$202,222** | +$134,541 | +$67,681 | $13.4k | **15.1** | −$3,806 | 0 |
| **The spec:** +30 pips, ×0.5, 3 tiers, breakeven lock | +$35,506 | +$46,054 | **−$10,547** | $36.1k | 1.0 | −$4,559 | 2 |
| spec, +20 / +50 / +100 pips | +$28.8k / +$37.6k / +$158.6k | | | $29–51k / $21.4k | 1.0 / 0.7 / 7.4 | | 0–3 |
| spec, equal-size add-ons (×1.0) | +$42,046 | +$39,266 | +$2,780 | $39.8k | 1.1 | −$4,708 | 4 |
| spec, 2 tiers / 5 tiers | +$47.4k / +$33.7k | | | $31.8k / $36.5k | 1.5 / 0.9 | | 3 |
| **No breakeven lock**, +30 pips, ×0.5, 3 tiers | **+$306,664** | +$203,194 | +$103,470 | $23.6k | 13.0 | −$7,349 | 0 |
| No breakeven lock, +50 pips | +$286,907 | +$192,422 | +$94,484 | $23.7k | 12.1 | −$7,679 | 0 |
| **v1.17 at 2 lots (no pyramiding)** | **+$404,444** | | | $26.8k | **15.1** | −$7,611 | 0 |

**What it shows:**
1. **The breakeven lock is what breaks the spec.**
   - The first add-on comes only $3 after the entry, so "stop at the basket's average entry" pulls
     the base trade's stop from about −$11 up to about +$1.
   - Normal gold noise then scratches the trade right before the real move.
   - Result: profit collapses from $202k to $36k and the unseen Jul–Oct period loses money.
2. **Without the lock, pyramiding makes more money in both halves** (+$307k vs +$202k), because
   adding to trades that are already working does follow the trend.
3. **But it's a worse way to take extra risk than simply trading more lots:**
   - v1.17 at **2 lots** makes **+$404k** with a $26.8k drawdown and a −$7.6k worst day.
   - Pyramiding makes +$307k with a $23.6k drawdown and a −$7.3k worst day: about the same bad days
     for **$98k less**.
   - Profit per unit of drawdown falls from 15.1 to 13.0.
   - Scaling in adds size *late*, at worse prices, right where reversals hit.

**Verdict: not adopted.** If Zee wants more profit and accepts bigger swings, plain v1.17 at 2 lots
(`InpLots = 2`) beats every pyramid version on profit, drawdown ratio and simplicity.

### 21b. How "no breakeven lock, +30 pips, ×0.5, 3 tiers" actually trades

Re-run: **+$306,664.42**, identical. MT5 report: `testing/Pyramid_nolock_30pips_x05_3tiers_1lot.htm`.

**The rules in plain words:**
1. **v1.17 opens its normal 1-lot trade.** Same setups, same stop, same TP1 / 50% partial / $2
   trail. The base trade behaves exactly like v1.17's.
2. **Price moves $3 (30 pips) our way → add 0.5 lot.**
3. **Another $3 our way → add 0.25 lot.** At most 1.75 lots are open at once.
4. **The add-ons always carry the base trade's stop,** and that stop moves with v1.17's rules. When
   the base trade closes, the add-ons close with it.

**What happened over Jan 6 – Oct 8 (867 trades):**

| Trade reached… | Trades | Their net | Add-ons' part |
|---|---|---|---|
| base only (never got $3 ahead) | 207 | −$158,789 | – |
| base + 1 add-on (got $3 ahead, not $6) | 180 | −$146,962 | **−$62,547** (lost on 150 of 161) |
| base + 2 add-ons (got $6 ahead) | 468 | +$593,240 | **+$157,160** |

- **Add-ons fire within minutes.** $3 is small next to gold's normal M15 range, so **54% of all
  trades end up holding 1.75 lots.** In practice it's "1 lot, becoming 1.75 lots if the trade starts
  well".
- **The add-ons' extra +$100k comes entirely from the big runners.** On the year's best trade
  (27 Jan, BUY):
  - 1 lot at 5093.74, +0.5 at 5097.14 four minutes later, +0.25 at 5100.31 five minutes after that
  - all closed at 5285.28 the next morning
  - **+$33,178** instead of +$19,088
- **On losers, the add-ons lose with the base, and more per dollar,** because they sit closer to the
  far stop's price but use the same stop. A typical loser (1 Apr, SELL): base −$1,504, add-ons −$1,438,
  **basket −$2,948**. The biggest basket loss was **−$4,880** (the 24 Jul weekend gap).

**Why plain extra lots are still better:** a constant 1.75 lots of v1.17 would make about +$354k
with a similar drawdown (about $23.5k) and a smaller worst day (about −$6.7k). The pyramid makes
+$307k with a $23.6k drawdown and a −$7.3k worst day.

## 22. Pyramiding v2: ATR spacing, volatility sizing, protection — tested (13 Oct)

**Starting point:** the best pyramid from §21: no breakeven lock, +30 pips, ×0.5, 3 tiers.
**New options in `Saad_pyramid`:**
- `InpPyrSpacingAtr`: next add-on after N × ATR(14) instead of 30 pips
- `InpPyrRiskPct`: each add-on risks X% of equity to its real stop
- `InpPyrTrailAtr`: trail the whole basket to 2× ATR when an add-on fills

Same run settings (base 1 lot, $25k, Jan 6 – Oct 8, real ticks, 200 ms). **"Net ÷ DD"** is profit per
dollar of max drawdown, the fair way to compare things that take different amounts of risk.

| Version | Net | Jan–Jun | Jul–Oct | Max DD | **Net ÷ DD** | Worst day | Biggest loss |
|---|---|---|---|---|---|---|---|
| **v1.17 (1 lot)** | +$202,222 | +$134,541 | +$67,681 | $13.4k | **15.1** | −$3,806 | −$2,570 |
| **v1.17 at 2 lots** | +$404,444 | | | $26.8k | **15.1** | −$7,611 | −$5,139 |
| Pyramid, 30 pips (§21 best) | +$306,664 | +$203,194 | +$103,470 | $23.6k | 13.0 | −$7,349 | |
| ATR spacing 0.25× | +$311,076 | +$207,666 | +$103,410 | $25.7k | 12.1 | −$7,357 | −$4,781 |
| ATR spacing 0.5× | +$294,624 | +$196,937 | +$97,687 | $24.4k | 12.1 | −$7,147 | −$4,848 |
| ATR spacing 0.75× | +$279,478 | +$188,770 | +$90,708 | $20.6k | 13.6 | −$6,287 | −$4,991 |
| **ATR spacing 1.0×** | +$277,796 | +$190,076 | +$87,720 | $19.2k | **14.5** | −$5,944 | −$4,214 |
| ATR spacing 1.5× | +$255,260 | +$174,943 | +$80,317 | $18.3k | 14.0 | −$4,970 | −$4,341 |
| Risk sizing 0.5% per add-on | +$328,564 | +$183,701 | +$144,863 | $32.7k | 10.1 | −$10,282 | −$6,800 |
| Risk sizing 1% per add-on | +$406,672 | +$246,102 | +$160,570 | $41.1k | 9.9 | **−$13,299** | −$8,644 |
| 2× ATR basket trail on each add-on | +$259,598 | +$166,808 | +$92,790 | $35.5k | 7.3 | −$6,548 | −$4,810 |
| Breakeven lock + 1× ATR spacing | +$103,946 | +$77,456 | +$26,490 | $24.1k | 4.3 | −$5,124 | −$4,214 |

**What it shows:**
1. **ATR spacing helps the pyramid,** and it holds in both halves of the year:
   - 1× ATR keeps most of the profit (+$278k) with a smaller drawdown ($19.2k vs $23.6k) and smaller
     bad days (−$5.9k vs −$7.3k).
   - Profit per unit of drawdown rises from 13.0 to **14.5**.
   - It waits for a move that's big *for the current market* before adding, so fewer add-ons get
     stopped in chop.
2. **Volatility sizing makes it worse.** At 0.5–1% risk per add-on, the add-ons grow as the account
   grows and when the stop is close. The worst day reaches **−$13.3k** and net ÷ DD falls to about 10.
3. **Protection on add-on (breakeven lock or 2× ATR trail) still hurts.** Tightening the base trade's
   stop right after it moves our way scratches the trade before the real move. This is the same
   result as §21.
4. **No pyramid beats plain lots on a like-for-like basis.** Every version's net ÷ DD (4.3–14.5) is
   below plain v1.17's **15.1** at any lot size. For the same $19.2k drawdown as "ATR 1.0×", about
   1.43 lots of plain v1.17 would make about +$289k with about a −$5.4k worst day, a bit more than the
   pyramid's +$278k.

**Verdict:** if Zee wants a pyramid, **ATR spacing 1.0× (no lock, ×0.5, 3 tiers)** is the best one
found. It's consistent in both halves and the safest pyramid tested. But for the same risk, simply
raising `InpLots` is still slightly better and has no extra moving parts. Not shipped.

## 23. Pyramiding: more tiers, smaller ATR spacing — tested (13 Oct)

Zee: *"can u try more than 3 tiers? and lesser ATR?"* Base 1 lot, no breakeven lock, $25k,
Jan 6 – Oct 8, real ticks, 200 ms. "Max lots" is the most the basket can hold at once.

| Version | Max lots | Net | Jan–Jun | Jul–Oct | Max DD | Net ÷ DD | Worst day |
|---|---|---|---|---|---|---|---|
| **v1.17, 1 lot** | 1.00 | +$202,222 | +$134,541 | +$67,681 | $13.4k | **15.1** | −$3,806 |
| **v1.17, 2 lots** | 2.00 | **+$404,444** | | | **$26.8k** | **15.1** | **−$7,611** |
| ATR 1.0×, 3 tiers (§22) | 1.75 | +$277,796 | +$190,076 | +$87,720 | $19.2k | 14.5 | −$5,944 |
| ATR 1.0×, 5 tiers | 1.94 | +$287,668 | +$196,446 | +$91,222 | $20.0k | 14.4 | −$5,944 |
| ATR 0.5×, 5 / 7 / 10 tiers | 1.94–2.00 | +$310k / +$314k / +$316k | ~+$210k | ~+$103k | $25.1k | 12.3–12.6 | −$7,389 |
| ATR 0.25×, 5 / 7 / 10 tiers | 1.94–2.00 | +$336k / +$341k / +$342k | ~+$227k | ~+$113k | $27.2–27.7k | 12.3–12.4 | −$7,933 to −$8,137 |
| ATR 0.5×, 5 tiers, ×0.75 add-ons | 3.05 | +$417,330 | +$283,685 | +$133,645 | $36.6k | 11.4 | −$11,064 |
| ATR 0.25×, 5 tiers, ×0.75 add-ons | 3.05 | +$479,815 | +$320,169 | +$159,646 | $41.8k | 11.5 | −$12,338 |
| *(v1.17, 3 lots: 3× the 1-lot run)* | 3.00 | *≈ +$607k* | | | *≈ $40.3k* | *15.1* | *≈ −$11.4k* |

**What it shows:**
1. **Smaller spacing and more tiers do make more money,** and in both halves of the year: up to
   +$342k with ×0.5 add-ons and +$480k with ×0.75.
2. **Above 5 tiers, the extra tiers barely matter.** With ×0.5 they're tiny (0.125, then 0.06 lot…),
   so 7 and 10 tiers add only $1–5k.
3. **The extra money is bought with extra risk, at a worse rate than just trading more lots:**
   - ATR 0.25×, 10 tiers: +$342k, $27.7k drawdown, −$8.1k worst day.
   - v1.17 at **2 lots**: +$404k, $26.8k drawdown, −$7.6k worst day. More profit for about the same
     risk.
   - ATR 0.25× with ×0.75 add-ons: +$480k, $41.8k drawdown, −$12.3k worst day.
   - v1.17 at about 3 lots: about +$607k for the same drawdown.
   - Every pyramid's net ÷ DD (11.4–14.5) stays below plain lots (15.1).
4. **Why:** tight spacing fills the add-ons within minutes on most trades, so it acts like trading
   about 2 lots. But the add-ons are bought at worse prices than the entry and share the entry's far
   stop, so on losing trades they lose more per lot than the base does.

**Verdict:** more tiers and smaller ATR spacing = more profit **and** proportionally more risk; it's
a bigger position, not a better one. For any amount of risk Zee is willing to take, plain v1.17 with
a higher `InpLots` gives more profit than the matching pyramid.

## 24. How Saad_strategy_15min (v1.18) manages a trade: stop, targets, trailing

This is the plain EA, without pyramiding, with its default settings. It's read from the code
(`mt5/Saad_strategy_15min.mq5`: `DoEntry`, `ManageTick`, `ManageBar`, `LongTouched`, `ShortTouched`,
`DayCloseCheck`). At 1 lot, **$1 of gold price = $100**.

### 1. Entry and the first stop

- A setup candle forms touching an EMA:
  - **SELL:** on the 9 EMA, a red marubozu, a shooting star, or a pin bar that closes red
  - **BUY:** on the 9 or 50 EMA, a green marubozu, a hammer, or a pin bar (green or flat on the 9 EMA, any
    colour on the 50)
- **Filters:** the candle is at least 0.55 × ATR(14) tall, and the market isn't choppy (efficiency ratio ≥
  0.11 over 16 candles). Full shape rules: `lifecycle.md`.
- The trade opens when the **next candle breaks its high (BUY) or low (SELL) by 2 pips**. If that
  doesn't happen within one candle, or the market closes in between, the setup is dropped.
- **Stop loss:** **35 pips ($3.50) beyond the setup candle**, below its low for a BUY, above its high
  for a SELL. It's sent to the broker with the order, so it protects the trade even if the PC is off.
- **Too-wide stops are skipped:** if the stop would be more than **$15** from the entry ($1,500 at 1
  lot), there's no trade.
- **One trade at a time.**

### 2. The first target (TP1), different for BUY and SELL

| | BUY | SELL |
|---|---|---|
| **TP1** | the price **touches the "exit" EMA**: the 50 EMA for a setup on the 9 EMA, the 9 EMA for a setup on the 50 EMA. It's re-read every tick, so it moves with the EMA | the **last support**: the most recent swing low (lowest of 3 candles each side, within the last 100 candles) at least 5 pips below the entry |
| No target available | if the exit EMA is below the entry (or less than 5 pips above), there is no TP1: the trade **trails from the start** (see 5) | if there's no support below, **no trade** |
| Sent to the broker? | **no**, the EA watches it | **no**, the EA watches it |

### 3. Before TP1: move the stop to the entry at 75%

While the trade heads for TP1, the stop stays at its original level. Once price has covered **75% of
the distance from the entry to TP1**, the stop moves to the **entry price**. From then on the trade
can't lose, apart from spread and commission. The EA logs this as "CTC" (cover the cost). It doesn't
apply to BUYs with no TP1.

### 4. At TP1: bank half, trail the rest $2 behind

The moment TP1 is touched:
1. **Half the position is closed** (0.50 of 1 lot), and that profit is banked.
2. **The stop on the other half jumps to $2 behind the price** (BUY: price − $2; SELL: price + $2),
   and **never worse than the entry**.
3. From then on **the stop follows the price, tick by tick, $2 behind**. It only ever moves in our
   favour, in steps of 10 cents or more.
4. **TP2, TP3…** are the next swing highs (BUY) or swing lows (SELL) beyond TP1. They are **only
   labels**: when price reaches TP2, the EA logs it and points at TP3. Nothing closes there. **The
   exit is always the $2 trail.** A strong trend can run through several levels, which is where the
   +$19k trades came from.

### 5. BUYs with no TP1: the 2× ATR trail

When a BUY's exit EMA is already below the entry, there's no TP1 to aim for. The trade rides from the
start:
- At every 15-minute candle close (from the second candle on), the stop moves to **the highest high
  since entry − 2 × ATR(14)**, if that's higher than the current stop and below the last close.
- It never moves down. There's no 50% partial close on this path.

### 6. The daily close

**3 minutes before the broker's daily close, any trade that is in loss is closed.** Winning trades are
kept overnight and keep trailing.
- A waiting setup is dropped across the close or the weekend.
- An open trade is **not** closed for the weekend. That's how the 24 Jul breakeven SELL was hit by a
  $26 Monday gap (−$2,612, §12). A Friday close was tested and is available if wanted (§16).

### 7. Where the money comes from (per trade, Jan 6 – Oct 8 at 1 lot)

| Outcome | What happened |
|---|---|
| Full loss (about −$700 to −$1,500) | price never got 75% of the way to TP1, and the original stop was hit |
| About $0 | 75% reached, stop at entry, then price came back |
| Small win (+$100 to +$600) | TP1 reached, half banked, the rest trailed out $2 later |
| Big win (+$2k to +$19k) | TP1 reached, the $2-trailed half rode a trend through TP2, TP3… |

Per whole trade it wins about 47% of the time. The average win ($1,201) is about 1.7× the average
loss ($710), and the few big runners pay for the losers (§17b).

### 8. Worked example (illustrative numbers)

A SELL setup candle on the 9 EMA, high 4210.00, low 4205.00. The last support is 4198.00.
1. The next candle breaks 4204.80 (low − 2 pips) → **SELL 1 lot at 4204.80**.
2. **Stop** = 4210.00 + $3.50 = **4213.50** (risk $8.70 = **$870**). **TP1** = **4198.00**
   ($6.80 away).
3. Price falls to **4199.70** (75% of $6.80) → **stop moves to 4204.80** (entry). The trade is now
   risk-free.
4. Price touches **4198.00** → **0.50 lot closed (+$340 banked)**. The stop on the other 0.50 jumps to
   **4200.00** ($2 above).
5. Price keeps falling to 4190.00 → the stop follows to **4192.00**. TP2 (the next support, say
   4193.50) is passed and only logged.
6. Price bounces to 4192.00 → **the second half closes at 4192.00 (+$640)**. Total about **+$980**,
   minus $4 commission.

### 9. Important: what the broker holds vs what the EA does

| Item | Held by the broker (works if the PC is off) | Done by the EA (needs the PC + MT5 running) |
|---|---|---|
| Original stop loss | ✅ | |
| Stop to entry at 75% (CTC) | ✅ once moved | the move itself |
| TP1 half-close | | ✅ |
| $2 trail, 2× ATR trail | ✅ each new stop level, once moved | the moving |
| TP2 / TP3 labels | | ✅ (labels only) |
| Closing losers 3 min before the daily close | | ✅ |

**If the PC or MT5 goes offline,** an open trade keeps its **last stop** at the broker, so it's
protected, but it won't bank TP1, move to breakeven or trail until the EA is running again. Keep the
trading PC on, or run it on the VPS.

## 25. A profitable 5-minute variant: `Saad_strategy_5min` v1.01 (13 Oct)

§11's v1.00 (v1.17 rescaled for M5) lost money on the unseen months. This time:
- **Optuna searched 15 settings** in about 150 real MT5 tests: trading hours, longs/shorts, candle size,
  stop, trail, breakeven point, partial close, minimum target, choppy filter.
- **Tuned on Jan–Jun only,** then the top 10 were judged on unseen Jul–Oct.

| Version (1 lot, real ticks, $4/lot) | Jan–Jun | Jul–Oct (unseen) | PF | Max DD | Worst day |
|---|---|---|---|---|---|
| v1.00 (rescaled 15-min settings) | +$16,243 | **−$27,816** | 1.06 | $34.6k | |
| Optuna's #1 on Jan–Jun (trial 104) | +$20,856 | −$1,714 | 0.99 | $11.4k | |
| **v1.01 = trial 126** | **+$13,651** | **+$16,505** | 1.26 | $6.0k / $9.9k | −$4,231 |
| trial 140 (runner-up) | +$12,831 | +$10,737 | 1.21 | $9.3k | −$5,007 |
| v1.01, full period with random delays | | +$32,992 in total | 1.29 | $9.4k | −$4,270 |
| v1.01 settings **with buys allowed** | −$1,784 | +$6,241 | 1.03 | $21.2k | −$5,723 |

On Jul–Oct, 7 of the top 10 Jan–Jun settings were profitable.

**What the winners share:**
- **sell only**
- **big setup candles only** (≥ 1.1 × ATR)
- a tighter 15-pip stop with a wider $4 trail
- a first target at least 30 pips away
- no new setups in the first 8 hours of the broker day

**Verdict: a real but small M5 edge. Shipped as v1.01, demo first.**
- It's profitable in both halves and survives random execution delays.
- **Caution 1: it only sells.** The longs lose on M5, and gold fell about 20% over the test year, so the
  edge may depend on the falling market.
- **Caution 2: the pick is flattered.** Trial 126 was picked from the top 10 by its Jul–Oct result.
- **Caution 3: it's lumpy.** 5 of 10 months were negative.
- It makes about 1/6 of the 15-min EA's profit (+$202k). **The 15-min EA stays the main one.**

## 26. Trade lifecycle: Saad_strategy_5min v1.01 (the optimized 5-minute EA)

Read from the EA's defaults (`mt5/Saad_strategy_5min.mq5` v1.01, magic 88320, XAUUSD **M5**). It uses the same
engine as the 15-min EA (§24 / `lifecycle.md`) with different settings. **It only sells** (`InpBuys = false`).
At 1 lot, $1 of gold = $100.

### SELL trade, step by step

1. **Setup:** a **5-minute** candle closes as a pin bar, marubozu or shooting star (hammers are allowed too, but
   only SELLs are taken) touching the **9 EMA**.
2. **Filters**, all must pass, otherwise the setup is ignored:
   - **big candle:** the setup candle is at least **1.1 × ATR(14)** tall. This is the main v1.01 filter; most
     small M5 candles are skipped
   - **trading hours:** the setup candle starts at **broker hour 8 or later** (Axi server time, UTC+3;
     11:00 Pakistan time). Nothing new in the first 8 hours of the broker day
   - **not too choppy:** the efficiency ratio over the last **40 candles** (3 h 20 min) is at least **0.06**
   - **a target exists:** a **support** (a swing low with 3 lower candles on each side, within the last
     100 candles ≈ 8 hours) at least **30 pips ($3) below** the price. No support that far → no trade
3. **Entry:** the **next 5-minute candle** must break the setup candle's **low by 1 pip**. It sells the moment
   that happens; otherwise the setup is dropped (also across the daily close or weekend).
4. **Stop loss:** **15 pips ($1.50) above the setup candle's high**, sent to the broker with the order. If that's
   more than **$8** from the entry ($800 at 1 lot), the trade is skipped.
5. **Target:** **TP1 = that support**, at least $3 away. The EA watches it; no take-profit is sent to the broker.
6. **Breakeven:** once price has covered **75% of the way to TP1**, the stop moves to the **entry price**.
7. **TP1 touched:**
   - **half the trade closes** and that profit is banked
   - the stop on the other half jumps to **price + $4**, never worse than the entry
   - **TP2** becomes the next support below
8. **Trailing:** the stop follows price down, **$4 above it, tick by tick**, and never moves back up. TP2, TP3…
   are labels only.
9. **Exit**, whichever comes first:
   - **original stop** → full loss (at most $800 at 1 lot)
   - **breakeven stop** → about $0
   - **$4 trail** after TP1 → win
   - **3 minutes before the daily close while in loss** → closed

**One trade at a time.** Setups during an open trade are skipped. Winners stay open overnight and over weekends.

### How it differs from the 15-min EA

| | 15-min EA (v1.18) | 5-min EA (v1.01) |
|---|---|---|
| Candles | M15 | **M5** |
| Directions | BUY and SELL | **SELL only** |
| Setup candle size | ≥ 0.55 × ATR | **≥ 1.1 × ATR** (only big candles) |
| Hours | all day | **broker hour 8 → close** |
| Choppy filter | ER ≥ 0.11 over 16 candles | ER ≥ 0.06 over 40 candles |
| Break needed | 2 pips | 1 pip |
| Stop | 35 pips beyond the candle, max $15 | **15 pips**, max **$8** |
| First target | last support ≥ 5 pips away | last support **≥ 30 pips** away |
| Breakeven | at 75% to TP1 | same |
| At TP1 | half closed, $2 trail | half closed, **$4 trail** |
| BUY "trail from entry" path | yes | not used (no BUYs) |

### Worked example (illustrative numbers)

1. A 5-minute bearish marubozu on the 9 EMA at 12:35 broker time: high 4120.00, low 4115.60 (4.4 = 1.2 × ATR;
   big enough). The last support is 4110.80, which is $4.60 below: more than 30 pips, so it's a valid target.
2. The next candle breaks **4115.50** (low − 1 pip) → **SELL 1 lot at 4115.50**.
3. **Stop** 4121.50 (4120.00 + $1.50) = **$600 risk**. **TP1** 4110.80 ($4.70 away).
4. Price reaches **4111.97** (75% of $4.70) → **stop to 4115.50**. The trade is now risk-free.
5. Price touches **4110.80** → **0.50 lot closed, +$235**. The stop on the other 0.50 moves to **4114.80**
   ($4 above).
6. Price falls to 4104.00 → the stop follows to **4108.00**.
7. Price bounces to 4108.00 → **the second half closes, +$375**. Total about **+$610**, minus $4 commission.

**Broker vs EA:** the same as §24. Only the stop loss sits at the broker. TP1, the half-close, breakeven and
the $4 trail need the PC and MT5 running.

## 27. BUY rules of the 5-minute EA (off by default in v1.01)

`Saad_strategy_5min` v1.01 ships with **`InpBuys = false`**. If buys are switched on (Inputs tab →
`InpBuys = true`), the EA uses the rules below with v1.01's settings. They mirror the SELL side in §26,
except the target is an EMA rather than a support.

### BUY trade, step by step

1. **Setup:** a **5-minute** candle closes as a **pin bar, marubozu or hammer** touching an EMA. With
   `InpLongRule = 2` both kinds count:
   - **on the 9 EMA** → its exit (target) EMA is the **50 EMA**
   - **on the 50 EMA** → its exit EMA is the **9 EMA**
2. **Filters**, the same as for SELLs:
   - the setup candle is **≥ 1.1 × ATR(14)** tall
   - it starts at **broker hour 8 or later**
   - efficiency ratio over 40 candles **≥ 0.06**
3. **Entry:** the **next 5-minute candle** must break the setup candle's **high by 1 pip** (judged on the bid,
   like the chart). It buys the moment that happens.
4. **Stop loss:** **15 pips ($1.50) below the setup candle's low**, sent to the broker. More than **$8** away →
   skipped.
5. **Which path the trade takes:**

   **Path A: the exit EMA is at least 30 pips above the entry (the normal case)**
   1. **TP1 = the price touching the exit EMA.** It's re-read every tick and moves with the EMA. No TP at the
      broker.
   2. At **75% of the way** to the EMA → **stop to the entry**.
   3. **EMA touched:** **half closes**, the stop jumps to **price − $4** (never below the entry), and **TP2**
      becomes the next swing high above (a label only).
   4. The stop follows price up, **$4 below it, tick by tick**.

   **Path B: the exit EMA is below the entry or less than 30 pips above it**
   1. There's no TP1: **no half-close, no 75% step.**
   2. From the second candle on, at each 5-minute close, the stop rises to
      **the highest high since entry − 2 × ATR(14)**. It never moves down.

   Note: v1.01's 30-pip minimum target (`InpMinTpPips = 30`) sends many more BUYs down Path B than the 15-min
   EA's 5 pips does.
6. **Exit:** the original stop, the breakeven stop, the trail, or "3 minutes before the daily close while in
   loss".

### Why buys are off: the test results

| v1.01 settings, 1 lot, real ticks, $4/lot | Jan–Jun | Jul–Oct | Full period | PF | Max DD |
|---|---|---|---|---|---|
| **SELL only (shipped)** | +$13,651 | +$16,505 | +$32,992 (random delay) | 1.26–1.29 | $9.4k |
| **BUY + SELL** | −$1,784 | +$6,241 | +$4,457 | 1.03 | $21.2k |
| → what the BUYs added | about −$15k | about −$10k | **about −$28k** | | |

- **The buys lost in both halves of the year,** and they doubled the drawdown.
- **The likely reason:** gold fell about 20% over the test year (about 5,100 → 4,100), and these settings
  were tuned for selling.
- **The open question:** whether different, buy-specific settings could make buys pay on M5. The next step
  is a buy-only Optuna search, tuned on Jan–Jun and judged on Jul–Oct. If a buy setup holds up, v1.02 would
  give buys and sells separate settings, so the sell side stays as tested.

**For now:** keep `InpBuys = false`. Turning buys on with v1.01's settings made the EA about $28k worse in
testing.

## 28. VSISA (M5): every machine-learning method from this report, applied — VSISA v1.29 (14 Oct)

Zee: *"apply all the machine learning methods described in report.md to the VSISA EA on 5 min timeframe to get
the best ever result"*.

**Method:** the same as for Saad.
- **Data:** Axi real ticks (XAUUSD_TK, + $4/lot), 0.28 lots, $25k, 200 ms delay.
- **Walk-forward:** every model and setting is chosen on **Jan 6 – Jun 30 only**; MT5 judges it on unseen
  **Jul 1 – Oct 8**.
- **Test copy:** `mt5/VSISA_ml.mq5` (built by `patch_vsisa_ml.py`). It logs its own features and outcomes, and
  runs each trained model compiled into the EA. With every switch off it equals v1.28 to the cent
  (+$15,858.69 full year).
- **Trainer:** `meta_labeling_system/src/vsisa_train.py`.

**Starting point:** VSISA v1.28 makes **+$7,379 on Jul–Oct** (PF 1.77, drawdown $1,987, worst day −$596) and
+$15,859 over the full year. On XAUUSD.pro it makes +$14,437, so the clean-data symbol tells the same story.

### 1. Optuna parameter search (§18 method): v1.28 is already the best

About 150 MT5 trials over 24 settings: volume thresholds, reaction body, stop buffer/limits, target R,
breakeven/ratchet, fake break, fade, trend filter, hours, concurrent trades, setup length.
- **On Jan–Jun, no trial beat v1.28** (+$8,480).
- **On Jul–Oct, all 7 runners-up lost money** (−$477 to −$2,996).

VSISA's hand-tuned settings are robust. v1.28 stays the base.

### 2. Each machine-learning layer on its own (Jul 1 – Oct 8, unseen)

| Layer (trained on Jan–Jun) | Net | PF | Max DD | Worst day | vs v1.28 |
|---|---|---|---|---|---|
| **v1.28 (none)** | +$7,379 | 1.77 | $1,987 | −$596 | |
| Meta-label classifier, P ≥ 0.40 (§13) | **+$8,470** | 2.47 | $1,502 | −$435 | **+15%, less risk** |
| Meta-label regression, predicted ≥ −$50 (§14) | +$7,158 | 1.75 | $1,987 | −$596 | ≈ same (filtered 1 trade) |
| Regime GMM: skip the high-volatility cluster (§15) | +$7,523 | 1.86 | $1,742 | −$596 | +2% |
| Exhaustion exit, P ≥ 0.85 (§17) | +$8,382 | 1.93 | $1,749 | −$558 | +14% |
| **Exhaustion exit, P ≥ 0.75** (§17) | **+$8,730** | 2.08 | $1,469 | −$558 | **+18%, less risk** |
| PPO sizing, seed 0, avg 1.58× (§19) | +$13,428 | 2.16 | $2,212 | −$844 | |
| …constant 1.576× (fair benchmark) | +$11,595 | 1.77 | $3,122 | −$937 | PPO better |
| PPO sizing, seed 1, avg 1.45× | +$13,255 | 2.01 | $2,287 | −$871 | |
| …constant 1.46× | +$10,804 | 1.77 | $2,909 | −$873 | PPO better |

**Unlike Saad, VSISA does benefit.**
- **The classifier works here.** VSISA's losers look different at entry: risk size, trend agreement, fade vs
  normal setup.
- **The exhaustion exit works.** Its trades have a fixed far target (10R), so cutting dying winners early pays.
- **PPO beat its constant-lot benchmark with both seeds.**

### 3. Combinations

| Jul 1 – Oct 8 | Net | PF | Max DD | Worst day | Trades |
|---|---|---|---|---|---|
| classifier + exhaustion 0.75 | +$9,338 | 2.87 | $1,225 | −$435 | 88 |
| **classifier + exhaustion 0.75 + regime skip = v1.29** | **+$10,019** | **3.37** | **$981** | **−$276** | 83 |
| v1.29, random execution delays | +$10,221 | 3.34 | $1,062 | −$232 | 83 |
| v1.29 + PPO sizing (avg 1.67×) | +$14,599 | 3.16 | $1,358 | −$553 | 71 |
| v1.29 at a constant 1.667× (fair benchmark) | +$16,817 | 3.37 | $1,647 | −$464 | 83 |
| classifier + exhaustion + PPO (avg 1.67×) | +$13,856 | 2.80 | $1,684 | −$553 | 75 |
| …at a constant 1.67× | +$15,674 | 2.87 | $2,057 | −$730 | 88 |

**Once the three filters are on, PPO adds nothing over a constant lot:** net ÷ drawdown is 10.7 vs 10.2, with
less profit. So v1.29 ships the filters at the normal lot, and **lot size remains Zee's choice**.

### 4. VSISA v1.29 (shipped)

v1.28 plus, all trained on Jan–Jun:
- **meta-label classifier:** skip entries with win probability < 0.40
- **regime GMM:** no entries in the high-volatility regime
- **exhaustion exit:** close a profitable trade when P ≥ 0.75

| VSISA, 0.28 lots | Jul–Oct (unseen) | PF | Max DD | Worst day |
|---|---|---|---|---|
| v1.28 | +$7,379 | 1.77 | $1,987 | −$596 |
| **v1.29** | **+$10,019 (+36%)** | **3.37** | **$981 (−51%)** | **−$276** |

- **Full year:** +$22,078, PF 3.93, drawdown $981. Jan–Jun is the period the models were trained on, so that
  half is optimistic. **The Jul–Oct row is the honest one.**
- **v1.29 on its own defaults reproduced the Jul–Oct result to the cent.** It's compiled in the Axi terminal.

**Cautions:**
- **Some choices were made after seeing Jul–Oct.** The exhaustion threshold (0.75 vs 0.85) and the final
  combination were picked from Jul–Oct results. The models and the regime choice themselves come from Jan–Jun
  only. Expect some shrinkage live.
- **It needs its model files.** `VsisaMetaModel.mqh`, `VsisaRegimeModel.mqh`, `VsisaExhaustModel.mqh` and
  `VsisaDrlPolicy.mqh` must sit next to `VSISA.mq5`.
- **Switching back:** setting `InpMetaMode`, `InpRegimeMode` and `InpExhMode` to 0 gives plain v1.28.
- **Retrain from time to time** on newer data with `vsisa_train.py`.

## 29. Hybrid EA: Saad 15-min probe + VSISA 5-min adds — does the combined win rate rise? (14 Oct)

**Zee asked:** *"develop a new hybrid EA which uses the 15 minute saad EA to open a probe trade. When that trade
becomes sufficiently mature, the EA looks for the 5 minute VSISA setup and executes by pyramidding ... tell me if
winrate of these both EA's combined into 1 ea is higher.."*

**Short answer: no.** The combined win rate is **47%**, Saad's own rate. VSISA almost never finds a setup while
a same-direction Saad trade is open and mature: **2 of 146 VSISA setups in Jul–Oct, 6 of 322 over the full
year.** The gate blocks nearly every VSISA trade, so the hybrid is Saad alone plus a handful of adds.

### The EA

`mt5/Hybrid_Saad15_VSISA5.mq5` v1.00 (attach on XAUUSD **M5**). It is built by
`monitor/strategy_lab/build_hybrid.py` (+ `patch_hybrid_stats.py`):
- **Probe engine:** `mt5/SaadEngine15.mqh` is Saad v1.18 with every name prefixed `S_` and its candles fixed
  to M15. It opens the probe trades (magic **88340**).
- **Add engine:** VSISA v1.30 on M5. A VSISA setup may fire only when a **same-direction** probe is open and
  mature (`InpHybMature`):
  - 0 = probe just open
  - 1 = probe in profit ≥ `InpHybMatureR` × its risk (default 0.5R)
  - 2 = probe stop at or past breakeven
- **Adds** use magic **88341**.
- **At the end of a test** the EA prints its own per-engine win rates, counted **per position**.
- **Copies are exact.** With VSISA off, the hybrid reproduces Saad's full year to the cent (+$202,221.80). With
  Saad off and ML off, it reproduces VSISA v1.28's Jul–Oct to the cent (+$7,378.64).

### Results

XAUUSD_TK real ticks, $4/lot, 200 ms; Saad 1 lot, VSISA 0.28 lots. **WR = winning positions ÷ positions.**

**Jul 1 – Oct 8** (unseen by the VSISA models):

| Setup | Saad trades (WR) | VSISA trades (WR) | **Combined WR** | Net |
|---|---|---|---|---|
| Saad alone | 365 (46.8%) | — | **46.8%** | +$67,681 |
| VSISA v1.30 alone | — | 83 (60.2%) | **60.2%** | +$10,019 |
| Both side by side (no gate) | 365 (46.8%) | 83 (60.2%) | **49.3%** | **+$77,696** |
| Hybrid, mature = just open | 365 (46.8%) | 3 (2 wins) | 47.0% | +$68,233 |
| **Hybrid, mature = 0.5R (default)** | 365 (46.8%) | **2 (1 win)** | **46.9%** | +$67,833 |
| Hybrid, mature = 1.0R | 365 (46.8%) | 1 (1 win) | 47.0% | +$67,982 |
| Hybrid, mature = breakeven | 365 (46.8%) | 0 | 46.8% | +$67,681 |
| Hybrid 0.5R + close adds with the probe | 365 (46.8%) | 2 (1 win) | 46.9% | +$67,833 (identical: the adds had closed first) |
| Hybrid 0.5R, VSISA ML off | 365 (46.8%) | 2 (1 win) | 46.9% | +$67,833 |

**Full year (Jan 6 – Oct 8)** (Jan–Jun is in-sample for the VSISA models):

| Setup | Saad trades (WR) | VSISA trades (WR) | **Combined WR** | Net |
|---|---|---|---|---|
| Saad alone | 867 (47.9%) | — | 47.9% | +$202,222 |
| VSISA v1.30 alone | — | 163 (65.6%) | 65.6% | +$22,078 |
| Both side by side | 867 (47.9%) | 162 (65.4%) | **50.6%** | **+$224,321** |
| Hybrid, mature = just open | 867 (47.9%) | 11 (8 wins) | 48.1% | +$204,194 |
| Hybrid 0.5R | 867 (47.9%) | 4 (3 wins) | 48.0% | +$202,760 |

### What it means

1. **The gate is the problem, not the threshold.** Even "probe just open, same direction" lets only 6 of 146
   setups through. The most likely reason: Saad trades the breakout, while VSISA (a fade) trades the
   reversal. When both are active they mostly point opposite ways, or VSISA fires when Saad is flat.
2. **The adds' win rate can't be judged.** 1–4 trades is far too few; 75% on 4 trades means nothing.
3. **Running both EAs separately beats the hybrid on everything.** Side by side scores a higher combined win
   rate (49.3% vs 46.9% in Jul–Oct), about +$10k more profit in Jul–Oct and +$22k more over the year.
   Different magics (88302 / 88201) already let them share one account.
4. **VSISA's win rate comes from its ML layers, not from Saad.** VSISA with ML off is 44.0% (141 trades); with
   ML on it is 60.2% (83 trades).

**Verdict: not shipped.** The hybrid stays in the repo as a tested, working build. Zee's idea ("VSISA trades
only with Saad's confirmation") could be tested in a looser form, where VSISA needs Saad's **direction or bias**
on M15 instead of an open trade. That is a different hypothesis; per this section's numbers, it hasn't been
tested.

## 30. Blending the other way: VSISA confirms, Saad trades — does a double confirmation double the win rate? (14 Oct)

**Zee asked:** *"what if the pyramidding inner trade is saad's EA and the outer one is the 5 minute VSISA? ...
the VSISA can tell hey the market is moving up now.. then Saad's EA takes its trade and that's a doubled
confirmation so the chances of that trade winning should double."*

**Short answer: no.** The win rate doesn't double, and doesn't reliably rise at all.
- When VSISA agreed, Saad won **50.0%** over the full year vs **47.5%** when it didn't.
- In the unseen Jul–Oct period it was **45.8% vs 47.2%**.
- The one stronger split is "VSISA traded the same way within the last hour": 61% (17/28). That is too few
  trades to trust; it's about 1.4 standard errors from Saad's average.

### What was added to the hybrid EA (v1.00 build, still not shipped)

`monitor/strategy_lab/patch_hybrid_blend.py`:
- **Saad confirmed by VSISA** (`InpHybSaadGate`), same direction, by one of three definitions:
  - 1 = a VSISA trade is **open**
  - 2 = VSISA **opened** a trade within `InpHybWinMin` minutes
  - 3 = VSISA **saw** a setup (before its ML filters) within that window
- **What happens to unconfirmed Saad trades** (`InpHybSaadAct`):
  - 0 = Saad skips them
  - 1 = Saad takes every trade, confirmed ones at 2× lots
- **The reverse** (`InpHybVsGate` 2/3): VSISA trades only when Saad confirms.
- **Tagging:** every trade is tagged at open with every definition. The test then prints the win rate of each
  group, measured on the same trades in one run.
- **Gates off = no change:** with no gate, the results match §29's side-by-side run exactly.

### 1. Same trades, split by confirmation (both EAs ungated, per position)

| Saad trades… | Jul–Oct n | WR | Full-year n | WR |
|---|---|---|---|---|
| all | 365 | 46.8% | 867 | 47.9% |
| VSISA trade open, same dir | 10 | 60.0% | 18 | 66.7% |
| VSISA traded same dir, last 60 min | 14 | 64.3% | 28 | 60.7% |
| VSISA traded same dir, last 240 min | 40 | 45.0% | 71 | 47.9% |
| VSISA setup same dir, last 60 min | 22 | 50.0% | 44 | 50.0% |
| VSISA setup same dir, last 240 min | 59 | 45.8% | 124 | 50.0% |
| **no VSISA confirmation at all** | 305 | **47.2%** | 741 | **47.5%** |
| VSISA's last setup was the **opposite** way | 61 | 52.5% | 112 | 52.7% |

- **The two engines more often disagree than agree.** Over the full year, 48 VSISA trades opened against an
  open Saad trade, and only 11 alongside one.
- **Disagreement is not bad for Saad.** When VSISA's last setup pointed the other way, Saad did slightly
  better (52.7%). VSISA (a fade) and Saad (a breakout) read the same move differently.
- **VSISA trades confirmed by Saad:** 65.7% (35 trades) vs 65.5% unconfirmed. No lift.

### 2. Gated and boosted runs (MT5, XAUUSD_TK real ticks, $4/lot, 200 ms; Saad 1 lot, VSISA 0.28 lots)

WR is per position. Combined = Saad + VSISA positions together.

| Variant | Jul–Oct Saad n / WR | Combined WR | Net | Net ÷ DD | Full-year combined WR | Net | Net ÷ DD |
|---|---|---|---|---|---|---|---|
| **Both side by side (no gate)** | 365 / 46.8% | 49.3% | **+$77,696** | **7.18** | 50.6% | +$224,321 | 18.70 |
| Saad alone | 365 / 46.8% | 46.8% | +$67,681 | 5.10 | 47.9% | +$202,222 | 15.07 |
| Saad only if a VSISA trade is open | 21 / 38.1% | 55.8% | +$4,401 | 1.22 | 62.9% | +$18,726 | 5.17 |
| Saad only if VSISA traded ≤60 min | 25 / 48.0% | 57.4% | +$17,102 | 6.01 | 62.4% | +$35,135 | 10.31 |
| Saad only if VSISA traded ≤240 min | 60 / 40.0% | 51.7% | +$4,842 | 0.43 | 57.4% | +$29,906 | 2.67 |
| Saad only if VSISA setup ≤60 min | 38 / 39.5% | 53.7% | +$12,208 | 1.97 | 59.0% | +$28,725 | 4.64 |
| Saad only if VSISA setup ≤240 min | 85 / 41.2% | 50.6% | +$10,524 | 1.09 | 55.4% | +$52,305 | 5.41 |
| same, VSISA ML off | 85 / 41.2% | 42.9% | +$7,884 | 0.69 | — | — | — |
| Saad all, 2× lots if VSISA trade open | 365 / 46.8% | 49.3% | +$78,406 | 6.36 | 50.6% | +$226,855 | 18.39 |
| Saad all, 2× lots if VSISA traded ≤240 | 365 / 46.8% | 49.3% | +$80,441 | 6.46 | 50.6% | +$239,625 | 19.25 |
| Saad all, 2× lots if VSISA setup ≤240 | 365 / 46.8% | 49.3% | +$86,377 | 6.64 | 50.6% | +$263,394 | 19.41 |
| VSISA only if Saad traded ≤240 min | 365 / 46.8% | 47.8% | +$70,456 | 6.11 | 48.6% | +$208,045 | 15.86 |
| VSISA only if Saad setup ≤60 min | 365 / 46.8% | 47.0% | +$68,415 | 5.34 | 48.0% | +$204,013 | 15.20 |
| VSISA only if Saad setup ≤240 min | 365 / 46.8% | 47.5% | +$69,949 | 6.07 | 48.2% | +$206,308 | 15.27 |
| Both must agree (setups ≤240 min) | 85 / 41.2% | 42.9% | +$1,880 | 0.16 | 48.0% | +$34,857 | 2.97 |
| **Mirror of §29:** Saad adds only behind a VSISA probe at ≥0.5R | 15 / 40.0% | 57.1% | +$3,037 | 0.96 | 64.2% | +$18,268 | 5.77 |
| **Mirror:** VSISA probe stop at breakeven | 0 | 60.2% | +$10,019 | 10.21 | 65.6% | +$22,078 | 22.50 |
| **Saad all, 2× lots if VSISA traded same dir ≤60 min** | 365 / 46.8% | 49.3% | **+$86,560** | **7.82** | 50.6% | **+$238,731** | **19.90** |

The mirror of §29 (VSISA as the probe, Saad as the add) finds Saad trades behind a mature VSISA probe only
15–24 times at 0.5R, and never at breakeven. That is too few to judge, and it makes far less money.

**The 60-minute boost, rechecked with MT5's random execution delay:**

| Random delay | Net | Max DD | Net ÷ DD |
|---|---|---|---|
| Side by side, Jul–Oct | +$77,149 | $11,992 | 6.43 |
| **2× lots ≤60 min, Jul–Oct** | **+$88,194** | $12,152 | **7.26** |
| Side by side, full year | +$224,258 | $11,462 (6.95%) | 19.57 |
| **2× lots ≤60 min, full year** | **+$241,320** | $11,251 (17.89%) | **21.45** |

### What it means

1. **Gating Saad raises the COMBINED win rate only by changing the mix.** The gates cut Saad from 365 trades
   to 21–85, so VSISA's 60% trades make up more of the total. Saad's own win rate under a gate is about the
   same or lower (38–48%), and net profit falls by $60–73k in Jul–Oct. That is fewer trades, not better
   trades.
2. **Doubling the lots on confirmed Saad trades makes more money only because it trades bigger.**
   - Full year: net ÷ drawdown 19.41 vs 18.70 for side by side.
   - Unseen Jul–Oct: worse, 6.64 vs 7.18.
   - The drawdown in % of the account doubled over the full year (15% vs 7%).
   - Not an edge.
3. **Gating VSISA on Saad's direction just removes VSISA trades.** It loses money, and VSISA's win rate
   doesn't rise over the full year.
4. **Best blend = no blend.** Run both EAs side by side on one account (magics 88302 and 88201). This was the
   best net ÷ drawdown in the unseen period, with a combined WR of 49.3% (Jul–Oct) / 50.6% (full year).
5. **The one blend that tested positive: a lot boost, not a gate.** Saad entries within 60 minutes after a
   same-direction VSISA trade won 61% (17 of 28, full year).
   - **A gate on that condition does nothing.** Saad's own WR stays at 48–50%. Skipping the other entries
     changes which later Saad trades happen, so the gate never selects those 28 trades.
   - **Doubling the lots on exactly those trades does work.** It keeps Saad's trades identical and beats side
     by side on net ÷ drawdown in both periods, with 200 ms and with random delay:
     - Jul–Oct: 7.26 vs 6.43 (random delay)
     - Full year: 21.45 vs 19.57 (random delay)
     - The extra profit is positive in both halves of the year (about +$5.5k in Jan–Jun, +$8.9k in Jul–Oct
       at 200 ms).
   - **Cautions:**
     - 61% was the best of about 7 splits I tried, at about 1.4 standard errors. A gap that size often comes
       from chance alone.
     - The 60-minute window was chosen after seeing the splits.
     - Only 28 trades are boosted over 9 months.
     - The drawdown in money is the same, but it hit at a lower account balance, so it is 17.9% vs 7.0% of
       the account.
   - **So it's a candidate, not a ship.** If Zee wants it, it would ship as a small boost (×1.5, say) on the
     side-by-side setup and be judged on live trades.

**Verdict: no version ships.** The 60-minute boost is the only candidate (point 5). The hybrid EA keeps every mode for future tests. Results:
`testing/hybrid_blend_runs.jsonl`; summary: `monitor/strategy_lab/blend_summary.py`.

## 31. Loosening the VSISA confirmation for the 2× Saad boost: more trades, but the edge fades (14 Oct)

**Zee asked:** *"try loosening the vsisa version a bit to achieve much more than 28 trades.. then check"*

**What was loosened.** Only the signal: VSISA's own trades stay exactly as they were. Saad takes every trade,
at 2× lots when VSISA confirms by one of these:
- **VSISA traded** the same direction within 60 / 90 / 120 / 180 min
- **soft signal:** a VSISA setup that passed its regime filter and guards and scored ≥ 0.3 / 0.2 / 0.1 / 0.0
  on its meta model, within 60 / 120 min. VSISA itself still needs 0.40 to trade.
- **raw setup:** any VSISA setup, before every filter, within 60 / 120 min
- **looser VSISA detector** (`InpBigMode 0`: every loud setup bar, not just the loudest)

The no-boost baseline (both EAs side by side) re-ran identically: Jul–Oct +$77,696 (net ÷ DD 7.18), full
year +$224,321 (18.70).

**"vs random"** is what boosting the same number of RANDOM Saad trades would add on average: N × Saad's
average trade ($185 Jul–Oct, $233 full year). Saad makes money, so any 2× boost adds profit. The question is
whether the confirmed trades add more than random ones.

| Confirmation | Jul–Oct boosted n | Their WR | Extra net | vs random | Net ÷ DD | Full-yr boosted n | Their WR | Extra net | vs random | Net ÷ DD |
|---|---|---|---|---|---|---|---|---|---|---|
| **VSISA traded ≤60 min** (§30) | 14 | 64.3% | +$8,864 | +$2,600 | **7.82** | 28 | 60.7% | +$14,410 | +$6,500 | **19.90** |
| VSISA traded ≤90 min | 18 | 55.6% | +$6,912 | +$3,300 | 7.65 | 36 | 52.8% | +$11,433 | +$8,400 | 19.66 |
| VSISA traded ≤120 min | 22 | 45.5% | +$4,766 | +$4,100 | 7.45 | 42 | 47.6% | +$11,641 | +$9,800 | 17.75 |
| VSISA traded ≤180 min | 29 | 44.8% | +$5,211 | +$5,400 | 6.96 | 53 | 47.2% | +$10,854 | +$12,300 | 18.15 |
| Raw setup ≤60 min | 22 | 50.0% | +$6,746 | +$4,100 | 7.63 | 44 | 50.0% | +$11,444 | +$10,300 | 19.66 |
| Raw setup ≤120 min | 34 | 41.2% | +$3,775 | +$6,300 | 6.94 | 69 | 44.9% | +$18,480 | +$16,100 | 18.27 |
| Soft score ≥0.3, ≤60 min | 22 | 50.0% | +$6,746 | +$4,100 | 7.63 | 40 | 52.5% | +$11,818 | +$9,300 | 19.69 |
| Soft score ≥0.3, ≤120 min | 31 | 41.9% | +$4,247 | +$5,700 | 7.40 | 60 | 46.7% | +$12,600 | +$14,000 | 17.82 |
| Soft score ≥0.0–0.2, ≤60 min | 22 | 50.0% | +$6,746 | +$4,100 | 7.63 | 42 | 50.0% | +$10,582 | +$9,800 | 19.58 |
| Soft score ≥0.0–0.2, ≤120 min | 32 | 40.6% | +$3,680 | +$5,900 | 6.93 | 65 | 44.6% | +$17,524 | +$15,100 | 18.19 |
| Looser detector, raw ≤60 min* | 22 | 50.0% | +$6,747 | +$4,100 | 7.64 | 43 | 48.8% | +$10,118 | +$10,000 | 19.49 |
| Looser detector, raw ≤120 min* | 34 | 41.2% | +$3,775 | +$6,300 | 6.95 | 68 | 44.1% | +$17,154 | +$15,800 | 18.12 |

\*Measured against its own side-by-side baseline: +$77,804 / +$223,702.

### What it means

1. **"Much more than 28" isn't available from VSISA.** VSISA finds only about 320 setups a year, before any
   filter, so even the loosest version boosts just 65–69 Saad trades a year. Its looser detector setting
   changes almost nothing.
2. **The looser the confirmation, the closer the boosted trades come to an ordinary Saad trade.**
   - Their win rate: 60.7% (28) → 52.8% (36) → 50% (42–44) → 44–47% (53–69).
   - Saad's normal is 47.9%.
   - Past 90 minutes, the boosted trades are no better than random Saad trades. In Jul–Oct, the 120- and
     180-minute versions added *less* than boosting random trades would.
3. **Only the tight versions (≤60–90 min) beat side by side on net ÷ drawdown in both periods.** Their edge
   over random is a few thousand dollars on 14–36 trades. That is the profile of a small-sample effect, not
   a confirmed one.

**Verdict:** loosening doesn't produce a bigger, stronger confirmation. It produces more ordinary Saad trades
at double size. Nothing ships. If anything is kept, it's §30's tight 60-minute boost, judged on live trades.
