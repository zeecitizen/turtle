# The winning UHV strategy: how we reached a 100% win rate (6 November 2026)

**Instrument:** EUR/USD on PrimeXBT (real ticks, 6 Mar – 4 Nov 2026).
**Tester:** Turtle TV UHV (`monitor/TurtleTVUHV`, http://127.0.0.1:8774), a Python tick replay.
**Live:** the Golden Gravity game (`games/gold_runner`, http://127.0.0.1:8790), played by the bot.

> **Read this first.** Every number in this document comes from the Python tick replay. Per CLAUDE.md, Python
> *generates* a hypothesis and only MT5 or live fills *promote* one. The 100% was reached by adding rules **after
> looking at the losses**. The independent red team expects **about 99% on new trades** (range 98.3–99.4%), close to
> the ~99.3% break-even. `monitor/doctrine.py` verdict: **NOT PROMOTED**. Judge it on live fills over NEW trades.

---

## 1. The strategy (what a trade is)

- **Setup:** the UHV breakout. A candle with ultra-high volume (the UHV) marks a level: its high for a buy, its low
  for a sell. When price crosses that level after a quieter pull-back, we enter instantly at the crossing tick
  (`InpUhvEntry 1`, "instant").
- **Latency:** 0.3 s from the break to the fill (`InpUhvLatency 0.3`), to model real execution.
- **Target:** a tiny fixed take-profit of **+0.1 pip** (`InpUhvFixTp 0.1`). That is about +$1.0–1.5 per win at 1 lot.
- **Stop:** structural, 19 pips beyond the UHV extreme (`InpUhvStopMode 1`, `InpUhvSlBeyond 19`). That is about
  21 pips, roughly −$200 at 1 lot.
- **Geometry:** this lopsided shape is why the win rate is naturally high (97–99%). It is also why one loss erases
  about 140 wins. Break-even sits around **99.3%** (average win $1.44 against a typical loss of $213).

### The base setting `2026-11-05 05-45-38` ("97.7%")

| Trades | Losses | Win rate | Net (1 lot) |
|---|---|---|---|
| 7,631 | 172 | 97.75% (Mar–Jun 96.64 / Jul–Nov 98.60) | −$25,526 |

At 97.7% the geometry loses money. Every step after this was about removing losses.

**MT5 note.** EA `mt5/ZeeUHV_TurtleTV.mq5` v1.02 follows this engine. In MT5 the "97%" read off the EA's own prints
was wrong. Computed from the deals it was about **66%**. Always compute the win rate from deal prices.

---

## 2. Step 1: the loss study (172 losses read on charts)

Folder: `monitor/TurtleTVUHV/research/loss_study/` (`build.py`, `final/`, `claude_loss_comments.json`).

- I read every one of the 172 losses on the chart and wrote my own comment for each. They appear in the "List of trades"
  page, in the column "Claude's reading of the loss". Zee also labelled the October and March losses himself.
- **Finding:** most losses (156 of 172) look exactly like winners. There is no chart pattern that separates them.
  Only *clock* pockets were truly selective:
  - **NY rollover, 16:45–17:45 New York:** losses ×5.3 / ×10 on the two halves. This became `InpUhvNoClose 1`, in NY
    time with daylight saving handled by zoneinfo (the rollover moved one hour on 1 Nov).
  - **Wide spread at the breakout tick:** `InpUhvMaxTrigSpread 1.0` pip.
  - **News minutes, Friday close, spikes:** these became scanner settings.
- Every cause was turned into a **setting the scanner can tune** (Exit Lab page). The groups are: "cause:
  support / resistance", "against the structure", "market close", "exhausted / climax", "rollover / dead market",
  "news / spike", "chop", "bad fill", plus "UHV detection" and "loss filters". All are in `uhv_filters.py` and
  `scan.py`; all default to OFF.
- **Lesson:** stacking many filters found by the scanner always looked great and was always overfit. The red team
  compared each stack with random thinning, and none beat it.

## 3. Step 2: the risk manager (the angel) and the secure zone

Zee's idea: don't filter everything; run a **risk manager** that only allows trades in the *safe* part of a trend.

- **Secure zone:** the trade's colour has made between N and M **camel humps** in a row, and **ER16** sits in a band.
  ER16 is the efficiency ratio of the last 16 closes: net move ÷ path length, where 0 is chop and 1 is a straight
  line.
- Input `InpUhvRiskMgr 2`: trade **only** inside the secure zone. (Mode 1 = mark the zone only; modes 3/4 = Zee's zone
  model of risky pockets.)
- **Risk levels found,** with EV per trade per lot:

| Level | Name | Definition | Trades/day | Win rate | EV/trade |
|---|---|---|---|---|---|
| 0 | zero risk (sun) | humps 2–3 and ER16 0.30–0.35, no clock risk | 1.1 | 100% | +$1.45 |
| 1 | low (drizzle) | rest of the secure zone | 5.9 | 99.12% | −$0.14 |
| 2 | risky (rain) | start of trend (1 hump), 4–5 humps, ER < 0.15 or ≥ 0.45, no trend | 32.3 | 97.90% | −$3.20 |
| 3 | danger (storm) | rollover / near close 16–18 NY, Friday afternoon, news minutes, spread ≥ 1 pip, spike > 3 ATR, 6+ humps | 4.3 | 94.09% | −$10.23 |

- **Zee's 100% box, setting `2026-11-06 07-33-17`:** RiskMgr 2, humps 2–3, ER16 0.30–0.35, NoClose 1, MaxTrigSpread
  1.0. Result: **308 trades, 0 losses, +$444** (Mar–Jun 125/0, Jul–Nov 183/0), about 39 trades a month, and every month
  was green.
- **Tight zone, setting `2026-11-06 09-00-00`:** the same with ER 0.30–0.45. Result: 714 trades, 4 losses, 99.44%.
- **Important engine fact:** under `InpUhvRiskMgr 2` the ordinary loss filters (`uhv_filters.skip`) do **not** apply to
  secure trades. A cure meant for the zone needs its own input. That is why the Friday rule below is a new input.

## 4. Step 3: curing the tight zone's losses one by one

Starting point: the tight zone with 4 losses. Each one was studied on the chart:

### a) Selling into a major support: `InpUhvSellSup 2`
Zee: *"some of the losses came exactly when we sold right into ... a support level"*. The rule: skip a **sell** whose
level sits 0–2 pips above the last 10-candle swing low (`InpUhvSellSupPiv 10`, `InpUhvSellSupLast 1`). Inside the
angel's zones these sells lost about 2× as often, on both halves (`pockets/sell_support.py`). The mirror for buys
(`InpUhvBuyRes`) exists, but its evidence was weaker, so it is off.

### b) The tested round-figure wall: `InpUhvWall 1`, `InpUhvWallTouches 1`
This was the **8 April 12:56 PM PKT loss**. We bought at 1.16999 right under a **triple top** (1.16996 / 1.16997 /
1.17000) sitting on the 1.1700 figure, so the 0.1-pip target was exactly that ceiling.

- **Rule:** skip when a level the highs touched in the last 60 candles (`InpUhvWallBars 60`), within 1 pip of a 00
  figure (`InpUhvWallFig 100`), lies 0–1 pip ahead of the entry. A sell mirrors it with lows.
- **Touch count:** first built at 3 touches. Zee then said: *"we should also be careful about if a level was touched
  2x or 1x times ... if all we're loosing is that 1 or 2 trades ... we can cut them"*. Test inside the angel zone: 1 or
  2 touches cost the **same 3 winners and no losses**, so it now fires at **1 touch**. That covers 2x as well. It is
  insurance; there is no remaining loss to prove it on.
- **Variants rejected:** 50-figures cost 12–22 winners for nothing. "Any level" with no round figure deleted most of
  the zone.

Result after a) + b), setting `2026-11-06 15-00-00`: **648 trades, 1 loss, 99.85%, +$896**.

### c) The last loss: Friday 23 Oct, 7:50 PM PKT (10:50 NY), `1023-145031-B`
- **What happened:** a buy at 1.12059, which was the very top tick of that minute. The UHV was the 7:47 PM red candle.
  The entry was 1 pip under **1.12065, touched 4 times** (7:15, 7:22, 7:23, 7:24 PM PKT), and that level was not a round
  figure. Price never went even 0.1 pip our way, and the **weekly close flattened it at −$40**.
- **Zee's reading:** *"it broke the last higher high of the last hump but closed below it.. so it broke with a
  wick"*. Correct: the entry candle wicked to 1.12059 and closed at 1.12050. But that close only exists *after* we
  enter. A pre-entry wick check (`pockets/last_loss.py`) did not catch it. Using it properly would need a different
  entry: wait for the breakout candle to close above the level, then enter. That is open as a future scanner test.
- **Rejected:** a "tested ceiling at any level, strictly ahead" check caught it but cost 126–500 winners. Equal highs
  sit above most breakouts (`pockets/ceiling_ahead.py`).
- **Adopted: `InpUhvFriCutAllNY 10`** — no Friday entries from 10:00 New York, for **every** trade, the angel zone
  included. Evidence: on the base, Friday-from-10 trades lose **2.6× as often on both halves** (500 trades, 29 losses).
  The earlier red team, run before this loss was singled out, found Friday-10 to be the only step that held on the test
  half (P 0.003). Inside the angel zone it costs 37 winners.

| Friday from (NY) | Angel trades | Losses | Win rate | Net |
|---|---|---|---|---|
| off | 645 | 1 | 99.84% | +$893 |
| 8:00 | 595 | 0 | 100% | +$865 |
| 9:00 | 601 | 0 | 100% | +$874 |
| **10:00** | **610** | **0** | **100%** | **+$889** |
| 11:00 | 620 | 1 | 99.84% | +$862 |
| 13:00 | 628 | 1 | 99.84% | +$871 |

---

## 5. The final setting: `2026-11-06 16-00-00`

**Result: 610 trades, 0 losses, 100.00% on both halves (Mar–Jun 285, Jul–Nov 325), net +$889, about 3.3 trades/day
on 185 days.** The Turtle TV server reproduces this exactly.

| Input | Value | Meaning |
|---|---|---|
| InpUhvEntry | 1 | instant entry at the level crossing |
| InpUhvLatency | 0.3 | 0.3 s fill delay |
| InpUhvFixTp | 0.1 | +0.1 pip target |
| InpUhvStopMode / InpUhvSlBeyond | 1 / 19 | stop 19 pips beyond the UHV extreme |
| InpUhvLots | 1 | 1 lot |
| InpUhvRiskMgr | 2 | trade only inside the secure zone |
| InpUhvSafeHumpsMin / Max | 2 / 3 | 2–3 camel humps of the trade's colour in a row |
| InpUhvSafeErMin / Max / Bars | 0.30 / 0.45 / 16 | ER16 between 0.30 and 0.45 |
| InpUhvNoClose | 1 | no entries 16:45–17:45 New York (rollover) |
| InpUhvMaxTrigSpread | 1.0 | no entry if the spread at the breakout tick ≥ 1 pip |
| InpUhvSellSup | 2 | no sells 0–2 pips above the last 10-candle swing low |
| InpUhvWall / Touches / Bars / Fig | 1 / 1 / 60 / 100 | no trades into a touched 00 figure 0–1 pip ahead |
| InpUhvFriCutAllNY | 10 | no Friday entries from 10:00 New York |

### The road, in one table

| Step | Setting | Trades | Losses | Win rate | Net |
|---|---|---|---|---|---|
| Base | 2026-11-05 05-45-38 | 7,631 | 172 | 97.75% | −$25,526 |
| + risk manager, tight zone, rollover, spread | 2026-11-06 09-00-00 | 714 | 4 | 99.44% | — |
| + sell-support + wall (3 touches) | 2026-11-06 15-00-00 | 648 | 1 | 99.85% | +$896 |
| + wall 1 touch | — | 645 | 1 | 99.84% | +$893 |
| **+ Friday from 10 NY** | **2026-11-06 16-00-00** | **610** | **0** | **100%** | **+$889** |
| Zee's narrow box (ER 0.30–0.35) | 2026-11-06 07-33-17 | 308 | 0 | 100% | +$444 |

The last step bought the win rate, not money: net went from +$896 to +$889.

---

## 6. What the red team said (the honest part)

A multi-agent workflow tested Zee's 100% box: walk-forward, perturbation, chart study and a red team. Files are in
`research/loss_study/tight/work_wf/` and `work_judge/`.

- **Knife-edge, not a plateau:** every outward step adds losses — 0.01 of ER, one hump, one bar of the ER window (17
  bars gives 7 losses).
- **Execution sensitivity:** 4 wins flip to full stops under small latency changes (0–1 s), and 2 under 0.05 pip of
  extra slippage.
- **No skill in choosing the bounds:** blind walk-forward picks scored 99.40 / 97.11 / 99.29 / 98.88% on the half
  they had not seen, and the rank correlation between in-sample and out-of-sample was about 0.
- **Chance:** a loss-free box this size appears by pure chance about 42% of the time.
- **Cures:** none of the 24 tested cures beat a same-size random skip at the strict bar.
- **The Jul–Nov tight losses (23 Jul, 19 Oct, 23 Oct)** were each decided by one 0.1-pip tick after the fill. That is
  the geometry's normal tail.
- **Expected on new trades:** about **99.0%** (98.3–99.4%), at or below break-even. That is about one −$210 loss per
  100 trades. Two months in three will still show 100% (0.99^39 = 68%).
- **To prove it beats break-even:** about 450 new trades with zero losses are needed.

**Next step that can promote it:** MT5 Strategy Tester (custom symbol, random delay) on both halves, then live fills.

---

## 7. What was implemented today

### Turtle TV UHV (`monitor/TurtleTVUHV`)
- `uhv_engine.py`: the risk manager (RiskMgr 0–4), NoClose in NY time, the trigger-spread check, sell-support and
  wall checks, harvest, and the **new `InpUhvFriCutAllNY`** (checked before the risk manager, so it applies to secure
  trades too). A guard `sl_t = max(sl_t, 0.1)` fixed a crash on 0-pip stops.
- `uhv_filters.py`: all the loss-cause filters, the zone model, `secure()`, `risky_zone()`, `into_major()`, and
  `into_wall()` (touches may now be 1).
- `scan.py`: every cause is a scanner group. The wall's touches list includes 1, and "cause: market close" includes
  `InpUhvFriCutAllNY` (0, 8–13).
- List of trades: a "Your comment on the loss" box with Save, and "Claude's reading of the loss".
- Exit Lab: scan-only include toggles and a STOP SCAN button.
- Saved settings: 07-33-17, 09-00-00, 09-10-00, 13-00-00, 14-00-00, 15-00-00 and **16-00-00**.
- Research scripts in `research/loss_study/pockets/`: `sell_support.py`, `bounce_levels.py`, `triple_top.py`,
  `wall_touches.py`, `last_loss.py`, `ceiling_ahead.py`, `angel_final.py` (each with its `.out`).

### The live game, Golden Gravity (`games/gold_runner/engine.py`)
- **The angel** (`_risk_verdict`) blesses or blocks each live UHV breakout. It blocks on:
  - the rollover hour (16:45–17:45 NY);
  - **Friday from 10:00 NY**;
  - spread ≥ 1 pip;
  - humps outside 2–3;
  - ER16 outside 0.30–0.45;
  - a sell 0–2 pips above the last 10-candle swing low;
  - a touched (1+) 00-figure wall 0–1 pip ahead.
- **On screen:** the angel shields the player with a bubble when it blesses a trade, and puts light shields before
  the bank and mafia when it blocks one.
- **Risk weather:** sun = level 0, drizzle = 1, rain = 2, storm = 3 with thunder. Storm covers rollover, Friday from
  10 NY, news minutes, spikes, wide spread and tired trends.
- **The yogi** appears for a coming setup, with day and night, and the camel sign shows the humps.
- **Safety:** daily consent is saved in `live_signed.json`, rounds freeze on uncertain orders, and the broker stop is
  capped at 2.5 pips.

### The bot (scratchpad `u97_bot.py`)
- Plays the angel's blessed signals live, with a budget of $10 (floor $13.92).
- Sizing: the maximum coins the balance carries on level-0 ("dead sure") trades, otherwise 1 coin. A coin is
  5,000 EUR.
- Ejects at −2 pips, and stops if the win rate falls under 94% after 20 rounds.
- **New:** it shoots only after 2 minutes of continuously fresh quotes. The PrimeXBT tab was being frozen by Chrome in
  the background.

### Known live issue
Chrome freezes the hidden PrimeXBT tab, which stalls quotes. Keep PrimeXBT in its own visible window, or add it to
Chrome Settings → Performance → "Always keep these sites active".

---

## 8. Important rules learned
1. Removing trades always "helps" net when each trade has negative EV. Judge a rule by **lift on both halves**, not by
   net.
2. Fewer trades buy clean days without making trades safer: loss-free days ≈ WR^(trades/day).
3. A cure must hold on Mar–Jun **and** Jul–Nov (split at 1 Jul 2026), with lift above about 2.
4. Always show net beside the win rate.
5. Python is a hypothesis. MT5 deals and live fills are the truth.
