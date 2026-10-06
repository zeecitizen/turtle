# TICK SPEED — the order-flow gauge for XAUUSD (2026-10-03)

**File:** `mt5/TickSpeedGauge.mq5` · **current version v1.15** · 882 lines
**Deployed to:** Blueberry (`DBE9B8B3…3FD8`) **and** PXBT (`BCB58008…CCFF8`)
**Deploy:** `py monitor/deploy_ea.py TickSpeedGauge` · `py monitor/deploy_ea.py --terminal pxbt TickSpeedGauge`
*(`pxbt` was added as a permanent target in `deploy_ea.py` today. Its editor is
`MetaEditor64.exe` with capitals — a lowercase glob misses it.)*

> **It does not trade.** It draws a meter and writes a CSV. Every signal in it is a
> **hypothesis**, and the CSV exists so they can be measured before any money depends on them.

---

## 1. WHAT ZEE ASKED FOR

> *"i want you to help me take trades on XAUUSD chart on MT5.. by developing an EA which is a
> meter with a needle to help me understand what is the tick speed"*

His design, which the EA follows literally:

* **Ticks per second**, measured with millisecond precision
* A **rolling statistical baseline** — 300-second SMA + standard deviation
* Zones expressed in **standard deviations**, never fixed numbers
* **+2 SD = the action zone**

**His own words on why a fixed threshold is wrong, and the single most important constraint
in the file:**

> *"A 'High' tick speed during the Asian session might only be 10 ticks per second, whereas a
> 'High' tick speed during the New York open might exceed 80 ... a static threshold will
> generate false signals."*

So **nothing in the EA has a fixed threshold.** The dial's full scale is `baseline + 3 SD` and
re-scales itself continuously; "stalling" is judged against a rolling baseline of price range,
not a number of points.

---

## 2. HOW IT MEASURES (architecture)

| piece | how |
|---|---|
| tick capture | `OnTick()` stores **one timestamp + price + side** into a fixed ring (`TICKBUF 8192`). O(1), **no allocation** — a draft that called `ArrayResize()` per tick would have done it 80×/second at the NY open |
| live needle | ticks within `InpLiveWindowMs` (2000 ms) — smooth enough to read |
| baseline | clean **1-second** counts pushed into a 300-slot ring; mean + SD recomputed each second (300 iterations at 1 Hz is free) |
| z-score | `(this second − mean) / sd` — drives every zone |
| drawing | `CCanvas` bitmap label, 50 ms timer (20 fps), needle eased toward the live value |

**`LineThick()` takes 8 arguments** (`x1,y1,x2,y2,clr,size,style,end_style`). The draft Zee was
given called it with 7 and would not have compiled. Signatures were read from the installed
`Include/Canvas/Canvas.mqh` rather than assumed.

**Everything scales from `InpRadius`** via `SC(px)`. Raising the radius alone would give a big
dial with 11-pixel text and a dotted band, so fonts, needle weight, marker lengths, text
offsets, canvas height and **band segment count** all derive from it. Band resolution matters:
the arc is ~`4.36 × radius` px long, so a fixed 126 segments renders as a dashed line at
radius 170.

---

## 3. THE INFER PROBLEM — Zee's critique, and the measurement that confirmed it

Tick speed is a **scalar**. He correctly pushed for direction:

> *"Tick speed alone cannot tell you direction ... you must combine tick speed with price
> micro-structure."*

v1.02 added an up/down delta. He then made the sharper point:

> *"If the EA only counts a tick as 'Up' because the price moved up, your Delta bar is no
> longer an independent variable measuring buying pressure. It is just a delayed, highly
> sensitive mirror of the price itself."*

**He was right, and it was measured on 164,760 real ticks** from his own
`shano_ticks_2026-10-01.csv` (`scratchpad/inferfix.py`):

```
corr(delta, the NEXT second's move) = +0.034
corr(delta, the PAST second's move) = +0.486     <- 14x stronger
```

The forward correlation sits barely above the noise band (±0.016 on 15,386 buckets) and
explains **~0.1% of variance**. Not tradeable.

### His proposed bid/ask fix was tested and does NOT fix it

The suggested "tick rule" (`ask > prev_ask → +1`, `bid < prev_bid → −1`, …):

```
agrees with the mid-price rule on 164,649 of 164,759 ticks = 99.93%
differs on 110 ticks = 0.07%

branch 1 ask up   (buyers lift)   78,670  47.7%
branch 2 bid down (sellers hit)   81,257  49.3%
branch 3 bid up   (buyers support)   335   0.2%   <- the only informative branches
branch 4 ask down (sellers press)    260   0.2%
```

Branches 1 and 2 catch 97% of ticks and fire exactly when bid and ask move **together** —
i.e. when the mid moves. It is the same signal. Both correlate +0.485 with the past move.

### Why no price-derived delta can work on this feed

Measured on the same 164,760 ticks:

```
last   != 0 :  0 rows (0.0%)
volume != 0 :  0 rows (0.0%)
```

The broker sends **bid and ask only** — no last price, no volume, so `TICK_FLAG_BUY/SELL`
never arrive and `FLAGS` mode can never activate. Zee's own point 3 is confirmed: XAUUSD is
OTC, there is no central tape.

---

## 4. THE BREAK — PXBT serves Level 2

```
2026.10.03 02:12:21  [TPS] depth of market on XAUUSDp: AVAILABLE - true book delta in use
2026.10.03 02:18:01  [TPS] depth of market on SOLUSDTp: AVAILABLE - true book delta in use
```

`MarketBookAdd()` **succeeds on PXBT**, which gives a source of direction that never touches
price. v1.04–v1.05 rebuilt the delta on it.

### What v1.05 measures: TOUCH consumption

```
delta = (volume taken from the ASK − volume taken from the BID) / (total taken)
```

Volume disappearing from the **best ask at an unchanged price** = offers lifted = aggressive
buying. **No price input anywhere.**

**Four corrections to the implementation Zee was given**, each a real defect:

| proposed | fault | v1.05 |
|---|---|---|
| `if / else if` on the two sides | buy branch always wins ties → **permanent green skew** | both sides accumulate independently |
| `side = ±1` per event | 3 lots and 300 lots both count as 1 — magnitude *is* the signal | weighted by actual volume |
| `ask > prev_ask ⇒ buying` | a cancel-and-requote reads as aggression — **price again** | logged separately as `swept_*`, **not** in the delta |
| `g_have_flags = true` | readout claims broker aggressor flags, which these are not | reads `BOOK a1240/b310` |

Also rejected: **deep-book** consumption (v1.04's first attempt). Levels far from the touch
churn with cancellations that are not aggression and buried the signal. The totals are still
computed and logged; they no longer drive the delta.

**Honest limit, written into the code:** MT5's book cannot distinguish a **cancelled** order
from a **filled** one — both just reduce a level. Consumption is an **upper bound** on
aggression, not a tape. It is still independent of price, which the old delta was not.

---

## 5. THE DEAD-MARKET BUGS — found by Zee testing on SOLUSDTp with gold shut

The gauge displayed all of this **in one frame** at 02:19:

```
0 /s                       <- no ticks arriving
SPEED +2.7 SD              <- yet "abnormally fast"
+100%   up 1               <- a delta built from ONE event
FADE DOWN (absorb)         <- a confident directional verdict
base 0 sd 0 | rng 0/0 | BOOK a206/b0
```

Three independent faults, harmless alone and dangerous together:

1. **Z-score blow-up.** Baseline near zero ⇒ SD near zero ⇒ one tick divides by almost
   nothing. The old guard only caught `sd` **exactly** zero.
2. **Delta from one event.** A single consumption of 206 on the ask gives +100%.
3. **Trivial stall.** `stalling` required only `range_base > 0`; on a dead symbol range **is**
   ~0, so "price has stopped" was true every second and absorption fired forever. It wasn't
   detecting absorption — it was detecting a closed market.

**v1.06 adds four floors**, below which the verdict is `TOO QUIET` and the EA says nothing:

| input | default | stops |
|---|---|---|
| `InpMinBaseTps` | 2.0 | baseline under 2 ticks/sec = market shut |
| `InpMinBaseSd` | 0.5 | z dividing by ~nothing |
| `InpMinWindowTicks` | 10 | a delta built from one event |
| `InpMinRangeBase` | 2.0 pts | "price stopped" when price never started |

**This test was worth more than the feature it broke.** Attaching to a dead symbol is the case
nobody checks, and it found a gauge that would have sat on the gold chart telling him to fade
a market that wasn't moving.

---

## 6. THE VERDICT LINE — his summary table, in code

| speed | price | verdict |
|---|---|---|
| ≥ +2 SD | travelling with the flow | **RIDE UP / RIDE DOWN** |
| ≥ +2 SD | **stalled** vs its own range baseline | **FADE DOWN / FADE UP** (absorption) |
| +1 … +2 SD | — | WATCH |
| < +1 SD | — | NO TRADE |
| below any floor | — | **TOO QUIET** |

Display: dial + `NN /s` + `SPEED ±N.N SD` + delta bar (red/green split at centre) + verdict +
a stats line (`base, sd, mv, rng, mode`) so nothing is a black box.

---

## 7. THE LOG — why it exists

> **SUPERSEDED — the log is now 35 columns. See [section 16](#16-the-log--now-35-columns).**
> The 23 columns below are v1.06. Kept because the *reasons* (per-symbol filenames, share
> flags, sweeps logged apart) all still apply.

`Common\Files\tickspeed_xau_<SYMBOL>.csv`, one row per second, **23 columns**:

```
server_time, symbol, tps, tps_base, tps_sd, z, up, down, delta, net_pts,
range_pts, range_base, verdict, side_mode, bid, ask, spread_pts,
book_bid_vol, book_ask_vol, touch_consumed_bid, touch_consumed_ask, swept_bid, swept_ask
```

*Per-symbol and opened `FILE_SHARE_READ|FILE_SHARE_WRITE` — one hardcoded name meant the
second chart to load lost its logging silently ("could not open tickspeed_xau.csv" on
SOLUSDTp and ETHUSDTp).*

**A header/data mismatch was caught on 2026-10-03** — header 21 fields, data row 23, because a
patch failed to match on indentation. Fixed; **any CSV written before that fix has a 21-column
header over 23-column rows and should be discarded.**

---

## 8. THE TEST THAT DECIDES EVERYTHING — not yet run

> **Still not run.** Restated with the BTC option in [section 19](#19-state--what-is-proven-and-what-is-still-only-on-display) — gold no longer has to open first.

The old price-derived delta was condemned by one measurement. **Run the identical test on the
book delta** once a London or New York session of gold has been logged:

```
corr(touch_consumed_ask − touch_consumed_bid , NEXT second's move)
corr(touch_consumed_ask − touch_consumed_bid , PAST second's move)
```

* **forward > backward** → book consumption *leads* price. A real order-flow signal on gold,
  and his velocity-alignment and absorption ideas gain a foundation.
* **backward > forward** → it follows too, and the direction half of the gauge is decoration.

`swept_bid`/`swept_ask` are logged apart so the ambiguous sweeps can be tested for inclusion
**with evidence** rather than blended in by assumption.

Reference script: `scratchpad/inferfix.py` (bucket by second, correlate delta against the next
and previous bucket's mid-price change).

---

## 9. VERSION LOG

| ver | what |
|---|---|
| 1.00 | needle, rolling 300 s baseline, SD zones, CSV |
| 1.01 | radius 92 → **170**; every dimension scales via `SC()`; band segments follow radius |
| 1.02 | **direction**: up/down delta bar, verdict line from his summary table |
| 1.03 | `MarketBookAdd()` probe + honest mode label (`FLAGS` / `DOM` / `INFER=price lag`) |
| 1.04 | deep-book consumption delta; per-symbol logs; **one `VER` define** so the banner cannot drift from `#property version` |
| 1.05 | **touch-level** consumption, volume-weighted, both sides, sweeps logged apart; deep-book branch removed |
| 1.06 | **dead-market floors** → `TOO QUIET`; stall floor; 1-decimal readout; CSV header fixed to 23 |

**The v1.02-banner-on-a-v1.03-build fault** (visible in his Journal) is the same one
`ZeeUHV_Diamond` has on record — *"it said v1.14 for the whole of the v1.15 ship … the live log
therefore misreported which machine was trading."* Now impossible: one `VER` define feeds both.

---

## 10. STATE AND NEXT STEPS (as of v1.06)

> **SUPERSEDED by [section 19](#19-state--what-is-proven-and-what-is-still-only-on-display).**

**Working:** gauge renders on both brokers; DOM confirmed available on PXBT for `XAUUSDp` and
`SOLUSDTp`; logging per symbol; dead-market guards in.

**Unproven:** the book delta has **no forward-predictive evidence yet**. Treat `RIDE`/`FADE` as
hypotheses on display, not signals to trade.

**Next, in order:**
1. Log one full gold session on PXBT (London or NY).
2. Run the forward/backward correlation above. That single number decides whether the
   direction half is real.
3. Only then consider whether `FADE` (absorption) is worth trading — it is the one signal that
   needs **no** aggressor data, only high speed with no price movement, both of which a
   bid/ask feed can measure.

**Note on brokers:** gold is `XAUUSD.pi` on Blueberry and `XAUUSDp` on PXBT. Absolute tick
rates differ between feeds — only the z-score is comparable. Blueberry has **not** been
confirmed to serve DOM; its Journal line on attach will say.

---
---

# PART TWO — v1.07 → v1.15 (same session, 2026-10-03)

Everything above still holds. This part covers the three micro-structure setups, the Level-2
break, and **eight bugs found by proofreading rather than by crashing** — several of which
would have produced confident, wrong signals on his screen.

---

## 11. THE THREE MICRO-STRUCTURE SETUPS (v1.07)

Zee's three patterns, each now its own verdict:

| verdict | fires when | predicts |
|---|---|---|
| **COIL → UP/DOWN** | high speed · price pinned · delta **held one side ≥ `InpCoilMinRun` (3) s** | break **with** the delta — the wall is being eaten |
| **WICK → UP/DOWN** | **z ≥ `InpWickSigma` (3.0)** · price pinned · delta **flipped** within `InpFlipWindow` (6 s) | reversal — the aggressors gave up |
| **IGNITION UP/DOWN** | speed spike · abs(delta) ≥ `InpVacuumDelta` (0.75) · **thin book** (< `InpThinBookPct` 0.60 × its own baseline) | sustained run — nothing resting to stop it |

### The conflict that had to be resolved before any of it could be coded

**Setups 1 and 2 are the same observation with opposite conclusions.** Both are "high speed +
price stalling". The coiled spring says *buy into the stall*; the early wick says *sell it*.
v1.06 had a single `FADE` verdict that silently assumed the second **every time** — in a real
coiled spring it would have printed `FADE DOWN` at the exact moment the wall broke upward.

What separates them is the delta's **behaviour over time**, not its value:

```
delta HELD one side while price is pinned   ->  attack still on      -> COIL (break with it)
delta FLIPPED sign while price is pinned    ->  attack collapsed     -> WICK (reverse it)
```

**⚠ BEHAVIOURAL INVERSION, v1.06 → v1.07.** During any sustained stall the delta stays
one-sided, so `run >= 3` is reached easily and **COIL fires where v1.06 said FADE — the
opposite trade.** Generic `FADE` now survives only in the narrow window where the delta has
just turned strong (run 1–2, no flip). This is what setup 1 asks for, but it is the largest
behavioural change in the build and it is **unproven** — it must not be met by surprise.

### The vacuum is measured, not inferred

"there are no buy limit orders to stop them" is a claim about **resting liquidity**, so
`IGNITION` requires total book volume below `InpThinBookPct` × its own rolling baseline.
Inferring "thin" from a quiet tick rate would have been one more proxy posing as a measurement.

---

## 12. ORDER BOOK IMBALANCE (v1.11) — the friction against the engine

> *"your EA measures the engine (Delta = aggressive market orders). To predict the exact second
> the price will break, you must measure the friction (OBI = resting limit orders blocking the
> path)."*

```
OBI = (bid_vol - ask_vol) / (bid_vol + ask_vol)    computed at the TOUCH and across the BOOK

PREDICT UP    delta >= +InpDeltaStrong  AND  OBI_touch > +0.60  AND  OBI_deep > +0.30
PREDICT DOWN  delta <= -InpDeltaStrong  AND  OBI_touch < -0.60  AND  OBI_deep < -0.30
```

His arithmetic checks out: `OBI > 0.60` does mean the bid side holds **>= 4x** the ask side.
Placed **before** the stall family, because this is what *resolves* a stall rather than being
one more description of it.

**Three corrections to the proposed implementation, each of which would have broken
something:**

1. **Verdict code collision.** The snippet defined `V_PREDICT_UP = 8` — already `V_QUIET`,
   with 9–14 taken by COIL/WICK/IGNITION. `TOO QUIET` and `PREDICT UP` would have been the
   same integer and the switch would have returned whichever case came first. Now **15/16**.
2. **It returned before the dead-market guards.** The snippet's `Decide()` opened with
   `Ready()` and the z test alone, dropping the four floors added in v1.06 after the gauge
   shouted `FADE DOWN` at a shut market. The guards stay first; OBI is tested after them.
3. **The touch is the most spoofable number in any book.** A maker pulls size for 50 ms and
   touch OBI swings to ±1.0. The deep book must agree (at half the trigger), or it is quote
   flicker — this broker's book is its own liquidity pool, not a central exchange.

**One claim deliberately NOT built:** *"submitting your order in the millisecond gap between
the destruction of the limit wall and the printing of the new Ask."* That is colocation
framing. This project measured its own execution delay at **163 ms median**, and a manual click
adds human reaction on top. What OBI can honestly offer is a **1–2 second read on direction**,
which is what the verdict claims and no more.

---

## 13. WHAT THE BROKERS ACTUALLY SERVE

| symbol | broker | DOM | depth |
|---|---|---|---|
| `XAUUSDp` | PXBT | **AVAILABLE** | not yet reported — gold was shut during the test |
| `SOLUSDTp` | PXBT | **AVAILABLE** | — |
| **`BTCUSDTp`** | PXBT | **AVAILABLE** | **10 levels (5 bid / 5 ask)** — a real book |
| `XAUUSD.pi` | Blueberry | **UNKNOWN** — the Journal line on attach will say | — |

```
2026.10.03 03:14:01.570  [TPS] book depth on BTCUSDTp: 10 levels (5 bid / 5 ask)
```

**Ten levels is a genuine order book, not an LP quote.** That is the threshold that makes OBI
mean anything at all, and it is why the EA prints the depth on its first book event instead of
assuming.

**BTC trades 24/7 and has the book — so the decisive test can be run on BTC tonight instead of
waiting for gold to open.** A positive result there proves the *mechanism*; gold would still
need its own calibration, because absolute tick rates and book sizes are not comparable
between instruments.

---

## 14. EIGHT BUGS FOUND BY PROOFREADING (v1.08 → v1.14)

None of these crashed. Every one would have produced a confident, wrong, or invisible result.

| # | ver | bug | why it mattered |
|---|---|---|---|
| 1 | 1.08 | **delta history was fed the LIVE (2000 ms) delta, sampled every 1000 ms** | consecutive samples shared **half their data**, so `run` was autocorrelated by construction — one 2-second burst registered as a run of 2–3 "independent" seconds. Since `run >= 3` promotes a FADE into a **COIL, the opposite trade**, window overlap was deciding direction. Now a clean **non-overlapping 1-second** delta, from the book when DOM is live |
| 2 | 1.08 | `g_sec_into_bar = TimeCurrent() - iTime(...)` | `iTime()` returns **0** when the M1 series is not ready → **~1.8 billion seconds** onto the display and into the CSV. Clamped to 0–59, else -1 |
| 3 | 1.09 | **the delta bar's labels contradicted the bar itself** | the bar's extent came from the **book**, the labels from **tick counts** — `+80%` above `12 dn / up 14` (which is +7.7%). Two numbers for one quantity. The draw gate was tick-based too, so a book-only second drew nothing at all |
| 4 | 1.12 | **`MarketBookGet()` called immediately after `MarketBookAdd()`** | the subscription is **asynchronous** — the probe read an empty book and would have reported **0 levels on a broker that serves 10**. Moved to the first real `OnBookEvent` |
| 5 | 1.12 | a comment had drifted off the code it describes | *"BOTH sides accumulate — an if/else would skew the bar"* ended up above the OBI block. That comment exists to stop someone reintroducing the permanent green skew; pointing at the wrong lines it fails its only job |
| 6 | 1.13 | **the stats line needed 871 px in a 392 px canvas** | only ~39 of 88 characters fit — **everything from `OBI` onward rendered off-screen.** Four proofreads had been telling him to read `run`, `FLIP`, `OBI` and the book depth off a line that was being clipped in half on his laptop. Split into two measured lines |
| 7 | 1.13 | **`InpLiveWindowMs = 0` → infinite loop** | the adaptive loop computes `0 x 2 = 0` forever and **hangs MT5**, then divides by zero. Clamped to a 100 ms floor |
| 8 | 1.14 | **`TimeCurrent()` only advances on ticks** | on a quiet symbol three consecutive one-second rows carried an **identical timestamp**. Any next-second correlation would mis-align and silently produce nonsense. Added a monotonic `local_ms` column |

**Bug 6 is the one to remember.** It was not a logic error at all — the logic was right and the
answer was being drawn past the edge of the canvas. Measure text against the canvas width; do
not assume it fits.

---

## 15. THE ADAPTIVE WINDOW (v1.10) — and why there is no separate "slow symbol" EA

Zee, with the gauge on SOLUSDTp while gold was shut:

> *"its always Too Quite … the needle is always at zero. then flips to red for an instant
> before flipping to zero again."*

**Diagnosis.** The live window was a fixed 2000 ms. Gold at the NY open puts ~160 ticks in it;
SOL at ~1 tick/second puts **0 to 2**. One tick means `delta = ±100%` — that is the flash of
red — then it ages out of the window and the needle drops to zero. Nothing was being measured;
the gauge was displaying a sample of one.

He asked for a second EA with slower constants. **Not built, deliberately**, for two reasons:

1. Fifteen versions shipped in one session; every future fix would need doing twice and the
   two copies would drift. This build already produced a banner reading v1.02 on a v1.03
   binary — the same fault `ZeeUHV_Diamond` has on record.
2. **Hand-tuned constants are the same mistake one level down.** His own argument —
   *"a static threshold will generate false signals"* — applies to a static **window** exactly
   as it does to a static speed threshold. It would be wrong again the moment SOL got busy or
   gold went quiet at 3am.

**So the window adapts.** Starting at `InpLiveWindowMs` (2000, floored at 100), it doubles
until it holds `InpMinWindowTicks` (10) ticks, capped at `InpMaxWindowMs` (24000). Gold keeps
its 2 s; SOL settles around 8–16 s by itself with no input from anyone. Speed is still reported
**per second**, so the needle and the baseline stay comparable at any window width, and the
active window is shown on the stats line (`win 8.0s`) so an adapting gauge is visible rather
than spooky.

**`TOO QUIET` changed meaning for the better.** It used to be "fewer than 2 ticks/second" — an
absolute that could only ever be right for one instrument. It now means *"even at the widest
window there still are not enough ticks to have a side"*, which is a **sample-size** statement
and is true for any symbol. `InpMinBaseTps` dropped 2.0 → **0.2** and `InpMinBaseSd` 0.5 →
**0.15**, because sample size is now the real guard and those two only need to catch a
genuinely closed market.

---

## 16. THE LOG — now 35 columns

`Common\Files\tickspeed_xau_<SYMBOL>.csv`, one row per second:

```
server_time, local_ms, symbol, tps, tps_base, tps_sd, z, up, down, delta, net_pts,
range_pts, range_base, verdict, side_mode, bid, ask, spread_pts,
book_bid_vol, book_ask_vol, touch_consumed_bid, touch_consumed_ask, swept_bid, swept_ask,
run, flip, book_total, book_base, sec_into_bar, early,
obi_touch, obi_deep, best_bid_vol, best_ask_vol, book_levels
```

**⚠ The column count changed four times in one session: 9 → 21/23 → 34 → 35.** A CSV written
by an earlier build cannot be fixed by appending to it — the header no longer describes the
rows. Checked on disk 2026-10-03 03:30:

| file | header | rows | status |
|---|---|---|---|
| `tickspeed_xau.csv` | **9 cols** | 2,049 | **stale — the pre-v1.04 hardcoded filename. Delete.** |
| `tickspeed_xau_BTCUSDTp.csv` | **35 cols** | 363 | **clean, current, accumulating** (~6 min — far too short to conclude anything) |

Order rows by `local_ms`, **never** by `server_time` (bug 8).

---

## 17. DISPLAY (v1.15)

`InpRadius` **235** (92 → 170 → 235) plus a separate `InpFontScale` **1.15**, because "the dial
is small" and "the text is small" are not always the same complaint and one knob cannot answer
both.

```
canvas   542 x 680 px      readout 56 px   verdict 44 px   zone 32 px   stats 29 px
stats line 1   31 chars -> 494 px of 542      OK
stats line 2   29 chars -> 462 px of 542      OK
lowest element ~637 px of 680                 fits
```

Both stats lines sit at ~90% of canvas width, so **above roughly `InpFontScale` 1.3 they clip
again** (bug 6). There is about 1.25 of headroom, not more.

---

## 18. VERSION LOG, CONTINUED

| ver | what |
|---|---|
| 1.07 | **COIL / WICK / IGNITION** separated by delta run-vs-flip and book thickness |
| 1.08 | non-overlapping 1 s delta for `run`/`flip`; `iTime` guard; early flag hardened |
| 1.09 | the delta bar's gate and labels come from whatever actually drives the bar |
| 1.10 | **adaptive live window**; `TOO QUIET` becomes a sample-size test |
| 1.11 | **OBI** (touch + deep) → `PREDICT UP` / `PREDICT DOWN`; book-depth disclosure |
| 1.12 | depth reported from the first real book event; comment restored to its code |
| 1.13 | window clamped against a hang; stats split into two lines that fit the canvas |
| 1.14 | `local_ms` — rows orderable when server time is frozen between ticks |
| 1.15 | radius 235, `InpFontScale` |

---

## 19. STATE — what is proven, and what is still only on display

**Proven, with numbers:**

* a price-derived delta is a **mirror of price** — `+0.486` backward vs `+0.034` forward on
  164,760 of his own ticks
* the proposed bid/ask "tick rule" is the **same signal** — 99.93% identical classification
* this broker sends **no last price and no volume** (0.0% of 164,760 ticks), so `FLAGS` mode can
  never fire on XAUUSD
* **PXBT serves a real 10-level book on BTCUSDTp**, so book-derived direction is possible at all

**NOT proven — and this is the whole point of the CSV:**

* **no verdict has any forward-predictive evidence.** `RIDE`, `FADE`, `COIL`, `WICK`,
  `IGNITION` and `PREDICT` are six hypotheses on a dial, not signals to trade.
* **COIL and WICK make opposite calls from nearly identical conditions**, separated only by a
  run-length threshold and a flip window. If that separation is noise, the gauge will point
  both ways on alternating seconds with full confidence — which is worse than pointing nowhere.

### THE ONE TEST THAT DECIDES IT

Run it on a BTC session (available now), then on gold when it opens:

```
corr(touch_consumed_ask - touch_consumed_bid , NEXT second's move)
corr(touch_consumed_ask - touch_consumed_bid , PAST second's move)
```

* **forward > backward** → book consumption *leads* price. The direction half is real and the
  absorption and ignition ideas gain a foundation.
* **backward > forward** → it follows price too, and the direction half of the gauge is
  decoration, exactly like the old INFER delta.

`swept_bid` / `swept_ask` stay logged apart so the ambiguous sweeps can be tested for inclusion
**with evidence** instead of blended in by assumption.

Reference script: `scratchpad/inferfix.py` — bucket by second, correlate against the next and
the previous bucket's mid-price change. **Use `local_ms`.** Delete the 9-column
`tickspeed_xau.csv` first so it cannot be picked up by a glob.

---

## 20. TWO LIVE FRAMES — and the gap they exposed (v1.16)

BTCUSDTp, 2026-10-02 22:25 and 22:27 broker time (the dead hour between the US close and
Asia). Both read straight off his screen.

### Frame A — 22:25

```
0 /s        SPEED -0.3 SD
bid 61   +21%   ask 93
TOO QUIET
base 0.1 sd 0.4 win 24s run 1F
OBI -0.27/-0.27 L10 t+49s BOOK
```

* `win 24s` — the adaptive window **hit its `InpMaxWindowMs` cap and still could not find 10
  ticks.** v1.10 working exactly as designed, and saying so.
* `base 0.1` — one tick every ten seconds. The M1 status bar agrees: `V: 14` and `V: 9` per
  minute.
* `run 1F` — delta run of 1 with the **FLIP** flag set: the sign is flapping, i.e. noise.
* **The bar and its labels agree**: (93 − 61) / 154 = **+20.8% → +21%**. Bug 3 confirmed fixed
  on live data.

### Frame B — 22:27, the one that matters

```
0 /s        SPEED -0.4 SD
bid 3    +87%   ask 43
TOO QUIET
base 0.2 sd 0.5 win 24s run 0
OBI -0.57/-0.57 L10 t+24s BOOK
```

**The engine and the friction disagree, and that is the whole point of section 12.**

| leg | reads | says |
|---|---|---|
| engine (delta) | **+87%** — 43 lifted off the ask, 3 hit on the bid | buyers attacking |
| friction (OBI) | **−0.57 / −0.57** — ask side thicker than bid | **the ceiling is thick** |

Buyers pushing into a wall. His own model's prediction for that combination is *the price will
not move* — and the chart shows exactly that: **0 ticks/second.**

**A delta-only gauge (every version up to v1.10) would have flashed a strong green buy here.**
The OBI leg is what stops it. This frame is the best argument for the v1.11 work and it cost
nothing to find — it was sitting on the chart.

**Why no verdict fired:** three gates, two of them failing.

| gate | needs | frame B | |
|---|---|---|---|
| speed | z ≥ `InpPredSigma` 1.0 | **−0.4** | ✗ |
| engine | \|delta\| ≥ `InpDeltaStrong` 0.30 | **+0.87** | ✓ |
| friction | OBI_touch > **+0.60**, deep > +0.30 | **−0.57 / −0.57** | ✗ wrong sign |

`TOO QUIET` itself came from the sample-size floor (fewer than `InpMinWindowTicks` 10 ticks in
the 24 s window), which is checked before any of the above.

### ⚠ The honest caveat on frame B

At **0 ticks/second**, a +87% book delta is **more likely a market maker pulling quotes than
buyers lifting offers.** MT5's book cannot distinguish a cancelled order from a filled one
(section 4) — consumption is an upper bound on aggression. In a dead hour, cancellation is the
better explanation. This is precisely what `TOO QUIET` exists to say.

### The gap Zee found

> *"it says bid on one side.. and ask on the other.. but it gives no conclusion whether this is
> driving price upwards or not?"*

**Correct, and it was a design gap, not a misreading.** The engine and the friction were both
on screen as raw numbers with **no synthesis**, and the one line that does synthesise them —
the verdict — gets swallowed by `TOO QUIET` whenever the sample is small. So on a quiet book he
saw `+87%` beside `OBI −0.57` and was left to do the arithmetic himself.

**v1.16 adds the PATH line**, between the verdict and the stats, which always states the
conclusion:

| condition | line | colour |
|---|---|---|
| push up, OBI favours up ≥ 0.30 | `BUY + CLEAR ABOVE: GO UP` | green |
| push up, OBI against ≤ −0.30 | `BUY vs WALL ABOVE: BLOCKED` | amber |
| push down, OBI favours down | `SELL + CLEAR BELOW: GO DOWN` | red |
| push down, OBI against | `SELL vs WALL BELOW: BLOCKED` | amber |
| push strong, book balanced | `BUY, PATH EVEN: WAIT` | dim |
| \|delta\| < 0.30 | `FLOW MIXED: NO CALL` | dim |
| no DOM, or < 2 levels | `NO BOOK: NO CALL` | dim |

Frame B would now read **`BUY vs WALL ABOVE: BLOCKED?`** — and frame A, whose delta is only
+21%, **`FLOW MIXED: NO CALL?`**.

Two deliberate choices:

1. **It shows even when a guard has silenced the verdict**, because "I cannot trust this" is
   not the same as "I have nothing to say". A trailing **`?`** and dim colour mark it untrusted
   under `TOO QUIET` / `WARMING UP`.
2. **It is NOT a new CSV column.** The state is fully derivable from `delta`, `obi_touch`,
   `obi_deep` and `book_levels`, all already logged — a 36th column would have invalidated the
   `tickspeed_xau_BTCUSDTp.csv` now accumulating, for information already in the file.

Also in v1.16: the bar's labels became **`hit` / `lift`** (bids get hit, asks get lifted)
instead of `bid` / `ask`. Those numbers are volume **consumed**; the OBI field two lines below
is volume **resting**. Labelling both by side invited reading one as the other.

### What BTCUSDTp is and is not good for

`base 0.1–0.2` ticks/second at this hour means roughly **12 ticks a minute**. BTC on PXBT is a
**poor test bed for the speed half** of the gauge in the dead hour — but the **book keeps
updating while the tape is dead** (43 lots left the ask in a window with almost no ticks),
because book events are independent of ticks. So the OBI and consumption halves can be
collected overnight; the z-score and the speed zones need a London or NY session.

---

## 21. VERSION LOG — v1.16

| ver | what |
|---|---|
| 1.16 | **PATH line**: engine vs friction stated as a conclusion, shown even under a guard; bar labels `hit`/`lift` (consumed) to separate them from OBI (resting); canvas `SC(146)` → `SC(168)` for the extra line |

---

## 22. BTCUSDTp CANNOT WORK — measured, not guessed

Zee: *"the speed is nearly always too quiet on BTCUSDt.. hmm..."* — then *"see.. its too quiet"*.

He is right, and it is not a calibration problem. **806 seconds logged on BTCUSDTp:**

```
verdicts:    TOO QUIET 748    WARMING UP 58    everything else 0
tps          mean 0.114 /s    max 5.0 /s
tps_base     mean 0.111 /s    max 0.220 /s
book_levels  10 on 804 of 806 rows
```

**The gauge has never once produced a verdict on this symbol, and it never can.**

```
the sample gate needs    InpMinWindowTicks = 10 ticks in the window
the feed delivers        0.114 ticks/sec  =  6.8 ticks per MINUTE
so 10 ticks takes        88 seconds
the window caps at       InpMaxWindowMs = 24 seconds
```

**88 > 24. The gate is arithmetically unsatisfiable on this feed.** No threshold tweak fixes
that, and the two obvious tweaks are both traps:

| "fix" | what it really does |
|---|---|
| raise `InpMaxWindowMs` to 120 s | verdicts appear — but a **2-minute** window cannot call a **1–2 second** move. It would be measuring a different thing under the same label |
| drop `InpMinWindowTicks` to 2 | back to deciding direction from one or two events — **exactly the v1.06 dead-market bug** that section 5 was written about |

### The real finding: PXBT is not sending BTC ticks

**6.8 quotes a minute on Bitcoin.** Real BTC spot prints thousands of trades a minute. This is
a **throttled, aggregated CFD quote feed**, not a tape. The gauge measures tick speed; on this
symbol there is no tick speed to measure.

**→ THE QUESTION THAT NOW MATTERS MOST: does PXBT throttle `XAUUSDp` the same way?**
Check it in the first minute gold opens. If gold's `tps_base` is also under ~1 /s, **the speed
half of this gauge is dead on PXBT** and the split is: **speed on Blueberry, book on PXBT.**
For reference, Blueberry's XAUUSD archive ran ~1.9 ticks/sec averaged across a full day —
**17× PXBT's BTC rate**, and far higher than that at the NY open.

### But the book is alive while the tape is dead

Frame D (22:33) — `bid 2 | +67% | ask 10`, `OBI -0.50/-0.50`, `L10`, `0 /s`. **Ten lots left
the ask in a window with almost no ticks.** Book events are independent of ticks, so BTCUSDTp
is still a usable test bed for the **OBI and consumption** research — just not for speed.

### ⚠ CORRECTION to section 12, claim 3

`obi_touch` equals `obi_deep` **exactly on 618 of 806 rows (76.7%)**, and did so in all four
photographed frames (−0.27/−0.27, −0.57/−0.57, +0.00/+0.00, −0.50/−0.50).

PXBT's BTCUSDTp book is a **near-uniform ladder** — the same size resting at every level. Where
every bid level holds X and every ask level holds Y, the touch and deep ratios are
*algebraically identical*:

```
touch = (X - Y)/(X + Y)        deep = (5X - 5Y)/(5X + 5Y)        same number
```

So the "deep book must confirm the touch" anti-spoofing guard added in v1.11 is **doing almost
no work on this symbol** — three quarters of the time it is literally the same number being
compared with itself. The guard is not wrong and it costs nothing; it simply is not the
protection claimed for it here. It would do real work on a book with a genuine size
distribution. **Whether XAUUSDp's book is uniform too is unknown and must be checked the same
way: count how often the two columns match.**

---

## 23. v1.17 — MEASURE THE STREAM THE SYMBOL ACTUALLY DELIVERS

> Zee: *"i'm not trading XAU.. i'm trading BTCUSDTp"*

That retires "wait for gold to open" as an answer. Section 22 proved the tick-speed gate is
arithmetically unsatisfiable on BTCUSDTp — **but the book is busy while the tape is dead.**

So `speed` is no longer hardwired to ticks:

```
input ESpeedSrc InpSpeedSource = SRC_AUTO;    // AUTO | TICKS | BOOK
```

* Book-event arrival times go into their own 8192-slot ring, counted by `BookWithin()` — the
  exact twin of `Window()`.
* **Both** streams feed their own 300-second baseline every second; both means and SDs are
  computed.
* `AUTO` picks whichever stream has the **higher baseline**. Compared on the 300-second
  average, never on the current second, so the choice **cannot flap** and corrupt the very
  baseline it is chosen from.
* Everything downstream is untouched: zones, needle, z-score and all nine verdicts read
  `g_tps / g_mean / g_sd / g_z`, which are simply fed from the selected stream.
* The **adaptive window and the sample gate now count the active stream too** — sizing a
  window by tick count and then measuring it in book events would size it for nothing.

The stats line says which is live: **`TK`** or **`BK`** in front of `base`.

**Log schema 2** → `tickspeed2_<SYMBOL>.csv`, adding `bps`, `bps_base`, `tps_tick_base`, `src`.
New filename on purpose: the 35-column `tickspeed_xau_BTCUSDTp.csv` keeps its OBI history
intact instead of being invalidated for the fourth time.

**⚠ STILL UNMEASURED:** whether book events actually arrive faster than ticks on this feed.
The consumption totals in the photographed frames (46, 12 lots moving in windows with ~0
ticks) say they do, but that is an inference. **`bps_base` vs `tps_tick_base` in the new log
settles it in one minute.** If they are equal, the book updates only when a quote does, `AUTO`
falls back to `TICKS`, and nothing is lost — but then BTCUSDTp cannot drive this gauge at all.

---

## 24. v1.18 — THE MASTER SIGNAL BAND

> Zee: *"a cummulative decision which combines the values on the dial / OBI etc… you only need
> to look at one word and one color"*

A filled colour block under the delta bar, carrying one word. His 3-filter checklist:

| filter | test | input |
|---|---|---|
| 1 VELOCITY | `z >= 1.5` | `InpSigGoSigma` |
| 2 PRESSURE | `\|delta\| >= 0.50` | `InpSigDelta` |
| 3 FRICTION | touch OBI `>= 0.50` **and** deep `>= 0.30`, same side as the push | `InpSigObi`, `InpSigObiDeep` |

| band | meaning |
|---|---|
| **BUY NOW** (green) | all three pass upward |
| **SELL NOW** (red) | all three pass downward |
| **BLOCKED** (amber) | strong push, and the book **opposes** it |
| **WAIT / WAIT - SLOW / WAIT - NO BOOK** | no setup, and why |
| **TOO QUIET** / **WARMING UP** | the dead-market floors have the final say |

### Four changes to the proposed snippet

1. **No emoji.** MT5's Canvas renders Consolas; the snippet's emoji come out as boxes or
   vanish. A filled colour block with one plain word reads faster than an emoji anyway.
2. **The dead-market guards outrank the signal.** The snippet gates on `speed_sd < 1.0` alone.
   With `sd ≈ 0` the z-score is meaningless, so any signal built on it is meaningless — the
   exact fault in section 5. The band defers to `TOO QUIET`.
3. **`BLOCKED` is not the catch-all.** The snippet returned `BLOCKED` for everything that was
   not a clean BUY/SELL, so it would read BLOCKED almost permanently and therefore mean
   nothing. It now means specifically *the push is strong and the book is fighting it*;
   everything else says `WAIT`, and says why.
4. **His numbers became inputs, not constants.** 1.5 SD / 50% / 0.50 / 0.30 are the defaults,
   but they deliberately differ from the verdict engine's own thresholds (`InpDeltaStrong`
   0.30, `InpObiTrigger` 0.60), so they get their own knobs instead of silently disagreeing
   with the line printed underneath them.

The PATH line of v1.16 is **gone** — the band is that conclusion, larger. Verdict and stats
moved below it; canvas `SC(168)` → `SC(184)`.

### ⛔ THE STANDING CAVEAT, UNCHANGED

**`BUY NOW` is a hypothesis in large green letters. Nothing in this gauge has been validated
against forward price movement** — not one verdict, not the band. The three filters are
plausible and they are his, but plausible is what section 19 exists to warn about. The
measurement in section 19 has still not been run. **Do not size positions off this band until
it has.**

---

## 25. v1.19 — BOOK-MODE SPEED WAS MEASURING THE BROKER, NOT THE MARKET

**First, v1.17 is confirmed working.** On ETHUSDTp the stats line reads `BK base 9.2`: the
gauge selected the book stream, which delivers **~9 events/second against ~0.1 ticks/second**
— roughly **90×**. `AUTO` works, and the open question in section 23 is answered: on this
broker the book is overwhelmingly the livelier stream.

**Then Zee broke it in one sentence:** *"it says wait slow.. even when it made a large bar
upwards.. it didnt say BUY."*

Three frames, and the fault is visible in all three:

```
 8 v/s   SPEED -1.1 SD   BK base 9.2 sd 1.2   hit 0  / lift 0   +0%    OBI -0.37/-0.32
 9 v/s   SPEED -0.2 SD   BK base 9.2 sd 1.0   hit 22 / lift 2   -83%   OBI -0.70/-0.69
10 v/s   SPEED -0.1 SD   BK base 9.1 sd 1.1   hit 3  / lift 6   +33%   OBI +0.09/+0.15
```

**The book-event rate never leaves 8–10 per second.** Mean 9.2, sd ≈ 1.1 — a 12% coefficient
of variation. The band's `+1.5 SD` would need **10.9/s**, `+2 SD` would need **11.4/s**, on a
feed that appears capped near 10. **The velocity filter could essentially never pass.**

### The mistake was mine, in v1.17

Tick rate is **bursty** — that is the entire premise of this gauge, and Zee's own founding
quote says so ("10 ticks/sec in Asia, 80 at the NY open"). **Book-update rate on a throttled
feed is not bursty at all.** It is the broker's **push cadence**, roughly constant whatever the
market does. v1.17 made the gauge *run* on BTCUSDTp and ETHUSDTp, but what it then measured was
the broker's metronome.

What actually varies in those same frames is the **volume consumed**: `0`, then `24`, then `9`.
That is real aggression.

### The fix

In BOOK mode, the speed stream is now **consumed volume per second**, baselined and z-scored
exactly as tick counts are. The readout says **`v/s`** instead of `/s` so the number can never
be misread as ticks.

* Event count is **kept** for the `AUTO` decision — that comparison must stay like-for-like
  (events vs ticks, not lots vs ticks) — and is still logged as `bps`.
* The sample-size gate still counts **events**, which is the correct test for "is there enough
  data", independent of how much volume moved.

### Frame 2 is the proof case

```
hit 22 / lift 2   =  delta -83%        PRESSURE filter: PASS (needs -50%)
OBI -0.70/-0.69                        FRICTION filter: PASS (needs -0.50 / -0.30)
SPEED -0.2 SD                          VELOCITY filter: FAIL
```

**Two of the three filters had already passed for `SELL NOW`, on a bar that was dropping.**
Only the broken velocity filter held it back. That frame is the single best evidence that the
pressure and friction legs are measuring something, and that the velocity leg was measuring
nothing.

### ⚠ Known secondary effect, not yet fixed

`stalling` still derives from the **price range in the tick window**, and on a tick-starved
feed `range_base` sits near zero — below `InpMinRangeBase` (2.0 points) — so the stall test is
permanently false. **`COIL`, `WICK` and `FADE` therefore cannot fire on these crypto symbols**,
only `RIDE`, `IGNITION`, `PREDICT` and the master band. The band is unaffected because it does
not use `stalling`. Fixing it means deriving range from book touch prices rather than ticks.

### ⛔ And the caveat has not moved

The velocity filter now measures something real. **That is not the same as it being
predictive.** Section 19's correlation test still has not been run, and `BUY NOW` is still a
hypothesis in large green letters.

---

## 26. ⛔ THE TEST WAS RUN. THE ENGINE IS DEAD; THE FRICTION IS UNDECIDED.

Zee, watching ETHUSDTp: *"because even at lift +100% the price doesnot move.."*

He is right, and it is measurable. **810 logged seconds of ETHUSDTp**, from
`tickspeed2_ETHUSDTp.csv`. This is the section 19 test, finally run.

### His claim, tested directly

```
seconds with |delta| >= 0.90  (near-total one-sided consumption):   225

    price moved the SAME way :    9
    price did NOT move AT ALL:  210      <-- 93%
    price moved AGAINST      :    6
```

**93% of the time, near-total one-sided "aggression" is followed by no price change at all.**

And the reason is in the next line down:

```
seconds in which the mid price changed AT ALL:  43 of 783  (5%)
median move when it does move:                  0.120
```

**The mid updates roughly once every 18 seconds** while the book "consumes" continuously.

### Forward vs backward correlation, every horizon

Noise band on n=810 is **±0.035**.

| horizon | delta fwd / bwd | obi_touch fwd / bwd | obi_deep fwd / bwd |
|---|---|---|---|
| 1 s | +0.024 / +0.014 | +0.120 / **+0.187** | +0.116 / **+0.188** |
| 5 s | +0.087 / −0.027 | +0.171 / **+0.290** | +0.169 / **+0.294** |
| 15 s | +0.043 / −0.048 | +0.096 / **+0.312** | +0.101 / **+0.320** |
| 30 s | +0.068 / −0.090 | −0.076 / +0.143 | −0.071 / +0.147 |
| 60 s | −0.003 / −0.075 | −0.128 / +0.145 | −0.136 / +0.145 |
| 120 s | −0.053 / −0.085 | −0.186 / +0.134 | −0.202 / +0.138 |

**delta** — forward correlation never clears noise in any stable way. +0.087 at 5 s, back to
+0.043 at 15 s, −0.003 at 60 s. No coherent horizon. **It is noise.**

**OBI** — backward beats forward at **every single horizon**, and from 30 s onward the forward
correlation turns **negative** while backward stays positive. **OBI is a lagging mirror of
price** — precisely the INFER problem of section 3, one level up. The book repositions *after*
the move, not before it.

### Why: the limitation in section 4 is not a caveat here, it is the whole story

MT5's book cannot distinguish a **cancelled** order from a **filled** one. On PXBT's crypto
symbols the price updates in 5% of seconds while the book churns every 100 ms — so what the EA
counts as "212 lifted off the ask" is **overwhelmingly the market maker pulling and reposting
quotes**, not buyers lifting offers. There is no tape here; there is a quote engine
maintaining itself.

**This is a throttled LP quote feed, not an order-driven market.** The gauge's entire premise —
that event flow reveals aggression — has nothing to act on.

### ⛔ WHAT THIS MEANS

1. **Do not trade the master band on ETHUSDTp, BTCUSDTp or ETHBTCp.** `BUY NOW` on these
   symbols would be firing on quote churn. No threshold change fixes a signal that is not
   there — the 3.6% of seconds reaching +1.5 SD are not the good ones, they are just the
   extreme tail of the churn.
2. **`WAIT - SLOW` was not only a calibration failure.** v1.19 fixed a real bug (the velocity
   filter measured the broker's push cadence). But even with it fixed, the band would have
   been firing on noise. The gate was wrong AND the thing behind the gate is empty.
3. **Stop polishing the dial for these symbols.** A redesigned OBI bar would make a
   non-predictive number easier to read, which is worse than leaving it hard to read.

### What is still worth testing

**Gold on Blueberry.** Its archive runs ~**1.9 ticks/sec averaged over a full day** — 17× the
PXBT crypto rate — and it is a genuine tick stream rather than a 10 Hz quote metronome. The
entire premise of this EA was written for that feed, and it has **never been tested on it**,
because gold has been shut all session. Run the identical test the first London or New York
session gold is open:

```
py scratchpad/calibrate.py tickspeed2_XAUUSD.pi.csv
```

If forward beats backward there, the gauge has a foundation and the crypto result is simply a
statement about PXBT's crypto feed. If it does not, the concept is finished and the honest
move is to say so.

**The discipline that applies here is already written down** (`feedback_validate_profitability_not_capture`,
`feedback_apologies_dont_pay_hospital_bills`): a number on a screen is not evidence. This is
the first time in this build that the gauge has been checked against price, and it did not
survive the check.

---

## 27. ⚠ CORRECTION TO SECTION 26 — a second symbol disagrees about OBI

Section 26 was written from **one** symbol. Running the same script on `ETHBTCp` (281 s)
contradicts half of it, so the conclusion has to be split.

```
horizon |       delta       |     obi_touch     |      obi_deep
     1s |   -0.011/+0.067   |   +0.193/-0.173   |   +0.271/-0.124
     5s |   +0.024/+0.185   |   +0.265/-0.264   |   +0.400/-0.232
    15s |   -0.108/+0.277   |   +0.322/-0.215   |   +0.361/-0.237
```

On ETHBTCp, **OBI's forward correlation beats backward at every horizon** and the backward
correlation is *negative* — the exact opposite of ETHUSDTp, where backward won everywhere.

### What survives both symbols

| leg | ETHUSDTp | ETHBTCp | verdict |
|---|---|---|---|
| **delta** (the hit/lift bar) | noise, fwd never clears band | fwd ~0, **bwd +0.19…+0.36** | **DEAD on both** |
| **OBI** | mirror (bwd wins) | **leads (fwd +0.27…+0.40)** | **UNDECIDED — needs more data** |
| no-move at \|delta\| ≥ 0.90 | **93%** | **83%** | **robust on both** |

**Zee's instinct was right and the data backs it.** He said *"the hit lift meter with red /
green is not helping much. instead we could have that red green for the OBI"* — and the
measurement says exactly that: **delta is the dead leg, OBI is the surviving candidate.** So
the bar becomes OBI in v1.20, not as cosmetics but because the dead number should not have the
biggest display element.

### ⚠ The statistical caveat that applies to BOTH tables

These windows **overlap**, so the rows are heavily autocorrelated and the effective sample is
far smaller than `n`. At h = 60 on 281 rows, consecutive forward windows share 59/60 of their
data — about **5 independent observations**. So:

* **only the short horizons (h = 1, 2, 5) carry weight**; h = 30+ should be read as decoration
* ETHBTCp's `+0.432` at 60 s is **not** evidence of anything
* ETHBTCp at h = 1 (`+0.271` forward vs `−0.124` backward, noise ±0.060) **is** above noise and
  is the one cell worth taking seriously

**281 seconds is five minutes.** Before OBI is believed on any symbol it needs a session, not a
coffee break — and it needs to hold on more than one instrument.

### The standing instruction, unchanged

**Do not trade the master band yet on any of these symbols.** The engine leg is measuring quote
churn on both, which means `BUY NOW` currently requires a dead number to agree with a live one.

---

## 28. PREDICT HAS A TRACK RECORD — 10 firings, 0 wrong (v1.20)

Zee: *"it said predict up for a brief milisecond and it went up.. that was really cool. a
shooting candle up"*

Every `PREDICT` in both logs, scored against what price actually did next:

| symbol | verdict | n | horizon | right | flat | **wrong** |
|---|---|---|---|---|---|---|
| ETHUSDTp | PREDICT UP | 7 | 1 s | 2 | 5 | **0** |
| ETHUSDTp | PREDICT UP | 7 | 3 s | 3 | 4 | **0** |
| ETHUSDTp | PREDICT UP | 7 | 10 s | 3 | 4 | **0** |
| ETHBTCp | PREDICT UP | 3 | 3 s | 3 | 0 | **0** |
| ETHBTCp | PREDICT DOWN | 2 | 3 s | 1 | 1 | **0** |

**Ten PREDICT UP firings across two symbols. Wrong zero times, at every horizon.** And it beats
the base rate: on ETHUSDTp the mid moves at all in **16%** of 3-second windows, but moved in
**43%** of the windows following a PREDICT UP — and when it moved, it moved the predicted way
every single time.

### ⚠ Ten is ten

6 resolved / 6 correct is `p = 1/64 ≈ 1.6%` by coin flip — suggestive, **not** proof. The
firings may cluster in time, and this is one evening on two crypto CFDs. **This is the first
thing in the entire build with evidence behind it, and it is still nowhere near enough to size
a position on.**

### Why it was invisible — and what changed

`PREDICT` was being printed on the **small verdict line** while the big band said `WAIT - SLOW`,
because the band used its own thresholds (stricter on speed, looser on OBI) rather than the
verdict's. He caught it by eye, for "a brief milisecond". The signal with the track record was
the one not being displayed.

**v1.20:**

1. **The band is driven by `PREDICT`.** `BUY NOW` / `SELL NOW` now mean *PREDICT fired*. The
   3-filter checklist, which has **no** track record, is demoted to `LEAN BUY` / `LEAN SELL` in
   darker colours.
2. **The band latches for `InpSignalHoldSec` (4 s) with a visible countdown** — a one-second
   flash is not something a human can act on, and hiding the signal's age would be worse than
   not showing it.
3. **The bar now carries OBI, not delta**, with the resting walls (`ask N` / `bid N`) on its
   ends and the deep-book value as a white tick mark. Delta drops to a figure in the centre
   label. This is Zee's suggestion, and section 27 is why it is right: delta is the dead leg.

### What PREDICT requires, for the record

```
z >= InpPredSigma (1.0)  AND  book has >= 2 levels
    AND  delta >= +InpDeltaStrong (0.30)  AND  OBI_touch > +0.60  AND  OBI_deep > +0.30
```

Note it is **OBI-gated at 0.60** — the stricter of the two legs, and the one that led price on
ETHBTCp. That is consistent with where the evidence points: **the friction leg is carrying this
signal, not the engine leg.**

### Next

**Let it run and collect firings.** Ten is a hint; fifty would be an argument. Re-run:

```
py monitor/strategy_lab/tickspeed_calibrate.py tickspeed2_ETHUSDTp.csv
```

and re-score the PREDICT table. **Until that count is far higher, `BUY NOW` is still a
hypothesis — a better-supported one than anything else here, but a hypothesis.**

---

## 29. HE WAS RIGHT: AT PEAK SPEED THE GAUGE WAS SILENT (v1.21)

Zee: *"when the speed goes really really high.. then at that instant we need to tell the user
whether this speed is converting into a buy direction to detect a breakout.. mostly it says
blocked etc and not predict when the speed is fully high.. but i might be wrong"*

**He was not wrong.** 1,147 logged seconds of ETHUSDTp, bucketed by z:

| speed bucket | n | what the gauge said |
|---|---|---|
| z < 1 | 1043 | NO TRADE 983, WARMING UP 60 |
| 1 ≤ z < 2 | 66 | WATCH 51, **PREDICT UP 5, PREDICT DOWN 2** |
| 2 ≤ z < 3 | 17 | **MIXED 11**, PREDICT UP 2, RIDE UP 1 |
| **z ≥ 3** | **21** | **MIXED 21 — 100%** |

**At the highest speeds the gauge called direction zero times out of twenty-one.** The one
moment it most needed to speak, it said "MIXED".

### Why — and it is structural, not a threshold

`RIDE` requires a **one-sided delta**. At peak activity **both sides are consuming**, so
`|delta|` falls below `InpDeltaStrong` and `MIXED` is the fallback. **The engine leg collapses
exactly when the market is busiest.**

And the numbers say delta deserves to collapse — agreement with the **next 3-second** move:

| bucket | **delta** agrees | **OBI** agrees |
|---|---|---|
| z < 1 | 60% | **82%** |
| 1–2 SD | 62% | **77%** |
| **z ≥ 2** | **25%** | **88%** |

**At high speed delta is worse than a coin flip (25%, n=8).** OBI is at 88%.

### The fix: `BREAK UP` / `BREAK DOWN`

Above `InpHighSigma`, direction is now read from **OBI plus where price has actually travelled
in the window**, instead of from delta. New verdicts `BREAK UP` / `BREAK DOWN`, shown on the
band in blue/orange — **deliberately not** `BUY NOW`.

### ⚠ THE MIRROR TEST — why it is called BREAK and not BUY

| horizon | OBI vs **NEXT** move | OBI vs **PAST** move |
|---|---|---|
| 1 s | 88% (n=75) | **89%** |
| 3 s | 81% (n=194) | **86%** |
| 10 s | 71% (n=488) | **74%** |

**OBI matches the past move slightly better than the next one at every horizon. It is
COINCIDENT, not predictive.** The 80–88% is not foresight — it is OBI tracking a move that is
already running, and that move persisting.

For a scalper watching a burst that has already started, "which way is this one going" is a
real question and a coincident read answers it. **But it is not the 1–2 second head start of
section 12, and the label must never imply one.** Hence `BREAK UP` — *this burst is going up*,
not *this will go up*.

### ⚠ And the real sample size

The 194 moving rows cluster into **~38 distinct episodes**. Thirty-eight, not 194 — the rows
inside one burst are not independent observations. Every percentage above should be read
against **n ≈ 38**.

### Where this leaves the three legs

| leg | status |
|---|---|
| **speed (z)** | works as a *trigger* — it finds the bursts |
| **delta (engine)** | **dead.** 25% at high speed, 93% of one-sided flow followed by no move |
| **OBI (friction)** | **coincident.** Best thing here, but mirrors as much as it leads |
| **PREDICT** | 10 firings, 0 wrong — still the only thing with a forward record, still n=10 |

---

## 30. ACCELERATION — TESTED, AND IT DOES NOT HOLD (v1.22)

Zee: *"the needle.. instead of showing speed.. it should show acceleration.. because.. if its
accelerating.. rate of change of speed.. then we can say wow an upcoming move is incoming..
visualizing speed going up we cannot say ok the move is here (before time).. test"*

**Tested on 1,387 logged seconds of ETHUSDTp.** `accel = z[i] − z[i−1]`. Noise band ±0.027.

### Q1 — does it anticipate that a move happens?

| horizon | corr(**level**, \|move\|) | corr(**accel**, \|move\|) |
|---|---|---|
| 1 s | −0.010 | **−0.058** |
| 2 s | +0.030 | −0.035 |
| 3 s | **+0.048** | −0.001 |
| 5 s | +0.030 | −0.004 |
| 10 s | +0.041 | −0.006 |

**Acceleration is zero-to-negative at every horizon.** Level is weakly positive.

### Q2 — hit rate, P(price moves at all in the next 3 s). Base rate **19%**

| condition | n | moves | lift |
|---|---|---|---|
| **level z ≥ 2** | 50 | **34%** | **+15 pts** |
| level z ≥ 3 | 26 | 27% | +8 |
| accel ≥ +3 | 32 | 28% | +9 |
| accel ≥ +2 | 67 | 21% | +2 |
| accel ≥ +1 | 184 | 21% | **+1 — nothing** |

**Plain speed level is the better trigger.** The best acceleration cut (+3) still loses to
`z ≥ 2`, on a smaller sample.

### Q3 — is acceleration *early*? Does it lead the speed peak?

```
corr(accel[i], z[i+1]) = +0.022
corr(accel[i], z[i+2]) = -0.005
corr(accel[i], z[i+3]) = +0.032
```

**No.** All inside the noise band. It does not arrive before the speed does.

### Why it fails — and the idea is not stupid

Two reasons, and both are about what it is being applied to, not about the concept:

1. **`z` is already a differenced quantity.** It is a normalised deviation from a 300-second
   rolling baseline, so it has *already* had the level removed. Differentiating it again mostly
   amplifies noise — which is exactly what those negative correlations are. This is the
   ordinary behaviour of a derivative on a noisy series, not a quirk of this feed.
2. **There is nothing underneath to differentiate.** The "speed" being differenced is consumed
   volume on a quote-churn feed that section 26 showed is overwhelmingly the maker requoting.
   **Differentiating a signal with no information in it gives no information, faster.**

On a real tape — gold on Blueberry, ~1.9 ticks/sec of genuine tick flow — the question is open
again and worth re-running, because there the underlying series carries something.

### What shipped

**The needle did not change.** It keeps the quantity that measured best (`z ≥ 2` → 34% against
a 19% base). Acceleration is shown as a figure (`acc +1.2`) on stats line 2 so it can be
watched, replacing the OBI field that became a **duplicate** in v1.20 when OBI took over the
bar and its labels.

**This is the doctrine working as intended** (`feedback_backtests_hallucinate_take_all_chances`,
`feedback_validate_profitability_not_capture`): a good hypothesis was proposed, measured
against real logged data, and **not shipped as a default** when the data declined it. The
readout is there so the idea can keep being watched on a better feed.

---

## 31. ⭐ THE SIGNAL IS REAL — AND IT STILL CANNOT BE TRADED HERE (v1.23)

Zee: *"i think the prediction is getting better. it said buy now and it went up a few seconds
later.. can u check the last candle we made and see our accuracy.. its looking good u know ;)"*

### Part 1 — he is right, and it survives the controls

**1,688 seconds of ETHUSDTp (23:11 → 23:40).** Every directional verdict scored:

| verdict | n | h | right | flat | **wrong** | base rate |
|---|---|---|---|---|---|---|
| **PREDICT UP** | 11 | 3 s | 5 | 6 | **0** | up 11% |
| **PREDICT UP** | 11 | 10 s | 7 | 4 | **0** | up 25% |
| PREDICT DOWN | 4 | 10 s | 1 | 3 | **0** | down 20% |
| BREAK UP | 7 | 10 s | 5 | 2 | **0** | up 25% |
| BREAK DOWN | 1 | 3 s | 1 | 0 | **0** | down 8% |

**Zero wrong, across 24 directional calls.** And the two things that usually destroy a result
like this were checked and did not:

* **Clustering** — the 11 PREDICT UPs fired at seconds 504, 719, 743, 756, 774, 775, 838, 1217,
  1277, 1481, 1596: **10 separate episodes**, not one burst seen eleven times.
* **Upward drift** — the window did drift up (base 25% up vs 20% down at 10 s), so a permutation
  test was run: **20,000 random draws of the same number of firings.** Random matched or beat
  this in **0.1% of draws at h=3 s and 0.2% at h=10 s** — and the same when drawing random
  *episodes* rather than random seconds.

**p ≈ 0.001–0.002. This is the first genuine positive result in the entire build.**

### Part 2 — and then the only test that pays bills

```
spread on ETHUSDTp              1.310     FIXED (min = max = median = 1.310)
median move 10 s after PREDICT  0.090
                                -------
the spread is 14.5x the move the signal predicts
```

Buy the **ask** on PREDICT UP, sell the **bid** later, all 11 firings:

| hold | winners | losers | net | avg/trade |
|---|---|---|---|---|
| 3 s | **0** | **11** | −13.15 | −1.196 |
| 10 s | **0** | **11** | −13.16 | −1.196 |
| 30 s | 1 | 10 | −12.11 | −1.101 |

**Eleven correct predictions. Eleven losing trades.**

Even the **90th-percentile** 10-second burst does not clear the spread:

| symbol | spread | spread (bp) | p90 burst | burst / spread |
|---|---|---|---|---|
| ETHUSDTp | 1.3100 | 4.9 | 0.470 | **0.36×** |
| ETHBTCp | 0.0000 | 4.1 | — | **0.23×** |

PXBT's crypto CFDs carry a **fixed ~4.9 basis point spread**, and the moves this signal finds
are a third of it. **No signal, at any accuracy, can pay that.**

### What shipped — the guard, in code

A rolling estimate of the typical burst (mean + 1.28 sd of the `InpBurstSec` move ≈ p90) is
divided by the live spread into `edge`, shown on stats line 2 as `edge 0.4x`. **When
`edge < InpMinEdgeRatio` (2.0) the band refuses to show BUY/SELL and says `SPREAD TOO WIDE
0.4x` instead.**

This is `feedback_validate_profitability_not_capture` and `feedback_greed_has_no_measurement_rulebook`
turned into code, so it cannot be forgotten at 3am or rationalised past on a good run.

### ⛔ WHAT TO DO WITH THIS

**Do not trade PREDICT on ETHUSDTp, ETHBTCp or BTCUSDTp.** Not because the signal is wrong —
it is the most convincing thing here — but because it predicts moves 14× smaller than the cost
of entering.

**The signal needs an instrument where `edge >= 2`.** Attach the gauge and read the number;
it now declares viability in one glance. The obvious candidate is the one this EA was written
for and that has been shut all session: **gold**, where a spread near 0.20–0.30 meets
London/NY bursts of 0.50–1.00 — a ratio of 2–4× rather than 0.36×.

**That is the next test, and it is now a one-glance test.**

---

## 32. v1.24 — THE SPREAD GUARD BECOMES AN INPUT (OFF)

Zee: *"for now u can turn off the spread guard.. as we test / refine our EA.. for Monday"*

Legitimate — the veto hides the band entirely on crypto, which makes it impossible to *watch*
PREDICT behave while refining it. `InpSpreadGuard` now defaults **false**.

**But the finding does not leave with the veto.** With the guard off, a signal that cannot pay
the spread is still shown — **muted** (dark green / dark red instead of bright) and **labelled
with its own ratio**: `BUY NOW  3  0.4x`. A clean, confident green `BUY NOW` can never appear
on a symbol whose spread eats the move. That was the only part that had to survive.

**→ Turn `InpSpreadGuard` back to `true` before trading anything on Monday.**

---

## 33. v1.25 — `GET READY`, measured before it was built

Zee: *"if the speed is above 25% of the speed dial.. and the speed is consistently increasing..
then we can write GET READY.. because that's how we predict early on.. like user can say OK ..
now get ready.. ready to click buy/sell"*

Tested on **2,153 seconds holding 20 PREDICT firings**, before picking a threshold:

| rule | armed | catches | median lead | false alarms |
|---|---|---|---|---|
| z ≥ 0.50 & rising | 356 | 16/20 | 3 s | 90% |
| **z ≥ 0.75 & rising** | **270** | **15/20** | **4 s** | **90%** |
| z ≥ 1.00 & rising | 185 | 13/20 | 4 s | 90% |
| \|OBI\| ≥ 0.6 (both) | 801 | 12/20 | 4 s | 93% |
| either of the above | 1010 | 18/20 | 3 s | 92% |

**Shipped: `z >= InpReadySigma` (0.75) AND speed rising.** Arms on 12.5% of seconds, catches
15 of 20 firings, ~4 seconds of warning. Amber, never green/red, and it says `GET READY UP?` /
`GET READY DN?` only when the book agrees — with the question mark.

**Two design decisions worth recording:**

1. **The OBI arm was NOT included, although he asked for it.** On its own it arms on 801–1024
   of 2,153 seconds — **37% to 48% of the session.** A warning light that is on half the time
   is not a warning. Speed-rising arms on 12% and catches more.
2. **Nine out of ten GET READYs go nowhere.** That is inherent to an early warning and it is
   fine for the job he described — *hand on the mouse* — but it is **not a signal**, must never
   be coloured like one, and the 90% has to stay on the record so it cannot quietly be promoted.

---

## 34. WHICH INSTRUMENT HAS A SPREAD WORTH TRADING

From his Market Watch, 2026-10-02 23:48. Spread converted to **basis points**, which is the
only way to compare a ¥157 pair with an $84,000 one.

| symbol | spread | **basis pts** | vs ETHUSDTp | open now? |
|---|---|---|---|---|
| **USDJPYp** | 0.020 | **1.27** | **3.9× tighter** | Mon |
| EUR50p | 1.600 | 2.56 | 1.9× | Mon |
| **BTCUSDTp** | 25.000 | **2.96** | **1.7× tighter** | **yes** |
| ETHBTCp | 0.000013 | 4.12 | 1.2× | yes |
| BRENTp | 0.050 | 4.70 | 1.0× | Mon |
| ETHUSDTp *(tested: edge 0.36×)* | 1.310 | 4.91 | — | yes |
| BNBUSDTp | 0.410 | 5.33 | 0.9× | yes |
| XAGUSDp | 0.060 | 9.94 | 0.5× | Mon |
| SOLUSDTp | 0.130 | 10.96 | 0.4× | yes |
| DOGEUSDTp | 0.00015 | 16.14 | 0.3× | yes |

### ⚠ A tighter spread is only half the ratio

`edge = burst / spread`. **Volatility does not scale with price between instruments**, so a
3.9× tighter spread on USDJPY does *not* mean a 3.9× better edge — USDJPY is a low-volatility
major and its bursts are correspondingly smaller. **Any projection from this table is a guess.
Only the live `edge` readout settles it, per instrument, per session.**

### What this says to do

* **Tonight:** attach to **BTCUSDTp** (best spread of anything open, 1.7× tighter than ETH) and
  simply read `edge` on stats line 2. Also worth a look: nothing else open beats ETHUSDTp
  except ETHBTCp, marginally.
* **Avoid:** SOLUSDTp (10.96 bp) and DOGEUSDTp (16.14 bp) — three to five times worse than ETH.
* **Monday:** **USDJPYp first** by spread. And **`XAUUSDp` is not in his Market Watch at all —
  add it.** Gold is the instrument this EA was written for, has never once been tested, and is
  the whole reason the premise exists.

---

## 35. v1.26 — THE DIAL NOW SHOWS BIAS, SPEED BECOMES A BAR

Zee: *"the speed dial is telling me nothing when i look at the needle for long times and its
just at slow speeds.. i think the dial can be more useful if it shows a BIAS.. so on the left
of the dial is SELL.. on the right of the DIAL is BUY.. this way i can look at the needle and
say .. OOO we're on the sell side don't take a buy trade yet.. then below this new dial we can
have the speed as a 0-100 progress bar"*

**This is the right way round, and every measurement in this file says so:**

| | measured | role |
|---|---|---|
| **OBI** | agreed with the next 3 s move **82% / 77% / 88%** across speed buckets | **direction** |
| **speed** | `z ≥ 2` → 34% chance of a move vs a 19% base rate | **trigger only** |

The informative quantity was on a bar; the trigger had the big needle. **Swapped.**

### The dial

* sweeps **SELL (left, −1) → BALANCED (top, 0) → BUY (right, +1)**
* driven by the **mean of touch and deep OBI**, eased at 0.20 — touch alone flickers with every
  pulled quote (v1.11), deep alone is slow, and this is a needle meant to be watched for long
  stretches
* band in five zones: heavy sell, sell, neutral, buy, heavy buy
* **three markers**: centre (balanced book) and the **two OBI levels `PREDICT` actually uses**
  (±`InpObiTrigger`), so the distance from a real trigger is visible, not guessed
* readout under it: `+0.52` plus a word — `SELL SIDE - HEAVY` / `SELL SIDE` / `BALANCED` /
  `BUY SIDE` / `BUY SIDE - HEAVY`, or `NO BOOK - NO BIAS`

### The speed bar

0–100 of full scale (`baseline + 3 SD`), filling left to right, coloured by zone, with a
**marker where +2 SD sits** — above that line the dial is worth reading. Labels: live rate on
the left, delta on the right, `SPEED 34/100  +1.2 SD` in the centre.

### What was retired

**The OBI bar is gone.** The dial carries OBI now, and keeping both would be the same number
twice — the exact duplication already fixed twice in this file (v1.09's bar-vs-labels, v1.22's
stats-line OBI). Delta survives as a figure on the bar's right-hand label.

### ⚠ Note on what this does and does not change

This is a **display** change. No threshold, verdict or signal was touched: `PREDICT`, `BREAK`,
`GET READY` and the band all compute exactly as they did in v1.25. It makes the informative leg
easy to watch — **it does not make it more predictive**, and section 31 still stands: OBI is
coincident as much as leading, and on ETHUSDTp the moves it finds are 14× smaller than the
spread.

---

## 36. IS THE SPEED BAR LATE? NO — IT IS *COINCIDENT*, WHICH IS WORSE

Zee: *"i think after the candle falls it gives the speed.. what we intended was to give speed
using ticks so we can see the speed during the bar formation to see early on what the speed is
before the breakout"*

Lead-lag cross-correlation of `speed[i]` against `|price move|` at `i+k`, **3,269 seconds**,
noise band ±0.017:

```
  k=-4  +0.065    speed leads by 4s
  k=-1  +0.081    speed leads by 1s
  k=+0  +0.696    SAME SECOND        <-- the peak, by a factor of 8
  k=+1  +0.088    speed lags by 1s
  k=+2  +0.036    speed lags by 2s
```

**The bar is not late.** The peak is at **k = 0**, and ±1 second is almost perfectly symmetric
(+0.081 before, +0.088 after). Nothing is arriving after the fact.

**But it is exactly coincident, which gives no warning at all** — and that is what he actually
needs. The reason is mechanical and was baked in at v1.19: **in BOOK mode "speed" is consumed
volume, and volume is consumed *as* price moves.** A correlation of 0.696 at zero lag means it
is very nearly measuring the move itself. It is a thermometer inside the fire.

### His original design is not possible on this symbol

```
tick-rate baseline   mean 0.11 /s   max 0.26 /s     <- one tick every 9 seconds
book-event baseline  mean 8.99 /s   max 9.50 /s     <- flat broker cadence, no variance
```

**There is no tick flow on ETHUSDTp to form a speed from.** "Speed during bar formation,
before the breakout" needs a tape; this feed has a quote metronome. This is now the **third**
independent finding pointing at the same conclusion (sections 22, 26, 30): the premise needs
gold or an FX major, not a crypto CFD.

### What *does* arrive early — one faint thing

Everything tested correlates at zero: book thinning, touch volume, book total, all between
−0.031 and +0.004 against a ±0.017 noise band. **But conditioning on the big moves shows a
small, consistent signature:**

| lead | book thin ratio before a **top-decile** move | before a normal second | diff |
|---|---|---|---|
| 1 s | 1.003 | 1.071 | **−0.068** |
| 2 s | 1.000 | 1.071 | **−0.071** |
| 3 s | 1.011 | 1.070 | −0.059 |
| 5 s | 1.010 | 1.070 | −0.060 |

**The book sits ~6% thinner for several seconds before a big move** — the liquidity-vacuum
idea of section 11, with a real if faint signature, consistent at every lead tested.

**Nothing was shipped for it.** A per-second correlation of zero is not something to put a
signal on, and doing so would be exactly what `feedback_backtests_hallucinate_take_all_chances`
forbids. It is logged (`book_total`, `book_base`) and can be re-tested on a better feed.

### The early warning already exists — it is `GET READY`

What he is describing — *"see early on what the speed is before the breakout"* — is v1.25.
`GET READY` arms on **speed rising**, not speed level, and measured **~4 seconds of warning**
before a PREDICT, catching 15 of 20. That is the only validated lead in the build. **Watch the
amber band, not the speed bar, for early.** And its 90% false-alarm rate is why it says GET
READY and not BUY.

---

## 37. PASSIVE ABSORPTION — TESTED, AND IT IS INVERTED (v1.27)

Zee asked for two things to be implemented. Both were measured first on **3,269 seconds of
ETHUSDTp**. Both ship **OFF**, each carrying its own hit rate in its on-screen label.

### The absorption theory

> *"sometimes the OBI says sell side is heavy but price isnot moving down. is that a signal?
> Yes, absolutely … a hidden institutional buyer is sitting underneath, absorbing every single
> sell order … This is your cue to enter a BUY."*

| rule | n | right | wrong | **hit** | base |
|---|---|---|---|---|---|
| absorb-BUY, refuse 3 s, next 3 s | 659 | 22 | **133** | **14%** | 52% |
| absorb-BUY, refuse 3 s, next 10 s | 659 | 74 | 277 | 21% | 53% |
| absorb-BUY, refuse 60 s, next 60 s | 470 | 176 | 250 | 41% | ~55% |
| absorb-BUY, refuse 120 s, next 60 s | 477 | 198 | 231 | 46% | ~55% |
| absorb-SELL, refuse 3 s, next 3 s | 704 | 16 | **171** | **9%** | 48% |

**At short horizons it is wrong 86–91% of the time, and it never beats the base rate at any
window tested.** The apparent improvement as the window lengthens is regression toward the
session's upward drift, not signal.

**The control explains why.** Plain `OBI ≤ −0.5` with **no** refusal condition gives 12% at
3 s — so the "price refuses to drop" filter adds essentially nothing, and the real story is
simply:

> **a heavy sell wall means price falls.**

That is the 82–88% OBI agreement of section 29 seen from the other side. **His observation is
real — the OBI does show a heavy sell side while price sits still — but the resolution is the
opposite of the theory: price then goes down, not up.**

**This does not mean absorption is not a real phenomenon.** It is well documented in
order-driven markets. It does not appear on a throttled CFD quote feed where OBI is partly a
mirror of price (section 26) and the mid updates in 5% of seconds. **Worth re-testing on gold.**

### The thin-book trigger

Section 36 found the book sits ~6% thinner before a big move. True — and it does **not**
convert into a trigger. Base rate of a big move in any second: **9.1%**.

| condition | n | big move within 1 s | within 3 s | within 5 s |
|---|---|---|---|---|
| thin ≤ 0.90 | 1783 | 10.2% (**+1.1**) | 25.4% (**−2.0**) | 37.2% (**−8.3**) |
| thin ≤ 0.80 | 1325 | 10.0% (+0.9) | 25.0% (−2.3) | 35.8% (−9.7) |

**One point of lift at one second, negative beyond it.** A real conditional difference that is
not a usable signal — the difference between "statistically present" and "tradeable", which is
the whole lesson of section 31.

### How they shipped

```
InpShowAbsorb  = false    ->  "ABSORB BUY? 14%" / "ABSORB SELL? 9%"   (blue-grey)
InpShowThin    = false    ->  "THIN BOOK 0.85x"                       (dim amber)
```

**Both default OFF, and both print their measured hit rate in the label**, so neither can be
watched without its own evidence beside it. Turn them on to observe; they are instruments, not
signals.

**Nothing was deleted and nothing was talked out of.** Both ideas were implemented exactly as
described, then measured, and the measurement travels with them on screen.

---

## 38. ⭐⭐ THE SPRING — THE BEST RESULT IN THIS BUILD (v1.28)

Zee: *"if the needle is towards heavy sell.. but the price refuses to go down .. until the
needle turns towards buy again.. and it starts moving upwards the price.. then this looks like
it is a SPRING.. the spring is being compressed till it throws the price up finally"*

He described a **sequence**, not a state — which is why section 37's state test missed it.

**4,658 seconds. 45 releases** (OBI crossing from ≤ −0.25 to ≥ +0.25) in **36 distinct
episodes.** Base rate 57%.

| test | n | right | wrong | **hit** |
|---|---|---|---|---|
| release, next 3 s | 45 | 17 | 1 | **94%** |
| release, next 10 s | 45 | 28 | 6 | 82% |
| **clean subset** (price not already up), next 3 s | 32 | 12 | **0** | **100%** |
| **clean subset, next 10 s** | 32 | 21 | 2 | **91%** |
| clean subset, next 30 s | 32 | 23 | 5 | 82% |

### It passes the mirror test — the first thing here that does

```
h = 10s      FORWARD up 82%        BACKWARD up 24%
```

**Price was falling before the release and rises after it.** Every other signal in this file
matched the past as well as the future (sections 26, 29). This one genuinely *reverses*. It is
not OBI tracking a move already underway.

### And the permutation test

**20,000 random draws of 45 seconds. Random matched it in 0.01%.** `p = 0.0001`, on 36
independent episodes.

### ⚠ One correction to his model — from the control

Requiring price to have **refused to fall** during the compression **adds nothing**: the
releases where price *did* fall scored **86–88%**, as well or better.

**The trigger is the TURN, not the refusal.** He named the right moment — *"until the needle
turns towards buy again"* — and the mechanism is simply that turn. The compression story is a
good explanation but it is not what carries the signal, so it is not in the code.

### And the same wall

| horizon | median move | spread |
|---|---|---|
| 3 s | +0.000 | 1.310 |
| 10 s | +0.090 | 1.310 |
| 30 s | +0.270 | 1.310 |

Buy the ask on release, sell the bid later: **0 winners of 45** at 3 s, 10 s and 30 s; **1 of
45** at 60 s. Best single move in 45 firings was +2.01 — the only one that clears the spread.

**The signal is real. ETHUSDTp cannot pay for it.** This is now the specific thing to run on
gold on Monday.

### What shipped

* `SPRING UP` / `SPRING DOWN` on the band, **ranked above everything else** — it has the best
  evidence. Muted with its ratio attached when `edge` cannot pay.
* **The coil**, drawn in a strip to the right of the dial: nine zigzags that compress as the
  book sits one-sided, with a `%` load figure, snapping open and reading `FIRED` on release.
  Amber while loading past 60%, green/red when it fires.
* `InpShowSpring` (default **true** — this is the one thing here that earned its default),
  `InpSpringLoad` 0.25, `InpSpringFire` 0.25.

---

## 39. v1.29 — TWO SPRINGS, ONE PER SIDE

Zee: *"would it work if we had 2 springs.. 1 for buyers and 1 for sellers? that way the one
that fires tells us ok go SHORT and SELL .. or go LONG and buy… just trying to make the spring
theory simpler to read visually"*

**Yes — and it is not only cosmetic. It fixes a real flaw in v1.28.**

The single shared coil incremented on **either** side, so a book oscillating between sell-heavy
and buy-heavy kept loading it as though it were one sustained compression. Two counters each
track their own side and bleed the other, which is what compression actually means.

### Checked before changing the gate

Changing the load gate could silently drop real fires, so it was measured first. **71 releases:**

| | fires kept | hit rate (clean, next 10 s) |
|---|---|---|
| as originally tested (no gate) | 71/71 | **86%** |
| shared coil > 0.3 (v1.28) | 70/71 | 85% |
| **per-side coil > 0.3 (v1.29)** | **61/71** | **86%** |

**Ten fewer signals at identical accuracy.** Fewer, cleaner.

*(Note the sample has grown from 45 to 71 releases as logging continued, and the clean-subset
hit rate settled from 91% on n=32 to **86% on n=48** — still far above the 57% base rate. It is
holding up as data accumulates, which is the only way a result earns trust.)*

### The layout, which is the point of the idea

```
  LEFT coil  ── loaded by a SELL-heavy book ──  fires LONG   (green)
  RIGHT coil ── loaded by a BUY-heavy  book ──  fires SHORT  (red)
```

Each spring sits on the side that is **compressing** it and throws price the other way — which
is what a spring physically does. A v1.28 coil sitting at 80% told you nothing about which side
had loaded it without reading the needle; now it is unambiguous at a glance.

### The labelling trap, avoided

Each coil is labelled by **what it does when it fires** (`LONG` / `SHORT`), never by which side
loaded it. "The sell spring" that makes you **buy** is the confusing half of his own phrasing,
and naming them by their action removes it entirely.

Under each: the per-side load `%`, or `FIRED`. Grey below 5%, dim while loading, **amber past
60%**, green/red on fire.

### Unchanged

**The trigger, thresholds and measured performance are identical to v1.28** — same single-second
cross through ±`InpSpringFire`. This is a display and bookkeeping change, so the 86% carries
over without needing to be re-earned.

---

## 40. v1.30 — the coils carry both namings (CURRENT)

Zee: *"i think the labels are switched. the left spring loads up on sell heaviness so it should
be labelled SHORT"* → then, after the check below: *"ok then let's keep the labels as is for
now.. no change"*

**He was right about what loads them; the v1.29 label was the trade, which runs the other way.**
Verified from first principles on his own log:

```
when OBI is negative:  mean resting bid 50  vs  ask 307   -> the SELL side is the heavy one

LEFT  coil (loads sell-heavy), on release:  next 3s  UP 33 / DOWN  3   -> price RISES 92%
RIGHT coil (loads buy-heavy),  on release:  next 3s  UP  5 / DOWN 36   -> price FALLS 88%
```

That is his own original description — *"heavy sell … throws price up finally"* — so the
mechanism was never in dispute, only what the word on the coil referred to. **Labelling the
left coil SHORT and acting on it would take the opposite side of a 92% signal.**

**Both namings now appear, and cannot be confused:**

```
      SELL                    BUY
      WALL                    WALL        <- what COMPRESSES it (his naming)
       |                       |
      62%                     12%         <- load while winding
     LONG!                  SHORT!        <- the trade when it lets go
```

Reads as a sentence: *a SELL WALL compresses the left spring, and its release → LONG.* Wall
label is red on the left, green on the right; the action goes green/red on fire.

**Settled — no further label changes.** This is the current shipped state.

---

# CURRENT STATE — v1.30 on both terminals

| | |
|---|---|
| **Best signal** | **SPRING** — 86% at 10 s on the clean subset (n=48), p=0.0001, 71 releases in ~36 independent episodes, **passes the mirror test** (backward 24% vs forward 82%) |
| Second | `PREDICT` — 10 firings, 0 wrong, but n=10 |
| Dead | `delta` / the engine leg — 25% at high speed; 93% of one-sided flow precedes no move |
| Rejected after testing | acceleration (§30), passive absorption (§37), thin-book trigger (§37) |
| **Blocker** | **spread.** ETHUSDTp spread 1.310 vs a median post-spring move of 0.090–0.270. **0 winners of 45** buying the ask and selling the bid |

**Monday, in order:**
1. Add `XAUUSDp` to Market Watch — it is not there, and gold is what this EA was written for.
2. Attach and **read `edge` on stats line 2 before anything else.** Below 2.0, nothing here can pay.
3. Set `InpSpreadGuard = true` before any real trade.
4. Log a session, then `py monitor/strategy_lab/tickspeed_calibrate.py tickspeed2_XAUUSDp.csv`
   and re-run the spring grid. Everything above was measured on a quote-churn crypto CFD; none
   of it is yet known to hold on a real tape.

---

## 41. ICEBERG / RELOAD TRACKING — implemented, then measured (v1.31 / v1.32)

The idea is the best in the report and it is **exactly right about the constraint**: cumulative
consumption at a *static* price, measured against the peak size ever visible there, needs **no
aggressor flags at all**. It sidesteps the limitation this file has documented since section 3.

### Four deviations from the spec

1. **`g_ice_bid_px` / `g_ice_ask_px` dropped.** The spec writes them on every reset and never
   reads them — the comparison uses `g_ta_px` / `g_tb_px`, which already hold the level. Dead
   state a future reader would assume was load-bearing.
2. **The replenishment counter is actually used.** The spec computes `g_ice_*_repl` then never
   tests it. **Refill is the iceberg signature** — consumption alone can exceed peak simply
   because ordinary new orders arrived. Detection now requires consumption past the ratio
   **and** genuine replenishment past the peak.
3. **The delta gate is OFF by default** (`InpIceNeedDelta`). The spec requires a one-sided delta
   to confirm. Delta is the leg this project **measured as dead**: 25% agreement at high speed
   (§29), and 93% of near-total one-sided flow precedes no price move (§26). Gating a new
   signal on a dead variable suppresses it for no information.
4. **Ranked below `SPRING` and `PREDICT`**, not above. An untested verdict must not shadow a
   measured one.

### Then it was measured, and it is inverted

Reconstructed at 1-second resolution from 8,520 logged seconds. Base rate 53% up.

| ICEBERG BID → expect **UP** | n | next 3 s | next 10 s | next 30 s |
|---|---|---|---|---|
| ratio 2× | 4327 | 39% | 43% | 47% |
| ratio 3× | 3049 | 36% | 41% | 45% |
| ratio 5× | 1623 | 28% | 35% | 37% |
| **ratio 8×** | 467 | **24%** | 29% | 34% |

| ICEBERG ASK → expect **DOWN** | n | next 3 s | next 10 s |
|---|---|---|---|
| ratio 3× | 3074 | 27% | 33% |
| ratio 5× | 1585 | 24% | 33% |

**Both sides inverted, and the inversion gets monotonically STRONGER as the ratio rises** —
39% → 24% going from 2× to 8×. That consistency means it is not noise: **heavy consumption at
the bid genuinely precedes price falling.** Which is simply the market working — the bid is
being eaten, so price drops. The "hidden reloading buyer" reading requires the refills to be
one actor, and nothing here shows that.

**And it is not rare: it fires in 36% of all seconds** (3,063 of 8,520). A near-permanent state,
not a signal.

### ⚠ What this test could NOT check

* It runs at **1-second resolution** from the schema-2 log. The EA tracks **per book event**,
  roughly 9× finer, and may separate things this cannot.
* **The replenishment gate (deviation 2) is not in the approximation**, because schema 2 never
  logged refills. That gate is the part most likely to cut the 36%, and it is untested.

### How it shipped

`InpShowIceberg = false`, same treatment as absorption and the thin-book trigger. **The state is
logged either way** — schema 3, `tickspeed3_<SYMBOL>.csv`, adding `ice_b_cons`, `ice_b_repl`,
`ice_b_peak` and the ask trio. **Tonight's log settles it properly**, including the refill gate
this approximation could not reach.

---

## 42. ⭐ THE ICEBERG IS A SWEEP — and only one side of it leads (v1.34)

Your Scenario B was right, and the continuous sweep you asked for is what proved it.

### Answer to "binary gate or continuous ratio" — continuous, and it paid off immediately

Sweeping `repl/cons` across bands rather than testing one threshold:

| `repl/cons` | n |
|---|---|
| 0.00 – 0.25 | 1201 |
| 0.25 – 0.50 | 201 |
| 0.50 – 0.75 | **9** |
| 0.75 – 1.00 | **0** |
| above 1.00 | **0** |

**The refill gate can never fire on this feed.** Levels are consumed far faster than they
refill — `repl` never reaches even three-quarters of `cons`, let alone exceeds it.
**Scenario A was unreachable, and a single binary threshold would have reported "no firings"
without ever showing why.**

### Inverted, it is strong and monotonic

Bid consumed → SHORT, base rate down 47%:

| ratio | n | 3 s | 10 s |
|---|---|---|---|
| 2× | 2622 | 66% | 60% |
| 3× | 1411 | 70% | 62% |
| 5× | 452 | 77% | 64% |
| **8×** | 91 | **82%** | 67% |

66 and 71 **independent episodes** per side; permutation **p < 0.0001** on both.

### ⚠ THE MIRROR TEST SPLITS THEM — and this is what decided the ship

| side | h | forward | backward | |
|---|---|---|---|---|
| BID swept → SHORT | 3 s | 76.6% | **78.0%** | **MIRROR** |
| BID swept → SHORT | 10 s | 64.5% | **70.7%** | **MIRROR** |
| **ASK swept → LONG** | 3 s | **87.6%** | 64.9% | **LEADS by 23** |
| **ASK swept → LONG** | 10 s | **79.9%** | 64.0% | **LEADS by 16** |

**Only the ask side leads price.** The bid side reports a drop that has already begun.
Shipping both because the logic is symmetric would have shipped a mirror as a signal.

```
InpShowSweepUp = true     "ASK SWEPT - LONG"    88% at 3s, leads
InpShowSweepDn = false    "BID SWEPT - SHORT"   77% at 3s, mirrors
```

The `repl` requirement is **dropped from the trigger** — it belonged to the iceberg hypothesis,
which is dead. The counters stay and are still logged.

### Why this works when raw delta does not

Delta is a raw percentage of flow and measured **25%** at high speed (§29). This is the **same
flow normalised by the level's own visible depth**, inside a 20-second window. **The
normalisation is the signal.** That is the most useful thing learned tonight.

### Answer to "sessions or global" — global for now

The log is **8,520 seconds ≈ 2.4 hours of one evening**. Splitting that by London/NY would
leave a few hundred seconds per bucket and a handful of episodes. Session effects are real and
worth testing, but they need **days** of logging, not one night. Global hit rate first; split
when each bucket can carry its own permutation test.

### ⚠ Two corrections to the record

* **SPRING is 86%, not 91%.** It settled from 91% (n=32) to **86% on n=48** as data
  accumulated (§39). The 91% was an early reading.
* All of this is still on a feed whose spread is **14× the move** (§31). `ASK SWEPT - LONG` at
  88% is the second-best-evidenced thing here and **still cannot be traded on ETHUSDTp.**

---

## 43. WHICH ARENA — measured, and BTCUSDTp is WORSE (not better)

The question: point v1.34 at a thicker, tighter ticker on the same feed, or port to a
raw-spread feed?

**`edge = p90 10-second burst / spread`, across every symbol logged:**

| symbol | n | spread | p90 burst | spread (bp) | **edge** |
|---|---|---|---|---|---|
| **BTCUSDTp** | 1392 | 25.0000 | 1.3000 | **2.95** | **0.05×** |
| BTCUSDTp (2nd log) | 1444 | 25.0000 | 8.0000 | 2.96 | 0.32× |
| ETHBTCp | 1218 | 0.000013 | — | 4.12 | 0.31× |
| ETHUSDTp | 8520 | 1.3100 | 0.3800 | 4.91 | 0.29× |
| ETHUSDTp (schema 3) | 1483 | 1.3100 | 0.5700 | 4.88 | **0.44×** |

**BTCUSDTp has the tightest spread in basis points (2.95) and the WORST edge (0.05–0.32×).**

### The correction that matters

**Basis points are the wrong metric for this strategy.** BTC is tighter *relative to its price*
and far wider *relative to its 10-second bursts* — a 25-point spread against a 1.3-point p90
burst. The §34 ranking by basis points was the right way to compare quoting costs and the
**wrong** way to pick an arena. `edge` is the only metric that decides it, which is exactly why
v1.23 put it on the panel.

### What it would take

```
ETHUSDTp   spread 1.3100 -> 0.1900    6.9x tighter
BTCUSDTp   spread 25.000 -> 0.6500   38.5x tighter
```

**No symbol on this broker clears even 1.0×, let alone the 2.0× a real edge needs.** There is no
ticker-picking solution inside PXBT; the firewall is the fee structure, not the instrument.

### The answer

**Port it.** PXBT would have to get ~7× tighter on its best candidate. A raw-spread/ECN feed on
gold or an FX major runs 0.1–0.5 bp plus commission against PXBT's 4.9 bp — the right order of
magnitude to close a 6.9× gap, which is precisely why this is worth doing rather than hopeless.

**And measure before believing it.** For gold, a ~0.20–0.30 spread against NY-open 10-second
bursts of 0.40–1.00 gives a projected edge of **1.3–5×** — which straddles the 2.0 threshold, so
it is a real question and not a formality. The EA prints `edge` on stats line 2; **that number,
read in the first minute of a session, decides whether to go further on any new feed.**

**Nothing else should be tuned until a feed is found where `edge >= 2`.** The engine is finished;
the arena is not.

---

## 44. v1.36 — SWEEP GETS ITS OWN ROW, AND SAYS WHAT TO DO

Zee: *"can we say instead -> ASK SWEPT - BUY NOW! … and if its 80%+ in its accuracy then maybe
we can have a separate label for it instead of letting it being overwritten by outranked band
labels"*

**Right on both counts.** At **87% / 3 s and 80% / 10 s on 71 episodes**, SWEEP is level with
SPRING (86%) and better evidenced than PREDICT (n=10) — and the single-slot band was hiding it
whenever either of those fired.

```
   [ MASTER BAND ]     SPRING UP / BUY NOW / BREAK UP / WAIT ...
   [ SWEEP STRIP ]     ASK SWEPT - BUY NOW!  3        <- never overwritten
```

### The side benefit is worth more than the visibility

With two independent rows, **agreement and disagreement between the two best-evidenced signals
becomes visible.** Band `SPRING UP` with strip `BUY NOW!` is confirmation. `SPRING DOWN`
against `BUY NOW!` is a conflict — and a conflict is information the single slot was silently
discarding by precedence.

### Correction in his favour, found while answering

**The EA requires `z >= 1.0` before SWEEP can be reached** (the NO TRADE gate sits above it in
`Decide()`), and the §42 backtest did **not** include that gate. Re-run with it:

| | fires | episodes | 3 s | 10 s |
|---|---|---|---|---|
| sweep only (what was quoted) | 1612 | 91 | 81% | 74% |
| **sweep + z ≥ 1.0 (the EA)** | **171** | **71** | **87%** | **80%** |
| sweep + z ≥ 2.0 | 47 | 40 | 94% | 88% |

Base rate 54% / 53%. **The shipped behaviour is better than the number quoted, not worse** — the
speed gate removes the low-conviction sweeps.

### Also in v1.35/v1.36

* **SWEEP is latched** for `InpSignalHoldSec` with a countdown, like PREDICT. It was firing for
  ~2.4 seconds per episode, and "a brief milisecond" has already been raised once as unusable.
* Font measured, not eyeballed: `"ASK SWEPT - BUY NOW!  3"` is 23 chars; at FS(11) that is
  ~405 px inside a 398 px bar and would spill both sides. **FS(10) gives 368 of 398.** Same
  arithmetic as bug 6 in §36.
* Canvas `SC(184)` → `SC(214)`; lowest element ~801 px of 854.

---

## 45. ⚠ `GET READY` REMOVED — and §33 was measured against the wrong thing (v1.37)

Zee: *"i think the GET READY can be removed.. because they're based not on any concrete values
but something we were experimenting with"*

**His conclusion is right. His reason is not, and the real reason is worse.**

It was *not* arbitrary — §33 picked `z ≥ 0.75 & rising` from a measured grid of five rules, and
it did give ~4 seconds of warning before a PREDICT. **The fault is that §33 never ran a
same-frequency control.**

```
GET READY arms on 1,114 of 8,520 seconds  =  13% of the session

  caught within 10s        GET READY     a RANDOM light of the SAME SIZE
    SWEEP  (171 fires)        88%                  75%            +13 points
    SPRING  (91 fires)        78%                  76%             +2 points
```

**A light that is on 13% of the time falls inside the 10-second lookback of almost any event by
chance.** Against SPRING it beats random by **two points** — it was measuring its own firing
frequency, not the market.

### The lesson, which is bigger than the feature

§33 reported "catches 15 of 20 firings, 4 s median lead, 90% false alarms" and **shipped on
it**. Every one of those numbers was true. None of them was meaningful without the control,
because a hit rate for an *early warning* has to be compared against a random warning of the
same frequency — not against zero.

It was also calibrated against **PREDICT**, which has since become the weakest-evidenced signal
here (n=10), while SPRING and SWEEP carry the actual evidence.

**Removed outright, not defaulted off.** A dead input with a measured-worthless meaning is
something a future reader will try to re-enable.

### Where the panel stands after the removal

| row | shows | evidence |
|---|---|---|
| **two coils** | spring load per side | 86%, p=0.0001, 36 episodes, passes mirror test |
| **master band** | SPRING / BUY NOW / BREAK / LEAN / BLOCKED / WAIT | mixed — SPRING strongest |
| **sweep strip** | `ASK SWEPT - BUY NOW!` | 87% @3 s, 80% @10 s, 71 episodes, passes mirror test |
| verdict line | the full nine-verdict name | — |
| two stats lines | base, sd, win, run, acc, edge, levels, source | — |

**Everything on the panel that claims a direction now has a forward-tested number behind it.**

---

## 46. v1.38 — THE SWEEP DIAL

Zee: *"could we make a needle based dial / meter out of this ASK SWEEP engine? … that can tell
us if we're leaning on Sell (on the left) and BUY (needle on the right)"*

**His design was taken, not the report's.** The report maps `cons/peak` (0 → 8×) left to right,
which is a **magnitude** meter: it cannot tell a bid sweep from an ask sweep, so it needs two
dials. His is directional, and both sides are already tracked, so one dial carries it:

```
strain     = min(cons / peak, InpSweepClamp) / InpSweepClamp      per side, 0..1
sweep bias = (askStrain - bidStrain) / (askStrain + bidStrain)    -1 .. +1

  ask eaten (buyers lifting)  -> needle RIGHT -> BUY
  bid eaten (sellers hitting) -> needle LEFT  -> SELL
```

### ⚠ The honesty problem, solved in the drawing

§42 measured that **only the ask side leads** (fwd 87.6 vs bwd 64.9). The **bid side mirrors**
(fwd 76.6 vs bwd 78.0). A plain symmetric dial would give a validated signal and a lagging one
identical visual weight.

So the **right half is full colour** and labelled `BUY / 87%`; the **left half is muted** and
labelled `SELL / mirror`. The needle still swings there — the information is real — but the
dial states what each half is worth.

### The report's "snap" point was right, and is implemented

A 10-lot wall taking a 50-lot order moves the ratio 0 → 5 **in one event**, and the level reset
drops it straight back, so the eye never catches it. A **peak-hold** marker (goldenrod) lingers
at the extreme and decays at 0.97 per frame.

### One correction to the report

It advises decoupling the draw into `OnTimer` because `OnBookEvent` fires too fast. **That is
already the architecture** — computation in `OnBookEvent`, drawing in `OnTimer` (§2). And 60 fps
is not needed: the peak-hold is what makes a snap visible, not the frame rate, so a 16 ms timer
would cost CPU for nothing. The existing 50 ms / 20 fps stands.

### ⚠ THE PANEL IS NOW TOO TALL AT THE DEFAULT RADIUS

| `InpRadius` | width × height | |
|---|---|---|
| **235 (current default)** | 778 × **993** | **too tall for a laptop chart** |
| 200 | 660 × 844 | still too tall |
| 180 | 594 × 759 | tight |
| **160** | 528 × **675** | **comfortable** |
| 140 | 462 × 590 | comfortable |

Everything scales from `InpRadius`, so **dropping it to ~160–180 is the fix**, not turning
features off. Alternatives: `InpSweepDial = false` → 778 × 854; also `InpShowSpring = false` →
542 × 854.

---

## 47. THE TRAPPED DIAL — real as a filter, NOT as the 60-second bridge (v1.39)

Tested on 8,520 seconds before a line was drawn.

### Standalone it is dead — as delta's record predicts

| band | n | next 10 s | next 60 s |
|---|---|---|---|
| score > +1.0 | 929 | 56% | 58% |
| middle | 4389 | 55% | 58% |
| score < −1.0 | 985 | 52% | 66% |
| **base rate** | | | **57%** |

### As a FILTER on sweep it is real, at 10 seconds

| | n | episodes | 10 s |
|---|---|---|---|
| sweep alone | 170 | 71 | 80% |
| **sweep + trap > 0** | 84 | **38** | **89%** |
| sweep + trap < 0 (wrong side) | 86 | — | **70%** |

**A 19-point spread from the filter alone.** Permutation **0.00%**, and it **passes the mirror
test**: forward 89% vs backward 78%.

### ⛔ But the 60-second claim fails, and the formula says why

```
sweep + trap > 0    at 60s:  62%, permutation 6.8%   NOT significant
mirror test at 60s: forward 62%  vs  BACKWARD 92%    it reports the minute just gone
sweep + trap > 1.0  at 60s:  88%  - but on EIGHT episodes (26 firings in 8 bursts)
```

`Trapped_Score = Price_Trend_60s − CVD_60s` **contains a 60-second price term**, so testing it
against the *next* 60 seconds is contaminated by construction. **The backward 92% is that
contamination showing itself.** The `trap > +1.0` cell that looks like 88% at 60 s rests on
**eight episodes** and is almost certainly the same artefact at a smaller sample.

**The gauge does not bridge a 2-second spark to a 60-second hold. It sharpens the 10-second
call.** That is what shipped, and no 60-second claim appears anywhere in the EA.

### How it ships

* **A third dial beside the sweep dial** — placed to its right as asked, so the panel gains
  **no height**: `TRAPPED BUYERS` left (bearish), `TRAPPED SELLERS` right (bullish).
* **`+FUEL` on the sweep strip** when `trap > 0` — `ASK SWEPT - BUY NOW!  3  +FUEL`. That tag
  marks the measured 89% case and claims nothing else.
* `InpTrapDial` (default true), `InpTrapSec` (60).

### What this now means on the panel

```
ASK SWEPT - BUY NOW!  3  +FUEL     sweep agrees with the trap gauge   89% at 10s
ASK SWEPT - BUY NOW!  3            sweep against it                   70% at 10s
```

**The tag is the difference between an 89% read and a 70% one** — which is the single most
useful thing the third dial does.

---

## 48. ⏱ THE EXIT CURVE — the edge has a half-life (v1.40)

Zee: *"i don't need 60 second hold… what i meant by 60 seconds metaphorically was that i want
to trade in terms of scalping mini movements in price."*

Understood — and the right question is not 10 s versus 60 s, it is **where the move peaks**.
Measured on the 79 `ASK SWEPT +FUEL` firings:

| hold | mean move | hit rate | net after spread |
|---|---|---|---|
| 1 s | 0.043 | 100% | −1.267 |
| 3 s | 0.098 | 90% | −1.212 |
| 5 s | 0.117 | 88% | −1.193 |
| **10 s** | **0.178** | **88%** | **−1.132** |
| 20 s | 0.157 | 73% | −1.153 |
| 30 s | 0.086 | 60% | −1.224 |
| 60 s | **0.002** | 62% | −1.308 |
| 120 s | **−0.024** | 48% | −1.334 |
| 300 s | 0.200 | 57% | −1.110 |

**The edge peaks at ~10 seconds, is gone by 60, and is negative by 120.** Holding longer does
not accumulate — it gives the move back.

**The 180 s / 300 s rows are not a second peak.** Their hit rates (46% / 57%) sit at or below
the 57% base rate: that is the session's upward drift, not the signal. A positive mean with a
chance-level hit rate is drift every time.

### So hold time is not free, even though his account allows any hold

This *is* the mini-movement scalp he describes — and it has a **measured half-life of roughly
20–30 seconds.** That is a constraint on the trade, not a preference.

### What shipped: the exit clock

When a sweep fires, the strip runs a countdown for `InpEdgeHoldSec` (10 s):

```
ASK SWEPT - BUY NOW!  3  +FUEL        <- entry, latched 4s
IN TRADE - EDGE ENDS IN 7s            <- the measured window, counting down
```

This is `feedback_exit_is_the_edge` turned into a number instead of a feeling.

### And the same wall, now with an exact target

At the best hold, **mean move 0.178–0.203 against a 1.310 spread**.

```
to break even:  spread must fall below ~0.18   =  7.4x tighter  =  ~0.67 basis points
```

For reference: raw ECN on an FX major runs ~0.1–0.3 bp plus ~0.2–0.4 bp commission round trip,
so **~0.5 bp all-in — just inside the requirement**. Gold at a 0.12–0.20 raw spread on ~2650 is
**0.45–0.75 bp, straddling it.**

**This is marginal even on a raw-spread feed.** What decides it is whether gold's 10-second
bursts are larger *relative to its spread* than ETH's are — which is the one number to read at
the open, and it is already on the panel as `edge`.

---

## 49. PROOFREAD OF v1.38–v1.40 — three defects (v1.41)

### ⚠ Bug 1 — the trapped score ran at 20 Hz, not 1 Hz

Its own comment said *"once a second is enough"*, but the block sat **after the closing brace of
the per-second gate**, so it ran on every 50 ms timer tick. Two consequences, one of them
distorting the number the `+FUEL` tag is thresholded on:

* **The normalisers were 20× too fast.** `g_cvd_n` and `g_pch_n` ease at 0.02 per update — a
  time constant of ~50 seconds **at 1 Hz**. At 20 Hz that becomes **~2.5 seconds**, so the
  normalisers chase the current value and **squash the score toward zero** — exactly the
  quantity `trap > 0` tests.
* `ConsumedWithin` scanned ~540 ring entries for a 60-second window **20× a second** —
  ~10,800 iterations/sec for one number that changes once a second.

Moved inside the per-second gate; only the visual ease stays on the timer.

### Bug 2 — a dead branch

`else if(g_swp_latch == 0 && g_exit_ms == 0 && edgeLeft == 0) { }` did nothing at all, left
behind while restructuring the strip. Removed.

### Bug 3 — latent, not on this feed

`ConsumedWithin` over `InpTrapSec` can outrun `CONSBUF` (4096). At 9 book events/sec a
60-second window holds ~540 — fine. **Gold at a NY open can push 70+/sec = ~4,200**, which
would silently truncate the window and **understate CVD with no warning.** Now clamped to what
the ring can hold, and it prints the clamp once.

### Checked and clean

| check | result |
|---|---|
| CSV header vs data | **45 / 45 — match** |
| dial geometry, R = 120…235 | no clipping, no overlap, springs on or off |
| orphans (`InpShowIceberg`, `InpReadySigma`, `g_coil`, `V_ICE_UP`, `GET READY`, `g_ice_bid_px`) | **0 references each** |
| version banner vs `#property` | **1.41 / 1.41** |
| compile | 0 errors, 0 warnings, both terminals |

### Considered and left alone

If `InpSignalHoldSec` were set **above** `InpEdgeHoldSec`, the exit clock would expire while the
sweep text is still latched and never display. That is semantically correct — the edge really
has expired — and the defaults (4 vs 10) cannot produce it. Noted rather than guarded.

---

## 50. FULL-FILE PROOFREAD — three more defects (v1.42–v1.44)

### ⚠ Bug 1 — the alert fired on the weakest verdicts and was silent on the strongest

```mql5
bool actionable = (g_verdict >= V_RIDE_UP && g_verdict <= V_FADE_DN);
```

Codes **3..6** — `RIDE UP/DOWN` and `FADE UP/DOWN`. Written in v1.02 when those were the *only*
verdicts, and **never revisited across sixteen versions of new ones.** So the audible alert
covered `FADE` (the reading §11 showed `COIL` inverts) and `RIDE` (never tested), and was
**silent on every measured signal**:

| | | |
|---|---|---|
| `SWEEP` 19/20 | 87% @3 s, 71 episodes, passes mirror | **no alert** |
| `PREDICT` 15/16 | 10 firings, 0 wrong | **no alert** |
| `SPRING` | 86%, p=0.0001 | **not a verdict at all — could never alert** |

Replaced with an **explicit list**, not a range — a range silently re-reads itself every time a
`#define` is added, which is exactly how this rotted. SPRING got its own edge-triggered alert.

### ⚠ Bug 2 — `g_net_pts` was inert in BOOK mode, so half of BREAK and all of RIDE were dead

`g_net_pts` came from `Window()`, which walks the **tick** ring. At 0.11 ticks/sec that window
usually holds **zero** ticks, so `g_net_pts` was 0.0 almost always:

```
RIDE_UP needs net_pts >  0.0   ->  essentially NEVER fires
BRK_UP  needs net_pts >= 0.0   ->  TRIVIALLY TRUE at 0
BRK_DN  needs net_pts <= 0.0   ->  ALSO trivially true
```

**`BREAK`, documented in §29 as "OBI plus where price has actually travelled", was running on
OBI alone** — the price half could not even disagree. Now taken from the per-second **mid ring**
in BOOK mode, which needs no ticks. Tick mode untouched.

**Not changed, deliberately:** `g_range_pts` has the same tick origin, which is why
`COIL`/`WICK`/`FADE` cannot fire on these symbols (§25). Those three have **no** forward
evidence, so silently making them fireable would put untested signals on the panel.

### Bug 3 — a latent lockup in the warmup

`g_bn` caps at the baseline ring size; `Ready()` tested `g_bn >= InpWarmupSec`. **Set
`InpWarmupSec` above `InpBaselineSec` and `Ready()` is never true** — the gauge draws
"warming up 300 / 400 s" forever, counter visibly stuck, no hint why. Clamped, with a one-line
Journal warning rather than silently rewriting what was typed.

### Checked and clean this pass

| check | result |
|---|---|
| `nnb`/`nna` vs `BOOKMAX` | **bounded** — `if(nnb < BOOKMAX)` on both sides |
| `OnDeinit` | timer killed, book released, file closed, canvas destroyed, object deleted |
| every division | guarded or operating on clamped-positive values |
| unused inputs | none |
| range-based verdict tests | **only the one, now removed** |
| CSV header vs data | 45 / 45 |
| compile | 0 errors, 0 warnings, both terminals |

**Bugs 1 and 2 share a cause worth naming: both were correct when written and rotted as the
file grew around them.** A range over verdict codes and a price term sourced from a stream that
later stopped flowing. Neither would ever have thrown an error.

---

## 51. ⭐ EXNESS — GOLD, OPEN, WITH A REAL BOOK (v1.45)

Zee switched to **Exness MT5**, `XAUUSD`, market open, DOM window serving a full ladder. **This
is the feed every "test it on gold" note in this file has been waiting for.**

```
deploy target added:  exness
  data   C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/53785E099C927DB68A545C249CDBCE06
  editor C:/Program Files/MetaTrader 5 EXNESS/MetaEditor64.exe     (capitals, as with PXBT)

py monitor/deploy_ea.py --terminal exness TickSpeedGauge
```

v1.45 is on **all three** terminals.

### ⚠ The thing in that screenshot that would have broken `edge`

His DOM shows **best bid 4142.787 against best ask 4142.788** — a spread of **0.001 on a 4142
instrument = 0.0024 basis points.**

**That is not a tight spread. It is a raw-spread account, where the real cost is commission** —
and `edge` measured spread only.

Left alone, `edge` on this account would have read **in the hundreds**, and the panel would have
declared every micro-wiggle tradeable. For a gauge whose entire purpose since §31 has been to
say when a move *cannot pay its costs*, that is the most dangerous failure available.

```
edge = burst / (spread + InpCommissionPx)
```

`InpCommissionPx` is the **round-turn commission in PRICE units**, taken from the account's
contract specs — it varies by account type and symbol, so the EA does not guess it. For gold at
`$X per lot per side`: **`(2 * X) / 100`**, since one lot is 100 oz.

**And the EA now refuses to flatter a zero-spread account.** If the spread is under 1 basis
point and no commission has been entered, it prints a Journal line saying so instead of showing
a huge number.

### What to do at this session, in order

1. **Set `InpCommissionPx`** from the Exness contract specs. Everything below is meaningless
   without it.
2. **Set `InpRadius` to ~160–180** — the panel is 778 × 993 at the current 235.
3. **Read `edge` on stats line 2 before anything else.** Under 2.0, nothing here can pay.
4. Let it log a full session, then:
   ```
   py monitor/strategy_lab/tickspeed_calibrate.py tickspeed3_XAUUSD.csv
   ```
   and re-run the SPRING and SWEEP grids.

**Everything measured so far — SPRING 86%, SWEEP 87%, the 10-second edge half-life — comes from
one evening on PXBT crypto. Gold on Exness is the out-of-sample test, and nothing carries over
until it is run.**

---

## 52. EVERY LABEL NOW NAMES THE TRADE (v1.46–v1.48)

Zee, twice: *"what does it mean seller trapped? trapped in what.. is this a buy signal?"* and
*"the text on top of left spring is called SELL WALL.. does it mean i need to sell? or buy?"*

Both labels were **true and useless**: a market-microstructure noun the reader has to translate
mid-trade. Every gauge now carries the **action**, and the cause lives here in the doc.

| gauge | was | now |
|---|---|---|
| left spring | `SELL WALL` … `LONG!` | **`BUY`** … **`BUY NOW!`** |
| right spring | `BUY WALL` … `SHORT!` | **`SELL`** … **`SELL NOW!`** |
| trap dial ends | `BUYERS trapped` / `SELLERS trapped` | **`SELL`** / **`BUY  89%`** |
| trap dial centre | `TRAP +2.00` | **`FAVOURS BUY`** / `FAVOURS SELL` / `NO BIAS` |

### The labels were also making agreement look like contradiction

In his screenshot the **left spring sits at 100%** while the **trap dial reads FAVOURS BUY**.
Under the old labels that was `SELL WALL` beside `FAVOURS BUY` — which reads as a conflict.
Under the new ones it is **`BUY 100%` beside `FAVOURS BUY`**, which is what both gauges were
actually saying all along.

### ⚠ "FAVOURS", not "BUY NOW" — the asymmetry is measured

| signal | filter | n | hit @10 s |
|---|---|---|---|
| **SWEEP UP (buys)** | **trap > 0** | 84 | **89%** |
| SWEEP UP (buys) | trap < 0 | 86 | 70% |
| SWEEP UP (buys) | none | 170 | 80% |
| SWEEP DOWN (sells) | trap > 0 | 95 | 63% |
| SWEEP DOWN (sells) | trap < 0 | 52 | 65% |
| SPRING DOWN (sells) | trap < 0 | 36 | 73% |
| SPRING DOWN (sells) | none | 94 | 65% |

**The right side is strongly validated for buys** (19-point spread). The left side is
suggestive for sells on one signal and **flat on another**. Standalone the dial is 56% against
a 57% base (§47) — it **grades** a signal, it never generates one. Hence `FAVOURS`.

### ⚠ Bug — the speed bar's three labels overlapped

Visible in his screenshot as `0 v/SPEED 0/100  -0.2 SID+14%`: left, centre and right labels
written into one strip and colliding at both ends.

```
at R=160:  centre "SPEED 0/100  -0.2 SD" = 20 chars = 220px, +/-110 from centre
           bar is 271px, centre sits 135px in  ->  text runs 25..245
           left label "0 v/s" occupies 0..55   ->  OVERLAP 25..55
```

**Three labels do not fit a 271 px strip, and shrinking the font only delays the overrun** —
same class as bug 6 in §36. Replaced with **one measured line**: `0v/s 0/100 -0.2SD +14%`.

| radius | bar | typical | worst case |
|---|---|---|---|
| 140 | 237 | 194 OK | 238 — **clips by 1px** |
| **160** | 271 | 218 OK | 267 OK |
| 180 | 305 | 242 OK | 297 OK |
| 235 | 398 | 315 OK | 386 OK |

**Use `InpRadius` ≥ 160.** At 140 the worst case (`160v/s 100/100 +3.2SD +100%` all at once)
overruns by a single pixel.

---

## 53. ⛔ EXNESS SERVES NO LEVEL 2 — the DOM window is a trading ladder (v1.50)

```
2026.10.05 03:49:53  [TPS] spread is 0.0800 (0.19 bp) - RAW-SPREAD account, real cost is COMMISSION
2026.10.05 03:49:53  [TPS] depth of market on XAUUSD: NOT AVAILABLE - direction is INFERRED
```

**`MarketBookAdd()` is correct and the DOM window is not a book.** Three tells in his own
screenshot:

1. **No volume column.** It shows `Price` and `Trade` only. A real Level 2 book has a volume at
   every level — that volume *is* the book.
2. **Irregular price steps**: 0.001 near the touch, then 0.01 further out. MT5 generating rows
   around the current spread, not levels a market posted.
3. **The coloured gap is the spread**: top bid row 4147.425, bottom ask row 4147.505 — exactly
   the **0.0800** the EA reported.

That is MT5's built-in **order-entry ladder**, drawn for one-click trading on any symbol,
with or without depth.

### ⚠ What this costs

**Every validated signal in this build requires `g_dom_ok`:**

| | needs the book |
|---|---|
| `SPRING` — 86%, p=0.0001 | **yes** |
| `SWEEP` — 87% @3 s | **yes** |
| `PREDICT` — 10-for-10 | **yes** |
| `BREAK`, the OBI dial, the trap dial | **yes** |
| speed / `z` | no |

**On Exness XAUUSD the panel is reduced to tick speed and an inferred delta that §3 measured as
a mirror of price.** Not one of the signals that took this whole session to find can fire.

### The question that now decides everything — and a probe for it

A book is not the only way to get direction. **A tape that tags the aggressor is better than a
book**, and the EA never reported whether this feed has one. v1.50 counts real ticks and prints,
once, after `InpProbeTicks` (400):

```
[TPS] FEED PROBE on XAUUSD after 400 ticks: aggressor flags x%, last price y%, volume z%.
```

* **flags present** → the delta becomes *real*, not inferred. Most of this build works again on
  a tick basis, and the calibration should be re-run from scratch on it.
* **no flags, no book** → **direction cannot be measured on this symbol.** Only speed is real.

### Where that leaves the two brokers

| | book | spread | verdict |
|---|---|---|---|
| **PXBT** crypto | **10 levels, real** | 2.9–16 bp | signals work, **costs 7× too high** |
| **Exness** XAUUSD | **none** | 0.19 bp + commission | **costs look right, signals cannot fire** |

**The two halves of a working setup are on two different brokers.** That is the actual state,
and it is worth saying plainly rather than tuning around.

**Next:** read the FEED PROBE line after ~400 ticks. If Exness tags the aggressor, this is
solved on the better-priced broker. If not, check whether any *other* Exness symbol returns a
book before concluding the broker serves none.

---

## 54. ⛔⛔ OUT-OF-SAMPLE ON GOLD: BOTH SIGNALS FAIL

**`tickspeed3_XAUUSDp.csv` — PXBT's own GOLD had been logging all along, 3,672 seconds, with a
book.** This is the out-of-sample test the whole session has been building toward.

### First, the arena is finally right

| | ETHUSDTp | **XAUUSDp (gold)** |
|---|---|---|
| book levels | 10 | **20** |
| spread | 1.3100 (4.88 bp) | **0.1700 (0.41 bp)** |
| p90 10-second move | 0.38 | **0.56** |
| **edge** | **0.29×** | **3.29× — clears the 2.0 threshold** |
| seconds in which price moves | **5%** | **85%** |

**PXBT gold has the book AND a cost structure the moves can pay.** Both halves, on one symbol,
which §53 said were split across two brokers. That part is genuinely good news.

### And then both signals evaporate

**SPRING** — 16 releases in 11 episodes:

| horizon | forward | backward | |
|---|---|---|---|
| 3 s | **38%** | 31% | below the **53%** base |
| 10 s | 56% | 56% | **mirror** |
| 30 s | 50% | 62% | **mirror** |

**SWEEP** — and it never fired once in 3,672 seconds of live gold:

| ratio | n | up next 10 s |
|---|---|---|
| 1× | 93 | 55% |
| 2× | 61 | 55% |
| 3× | 58 | **57%** |
| base | | **53%** |

86% and 87% on ETHUSDTp. **55–57% on gold.** Gone.

### ⚠ WHY — and it invalidates the discovery, not just the numbers

```
                              ETHUSDTp        XAUUSDp (gold)
ask price unchanged sec-to-sec    ~95%              35%
mid price moves                     5%              85%
one ask level survives          minutes      median 0 sec
```

**Both signals were measuring properties of a nearly-frozen quote feed, not of market
microstructure.**

* **SWEEP** needs 3× a level's visible size consumed **at one price**. On ETHUSDTp a level sat
  still for minutes, so consumption piled up. On gold the median level survives **zero
  seconds** — it is gone before anything can accumulate. That is why it never fired.
* **SPRING** needs OBI to cross from −0.25 to +0.25 **in one second**. On a book that barely
  moved, that crossing was rare and meant something. On a live book it is ordinary churn.

**The p = 0.0001 was real for that feed and meant nothing about gold.** Permutation tests and
mirror tests both passed, on 36–71 independent episodes, and the finding still did not survive
a change of instrument. That is the lesson, and it is the project's own doctrine —
`feedback_backtests_hallucinate_take_all_chances`, `feedback_validate_profitability_not_capture`
— arriving in the most expensive possible form.

### What is actually in hand

| | status |
|---|---|
| **the arena** | **solved — PXBT XAUUSDp, 20 levels, edge 3.29×** |
| SPRING, SWEEP, the trap filter, PREDICT, BREAK | **calibrated on a feed that does not resemble this one** |
| `RIDE` | fires now that v1.43 fixed `net_pts` — 62 firings, untested |
| speed / z | the one thing never feed-dependent |

**Nothing should be traded on gold using thresholds fitted to ETHUSDTp.** The discovery work has
to be redone on gold data: same method — forward vs backward, permutation against same-size
random draws, episode counting — on the instrument that will actually be traded.

**3,672 seconds is one hour.** Leave the gauge on XAUUSDp through a London and a New York
session, then re-run the grids from scratch.

---

## 55. ⭐ THE HORIZON WAS WRONG ALL ALONG (PXBT gold, 4,094 sec)

The Exness probe closed that question — **0.0% flags, 0.0% last price, 0.0% volume on 400 real
ticks.** Bid and ask only. So the work moved to PXBT gold, which has 20 book levels, and the
scan there produced the most important table in this file.

### THE MINIMUM VIABLE HOLD

Before any win rate matters, **the mean move must beat the spread.** PXBT gold, spread 0.1700:

| hold | mean \|move\| | vs spread | win rate a 1:1 scalp would need |
|---|---|---|---|
| 1 s | 0.0546 | 0.32× | **IMPOSSIBLE** |
| 3 s | 0.1156 | 0.68× | **IMPOSSIBLE** |
| 5 s | 0.1574 | 0.93× | **IMPOSSIBLE** |
| 10 s | 0.2315 | 1.36× | 87% |
| 20 s | 0.3314 | 1.95× | 76% |
| 30 s | 0.3883 | 2.28× | 72% |
| **60 s** | **0.5184** | **3.05×** | **66%** |
| 120 s | 0.7995 | 4.70× | 61% |
| 300 s | 1.4772 | 8.69× | 56% |

**Below 10 seconds no win rate can pay the spread — not 90%, not 100%.** The arithmetic closes
before skill enters.

**This session was spent building and validating 3-to-10-second signals.** SPRING at 3 s. SWEEP
at 3 s. The exit clock set to 10 s "because the edge peaks there". **Every one of those horizons
is inside the impossible zone on the instrument that can actually be traded.** The edge peaking
at 10 seconds on ETHUSDTp was a property of a frozen quote feed, and it sent the whole build
down a horizon that cannot pay.

**The viable zone starts around 30–60 seconds.** That is not a preference about hold time
(§48) — it is set by the spread, and it is not negotiable.

### A new candidate, measured on the right instrument

OBI on gold is **inverted** from ETH — thick bid precedes a fall — and it is monotonic:

| band | n | down next 3 s | episodes |
|---|---|---|---|
| OBI ≥ +0.6 | 322 | **56.7%** | 61 |
| middle | 2848 | 48.9% | 15 |
| OBI ≤ −0.6 | 867 | 44.3% (= 55.7% up) | 69 |

Permutation: **0.0% of 5,000 random draws.** Real — but only **+8 points** over base, against
+36 on ETH.

**Traded at the horizon the table permits, with a same-size random control:**

```
LONG on OBI <= -0.6, hold 60s :  +0.0562 per trade
LONG at a RANDOM second, 60s  :  -0.1046 per trade    <- the control
                                 ---------
the signal contributes           +0.1608 per trade
```

**The control loses (it pays the spread) and the signal does not.** That is the first result in
this file measured on the instrument that would actually be traded, at a horizon that can pay.

### ⚠ How thin it is

**870 observations, but they overlap**: OBI sits below −0.6 for 21% of the session, so
consecutive seconds are the same episode. At a 60-second hold the effective sample is roughly
**15 independent observations**, from **one hour**. That is a hypothesis with a pulse, nothing more.

**Do not trade it.** §54 is four hours old: a signal with p = 0.0001 on 36 episodes evaporated
when the instrument changed. This one has p = 0.0 on ~15.

### What to do

1. **Leave the gauge on PXBT `XAUUSDp`** through a London and a New York session.
2. Re-run this scan on that data — directional lead-lag, the minimum-hold table, and the random
   control.
3. **Stop designing for 3-second signals.** The spread has already ruled that horizon out.

---

## 56. CALIBRATION ON PXBT XAUUSDp — 35,563 sec, train/test (v1.51)

Zee: *"can you caliberate for xauusd on primexbt our EA"*

Done properly: **first half fits, second half validates, nothing from ETHUSDTp carried over.**

### The result

| | per trade |
|---|---|
| best on TRAIN — OBI ±0.75, hold 300 s | **+0.0928** |
| **that exact config on the unseen TEST half** | **−0.3446** (45% winners) |
| random control on TEST | −0.4585 |
| **random beat the signal in** | **0 of 200 draws** |

**The signal carries information and still loses.**

```
signal's edge over random   ~ +0.03 to +0.11 per trade
spread to cross            =   0.17
                              --------
the gap is 2x to 5x
```

**No configuration in the explored space is profitable.** That is the calibration's answer, and
it is an answer, not a failure to find one.

### Two findings that change how the EA should be tuned

**1. The OBI threshold is not a knob on this instrument.** OBI on gold is **bimodal** — 52% of
seconds sit at ~0.0 and the rest cluster at ±0.7–0.8, with almost nothing between:

```
  -0.8  2940 ####      +0.0 18391 ###############################      +0.8  9109 ###############
  -0.7  2373 ####                                                      +0.7  2168 ###
```

So 0.50, 0.60, 0.70 and 0.75 select the **same observations** and score identically to four
decimals. Tuning `InpObiTrigger` on gold does nothing.

**2. The one profitable cell is noise.** `z ≥ 3, hold 300 s` scored **+0.1934 on test** — and
**−0.1338 on train.** A config that loses on the fit sample and wins on the holdout is a coin
landing differently twice, not a finding.

### What shipped instead of thresholds

**The minimum viable hold, measured live.** Before any win rate matters the mean move must beat
the round-turn cost; below that horizon **no win rate can pay — not 90%, not 100%**. The EA now
computes it from its own mid ring, per instrument, and prints it on stats line 2:

```
edge 3.3x  min 20s  L20 BOOK
```

So any symbol it is attached to **declares its own floor** rather than inheriting one fitted to
a different feed — which is precisely the mistake §54 recorded.

`InpEdgeHoldSec` **10 → 60**. The 10 came from ETHUSDTp's exit curve (§48) and sits inside
gold's impossible zone.

### Where this leaves the project

| | |
|---|---|
| **instrument** | **settled — PXBT XAUUSDp: 20 levels, edge 3.3×, real market** |
| **horizon** | **settled — nothing under ~10 s can pay; 30–60 s is the viable zone** |
| direction signal | **not found.** OBI beats random consistently and by far too little |
| what is needed | a signal worth **more than 0.17 per round turn**, not 0.03 |

**The honest position: the measurement apparatus is now correct and the edge is not there yet.**
That is a better place to stand than a 91% number fitted to a frozen quote feed — but it is not
a trading system, and nothing in this build should be traded on gold today.

---

## 57. ALL THREE BROKERS, MEASURED — only one has a real book (v1.53)

| | **PXBT XAUUSDp** | Exness XAUUSD | Blueberry XAUUSD.pi |
|---|---|---|---|
| `MarketBookAdd` | succeeds | **fails** | succeeds |
| book levels | **20** | 0 | **2** |
| touch volumes | **500–1100** | — | **1 and 1, max ever 1** |
| distinct OBI values seen | many | — | **ONE: 0.0, in all 273 sec** |
| aggressor flags | none | none | none |
| spread | 0.1700 (0.41 bp) | 0.0800 (0.19 bp) | **0.0700 (0.17 bp)** |
| commission | none | $3.50/side | yes (raw) |
| **usable for this EA** | **YES** | no | **no** |

### Blueberry: "AVAILABLE" and useless

`MarketBookAdd()` succeeds, so `g_dom_ok` went true, the EA printed *"true book delta in use"*
and the panel showed `BOOK` mode. Then:

```
best_bid_vol : median 1, MAX 1        best_ask_vol : median 1, MAX 1
obi_touch    : 0.0 in ALL 273 seconds - one distinct value in the entire log
```

**"Volume 1" is a flag meaning "a quote exists at this price", not a size.** OBI is therefore
identically `(1−1)/(1+1) = 0`, which pins **SPRING** (needs \|OBI\| ≥ 0.25), **PREDICT** (> 0.60),
**BREAK**, **SWEEP** and the **trap dial** — all at once, silently, while every needle sat
confidently at centre.

**The v1.11 depth warning fired correctly** — *"a 1-2 level book is an LP quote, not an order
book"* — it simply **was not wired to anything.** `g_dom_ok` stayed true regardless.

**v1.53 wires it:** a book with fewer than `InpMinBookLevels` (4) levels, or whose touch volume
never exceeds `InpMinTouchVol` (2), is **demoted to tick mode** with a Journal line naming the
numbers. Better to lose the book loudly than to display constants as signals.

### Why the best spread is on the worst feed

Blueberry has the tightest raw spread of the three (0.17 bp) and the emptiest book.
Exness is next (0.19 bp) with no book at all. **PXBT has the widest spread (0.41 bp) and the
only real order book — 20 levels with genuine 500–1100 lot sizes.**

**That is the trade, and it is not close:** PXBT's extra ~0.09 of spread buys the only
instrument on this machine where direction can be measured at all. §56 already showed PXBT gold
clears the cost bar at edge 3.3×.

**The instrument question is now closed: PXBT `XAUUSDp`.** Keep the other two attached as free
tick-speed data; neither can carry a directional signal.
