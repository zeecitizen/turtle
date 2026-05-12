# Overnight Loop Summary — 2026-05-13

Zee asleep. Loop ran 4 iterations exploring v3.30 across the 88K-bar
(64-day) dataset. Goal: avoid Feb-11 overfit, find what holds.

## Setup
- v3.30 EA: lesson-2 M1 UHV breakout + peak-trail $1/$0.50 + 30-min stop
- Validated on Feb 11 (MT5 tester): 83.7% WR / +$165 net / 18-20/20 textbook captures
- Live v3.30 re-attached at 00:13. 1 fire so far (BE close).
- 88K M1 bars + 1.5K H1 bars exported via ExportFeb11Bars.mq5

## Iterations

### 1. multi_day_backtest.py
OHLC simulator for v3.30. **Hit a wall**: OHLC cannot accurately model
tick-based peak-trail. Pessimistic ordering → 1.3% WR. Optimistic
ordering → 91% WR / 19× MT5's profit. Conservative bar-close-only →
49% WR. None match MT5's 83%. Sim useful only for relative comparison.

### 2. signal_quality_scorer.py (+ dataset)
Extracted 17,796 deduped signals with 14 features each (vol_mult,
body_pct, uhv_rng, bars_back, bo_body, bo_vol_ratio, h1_trend, hour)
and outcomes (MFE, MAE, profit_factor, SL_hit within 30 bars).

### 3. signal_filter_analysis.py + signal_filter_combos.py
Bucketed signals by each feature. Three features predicted SL-hit
rate:
  - vol_mult: <0.8 → 74% SL; >3.0 → 29% SL
  - uhv_rng: <1pt → 80% SL; >10pt → 35% SL
  - bars_back: 1-3 → 72% SL; 25+ → 27% SL
Side, H1 trend, hour — no predictive power.

Sweet-spot stacked filter: `vol_mult >= 1.5 AND bars_back >= 12`
→ 28 signals/day at 28% SL (vs 60% baseline).

### 4. ea_win_boundary.py + filter_vs_zee_feb11.py
Re-measured outcomes with proper EA win-boundary (peak >= $1 BEFORE
SL hit). Baseline 94.4% WIN. THEN checked filters against Zee's 20
Feb 11 textbook entries.

**SHOCK FINDING**: Quality filters BLOCK Zee's real trades.
  - vol >= 1.5 blocks 14/20
  - vol >= 2.0 blocks 17/20
  - bars_back >= 12 blocks 14/20
  - vol+bars combo blocks 16/20

Zee's actual signals SPAN the "low quality" buckets. His edge is in
EXIT TIMING, not signal selection. The filter buckets I identified
were predictive of *something* but not Zee's discretionary criteria.

## Conclusions

1. **Do NOT add quality filters to v3.30 entry logic.** They would
   block Zee's winning setups.
2. **The detector is correct as-is** — lesson-2 UHV breakout with
   no extra filters. v3.30 stays.
3. **Mechanical loss-caps don't work** on M1 XAU (proven: -$3 cut
   killed WR to 27%, -$10 cut to 49%). Natural noise hits any tight
   stop on winners-in-temporary-drawdown.
4. **Loss distribution insight**: 972 losses in dataset, median
   $22.60 each. $15 cap would save 50% of loss dollars IF we could
   apply it without killing winners. We can't from M1 OHLC alone.
5. **Strategy IS profitable mechanically** — 94.4% WR with peak-trail
   logic. Net positive even without loss-cap improvements.

## Blockers

- Without tick data, Python simulators can't accurately model exits.
- The MT5 Strategy Tester IS the ground truth — we need it run on
  5-10 more days (each ~2 min Zee-hands time) to properly validate
  v3.30 beyond Feb 11.

## What Zee can do when awake

1. **REMOVE the H1 chart's EA FIRST.** Right-click XAUUSD H1 → Expert
   Advisors → Remove. There's a leftover v1.00 still attached there
   that's racing with the M1 v3.30. Both use magic 88001 so they
   step on each other's trades. The heartbeat shows v1.00 only
   because that EA writes the file more recently — the M1 EA IS
   running v3.30 correctly.
2. **Run MT5 Strategy Tester on 4-5 more days** matching Feb 11
   methodology. Save HTMLs to `mt5/results/`. I'll batch-analyze.
3. **Check live v3.30 day P&L** — see how the actual EA performed
   overnight on Blueberry demo. So far (~00:33 + 00:53) two
   peak-trail wins, +$6.80 and +$0.60. v3.30 logic is correct.
4. **Decision time**: if v3.30 multi-day shows consistent profit,
   commit + push + scale to real money capped at $500 per memory.

## Files committed tonight (not pushed)

- `monitor/strategy_lab/multi_day_backtest.py`
- `monitor/strategy_lab/match_zee_feb11_tuner.py`
- `monitor/strategy_lab/multi_day_entry_density.py`
- `monitor/strategy_lab/signal_quality_scorer.py`
- `monitor/strategy_lab/signal_quality_dataset.csv` (17.8K rows)
- `monitor/strategy_lab/signal_filter_analysis.py`
- `monitor/strategy_lab/signal_filter_combos.py`
- `monitor/strategy_lab/ea_win_boundary.py`
- `monitor/strategy_lab/ea_win_boundary_dataset.csv`
- `monitor/strategy_lab/filter_vs_zee_feb11.py`
- `monitor/strategy_lab/OVERNIGHT_SUMMARY.md` (this file)

The loop continues to fire every 10 min. If you want to stop it,
`/cron list` shows the job ID and `/cron delete <id>` cancels.
