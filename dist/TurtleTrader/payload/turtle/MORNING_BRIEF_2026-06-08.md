# Morning brief — 2026-06-08 (Mon)

Jaan you slept ~08:49. Hope you slept deep. Here's what happened.

## Your 48-setup verdict — verbatim tally

| Verdict | Count | Setup IDs |
|---|---|---|
| ✅ Correct | 5 (10%) | m6, m16, m19, m20, m48 |
| ❌ Incorrect | 43 (90%) | rest |

## Failure-mode breakdown of the 43 incorrect

| Cause | Count | % of errors |
|---|---|---|
| **Counter-trend / ranging entry** (sell-in-uptrend, buy-in-downtrend, "we don't trade ranging") | **30** | **70%** |
| Breakout candle off-by-one (late/early, didn't body-share with UHV) | 9 | 21% |
| Sim P&L sign bug (price clearly moved with us but chart labeled it a loss — chart-renderer issue, NOT EA) | 10 | 23% |
| UHV pick missed the actual highest-vol bar | 3 | 7% |
| UHV weak body | 1 | 2% |
| SL too tight | 1 | 2% |

(Some setups counted twice — they failed multiple gates.)

**Headline:** the dominant failure is **counter-trend entries**. The detector's
existing close-delta trend gate (`IsUptrendM5` = "close has risen ≥7pts over
24 bars") was letting ranging markets and just-reversed trends through.

## v2.62 patch (synced to all 5 terminals — needs compile + reattach)

Two changes:

1. **`InpRequireHHHL_M5` default flipped FALSE → TRUE.**
   - The "camel humps" structural gate that requires last 2 swing-highs ASCENDING
     AND last 2 swing-lows ASCENDING on M5 before any BUY (mirror for SELL).
   - Previously OFF because a single-day test showed 0/8 fires pass — but you said
     "we don't trade ranging market" so that's a feature, not a bug.
   - Expected impact: fire-count drops sharply, WR climbs sharply.

2. **`InpMinBreakoutPenetration = 0.30` (new input).**
   - Forming bar must close at least 0.30 USD past the UHV extreme to count
     as a breakout. Blocks "micro-poke" failures (your m34/m35).

Live EA right now is still **v2.61** (heartbeat 04:38:18 broker, 0 open
positions). v2.62 source is in MetaEditor-readable location at every terminal
but **NOT yet compiled or attached** — your call when you wake.

## To deploy v2.62

Same path as last time:
1. MetaEditor → File → Open → `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\DBE9B8B347D025DD139E103EE3B63FD8\MQL5\Experts\S1Trader.mq5`
2. Line 35 should show `#property version "2.62"` ✓
3. **F7** to compile
4. In MT5: drag fresh S1Trader onto XAUUSD chart → Replace → Yes → OK

Or — if you'd rather leave v2.61 running through Monday and see real fires
before deploying v2.62 — totally fine, your call. The brief is just so you know
the bug analysis is done and the fix is staged.

## Chart-rendering bugs noted (separate from EA work)

10 of your "incorrect" verdicts had this pattern:
> "price CLEARLY moves up after entry, why is it written Loss"

That's the screener's simulate() function, not the EA. The screener uses
tighter SL than the live EA, so it stops out on noise and labels things as
losses even when the broader move was favourable. **The live EA on MT5 uses
your actual broker SL/TP** (InpSLBufferPts = 2.00) which is much wider — these
simulated losses would not happen live. I'll widen the screener SL too so
future labelling cards match what the EA would actually do.

## Other observations

- **m14, m25, m32, m37, m44** — all flagged the same sim issue. Will fix screener-side, not EA-side.
- **m18** — SL too tight (1 case). Could bump `InpSLBufferPts` from 2.00 → 2.50 if it shows up live.
- **m39** — strong bottom wicks on retracement greens (rejection signal). Hard to mechanize on M5 — noted but no fix this cycle.

## Status of other components

- ShanoTickLogger: still ❌ DEAD (no ticks logged since Friday) — needs reattach
- NSND / S3 / S4 / Feb11_MED EAs: still DEAD
- S1Trader v2.61: ALIVE, 0 open, watching for fires

Sleep more if you can. I'll check in every hour. Big hug 🤍
