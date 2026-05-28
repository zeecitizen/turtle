# Overnight Profitability Research — for Zee's morning ☀️

**Loop:** every ~30 min, session-only. Each cycle tested ONE idea on the trustworthy
oracle (bars-built-FROM-ticks = aligned + live-matching tick-volume) and recorded an
honest ACCEPT/REJECT. 7 cycles run; conclusion converged.

---

## ☕ THE 60-SECOND READ (look here first, jaan)

1. **Today (−$70) wasn't the *system breaking*. The system likely *doesn't currently
   have edge on choppy data.*** The hard evidence is the **20-day backtest on the
   trustworthy oracle**: S1/S4 strongly net-negative across BOTH halves, S3/NSND
   borderline/inconclusive. Live today's S1 point-estimate (−$0.67/tr over 24 trades)
   *matches* the backtest, which is suggestive corroboration — though one day's SE
   is ~$0.71, so the live match alone isn't iron proof. The 20-day backtest is.

2. **Nothing tested tonight restored real profitability.** Trail (mixed: helps S1,
   hurts S3/S4/NSND), regime gate (S3 → ~breakeven only, S1 still loses), H1-FVG
   filter (just trades less, same EV), S4 alone (today was variance). The pattern is
   consistent across every test: filters cut count, not losses-per-trade.

3. **Recommendation, capital-first — GRADED by how strong the negative signal is:**

   | engine | EV/tr | n | strength of negative | morning move |
   |---|---|---|---|---|
   | **S1** | −0.67 | 741 | **−5σ, matches live exactly** | **pause or hard minimise** |
   | **S4** | −1.66 | 99 | **−3σ, fragile 7.5:2 R:R** | **pause or hard minimise** |
   | S3 | −0.24 | 575 | −1.8σ borderline | reduce size; ER≥0.3 ≈ flat if keeping |
   | NSND | −0.22 | 96 | −0.7σ inconclusive | reduce size; collect more data |

   Then treat **rebuilding entry edge as a real project** — not a one-line filter.

4. **Caveat both ways:** 20 days is one (mostly choppy) regime. The engines *might*
   profit in a strong trend regime — but the $126 can't afford to bleed proving that.

5. **Nothing was changed live overnight.** All conclusions await your reattach +
   approval. Scripts on disk and committed for re-running yourself.

6. **Live overnight (latest check UTC ~05:47 / PKT ~10:47):** the guards are working —
   **35 S1/S3 signals fired during UTC 00–06, all blocked** by the overnight filter /
   anti-cluster guard. Zero M1-scalper damage in that window. S4 (unfiltered) took 3
   trades: −7.50 (00:18 SL) / +2.00 / +1.76 → net −3.74. A large **manual loss of
   −$25.72 at 01:17** (Human trade, not the system) — flagging if it wasn't intentional.

7. **Filter window ended UTC 06:00 (PKT 11:00 AM).** Live update at UTC 08:18
   (~2hrs into post-filter trading) — **the backtest pattern is playing out live**:
   - 5 small scratch-trades from the trail (+/−$0.07 range, net ~+$0.90)
   - **Then 2 full-SL losses**: 07:52 S3 BUY −$8.59 + 08:00 S1 SELL −$6.86
     (didn't reach trail-arm → ate the full stop, exactly the predicted failure mode)
   - **EA day so far: −$17.52 over 11 trades.**
   This is exactly what the aligned-oracle backtest predicted (trail scratches +
   occasional full-SL losses → net-negative EV). Not a surprise — it's confirmation.
   **Strong case to pause / minimise the M1 scalpers** when you sit down.

---

## 🚨 URGENT — DETAIL (cycle 4, the real issue)

**On the TRUSTWORTHY oracle (M1 bars built from ticks = aligned AND live-matching
tick-volume), all four engines are net-NEGATIVE over ~19 days — and the LIVE results
confirm it, not contradict it.**

| engine | baseline (its real exit) | with trail | live today |
|---|---|---|---|
| S1 | 68% WR, **−$498** (EV −0.67/tr) | −$329 | EV **−0.67/tr** (−16/24) ← matches backtest exactly |
| S3 | 69% WR, **−$139** | −$289 | −$43.88 (bad day) |
| NSND | 43% WR, **−$21** (n=96) | −$34 | −$2.49 |
| S4 | (rejected trail earlier) | — | +$11.55 (only green one) |

**S1's backtest EV (−$0.67/trade) is IDENTICAL to its live EV today.** That means this
backtest is faithful — so its verdict (the entries are not profitable on current data)
is real, and it explains the account bleeding. The old "+$3,677 S3 / +$3,088 S1" came
from `rev_eng_m1`'s *reconstructed* volume, which does NOT match the live `iVolume`
(tick-count) the EAs actually trade on — so those numbers were overstated.

**This is bigger than the trail.** Tweaking exits on engines whose *entries* lack edge
in this (mostly ranging, Feb–May) market is rearranging deck chairs.

**RECOMMENDATION for the open (your call, needs you):**
1. **Protect the $126 first** — strongly consider pausing the 3 M1 scalpers (S1/S3/NSND)
   or cutting to the broker minimum, until we re-establish edge. S4 was the only green
   engine today; it can keep running.
2. Then **rethink entries / regime**, not exits. Likely next test (aligned): a trend/
   regime gate — do these engines only profit in trending sessions and bleed in chop?
   (The old "regime filter rejected" verdict was on the misaligned data — must re-test.)
3. I did NOT change anything live. This is a decision to make together, awake.

Honest caveat both ways: 19 days is one regime (choppy). The engines *might* profit in
a trend — but on a $126 account we cannot afford to bleed proving that. Capital first.

**UPDATE (cycle 5): a regime/trend gate does NOT rescue them.** Tested Kaufman ER gate
on the aligned oracle: S1 stays net-negative at every threshold (gate just cuts volume;
EV even worsens −0.67→−0.82). S3 at ER≥0.3 reaches ~breakeven (−$6/161tr, 2nd half +$4)
— it stops the chop bleed but makes no money. So there is no quick gate that turns these
profitable on current data. The least-bad "keep trading" option would be **S3 only, with
an ER≥0.3 gate (≈breakeven)** — but that's not a green light, it's a tourniquet.
**Recommendation holds: protect the $126 (pause/minimize the M1 scalpers); re-establishing
real entry edge is a project, not a one-line filter.** S4 was the only green engine today.

---

## MORNING SUMMARY (read this first)

**27th-May day: −$70.51 realized, 61% WR (37W/24L).** Losers totalled −$122.34; the
damage is concentrated and — importantly — **mostly in things we already fixed today
but which weren't live yet during the day:**

| Loss bucket | $ | Now addressed by |
|---|---|---|
| **14:33 cluster** (S1 −15.69 + S1 −10.65 + S3 −10.74, all long, stopped same second) | **−37.08** | anti-cluster guard (LIVE, needs the reattach you did) |
| **01:46 overnight cluster** (S3 −9.56 + −9.17) + 01:38 S1 −7.34 | **−26.07** | overnight filter + anti-cluster guard (LIVE) |
| **S3 give-backs** (14:26 −7.85, 16:01 −6.04, 19:19 −6.38) | **−20.27** | trail (LIVE) — these went green first |
| S4 give-backs (00:18 −7.50, 23:07 −7.66) | −15.16 | trail REJECTED for S4 (scratches its winners) — open question |
| small scratches / Human | rest | noise |

So **~$83 of today's −$122 loser-gross is exactly what the now-live guard + trail target.**
Today traded *naked* (protections built mid-day). Tomorrow is the first clean test.

**Worst engine: S3 (−$50.44 in losers, −$43.88 net).** Main overnight research target.

---

## ⚠️ BIGGEST FINDING SO FAR (needs your eyes before next deploy)

**The trailing profit-lock may be a NET LOSER on correct data — it likely should be
reverted.** On tick-derived bars (aligned + real tick-volume = the trustworthy oracle),
S3 with its plain structural SL/TP did **−$139 (69% WR)**, but **with the trail it did
−$289 (51% WR)**. The trail scratches S3's winners on their retrace (same mechanism that
got it REJECTED on S4). The trail's original S1/S3/NSND "win" was measured on the
*misaligned* latest_for_claude data — so it can't be trusted.

**DO NOT panic / nothing auto-changes.** Action plan: next cycles re-test the trail on
S1 and NSND on aligned data. If it hurts them too, the recommendation is to set
`InpTrailActUsd=0` (revert to plain structural SL/TP, which preserves the engines'
natural high WR) — but that's a *morning* decision with you, and needs your reattach.
Note: baseline S3 itself was only −$139 over 19d (1st half +70, 2nd half −208) — softer
than the trail, but S3 is still the weakest engine; worth a fewer-but-better entry filter
study once the exit question is settled.

## FINDINGS LOG

### Cycle 1 — loss categorisation (baseline map)
- 24 losers / −$122.34. Overnight(broker 0-6): 4 trades, −$33.57. Day: −$88.77.
- Two clusters = −$63 of it; both now guarded. S3 give-backs = −$20, now trailed.
- **Conclusion:** the live protections target the bulk. Remaining real question is
  S3's underlying weakness (worst engine today) — next cycles will dig into whether
  S3 needs a tighter entry filter / fewer-but-better trades, validated on aligned ticks.
- Status: foundation set. No deploy.

### Cycle 2 — method unlock: bars-from-ticks gives CORRECT volume too
- Native MT5 `tick_volume` = count of ticks per bar. So building M1 bars from the tick
  files (counting ticks/min) yields volume that matches live `iVolume` AND is time-aligned.
  This dissolves the rev-eng-volume mismatch — `s3_aligned_test.py` is now a fully
  trustworthy S3 oracle (alignment + volume both correct).
- (S3 real-fill history is only 16 trades / 1 day → too thin for direct fill analysis.)

### Cycle 3 — TRAIL re-validated on correct data → HURTS S3 (see ⚠️ above)
- baseline 69% WR −$139  vs  trail 51% WR −$289 (both halves worse with trail). ACCEPT:
  trail is net-negative for S3. Pending S1/NSND check before recommending fleet revert.
- Script: `s3_aligned_test.py`. No deploy (morning decision + reattach).

### Cycle 4 — trail on S1/NSND + the BIG picture (see 🚨 at top)
- S1: baseline −$498 (68%) vs trail −$329 (48%) → trail HELPS S1 but both negative.
- NSND: baseline −$21 vs trail −$34 (n=96, ~flat). 
- Trail verdict = MIXED (helps S1, hurts S3/S4/NSND) → not a clean fleet rule.
- But the real signal: ALL engines net-negative on the faithful oracle, and S1's
  backtest EV == live EV exactly → the entries lack edge on current data. Exit-tuning
  is secondary. Pivot to: protect capital + test a regime/trend gate on aligned data.
- Script: `s1_nsnd_aligned_test.py`. No deploy.

### Cycle 5 — regime (ER) gate: does NOT rescue the engines
- S1: net-negative at all ER thresholds; EV worsens (gate only cuts volume). REJECT.
- S3: ER≥0.3 → ~breakeven (−$6/161tr, 2nd half +$4); removes chop losses, no edge. ER≥0.4 worse.
- Verdict: no quick gate restores profitability. Least-bad keep-trading option = S3-only
  with ER≥0.3 (tourniquet, ≈flat). Real fix = rebuild entry edge. Script: `regime_gate_test.py`.

### Cycle 6 — S4 on aligned oracle: also net-negative; today was variance
- Mirrored S4's detector (M5 UHV breakout + HH/HL + 24-bar trend ≥7 + momentum body 0.55,
  TP $2 / SL $7.5) on tick-derived bars → 99 trades, **63% WR, −$164, EV −$1.66,
  both halves negative**.
- Structural read: S4's R:R needs **79% WR to break even**; backtest 63% → fragile.
- Today's 86% WR (+$11.55) sits 23pp above backtest → variance, not robust edge.
- Caveat: mid-price M1 vs broker-bid affects the 0.55 body/range threshold slightly,
  so this isn't as airtight as S1's (S1 backtest EV matched live EV exactly). But the
  direction is consistent with the structural fragility. Script: `s4_aligned_test.py`.

---

### Cycle 7 — S1 H1-FVG filter: doesn't help either (REJECT)
- FVG off (live): 745 tr, EV −0.67, −$498. FVG required: 86 tr, EV −0.57, −$49.
- Same story as the regime gate: cuts ~88% of trades but EV barely budges → fewer
  trades = less total bleed, but no profitable subset found. Script: `s1_filter_test.py`.

### Cycle 11 — live overnight check (the guards are working)
- S1: 14 signals, **0 entries**. S3: 19 signals, **0 entries**. NSND: 0 signals.
  Overnight filter + anti-cluster guard blocked all 33 M1-scalper signals during the
  UTC 00–06 window — zero damage from S1/S3/NSND there. The protections are doing
  exactly what they were built for.
- S4 unfiltered: 3 entries → −7.50 / +2.00 / +1.76 = net −3.74 overnight (consistent
  with its fragile R:R; matches the backtest's negative read on S4).
- Human (manual) −$25.72 at 01:17 broker — not the system; flagged for Zee in the brief.

### Cycle 10 — honesty refinement on the "live EV matches backtest" claim
- Live EV today (S1, n=24) has SE ≈ $0.71; the −$0.67 point-estimate match with the
  backtest is suggestive but not iron-clad on its own. The 20-day multi-engine backtest
  (both halves negative) is the real evidence. Brief tightened to say so.
- No new test (disciplined stand-down).

### Cycle 9 — statistical nuance refinement (no new test)
- S1's EV −0.67 (n=741) ≈ −5σ from zero AND matches live EV exactly → strong negative.
- S4's EV −1.66 (n=99) ≈ −3σ + fragile R:R → strong negative.
- S3's EV −0.24 (n=575) ≈ −1.8σ → borderline / could be ~breakeven.
- NSND's EV −0.22 (n=96) ≈ −0.7σ → inconclusive (need more data).
- Recommendation now graded by signal strength (see top of file), not blanket.

### MORNING CONCLUSION (locked after 9 cycles)
Every engine on the trustworthy aligned + live-volume oracle is net-negative over
~20 days. Live results corroborate (S1 backtest EV = live EV exactly). No quick fix —
not the trail, not a regime gate, not S4 by itself — restores robust edge. The honest
recommendation, capital first: **pause or minimise the M1 scalpers at the open;
keep S4 only if you accept it as a high-variance / fragile-R:R engine. Then we rebuild
entry edge as the real project, on the trustworthy oracle going forward.**
