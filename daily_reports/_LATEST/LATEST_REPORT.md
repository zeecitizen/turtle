# POST-MORTEM — 6 months, $0 profit. The honest document.

> **Date:** 2026-07-21
> **Author:** Claude (laptop session, Opus 4.8), with Zeeshan.
> **Purpose:** Break the hallucination. This is the sober, receipt-driven account
> of WHY six months of work never produced a single profitable day. Any Claude
> (laptop, VPS, future model) MUST read this before touching the strategy again.
> No hype. No "next version will fix it." Only what the receipts show.

---

## 0. The brutal fact

- **Duration:** ~2026-02 → 2026-07 (6 months).
- **Result:** **$0 net profit. No overall profitable day.** Recent live run
  (VPS Blueberry, 2026-06-29 → 07-01): 9 trades, 66% WR, **net −$177**. Then the
  VPS stopped (unpaid) and it went silent for 20 days.
- Zeeshan is an MIT software engineer. His cousins mock him: "he can't even build
  one EA." **This document exists to prove the failure was a specific, fixable
  methodology error — not incompetence, and not a fake strategy.**

## 1. The strategy is REAL

Feb 11, 2026 (Blueberry-Live02, account 5118408, **real money**): **69 trades,
65W / 4L = 94.2% WR, net positive.** This is not a backtest. It happened. The
edge is real. The question was never "is the strategy real" — it was "why can't
we reproduce it mechanically."

## 2. The root cause (three independent investigations converged)

> **The 94% was a property of the EXIT, not the ENTRY. We spent six months
> perfecting the ENTRY and never faithfully built the EXIT.**

### 2a. What the Feb 11 receipts actually show (measured 2026-07-21, first time ever)
Every trade had **NO S/L and NO T/P set** — all opened and closed **by hand**.
- **Winners RAN:** held to large moves. Big ones +$50–$55 on 0.1 lot ≈ **+6 points**
  (17:02 basket +$153, 17:49 basket +$157). Small scalps +$5–$17.
- **Losers were CUT tiny:** the only 4 losses were −$0.76, −$1.43, −$1.51, −$1.60.
  Biggest loss of the whole day = **−$1.60**. Biggest win = **+$54.93**.
- **Positions were STACKED** (2–4 lots per signal) and **closed as a basket at one
  instant** (all of 17:02 closed 17:03:51; all of 18:41 closed 19:06:41).
- **No fixed target.** Profit ranged +$0.17 → +$54.93. He exited when the
  **momentum stalled/reversed**, judged by eye — not at a number.

**The insight that makes it click:** the 94% WR and the asymmetric R:R are the
SAME thing — both produced by the discretionary exit. Cutting a would-be-loser
near breakeven keeps it out of the "loss" column (raises WR) AND keeps losses
tiny (fixes R:R). Letting winners run creates the big average win. Entry is
ordinary; **the exit is the entire edge.**

### 2b. What we actually built for 6 months
- **Era 1 — TradingView Pine indicator** (Feb → early May): UHV breakout signals
  via PineConnector. Hit platform limits; signal-vs-fill parity never trustworthy.
- **Era 2 — Python backtests** (May): glowing numbers ("+$8079/18d", "94% WR",
  "85.6% WR") that **never reproduced live**. Birth of the doctrine
  *"all backtests hallucinate."*
- **Era 3 — native MQL5 EA** (May 12 → now): S1Trader family. Still oscillating
  between over-strict (fires nothing / all-MISS) and over-loose (~50% noise).
  Never closed successfully.

Across all three eras the effort went into **ENTRY DETECTION** — dozens of gates
(HHHL, H1Bias, slow-trend, big-spread-climax, UHV body/color/global-max, sweep,
FVG, volume-source). Most tested negative or redundant.

### 2c. We even DIAGNOSED this correctly once — then threw it away
- **2026-05-22 commit:** *"Feb-11: gap is ENTRY TIMING, not exit"* and *"Zee's
  entry + mechanical exit is walk-forward robust."* → abandoned in the next rewrite.
- **v2.84 (2026-06-18):** stripped all auto-exits, implemented "master takes exit
  manually" (catastrophe SL only, human closes). → reverted within days back to a
  fixed 1.3pt TP.

This is **the rediscovery loop**: progress → failure → abandon prior learning →
rewrite → repeat. Six months, three rewrites, the one correct finding erased each time.

## 3. The current live EA is the EXACT INVERSE of Feb 11

v3.02 (live config): **`InpTPPoints = 1.3`** (winner capped at 1.3pt),
**SL = UHV-extreme ± 2pt** (loser runs 2–6pt), trail/BE/auto-close all **0 / off**.

| | Zee (Feb 11) | EA (v3.02 live) |
|---|---|---|
| Winner | runs to ~6pt | **capped at 1.3pt** |
| Loser | cut ~−1.5pt | **wide 2–6pt** |
| Realized R:R | ~10:1 for | ~0.3:1 against |
| Result | +$800 day | −$177 |

And every exit that ever "backtested well" won by **capping winners** (e.g.
`trail_18_4` = 100% WR +$163 by capping each winner at ~$27). The machine kept
optimizing toward the WRONG behavior because it was tuned to **capture-WR, not P&L**.

## 4. The two doctrine traps

1. **"Take all chances, filters off, trash hides gems."** Adopted to stop
   overfitting. But firing on every UHV 24/7 is mathematically ~50% coin-flip —
   the OPPOSITE of a selective 94% day. This doctrine, meant to help, guaranteed
   regression to noise. **Selectivity is not the enemy; overfit backtests were.**
2. **"94% is repeatable every day."** It is NOT. Feb 11 was also a strong
   trending/high-range regime. Honest achievable target = **positive expectancy**
   (even 60–65% WR) with the RIGHT R:R. At Zee's real R:R, 65% WR is very profitable.

## 5. THE FIX IS ASSEMBLY, NOT INVENTION

Every piece needed already exists in the codebase — they were just never combined
into ONE coherent exit for the UHV strategy:
- **Basket close** — `grab_command.txt` / GRAB (`S1Trader.mq5` ~:2747).
- **Momentum-stall exit** — `MIDTRADE_DECEL` (`ShanoExitManager.mq5` ~:1287).
- **Impulse-death exit** — `CDD_DIV` cumulative-delta divergence (`ShanoExitManager.mq5` ~:1251).
- **Manual-exit + catastrophe-SL skeleton** — v2.84 (`S1Trader.mq5` ~:314).
- **Correct RATIO already** — sniper `SL15 / TP52` pips ≈ 1.5pt cut / 5.2pt run.

## 6. THE NEW METHOD (the loop-breaker rules)

1. **Entry is FROZEN.** It is good enough (66% WR = decent entries). We do NOT
   touch detection/gates anymore. No more entry rewrites.
2. **All effort on EXIT**, assembling the pieces above into one mechanism:
   - Loser **hard-cut ~1.5pt**.
   - Winner **late-arm, wide-give-back trail** (arm ~+3–4pt, give back ~1.5–2pt) —
     let it RUN; TP is only a runaway ceiling, not the primary exit.
   - **Basket** momentum-stall close for stacked fires.
   - Human override + catastrophe SL retained.
3. **Success = LIVE P&L only.** Not WR. Not backtest. Not dashboards. Not "signals
   detected." The only question each day: *did the account close green?*
4. **Claude will refuse the "next version will fix it" reflex.** If a change isn't
   validated on full P&L across many days of real ticks, it is a hypothesis, not
   progress. Report footers already say: *"NOT progress unless it documents a
   positive P&L day."*

## 7. Where things physically are (2026-07-21)
- Trading moved laptop → VPS (2026-06-27) → but **VPS is down (unpaid)**. Zee is
  now running on the **local laptop** (farmhouse, 24/7). Blueberry open locally.
  Terminal GUID `DBE9B8B347D025DD139E103EE3B63FD8`.
- EA `S1Trader.mq5` v3.02, compiled, identical to repo. Magic 88005, 0.30 lots.
- Next concrete step: assemble the Feb-11 exit (§5/§6), validate on real ticks P&L.

---

*This document is the antidote to the hallucination. If a future session finds
itself adding another entry filter or celebrating a backtest WR, STOP and re-read
§2 and §6. The edge is the exit. Validate on P&L. Save the mother. — 🤍*
