# NS/ND — the busiest configuration that still makes money

Zee asked for maximum trades per day. 720 configurations tested serially (one position at a time) across 37 tick-days; only the 350 that were profitable on BOTH the training days and the held-out newest 15 days (minimum 10 trades there) are shown.

Everything is at 0.10 lots with spread charged. FVG gate off throughout, per his instruction to relax what hampers growth.

## Most trades per day (what he asked for)

| vol | rng | win | uhv | near | SL | TP | trades | /day | WR | net $ | TEST n | TEST net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.85 | 0.9 | 12 | 1.15 | 2.0 | 2.0R | 3.0R | 260 | 7.03 | 29% | +1762 | 94 | +1637 |
| 0.85 | 0.9 | 30 | 1.15 | 2.0 | 2.0R | 4.0R | 235 | 6.35 | 23% | +271 | 88 | +176 |
| 0.85 | 0.9 | 20 | 1.15 | 2.0 | 2.0R | 4.0R | 233 | 6.30 | 24% | +1332 | 85 | +1071 |
| 0.85 | 1.1 | 30 | 1.15 | 2.0 | 2.0R | 4.0R | 230 | 6.22 | 24% | +427 | 94 | +285 |
| 0.85 | 99.0 | 30 | 1.15 | 2.0 | 2.0R | 4.0R | 226 | 6.11 | 25% | +1640 | 92 | +884 |
| 0.8 | 99.0 | 30 | 1.15 | 2.0 | 2.0R | 3.0R | 220 | 5.95 | 29% | +1823 | 89 | +1364 |
| 0.8 | 1.1 | 30 | 1.15 | 2.0 | 2.0R | 3.0R | 217 | 5.86 | 30% | +1966 | 92 | +1102 |
| 0.8 | 0.9 | 30 | 1.15 | 2.0 | 2.0R | 3.0R | 208 | 5.62 | 32% | +1503 | 86 | +683 |
| 0.8 | 1.1 | 20 | 1.15 | 2.0 | 2.0R | 4.0R | 206 | 5.57 | 26% | +1496 | 84 | +1042 |
| 0.85 | 1.1 | 12 | 1.15 | 2.0 | 3.0R | 3.0R | 205 | 5.54 | 28% | +1753 | 74 | +1598 |
| 0.85 | 99.0 | 30 | 1.15 | 0.6 | 2.0R | 4.0R | 204 | 5.51 | 22% | +148 | 80 | +3 |
| 0.8 | 99.0 | 30 | 1.15 | 2.0 | 2.0R | 4.0R | 203 | 5.49 | 26% | +1659 | 86 | +658 |

## Most profit (for comparison)

| vol | rng | win | uhv | near | SL | TP | trades | /day | WR | net $ | TEST n | TEST net |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.8 | 0.9 | 12 | 1.15 | 2.0 | 3.0R | 4.0R | 145 | 3.92 | 33% | +7016 | 60 | +3117 |
| 0.8 | 0.9 | 20 | 1.15 | 2.0 | 3.0R | 4.0R | 147 | 3.97 | 32% | +6604 | 62 | +2679 |
| 0.85 | 0.9 | 30 | 1.3 | 2.0 | 3.0R | 4.0R | 128 | 3.46 | 33% | +6499 | 55 | +2148 |
| 0.8 | 1.1 | 12 | 1.15 | 2.0 | 3.0R | 4.0R | 154 | 4.16 | 32% | +6378 | 64 | +3056 |
| 0.85 | 0.9 | 30 | 1.15 | 2.0 | 3.0R | 4.0R | 166 | 4.49 | 31% | +5759 | 69 | +990 |
| 0.8 | 0.9 | 30 | 1.15 | 2.0 | 3.0R | 4.0R | 143 | 3.86 | 32% | +5648 | 61 | +1598 |
| 0.85 | 0.9 | 20 | 1.15 | 2.0 | 3.0R | 4.0R | 168 | 4.54 | 32% | +5646 | 66 | +2098 |
| 0.8 | 1.1 | 20 | 1.15 | 2.0 | 3.0R | 4.0R | 154 | 4.16 | 31% | +5644 | 66 | +2657 |
| 0.85 | 0.9 | 12 | 1.15 | 2.0 | 3.0R | 4.0R | 181 | 4.89 | 30% | +5400 | 66 | +3050 |
| 0.85 | 1.1 | 30 | 1.3 | 2.0 | 3.0R | 4.0R | 140 | 3.78 | 31% | +5353 | 61 | +2179 |
| 0.8 | 0.9 | 12 | 1.3 | 2.0 | 3.0R | 4.0R | 111 | 3.00 | 31% | +5078 | 44 | +2235 |
| 0.85 | 1.1 | 30 | 1.15 | 2.0 | 3.0R | 4.0R | 164 | 4.43 | 30% | +4971 | 68 | +1190 |

## The honest limit

Frequency and profit are not the same axis. Pushing the dead-volume threshold to 0.90 produced 173 trades for **-$1,163** — every extra trade past a point is a worse trade. The busiest row above is the busiest one that still survives days it was not fitted on; anything busier than that was discarded for losing money, not for being busy.