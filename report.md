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
