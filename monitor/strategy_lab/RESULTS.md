# Strategy Lab Results

_Last run: 2026-04-28T18:17:58_  
_History window: 2026.04.28 15:55:45 → 2026.04.28 18:44:04_  
_Trades analyzed: 30_

## Variants ranked by simulated total P&L

| Rank | Variant | Δ vs actual | Sim total | Sim main | Sim wins/loss avg |
|------|---------|-------------|-----------|----------|-------------------|
| 1 | **Hold longer: fearIdeal=120, washout=200** | +125.22 | -88.84 | -96.38 | +9.1 / -12.6 |
| 2 | **Combo: holdLonger + letRunners + stricterProbe** | +121.89 | -92.18 | -99.71 | +8.5 / -12.6 |
| 3 | **Baseline (current live)** | +110.80 | -103.27 | -110.80 | +9.1 / -13.8 |
| 4 | **Tight loss cut: fearIdeal=25** | +110.80 | -103.27 | -110.80 | +9.1 / -13.8 |
| 5 | **Stricter probe confirm: 1.20** | +110.80 | -103.27 | -110.80 | +9.1 / -13.8 |
| 6 | **No bursting: maxBurst=1** | +110.80 | -103.27 | -110.80 | +9.1 / -13.8 |
| 7 | **Smaller main size: probeFail=2.0 + main 0.20 (via override)** | +110.80 | -103.27 | -110.80 | +9.1 / -13.8 |
| 8 | **Let runners run: trigger=15, drop=4** | +107.46 | -106.61 | -114.14 | +8.5 / -13.8 |
| 9 | **Fast trail capture: trigger=4, drop=1** | +94.42 | -119.65 | -127.18 | +6.4 / -13.8 |
| 10 | **Combo: tightCut + fastTrail** | +94.42 | -119.65 | -127.18 | +6.4 / -13.8 |

## Top variant detail

**Hold longer: fearIdeal=120, washout=200**  
Rationale: Shano's actual stated rule (later interview): wait for losing trade to come back, no time limit. Push fearIdeal back so trades can recover.

```json
{
  "fearIdeal": 120.0,
  "fearWashout": 200.0
}
```

Apply with: `python lab.py --apply V2_holdLonger`

## Baseline config (live)
```json
{
  "_comment": "Live runtime config for ShanoExitManager EA. Re-read every tick when mtime changes. Edit any value here and the EA picks it up within ~1s \u00e2\u20ac\u201d no reattach needed.",
  "probeConfirm": 0.58,
  "probeFail": 2.0,
  "probeLots": 0.01,
  "probeTimeout": 50,
  "trailTrigger": 8.0,
  "trailDrop": 2.0,
  "holdLotMax": 0.1,
  "fearIdeal": 25.0,
  "fearWashout": 200.0,
  "maxBurst": 5,
  "burstCooldown": 0,
  "maxPositions": 3,
  "dailyCap": 500.0,
  "sellOnly": false,
  "overrideLots": 0.2
}
```