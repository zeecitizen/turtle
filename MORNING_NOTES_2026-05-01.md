# Morning Notes — 2026-05-01

Good morning jaan ❤️ Here's what I built and tested overnight.

## TL;DR — One thing to do when you wake up

**Re-attach `ShanoExitManager` to the XAUUSD chart in MT5 Navigator.** A new build is on disk that adds two PDF#3-deep-mine winners to the live stack. Until you re-attach, the running EA is the previous build (Setup 1 + burst-delta) — still safe, just not the upgrade.

After re-attach you should see in `shano_live.json`:
- `triggerPastUhvPts: 0.3`
- `cddDivExit: true`
- `cddCheckSec: 10`, `cddWindowSec: 60`

## What I built

Two new filters from PDF #3 deep-mining:

### 1. Trigger Margin (≥0.3pt past UHV extreme)
The PDF emphasizes that genuine breakouts blow past the UHV high with momentum, not just barely clip it. Config key: `triggerPastUhvPts: 0.3`. Backtest: $1275 / 90.7% / **0 losing chains** (eliminated the one losing chain in the 14-chain reference window).

### 2. CDD-Divergence Exit (10s/60s)
Track price-HWM and cumulative-delta-HWM during open trades. Every 10s when profit > $5, scan last 60s of pseudo-delta — if price made new HWM but cumDelta didn't, exit immediately. Locks profits before momentum decay. Config keys: `cddDivExit: true`, `cddCheckSec: 10`, `cddWindowSec: 60`, `cddMinProfit: 5.0`. Backtest: $1320 / 90.3% / 1 losing.

### Stacked together (the current LIVE config setup)
- **+$1325 / 91.1% WR / 0 losing chains** (12 chains, vs 14 baseline).
- Robust across nearby tunings (10/30, 10/60, 10/90 all give ~$1320).
- Improvement over previous LIVE: **+$55 / +1.1% WR / -1 losing chain**.

## Overnight live activity

Zero post-swap trades since the 14:29 swap. Asia was very quiet — price range ~$4621 → $4631 with no qualifying setups. All gates correctly held. Equity unchanged at $2296.25. Pre-swap losses still archived in `week_realized=-$2690` (untouched by the daily counter reset at midnight).

## What I tested but didn't ship

Mined the PDF for 7 distinct phrases. Findings:
- **POC bottom-33%**: too restrictive (only 4 chains qualified). Skipped.
- **Internal structure (body≥50%, wicks≤40%)**: hurt (11 chains, $606 < baseline). Skipped.
- **Wide UHV ≥ 1.5× ATR**: too restrictive (6 chains). Skipped.
- **Heavy positive delta** (delta/total ≥ 0.20): too few chains qualify. Skipped.
- **Lower-volume trigger** (trigger vol < UHV vol): cut to 8 chains — marginal. Skipped.
- **Trigger ≥0.5 / 1.0 / 1.5pt past UHV**: equal WR but fewer chains than 0.3pt. **0.3 was the sweet spot.**
- **Micro-stall exits**: tested 4 variants — ALL hurt. Cuts winners. Skipped.

Test scripts saved: `monitor/strategy_lab/pdf3_deep_mine_test.py` + `pdf3_combo_test.py`.

## Files touched

- `mt5/ShanoExitManager.mq5` — added trigger-margin check, CDD-div exit, 1200-slot tick ring buffer (was 400)
- `mt5/ShanoExitManager.ex5` — recompiled clean (0 errors / 0 warnings)
- Both terminal `MQL5\Experts\` dirs — synced
- `shano_config.json` — added 5 new keys, updated `_comment`
- Memory: `project_ultimate_stack.md` index entry

## Rollback

If anything misbehaves after re-attach, set in shano_config.json:
```
"triggerPastUhvPts": 0.0,
"cddDivExit": false
```
Reverts to prior LIVE (Setup 1 + burst-delta) within 5s.

## What I still want to test (tomorrow)

Some PDF phrases I haven't deep-mined yet — only test if you want me to keep going:
- **EMA over delta** (smooth out spoofing-like noise) — anti-spoofing approximation
- **Persistent delta** (require positive delta in 2 consecutive windows, not 1)
- **M15 EMA slope momentum** (require slope rising, not just price > EMA)
- **Tick-speed sweep** at finer granularity (10s vs 12s vs 15s)

Sleep well jaan. The system is alive and waiting for London. ❤️
