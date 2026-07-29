"""setup_strength.py — conviction-based position sizing (Zee 2026-07-29).

Scores each setup's STRENGTH from its features and maps it to a lot size, so we risk
tiny on weak setups and scale up on strong ones. Validated on OANDA data: strength
correlates with WR+profit (Q1 weak ~breakeven, Q3-Q4 strong +0.6-0.9pt), and
conviction sizing produced ~5.8x the net of flat 0.1 lots.

Tiers (Zee): weak=0.01 · 1x=0.10 · 2x=0.40 · 3x strongest=0.80.
Amplifies risk: a 0.8-lot loss at the 3pt cap is -$240. Strong setups are ~91% WR.
"""

WEIGHTS = dict(uhv_vol=0.35, uhv_peak=0.15, brk_body=0.20, brk_wick=0.15, dominance=0.15)


def strength(f):
    """0..~1 strength from the setup feature dict (case_engine.extract_features)."""
    return (min(f["uhv_vol_ratio"], 3) / 3 * WEIGHTS["uhv_vol"]
            + (1.0 if f["uhv_is_peak"] else 0.0) * WEIGHTS["uhv_peak"]
            + min(f["brk_body"], 1) * WEIGHTS["brk_body"]
            + max(0.0, 1 - f["brk_wick"] / 0.5) * WEIGHTS["brk_wick"]
            + min(f["dominance"], 3) / 3 * WEIGHTS["dominance"])


def lot_for(st):
    """-> (lots, label) for a strength score."""
    if st >= 0.66: return 0.80, "3x STRONGEST"
    if st >= 0.58: return 0.40, "2x strong"
    if st >= 0.50: return 0.10, "1x normal"
    return 0.01, "weak"
