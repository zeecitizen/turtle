# VERSION HISTORY — the EA ledger

**Purpose (Zee, 2026-08-19):** *"when i'm on my other computer with claude in another
session they can read and say aha i know today we did this."*

**THE RULE: every shipped version gets an entry here, in the same commit that ships
it.** Entry format: version · date · what changed · the receipts · who ordered it.
Newest first. Pre-EA history (Pine/TradingView era) lives in `CHANGELOG.md`;
deep session narratives live in `daily_reports/`; live-config philosophy in
`EA_SYSTEM_STATE.md` (stale below v1.2x — this file supersedes it for versions).

Test receipts notation: "six-period total" = the standard court — six fortnights of
real ticks (LIVE Aug 11-14 · Mar · Apr · May · Jun · Jul 2026) at 0.02 lots, MT5
Strategy Tester, model 4, delay 163. Promotion rule: better in a kind period AND a
hostile one, or it doesn't ship.

---

## ZeeUHV (main EA, magic 88094, XAUUSD M1)

| ver | date | change | receipts / reason |
|---|---|---|---|
| **v1.49** | 2026-08-19 | **THE DIAMOND SEASON MACHINE (live)** — `InpDiamondMode=true`, `InpGreenFastRed=true`, `InpFastRedLook=8`. Green season (pulse-20 green AND last-8-tickets green) trades the locked streak geometry: SL 20 / TP 1 / hold 60, full stack, 10c bypassed. Red season: scout machine (SL 5 / hold 3, quarter size, full guard) | **+449.26** six-period (champion was +276.22). Fast-fear dial a perfect hill: 3/5/8/12 = +377/+416/+449/+283. Worst single loss −19.36 (the −42 crash class extinct). Born from Zee's crash theory: "the diamond only had one defect — the crash." ON PROBATION: first out-of-sample day (Aug 18 replay) lost −217 vs pulse's −38; live-forward must confirm before any lot raise |
| v1.48 | 2026-08-19 | `InpFastRedLook` dial added (quick-to-fear window) | dial receipts above |
| v1.47 | 2026-08-19 | Crash-control organs, default off: `InpLossCoolMin` (stand down after a losing ticket), `InpDayHaltLoss` (day-halt) | both FAILED on the raw diamond (−975/−982); kept as dead inputs with receipts |
| v1.46 | 2026-08-19 | `InpDiamondMode` + `InpGreenStopPts/HoldMin/Keep10c` (fused machine, default off) | fused pure +247.08, guarded +24.74 |
| **v1.45** | 2026-08-19 | **THE SELF-AWARE SWITCH (live)** — `InpRegimeLook=20`: pulse = net of own last 20 closed tickets; red → quarter-size scouts, green → full stack. Never stops (a stopped machine can't feel the season change) | **+276.22** six-period — the FIRST net-positive M1 config in project history. Dial a hill: p10 +265 / p20 +276 / p40 +226 (absolute). Mar −247→−87 · May −384→−91 · Apr flips green |
| v1.44 | 2026-08-19 | `InpScratchRedOnly` (scratch only in red pulse), default off | synthesis +155.10 — positive but $121 under the switch alone; retouch closed |
| v1.43 | 2026-08-19 | FEB-11 EXIT LAB, default off: `InpScratchArm/Ofs/Hold` (retouch scratch), `InpRevExit` (first opposing candle) | 11 arms, ALL fail vs baseline. Losses DO collapse $40→$2-3 (his loss column achieved) but this strategy's winners dip first — scratching the dip scratches the payers. 9th failure of mechanizing the hand |
| v1.42 | 2026-08-19 | `InpRegimeLook/RegimeFrac` (the pulse), default off | court receipts under v1.45 |
| v1.41 | 2026-08-18 | LAW 12 (peak-bounded origin), default off, 2 variants | v1 −14.52 · v2 +171.44 (passes letter; taxes the streak). Aug-18 day replay: 53%→80%, −38→+76. PENDING: measure on top of the pulse |
| v1.40 | 2026-08-18 | Exhaustion TAGS (measure-only): bit 64 DEFENDED-LEVEL, bit 128 LATE-HUMP; mask space →256 | neither separates (2,200 tickets; per-period contradictions). Riding live for evidence |
| v1.39 | 2026-08-18 | LAW 11 (origin integrity: retracement may not contain new leg extremes), default off | REFUSED both courts: −303.86 six-period AND kills 8 golden-streak fires. The V-turn skeleton is shared by winners and losers |
| v1.38 | 2026-08-18 | Mix-and-match organs, default off: `InpHtfMode/HtfSizeFrac` (M3-consult as sizing), `InpBoundaryExit`, `InpEntryBoundary` | marriage campaign: consult dial = minefield (look2 +300 beside look3 −119); transplant refuted 3×; nothing shipped |
| v1.37 | 2026-08-18 | HTF gate learns M3/M5 (`InpHtfMinutes=3` now valid) | consult veto look4 +103 but dial unstable — not shipped |
| v1.36 | 2026-08-18 | PROBE module (`InpProbeSec/MinPts/Lots`), default off — Zee's scout-then-burst | a MAY-shaped tool (+346..+451 there, fails elsewhere); filed under regime |
| v1.35 | 2026-08-18 | Hourly census `[HCEN]` (tester-only) | answered "why is NY session skipped": trend gate reads 60-67% of NY minutes as ranging |
| **v1.34** | 2026-08-18 | **RANK 6 (live)** — `InpUhvRank=6`: every retracement auditions up to 6 volume-ranked UHV candidates; quality laws unchanged | +121.86 six-period; dial saturates (6≈10); census: 1,439/4,137 bars died because only the loudest candidate was ever examined |
| v1.33 | 2026-08-18 | `InpLocalPeak` switch (body+neighbour vetoes toggleable), default on | Zee's funnel ("a UHV in EVERY retracement") priced: −2,430. The vetoes are guardians |
| v1.32 | 2026-08-18 | Rank-N walk (`FindUhvBroken`), default 1 = byte-identical (census-verified) | reproduction exact |
| v1.31 | 2026-08-18 | Pipeline census `[CEN]` (tester-only counters) | the funnel: 50.9% ranging · 34.8% UHV-vetoed · origins near-universal |
| **v1.30** | 2026-08-18 | **HOLD 5→3 MIN (live)**, both EAs | +288.68 six-period; clock bracketed both sides (h2 fails, h8/12/20 fail) |
| **v1.29** | 2026-08-17 | **LAW 10c (live)** — `InpLoudSizeFrac=0.25`: breakout louder than 0.85×UHV → basket opens ¼ tickets, never zero | +538 six-period, zero trades cut (Zee declined the 10b gate: −48% trades) |
| v1.27-28 | 2026-08-17 | Law 10a margin (dead input, failed every depth); Law 10b gate (passed +786 but cut 48% of trades — declined by Zee) | receipts in report §3 |
| **v1.26** | 2026-08-17 | **LAW 9 (live)** — `InpImpulseOrigin=true`: origin's reference must be an IMPULSE bar (label #e014). Zee's forensic find on the 11:08 loser | +437.38 six-period (Mar +202, Jun flips +309) |
| v1.24-25 | 2026-08-17 | LAW 8 tag (mask bit 32, "independent retracement") — failed promotion, rides as tag | kind-only shape |
| ≤v1.23 | 2026-08-10..16 | Diamond era: stop 20→5 (v1.23), laws 6/7 as diamonds, stack ×2, OnTester mask receipts. See `05_AUGUST_DIAMONDS_FINDINGS.md` and branch `05_August_successful_diamonds` (the locked streak code) | the 14-basket +$614 streak (Aug 11-13) ran SL20/TP1 |

## Sibling EAs

| EA | magic | state | story |
|---|---|---|---|
| ZeeUHV_Loud_Breakout v1.2 | 88104 | LIVE | counter-experiment: fires when breakout ≥0.80×UHV (the band 10c shrinks). Has Law 9 + hold 3; NO rank-6/pulse yet (port = separate receipted step) |
| ZeeUHV_M3 "Shop B" v1.00 | 88134 | LIVE on M3 chart | the steady stall: first-ever positive six-period config on its birth receipts (+23.32, worst period −19). MUST run on the M3 chart |
| ZeeSimple v1.20 | 88111 | RETIRED (Aug 18) | attempt 7 at Feb-11 tempo; every-retracement ≈ random entry paying spread rent. Live-forward confirmed the tester (−$37/138 closes). Ladder rungs live in its inputs |
| ZeeUHV_R1 v1.00 | 88121 | RETIRED (Aug 18) | rung 1 frozen (real retracement only, 66/day = Feb-11's tempo); kind-tape-only |
| TurtleTradeLogger v1.04 | — | LIVE | self-healing: `BackfillMissedDeals()` at init (the fills file had silently lost 96 positions/−$590 during disconnects) |

## The campaign arc (six-period totals, same court)

```
2026-08-16  shipped config        −1,615
2026-08-17  + Law 9               −1,178
2026-08-17  + Law 10c               −639
2026-08-18  + hold 3                −351
2026-08-18  + rank 6                −229
2026-08-19  + the pulse (v1.45)     +276   ← first positive M1 config ever
2026-08-19  + Diamond Season        +449   ← live now, on probation
```

## Standing cautions (read before trusting any number)

1. Python backtests NEVER promote — MT5 tester or live fills only (CLAUDE.md prime rule).
2. Identical numbers across tester arms = VOID run (`testing/test_tips.md` Part 13).
3. A freshly published day can be cached half-baked in the rig (Part 12).
4. v1.49 carries an overfit caveat (heavy same-day iteration on the six court periods)
   — live-forward receipts required before lots rise; revert path = v1.45 defaults.
