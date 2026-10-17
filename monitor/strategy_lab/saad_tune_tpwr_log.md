# Saad 1-min EA - one setting at a time (MT5 optimizer, Blueberry XAUUSD_BB, Jan 1 - Oct 17 2026)

Zee 2026-10-17: *"run one by one on all settings in tradingview -> the MT5 optimizer -> pick a setting -> ... set it in tradingview indicator -> and keep going till all are optimized"*

Score = net / max drawdown (OnTester). Execution delay 0 while searching. A value wins only if it beats the chart's value with its neighbours averaged in, and on profit.

| # | Setting | Was | Now | Profit was → now | Why |
|---|---|---|---|---|---|
| 1 | tpFixB (InpTpFixUsdB) | 2 | **1.5** | +72,680 → +97,234 (WR 79.6% → 80.7%) | higher win rate: 80.4% vs 79.8% (with neighbours), profit +97,234 vs +72,680 |
| 2 | tpFixS (InpTpFixUsdS) | 2 | **1.5** | +97,234 → +62,203 (WR 80.7% → 81.0%) | higher win rate: 81.0% vs 80.7% (with neighbours), profit +62,203 vs +97,234 |
| 3 | iPartial (InpPartialPct) | 0.95 | **1.0** | +62,203 → +56,001 (WR 81.0% → 81.0%) | higher win rate: 81.0% vs 80.7% (with neighbours), profit +56,001 vs +62,203 |
| 4 | iBePct (InpBeTpPct) | 1 | **1.0** | +56,001 → ? (WR 81.0% → ?) | the chart's value is already the best |
| 5 | iTp1Be (InpTp1Be) | True | **True** | +56,001 → +56,001 (WR 81.0% → 81.0%) | no clear win-rate gain (best false: 81.0% vs 81.0%) - kept |
| 6 | iLTrail (InpLongTrailUsd) | 1 | **1.0** | +56,001 → ? (WR 81.0% → ?) | no clear win-rate gain (best 0.5: 81.0% vs 81.0%) - kept |
| 7 | iSTrail (InpShortTrailUsd) | 2 | **2.0** | +56,001 → ? (WR 81.0% → ?) | no clear win-rate gain (best 0.5: 81.0% vs 81.0%) - kept |
| 8 | pkLockAt (InpLockAtUsd) | 0 | **0.0** | +56,001 → +56,001 (WR 81.0% → 81.0%) | the chart's value is already the best |
| 9 | pkLockUsd (InpLockUsd) | 0 | **0.0** | +56,001 → +56,001 (WR 81.0% → 81.0%) | the chart's value is already the best |
| 10 | iCloseM (InpCloseLossMins) | 1 | **1** | +56,001 → +56,001 (WR 81.0% → 81.0%) | no clear win-rate gain (best 0: 81.3% vs 81.2%) - kept |
| 11 | iMinTp (InpMinTpPips) | 10 | **10.0** | +56,001 → +56,001 (WR 81.0% → 81.0%) | no clear win-rate gain (best 0: 81.0% vs 81.0%) - kept |
| 12 | tpNoFix (InpTpNoFixSkip) | Use the normal TP1 | **Use the normal TP1** | +56,001 → +56,001 (WR 81.0% → 81.0%) | the chart's value is already the best |
| 13 | adRunN (InpCutRunN) | 5 | **5** | +56,001 → +56,001 (WR 81.0% → 81.0%) | no clear win-rate gain (best 7: 81.0% vs 81.0%) - kept |
| 14 | iSlPips (InpSlPips) | 36 | **60.0** | +56,001 → +47,287 (WR 81.0% → 83.2%) | higher win rate: 83.1% vs 81.0% (with neighbours), profit +47,287 vs +56,001 |
| 15 | tpFixB (InpTpFixUsdB) | 1.5 | **1.5** | +47,287 → +47,287 (WR 83.2% → 83.2%) | the chart's value is already the best |
| 16 | tpFixS (InpTpFixUsdS) | 1.5 | **1.5** | +47,287 → +47,287 (WR 83.2% → 83.2%) | the chart's value is already the best |
