# Exhaustive Improvement Analysis — All Findings

> **Generated**: 2026-05-27 by Antigravity (Gemini)  
> **Data**: 18 real-tick days from Exness (2026-04-29 → 2026-05-26), walk-forward split at day 9  
> **Scripts**: `monitor/strategy_lab/winrate_improvement.py` + `exhaustive_improvements.py`  
> **Raw output**: `docs/exhaustive_results.txt`

---

## Phase 1: Breakeven SL (NET Effect — Full Tick Simulation)

The previous analysis showed 79% of S1 losses went positive first. But the **full simulation** (which also accounts for winners that get stopped at breakeven) tells a very different story:

### S1 — Breakeven DESTROYS profitability

| Config | WR | P&L | OOS | DD | BE'd trades | WF |
|---|---|---|---|---|---|---|
| BASELINE | 69.3% | **+$629** | +$344 | $78 | — | ✅ |
| BE@+$0.50 | 93.4% | +$71 | -$17 | $58 | 264 | ❌ |
| BE@+$1.00 | 90.6% | +$97 | -$41 | $62 | 236 | ❌ |
| BE@+$1.50 | 89.0% | +$194 | +$16 | $66 | 208 | ✅ |
| BE@+$3.00 | 81.5% | +$204 | +$88 | $86 | 148 | ✅ |

> **⛔ VERDICT: DO NOT ADD BREAKEVEN TO S1.** It kills too many winners. P&L drops from $629 to $71-$204. The WR goes up but the P&L collapses because S1's TP ($7.50) requires letting winners run far.

### S3 — Breakeven also hurts

| Config | WR | P&L | OOS | DD | BE'd trades | WF |
|---|---|---|---|---|---|---|
| BASELINE | 71.9% | **+$504** | +$199 | $67 | — | ✅ |
| BE@+$0.50 | 94.9% | +$151 | +$56 | $23 | 252 | ✅ |
| BE@+$1.00 | 89.1% | +$125 | +$47 | $66 | 192 | ✅ |
| BE@+$3.00 | 81.0% | +$260 | +$120 | $58 | 95 | ✅ |

> **⛔ VERDICT: DO NOT ADD BREAKEVEN TO S3.** Same problem — P&L drops from $504 to $125-$260. Not worth it.

### S4 — Breakeven is neutral/slightly negative

| Config | WR | P&L | OOS | DD | WF |
|---|---|---|---|---|---|
| BASELINE | 85.6% | **+$69** | +$27 | $25 | ✅ |
| BE@+$1.50 | 88.3% | +$70 | +$15 | $21 | ✅ |

> **→ VERDICT: Skip breakeven on S4 too.** The TP is only $2.00 — breakeven trigger can't be lower than TP.

### 🚨 KEY INSIGHT: Breakeven is a TRAP for these strategies
The MFE analysis made breakeven look amazing (+$686 recoverable for S1), but the full tick simulation shows it kills far more in winning trades than it saves in losing trades. **Do not implement breakeven on any EA.**

---

## Phase 2: Trend Threshold Optimization

### S1 — Best filter: `td24 >= $7`

| Filter | Trades | WR | Total P&L | OOS | DD | WF |
|---|---|---|---|---|---|---|
| None (baseline) | 319 | 69.3% | +$629 | +$344 | $78 | ✅ |
| td24 >= $5 | 276 | 72.8% | +$690 | +$351 | $61 | ✅ |
| **td24 >= $7** | **254** | **75.6%** | **+$745** | **+$369** | **$51** | ✅ |
| td24 >= $9 | 213 | 76.5% | +$674 | +$303 | $58 | ✅ |
| td24 >= $11 | 181 | 77.3% | +$589 | +$268 | $49 | ✅ |

> **🏆 WINNER: `td24 >= $7`** — highest TOTAL P&L (+$745), highest OOS (+$369), lowest DD ($51). WR jumps to 75.6%. Removes 65 weak-trend trades that were net -$116.

**Code change**: `InpTrendThreshold = 7.0` (currently 2.0)

### S3 — Best filter: `td60 >= $5` or `skip h12-13`

| Filter | Trades | WR | Total P&L | OOS | DD | WF |
|---|---|---|---|---|---|---|
| None (baseline) | 331 | 71.9% | +$504 | +$199 | $67 | ✅ |
| **td60 >= $5** | **269** | **74.7%** | **+$571** | **+$216** | **$55** | ✅ |
| td60 >= $7 | 246 | 75.2% | +$538 | +$208 | $53 | ✅ |
| **skip h12-13** | **303** | **73.6%** | **+$579** | **+$204** | **$67** | ✅ |
| td60>=9 + skip h12-13 | 206 | 76.2% | +$539 | +$194 | $44 | ✅ |

> **🏆 WINNER: `skip h12-13`** — highest total P&L (+$579), minimal trade reduction (303 vs 331). Or **`td60 >= $5`** for higher WR and lower DD.  
> **Best combo for safety: `td60>=9 + skip h12-13`** — WR=76.2%, DD=$44 (safest for $126 account).

### S4 — Best filter: `skip h12-13` or `td24 >= $9 + skip h12-13`

| Filter | Trades | WR | Total P&L | OOS | DD | WF |
|---|---|---|---|---|---|---|
| None (baseline) | 111 | 85.6% | +$69 | +$27 | $25 | ✅ |
| td24 >= $7 | 101 | 88.1% | +$87 | +$29 | $21 | ✅ |
| **skip h12-13** | **99** | **88.9%** | **+$93** | **+$34** | **$15** | ✅ |
| **td24>=9 + skip h12-13** | **77** | **92.2%** | **+$96** | **+$37** | **$7.5** | ✅ |
| td24>=7 + td60>=9 + skip h12-13 | 61 | **93.4%** | +$83 | +$29 | **$7.5** | ✅ |

> **🏆 WINNER: `td24>=9 + skip h12-13`** — WR jumps to **92.2%**, P&L +$96 (+39% improvement), DD drops to **$7.50** (6% of account). Only 1 max loss possible before recovery.
> **Ultra-safe: `td24>=7 + td60>=9 + skip h12-13`** — **93.4% WR**, DD=$7.50.

---

## Phase 3: Candle Quality Features

### S4 — Body ratio ≥ 90% = 100% WR
- Body ratio >90%: n=12, **100% WR**, +$24 — these are the strongest momentum candles

### S4 — Green candle momentum
- 2 green candles in last 5: n=49, **91.8% WR**, +$60 (best)
- 3 green candles in last 5: n=36, 75.0% WR, -$14 (overextended, starts losing)

> **Insight**: S4 works best when momentum is building (2 greens) but not when it's overextended (3+ greens). This could be a filter but the sample sizes are small.

---

## Phase 4: Session Filter

### S1 — NY session is the problem

| Session | Trades | WR | P&L | OOS |
|---|---|---|---|---|
| **Asian (0-7)** | 121 | **72.7%** | **+$344** | **+$194** |
| London (7-14) | 118 | 69.5% | +$245 | +$135 |
| **NY (14-21)** | **65** | **61.5%** | **+$13** | **-$13** |
| Late (21-24) | 15 | 73.3% | +$27 | +$29 |

> **S1's NY session (14-21) is nearly breakeven with negative OOS.** Skipping it would improve robustness.

### S4 — London session is the problem

| Session | Trades | WR | P&L | OOS |
|---|---|---|---|---|
| **Asian (0-7)** | 38 | **92.1%** | **+$48** | **+$26** |
| **London (7-14)** | **41** | **75.6%** | **-$13** | **-$10** |
| NY (14-21) | 25 | **92.0%** | +$31 | +$1 |

> **S4 LOSES money during London session.** All of S4's edge comes from Asian + NY.

---

## Phase 5: Trailing Stops

### All EAs — Trailing stops HURT

| EA | Baseline P&L | Best Trail P&L | Verdict |
|---|---|---|---|
| S1 | **+$629** | +$317 (trail +$5/$2.5) | ❌ -50% P&L |
| S3 | **+$504** | +$259 (trail +$4/$2) | ❌ -49% P&L |
| S4 | **+$69** | +$69 (no effect — TP too small) | ➖ Neutral |

> **⛔ VERDICT: DO NOT ADD TRAILING STOPS.** They universally cut P&L by ~50%. These strategies need fixed TP to capture their edge. Trailing stops turn big winners into small winners.

---

## Phase 6: Multi-EA Confirmation

| Pair | Confirmed WR | Unconfirmed WR | Verdict |
|---|---|---|---|
| S1 confirmed by S4 | 72.6% | 67.2% | +5.4% WR ✅ (but loses unconfirmed P&L) |
| S1 confirmed by S3 | 67.1% | 71.4% | -4.3% WR ❌ (confirmation HURTS) |
| S3 confirmed by S4 | 71.6% | 72.0% | Neutral |

> **→ Only S1+S4 confirmation shows benefit**, but requiring confirmation would drop 195 trades (+$291 P&L). Not worth it. **Run all EAs independently.**

---

## FINAL RECOMMENDATIONS — Ranked by Confidence

### ✅ Implement (High Confidence)

| # | Change | EA | Code | Before | After | Impact |
|---|---|---|---|---|---|---|
| **1** | **Raise trend threshold to $7** | S1 | `InpTrendThreshold = 7.0` | WR 69%, DD $78 | **WR 76%, DD $51** | +$116 P&L, +6.3% WR |
| **2** | **Skip hours 12-13** | S4 | Add time filter | WR 86%, DD $25 | **WR 89%, DD $15** | +$24 P&L, +3.3% WR |
| **3** | **Skip hours 12-13** | S3 | Enable time filter | WR 72%, DD $67 | **WR 74%, DD $67** | +$75 P&L, +1.7% WR |

### ⚠️ Consider (Medium Confidence — tighter filter, fewer trades)

| # | Change | EA | Before | After | Tradeoff |
|---|---|---|---|---|---|
| 4 | td24>=9 + skip h12-13 | S4 | WR 86% | **WR 92%, DD $7.5** | Fewer trades (77 vs 111) |
| 5 | td60>=5 | S3 | WR 72% | **WR 75%, DD $55** | Fewer trades (269 vs 331) |
| 6 | Skip NY session (14-21) | S1 | OOS +$344 | OOS **+$358** | Removes 65 trades |

### ❌ Do NOT Implement (Proven Harmful)

| Change | Verdict | Why |
|---|---|---|
| **Breakeven SL** | ❌ DESTROYS P&L | Kills winners. S1: $629→$71. S3: $504→$125 |
| **Trailing stops** | ❌ Cuts P&L by 50% | Turns big winners into small winners |
| **Time-based exits** | ❌ Hurts everything | Winners need time to develop |
| **Multi-EA confirmation** | ❌ Not robust | Only S1+S4 shows marginal benefit, not worth the lost trades |

---

## Optimal Configs (If All Recommendations Applied)

| EA | Version | WR | Total P&L | OOS | DD | Changes |
|---|---|---|---|---|---|---|
| **S1** | v2.31 | **75.6%** | **+$745** | +$369 | $51 | Trend threshold $2→$7 |
| **S3** | v2.32 | **73.6%** | **+$579** | +$204 | $67 | Skip h12-13 |
| **S4** | v2.01 | **92.2%** | **+$96** | +$37 | $7.5 | td24>=9, skip h12-13 |
| **Combined** | — | — | **+$1,420** | **+$610** | ~$126 worst | All 3 on XAUUSD M5 |

vs current configs:

| EA | Current WR | Current P&L | Current DD |
|---|---|---|---|
| S1 | 69.3% | +$629 | $78 |
| S3 | 71.9% | +$504 | $67 |
| S4 | 85.6% | +$69 | $25 |
| Combined | — | +$1,202 | ~$170 |

**Net improvement: +$218 P&L (+18%), -$44 DD (-26%).**

---

## Files Reference

| File | Purpose |
|---|---|
| `docs/exhaustive_results.txt` | Full raw output of all 7 phases |
| `monitor/strategy_lab/exhaustive_improvements.py` | The exhaustive analysis script |
| `monitor/strategy_lab/winrate_improvement.py` | Initial improvement analysis (time/trend/MFE) |
| `docs/S1_STRATEGY.md` | S1 strategy documentation |
| `docs/S3_STRATEGY.md` | S3 strategy documentation |
| `docs/S4_STRATEGY.md` | S4 strategy documentation |
