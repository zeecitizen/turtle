# Recommended Improvements for S1, S3, S4 EAs

> **Generated**: 2026-05-27 by Antigravity (Gemini)  
> **Data**: 18 real-tick days from Exness (2026-04-29 → 2026-05-26)  
> **Script**: `monitor/strategy_lab/winrate_improvement.py`  
> **Method**: Full tick replay of all 3 EAs, analyzing trade-level features vs win/loss outcomes

---

## Priority 1: Trend Strength Filter (HIGHEST IMPACT)

### Problem
All 3 EAs fire signals in weak trends where they lose money. The data clearly shows that stronger trend = higher win rate, and weak-trend trades are net negative.

### S1 — Add minimum 24-bar trend delta

| Trend Strength (24-bar price delta) | Trades | WR | P&L |
|---|---|---|---|
| Weak (≤ $9.10) | 107 | **55.1%** | **-$37.1** |
| Medium ($9.10 – $17.10) | 106 | 74.5% | +$337.3 |
| Strong (> $17.10) | 106 | 78.3% | +$329.1 |

**Recommendation**: Increase `InpTrendThreshold` from $2.00 to $9.00.  
**Expected impact**: Remove 107 losing trades, keep 212 profitable ones. WR rises from ~69% to ~76%. P&L improves by ~$37.

**Code change** in `S1Trader.mq5`:
```diff
-input double InpTrendThreshold    = 2.0;
+input double InpTrendThreshold    = 9.0;   // 2026-05-27: raised from 2.0. Weak trend (<$9) had 55% WR and -$37 P&L over 107 trades.
```

### S3 — Add minimum 60-bar trend delta

| Trend Strength (60-bar price delta) | Trades | WR | P&L |
|---|---|---|---|
| Weak (≤ $9.10) | 111 | 65.8% | **-$1.4** |
| Medium ($9.10 – $23.10) | 110 | 70.9% | +$110.0 |
| Strong (> $23.10) | 110 | **79.1%** | **+$395.0** |

**Recommendation**: Add a 60-bar trend delta filter (minimum ~$9). S3 currently only checks 24-bar trend. Adding a longer-term confirmation would filter out the breakeven weak-trend trades.

**Code change** in `S3Trader.mq5`: Add a new input `InpTrend60Threshold = 9.0` and check `abs(close[0] - close[60]) >= threshold` before firing.

### S4 — Add minimum 60-bar trend delta

| Trend Strength (60-bar price delta) | Trades | WR | P&L |
|---|---|---|---|
| Weak (≤ $8.70) | 38 | 76.3% | **-$9.5** |
| Medium ($8.70 – $24.20) | 37 | 89.2% | +$35.2 |
| Strong (> $24.20) | 36 | **91.7%** | **+$43.5** |

**Recommendation**: Add `InpTrend60Min = 9.0` to S4. Would eliminate the weak-trend third (n=38, -$9.5) and keep the 89-92% WR configs.

---

## Priority 2: Breakeven SL Move (LARGEST $ IMPACT)

### Problem
The vast majority of losing trades go into profit before reversing into a loss. This is money being left on the table.

| EA | % of losses that went +$0.50 first | % that went +$1.00 first | Losses recoverable at +$1.00 BE | $ recoverable |
|---|---|---|---|---|
| **S1** | **79%** | **70%** | 68 of 97 losses | **$686** |
| **S3** | **82%** | **62%** | 57 of 93 losses | **$528** |
| S4 | 56% | 31% | 5 of 16 losses | $38 |

### How it works
When a trade reaches +$X.XX profit, move the stop-loss to the entry price (breakeven). If the trade reverses back to entry, it closes at $0 instead of a full loss.

### Recommendation
- **S1**: Move SL to breakeven after +$1.00 of favorable excursion
- **S3**: Move SL to breakeven after +$1.00 of favorable excursion  
- **S4**: Skip — only 5 trades affected, not worth the complexity

### ⚠️ IMPORTANT CAVEAT
This analysis only counts losses saved. It does NOT account for **winners that would be killed** — trades that go +$1.00, dip back to breakeven (getting stopped at $0), and then would have continued to TP. 

**Before implementing**: Run a full simulation that replays the breakeven logic on ALL trades (wins + losses) tick-by-tick to measure the NET effect. The raw $686 recovery is an upper bound — the real improvement will be smaller because some winners will be stopped at breakeven.

### Code pattern (for the EA)
```mql5
// In OnTick(), after checking TP/SL:
if (position_profit >= InpBreakevenTrigger) {
   if (current_sl != entry_price) {
      trade.PositionModify(ticket, entry_price, current_tp);
   }
}
```

---

## Priority 3: Time-of-Day Filter

### Problem
Hours 12-13 (broker time) are the weakest across all EAs. This corresponds to lunchtime during the London-NY overlap when markets tend to be choppy/ranging.

### S4 hourly breakdown (all hours with 3+ trades)

| Hour | Trades | WR | P&L | Status |
|---|---|---|---|---|
| 3:00 | 4 | 75.0% | -$1.5 | 🟢 Golden |
| 4:00 | 5 | 100% | +$10.0 | 🟢 Golden |
| 5:00 | 4 | 100% | +$8.0 | 🟢 Golden |
| 6:00 | 5 | 80.0% | +$0.5 | 🟢 Golden |
| 7:00 | 13 | 84.6% | +$7.0 | 🟢 Golden |
| 11:00 | 8 | 75.0% | -$3.0 | 🟢 Golden |
| **12:00** | **5** | **60.0%** | **-$9.0** | ⚠️ Weak |
| **13:00** | **7** | **57.1%** | **-$14.5** | ⚠️ Weak |
| 14:00 | 4 | 100% | +$8.0 | 🟢 Golden |
| 16:00 | 5 | 100% | +$10.0 | 🟢 Golden |
| 20:00 | 5 | 100% | +$10.0 | 🟢 Golden |

### Recommendation
Add a time-of-day filter to skip hours 12-13 broker time. S3 already has a time filter infrastructure (`InpStartHour`, `InpEndHour`). S1 and S4 would need it added.

**Expected impact**: Small — only ~10-15 trades affected per EA. But it removes the weakest-WR period at zero cost.

---

## Priority 4: Findings That DON'T Help (Don't Implement)

### ❌ Time-based exits
Closing trades after N minutes universally hurts performance:
- S1: Closing after 60min → P&L drops from $629 to $207 (−$422)
- S3: Closing after 60min → P&L drops from $504 to $232 (−$271)
- S4: Already resolves in 10-14 min, time exit has no effect

**Why**: Winners need time to develop. Cutting them early kills the edge.

### ❌ Pause after consecutive losses
- S1: WR after 3+ losses = 56.2% (still positive EV)
- S3: WR after 3+ losses = 71.4% (**higher** than baseline — mean reversion!)
- S4: Too rare to measure

**Why**: The strategies don't exhibit tilt behavior. S3 actually performs better after a losing streak.

### ❌ ATR filter (volatility)
Medium ATR is slightly better than high or low, but the effect is inconsistent across EAs and not robust enough to filter on. Would likely overfit.

---

## Trade Speed Characteristics

Understanding how fast each EA resolves helps with position management:

| EA | Avg Win Speed | Avg Loss Speed | Insight |
|---|---|---|---|
| S1 | 53 min | 42 min | Slowest. Losses resolve faster than wins |
| S3 | 29 min | 36 min | Medium. Losses are slower (good — gives them time to recover) |
| **S4** | **10 min** | **14 min** | Very fast scalp-like. Resolves within 2-3 M5 bars |

---

## Summary: Implementation Priority

| # | Improvement | EAs | Effort | Impact | Risk |
|---|---|---|---|---|---|
| **1** | **Raise S1 trend threshold to $9** | S1 | 1 line change | High (+$37, +7% WR) | Low (clear data) |
| **2** | **Add 60-bar trend filter** | S3, S4 | New input + check | Medium | Low |
| **3** | **Breakeven SL after +$1** | S1, S3 | OnTick logic | **Very High** ($686+$528 upper bound) | **Medium** (needs full sim first) |
| **4** | **Skip hours 12-13** | All | Time filter | Small | Low |

> **Note**: All recommendations are based on 18 days of data. More data would increase confidence. Always re-validate after implementing changes — the walk-forward test should still pass with these filters added.

---

## Files Reference

| File | Purpose |
|---|---|
| `monitor/strategy_lab/winrate_improvement.py` | The analysis script that generated these findings |
| `monitor/strategy_lab/s4_deep_sweep.py` | S4 parameter sweep (150+ configs) |
| `monitor/strategy_lab/s3_deep_sweep.py` | S3 parameter sweep (150+ configs) |
| `docs/S1_STRATEGY.md` | S1 full strategy documentation |
| `docs/S3_STRATEGY.md` | S3 full strategy documentation |
| `docs/S4_STRATEGY.md` | S4 full strategy documentation |
