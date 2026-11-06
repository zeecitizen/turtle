# The Risk Manager ("the Angel"): complete reference

Built 6 November 2026 from Zee's idea:

> *"create a risk manager out of your loss study -> run this risk manager only at start of trend / weak trend ...
> it can also access risk in areas like ranges / etc whichever areas are loss prone -> define those areas"*

It exists in two places that follow the same rules:

1. **Turtle TV UHV:** the engine `monitor/TurtleTVUHV/uhv_engine.py` and the rules `monitor/TurtleTVUHV/uhv_filters.py`.
   These are the tester inputs `InpUhv…`.
2. **The game:** `games/gold_runner/engine.py`. The angel character blesses or blocks each live breakout
   (`_risk_verdict`), and the sky shows the risk level (`_risk_weather`).

> **Doctrine.** Every win rate below is a Python tick replay (EUR/USD PrimeXBT ticks, 6 Mar – 4 Nov 2026). Only MT5 or
> live fills promote. The red team expects the best zone to deliver about 99% on new trades, not 100%. Break-even for
> this geometry (+0.1 pip target, ~21-pip stop) is about 99.3%.

---

## 1. Why a risk manager instead of more filters

- The loss study read all 172 losses of the base setting (7,631 trades, 97.75%). **156 of 172 looked exactly like
  winners.** Global filters therefore cut winners about as fast as losers.
- Stacks of many filters always looked great in-sample and always failed the red team: none beat random thinning.
- **The alternative:** don't ask "is this trade bad?" Ask "**is this part of the market safe?**" Trade only where the
  trend is established but not exhausted, and smooth but not spiking.

## 2. The building blocks

### Camel humps (trend age)
The camel indicator counts **humps of the same colour in a row**: consecutive swings of the trend in the trade's
direction (`camStk`, signed by direction).

- 1 hump = the **start of a trend**: most often a flip, and risky.
- 2–3 humps = an **established trend**: the safest.
- 4–5 humps = **getting old**.
- 6+ humps = **tired**: danger.

### ER16 (trend smoothness)
The efficiency ratio of the last 16 closed one-minute candles:
`ER = |close[k] − close[k−16]| ÷ Σ|close[i] − close[i−1]|`.

- About 0 = chop: the price went nowhere along a long path.
- About 1 = a straight line, a spike.
- The safe band is **0.30–0.45**. The narrowest, "dead-sure" band is 0.30–0.35.

### Clock pockets (measured on 172 losses, both halves)
| Pocket | Window (New York time, follows US daylight saving) | Loss rate vs normal |
|---|---|---|
| Daily rollover | 16:45–17:45 | ×5.3 (Mar–Jun) / ×10 (Jul–Nov) |
| Friday afternoon | Friday from 10:00 | ×2.6 / ×2.6 (base, 500 trades, 29 losses) |
| Near the close | 16:00–18:00, Friday from 13:00 | storm zone |
| US data | 08:30, 09:30, 10:00 (3 min before to 1 after) | storm zone |

---

## 3. The modes: `InpUhvRiskMgr`

| Value | Behaviour |
|---|---|
| 0 | off: the ordinary loss filters apply everywhere |
| 1 | loss filters apply only OUTSIDE the secure zone; secure trades are untouched |
| **2** | **trade ONLY inside the secure zone** (the winning setting) |
| 3 | Zee's zone model: loss filters apply only INSIDE the risky zones (section 6) |
| 4 | Zee's zone model: skip every trade inside a risky zone |

**Engine fact:** in modes 1 and 2, secure trades skip `uhv_filters.skip()`, the ordinary loss filters. A rule that
must also act inside the zone has to be checked *before* the risk manager. That is why the Friday rule has its own
input, `InpUhvFriCutAllNY`.

### Order of checks for every setup (`uhv_engine.py`)
1. `InpUhvNoClose`: rollover 16:45–17:45 NY, skip.
2. `InpUhvFriCutAllNY`: Friday from this NY hour, skip (all trades).
3. `InpUhvMaxTrigSpread`: spread at the breakout tick ≥ X pips, skip.
4. **Risk manager** (`InpUhvRiskMgr`): secure zone or risky zone.
5. `InpUhvSellSup` / `InpUhvBuyRes`: selling into a major support, skip (any risk mode).
6. `InpUhvWall`: a touched round-figure wall ahead, skip (any risk mode).
7. Harvest (`InpUhvHarvestWins`, `InpUhvHarvestStopLoss`): the trend is already harvested or lost, skip.
8. The ordinary loss filters, only when the trade is not secure.

---

## 4. The secure zone: `secure()` in `uhv_filters.py`

A trade is SECURE when, at the last closed candle before the breakout:

| Input | Default | Winning value | Meaning |
|---|---|---|---|
| InpUhvSafeHumpsMin | 2 | **2** | at least this many humps of the trade's colour in a row |
| InpUhvSafeHumpsMax | 5 | **3** | at most this many |
| InpUhvSafeErMin | 0.15 | **0.30** | ER at least this (not chop) |
| InpUhvSafeErMax | 0.45 | **0.45** (Zee's narrow box: 0.35) | ER below this (not a spike) |
| InpUhvSafeErBars | 16 | 16 | candles in the ER |
| InpUhvSafeRangeAtr | 0 (off) | off | optional: a range narrower than X ATR is never secure |
| InpUhvSafeRangeBars | 20 | — | candles for that range test |

**Zones found** (the "secure" zone is humps 2–5 with ER 0.15–0.45):

| Zone | Setting | Trades | Losses | Win rate |
|---|---|---|---|---|
| secure (humps 2–5, ER 0.15–0.45) | 09-10-00 | 2,237 | 30 | 98.66% |
| tight (humps 2–3, ER 0.30–0.45) | 09-00-00 | 714 | 4 | 99.44% |
| Zee's box (humps 2–3, ER 0.30–0.35) | 07-33-17 | 308 | 0 | 100% (+$444) |

## 5. The risk levels (the weather in the game)

| Level | Sky | Definition | Trades/day | Win rate | EV per trade (1 lot) |
|---|---|---|---|---|---|
| 0 | ☀ sun | humps 2–3, ER 0.30–0.35, no clock risk, normal spread | 1.1 | 100% | +$1.45 |
| 1 | drizzle | humps 2–3, ER 0.15–0.30 or 0.35–0.45 | 5.9 | 99.12% | −$0.14 |
| 2 | rain | no trend; start of trend (1 hump); 4–5 humps; ER < 0.15 or ≥ 0.45 | 32.3 | 97.90% | −$3.20 |
| 3 | ⛈ storm + thunder | rollover / near the close (16–18 NY, Friday from 10:00 NY), US data minutes, spike > 3 ATR in the last 15 candles, spread ≥ 1 pip, 6+ humps | 4.3 | 94.09% | −$10.23 |

- **Thunder interval:** every 28 s at level 2, and every max(2.5, 11/n) s at level 3, where n is the number of danger
  reasons at once. Lightning is shown only from level 2.
- **Sizing by zone** (Zee: *"on some trades ... we mark them dead sure -> we max the risk taken here"*): the bot plays
  level 0 with the most coins the balance carries (up to 10 × 5,000 EUR) and level 1 with 1 coin. Levels 2–3 never
  reach it, because the angel blocks them.

## 6. Zee's zone model: `risky_zone()`, modes 3/4

Zee: *"chunking based on trend ... start/middle/end ... ranging ... support/resistance: MOST IMPORTANT ... news spike,
near market close time, near market open time"*.

| Input | Default | Risky pocket |
|---|---|---|
| InpUhvZStart / ZStartHumps | 0 / 2 | start of trend: fewer than N humps |
| InpUhvZEnd / ZEndHumps | 0 / 4 | end of trend: more than N humps |
| InpUhvZRange / ZRangeBars / ZRangeAtr | 0 / 20 / 3 | inside a range box (span < 3 ATR); a breakout OUT of the box in our direction is allowed |
| InpUhvZSR / ZSRLook | 0 / 60 | near S/R: a swing high (buy) / low (sell) within X pips beyond the level |
| InpUhvZNews | 0 | US data minutes and spike candles |
| InpUhvZClose | 0 | 16:00–18:00 NY daily, Friday from 13:00 NY |
| InpUhvZOpen | 0 | first 30 min after 03:00 / 08:00 / 09:30 NY and the Sunday 17:00 NY reopen |
| InpUhvHarvestWins / HarvestStopLoss | 0 / 1 | after N wins in one trend (or any loss) stop trading that trend |

**Finding** (`research/loss_study/pockets/zone_eval.py`, `features.csv`): start-of-trend and near-S/R cover most
trades with a loss-rate ratio of about 1, so they are not selective. Close and news are real. Setting 13-00-00 holds
the zone-model attempt. Mode 2 (secure only) won.

## 7. The extra cures inside the zone

| Rule | Inputs (winning value) | Why | Cost inside the angel zone |
|---|---|---|---|
| Selling into major support | `InpUhvSellSup 2`, `SellSupPiv 10`, `SellSupLast 1` | Zee: losses came when we "sold right into ... a support level"; ×2 loss rate on both halves | part of 714 → 648 |
| Round-figure wall | `InpUhvWall 1`, `WallTouches 1`, `WallBars 60`, `WallFig 100` | the 8 April loss under a triple top on 1.1700; Zee: "careful if touched 2x or 1x" | 3 winners (1 touch vs 3) |
| Friday cut (all trades) | `InpUhvFriCutAllNY 10` | the 23 Oct loss, flattened by the weekly close; base pocket ×2.6 | 37 winners |
| Rollover | `InpUhvNoClose 1` | ×5–10 loss rate | — |
| Spread at the trigger | `InpUhvMaxTrigSpread 1.0` | wide-spread fills | — |

Rejected (tested, too costly or not selective): buys into resistance (`InpUhvBuyRes`), 50-figure walls, walls at any
level, bounce levels from long counter-candles (`bounce_levels.py`), the pre-entry wick-fake check (`last_loss.py`),
range-top checks (`ceiling_ahead.py`).

**Final result, setting `2026-11-06 16-00-00`: 610 trades, 0 losses, 100% on both halves, +$889** (before the last
cures: 648 / 1 / +$896).

---

## 8. The live angel in the game: `games/gold_runner/engine.py`

Settings dict `U97` (each can be overridden in `config.json` / `state/admin.json` with the same key):

| Key | Value | Meaning |
|---|---|---|
| u97_rm | 2 | angel on (secure-zone mode) |
| u97_safe_humps_min / max | 2 / 3 | humps band |
| u97_safe_er_min / max / u97_er_bars | 0.30 / 0.45 / 16 | ER band |
| u97_max_spread_pips | 1.0 | spread block |
| u97_sellsup_pips / piv | 2.0 / 10 | selling into support |
| u97_wall_pips / touches / bars | 1.0 / 1 / 60 | round-figure wall (00 figures) |
| u97_fri_cut_ny | 10.0 | no Friday trades from 10:00 NY |
| u97_angel_s | 40 | how long the angel's verdict stays on screen |
| u97_tp_pips / u97_max_stop_pips | 0.1 / 2.5 | target, and the cap on the broker stop |

**`_risk_verdict(tt, side, bid, ask, bars, m)`** returns None (blessed) or the reason it blocks. It checks in order:

1. rollover hour;
2. Friday after 10:00 NY;
3. spread;
4. humps (start of trend / only N humps / trend tired);
5. not enough history;
6. ER (choppy / too steep);
7. selling into support;
8. tested round-figure wall.

**On screen:**
- **Blessed:** the angel appears and puts a **bubble shield** around the runner, and the round is allowed.
- **Blocked:** the angel puts two **light shields** in front of the bank and the mafia, and the shoot action is
  refused ("angel").

**`_risk_weather(now, bars)`** is computed every step and exposed as `market.risk = {level, why}`. The front end
(`static/js/main.js`: `riskSky`, `drawRiskRain`) draws sun / drizzle / rain / storm with thunder.

**Live log examples (6 Nov):**
- "BUY breakout ... STOPPED by the risk manager - start of a trend (first hump)"
- "... trend tired (4 humps in a row)"

## 9. Honest limits (red team, `research/loss_study/tight/work_wf/`)

- The zone edges sit just between known losses (ER 0.352 and 0.370 above, 0.285 and 0.287 below), which makes them a
  knife-edge.
- Choosing the bounds showed no out-of-sample skill.
- Small execution changes flip 2–4 wins into full stops.
- **Expected about 99.0% on new trades** (98.3–99.4%), at or below break-even. Two months in three will still look
  like 100%.
- **Proof needs live:** about 450 new trades with zero losses.
