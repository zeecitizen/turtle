# NS/ND walk-forward — 2026-08-04

The overnight sweep found relaxations worth up to +$2,161. This asks whether any of them survive being (a) combined and (b) measured on days the choice never saw.

**Train** = oldest 22 tick-days.  **Test** = newest 15, held out.

Exit fixed at SL 3R / TP 4R, 0.1 lots, spread charged. 

## baseline (his lessons, literally)

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 8 | 6 | 25% | +131.95 | +21.99 |
| train | 6 | 5 | 33% | +237.95 | +47.59 |
| **TEST (unseen)** | 2 | 1 | 0% | -106.00 | -106.00 |

→ **inconclusive — only 2 test trades**

## dead-vol 0.60

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 30 | 13 | 30% | +2160.80 | +166.22 |
| train | 22 | 10 | 27% | +1501.80 | +150.18 |
| **TEST (unseen)** | 8 | 3 | 38% | +659.00 | +219.67 |

→ **PASSES out-of-sample**

## dead-vol 0.75

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 78 | 22 | 29% | +1203.81 | +54.72 |
| train | 55 | 14 | 22% | -691.75 | -49.41 |
| **TEST (unseen)** | 23 | 8 | 48% | +1895.56 | +236.95 |

→ **PASSES out-of-sample**

## no FVG gate

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 10 | 8 | 40% | +425.55 | +53.19 |
| train | 6 | 5 | 33% | +237.95 | +47.59 |
| **TEST (unseen)** | 4 | 3 | 50% | +187.60 | +62.53 |

→ **PASSES out-of-sample**

## sweep window 20

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 11 | 6 | 36% | +522.85 | +87.14 |
| train | 8 | 5 | 50% | +732.25 | +146.45 |
| **TEST (unseen)** | 3 | 1 | 0% | -209.40 | -209.40 |

→ **fails out-of-sample**

## dead-vol 0.60 + window 20

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 51 | 13 | 31% | +4394.20 | +338.02 |
| train | 39 | 10 | 28% | +3275.30 | +327.53 |
| **TEST (unseen)** | 12 | 3 | 42% | +1118.90 | +372.97 |

→ **PASSES out-of-sample**

## dead-vol 0.60 + no FVG

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 39 | 16 | 36% | +3032.30 | +189.52 |
| train | 29 | 11 | 31% | +2079.70 | +189.06 |
| **TEST (unseen)** | 10 | 5 | 50% | +952.60 | +190.52 |

→ **PASSES out-of-sample**

## dead-vol 0.60 + window 20 + no FVG

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 76 | 16 | 34% | +4415.12 | +275.95 |
| train | 60 | 11 | 28% | +2671.42 | +242.86 |
| **TEST (unseen)** | 16 | 5 | 56% | +1743.70 | +348.74 |

→ **PASSES out-of-sample**

## everything relaxed (0.75 + 20 + no FVG)

| set | trades | days | WR | net $ | $/day |
|---|---|---|---|---|---|
| all 37 days | 237 | 31 | 33% | +7517.30 | +242.49 |
| train | 176 | 20 | 27% | +2971.67 | +148.58 |
| **TEST (unseen)** | 61 | 11 | 49% | +4545.63 | +413.24 |

→ **PASSES out-of-sample**


## How to read this

A row that is large on the full sample but negative or empty on TEST is a row that found the shape of the past, not an edge. Only a configuration that is positive on the held-out days with enough trades to mean anything is worth putting in front of a live account — and even then, live receipts outrank every number here.