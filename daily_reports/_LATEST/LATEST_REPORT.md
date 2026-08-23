# 23–24 August 2026 — the night every constant of mine fell, and his eye wrote the EA

**Supersedes:** the 17–21 August report, archived at
[`daily_reports/2026-08/REPORT_2026-08-17_to_21_laws_and_diamonds.md`](../2026-08/REPORT_2026-08-17_to_21_laws_and_diamonds.md).

**Headline: BasedOnLaws went v1.19 → v1.29 in one night, and every improvement came
from Zeeshan reading his own chart.** Four of my invented constants were measured and
retired; four separate defects in the MEASUREMENT rig were found and fixed while
chasing them. Final config on his chart, seven days, 0.10 lots: **30 trades ·
12W/18L · 40.0% · +$624.00**, against +$224.10 where the evening began. **Attached
live at 0.01 (magic 88184) at ~03:00 PKT on Aug 24.**

⚠️ **STILL UNANSWERED AND URGENT: the Diamond (88154) is trading at FULL SIZE.** It
took **−$2,476.50 on Friday Aug 21** — 57% of the account, two baskets doing all of
it — while every guarded machine was fine. Recommendation standing since Aug 21:
detach it or cut it to 0.01.

---

## 1. His trade-#5 objection, and where it led

Friday's five setups had been agreed. He looked again at the 10:02 PM one (−$33.50):

> *"the 10:02 breakout candle has a wick on top making it not a momentum candle,
> secondly this candle's wick breaks the UHV high, its body does break the UHV high
> but with a very very small margin"*

Measured on his own chart, the level being 4629.245:

```
 #  breakout   reached above level   closed above level   HELD    result
 1  7:02 PM          3.465                 3.465         100.0%   WIN +158.10
 4  9:10 PM          3.365                 2.765          82.2%   flat  -0.40
 2  8:10 PM          0.885                 0.605          68.4%   WIN  +97.80
 3  8:51 PM          1.790                 0.555          31.0%   LOSS  -1.50
 5 10:02 PM          0.570                 0.055           9.6%   LOSS -33.50
```

The 10:02 candle pushed 57 cents through his level and kept five and a half. Both of
his objections are one measurement.

**Asked whether this was a new law, he ruled it was not:**

> *"a candle that closes well above your level is a momentum candle, whatever its
> shape.. the wick represents price rejection. a wick in the direction of the
> breakout weakens the strength of the breakout."*

So `LAWS.md` line 23 — *"a momentum candle (no big wick)"* — was already the law; I
had simply measured it in the wrong place. My test was `wick ÷ the candle's own
height ≤ 0.35`: a shape test blind to the level, and **0.35 was my number, never his
page's**. The 10:02 candle scored 29.9% and sailed through.

**v1.22 `InpBreakHold`:** of everything the candle took past the UHV's high, the close
must still hold this share.

## 2. The threshold, swept — and my second constant retired

The clause is his; the number is mine, so it was swept rather than chosen. Seven days,
his chart, frozen ground:

```
  no wick test at all            5W/16L  23.8%  +163.60
  my old shape test 0.35         5W/14L  26.3%  +224.10   <- where the evening began
  hold >= 25%                    5W/15L  25.0%  +197.10
  hold >= 40%                    5W/10L  33.3%  +358.90
  hold >= 50%                    4W/10L  28.6%  +184.20
  hold >= 75%                    3W/ 8L  27.3%  +139.40
```

Every version of his clause beats its own absence. But the 40% peak had worse
neighbours on both sides — luck's signature — so the arm with **my body-vs-average
body test also removed** was run, and the curve flattened into two clean steps:

```
  hold 40% / 45% + body test OFF   6W/10L  37.5%  +448.10
  hold 55% / 60% + body test OFF   5W/10L  33.3%  +273.40
```

**My body-vs-average test was what made the curve spike.** It is another shape test,
covered by the same ruling, and removing it recovered a winner. Retired in v1.24;
`InpBreakHold` shipped at 45%. Honest limit on record: **one trade** separates those
two steps, on a 16-trade sample.

## 3. FOUR DEFECTS IN THE MEASUREMENT RIG, all found chasing that one candle

### 3a. His chart was expiring (`f5c95f5`)
`oanda_m1.csv` is a rolling ~5,000-minute window. `oanda_bars.csv` — the candle table
the EA judges every setup on — was **overwritten** each cycle; the volume table got
this exact fix on Aug 21, the bars writer never did. Meanwhile `oanda_archiver.py`
(the permanent history) **had not run since Aug 7** — it was never in `startup.bat`.
Aug 8–17 is lost forever; Aug 18–21 was about a day from expiring. Fixed: bars write
merges, archiver in startup and running, new `monitor/oanda_tables_backfill.py`.
Testable ground: 4 partial days → **7** (Aug 5–7 recovered, Aug 18–21 kept).

### 3b. The EA silently mixed feeds (v1.20)
`bHigh`/`bLow`/… fall back to the BROKER's candle, one bar at a time, whenever the
OANDA table lacks that minute. A partially-covered day judged half the setup on his
chart and half on Blueberry's, invisibly. `InpOandaStrict` refuses such bars and the
census counts them. Aug 5 changed 8 trades/−131.00 → 5 trades/−160.80 — three of its
eight trades had been feed-mixed.

### 3c. The ground moved under the tester (v1.21)
Aug 18 returned **1 trade (−34.70) and then 0 trades** from the same binary and the
same `.set`. Three controlled runs with the data files hashed around each: the EA is
deterministic (runs 2 and 3 matched to the counter) — the **file changed mid-run**.
The EA re-read the tables every bar; the bridge rewrites them every cycle. Fixed: in
the tester the chart is read ONCE at init and frozen (it prints the row counts), live
still re-reads every bar. Runners now hash both tables around every run and print
`GROUND CHANGED`.

### 3d. 🚨 OANDA RESTATES SETTLED VOLUME (`fb9801e`, `ad2c2d9`)
One bridge cycle, zero rows added, **38 already-settled minutes revised**, days old:

```
  2026.08.18 17:06   1841 -> 1810
  2026.08.18 19:41    536 ->  477
  2026.08.19 03:06    847 ->  844
```

Prices did not move (0 revisions). **Volume did — and volume is what the UHV law ranks
on**, so a restatement can crown a different loudest candle and hand a different
verdict. This explains Aug 18's flip-flop, a seven-day total drifting +258.80 →
+224.10 on identical settings, and five of sixteen sweep arms tripping the tripwire.
Rule now in all three writers: **a settled minute is immutable** — only minutes
younger than 3 minutes of REAL TIME may change (defining "newest" by pull position
left Friday 23:59 mutable forever over a closed weekend, oscillating 33↔34).
Revisions per cycle: 38 → 1 → **0**.

## 4. The funnel: which law was actually cutting the trades

He asked, seeing few setups. Seven days, 2,078 New York minutes:

```
  RANGING (no trend)          1668   80.3%  ########################################
  no UHV in it                 346   16.7%
  no valid retracement          42    2.0%
  brk: WICK (his clause)        11    0.5%
  FIRED                         16    0.8%
```

**The trend gate refused four minutes in five.** His wick clause — the night's whole
subject — refused eleven candidates in seven days. Then his correction, which broke
the case open:

> *"friday 21st august is not at all a ranging day.. means most of the day the market
> was in an uptrend"*

## 5. TWO DEFECTS IN THE TREND LAW — one his page already forbade

A faithful transcription of `TrendNow()` diagnosed Friday minute by minute: **not a
single failure was "no structure found."** 287 of 420 session minutes failed on
clause C — *the last two lows and the last two highs must both be rising*. Price
climbed 4613 → 4627 → 4622 while the verdict flickered UPTREND / not / not / UPTREND.

And [`LAWS.md`](../../LAWS.md) line 33 already says otherwise:

> *we stop buying, when the last low is broken .. we keep trading until the last low
> is safe (unbroken below). Whenever a high is broken, the deepest point (the lowest
> point) is the confirmed higher low.*

**His page says the trend LATCHES; my code re-litigated it every minute.** Fixed in
v1.26 (latch) and v1.27 (the guard moves only when a genuine hump top is taken — his
camel humps are swing highs, not any candle that ticks higher):

```
  v1.25  re-proved each minute   ranging 80.3%   16 tr  6W/10L  37.5%  +448.10
  v1.26  latched, any new high   ranging 67.4%   22 tr  7W/15L  31.8%  +281.10
  v1.27  latched, hump tops      ranging 62.6%   24 tr  8W/16L  33.3%  +296.60
```

Better structure, more winners — **not better money**. And Friday still read 233 of
314 minutes as a range, so the latch fixed a real bug but not *the* bug: re-arming
still ran through the same broken two-point test.

## 6. 🏆 HIS IDEA WINS — the trend is the EMA-5 slope

> *"what if you remove this gate, see how it goes then? use the slope of EMA 5 instead
> as your trend line"*

Same laws, same chart, same seven days — only the answer to "are we trending" differs:

```
  my camel-hump structure (v1.27)   24 tr   8W/16L  33.3%  +296.60
  v1.25, where the evening began    16 tr   6W/10L  37.5%  +448.10
  EMA-5 slope over 1                45 tr  15W/30L  33.3%  +403.10
  EMA-5 slope over 3                37 tr  12W/25L  32.4%  +323.10
  EMA-5 slope over 5                32 tr  12W/20L  37.5%  +596.70
  EMA-5 slope over 10               30 tr  12W/18L  40.0%  +624.00
```

**More trades AND a higher win rate AND double the money** — the opposite of the usual
trade-off, from an indicator already on his page. Shipped as the default in v1.29
(`InpTrendMode=1`, `InpEmaSlopeBars=10`) and **attached live at 0.01**.

⚠️ **The "no gate at all" control arm was VOID** — identical to the gated arm to the
cent, because switching `InpRequireTrend` off still left the buy-side line demanding
`trend == +1`. Rebuilt as a separate EA (`BasedOnLawsNoGate`, magic 88194) so his
attached binary is not disturbed; result pending. It matters: if no gate matches
EMA-10, the gate is worth nothing.

## 7. His chart vs the broker's — the uncomfortable measurement

Same laws, same days, only the chart being judged differs:

```
              HIS CHART (OANDA)          BROKER (Blueberry)
  Aug 5     4 tr  1W/3L    -91.50      5 tr  3W/2L   +204.60
  Aug 6     4 tr  0W/4L   -188.70      2 tr  0W/2L    -46.90
  Aug 18    1 tr  0W/1L    -34.70      0 tr             0.00
  Aug 19    2 tr  1W/1L   +172.50      2 tr  1W/1L    +78.00
  Aug 20    2 tr  1W/1L   +149.00      4 tr  3W/1L   +425.00
  Aug 21    3 tr  3W/0L   +441.50      5 tr  1W/4L    +27.50
  TOTAL    16 tr  6W/10L  +448.10     18 tr  8W/10L  +688.20
```

**On raw P&L over five trading days the broker's chart scores higher.** But Friday is
the only day with ground truth — his own hand-marked setups — and there **his chart
returns exactly his three trades (3W/0L) while the broker's returns five different
ones (1W/4L)**. The feeds are not ranking the same setups better or worse; they find
DIFFERENT setups, exactly as the 46% "which candle is loudest" disagreement predicts.
His page says OANDA; five days do not overturn a law. Logged, not buried.

## 8. State at 03:00 PKT, Aug 24

```
LIVE      BasedOnLaws v1.29   magic 88184  0.01 lots  XAUUSD M1   (attached ~03:00)
          ZeeUHV / Loud / Shop B / logger — unchanged
🚨        ZeeUHV_Diamond 88154 — STILL FULL SIZE, decision still owed
BUILT     BasedOnLawsNoGate v1.29  magic 88194 — control arm, not attached
GROUND    7 days of his chart (Aug 5-7, 18-21), immutable, growing daily from now
```

**Still running as he sleeps:** the slope dial extended (15/20/30/45 — the default may
move if the crest is elsewhere), the no-gate control, and a live-feed check that the
immutability rule holds now that the market has reopened.

## 9. Numbers that are still MINE, not his — the standing audit

Each one is a place the EA can obey his law while measuring it differently than he
does, exactly as `0.35` did until he caught the 10:02 candle:

- `InpEmaSlopeBars = 10` — chosen on these same seven days
- `InpBreakHold = 0.45` — one trade separates it from 55%
- `InpTrendLook = 90`, `InpPivot = 2` — still used by the structure path
- `InpRetraceMax = 20`, `InpUpRunBars = 2` ("a sequence of greens")
- `InpMinRiskPts 0.5 / InpMaxRiskPts 10.0` — quietly refuses a setup or two a day
