# Overnight Progress Log

Autonomous 30-min cycles while Zee sleeps. Each entry: health + one research increment.
Rules: research/propose only, no live deploys, no config changes, validate FULL P&L
(walk-forward) not capture, no fabricated numbers. Zee reviews in the morning.

---

## Cycle 1 — 2026-05-27 ~05:09 PKT

**Health:** ✅ S1/S3/S4 alive (0s), ticks live (data_status=live, tick_age 0s),
market OPEN, TurtleTradeLogger publishing open_positions.json, ShanoTickLogger fresh.
Only warning: NsndTrader heartbeat stale — **expected** (NSND is intentionally disabled).
0 open positions. No action needed.

**Research:** Ran `backtest_all_eas_ticks.py` — 19 days real Exness ticks @ 0.10 lots,
walk-forward (train→OOS) baseline of all EAs:

| EA | n | WR | WR_OOS | Total | OOS | $/day | WF |
|----|---|----|--------|-------|-----|-------|----|
| **S1** (M5, TP7.5, sweep+bigSpread) | 93 | 73.1% | 73.2% | **+$2166** | **+$856** | +$114 | ✓ |
| S4b v2.00 (M1, ATR trail) | 300 | 32.0% | 29.9% | +$350 | −$144 | +$18 | ✗ |
| S4 (M1, TP12/SL6) | 288 | 34.4% | 30.5% | +$57 | −$850 | +$3 | ✗ |
| S3 (M5, peak-TP, sweep+wick) | 93 | 73.1% | 70.0% | −$153 | −$263 | −$8 | ✗ |
| S4 old (M1, TP5/SL6) | 299 | 51.2% | 52.8% | −$990 | −$193 | −$52 | ✗ |

(Caveat printed by script: S1/S3 here are WITHOUT the FVG filter — live config may differ.)

**Verdict:**
- S1 is the standout — robust across train+OOS, passes walk-forward. Strongest engine.
- **S3 is net-negative (−$153, OOS −$263) on this config** despite 73% WR → the avg loss
  ($101) dwarfs avg win ($35); TP/SL geometry is the suspect. **Thread for next cycle:**
  why does S3 win often but lose money? Test TP/SL or peak-TP exit variants.
- S4 / S4b / S4-old all fail walk-forward at 0.10 lots — OOS negative. Not deploy-worthy as-is.

Next cycle: dig into S3's win/loss asymmetry (R:R), since high-WR-but-losing = exit problem.

---

## Cycle 2 — 2026-05-27 ~05:46 PKT

**Health:** ✅ S1/S3/S4 alive (4s), ticks live, market OPEN. NSND stale = expected (disabled).
**1 open position** (S3 BUY 0.01 @4518.38, +$3.56, SL 4508.82 / TP 4527.96) — confirms the new
LIVE panel + open_positions.json snapshot render with a real trade. Good.

**Research:** Ran `v230_backtest.py` — the EXACT live v2.30 config (proper SL buffer) at 0.01 lots,
19 days real ticks, walk-forward:

| EA (v2.30 live config) | n | WR | AvgW | AvgL | Total | TRAIN | OOS | WF |
|----|---|----|------|------|-------|-------|-----|----|
| S1 | 197 | ~72% | — | — | — | +$216 | **+$235** | ✅ |
| S3 | 290 | 61.0% | $5.7 | $6.2 | **+$298.6** | +$184 | **+$115** | ✅ |

S3 by side: SELL +$240 (EV +$1.47) carries it; BUY only +$58 (EV +$0.46).

**Verdict — CORRECTION to Cycle 1:** Cycle 1 flagged "S3 loses money / R:R asymmetry."
That was a **mismatched variant** (peak-TP, no-FVG, different SL) — NOT the deployed config.
The actual live **S3 v2.30 is profitable AND walk-forward-positive** (+$298, OOS +$115),
with balanced R:R (AvgW $5.7 ≈ AvgL $6.2). False alarm — retracted. Lesson: always backtest
the EXACT live config, not a lab variant. Both deployed S1 and S3 are healthy.

**Real (smaller) thread:** S3's edge is almost entirely the SELL side (BUY EV +$0.46 vs SELL
+$1.47). Worth *carefully* exploring whether S3 BUYs need a stronger filter — but per-side n is
small, high overfitting risk, so this needs multi-split proof before any change. Next cycle:
test an S3 BUY-side filter idea with multi-split, or move to a fresh BTC/S4 angle.

---

## Cycle 3 — 2026-05-27 ~06:16 PKT

**Health:** ✅ all engines alive (0s), ticks live, market OPEN. NSND stale = expected.
**3 open positions** (S1 BUY + 2× S3 BUY, all 0.01, net ~+$1.4). Today realized +$2.24, 3/3 wins.
LIVE panel showing real multi-position data correctly.

**Research:** Ran `backtest_er_filter.py` — Kaufman Efficiency-Ratio (trend-strength) filter
sweep, thresholds 0.10–0.30, on S1/S3/NSND (19 days real ticks, walk-forward). Script uses
old 0.06/0.09 lots so read RELATIVELY (vs-base column).

- **S1: ER filter REJECTED.** Base (ER OFF) strictly best: +$1299 / OOS +$513 / WF✓.
  Every threshold reduces total (vs base −$232 to −$745). S1 is already a clean breakout;
  a regime filter only removes good trades. (Re-confirms prior S1 momentum-filter rejection.)
- **S3: ER filter NOT robust → rejected.** The WF✓ thresholds (≥0.20, ≥0.30) rest on tiny
  samples (OOS n=7 and n=3, 100% WR = overfitting artifact), while ≥0.15 is WORSE than base.
  Non-monotonic, sample-starved. No trustworthy improvement. (Also note: this script's S3 base
  is −$138, a different variant than the live v2.30 +$298 from cycle 2 — don't conflate.)
- NSND: ~4% WR across the board → this script's NSND config is broken; disabled EA, ignored.

**Verdict: REJECTED for both live EAs.** No ER filter to be added to S1 or S3 — would cost money
(S1) or rests on overfit micro-samples (S3). Value here is *not* making a bad change. Aligns
with memory (feedback_validate_profitability_not_capture).

Next cycle: switch angle to BTC (backtest_btc_friday.py) since gold filters are well-explored.
