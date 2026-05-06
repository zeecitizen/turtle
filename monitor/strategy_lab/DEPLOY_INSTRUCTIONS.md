# Deployment Instructions — Winning Strategy v2 (hour filter)

## Status

- ✅ Backtest **+$300 / 82.9% WR / both bad days positive** on 64-probe sample — see [WINNING_STRATEGY.md](WINNING_STRATEGY.md)
- ✅ EA source updated with `InpSkipBadHours` input + runtime config + hard-coded skip set (hours 4-6, 19-23 broker)
- ✅ EA recompiled clean (12/12 success via install_eas.ps1)
- ✅ Live config (`shano_config.json`) **rolled back to safe values** so the OLD running EA isn't affected mid-session
- ⚠ Running EA is still the OLD `.ex5` — new field `skipBadHours` is inert until reattach

## To activate (~30 seconds)

### Step 1 — Reattach EA

1. In MT5: `Ctrl+N` → Navigator
2. Right-click **Expert Advisors** → **Refresh** (← critical, picks up new .ex5)
3. Right-click chart with ShanoExitManager → **Remove Expert**
4. Drag **ShanoExitManager** from Navigator back onto the chart
5. Click OK in input dialog

### Step 2 — Update `shano_config.json`

File: `C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\shano_config.json`

Edit these 3 fields:
```json
"trailTrigger": 8.0,    →  "trailTrigger": 12.0,
"trailDrop":    2.0,    →  "trailDrop":    4.0,
```

**And add this new field** anywhere in the JSON object:
```json
"skipBadHours": true
```

EA hot-reloads in 5 seconds.

## Verify it's live

After reattach + config save, check `shano_live.json` (or the dashboard at /shano):

```json
"config": {
  "trailTrigger": 12.0,
  "trailDrop": 4.0,
  "skipBadHours": true,    ← THIS PROVES THE NEW EA IS LOADED
  ...
}
```

If `skipBadHours` is missing, the OLD .ex5 is still running — repeat Step 1 with the Refresh.

## Watch in MT5 Experts log

When the filter triggers (broker hour 4-6 or 19-23):
```
ShanoEA: SKIP MAIN — bad hour filter (broker hour 22 in low-liquidity window)
```

When it doesn't trigger (good hour), nothing is logged about the filter — main opens as normal.

## Hour map (broker time)

| Broker hour | Behavior | Why |
|-------------|----------|-----|
| 0-3 | TRADE | Asia/early-London — 88.9% WR in backtest |
| **4-6** | **SKIP** | Pre-Tokyo, thinnest market — 20% WR |
| 7-9 | TRADE | Tokyo |
| 10-12 | TRADE | London open |
| 13-15 | TRADE | London/NY overlap — 100% WR in backtest |
| 16-18 | TRADE | NY |
| **19-23** | **SKIP** | NY close + early Asia, low liquidity |

You'll trade roughly 13 of 24 broker hours.

## To revert (if it underperforms)

Just change one field:
```json
"skipBadHours": false
```

EA picks up in 5s, no reattach.

## What changed since v1 (yesterday's plan)

Yesterday's deploy plan was `dailyBigLossHalt: 1` (halt for day after first big loss). New research showed:

- **F4w (hour filter)**: +$300, fires 35 trades, both days positive
- **dailyHalt=1**: +$259, fires 19 trades, both days positive

The hour filter has **higher P&L AND more shots on goal** because it prevents the bad trades from EVER firing instead of waiting for 1 to hit fearIdeal first. The halt logic is still in the EA as a backup but defaults off (`dailyBigLossHalt: 99`).
