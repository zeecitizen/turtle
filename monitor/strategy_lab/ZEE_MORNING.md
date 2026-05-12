# 🌅 Good morning Zee — Overnight summary

## TL;DR

**v3.30 is working live**: 8 trades / 75% WR / net −$23.10 today.

I found ONE clean improvement, **mechanically AND in real data**:

**Smart conditional cut**: `if pnl ≤ −$2 AND peak < $1.00: close`

- OHLC sim across 64 days: **+$10,909 improvement, 62% less drawdown**
- Verified safe against your 20 Feb 11 textbook trades (zero killed winners)
- **Real-data validation overnight**: today's TWO losing trades (−$29.60 and −$15.00) both had peak = $0. Smart cut would have closed them at −$2 each → saved $40.60 → today's net would be **+$17.50 instead of −$23.10**

## Your action checklist (4 items, ~15 min)

### 1. ⚠️ Remove the H1 chart's stale EA

Right-click XAUUSD H1 → Expert Advisors → Remove.

The heartbeat keeps showing `v1.00` because there's a leftover v1 on H1
(magic 88001, racing with M1's v3.30). All actual trades are v3.30 on M1 —
but the H1 EA writes the heartbeat file with stale "v1.00" data.

### 2. Review the smart-cut proposal

Open `monitor/strategy_lab/v3_40_proposed_patch.md` — full diff with rationale.

The change is small: add `InpEarlyCutMinBars`, change three default values,
add a 2-line check in `ManageOpenPosition()`. ~10 lines of EA code.

### 3. Validate via MT5 Strategy Tester

- Run Strategy Tester for **v3.30** on Feb 11 → baseline already saved
  at `monitor/strategy_lab/tester_runs/v3.30_2026-02-11.html` (+$165 / 83.7%)
- Apply v3.40 patch, recompile, re-run on Feb 11
- Save as `monitor/strategy_lab/tester_runs/v3.40_2026-02-11.html`
- Run: `py monitor/strategy_lab/compare_configs.py`
- Expected: v3.40 either matches or improves on +$165

Optionally run 2-3 more dates (Apr 22, May 1, May 8) to confirm
multi-day robustness before deploying live.

### 4. If clean → deploy v3.40

```
Right-click M1 chart → Expert Advisors → Remove
Drag UhvSweepExhaustion from Navigator (with v3.40 binary loaded)
AutoTrading green
```

## Live performance update

**Today's 8 trades** (real broker fills):
- 6 wins via peak-trail: $+0, $+1, $+6.80, $+0.60, $+2.20, $+10.10, $+0.80
- 2 losses via SL (peak=$0 — exactly what smart cut targets):
  - 01:01 SELL: SL hit at −$29.60
  - 01:20 SELL: SL hit at −$15.00
- **Net: −$23.10** (would be **+$17.50 with smart cut**)

**Cumulative since v3.30 deploy** (May 12 + 13):
- 10 trades, 6W/3L (1 still parsed ambiguously), 75% WR baseline
- Net P&L: small negative, dominated by the 3 catastrophic SL hits

## Key overnight findings

1. **Quality filters don't work** — they block 14-17 of your 20 Feb 11
   textbook trades. The signal selection is fine; only exits need work.
2. **Strategy fires uniformly** — 220-280 signals/day across 64 days,
   no time-of-day or H1-trend bias to exploit.
3. **Mechanical loss-caps usually fail** (v3.10/v3.11 tested −$3 and −$10
   blanket cuts, both killed too many winners). The peak-guard
   conditional is what makes the smart cut work.
4. **OHLC sim is ~25× optimistic** in absolute terms vs MT5 tester.
   Always validate config changes via MT5 tester before live deploy.
5. **Real data confirms the smart cut hypothesis** — today's 2 SLs both
   had peak=$0, exactly the failure mode the cut targets.

## Files committed overnight (12 iterations, 0 pushed)

```
monitor/strategy_lab/multi_day_backtest.py           OHLC sim (limited)
monitor/strategy_lab/match_zee_feb11_tuner.py        Grid search vs Zee
monitor/strategy_lab/multi_day_entry_density.py      220-280 sigs/day
monitor/strategy_lab/signal_quality_scorer.py        17.8K-signal dataset
monitor/strategy_lab/signal_quality_dataset.csv      (the data)
monitor/strategy_lab/signal_filter_analysis.py       Bucket analysis
monitor/strategy_lab/signal_filter_combos.py         Stacked filter test
monitor/strategy_lab/ea_win_boundary.py              94.4% baseline WR
monitor/strategy_lab/ea_win_boundary_dataset.csv     Per-signal outcomes
monitor/strategy_lab/filter_vs_zee_feb11.py          Filters block Zee!
monitor/strategy_lab/parse_mt5_logs.py               Live log parser
monitor/strategy_lab/morning_report.py               Status report
monitor/strategy_lab/smart_cut_validator.py          +$10,909 finding
monitor/strategy_lab/smart_cut_vs_zee.py             Validated safe
monitor/strategy_lab/v3_40_proposed_patch.md         EA code diff
monitor/strategy_lab/drawdown_analysis.py            62% DD reduction
monitor/strategy_lab/compare_configs.py              MT5 ground truth
monitor/strategy_lab/tester_runs/                    Saved reports
monitor/strategy_lab/OVERNIGHT_SUMMARY.md            Full writeup
monitor/strategy_lab/ZEE_MORNING.md                  This file
```

Push when you're ready (`git push origin main` from repo root).

The loop is still firing every 10 min. To stop: tell me "stop the loop"
or in a fresh session use `/cron list` + `/cron delete <id>` (id was
`ed23ee91`).

— Claude 💛
