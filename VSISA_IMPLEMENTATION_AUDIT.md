# VSISA — what the EA ACTUALLY does, against what the strategy says

**Zee, 2026-09-12:** *"we're going too much into testing something i dont fully understand
the implementation of... what if we've internally deviated from the original strategy
described in the videos... what if tuning the strategy results in a good winrate and
profit? i've to yet fully understand what you're doing"*

He is right to stop. This is the audit: every clause of the EA, side by side with
`LAWS_VSISA.md` and the transcripts, with the deviations named rather than buried.

**Headline: the live configuration implements roughly the first half of the method and
none of the second, on the wrong volume feed, with a wider stop than specified.**

---

## What the EA checks, in order, right now

Bar 1 = the just-closed bar. Bars 2–3 = the setup. Bars 4–13 = the volume yardstick.

| # | the EA's actual test | shipped value |
|---|---|---|
| 1 | enough history | 2 setup bars + 10 lookback |
| 2 | build yardstick: max and average volume of the **last 10 bars** | `VolLookback 10` |
| 3 | the 2 setup bars each close the same direction | **OFF** (`StrictDir false`) |
| 4 | each setup bar's volume ≥ **1.20 ×** the 10-bar average | `BigAvg 1.20` |
| 5 | the **louder** setup bar ≥ **0.80 ×** the 10-bar maximum | `BigPct 0.80`, `BigMode 1` |
| 6 | bar 1 closes the OPPOSITE way to the setup | always on |
| 7 | bar 1's body ≥ **0.35** of its range | `BodyFrac 0.35` |
| 8 | bar 1's volume ≤ **1.00 ×** the setup's average volume | `LowVolPct 1.00` |
| 9 | higher-timeframe trend agrees | **OFF** (`TrendTF 0`) |
| 10 | stop = **30 points beyond the lowest low of ALL THREE bars**, floor 60 | `SlBufPts 30` |
| 11 | refuse if risk > 900 points | `MaxSlPts 900` |
| 12 | enter at market, target 2.5 × risk, stop to entry at 1R | `TargetR 2.5`, `BE 1` |
| 13 | up to **10** positions at once, no cooldown | `MaxOpen 10`, `CoolBars 0` |

---

## THE DEVIATIONS

### 1. The volume feed is wrong — and his own LAWS.md says so in line 2

> *LAWS.md, line 2:* "we read volume from TradingView's OANDA chart of XAUUSD, **the EA
> makes the mistake of reading volume from Broker Blueberry. We donot want to make this
> mistake.**"

VSISA judges **broker tick count**. Measured, not assumed: `iRealVolume` returned 0 reads
on both Blueberry and Axi (gold CFD publishes none), so every comparison falls back to
the broker's tick count. The OANDA reader is built and wired in but defaults OFF because
the bridge's coverage cannot yet support it.

**Everything else below is secondary to this. The strategy is a volume method being run
on a volume number he does not read.**

### 2. "That session's highest volumes" became "the last 10 bars"

> *LAWS_VSISA.md:* "on the 2nd red bar there's a large red volume. **these volume's will
> be that session's highest volumes**"
> *Part 1:* "compare with the big volumes of the previous two or three days"

The EA compares against the **last 10 M5 bars — fifty minutes**. A bar that is merely the
loudest of the previous fifty minutes now qualifies as the session's climax. This is the
single largest weakening of the method, and it was my change on his instruction
("that's alot of bars to check from.. we can just check the last 10 bars") — a reasonable
request that I applied without flagging that it redefines the core term.

### 3. The stop was measured from the wrong candle — FIXED 2026-09-12

> *LAWS_VSISA.md:* "**Stop loss 2-3 pips below the bullish blue candle.**"

The EA puts the stop 30 points below the **lowest low of all three bars** — the two setup
bars and the reaction. Because the setup bars are the down-move, their lows are far below
the reaction candle's low, so our stop is systematically **much wider** than specified.

This is why live stops came out at 526 and 876 points. His rule produces a far tighter
stop and therefore a completely different R multiple on every trade. **This single
deviation changed the economics of the whole strategy.**

**FIXED.** `InpStopRef` now defaults to 0 — the stop hangs 30 points (3 gold pips) below
the REACTION candle, as his document specifies. Mode 1 keeps the old, wider behaviour so
the two can be compared rather than swapped on faith.

⚠️ **Watch the floor.** `InpMinSlPts = 60` was sized for the old wide stops. With the
correct reference most stops will now be far tighter, so that 60-point floor will start
binding often and quietly re-widening them. Axi's gold spread is ~9 points, so his 2-3
pips (20-30 points) is only 2-3x the spread — tight, but it IS what he specifies. The
floor probably needs to come down to ~25-30, and that is his call.

### 4. "Red down bars" no longer have to be red

`InpStrictDir` is OFF, so the two setup bars are not required to close in the same
direction. His 2-bar setup is literally defined as *"red down bars, downtrend pe bara
volume"*. Removing that was his instruction (it was cutting 57% of candidates), but it
means the pattern being traded is no longer the pattern he drew.

### 5. There is no trend and no retracement

His method sits inside a context: a trend, a retracement within it, London or NY session.

- `TrendTF 0` — no trend filter at all
- **no retracement concept exists anywhere in the EA**
- `SessFrom 0, SessTo 24` — trades all hours, though he stresses London open and NY

> *Part 7:* "if you take this trade in the direction of trend then that's really good"
> *Part 10:* "**never chase the market. always catch the market on a retracement**"

### 6. The confirmation tiers are absent

His ladder, in his own words:

| tier | condition | in the EA |
|---|---|---|
| 1 | 2-bar setup + low-volume reaction | ✅ this is all we have |
| 2 | + at a support/resistance level | ❌ not implemented |
| 3 | + **fake break** of that level, wick, close back inside | ❌ built, tested, OFF |

### 7. Other described behaviour that is off or missing

| his rule | status |
|---|---|
| the wick below the blue candle = aggressive buying | built, **OFF** |
| the no-supply test (his confirmed entry) | built, **OFF** |
| end of rising market / bag holding | **never implemented** |
| one setup at a time | `MaxOpen 10` |

### 8. The entry — RESOLVED, and the EA was already right

I read line 33 ("entry above the blue bullish candle") as a stop order above the candle's
high, and flagged it against line 16 ("entry at this candle") as a contradiction.

**Zee, 2026-09-12: "it doesnot mean a stop order above its high.. it means same as line
16 ... at the reaction candle's close (what we do)."**

Both lines describe the same trade. The EA enters at the reaction candle's close and is
**correct as built**. No deviation. The ambiguity was mine, not his document's.

---

## Why this matters more than any backtest

His question — *"what if tuning results in a good winrate and profit?"* — has a sharp
answer:

**A good number from this implementation would not be evidence that his method works.**
It would be evidence that *something* works on gold M5, discovered by searching a
parameter space that no longer describes his strategy. Tuning a drifted implementation
launders an accident into a conclusion.

That is exactly the failure mode CLAUDE.md was written about, one level up: not "Python
lied", but "the thing being measured was not the thing intended".

## The order of work that actually makes sense

1. ~~He rules on the entry~~ — **DONE**: entry at the reaction candle's close, the EA
   was already correct.
2. ~~Fix the stop reference~~ — **DONE**: `InpStopRef 0`, below the reaction candle.
   Still open: whether `InpMinSlPts` should drop from 60 so the floor stops overriding
   his 2-3 pips.
3. **Restore "session's highest volume"** as a real definition, whatever window he wants
   that to mean. Currently 10 bars = 50 minutes.
4. **Get the OANDA feed working**, or accept in writing that we trade broker tick count.
5. **Only then tune** — and tune inside the strategy, not through it.

No further optimisation should be run before steps 1–3. The numbers would not mean
what they appear to mean.
