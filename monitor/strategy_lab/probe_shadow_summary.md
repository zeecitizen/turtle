# Probe Shadow Analysis — Live Experiment

_Updated: 2026-05-06T23:25:47_
_Probes analyzed: **439**_

## What this tests
For each probe that fired today, did its peak favorable price ever cross
a lower confirm threshold ($0.45, $0.30, $0.20)? If yes, would the
resulting main trade have made or lost money over the next 10 minutes?

## Headline numbers

| Metric | Value |
|--------|-------|
| Probes analyzed | 439 |
| Confirmed at current $0.58 threshold | 291 (66%) |
| Would have confirmed at $0.45 | 303 (69%) |
| Would have confirmed at $0.30 | 329 (74%) |
| Would have confirmed at $0.20 | 345 (78%) |
| Actual probe-only P&L | $+226.01 |
| Avg post-close 120s favorable continuation | $+2.03 |

## Simulated main-trade P&L by threshold

_(if we lowered probeConfirm to that value and let mains run with current trail/fearIdeal)_

| Threshold | Sim main total P&L |
|-----------|-------------------|
| $0.20 | $-2404.00 |
| $0.30 | $-2672.80 |
| $0.45 | $-1861.20 |
| $0.58 | $-1886.80 |

## Probes that current $0.58 missed but $0.45 would have caught

| Count | Sim main total | Avg per missed |
|-------|----------------|---------------|
| 12 | $-855.60 | $-71.30 |

## Last 8 probes (newest first)

| time | dir | actual P&L | MFE | conf 0.58 | conf 0.45 | sim main 0.45 | after 120s |
|------|-----|-----------|-----|-----------|-----------|---------------|-----------|
| 23:29:07 | sell | $+2.34 | $+3.59 | ✓ | ✓ | $+12.40 | $+2.44 |
| 23:25:05 | sell | $+3.68 | $+4.72 | ✓ | ✓ | $+8.40 | $+3.93 |
| 23:07:11 | buy  | $-2.98 | $+2.64 | ✓ | ✓ | $+6.00 | $+0.00 |
| 23:12:47 | buy  | $-3.04 | $+0.55 | · | ✓ | $-75.60 | $+0.00 |
| 23:18:11 | buy  | $-3.02 | $+0.00 | · | · | — | $+0.00 |
| 22:44:16 | sell | $-3.13 | $+0.53 | · | ✓ | $-70.00 | $+0.00 |
| 22:28:29 | sell | $+3.19 | $+4.26 | ✓ | ✓ | $+16.00 | $+3.54 |
| 22:31:05 | sell | $-3.33 | $+0.00 | · | · | — | $+0.00 |