# LAWS_VSISA_INFER — Volume Spread Imbalance Shift Analysis

**Inferred by Claude from (a) Zeeshan's `LAWS_VSISA.md` and (b) transcripts of the
22-part course "Volume Spread Imbalance Shift Analysis" by Sajid Ahmed.**

This file is MINE, not Zee's. `LAWS_VSISA.md` is his and is never edited. Where the two
disagree, HIS wins — every such point is flagged below.

> **Provenance.** Transcripts live in `monitor/_vsisa_transcripts/partNN_orig.md`
> (Urdu/Hindi, Whisper). Parts 1–21 are covered; part 22 is not.
> The YouTube auto-translated English captions were fetched too and are **worthless** —
> machine ASR of Urdu hallucinated into English nonsense. They were discarded.
> **The May transcript numbering was off by one** (that run downloaded an extra video at
> position 2): true Part N = old `part{N+1}.txt` for N≥2. Proven by matching audio
> durations against the videos in `C:\Users\zeesh\Downloads\VSISA`, not assumed.

---

## 0. The one idea the whole course is about

Everything below is one claim wearing different clothes:

> **Price moves when the resting orders in its path are gone — not when volume is big.**

Volume measures *transactions*, i.e. **effort**. Spread measures *result*. The teacher
judges every candle by the ratio between them, and by what the NEXT candle does about it.

- **Big volume + small spread** = huge effort, no result = the path is *full* of opposing
  orders. Someone is absorbing.
- **Small volume + big spread** = tiny effort, big result = the path is *empty*. This is
  the condition he trades.

An **imbalance shift** is the moment the path empties on one side. That moment is what
the EA has to detect.

---

## LAW 1 — Big volume is a QUESTION, never an answer

> *Part 1:* "Whenever you see a big volume on a bullish candle, never say straight away
> whether this is buying or selling. 50% chance it is aggressive buying. 50% chance
> there is supply. **That means you are not sure.**"

Classic VSA calls big volume on an up-bar "weakness". The teacher rejects that as
half-truth. A big-volume bar is *unresolved*. It is resolved by **LAW 2**.

**EA form:** a high-volume bar NEVER fires a trade on its own. It only arms a setup.

---

## LAW 2 — The next bar's REACTION resolves it

> *Part 1:* "Reaction to that candle will determine whether it was supply or demand."
> Big volume on an up-bar, next bar **down** → that volume was **selling**.
> Big volume on a down-bar, next bar **up** → that volume was **buying**.

**EA form:** direction of the bar AFTER the high-volume cluster selects the trade side.
Buy setups need a down-cluster then a bullish reaction; sell setups the mirror.

---

## LAW 3 — The reaction must come on LOW volume. This is the trigger.

The single most repeated sentence in the course, and the actual entry condition.

> *Part 15:* "When supply is hit, after that the next bar comes down — **the lower the
> volume on it, the stronger the signal. If a big volume comes, SKIP it, wait more.**
> Likewise when buying happens big volumes come; the next bar goes on smaller volume and
> its closing is strongly bullish — that is a strong buy setup, a strong imbalance shift."

> *Part 7:* "The liquidity providers who were bidding have removed their buy orders. Now
> they are not providing liquidity, so the market comes down **on low volume** — that
> means the imbalance of demand and supply has happened."

Why low volume proves it: if 150 sell orders sat in the path and now price travels the
same distance on a third of the transactions, **the orders are gone**. That is the shift.

> *Part 13:* "This low volume — do not call it *no demand*. Call it **low supply**."

**EA form:** `reaction_volume <= InpLowVolPct × cluster_volume`. Volume ABOVE that
threshold does not weaken the signal — **it cancels it.**

---

## LAW 4 — The cluster: two bars, three bars stronger

> *Part 4:* "This three-bar formation is stronger compared to the two-bar. In the two-bar,
> two bars form coming down with big volumes."

Zee's `LAWS_VSISA.md` opens with exactly this and adds the volume shape:

> *Zee, three-bar:* "on first 3 reds came on high red volumes"
> *Zee, two-bar:* "red down bars, downtrend pe bara volume. on the 2nd red bar there's a
> large red volume. these volume's will be that session's highest volumes"

> *Part 4:* second bar's volume ≥ first, third bar's "even higher volume than the previous
> two" — buyers stepping in harder each bar.

**EA form:** `InpClusterBars` ∈ {2,3}; optional `InpRisingVol` requiring the cluster's
volume to escalate.

---

## LAW 5 — "Big" means big for THIS session and the last 2–3 days. Never a VSA band.

> *Part 1:* "These bands are misleading. The more you get rid of them, the better you
> perform. Compare with the big volumes of the previous two or three days."

> *Part 13:* "If you stay stuck in the bands you will not see it — you will think there
> is no ultra-high volume at all."

**EA form:** a rolling lookback (`InpVolLookback`) over recent bars; a bar is "big" when
its volume reaches `InpBigPct` of the lookback maximum. No indicator, no fixed constant.

**⚠️ MEASURED, not assumed — what "volume" actually is here.** `BarVolume()` asks
`iRealVolume()` first. Over Feb–Aug 2026 on XAUUSD it returned **0 reads from
`iRealVolume` and 8,006,496 tick-count fallbacks** — the broker publishes no exchange
volume for gold CFD, so **every VSISA decision is made on TICK COUNT.**

This is defensible: tick count is what the teacher's own retail terminal shows him, so
we are reading roughly the number he reads. But it is not exchange volume, and it is a
third number alongside broker real volume and the OANDA feed the Diamond uses. The EA
prints the split at the end of every run so this can never quietly change underneath us.

(The `project_tester_volume_blind` warning still applies elsewhere: outside real-tick
mode MT5 fabricates `tick_volume` at ~4/bar. Under model 4 it is the genuine tick count,
which is the only reason this strategy is testable at all.)

---

## LAW 6 — The wick decides whether big volume is aggression or absorption

The subtlest rule, and Zee wrote it down three separate times, so it matters to him.

**On a big-volume DOWN bar (buy side):**
> *Zee:* "if this blue candle has no wick below it — then it means supply is being hit,
> we wouldn't buy, we hold. a wick below means aggressive buying happened"
> *Part 8:* "if this lower wick had not been there, **this could be a supply**. The lower
> wick formed because it first went down, and they did such aggressive buying that the
> down candle became bullish."

**On a big-volume reaction bar (sell side):**
> *Zee:* "the wick on top of the red reaction candle tells that there was a large sell
> order... so we won't wait and call it aggressive selling. if there were no wick on top
> then we would say we have a demand still and we would wait for more confirmation"
> *Part 6:* "In the case of aggressive selling, even if a big volume comes, **you don't
> wait — you enter here.**"

So the wick is an **override**: it lets an otherwise-disqualifying big volume through.

**EA form:** `InpWickMode` — 0 off · 1 require the confirming wick · 2 use it as the
override LAW 3 would otherwise block. Default 0; this is the least mechanically certain
rule in the course and must earn its place with receipts.

---

## LAW 7 — Anomaly: tiny spread + huge volume is the strongest single bar

> *Part 9:* "Such a small candle, such a big volume — this is **the most powerful
> signal**... so much aggressive buying that they did not let the market go down. All the
> selling there was, they packed it into a bag. **Bag holding.**"

> *Part 13:* "The spread of this candle and these three are comparable, but **three times
> the volume** came."

> *Part 11:* "58,400 volume on this one, 21,000 on that — this big candle has small
> volume, this small candle has huge volume. **That is called anomaly.**"

The up-side twin is **end of rising market** (*Part 6*, and Zee's own notes at 2:10 and
6:41): large spread on small volume, then small spread on large volume, then a bearish
reaction → sell.

**EA form:** `InpAnomalyMode` — require the cluster's last bar to have spread ≤
`InpAnomalySpread` × recent-average spread while volume is at cluster level.

---

## LAW 8 — Entry, stop and target are FIXED and tiny. This is not negotiable.

> *Part 12:* "There is no need to keep extra pips of stop loss. **Just 2 or 3 pips
> maximum — 3 pips; if you are doing it on M5, 2 pips.** Easily this becomes a 6–7 pip
> stop and you get good profit."

> *Part 10:* "If you want to be profitable and get big gains, **your SL should be from 3
> pips up to 8 pips.** That small."

> *Part 15:* "Entry on the closing of that bullish candle. And this is your stop loss —
> 2 pips beyond the wick. **Follow it as it is.** No need for RSI, no order blocks, no
> market profile. Add NOTHING."

> *Zee:* "Stop loss 2-3 pips below the bullish blue candle. entry at this candle."

Targets quoted across the course: **1:2, 1:3, 1:4** — *Part 9* books at 1:2 ("1:4 you got;
booking even 1:2 is plenty"), *Part 15* shows 15 pips risk for 300 pips, *Part 16* 1:6.
Zee's note: "such moves give 1:3 r:r ratio even".

**EA form:** entry at the confirming bar's close; SL = that bar's extreme ± `InpSlBufPips`;
TP = `InpTargetR` × risk. Default target **2R**, since that is the level he says is
already "plenty" and is the one that will actually be reached often.

**⚠️ Reality check.** 2–3 pips on his FX pairs is not 2–3 pips on XAUUSD with our spread.
The EA takes the buffer in POINTS and the court sweeps it, rather than transplanting a
number from a different instrument. This is the biggest single unknown in the port.

---

## LAW 9 — Trade with the higher-timeframe trend; enter on M5

> *Part 2:* "That setup comes on H1, and we take entry on M5... take the trade in trend
> direction. **Do not catch the top.** If the trend is there, take it; otherwise don't."

> *Part 15:* "These things come even on M15 or M5 — try to be in the direction of the
> trend of the bigger timeframe. Yes, if an exceptionally big volume comes you can go
> against the trend too."

**EA form:** `InpTrendTF` (0 = off, else H1/M15) with a simple slope/structure test;
`InpAgainstTrend` allows the exception. Off by default — per
`feedback_backtests_hallucinate_take_all_chances`, a new filter starts OFF.

---

## LAW 10 — Never chase. Trade the retracement back into the volume area.

> *Part 10:* "**Never chase the market.** Always catch the market on a retracement. If you
> chase you get hit. Mark the area and buy on the retracement — you always get a better
> risk-reward."

> *Part 10:* "Do not use highs and lows for support/resistance. Use H1/M30 **areas where
> buying happened**, seen through volume. Draw the line there."

This is the same finding as our own `project_level_not_chase` memory — from the opposite
direction. Ours says the limit-at-level LOST $593.10 because a limit only fills on the
setups that come back (adverse selection). His retracement entry is a *reaction* trade at
the level, not a resting limit — worth separating before we conclude the two disagree.

**EA form:** not in v1.00. The base engine must earn its keep first.

---

## LAW 11 — Session matters; London open is the reference

> *Part 11:* "London opening is 12 or 1 o'clock Pakistan time. Check the volume — very
> big volumes came. So the session also depends on volume; give that importance too."
> Asian-session setups are valid but their "big" volume is smaller, which is exactly why
> LAW 5 is relative, not absolute.

**EA form:** `InpSessFrom/InpSessTo` in broker hours, default open.

---

## LAW 12 — Falling volume on a fall is NOT automatically bullish

> *Part 1:* "Rising prices rising volume, falling prices falling volume is bullish —
> **this is wrong. This is incomplete.** This is why people cannot make money from VSA.
> You have to see: while prices were rising, did weakness appear? If weakness appeared,
> then a down move on low volume **is a sign of weakness, not strength.**"

**Consequence for the EA:** low volume is only meaningful *relative to a cluster that just
resolved*. A quiet drift with no preceding effort is not a setup. This is why the engine
is cluster-first and never scans for low volume on its own.

---

## LAW 13 — Breakout on big volume is SUPPLY, not a breakout

> *Part 12:* "When this high broke, do not call it a breakout. It is breaking on big
> volume — supply was hit there. Then the reaction is bearish... confirmed that on the
> fresh new high, **fresh supply was hit.**"

The mirror of LAW 3 applied to structure: a level taken on LOW volume is real; a level
taken on BIG volume is a trap. This is the same shape as Zee's own "fake break of support
+ wick + close back inside" (his strongest case).

**EA form:** `InpFakeBreak` — require the cluster to sweep a recent extreme and close back
inside. This is his tier-3 "strongest" case and is worth its own arm in the court.

---

## The confirmation ladder (Zee's own words, his `LAWS_VSISA.md` lines 22–24)

| tier | condition | strength |
|---|---|---|
| 1 | 2-bar cluster + low-volume reaction candle | valid |
| 2 | + at a support/resistance level | stronger |
| 3 | + **fake break** of that level, wick, close back inside | **strongest** |

---

## What the EA implements in v1.00

The engine is LAWS **1–5 + 8**, which is the irreducible core — cluster, reaction,
low-volume confirmation, fixed geometry. LAWS 6, 7, 9, 11, 13 ship as **inputs defaulting
OFF**, so each can be convicted or acquitted on its own MT5 receipts instead of being
smuggled in as an assumption. LAW 10 is not implemented.

**Not implemented, deliberately:**
- *Part 18*'s currency-strength-meter filter — it compares two currencies' strength and
  has no meaning on a single instrument.
- *Part 16/17*'s fib-50/61.8 + Automatic-Rally-line method — a genuinely different second
  strategy, not a variant of this one.

---

## VERDICTS — what the MT5 Strategy Tester said (2026-09-09)

Seven months of real XAUUSD M5 ticks, 2026-02-02 to 2026-09-01, model 4, delay 163 ms.
Every line below is an MT5 result, not a Python screen. Full receipts in
`VERSION_HISTORY.md` under *VSISA v1.00*.

| law | verdict | evidence |
|---|---|---|
| 1 · big volume is a question | **KEPT** — structural, cannot be tested alone | — |
| 2 · the reaction names the side | **KEPT** — structural | — |
| 3 · reaction must be QUIET | **CONFIRMED** | unconstrained +$621 vs constrained +$1,024 |
| 3b · quiet vs the CLIMAX | **CONFIRMED** | `QuietRef=0` swept every top row |
| 4 · the cluster | **CONFIRMED at 2 bars** | 2-bar beats 3-bar on net in every sweep |
| 4b · rising cluster volume | **REJECTED** | +$580 best vs +$3,376 |
| 5 · "big" is relative | **CONFIRMED**, plateau 30-105 bars | no spike — see the ledger |
| 6 · the wick | **REJECTED** | `WickMode=0` beats require and override alike |
| 7 · the anomaly | **REJECTED** | collapses to 1-4 trades; best +$305 |
| 8 · tight stop, R-multiple target | **CONFIRMED at 2.5R + BE@1R** | BE on +$1,386 vs off +$1,213 |
| 8b · his 2-3 pip stop | **DID NOT TRANSFER** | FX pips ≠ gold; 30-pt buffer, 60-pt floor |
| 9 · trade with the H1 trend | **CONFIRMED — the biggest single win** | same net, HALF the trades, 27% -> 34% WR |
| 10 · never chase, buy the retracement | **NOT IMPLEMENTED** | — |
| 11 · session | **NOT TESTED** | shipped open |
| 12 · falling volume ≠ bullish | **KEPT** — encoded as cluster-first | — |
| 13 · the fake break | **REJECTED** | absent from all 30 top rows of a 336-pass sweep |
| — · the no-supply test (confirmed entry) | **REJECTED, after a repair** | see below |

**The no-supply test deserves its own paragraph, because I nearly libelled it.** My first
implementation compared the test bar's volume to the REACTION bar — which LAW 3 has
already forced to be quiet — so it demanded the test be quieter than something already
quiet. It fired **zero trades in 48 passes across seven months**. That is my arithmetic
failing, not his rule failing, and reporting it as "tested and rejected" would have been
false. Re-measured against the climax, like every other "small volume" in the course, it
fires properly — and then genuinely loses: **+$233 best, most variants negative**, against
+$3,213 for the aggressive entry. Only the second number is evidence.

**Three of Zee's own emphases did not survive** — the wick, the anomaly, and the fake
break he calls the *strongest* case. That is worth saying plainly rather than burying:
they may still be real on his FX pairs, on his timeframe, or to his eye. What the receipts
say is narrower — on XAUUSD M5, mechanised this way, they cost money.

---

## Honest statement of risk

Three things could make this port fail even if the reading above is correct:

1. **The instrument.** Every example is FX majors with 2–3 pip stops. XAUUSD's spread
   alone can be several times that. The geometry may simply not transfer.
2. **The volume.** He reads a retail broker's tick volume on his terminal. We have real
   volume in the tester and OANDA volume live — three different numbers for "volume".
3. **The eye.** "Compare with the last two or three days" is a human judgement he makes in
   context. Any threshold I pick is a guess at it, which is precisely why `InpBigPct` and
   `InpLowVolPct` are swept rather than chosen.

Per CLAUDE.md: everything above is a **hypothesis** until MT5's Strategy Tester says
otherwise. No number in this document is a promise.
