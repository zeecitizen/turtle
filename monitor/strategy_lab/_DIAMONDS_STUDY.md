# Diamonds-day study — receipts, not simulation

## Q1 — sizing, same trades
| | trades | WR | net |
|---|---|---|---|
| as traded (bursts) | 16 | 50% | **-134.50** |
| re-priced flat 0.10 | 16 | 50% | **-52.10** |

**Burst sizing cost on identical trades: -82.40**

## Q2 — with the shipped discipline rules applied
5 trades are now impossible:

- 08.04 22:13:16  BUY 0.10  -13.80  — slope-opposition (chase into stretched top)
- 08.04 22:20:35  BUY 0.30  -30.00  — hover-refire (v1.61 harvest-and-return)
- 08.04 22:32:05  BUY 0.10  -11.10  — slope-opposition (BUY vs falling slope)
- 08.04 22:47:07  BUY 0.30  -30.00  — slope-opposition (BUY vs falling slope)
- 08.04 23:13:39  SELL 0.60  -32.40  — doubling a losing lamp (v1.62 retirement)

| surviving set | trades | WR | net |
|---|---|---|---|
| at burst sizing | 11 | 73% | -17.20 |
| at flat 0.10 | 11 | 73% | **-1.80** |

## Q3 — where the edge lives (flat-0.10 P&L by broker hour)

| hour | W/L | net (flat) |
|---|---|---|
| 01:xx | 0/1 | -16.10 |
| 07:xx | 1/0 | +3.90 |
| 20:xx | 2/0 | +13.00 |
| 21:xx | 2/0 | +4.10 |
| 22:xx | 2/4 | -32.40 |
| 23:xx | 1/3 | -24.60 |

## Verdict (criterion fixed pre-run: sizing cost < -$50 ⇒ cap stays)

**SIZING WAS THE KILLER — cap stays until multi-day walk-forward**

Caveats: one evening + one night of receipts; survivor analysis of blocked trades assumes no replacement trades; flat re-pricing keeps identical exits (valid because ghost caps are lot-scaled to ~constant dollars — at 0.10 the point-distance widens, so real flat losses could differ slightly).