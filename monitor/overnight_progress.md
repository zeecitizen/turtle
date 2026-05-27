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
