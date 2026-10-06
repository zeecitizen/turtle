# VSISA — what we learned on 19–21 September 2026

Written for Zeeshan. Plain language, no code.

This is the session's findings in one place so they are not lost in the Pine comments.
It covers **what we inferred from the laws**, **what we built**, and **what the chart
actually measured** — including the things that turned out to be wrong.

**Everything here is DIRECTION ONLY.** The scoreboard asks one question: after a label
printed, did the next candle close the way the label pointed? There is no entry price, no
stop, no target, no spread, no slippage. Under CLAUDE.md nothing here is promoted — only
MT5's Strategy Tester or live fills can do that. Treat every number as "where to look".

---

## 1. The laws we turned into code, and how we read them

### The wick is a binary call, not a scale
LAWS_VSISA.md line 219 says flatly *"a wick below means AGGRESSIVE BUYING happened"*, and
line 243 repeats it. It never grades the wick. So the tiered bands (25% / 45%) that had
crept into the script were an invention on top of a document that makes a yes/no call.
They were removed. Past the threshold it is aggressive buying; a bigger wick only
intensifies the same verdict.

**Your words that settled it:** *"we don't need tiers.. infact any existance of lower wick
greater than 10% is enough to classify it"*.

### But the wick does two different jobs, and they need two numbers
This caused a visible contradiction — a BUY SETUP marked WEAK while its own label said
"aggressive buying". The same 11% wick was being judged by two different thresholds.

- **Admission** — a wick standing in for low volume, letting a LOUD reaction qualify.
- **Grading** — deciding whether a setup that already qualified is strong or weak.

They are not the same question, so they now have separate settings.

### Low volume is measured against the campaign's LAST candle
Your correction, and it was right: *"i think we compare the reaction candle's volume to the
LAST CANDLE of the campaign"*. The law only says "a low volume bullish candle" and leaves
the yardstick open — mine (the campaign average) was refusing setups your eye accepted.
The 18 Sep 12:50 reaction failed against the average (107%) and passed easily against the
last bar (71%).

### Capping can be anywhere in the campaign, not only on its last candle
Your question — *"the second last bar before the 12:10 AM bar was capping.. can u check?"* —
found a rule that was too narrow. The supply that caps a rise does not have to land on the
very candle before the turn. On 18 Sep the capping bar sat three bars back and nothing was
looking there. Now the whole run is searched.

The *sequence* the law calls END OF RISING MARKET (line 250) still requires the capped bar
to be the last one, so that stayed a separate test.

### Engulfing can admit a setup — but only three bodies, and only with capping
Line 125 lists engulfing as evidence of aggressive selling, but always **alongside** the
wick, never instead of it. There was also a real objection: VSISA is an absorption method,
and a loud bar that engulfs and closes strong is momentum, not absorption — admitting it
quietly turns this into a breakout tool.

Resolved by demanding **three whole campaign bodies** plus capping. That is no longer a bar
that merely closed past the previous candle.

Your refinement mattered: *"if the reaction candle engulfs ANY of the 2 candles within the
campaign"* — not the last N in a row. A reaction can swallow the big second-last bar while
missing a small one in front of it, and counting consecutively scored that as zero.

### A campaign that keeps wicking is a warning
Your observation on a sell that failed immediately: *"the 3 previous candles before this
reaction candle have a large lower wick.. suggesting that during this campaign there's some
buyer's pushing the price up"*.

This is line 279 widened from one candle to a run. One wick is a moment and nearly every
bar has one; **three bars in a row bought off their lows is the market saying the same
thing three times**. It also arrives earlier than any reading of the reaction candle — it
is visible while the campaign is still printing.

**The polarity took two attempts.** The wick that matters follows the **setup's** direction,
not the campaign's. A sell is endangered by BUYERS (wicks below); a buy is endangered by
SELLERS (wicks above). My first version read the wrong half of the candle.

### The same candles read the other way are a strength signal
A candle has two ends, and both readings can be true at once — a campaign fought from both
sides. After a red campaign: upper wicks mean sellers still arriving (caution); lower wicks
mean buyers already arriving (strength).

**These needed separate bar counts.** Measured across 1,776 campaigns: **48.6% of campaigns
on M5 gold are exactly two bars long.** So any rule needing three campaign candles is
silent on half the chart before it measures anything. The caution stays at 3 bars (it turns
a label orange, so it must stay rare); the strength star moved to 2.

---

## 2. What the measurements actually said

### The settings that changed, and why

| setting | was | now | why |
|---|---|---|---|
| heavy volume test | PEAK | **AVERAGE** | PEAK asks if ONE bar was loud, which a single spike satisfies. AVERAGE asks if the whole run was loud. Better in a falling market, never worse. |
| campaign volume | — | **1.15×** | Peak of a smooth curve, and the same peak in both an up leg and a down leg. |
| quiet reaction | 0.85 | **0.65** | 0.85 was in a trough and had never been measured. |
| rejection wick | 0.25 | **0.10** | Your number from the law, not mine. *(See the open item below — 0.15 may now be better.)* |
| engulf admission | off | **on, 3 of 3** | The orange bucket collapses to near-zero at admit 3. |

### The biggest single finding: an unmeasured number was the worst one
We spent a whole night tuning five settings **around** the quiet-reaction threshold, and
nobody thought to sweep it. It was a number I invented when the script was written.

When we finally measured it, **0.85 turned out to sit in a trough** — the 27 setups it
admitted over 0.75 were worth **−1.57 each**, the most destructive band found all session.
Both 0.65 and 0.75 beat it on every measure.

**The lesson worth keeping:** a threshold nobody has measured is not a neutral default. It
is a guess wearing the costume of a decision. Several more remain unmeasured — the strong
imbalance level, the strong-closing level, the campaign-wick level, the capping volume
level. All are still mine, not yours, and not yet tested.

### The buy/sell gap is NOT the trend
I said repeatedly that our sample was a rising market and that this might explain why buys
beat sells. **That was factually wrong** — your 19 sessions close 4655 → 4378, a fall of
277. The rise was early August, before your chart window.

Split properly across a rising leg and a falling leg, buys beat sells in **both**:

| | BUY | SELL |
|---|---|---|
| rising leg | +1.80 | −0.24 |
| falling leg | +0.95 | +0.14 |

If it were trend drift, sells would pay in the falling leg. They don't. **The asymmetry
belongs to the method on M5 gold, not to the market direction.**

### And what the win/loss split then revealed
Once the table separated winners from losers, the sell problem changed shape entirely:

| | when RIGHT | when WRONG | hit rate |
|---|---|---|---|
| BUY | +4.05 | −2.46 | 66% |
| SELL | **+4.25** | −2.83 | **51%** |

**Sells pay MORE than buys when they work.** The size is not the problem at all. The entire
weakness is the hit rate — we cannot tell in advance which half will work.

That reframes the open question from "sell setups are weak" to **"sell setups are just as
big, we just can't filter them yet"** — which is a solvable problem, and a valuable one,
because the winners are already there.

### Things that were tried and REJECTED by measurement
- **Waiting for a candle in the reaction's direction before entering.** Same population of
  setups, but moving the entry one candle later took the move per setup from **+0.67 to
  −0.02**. **The edge lives in the reaction bar's close and is gone one candle later.** That
  is also why the scoreboard scores on the very next bar.
- **Requiring a minimum campaign of 1, 3, 4 or 5 bars.** 1 added 143 setups worth 0.02 each;
  3/4/5 gave 0.88 / 0.38 / 0.75 — a sawtooth, which is the signature of noise rather than a
  real effect.
- **Measuring capping against the campaign's own candles** instead of the 20-bar average.
- **A wrong-side wick downgrade on the reaction bar.** Reverted the same day — one wick on
  one bar is too common, and it painted half the chart orange. A flag that fires constantly
  stops being read.

### One instrument fact worth remembering
Your anomaly example — *"previously 500 volume resulted in 700 body height, and now 50,000
volume makes the same 500"* — describes a real phenomenon, but **not on this instrument**.
Across 7,247 bars of M5 gold, **nothing** reaches 3× average volume with a compressed range.
Gold volume is spread across thousands of participants around the clock; 2× is already a
big bar. The 10× world is a stock or a futures contract where one institutional order can
dwarf a quiet bar. The anomaly detector was recalibrated to this instrument (1.5× volume,
half the usual movement per unit) rather than to the illustration.

---

## 3. How to read the scoreboard

Six columns, and the two on the right are the ones that decide anything.

- **labels** — how many of that kind printed.
- **next candle our way** — how often the next candle closed the way the label pointed.
  **This is not a win rate.** No stop, no spread. The measured gap between this kind of
  number and real MT5 fills is about **16 points**, so 51% here is roughly 35% in the
  account.
- **when RIGHT** — how far it ran when it worked. Roughly where a target lives.
- **when WRONG** — how far it went against you. Roughly what a stop must survive.
- **net per label** — everything blended, winners and losers together. This is the number
  that ranks one SETTING against another.

**Do not optimise the hit rate.** Across every sweep this session it moved inside a 5-point
band while total movement moved sixteen-fold. You can reach 70% by taking three setups a
month and earning nothing. What pays is **when-RIGHT ÷ when-WRONG**, and total movement.

---

## 4. Open items — the honest list

1. ~~`wickX` may want to be 0.15~~ — **RESOLVED 21 Sep, and it overturned an earlier
   decision.** A 216-config grid put `wickX 0.15` on top of every ranking. The sweep that
   had chosen 0.10 was run while the script was still on PEAK with the quiet gate at 0.85;
   both changed afterwards, so it was measuring a landscape that no longer existed.
   Verified on the chart, the three gates together (**1.20 / 0.70 / 0.15**) give:

   | | setups | hit rate | BUY | SELL | per label |
   |---|---|---|---|---|---|
   | old | 165 | 59% | 1.82 | 0.95 | 1.37 |
   | **new** | 131 | 60% | **1.96** | **1.34** | **1.64** |

   The sell side lifts 41% and pays **+4.91 when it works** — the best measured anywhere.
   Cost: 1.8 fewer setups a day and 5% less total movement.

   **A warning about how this one was found.** The earlier settings were each swept alone,
   one at a time. This was picked as the best of **216 combinations** on 19 sessions — and
   the best of 216 is partly the luckiest of 216. Three things make it more than that: both
   directions improved, the hit rate and the expectancy agreed (they usually don't), and
   the per-setup gain held on your real chart, not just in the replication. But it has had
   **one** out-of-sample test — your chart — and that is not many. Watch it for a week
   before trusting it further than the numbers above.
2. **The strong-imbalance level (0.55) is now nearly meaningless.** It was calibrated when
   the admission gate was 0.85, so "≤55%" picked out a distinct minority. With the gate now
   at 0.65, most quiet reactions clear it. It should be re-tuned or it will stop carrying
   information.
3. **The `$` score is unmeasured.** Nobody has checked whether `$$$$` behaves better than
   `$`. Splitting the sell row by `$` count is the natural next test, and it aims straight
   at the sell-filtering problem above.
4. **Several labels describe but were never measured**: NO SUPPLY / NO DEMAND, IMBALANCE
   SHIFTED, ⭐ STRONG SIGNAL, the campaign-wick caution. They gate nothing, so they cost
   nothing — but none has earned its place with evidence.
5. **None of this has been through MT5.** Every number here is direction-only on 19
   sessions of one instrument on one timeframe.

---

## 5. Candle geometry — the whole library, tested (24 Sep)

Three separate rounds now. Recording the result so nobody runs it a fourth time.

### What was tested

| idea | n | result |
|---|---|---|
| **reaction body under 30% of range** | 40 | **72.5% vs 67% baseline — SHIPPED** |
| reaction body over 60% | 24 | 54.2% — shipped as a WEAK flag |
| close in the top quartile | 51 | 66.7% — flat, **dead** |
| closing wick bigger than rejection wick | 20 | 70.0% vs 70.0% — **dead** (asked twice) |
| wick ≥ 2× body | 30 | 73.3% — real but the same finding as body ratio |
| narrow spread vs 20-bar average | 12 | 75% but too few to act on |
| upper wick ≥ 50%, across 4,922 bars | 758 | −2.2 vs base rate — **noise** |
| lower wick ≥ 50% | 780 | +2.1 — **noise** |
| doji-ish body under 20% | 979 | −1.1 — **noise** |
| heavy volume + wide bar | 322 | −1.3 — **noise** |
| confirming bar LOUDER than the reaction | 24 | 75.0% vs 81.6% for quieter — **book is wrong here** |
| price invalidation at the reaction's extreme | 22 | looked like 78% vs 32%, **was circular**; really 52% vs 50% |

### The pattern underneath all of it

**Single-candle geometry almost never predicts. Context almost always does.**

Everything that has survived measurement in this project is about the candle's
*situation*, not its shape:

- how long the campaign behind it ran (the sell fix, +25 points)
- how much volume the level cost **last time** (the retest route)
- where the bar sits in its 20-bar range (the only direction hint that earned a mark)
- whether the campaign was capped

Everything that failed was about the candle **in isolation** — wick lengths, close
position, doji shapes, body-to-wick ratios read on their own.

The one exception, body ratio, is arguably context too: it isn't "this candle is pretty",
it's "this candle is momentum rather than absorption", which is a statement about what
kind of event it is.

### Two traps worth remembering

**Circularity.** The invalidation test showed a 46-point split and it was entirely an
artefact — "the bar broke the low" and "the bar closed down" are nearly the same event
when the outcome is that bar's close. Any rule measured on the bar it fires on needs this
check.

**The one-candle horizon.** `waitDir` proved the edge is gone one bar after the reaction
closes. The invalidation line failed for the same reason. Any idea that needs a bar to
pass before it acts is fighting that, and should be assumed dead until it proves otherwise.

---

*Findings only. LAWS_VSISA.md is yours and was not edited.*
