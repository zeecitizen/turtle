# Optimizer Token — Reference for Claude

This file explains the analysis token system built into the Turtle Trader indicator (`turtle.pine`).
When the user asks you to "generate a token" from their trade history, follow this guide.

---

## What is the token?

The indicator has a text input called **"Derive optimizations from Claude's analysis — Enter Token"** (`pAT`).
Entering a token here causes the indicator to display real MT5 execution stats alongside its simulated stats.

A second toggle **"Apply token corrections to labels (slip-adjusted entry & P&L)"** (`pATon`) — when ON —
adjusts label entry prices and TP/SL profit figures using the slippage fields in the token.
This makes labels reflect what actually happened in MT5 rather than Pine's simulated breakout-level entry.

This is a **display calibration tool only** — it does NOT change strategy logic, lot sizing, or alerts.

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
| `lots` | float | Lot size used (for context/scaling only) |
| `slipB` | float | Bull IOE entry slippage: MT5 fill − Pine entry (pts). Positive = MT5 filled above Pine's breakout level |
| `slipS` | float | Bear IOE entry slippage: MT5 fill − Pine entry (pts). Usually negative = MT5 filled below Pine's breakout level |

Fields 6–8 (`lots`, `slipB`, `slipS`) are optional. Omit if not available.

**Slippage sign convention:**
- `slipB > 0` → MT5 bull fill is above Pine's breakout level (paying spread, unfavorable)
- `slipS < 0` → MT5 bear fill is below Pine's breakout level (bear sells lower = smaller profit / larger loss)

---

## What the indicator does with the token

**Panel Row 9 (UHV strategy)** — appends a line:
```
Real MT5: 3/7 (43%)  avg +$5.97 / -$5.10
```

**Signal labels** — when `pATon` is ON, each UHV/EVR IOE signal label:
- Shows slip-adjusted entry as the main entry: `Entry: 2110.60`
- Appends Pine's original entry in parentheses: `(Pine: 2111.34)`
- Computes TP/SL profit figures using the adjusted entry instead of Pine's breakout level

---

## How to generate a token

### Step 1 — Collect MT5 trade history

The user will show you a screenshot of their MT5 trade history table. Extract:
- Each trade: direction (buy/sell), entry price, SL, TP, close price, P&L in USD
- Count wins (TP hit = green close) and losses (SL hit = red close)

### Step 2 — Get Pine label entry prices (for exact slipB/slipS)

Pine's assumed entry (`_entry` = the breakout level) is shown in the signal label on the chart:
```
Entry: 2114.12
```
This is the breakout level Pine uses for its P&L simulation. MT5 fills at market price.

**slipB (bull)** = MT5 fill − Pine label entry
**slipS (bear)** = MT5 fill − Pine label entry

Average across multiple trades in the same direction to smooth noise.

### Step 3 — Compute stats

```
avgWin  = sum of winning P&Ls / number of wins     (positive number)
avgLoss = sum of losing P&Ls / number of losses     (NEGATIVE number)
```

### Step 4 — Output the token

```
v1,<wins>,<total>,<avgWin>,<avgLoss>,<lots>,<slipB>,<slipS>
```

---

## Worked example (session 22-23, 2026-03-22)

**MT5 trades (XAUUSD 1m, UHV Bear Only, 8 lots fixed):**

| Signal | Dir  | Pine Entry | MT5 Fill | Result | P&L     |
|--------|------|-----------|---------|--------|---------|
| #1398  | Bull | 3021.70   | 3022.00 | SL hit | −$4.64  |
| #1399  | Bear | ~2113.6   | ~2113.4 | SL hit | −$1.52  |
| #1400  | Bear | 2110.90   | 2110.16 | TP hit | +$9.44  |
| #1401  | Bear | 2111.34   | 2111.14 | TP hit | +$6.40  |
| #1402  | Bear | 2109.98   | 2109.24 | SL hit | −$7.12  |
| #1403  | Bear | 2110.45   | 2109.71 | SL hit | −$7.12  |
| #1404  | Bear | 2111.45   | 2110.71 | TP hit | +$2.08  |

**Stats:**
- wins = 3 (#1400, #1401, #1404), total = 7
- avgWin  = (9.44 + 6.40 + 2.08) / 3 = **$5.97**
- avgLoss = (4.64 + 1.52 + 7.12 + 7.12) / 4 = **$5.10** → token uses **−5.10**
- lots = 8
- slipB = 3022.00 − 3021.70 = **+0.29** (1 bull trade)
- slipS = avg(2110.16−2110.90, 2111.14−2111.34, ...) = **−0.74** (multiple bear labels)

**Generated token:**
```
v1,3,7,5.97,-5.10,8,0.29,-0.74
```

**Effect on labels when `pATon` ON:**
- Bear labels: entry shifts −0.74 pts (e.g. Pine 2111.34 → display 2110.60)
- Bull labels: entry shifts +0.29 pts (e.g. Pine 3021.70 → display 3022.00)
- TP/SL profit figures recalculated from adjusted entry
- Panel shows: `Real MT5: 3/7 (43%)  avg +$5.97 / -$5.10`

---

## Notes

- Always use MT5 actual P&L (not Pine's simulated P&L) for avgWin/avgLoss
- avgLoss must be **negative** in the token
- slipB/slipS are in **price points** (same scale as the chart symbol)
- For XAUUSD: cM = 100, so 1 point slippage on 1 lot = $100 impact — slippage values typically 0.1–2.0 pts
- If the user only has a few trades, note the sample is small; regenerate as more trades accumulate
- Regenerate the token whenever lot size changes significantly or after 20+ new trades
- The `pATon` toggle is separate — token stats (panel row) always show; slip corrections to labels only apply when `pATon` ON

## Token history

| Date       | Token                                    | Trades | Notes |
|------------|------------------------------------------|--------|-------|
| 2026-03-22 | `v1,3,7,5.97,-5.10,8,0.29,-0.74`       | 7      | XAUUSD 1m, 8 lots, UHV Bear Only |
| 2026-03-22 | `v1,16,26,6.44,-8.90,8,-0.14,0.03`     | 26     | ETHUSD 1m, 8 lots, Both directions; 62% WR; slippage near-zero vs XAUUSD |
