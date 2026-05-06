# Strategy Research Report

_Computed: 2026-04-30T05:19:43_
_Probes analyzed: 105_

## Top 10 by total P&L

| Rank | Strategy | Fired | WR% | Total | Worst day | Best day | Big losses |
|------|----------|-------|-----|-------|-----------|----------|------------|
| 1 | I postLoss=1 + dailyHalt=2 + flipSkip=2 | 28 | 85.7 | $+239.20 | $-8.00 | $+247.20 | 4 |
| 2 | G postLoss=2 + dailyHalt=2 | 28 | 85.7 | $+193.60 | $-27.20 | $+220.80 | 4 |
| 3 | K trail=12/4.0 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 81.8 | $+171.60 | $+30.80 | $+140.80 | 4 |
| 4 | K trail=10/3.0 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 81.8 | $+112.80 | $+23.20 | $+89.60 | 4 |
| 5 | C dailyBigLossHalt after 3 (fi=50) | 31 | 80.6 | $+111.20 | $-55.20 | $+166.40 | 6 |
| 6 | G postLoss=1 + dailyHalt=3 | 31 | 80.6 | $+111.20 | $-55.20 | $+166.40 | 6 |
| 7 | O ultra: trail=5/1.5 + fi=35 + postLoss=2 + dailyHalt=2 | 24 | 83.3 | $+96.00 | $-40.80 | $+136.80 | 4 |
| 8 | C dailyBigLossHalt after 4 (fi=50) | 38 | 78.9 | $+77.20 | $-107.20 | $+184.40 | 8 |
| 9 | D consecLossSkip after 2 (fi=50) | 12 | 83.3 | $+71.60 | $+71.60 | $+71.60 | 2 |
| 10 | C dailyBigLossHalt after 2 (fi=50) | 22 | 81.8 | $+68.00 | $-3.60 | $+71.60 | 4 |

## Top 10 by worst-day P&L (regime robustness)

| Rank | Strategy | Worst day | Total | WR% |
|------|----------|-----------|-------|-----|
| 1 | D consecLossSkip after 2 (fi=50) | $+71.60 | $+71.60 | 83.3 |
| 2 | K trail=12/4.0 + postLoss=1 + dailyHalt=2 (fi=50) | $+30.80 | $+171.60 | 81.8 |
| 3 | K trail=10/3.0 + postLoss=1 + dailyHalt=2 (fi=50) | $+23.20 | $+112.80 | 81.8 |
| 4 | C dailyBigLossHalt after 2 (fi=50) | $-3.60 | $+68.00 | 81.8 |
| 5 | G postLoss=1 + dailyHalt=2 | $-3.60 | $+68.00 | 81.8 |
| 6 | J fi=50 + postLoss=1 + dailyHalt=2 | $-3.60 | $+68.00 | 81.8 |
| 7 | L pc=0.45 + postLoss=1 + dailyHalt=2 (fi=50) | $-3.60 | $+68.00 | 81.8 |
| 8 | I postLoss=1 + dailyHalt=2 + flipSkip=2 | $-8.00 | $+239.20 | 85.7 |
| 9 | L pc=0.3 + postLoss=1 + dailyHalt=2 (fi=50) | $-10.80 | $+27.20 | 75.0 |
| 10 | L pc=0.5 + postLoss=1 + dailyHalt=2 (fi=50) | $-15.60 | $+64.00 | 81.8 |

## Headline comparison

| Metric | Baseline (current live) | Best total | Best worst-day |
|--------|-------------------------|------------|----------------|
| Strategy | A0 baseline pc=.45 fi=50 (CURRENT LIVE) | I postLoss=1 + dailyHalt=2 + flipSkip=2 | D consecLossSkip after 2 (fi=50) |
| Total P&L | $-398.80 | $+239.20 | $+71.60 |
| Worst day | $-300.80 | $-8.00 | $+71.60 |
| WR | 67.8% | 85.7% | 83.3% |
| Trades fired | 59 | 28 | 12 |
| Big losses | 19 | 4 | 2 |

## All variants (sorted by total)

| Strategy | Fired | Skipped | WR% | Total | Worst day | Big losses |
|----------|-------|---------|-----|-------|-----------|------------|
| I postLoss=1 + dailyHalt=2 + flipSkip=2 | 28 | 31 | 85.7 | $+239.20 | $-8.00 | 4 |
| G postLoss=2 + dailyHalt=2 | 28 | 31 | 85.7 | $+193.60 | $-27.20 | 4 |
| K trail=12/4.0 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 37 | 81.8 | $+171.60 | $+30.80 | 4 |
| K trail=10/3.0 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 37 | 81.8 | $+112.80 | $+23.20 | 4 |
| C dailyBigLossHalt after 3 (fi=50) | 31 | 28 | 80.6 | $+111.20 | $-55.20 | 6 |
| G postLoss=1 + dailyHalt=3 | 31 | 28 | 80.6 | $+111.20 | $-55.20 | 6 |
| O ultra: trail=5/1.5 + fi=35 + postLoss=2 + dailyHalt=2 | 24 | 35 | 83.3 | $+96.00 | $-40.80 | 4 |
| C dailyBigLossHalt after 4 (fi=50) | 38 | 21 | 78.9 | $+77.20 | $-107.20 | 8 |
| D consecLossSkip after 2 (fi=50) | 12 | 47 | 83.3 | $+71.60 | $+71.60 | 2 |
| C dailyBigLossHalt after 2 (fi=50) | 22 | 37 | 81.8 | $+68.00 | $-3.60 | 4 |
| G postLoss=1 + dailyHalt=2 | 22 | 37 | 81.8 | $+68.00 | $-3.60 | 4 |
| J fi=50 + postLoss=1 + dailyHalt=2 | 22 | 37 | 81.8 | $+68.00 | $-3.60 | 4 |
| L pc=0.45 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 37 | 81.8 | $+68.00 | $-3.60 | 4 |
| L pc=0.5 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 37 | 81.8 | $+64.00 | $-15.60 | 4 |
| N defensive: fi=25 + postLoss=2 + dailyHalt=2 + flipSkip=2 | 12 | 47 | 66.7 | $+63.20 | $-44.00 | 0 |
| J fi=35 + postLoss=1 + dailyHalt=2 | 20 | 39 | 80.0 | $+62.00 | $-27.20 | 4 |
| M aggressive: fi=35 + postLoss=2 + dailyHalt=2 + flipSkip=2 | 17 | 42 | 76.5 | $+56.00 | $-28.00 | 4 |
| K trail=6/2.0 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 37 | 81.8 | $+45.60 | $-26.00 | 4 |
| K trail=4/1.5 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 37 | 81.8 | $+42.80 | $-28.80 | 4 |
| K trail=5/2.0 + postLoss=1 + dailyHalt=2 (fi=50) | 22 | 37 | 81.8 | $+41.20 | $-30.40 | 4 |
| L pc=0.4 + postLoss=1 + dailyHalt=2 (fi=50) | 20 | 41 | 80.0 | $+30.40 | $-18.00 | 4 |
| J fi=25 + postLoss=1 + dailyHalt=2 | 10 | 49 | 60.0 | $+28.00 | $-38.00 | 1 |
| L pc=0.3 + postLoss=1 + dailyHalt=2 (fi=50) | 16 | 52 | 75.0 | $+27.20 | $-10.80 | 4 |
| L pc=0.58 + postLoss=1 + dailyHalt=2 (fi=50) | 21 | 35 | 81.0 | $+25.60 | $-35.60 | 4 |
| L pc=0.7 + postLoss=1 + dailyHalt=2 (fi=50) | 15 | 34 | 73.3 | $-31.60 | $-34.00 | 4 |
| B postBigLoss skip 2 (fi=50) | 47 | 12 | 74.5 | $-70.00 | $-79.20 | 12 |
| B postBigLoss skip 3 (fi=50) | 39 | 20 | 74.4 | $-90.40 | $-67.20 | 10 |
| D consecLossSkip after 3 (fi=50) | 43 | 16 | 69.8 | $-190.80 | $-190.80 | 13 |
| D consecLossSkip after 4 (fi=50) | 44 | 15 | 68.2 | $-242.40 | $-242.40 | 14 |
| E directionFlipSkip after 3 same-dir wins | 52 | 7 | 69.2 | $-272.40 | $-221.60 | 16 |
| E directionFlipSkip after 2 same-dir wins | 45 | 14 | 66.7 | $-284.40 | $-233.60 | 15 |
| H postLoss=1 + flipSkip=2 | 45 | 14 | 66.7 | $-284.40 | $-233.60 | 15 |
| A0 baseline pc=.45 fi=50 (CURRENT LIVE) | 59 | 0 | 67.8 | $-398.80 | $-300.80 | 19 |
| B postBigLoss skip 1 (fi=50) | 59 | 0 | 67.8 | $-398.80 | $-300.80 | 19 |
| F burstPositionMax 2 (after burst of N wins) | 59 | 0 | 67.8 | $-398.80 | $-300.80 | 19 |
| F burstPositionMax 3 (after burst of N wins) | 59 | 0 | 67.8 | $-398.80 | $-300.80 | 19 |
| A2 pc=.45 fi=70 | 59 | 0 | 72.9 | $-480.00 | $-320.00 | 16 |
| A1 baseline pc=.58 fi=70 (ORIGINAL) | 56 | 0 | 69.6 | $-567.20 | $-444.00 | 16 |
| A3 pc=.45 fi=35 | 59 | 0 | 55.9 | $-569.60 | $-443.20 | 26 |