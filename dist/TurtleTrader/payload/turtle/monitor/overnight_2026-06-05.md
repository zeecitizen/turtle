# Overnight Iteration Journal — 2026-06-05

**Zee asleep. Mission: refine S1Trader until winrate matches his Doha/Feb 11 numbers (94%+).**
**15-min wakeups via ScheduleWakeup. Goal: when Zee wakes, give him a working v2.X with proven WR.**

---

## Starting state (handoff)

### EA: S1Trader v2.59 LIVE on Blueberry
- Magic 88004, runtime config in `Common\Files\s1_runtime_88004.json`
- Active gates:
  - `require_h1bias=true` (validated FTMO 15d: -$39.62 → +$120.21, PF 0.92→1.31)
  - `momentum_override_enabled=true`, threshold 5pts (NEW v2.59)
  - `require_hhhl_m5=false`, `require_hhhl_h1=false`
- Visualization features:
  - UHV box (outline only, exactly 1 M5 candle wide)
  - UHV / BREAKOUT paired arrows + sequence numbers (#N)
  - Per-candle volume labels
  - **NEW: faded MISSED markers** when a breakout level was crossed but EA didn't fire — labels the blocking gate

### Diagnosis of last-tested missed entry (UHV #6 at 23:50, Jun 3)
- Big down candle at 23:27 broke UHV.low ($4437.60 → $4435)
- EA didn't fire until 23:50 at $4431.43 — **6 dollars too late**
- Cluster guard was NOT the blocker (last SELL #10 closed at 20:09:31)
- Most likely: **slow trend filter** (`IsDowntrendM5`) wanted 2-hour close-delta > $7
  - At 23:27 the 2-hour delta was probably only ~$6 — gate failed silently
  - At 23:50 the delta finally crossed $7 → EA fired
- **v2.59 momentum override should fix this**: if 30-min close-delta > 5pts, bypass slow trend

### Open questions / known weaknesses
1. Does momentum override degrade WR on choppy days? (need backtest)
2. What's the OPTIMAL momentum threshold? (5? 4? 7?)
3. Are there other silent gates blocking valid setups? (missed markers will reveal)
4. Can we add lesson02 elements not yet implemented?
   - Momentum-body breakout candle check (hard with live tick — needs candle close)
   - Low-volume breakout candle check (same problem)
   - FVG mitigation requirement (currently optional, default OFF)

---

## Iteration plan

| Step | Action | Output |
|---|---|---|
| 1 | Read lesson02 + lesson06 transcripts to identify any MISSING strategy components | Decision: add another quality gate? |
| 2 | MT5 Tester: baseline v2.59 24h (2026-06-03 to 04) — confirm momentum override produces sensible results | Trade count, WR, PF |
| 3 | MT5 Tester: v2.59 48h (Jun 2→4) | Same metrics, validate consistency |
| 4 | MT5 Tester: v2.59 1-week (May 28→Jun 4) | Decisive comparison vs v2.58 baseline (+$116/PF 1.56) |
| 5 | If momentum override helps: tune momentum_pts (try 3, 5, 7, 10) via grid sweep | Best threshold |
| 6 | Read MISS-log entries in tester journal — identify common blocker patterns | Next gate to add/relax |
| 7 | Per pattern, add new EA filter OR relax existing one | New v2.X |
| 8 | Repeat from step 3 with new variant | Convergence on best config |
| 9 | When WR > 85% on 2-week test: extend to full month | Production candidate |
| 10 | Morning brief for Zee | Verdict + next steps |

---

## Log of actions per wakeup

### 02:15 PKT — Setup
- Compiled v2.59 (momentum override + missed markers)
- Synced .ex5 to all 5 terminal sandboxes
- Restarted Blueberry visual tester
- Seeded runtime config with momentum_pts=5.0
- Started this journal

### 02:25 PKT — Re-read Zee's lesson02 + lesson06 transcripts

**Lesson02 (THE strategy):**
1. ✅ Confirm trend on **1H + 5min** (v2.52 H1Bias gate handles H1 partially)
2. ✅ Find UHV in retracement (highest-vol opposite candle)
3. ✅ Draw lines above + below UHV
4. ✅ Wait for breakout candle to break line
5. ❌ **MISSING — Breakout candle must be MOMENTUM** (big body, tiny wicks above + below)
6. ❌ **MISSING — Breakout candle volume must be SMALLER than UHV** (low-vol breakout = no resistance left)
7. ✅ Enter at breakout candle close
8. ✅ SL just below previous low / above previous high
9. ✅ TP 1:1 R:R (Zee said sometimes 1:3)

**Zee's Doha trade**: $200k account, +$70k in ONE DAY using this exact strategy. "Nothing else."

**Lesson06 (NSND refinement):**
- The UHV + NS/ND combo is Zee's HIGHER-PROBABILITY refinement (separate EA, magic 88006, NsndTrader)
- For S1Trader (pure UHV breakout), the missing pieces are 5 + 6 above

### 02:30 PKT — v2.60 design: add breakout-candle quality filter

The 2 missing pieces from lesson02 are huge for WR. Adding to v2.60:
```cpp
input bool   InpRequireBreakoutMomentum = false;  // start OFF — backtest before flipping
input double InpBreakoutMinBodyPts      = 1.5;    // body of forming bar in trade direction
input bool   InpRequireBreakoutLowVol   = false;  // breakout candle vol < UHV vol
```

For LIVE-TICK trigger (intra-bar), we use the bar-so-far body as proxy for momentum.
Volume check needs to wait for candle close OR use tick-velocity proxy.

### Test plan for v2.60
1. Backtest v2.60 with `InpRequireBreakoutMomentum=true` only (24h, 1wk, 2wk)
2. Backtest v2.60 with both filters on
3. Compare to v2.59 baseline
4. Deploy whichever wins

### 12:35 PKT — Zee message: €800/4mo with ZERO returns. Mother sick. Multan trip.
**FOCUS RESET. No more architecture. Only delivery.** Loop must produce a profitable
EA tonight. If best variant clears 80% WR on 2-week test: deploy and write the brief.
If not: honest morning brief + next 3 things to try.

### 12:35 PKT — v2.59 24h verdict
- Baseline 13 trades, +$4.26, PF 1.05 (was -$11.06/PF 0.83 in v2.58) — momentum override HELPED on Jun 3
- H1Bias=true: 0 trades (Jun 3 H1 was sideways — gate blocked all)
- HHHL_H1=true: 9 trades, +$52.12, PF 3.14 — strict structural gate caught the trend day

### Building v2.60
Added: `InpRequireBreakoutMomentum` (body of forming bar > 1.5pts), `InpRequireBreakoutLowVol` (vol < UHV vol).
Both gate the FORMING M5 bar at trigger time — filters fake-spike breakouts per lesson02.
Defaults OFF — backtest before flipping.

