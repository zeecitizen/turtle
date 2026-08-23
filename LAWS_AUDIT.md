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
