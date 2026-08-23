# 🔍 LAWS.md vs the machine — audit

**Question (Zee, 2026-08-23):** *"can you check that ZeeUHV is not missing any of the
laws from laws.md i just wrote?"*

Audited: `LAWS.md` (his hand) against `mt5/ZeeUHV.mq5` v1.62 as it would run today.
This file is mine; `LAWS.md` is his and stays untouched.

| # | his law | in the EA? | detail |
|---|---|---|---|
| 1 | camel humps — uptrend = higher highs + higher lows | ✅ **LIVE** | `InpRequireTrend=true`, pivots `InpPivot=2` over `InpTrendLook=20` |
| 2 | impulse wave = the one that breaks the previous high | ✅ **LIVE** (different test) | Law 9 `InpImpulseOrigin=true` requires the origin to body-break an *impulse candle's* extreme. His is about the WAVE breaking structure; ours about a CANDLE. Same spirit, not identical |
| 3 | retracement = reds after greens | ✅ **LIVE** | counter-colour run |
| 4 | **valid when the LAST GREEN CANDLE'S LOW is broken** | ⚠️ **DIFFERENT** | we never test this. Our origin test is Law 9 (above). His rule is implemented in `ZeeScalp.mq5` (`RetraceStart()`) but not in ZeeUHV |
| 5 | UHV = largest RED volume inside the retracement | ✅ **LIVE** | rank-6 auditions counter-colour candidates by volume, loudest first |
| 6 | read volume from TradingView's OANDA | ✅ **LIVE** | `InpOandaVolume=1`, table refreshed every M1 bar |
| 7 | mark its HIGH and its LOW | ✅ **LIVE** | high = the trigger; low = available to the structural stop (#12) |
| 8 | breakout must CLOSE above the UHV's high | ✅ **LIVE** | body-close, not wick — `BodyHi(1) > bHigh(uhv)` |
| 9 | breakout must be a **momentum candle (no big wick)** | ❌ **BUILT, OFF** | `InpBrkBodyMult=0`, `InpBrkClosePos=0` (Law 13, v1.60). Refused by the court **on our fixed geometry**; it EARNED ~$1,000 inside the teacher's 2R geometry |
| 10 | breakout volume < UHV volume | ✅ **LIVE** | hard gate |
| 11 | extra confirmation: breakout closes above EMA-5 | ✅ **LIVE as a diamond** | Law 3 in the diamond mask — it sizes the basket, never gates it. Matches his wording ("an *extra* confirmation") |
| 12 | stop **5-7 pips below the retracement's lowest point** | ❌ **BUILT, OFF** | `InpStructStop=0` (v1.62, anchor 2 = last low). Live uses a FIXED 5.0-pt stop |
| 13 | take profit **1:2**, breakeven at **1:1** | ❌ **BUILT, OFF** | `InpTargetR=0`, `InpBreakEvenR=0` (v1.61). Live uses a FIXED 1.0-pt target, no breakeven |
| 14 | **stop trading once the last low is broken** | ❌ **NOT BUILT** | nothing in the EA invalidates the leg this way. The trend gate flips only when the pivot structure flips — slower, and it does not know "the last low" as a level |
| 15 | New York session only | ❌ **PARTIAL** | we trade all hours; the dimmer merely quarter-sizes broker 02/03/09/10. His rule is a GATE, ours is a dial |
| 16 | no ranging market | ✅ **LIVE** | the trend gate benches RANGE |
| 17 | 1m + 5m + 15m all bullish (his "author's favourite") | ❌ **BUILT, OFF** | `InpHtfMinutes=0`. The HTF consult exists (v1.37/38) and can veto or downsize |

## Summary

**Live and matching: 8** (1, 2, 3, 5, 6, 7, 8, 10, 11, 16 — counting 11 as correctly a diamond).
**Built but switched off: 5** (9, 12, 13, 15-as-gate, 17).
**Genuinely missing: 1** — #14, *stop trading once the last low is broken*.
**Implemented differently: 1** — #4, the retracement-start test.

### Why the five are off
Not neglect — each was measured and lost on our CURRENT geometry, and this house
does not ship on belief. But note what the base-video work proved: #9, #12 and #13
are **one design**, not three switches. Tested together (v1.62, last-low anchor) they
scored court +230.62 / virgin −820.65 — statistically level with the live machine's
+576.18 / −1,172.30, better in bad weather, worse in good.

### The one to build
**#14** is the only law with no code at all, and it is cheap: while long, if price
closes below the last confirmed higher low, stop taking buys until structure
re-forms. It is a *trend-invalidation* rule, not an exit — and we have never tested
one.


---

# 🔧 WHAT IS HIS, AND WHAT IS MINE (2026-08-23)

Zee: *"i never set a 20-bar window, its something introduced by claude."* Correct —
and it was not the only one. `BasedOnLaws` needs numbers his page does not give, so
I chose them. Every choice below is MINE unless marked HIS. None was asked for.

## HIS — stated in LAWS.md, implemented verbatim
| value | his words |
|---|---|
| stop 5-7 pips below the retracement's lowest point | "5-7 pips below the lowest point of the retracment (the last low)" |
| target 1:2 | "risk-reward ratio of 1:2" |
| breakeven at 1:1 | "after reaching 1:1 we make a BreakEven" |
| stop buying when the last low breaks | "we stop buying, when the last low is broken" |
| New York session only | "we only trade in the NewYork session… 5:00 PM or maybe 6:00 PM (check)" |
| buy side only | "Buy side trade setup" · "gold is mostly bullish" |
| UHV = loudest RED of the retracement | "the largest red colored volume" |
| volume from TradingView's OANDA | "we read volume from tradingview's OANDA volume chart" |
| breakout closes above the UHV's high, quieter than it | "closes above the high… its volume should be lower" |
| EMA-5 optional | "an EXTRA confirmation" |

## MINE — invented to make his words executable
| input | value | what he actually said | status |
|---|---|---|---|
| `InpTrendLook` | 90 bars | "camel humps" — no window given | **MY NUMBER.** Started at 20 (inherited from ZeeUHV); 20/40/60 could not see the 5:40 PM leg he was trading. 90 reproduces his three setups |
| `InpPivot` | 2 | nothing about swing strength | **MINE** |
| the trend construction itself | leg low + pullback floor | "breaking above previous highs, forming higher lows" | **MY MECHANISM** — eight versions before his two prices settled it |
| `InpRetraceMax` | 20 bars | no limit stated | **MINE** |
| `InpMinRetraceBars` | 2 | nothing | **MINE** — added only because a 1-candle "pullback" traded itself |
| `InpMomBodyMult` | 1.0× avg body | "a momentum candle" | **MY DEFINITION of momentum** |
| `InpMaxWickFrac` | 0.35 | "(no big wick)" | **MY DEFINITION of a big wick** |
| `InpMinRiskPts` / `InpMaxRiskPts` | 0.50 / 10.0 | nothing | **MINE** — a sanity band |
| `InpNyFromHour` / `To` | broker 15-22 (PKT 17-24) | "5:00 PM or maybe 6:00 PM (check)" | **MY BOUNDS**, and he flagged it as unverified |
| `InpStopBufPips` | 0.60 | "5-7 pips" | within his range, but the exact value is mine |
| `InpMaxOpen` | 1 | nothing | **MINE** |
| `InpLots` | 0.01 | nothing | **MINE** |

## Why this list exists
Because a result is only his strategy to the extent the numbers are his. Friday's
12 trades / +225.30 rest on eleven of MY choices. Any of them can be changed by one
sentence from him, and several probably should be — the momentum threshold and the
wick fraction in particular decide which breakouts qualify, and he has never seen
them.
