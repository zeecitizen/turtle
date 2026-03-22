# Optimizer Token — Reference for Claude

This file explains the analysis token system built into the Turtle Trader indicator (`turtle.pine`).
When the user asks you to "generate a token" from their trade history, follow this guide.

---

## What is the token?

The indicator has a text input called **"Derive optimizations from Claude's analysis — Enter Token"** (`pAT`).
Entering a token here causes the indicator to display real MT5 execution stats alongside its simulated stats,
and adds an estimated MT5 fill line to signal labels.

---

## Token format

```
v1,<wins>,<total>,<avgWin>,<avgLoss>,<lots>,<slipB>,<slipS>
```

| Field | Type | Description |
|-------|------|-------------|
| `v1` | literal | Version tag — always `v1` |
| `wins` | int | Number of winning trades (TP hit) in MT5 |
| `total` | int | Total closed trades in MT5 |
| `avgWin` | float | Average winning trade P&L in USD (positive) |
| `avgLoss` | float | Average losing trade P&L in USD (**negative**) |
| `lots` | float | Lot size used (for context only) |
| `slipB` | float | Bull entry slippage: MT5 fill − Pine entry (pts). Positive = filled above Pine's assumed entry |
| `slipS` | float | Bear entry slippage: MT5 fill − Pine entry (pts). Positive = filled above Pine's assumed entry (favorable for sell) |

Fields 6, 7, 8 (`lots`, `slipB`, `slipS`) are optional. Omit them if you don't have the data.

---

## What the indicator does with the token

**Panel Row 9 (UHV strategy)** — appends a line:
```
Real MT5: 2/4 (50%)  avg +$7.92 / -$3.08
```

**Signal labels** — if `slipB`/`slipS` are non-zero, appends under the TP line:
```
Est. MT5 fill: 2114.41 (slip +0.29)
```

---

## How to generate a token

### Step 1 — Collect MT5 trade history

The user will show you a screenshot of their MT5 trade history table. Extract:
- Each trade: direction (buy/sell), entry price, SL, TP, close price, P&L in USD
- Count wins (TP hit = green close) and losses (SL hit = red close)

### Step 2 — Collect PineConnector signal log (for slippage)

The user will show you the PineConnector alert log. Each signal has a comment field like:
```
UHV@2114.61_5:53_#1398#0100000011110000
```
The number after `UHV@` is the **bar close price at signal fire time** (NOT Pine's entry price).

### Step 3 — Collect Pine signal labels (for exact slipB/slipS)

Pine's assumed entry (`_entry` = the breakout level) is shown in the signal label on the chart:
```
Entry: 2114.12
```
This is what Pine uses for its P&L simulation. MT5 fills at a different price (slippage).

**slipB (bull)** = MT5 fill − label Entry price
**slipS (bear)** = MT5 fill − label Entry price

If the user doesn't have the label screenshot for bear signals, estimate slipS from:
`MT5 fill − close@fire` (rough approximation — note it's estimated).

### Step 4 — Compute stats

```
avgWin  = sum of winning P&Ls / number of wins     (positive number)
avgLoss = sum of losing P&Ls / number of losses     (NEGATIVE number)
```

### Step 5 — Output the token

```
v1,<wins>,<total>,<avgWin>,<avgLoss>,<lots>,<slipB>,<slipS>
```

---

## Worked example

**MT5 history (4 trades on ETHUSD, 8 lots fixed):**

| Signal | Dir | Pine Entry | MT5 Fill | Closed At | P&L |
|--------|-----|-----------|---------|-----------|-----|
| #1398 | Buy | 2114.12 (label) | 2114.41 | 2113.83 (SL) | -$4.64 |
| #1399 | Buy | ~2113.64 (est.) | 2113.41 | 2113.22 (SL) | -$1.52 |
| #1400 | Sell | ~2109.44 (est.) | 2109.62 | 2108.44 (TP) | +$9.44 |
| #1401 | Sell | ~2110.81 (est.) | 2111.14 | 2110.34 (TP) | +$6.40 |

**Stats:**
- wins = 2, total = 4
- avgWin = (9.44 + 6.40) / 2 = **7.92**
- avgLoss = (−4.64 + −1.52) / 2 = **−3.08**
- lots = 8
- slipB = 2114.41 − 2114.12 = **+0.29** (from label; 1 data point)
- slipS ≈ avg(0.18, 0.33) = **+0.26** (estimated from close@fire; no bear labels available)

**Generated token:**
```
v1,2,4,7.92,-3.08,8,0.29,0.26
```

---

## Notes

- Always use MT5 actual P&L (not Pine's simulated P&L) for avgWin/avgLoss
- avgLoss must be **negative** in the token
- slipB/slipS are in **price points** (same units as the chart — e.g. for ETHUSD: 1 pt = $1 per lot)
- For XAUUSD: 1 pt = $100 per lot; slippage values will typically be much smaller (e.g. 0.03)
- If the user only has a few trades, note the sample size is small and the token will improve over time
- Regenerate the token each session as more trades accumulate
