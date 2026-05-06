# Cousin's Filtered Line Break Strategy — Variant Sweep

Run: 2026-05-05T23:11

## Variants tested

| Variant | Trades | Wins | Losses | WR% | Net P&L |
|---|---|---|---|---|---|
| Strict (cousin's original spec) | 5 | 2 | 3 | 40.0% | $-72.20 |
| Strict + Keltner break (1.5 ATR) | 4 | 2 | 2 | 50.0% | $+18.80 |
| Strict + Keltner break (1.0 ATR) | 5 | 2 | 3 | 40.0% | $-72.20 |
| Strict + MACD-V (vol-normalized) | 4 | 2 | 2 | 50.0% | $+18.80 |
| Strict + CVD alignment | 5 | 2 | 3 | 40.0% | $-72.20 |
| Strict + Keltner + MACD-V + CVD | 4 | 2 | 2 | 50.0% | $+18.80 |
| Loose: indicators only (no LB/vol) | 134 | 38 | 96 | 28.4% | $-1100.30 |
| Loose: indicators + Keltner | 103 | 30 | 73 | 29.1% | $-722.80 |

## Per-trade detail (best variant)

### Strict + Keltner break (1.5 ATR)

#### 2026-04-30 (P&L $+58.10, WR 100.0%)

- 02:45 **buy** entry=4555.77 exit=4557.74 (macd_reverse, 7 bars) → $+58.10

#### 2026-05-01 (P&L $+117.65, WR 100.0%)

- 06:29 **buy** entry=4626.41 exit=4630.37 (macd_reverse, 9 bars) → $+117.65

#### 2026-05-04 (P&L $-156.95, WR 0.0%)

- 06:13 **buy** entry=4611.30 exit=4609.13 (macd_reverse, 4 bars) → $-65.95
- 14:39 **sell** entry=4554.04 exit=4557.04 (stop, 0 bars) → $-91.00

## Comparison to Shano-Zee

Today (2026-05-05) Shano-Zee: +$26.93 / 96 closes / 52% WR / 0 fearIdeal trips.

Best cousin's variant: $+18.80 / 4 trades / 50.0% WR over 5 days.

Cousin's strategy as-implemented does NOT clearly beat Shano-Zee on this sample.
