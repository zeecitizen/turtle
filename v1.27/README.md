# Saad_strategy_15min v1.27

**Gold (XAUUSD) on 15-minute candles. Magic number 88302. Released 2026-10-19.**

v1.27 is **v1.26 with one setting changed: the pin bar's "nose" limit goes from 0.20 to 0.35** (`InpNoseMax`). Every other setting, rule and default is exactly v1.26's. Zeeshan found this by hand on the TradingView chart, and MT5 confirmed it.

| MT5, Jan 1 – Oct 16 2026, 2 lots | **v1.27** (pure defaults, 2 runs) | v1.26 (pure defaults, 3 runs) |
|---|---|---|
| Net | **+$250,919 / +$253,195** | +$211,965 / +$210,445 / +$211,097 |
| Profit factor | **2.80 / 2.85** | 2.51 – 2.54 |
| Win rate (whole trades) | 52.9% / 54.3% | 50% – 54% |
| Trades | 197 | 191 |
| Average per trade | ≈ +$1,280 | ≈ +$1,105 |
| Max drawdown | **$28,320** | $35,000 – 36,000 |
| Red months | June only, **−$0.4k / −$0.5k** | June only, −$11k |

All runs: MT5 Strategy Tester, Blueberry's real XAUUSD ticks (`XAUUSD_BB`), every tick, random execution delay, $100,000 account.

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct 1–16 |
|---|---|---|---|---|---|---|---|---|---|
| +3.4k | +15.7k | +51.8k | +51.6k | +37.9k | −0.5k | +3.7k | +64.7k | +9.3k | +13.5k |

(v1.27 run 1. Run 2 is within ±$1k in every month.)

**Going back:**
- **To v1.26:** set `InpNoseMax` to 0.20.
- **To v1.23's behaviour:** set EMA 9/50, InpExitMode 0, all boxes to 1 and lots to 1. v1.23's file is also in the git history.

---

## What changed from v1.23

v1.23 is the Saad 15-min EA that was live before this work (EMA 9/50, pip stop, v1.23's TP1 / partial / trailing exits). Everything below is what v1.27 does differently. The list comes from comparing the two source files input by input, with v1.23 taken from the git history.

### 1. Settings with a different default

| Setting | Input | v1.23 | v1.27 | Effect |
|---|---|---|---|---|
| Fast EMA | `InpEmaFast` | 9 | **16** | Entry: which EMAs a setup candle must touch |
| Slow EMA | `InpEmaSlow` | 50 | **32** | Entry; also the EMAs the new exit aims for |
| Pin bar nose (short wick) limit | `InpNoseMax` | 0.20 | **0.35** | Entry: more pin bars qualify (the v1.27 change) |
| Break must clear the high / low by | `InpBreakPips` | 2 pips | **3 pips** | Entry |
| Chop filter (efficiency ratio) | `InpChopEr` | 0.11 | **0 (off)** | Entry filter removed |
| Stop loss type | `InpSlMode` | 0 = 35 pips beyond the setup candle | **1 = 1.6 × ATR(14) from the entry** | Stop |
| ATR stop multiple | `InpSlAtrMult` | 1.0 (unused in v1.23) | **1.6** | Stop |
| Skip if the stop is further than | `InpMaxRiskUsd` | $15 | **$20** | Risk (Zee's rule: at most $20) |
| Lot size | `InpLots` | 1 | **2** | Risk / money |
| Stop pips beyond the candle | `InpSlPips` | 35 | 31 | *Inactive* in this version (the ATR stop is used) |
| Higher-timeframe trend EMA | `InpHtfEma` | 50 | 90 | *Inactive* (the trend filter `InpHtfMin` is still 0 = off) |

### 2. New settings (did not exist in v1.23)

| Added in | Input | v1.27 value | What it does |
|---|---|---|---|
| v1.24 | `InpAdxMin` | **30** | Entry filter: trade only when ADX(14) of the last closed candle is at least 30 (MT5's own ADX). v1.23 had no ADX filter |
| v1.24 | `InpAdxPeriod` | 14 | ADX length |
| v1.24 | `InpAtrMinUsd` / `InpAtrMaxUsd` | 0 / 0 (off) | Volatility band: trade only when ATR is between $X and $Y. Available, not used |
| v1.24 | `InpOptScore` / `InpOptMinTrades` | 0 / 100 | Tester only: the score the MT5 optimizer maximises. Never affects live trading |
| v1.25 | `InpExitMode` | **1** | **The exit.** 0 = v1.23's exits; **1 = close everything when price touches the nearer EMA beyond the entry**; 2 = close after a candle closes back across the slow EMA |
| v1.26 | `InpRangeLook` / `InpRangeLookS` | **7 / 7** | Range boxes: the last 7 closed candles make the BUY / SELL range |
| v1.26 | `InpBandsB` | **`111110010100001010111`** | BUY range boxes, 0–5% … 95–100%, over 100% (1 = trade, 0 = unticked) |
| v1.26 | `InpBandsS` | **`111111100010001001110`** | SELL range boxes |
| v1.26 | `InpBandOff` | **1** | An entry in an unticked box: 0 = skip it; **1 = stand aside** (a ghost trade runs with the same stop and exit, and no new trade starts until it ends) |

### 3. New behaviour in the code

- **v1.24, ADX and volatility gates:** checked at the entry, right after the max-risk check. A failing trade is skipped.
- **v1.25, the exit modes.** With `InpExitMode` 1:
  - At the entry, the EA picks the nearer EMA beyond the entry price, from the live EMAs.
  - It closes the whole position when the bid (BUY) or ask (SELL) touches that EMA.
  - No EMA beyond the entry? It closes at the next open after a candle closes back across the fast EMA.
  - There's **no broker TP**, and v1.23's **SELL "last support" target is not needed**: v1.23 skipped a SELL when it found no support below; v1.26 / v1.27 take it.
- **v1.26, the range boxes.** Before a market entry, the EA measures where the entry sits in the last 7 closed candles' range, judged at the break level the way the TradingView indicator does. An unticked box means stand aside: a **ghost trade** runs (stop, exit, day-close-in-loss), no order is sent, and no new setup is taken until the ghost ends.
- **v1.26, the close-back exits** skip the entry candle's own close, as the indicator does.
- **Trade comment:** `Saad15 v1.26` / `Saad15 v1.27` (v1.23 wrote `Saad15 v1.23`). **Magic number: unchanged (88302).**

### 4. v1.23 settings that do nothing in this version

With `InpExitMode` = 1, these v1.23 exit settings are still in the EA but are **ignored**:
- the TP1 rules: `InpLongExit`, `InpLongTouch`, `InpShortTouch`, `InpLongTpPips`, `InpShortTpPips`, `InpMinTpPips`, `InpMaxTpPips`, `InpSwingPivot`, `InpSwingLook`, `InpLongResTp`, `InpLongResTp1`;
- breakeven at 75% of the way to TP1: `InpBeTpPct`;
- the 50% partial close at TP1 and its breakeven: `InpPartialPct`, `InpTp1Be`;
- the $2 trails after TP1 and the ATR trail: `InpLongTrailUsd`, `InpShortTrailUsd`, `InpTrail`, `InpRide`, `InpTrailAtr`.

**In other words, v1.23's "bank half at TP1, move to breakeven, trail the rest" is replaced by "close everything at the next EMA, stop never moves".**

### 5. Results side by side

MT5, Blueberry real ticks, Jan 1 – Oct 16 2026, random delay, $100k, **2 lots** for every row:

| | Net | PF | Win rate | Trades | Max DD | Red months |
|---|---|---|---|---|---|---|
| v1.23 (2 runs) | +$250,315 / +$238,448 | 1.32 / 1.30 | 45% | 932–935 | $30.7k–31.3k | Oct (−$5k to −$6k) |
| v1.26 (3 runs) | +$210k–214k | 2.50–2.54 | 53% | 191 | $34k–36k | Jun (−$11k) |
| **v1.27 (2 runs)** | **+$250,919 / +$253,195** | **2.80 / 2.85** | **53–54%** | **197** | **$28.3k** | Jun (−$0.4k) |

v1.27 makes about the same as v1.23 from **one fifth of the trades**. That's about **5× the profit per trade**, **twice the PF**, and a lower drawdown. v1.26 made about $35–40k less than v1.23, but with the same higher PF.

### 6. Going all the way back to v1.23

The short version (EMA 9/50, InpExitMode 0, all boxes to 1, lots to 1) is **not enough on its own**. ADX 30 and the other changes would still be active. For v1.23's exact trading, set all of these:

| Input | Set to |
|---|---|
| `InpEmaFast` / `InpEmaSlow` | 9 / 50 |
| `InpNoseMax` | 0.20 |
| `InpBreakPips` | 2 |
| `InpChopEr` | 0.11 |
| `InpSlMode` / `InpSlPips` | 0 / 35 |
| `InpMaxRiskUsd` | 15 |
| `InpAdxMin` | **0** |
| `InpExitMode` | 0 |
| `InpBandsB` / `InpBandsS` | `111111111111111111111` (all 21 boxes ticked) |
| `InpLots` | 1 |

Or simply attach the v1.23 file from the git history (`git show b9f6bbca^:mt5/Saad_strategy_15min.mq5`).

---

## What is in this folder

| File | What it is |
|---|---|
| `README.md` | This description |
| `Saad_strategy_15min_v1.27.mq5` | The EA source exactly as released (the live copy is `mt5/Saad_strategy_15min.mq5`) |
| `saad_15min_indicator.pine` | The TradingView indicator code |
| `indicator_settings.md` / `.json` | The indicator's 160 settings for v1.27 (= v1.26's with nose 0.35); Claude can re-apply the JSON to the chart |

The full story of how we got to this strategy (why 1 minute failed, the exit, the range boxes, stand aside) is in **`../v1.26/README.md`**. The overnight optimizer that tried to beat v1.26 is in **`../v1.26/OPTIMIZER_NIGHT_2026-10-19.md`**.

---

## How v1.27 came about

1. **The overnight genetic search** (about 4,980 tests over 26 settings) found **nothing** that beat v1.26 on the months it hadn't learned from. Its Jan–Jun winners failed on Jul–Oct.
2. **The next day Zee tuned the chart by hand.** In MT5 his combined changes **lost** money (−$20k), so each change was tested alone on v1.26:

| Change, alone on v1.26 | Net | PF | Max DD | Verdict |
|---|---|---|---|---|
| **nose 0.20 → 0.35** | **+$247,843** | **2.78** | **$28.3k** | ✅ better |
| body 0.60 → 0.55 | +$211,105 | 2.53 | $34.9k | no difference |
| wick 0.45 → 0.30 | +$206,301 | 2.41 | $30.6k | slightly worse |
| pin must point the trade's way | +$187,267 | 2.18 | $39.6k | worse |
| max risk $20 → $18 | +$165,505 | 2.30 | $33.6k | worse |
| new SELL range boxes | +$117,642 | 1.44 | $68.0k | much worse |
| new BUY range boxes (unticked BUY "over 100%") | +$72,145 | 1.61 | $29.8k | the main damage |

   The overnight optimizer had not searched the nose limit at all.
3. **The nose change was checked for luck** by running it twice more and testing its neighbours:

| `InpNoseMax` | Net | PF | Max DD | June |
|---|---|---|---|---|
| 0.20 (v1.26) | +$211k | 2.51 – 2.54 | $35k – 36k | −$11k |
| 0.25 | +$210,657 | 2.50 | $36.3k | −$11.2k |
| **0.30** | +$247,333 | 2.79 | $28.3k | −$0.0k |
| **0.35** (3 runs) | **+$245.7k – $248.2k** | **2.77 – 2.79** | **$28.3k** | −$0.7k to −$3.5k |
| **0.40** | +$243,935 | 2.74 | $28.7k | −$4.6k |
| **0.45** | +$245,429 | 2.76 | $28.7k | −$4.4k |

   Everything from 0.30 to 0.45 gives the same result, so 0.35 sits in the middle of a flat range, not on a lucky peak.

---

## What the nose change does

A **pin bar** is a setup candle with a long wick (the "tail") and a short wick on the other side (the "nose"):
- **v1.26** allowed a nose up to 20% of the candle's range.
- **v1.27** allows up to 35%.

So a few more pin bars qualify as setups. Over the year that means about 6 more trades: 197 instead of 191.

**Where the extra money comes from** (MT5 trade lists compared):
- **About +$24k is one trade:** a BUY on **March 31** (4565 → 4687, a $122 run to the EMA). It only qualifies as a pin bar once the nose limit is above 0.25.
- **About +$8–9k is June:** a different entry on June 25 (15:30 instead of 15:47) turned a −$2.7k loss into a +$5.9k win. This is also why June is now about flat, and why the worst drawdown fell from ~$35k to $28.3k.
- **The rest is small:** a few extra trades on either side, adding up to a few thousand.

**Honest reading:** this change is **safe**, since nothing got worse in any month and every value from 0.30 to 0.45 agrees. But much of the +$36–41k gain this year is **one lucky trade**. Expect the improvement to be real but smaller in future years.

---

## How v1.27 trades

Everything except the nose limit is identical to v1.26. The details are in `../v1.26/README.md`.

### Entry
- **Setup candle:**
  - A **pin bar**: wick ≥ 0.45 of the range, body ≤ 0.60, **nose ≤ 0.35** (the v1.27 change).
  - Or a hammer / shooting star, or a marubozu.
  - The range must be ≥ 0.55 × ATR.
- **On the EMA:** the candle touches the fast **EMA 16** or slow **EMA 32**, within 1 pip.
- **The break:** price breaks the setup candle's high (BUY) or low (SELL) by **3 pips** within 1 candle. The entry is at market.
- **Filters:**
  - **ADX(14) ≥ 30** (MT5's formula).
  - **Range boxes:** BUY `111110010100001010111`, SELL `111111100010001001110`, over the last 7 closed candles.
  - All hours, no chop filter.
  - One trade at a time.

### TP method: "Next EMA beyond the entry" (`InpExitMode` 1)
- **At the entry**, the target is the nearer EMA **beyond** the entry price: above it for a BUY, below it for a SELL.
- **Everything closes** when price touches that EMA.
- **If no EMA is beyond the entry**, the trade closes at the next open after a candle closes back across the fast EMA.
- **No partial close and no broker TP.** The EA watches the target itself.

### SL method: ATR stop (`InpSlMode` 1)
- The stop is **1.6 × ATR(14)** from the entry, sent with the order.
- **Max risk $20:** if that stop is more than $20 away, the trade is skipped. This is Zee's rule.

### Breakeven policy
- **None.** The stop never moves: no breakeven, lock or trailing. The only exception: 3 minutes before the daily close, a trade **in loss** is shut (`InpCloseLossMins` 3).
- These were tested on v1.26 in MT5 and none helped:
  - **Breakeven** at +$3 / $5 / $8, and at 50% or 75% of the way to the EMA.
  - **Partial close** at the EMA, with the rest trailing.
  - **Fixed targets** of +$5 to +$15.
  - **Profit locks.**
- Details are in the v1.26 ledger entry and in `monitor/strategy_lab/s15_betest.json` / `s15_tptest.json`.

### Stand aside (`InpBandOff` 1)
- An entry in an unticked range box becomes a **ghost trade**: the same stop and exit, but no order.
- No new trade starts until the ghost would have closed.

### Risk management

| Rule | Setting | Value |
|---|---|---|
| Lot size | `InpLots` (fixed) | **2 lots**; change it for smaller accounts |
| Skip trades with a far stop | `InpMaxRiskUsd` | $20 of price distance |
| Positions at once | `InpMaxPos` | 1 |
| Shut losers before the daily close | `InpCloseLossMins` | 3 minutes |
| Daily loss / profit stops, spread filter | | off |

At 2 lots on $100k: worst drawdown **$28,320 (≈14%)**, average trade about **+$1,280**, PF about **2.8**. Scale the dollar figures with the lot size.

---

## Caveats

- **Part of the setup was tuned on this same year.** The chart only holds Aug–Oct, and the range boxes were picked from a full-year table. Expect live results below the tester.
- **The nose gain leans on one trade** (March 31, +$24k).
- **Magic number 88302 is shared with v1.23 / v1.26.** Don't run two of them on the same account without changing `InpMagicNumber`.
- **Demo first.**

## Receipts

- **Release test (pure defaults, 2 random-delay runs):** `monitor/strategy_lab/v127_release_test.py`, results in `v127_release_test.json`.
- **Change-by-change tests and the nose check:**
  - Scripts: `s15_chart_vs_v126.py`, `s15_chart_vs_v126_each.py`, `s15_nose_check.py`.
  - Results: the matching `.json` files.
- **Ledger:** `VERSION.md` and `VERSION_HISTORY.md`, entry *Saad_strategy_15min v1.27*.
