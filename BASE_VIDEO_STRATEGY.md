# 🎥 THE BASE VIDEO — Ahmad Umair's buy-side gold scalp, extracted

**Source:** `base_video/VSA Buy Side Scalping Strategy for Gold  1-Minute Setup Part 1.mp4`
(32:49, Ahmad Umair Akhtar — *The Forex Guide*). Transcript already in the repo:
`monitor/_loom_audio/yt_2mKEfO85D04.txt` (12,178 chars, Urdu). Chart in the video:
**TradingView, XAUUSD 1-minute, OANDA feed, Volume indicator** — the same eye Zee
uses, which is why our OANDA-volume work matters.

Part 1 is BULLISH only. Part 2 (`JWmETwP7sx0`, also transcribed) is the sell side.

---

## His rules, in his order

**1. Session.** New York only. He shows ~4 trades inside about 1.5 hours.

**2. Trend first — scalp only with it.**
> *"جس طرف ٹرینڈ ہے اسی طرف کی سکیلپنگ ہوگی"* — scalping goes the way the trend goes.

Read on the 1-minute itself. Structure = two kinds of wave:
- **Impulse wave** — the one that BREAKS the left-side structure (break of structure).
- **Retracement** — the weak wave after it: *"جاندار ویو نہیں ہوتی"*, no life in it,
  small candles drifting back slowly.

The cycle repeats: impulse → retracement → impulse (new BOS) → retracement. **Every
retracement in a bullish leg is a buy opportunity.**

**3. What makes a retracement REAL** (his answer to "people get confused here"):
> the **LOW of the last bullish candle must be broken**.

Two candles are enough if that low broke. No broken low = not yet a retracement.

**4. The candle: the biggest volume in that retracement.**
> *"اس ریٹریسمنٹ کا سب سے بڑا والیوم"* — the largest volume bar of the pullback. Mark it.

**5. The trigger: its HIGH must break — and the breaker must be a LOW-VOLUME
MOMENTUM candle.**
> *"بڑے والیوم کا ہائی بریک ہو گیا... لو والیوم مومنٹم کینڈل"*

Both properties at once: **low volume AND momentum**. If the high breaks on a candle
that is not a momentum candle, he does **not** take it — *"اگر آپ کو مومنٹم کینڈل نہیں
ملتی... تو پھر آپ ویٹ کریں گے"* — you WAIT for a momentum candle.

**6. Stop loss: below the LOW of that big-volume candle**, plus a small buffer.
Structural — not a fixed distance. He mentions stops around 30-35 pips of his scale.

**7. Target: 1 : 2.** And a hard rule on the way there:
> at **1:1, move the stop to breakeven — لازمی (mandatory)**.

He shows the value of it: a trade that reached 1:1, was moved to breakeven, then came
back and stopped out flat — first target banked, nothing given away.

**8. No setup = no trade.** After a retracement's low breaks, if there is no big-volume
bullish candle whose high is then taken by a low-volume momentum candle, he skips it.

---

## What this changes for us — the honest diff

Our EA already shares his skeleton (trend → retracement → loudest candle → break of
its high on lower volume). The differences are in the parts we invented ourselves:

| | Ahmad Umair | ZeeUHV today |
|---|---|---|
| trend | 1-min BOS structure | camel humps HH/HL — **same idea** |
| retracement valid when | **last bullish candle's LOW breaks** | origin body-breaks an impulse candle's extreme (Law 9) — **different test** |
| the candle | loudest volume of the retracement | the UHV — **same** |
| trigger | break of its HIGH | **same** |
| breaker candle | low volume **AND momentum**; else WAIT | low volume only — **momentum missing** (Law 13, refused 2026-08-22) |
| stop | **below that candle's LOW** (structural) | fixed 5.0 pts |
| target | **1 : 2 of the risk** | fixed 1.0 pt |
| breakeven | **mandatory at 1:1** | none |
| session | New York | all hours, four dimmed |

**The biggest single difference is the geometry, and it is not small.**
His stop and target are *relative to the setup*: risk R, take 2R, protect at 1R. Ours
is absolute: risk 5.0 to make 1.0. That is 5:1 against us, which is why our machine
needs ~83% just to break even, while his needs ~33%. Same entry, inverted economics.

That combination — structural stop + 1:2 target + breakeven at 1:1 — **has never been
run through our court.** Every geometry test we own (SL20/TP1, SL5/TP1, TP 0.5/0.75/1.5,
the conviction-scaled family) kept a FIXED stop and a fixed target. This is the one
shape of the exit we have never measured.

**Also note what he confirms independently:** the breakout must be a *momentum* candle.
Zee said the same thing on 2026-08-22 from his own forensic, before we found this video.
Law 13 failed the court *as a filter on top of our geometry* — but it has never been
tried inside HIS geometry, where a momentum breakout is paired with a structural stop
and a 2R target. Those two may only work together.

---

## Suggested experiment (not yet run)

`ZeeScalp` — his rules end to end, on its own magic:
structural stop below the UHV's low · target 2× that risk · breakeven at 1R ·
breakout must be low-volume AND momentum · NY session · OANDA volume.
Court + virgin, win rate beside net. Then compare against ZeeUHV's fixed geometry
on identical days.
