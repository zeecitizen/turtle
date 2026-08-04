# NS/ND overnight study — 2026-08-04

Built M1 bars from **37 tick-days**. Exit held fixed at SL 3R / TP 4R, 0.1 lots, 0.2pt spread charged per trade, so that what moves between rows is the GATE, not the exit.

Baseline = every gate as Zee's lessons state them.

**Baseline: 8 trades over 6 days · 2W/6L · 25% WR · net $+131.95**

## dead-volume threshold (his 'half se bhi kam')

| value | trades | days | WR | net $ |
|---|---|---|---|---|
| 0.4 | 5 | 4 | 20% | -84.30 |
| 0.5  ← current | 8 | 6 | 25% | +131.95 |
| 0.6 | 30 | 13 | 30% | +2160.80 |
| 0.75 | 78 | 22 | 29% | +1203.81 |
| 0.9 | 173 | 34 | 26% | -1163.47 |

## how small the candle must be

| value | trades | days | WR | net $ |
|---|---|---|---|---|
| 0.5 | 2 | 2 | 0% | -161.35 |
| 0.7  ← current | 8 | 6 | 25% | +131.95 |
| 0.9 | 10 | 7 | 20% | -106.65 |
| 1.1 | 13 | 8 | 31% | -110.15 |
| 99.0 | 14 | 9 | 29% | -181.15 |

## distance allowed from the UHV lines (MINE)

| value | trades | days | WR | net $ |
|---|---|---|---|---|
| 0.3 | 7 | 5 | 29% | +249.15 |
| 0.6  ← current | 8 | 6 | 25% | +131.95 |
| 1.0 | 8 | 6 | 25% | +131.95 |
| 2.0 | 8 | 6 | 25% | +131.95 |
| 99.0 | 10 | 7 | 20% | +29.55 |

## how much the UHV must tower

| value | trades | days | WR | net $ |
|---|---|---|---|---|
| 1.0 | 14 | 8 | 21% | -224.40 |
| 1.15 | 14 | 8 | 21% | -224.40 |
| 1.3  ← current | 8 | 6 | 25% | +131.95 |
| 1.6 | 1 | 1 | 0% | -154.10 |

## FVG tap required

| value | trades | days | WR | net $ |
|---|---|---|---|---|
| True  ← current | 8 | 6 | 25% | +131.95 |
| False | 10 | 8 | 40% | +425.55 |

## bars allowed between candle and breakout

| value | trades | days | WR | net $ |
|---|---|---|---|---|
| 4 | 6 | 5 | 0% | -433.35 |
| 8  ← current | 8 | 6 | 25% | +131.95 |
| 12 | 9 | 6 | 33% | +374.90 |
| 20 | 11 | 6 | 36% | +522.85 |


_run took 1.2 min_