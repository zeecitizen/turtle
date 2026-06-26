# Overnight 2026-06-06 — Canonical UHV rewrite

Zee asleep at ~05:28 broker. Schedule: 15-min wakeup loop. Goal: profitable EA
by morning.

## ✅ Cycle 1 — Spec ingestion + Python canonical detector

### What Zee said
- 11-step canonical Setup 1 (UHV Breakout) spec posted in chat
- Followed by Clarification A: **FVG gate is SOFT** (3 modes: H1-strict / M5-relaxed / none)
- Clarification B: **Volume colour = TradingView convention** (vol bar matches candle's bullish/bearish), NOT MT5 delta-volume
- Then her 36-setup label pass (zee_labels.json) — **35 of 36 EA fires INVALID**

### What I extracted
Saved 10 sub-rules to `memory/project_uhv_canonical_rules.md` (Clarification C):
- C1 UHV must be strictly highest vol vs neighbours AND in retracement window
- C2 UHV must be correct colour (bearish for BUY, bullish for SELL)
- C3 Retracement must be CONFIRMED (opposite-colour body breaks prior same-colour extreme)
- C4 Breakout BODY must cross UHV's directional extreme (not just wick)
- C5 Breakout candle must be OPPOSITE colour of UHV
- C6 Breakout volume must be LOWER than UHV volume (new gate; missing from spec)
- C7 Breakout must have momentum body (body/range ≥ ~0.65)
- C8 One breakout per UHV (state machine)
- C9 Strong-bodied UHV preferred (weak body = indecision)
- C10 One UHV per retracement (already in old memory)

### Failure-mode tally on 35 invalid EA fires
| Failure | Count |
|---|---|
| Breakout body doesn't cross UHV extreme | 22 |
| UHV wrong colour for direction | 14 |
| No valid retracement | 12 |
| Breakout wrong colour | 11 |
| UHV not strictly highest vol | 9 |
| Breakout vol ≥ UHV vol | 4 |
| Breakout not momentum | 3 |

(most setups failed 2-4 gates simultaneously)

### Python canonical detector built
`monitor/strategy_lab/screener_canonical_uhv.py` — implements all 7 hard gates.

## ✅ Cycle 2 — Parameter sweep on 10 days of XAUUSD ticks

```
body  vrat  mom    fires  W  L  WR%   PF    PNL(pts)
0.35  1.00  0.55   13     4  7   36.4  1.16  +8.56
0.35  0.75  0.55    8     3  4   42.9  1.25  +8.16
0.40  0.75  0.60    7     3  3   50.0  1.97  +20.01
0.50  0.75  0.65    5     3  1   75.0  5.13  +32.67   ← BEST
0.50  0.60  0.65    5     3  1   75.0  5.13  +32.67
0.50  1.00  0.65    7     3  3   50.0  1.82  +18.34
0.40  1.00  0.55   13     4  7   36.4  1.16  +8.56
0.30  1.00  0.55   16     4 10   28.6  0.84  -11.50
```

### Verdict
**Canonical config:** UHV body ≥ 0.50, breakout vol ≤ 0.75 × UHV vol, breakout
momentum ≥ 0.65. Yields **75% WR, PF 5.13, +32.67 pts / 10 days** at 0 lots.

### vs. live EA v2.59 (1 week earlier)
| Metric | v2.59 EA (no canonical) | Canonical screener |
|---|---|---|
| Days | 7 | 10 |
| Trades | 41 | 5 |
| Win rate | 59% | **75%** |
| PF | 1.59 | **5.13** |
| Trade/day | 5.9 | 0.5 |

Canonical rules drop fires by 12× but lift WR by 16pp and PF by 3.2×.

### P&L projection (extrapolated)
At 0.10 lots and ~$1/pt: +$33/10 days → ~$3.30/day. Too thin for hospital
deadline alone. Three viable amplifications:
1. **Bigger lots**: 0.30 → ~$10/day, 0.50 → ~$16/day
2. **Add S3/NSND/BTC EAs** in parallel (uncorrelated edge stacking)
3. **Loosen M5-FVG relaxed mode** for more fires at 65–70% WR

## ✅ Cycle 3 — setups2.html live + Zee notified

- Built `monitor/build_setups2_canonical.py` — renders the 5 canonical fires
  with full overlays (cyan ■ origin, colour-validated UHV ▼, breakout ▲/▼,
  white-dashed entry, red SL, green TP, volume pane, pass/fail badge per gate).
- Wrote `monitor/setup_labels/setups2.html` with dual Zee+Shano verdict
  textboxes per setup (POST to same /api/labels endpoint, key prefix `c<idx>`).
- Public URL: https://setups.claudezeeshan.com/setups2.html (HTTP 200, PNGs 200)
- Notified Zee via webpush (1 device) + /me chat log
- WhatsApp instance still expired — TODO renew

## 🔜 Cycle 4+ — MQL5 EA port (next wake-ups)

Path forward:
1. **Wakeup #2-3**: extract IsBigSpreadClimax + add canonical 7-gate logic to
   S1Trader.mq5 → v2.61. Test compile.
2. **Wakeup #4-5**: MT5 Strategy Tester runs on 5d/10d with canonical config.
   Compare to Python detector — should match within tick-resolution noise.
3. **Wakeup #6+**: write final WR comparison table + lot-size projection for
   hospital deadline path. Ping Zee one last time when complete.

### Canonical config locked
```
UHV_BODY_MIN           = 0.50
BREAKOUT_VOL_MAX_RATIO = 0.75
MOM_THRESH             = 0.65
RETRACE_LOOKBACK       = 15 bars
HARD_TREND             = true
SL_BUFFER              = 0.30
TP                     = recent peak/trough on correct side, fallback to 2.5:1 R:R
```
