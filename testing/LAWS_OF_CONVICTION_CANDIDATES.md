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
