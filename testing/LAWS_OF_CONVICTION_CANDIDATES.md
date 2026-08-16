# THE POSSIBLE LAWS OF CONVICTION — a testable list

Zee, 2026-08-16: *"make a list of points we can test in MT5 strategy tester, that can lead
to an improvement of winrate, or strengthen our breakout's conviction. call them the
possible laws of conviction. then if some of them pass the test, we add them as filters /
diamonds (mark of conviction) to the setups we're taking."*

Every entry below is a **candidate**, not a belief. Each has a precise definition, a
parameter to sweep, and a stated reason it might work. Nothing here goes near the live EA
until it beats the shipped configuration on **a kind period AND a hostile one**, and then
survives periods it was never searched on.

---

## What we already learned, so nobody re-tests it

| | verdict |
|---|---|
| **Win rate is the wrong target** | `NullBurst` scored 91.36% at random on 22,000 trades and lost $19,132. A 1-point target against a wide stop wins from anywhere. **Rank candidates by expectancy per trade, never by win rate.** |
| **The average LOSS decides everything** | Across 13 windows the average win spans 2.09–2.81 (a factor of 1.3) while the average loss spans −0.49 to −40.82 (a factor of 83). A law that shrinks the loss beats one that adds winners. |
| **Volume needs scale to mean anything** | At 1-second resolution every law, and random, lost exactly the spread. Volume-based conviction only works where volume carries information. |
| **GATE vs DIAMOND is not the same question** | H1 alignment as a gate: −159.96 over five periods. As a diamond: −586.72. Its value was *removing* bad trades, not sizing good ones. **Every candidate must be tried both ways.** |

### Already tested — do not repeat

`MaxOpen` (inert at hold 5) · `breakout/UHV volume ratio` (tightening removes only winners) ·
`diamonds vs flat sizing` (identical at equal exposure) · `hour-of-day` (only 12:00–15:00
negative, on 14 trades) · `stop size` (5 is free at hold 5) · `hold length` (5 min best) ·
`pyramiding` (adds halve expectancy) · `UHV selection rule` (loudest is worst of four) ·
`fractal 1-second scale` (indistinguishable from random) · `cumulative delta` (impossible —
gold is OTC, our volume is a tick count).

---

## The candidates

### A. LOCATION — where the setup sits in the larger move

| # | law | definition | parameter | why it might work |
|---|---|---|---|---|
| A1 | **Higher-timeframe agreement** | M1 side must match the H1 direction | `InpHtfMinutes`, `InpHtfLook` | **TESTED — PASSES as a gate.** DD lower or equal in 8/8 periods, 18% better per trade, beats shipped on searched *and* unseen sets. Fails as a diamond. |
| A2 | **Trend age** | bars since the trend flipped | max age | VSA: a UHV early in a move is a *Jump Across the Creek*; late in an extended move it is a **buying climax** — exhaustion, not commitment |
| A3 | **Retracement depth** | how far the pullback retraced the prior leg | min/max % | a shallow pullback means buyers never let go; a deep one means the trend is in doubt |
| A4 | **Retracement speed** | bars from leg-high to the UHV | max bars | a fast, shallow pullback is urgency; a slow drift is indecision |
| A5 | **Level confluence** | UHV sits within X of a prior swing high/low | tolerance | a level that already mattered once is likelier to matter again |

### B. EFFORT AND RESULT — the VSA core

| # | law | definition | parameter | why it might work |
|---|---|---|---|---|
| B1 | **Effort vs result** | UHV range per unit of volume | min pts/100 vol | **TESTED — mixed.** Helps March (−1.65 → −0.83) but wrecks the live window (+85 → +28). Fails the two-period bar. Worth retrying as a *diamond*. |
| B2 | **Is the UHV genuinely ultra?** | UHV volume ÷ the session's average volume | min ratio | we call it Ultra High Volume but never check it is high *in absolute terms* — only that it is the loudest in a 20-bar window |
| B3 | **Retracement volume drying up** | mean volume of retracement bars ÷ impulse bars | max ratio | classic No Supply: a pullback on falling volume means nobody is selling into it |
| B4 | **Volume slope across the retracement** | is volume declining bar by bar? | boolean | the shape of the drying-up, not just its level |

### C. THE BREAKOUT CANDLE ITSELF

| # | law | definition | parameter | why it might work |
|---|---|---|---|---|
| C1 | **Close position in range** | breakout closes in the top/bottom X% of its own bar | min fraction | **TESTED — inconsistent** in both directions. Retry as a diamond. |
| C2 | **Penetration depth** | how far the breakout body closes beyond the UHV level | min points | a decisive break versus a nervous poke |
| C3 | **Body vs recent average** | breakout body ÷ mean body of last 20 | min ratio | momentum: a large body is commitment |
| C4 | **Freshness** | bars between the UHV and the breakout | max bars | the closer to the UHV, the less the level has been eroded |
| C5 | **Next-bar confirmation** | the bar after the breakout does not close back inside | boolean | VSA's own rule — it costs one bar of entry delay, which must be paid for |

### D. CONDITIONS AT ENTRY

| # | law | definition | parameter | why it might work |
|---|---|---|---|---|
| D1 | **Spread at entry** | refuse when the spread exceeds X | max points | measured mean 0.2014, but it reached 0.56. At a 1-point target a 0.56 spread is 56% of the prize |
| D2 | **Volatility regime** | recent ATR ÷ its own longer average | band | the loss size is what kills us, and loss size *is* volatility. This targets the quantity we know decides everything |
| D3 | **Clustering** | time since the previous setup | min gap | setups arriving in bursts may be one event counted many times |
| D4 | **Quote health** | already shipped in v1.21 | — | **LIVE.** Refuses a stale or drifted quote — this one is a safety law, not an edge law |

---

## How each will be judged

1. **Expectancy per trade**, never win rate.
2. **Both forms**: as a gate (blocks) and as a diamond (sizes). H1 proved these differ enormously.
3. **Kind period AND hostile period** — the live window plus March, minimum.
4. **Then unseen periods** it was never searched on. This is where nearly everything has died.
5. **Drawdown reported alongside**, because a law that halves drawdown at flat profit is worth having.

Priority order by expected value: **D2 volatility regime** (aims straight at the average
loss) → **B2 genuinely-ultra volume** (tests whether our UHV is even ultra) → **A2 trend
age** (the climax idea) → **C2 penetration depth** → **B3 retracement volume** → the rest.

---

# PART 2 — Zee's PDF, "The MT5 Laws of Conviction" (2026-08-16)

He supplied a five-page list. Triaged first, because four of its laws are already in the EA
and two are impossible on this instrument:

| from the PDF | status |
|---|---|
| Body breakout vs wick sweep | **already have it** — `BreakoutIsBar1` requires the BODY to cross |
| Liquidity sweep of prior low | **already have it** — this is Law 1, an existing diamond |
| Low-volume retracement | **already have it** — breakout must be quieter than the UHV |
| Trigger expiration (max bars) | **already have it** — `InpBreakWindow` |
| Micro-delta / positive delta | **impossible** — gold is OTC, no broker publishes delta; ours is a tick count |
| News filter | **not feasible** — the tester has no news calendar |
| FVG / VWAP, distance-to-HTF-level, partial TP | deferred — need level detection or partial-close plumbing |

**Everything below was tested on `ZeeUHV.mq5` — the LIVE EA, magic 88094 — at Zee's
instruction, not on a copy. All new inputs default OFF and the baseline was re-verified
first: 134 trades / 88.06% / +$838.80 / 4,137 bars, identical to the cent before and after
the code was added.**

Real ticks, 163 ms delay, 0.02 lots, stop 5 / hold 5.

| law | LIVE 11-13 | Mar 02-16 | Jun 01-15 | verdict |
|---|---|---|---|---|
| **baseline** | 67 · **+1.27** | 228 · **−1.65** | 368 · **−0.23** | — |
| L1 UHV vol ≥ SMA20 ×1.5 | 12 · −1.03 | 17 · +1.82 | 33 · −0.75 | ✗ 1 of 3 |
| L1 UHV vol ≥ SMA20 ×2.0 | 4 · +2.14 | 3 · +2.75 | 6 · +1.83 | ⚠ **13 trades total — a mirage** |
| L2 UHV range ≥ ATR ×1.2 | 37 · +0.42 | 108 · −0.36 | 162 · −0.83 | ✗ |
| L2 UHV range ≥ ATR ×1.5 | 18 · +0.02 | 43 · +1.41 | 51 · −1.89 | ✗ |
| L3 UHV close pos ≥ 0.4 | no trades | 13 · −0.74 | 48 · −0.62 | ✗ |
| L4 pre-compression ≤ 1.0 | 48 · +0.92 | 126 · −2.19 | 207 · +0.37 | ✗ 1 of 3 |
| L5 pullback ≤ 0.618 | 37 · +1.53 | 143 · −2.35 | 244 · +0.02 | ✗ 2 of 3 |
| **L6 spread ≤ 0.30** | 67 · +1.27 | 192 · **−1.06** | 360 · **−0.22** | ✓ **never worse, better twice** |
| L7 break window 5 | 67 · +1.27 | 228 · −1.65 | 368 · −0.23 | — **inert**, the break is always within 5 |
| **L8 H1 alignment** | 42 · **+1.54** | 105 · **−1.42** | 193 · **+0.12** | ✓ **PASSES** |

### What survived, and what it cost to find out

**L8 — higher-timeframe alignment.** The only law with both a real sample and a consistent
result. Separately validated across all eight periods: drawdown lower or equal in **8 of 8**,
expectancy −0.500 → −0.411, and it beats shipped on the searched set *and* the unseen set.
Use it as a **GATE, not a diamond** — as a diamond it was worse than shipped (−586.72 vs
−559.10 over five periods), because its value is removing bad trades, not sizing good ones.

**L6 — spread ceiling.** Never worse in any period, better in two. It costs nothing in the
live window because the spread there never exceeded 0.30. Cheap insurance against the
0.56-spread moments, which on a 1-point target would eat 56% of the prize.

**L1 is the cautionary tale.** 100% win rate in three separate periods looks like the find of
the week — on 4, 3 and 6 trades. Loosen it to ×1.5 so the sample triples, and it fails in two
of three. **A law is not tested until it has enough trades to be wrong.**

**L7 is a free lesson.** Identical results at 5 and 12 means the breakout, when it comes,
always comes within five bars. That parameter can never matter, and now nobody needs to
sweep it again.


---

# PART 3 — Wyckoff/VSA composite (Zee's 2nd PDF), and why L1 became a DIAMOND

Zee pushed back on my calling L1 a mirage: *"if its so good that it has a 100% winrate then
why not?"* He was right, and the correction matters more than the result.

### The arithmetic I should have shown first

L1 (UHV volume ≥ SMA20 ×2.0) won **13 of 13**. At our baseline win rate of 88.06%, thirteen
wins in a row happens **19.1% of the time by pure luck**. One run in five. That is not
evidence of an edge — but nor is it evidence against one. It is simply too few trades.

### But his conclusion was better than mine

As a **GATE** L1 discards 95% of trades (67 → 4) on the strength of 13 observations —
reckless. As a **DIAMOND** it blocks nothing and only sizes up when it fires, so a false
signal costs almost nothing while a true one pays. **The asymmetry is entirely favourable,
which is exactly why a thin signal belongs in a diamond and never in a filter.**

Measured, and it improves **all three periods**:

| | LIVE 11-13 | Mar 02-16 | Jun 01-15 |
|---|---|---|---|
| baseline | 67 · +1.27 | 228 · −1.65 | 368 · −0.23 |
| **L1 as DIAMOND ×2.0** | 68 · **+1.28** | 229 · **−1.63** | 369 · **−0.22** |

Total gain **+$7.36** across three periods — safe, positive, negligible in size because it
fires on one or two setups per period. The method is what matters, not the amount.

### The new Wyckoff laws

| law | LIVE 11-13 | Mar 02-16 | Jun 01-15 | verdict |
|---|---|---|---|---|
| **Squat** (range < ATR ×1.0) | 24 · **+2.36** | 87 · −3.37 | 122 · −0.28 | ✗ great here, catastrophic in March |
| Squat (range < ATR ×0.8) | 4 · +2.35 | 43 · −4.67 | 63 · +0.75 | ✗ |
| Next-bar fails to extend | 29 · +0.59 | 120 · −2.44 | 223 · +0.10 | ✗ |
| **Climax** (widest of 60) | 4 · +2.14 | 8 · −1.21 | 3 · +2.08 | ⚠ better in all 3 on **15 trades** — diamond only |
| **PTS** (brk vol ≥ 0.8×UHV) | 45 · **+2.14** | 132 · −2.31 | 242 · −0.35 | ⚠ **100% on 45 trades here** — see below |

### Two genuine contradictions worth keeping

**PTS vs Zee's own rule.** His rule: the breakout must be *quieter* than the UHV. Wyckoff's
Push Through Supply: it should be a *loud* green bar cutting through. Requiring loud gives
**100% on 45 trades** in the live window — and 45 straight wins is a **0.33%** coincidence,
not 19%. That is a real effect *in that regime*. It fails in March and June, so it is
regime-dependent rather than wrong. A strong diamond candidate.

**Squat vs effort-vs-result.** Wyckoff's squat wants a NARROW spread on high volume (buyers
and sellers matched order-for-order). The effort-vs-result law wants a WIDE one. Both cannot
be right, and the measurement says each wins in a different regime.

### The rule this session produced

**A thin or regime-dependent signal goes in as a DIAMOND, never as a GATE.** A gate acts on
every trade it removes; a diamond acts only on the trades it marks. When the sample is small
or the effect is regime-bound, that difference is the whole risk.
