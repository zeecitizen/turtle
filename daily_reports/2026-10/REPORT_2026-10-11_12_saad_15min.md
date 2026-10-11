# 11–12 October 2026 — Saad's strategy: indicator audited, EA ported, a 15-minute EA that works

**Supersedes:** the 24–25 August report, archived at
[`daily_reports/2026-08/REPORT_2026-08-24_25_his_own_laws_beat_every_substitute.md`](../2026-08/REPORT_2026-08-24_25_his_own_laws_beat_every_substitute.md).

**Headline: `mt5/Saad_strategy_15min.mq5` v1.09 (magic 88302, XAUUSD M15 on Axi).**
Measured in the MT5 Strategy Tester on Axi real ticks, Jan 1 → Oct 8/11 2026, at 1 lot:

| Execution | Net | Trades | Win rate | PF | Max drawdown |
|---|---|---|---|---|---|
| **Random delay — the realistic figure** | **+$177,545 / +$180,815** (two runs) | 1,033 | 46.5% | 1.40 | 13–14% |
| No delay | +$207,274 | 1,027 | 47.6% | 1.48 | 10.3% |

At 0.10 lots the no-delay result is +$20,727 with a 4.7% drawdown. There was **1 losing month**
(July). Nothing is live-proven. The settings were tuned on the same nine months they are scored
on, so expect less live.

⚠️ **Zee could not reproduce +$207k at first** — and he was right to question it. Two causes:
1. His Strategy Tester was still holding the old input `InpMaruBody = 0.7`. MT5 keeps the last
   run's inputs when an EA's defaults change.
2. +$207k was a **no-delay** figure. With random delay it is +$178k–181k.

His own run (0.7, random delay) made +$143,343. My copy under the same conditions made
+$141,909. **Always quote the random-delay number.**

---

## 1. What exists now

| File | What | Status |
|---|---|---|
| `mt5/Saad_strategy_15min.mq5` v1.09 | **The 15-minute EA.** Magic 88302. | Compiled into the Axi terminal; Zee is testing it |
| `mt5/Saad_strategy.mq5` v4.03 | The 5-minute EA (indicator port). Magic 88301. | Compiled into Axi |
| `pine/saad_strategy.pine` | TradingView indicator (v4 engine, PineConnector alerts, journal) | On Zee's chart, set to the 15min EA's settings. **Uncommitted edits from another session** (SL in dollars `iSlUsd`, "Trail from the TP price" option) |
| `mt5/Saad_strategy_BTC.mq5`, `mt5/Saad_strategy_15min_BTC.mq5` | BTC variants | **NOT promoted — they lose** (§5) |
| `SAAD_SETUPS.md`, `SAAD_INDICATOR_AUDIT.md` | Every indicator trade with its rule / SL / TP / outcome; the bug list; PineConnector steps | Done |
| `optimal_settings_saad_strategy.md` | Zee's chart settings, the EA v4.02 settings, and the 15-minute settings | Done |

## 2. How the 15-minute EA trades (v1.09 defaults)

**Setups**
- Pin bar (any direction — the EMA decides the side), marubozu (body ≥ **50%** of the candle),
  hammer or shooting star.
- Longs: on the 9 EMA (exit at the 50) or on the 50 EMA (exit at the 9).
- Shorts: on the 9 EMA.
- Efficiency ratio ≥ 0.10.
- Break of the high/low by 2 pips **within 1 candle**.

**Before the TP**
- SL 30 pips beyond the candle; skip the setup if the risk is above $15.
- **CTC:** at 75% of the way to the TP, the stop moves to the entry.

**After the TP**
- **TP1:**
  - long = a touch of the exit EMA
  - short = the last support
- At TP1 the stop moves to **$2** behind the market and trails tick by tick.
- **TP2** = the next resistance (long) or support (short). When it is reached, the target moves to
  **TP3**, the level beyond it, and so on.
- The EA watches TP2 and TP3 itself, without broker take-profits. The exit is always the trailing
  stop.

**Day close**
- 3 minutes before the broker's daily close (Friday included), trades in loss are shut and
  winners stay open.

**Chart labels** appear in the visual tester and on a live chart: setup boxes, entries, stop path,
TP1/TP2/TP3 notes and exits with their $ result.

## 3. The night's chain, in order (1 lot, Axi M15, no delay unless stated)

| Version | Change (who asked) | Net | PF | Max DD |
|---|---|---|---|---|
| M5 EA on M15 | — | −$15.6k | 0.87 | — |
| v1.00 | risk cap $15, break in 1 candle, shorts on 9 EMA, no day target (my M15 court) | +$133.4k | 1.30 | 18.1% |
| v1.02–1.03 | CTC at 75%, shut losers at the close, no new trades in the last 30 min (Zee) | +$126.9k | 1.34 | 21.2% |
| v1.04 | long: touch the 50 EMA → trail $3 + TP at the resistance (Zee) | +$135.8k | 1.36 | 16.6% |
| v1.05 | the 30-minute rule removed (Zee) | +$147.3k | 1.39 | 16.3% |
| v1.06 | TP1 → $3 trail → TP2 → TP3 ladder, longs and shorts (Zee) | +$141.5k | 1.36 | 15.3% |
| *(rig tick data re-synced here — see §6)* | | | | |
| v1.07 | trails $3 → $2 (Zee) | +$167.3k | 1.43 | 12.1% |
| v1.08 | directional pins tested — **rejected** | +$167.3k | 1.43 | 12.1% |
| v1.09 | marubozu body 0.70 → 0.50 (Zee) | **+$207.3k** (random delay +$178–181k) | 1.48 | 10.3% |

## 4. Tested and REJECTED tonight (do not re-test without a new reason)

- **Zee's indicator settings unchanged on M15:** −$2,161. The $9 risk cap skipped most setups,
  and waiting 2 candles for the break was too slow.
- **More than one trade at a time** (2, 3, 5; same side only; opposite side only): always less
  profit and more drawdown. The skipped setups lose money on average.
- **Fixed TPs** (10/15/30 pips): win 71–86% of trades and lose money.
- **"No new trades 30 min before the close":** −$11k at 1 lot. Removed at Zee's request.
- **Widening the trail per TP** ($2 → $3 → $4, or steps of $0.50 / $2): always slightly worse
  than a fixed $2.
- **Directional pins only:**

  | Variant | Net |
  |---|---|
  | Wick must point the trade's way | +$90k |
  | ...and body closes the trade's way | +$124k |
  | Current (any pin) | +$167k |

  The "inverted" pins earn about half the profit.
- **Strict marubozu** (body ≥ 0.8–0.95): +$61k–119k. The plateau is 0.35–0.55.
- On the 5-minute EA: session hours, trend / slope / price-side filters, daily loss stop,
  breakeven at $3, and no risk cap (−$2k with a 54% drawdown).

## 5. BTC — no edge (weekend experiment)

Gold was closed for the weekend, so I tried the same strategy on BTCUSD. Axi: 1 BTC per lot,
M5 candle ≈ $148, spread $12.
- Rescaled versions **lost on both timeframes**: M5 −$4.7k, M15 −$3.7k at 0.10 lots.
- The spread costs about 3× more than on gold, relative to the size of the move.
- 52 single changes each on M5 and M15 found none that profit.
- The best M15 combination (EMA slope + trend alignment + hours 08–20) made +$1.8k, PF 1.26.
  That is small and in-sample.
- **Stopped by Zee.** The BTC EAs are not compiled into Axi; do not trade them.

## 6. Lessons that cost time tonight (read these)

1. **Quote the random-delay result, not the no-delay one.** Zee said delays don't matter. With
   $2 trailing stops they cost about 13% (+$207k → +$178–181k).
2. **The MT5 Strategy Tester keeps old inputs** when an EA's defaults change. Tell Zee to
   right-click Inputs → **Defaults** after every new version, and check his tester log
   (`AppData/Roaming/MetaQuotes/Terminal/6FBEE…/Tester/logs`) when his numbers differ.
3. **The test copy's tick history changed mid-session:** 59,886,606 → 59,410,491 ticks for
   Jan–Oct, history quality "n/a". The same v1.06 build moved from +$141k to +$158k. Compare
   only runs on the same data. Zee's terminal still has the original 59.88M ticks.
4. The rig terminal sometimes hangs after a finished test. `saad_v4.py` now times out at 240 s,
   kills only the rig's own terminal, and retries.
5. A rig compile of a renamed EA must be done again (`--ea NAME` without `--nocompile`), or
   every run returns "no report".

## 7. Open items

- Zee to re-run v1.09 in his own tester with the inputs reset to defaults. Expect about
  +$175k–185k at 1 lot.
- **Lot size:** a $19k–24k drawdown at 1 lot is a lot of risk for a $25k account. For the
  $500 account the equivalent is about 0.01–0.02 lots.
- **The indicator** (`pine/saad_strategy.pine`) has the 15min EA's settings, but not yet:
  - CTC
  - the $2 trail with the TP1/TP2/TP3 ladder
  - the day-close rule
  - marubozu 0.50

  Another Claude session (turtle-7e) owns the file's uncommitted trailing-stop edit. Coordinate
  before pushing anything to TradingView.
- **PrimeXBT:** the spread there (about 18 points) is wider than Axi's (about 13), so live
  results there will be lower. The 15min EA has not been run on the PXBT rig since v1.00.
- **A weekend-gap trade** (#720 in Zee's run, −$3,864 at 1 lot) is now covered by "shut losers
  at the close". A winner held over the weekend can still gap against the trade.

Full receipts for every version: [VERSION_HISTORY.md](../../VERSION_HISTORY.md) (Saad_strategy_15min
v1.00–v1.09, Saad_strategy v4.00–v4.03). Raw results: `monitor/strategy_lab/saad_v4.jsonl`.
