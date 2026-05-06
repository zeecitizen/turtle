# Filter Relaxation Backtest — 2026-05-05T22:59

Tested 8 relaxations across 5 days. Deployable: 0.

## Summary

| Test | Skips | Allow | Wins | Loss | Fear | Trail | NoGreen | Net P&L | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| UHV margin 0.30 -> 0.15 | 16 | 0 | 0 | 0 | 0 | 0 | 0 | $+0.00 | net negative or zero |
| UHV margin 0.30 -> 0.10 | 16 | 1 | 0 | 1 | 1 | 0 | 0 | $-60.00 | net negative or zero |
| UHV margin 0.30 -> 0.00 | 16 | 1 | 0 | 1 | 1 | 0 | 0 | $-60.00 | net negative or zero |
| Spread mult 1.20 -> 1.50 | 4 | 2 | 1 | 1 | 1 | 1 | 0 | $-9.60 | net negative or zero |
| Spread mult 1.20 -> 2.00 | 4 | 3 | 2 | 1 | 1 | 2 | 0 | $+11.10 | sample too small (<5 trades) |
| Tick-speed 15s -> 25s | 3 | 1 | 1 | 0 | 0 | 1 | 0 | $+37.50 | sample too small (<5 trades) |
| Tick-speed 15s -> 30s | 3 | 1 | 1 | 0 | 0 | 1 | 0 | $+37.50 | sample too small (<5 trades) |
| Tick-speed 15s -> 60s | 3 | 2 | 1 | 1 | 1 | 1 | 0 | $-22.50 | net negative or zero |

## Per-day detail

### UHV margin 0.30 -> 0.15

- 2026-05-04: skips=2, allowed=0, pnl=$+0.00, fear=0
- 2026-05-05: skips=14, allowed=0, pnl=$+0.00, fear=0

### UHV margin 0.30 -> 0.10

- 2026-05-04: skips=2, allowed=0, pnl=$+0.00, fear=0
- 2026-05-05: skips=14, allowed=1, pnl=$-60.00, fear=1

### UHV margin 0.30 -> 0.00

- 2026-05-04: skips=2, allowed=0, pnl=$+0.00, fear=0
- 2026-05-05: skips=14, allowed=1, pnl=$-60.00, fear=1

### Spread mult 1.20 -> 1.50

- 2026-05-05: skips=4, allowed=2, pnl=$-9.60, fear=1

### Spread mult 1.20 -> 2.00

- 2026-05-05: skips=4, allowed=3, pnl=$+11.10, fear=1

### Tick-speed 15s -> 25s

- 2026-05-04: skips=1, allowed=0, pnl=$+0.00, fear=0
- 2026-05-05: skips=2, allowed=1, pnl=$+37.50, fear=0

### Tick-speed 15s -> 30s

- 2026-05-04: skips=1, allowed=0, pnl=$+0.00, fear=0
- 2026-05-05: skips=2, allowed=1, pnl=$+37.50, fear=0

### Tick-speed 15s -> 60s

- 2026-05-04: skips=1, allowed=0, pnl=$+0.00, fear=0
- 2026-05-05: skips=2, allowed=2, pnl=$-22.50, fear=1

