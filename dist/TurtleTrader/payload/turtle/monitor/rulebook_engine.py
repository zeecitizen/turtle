"""rulebook_engine.py — the stencil matcher.

Loads rulebook.json (the rules Zee curates), extracts features from a candidate
setup (bars + origin/uhv/breakout indices + side), and decides VALID/INVALID:
a setup is VALID iff every ENABLED + REQUIRED rule passes. SOFT rules are quality
flags only. Each rule maps to a `check` function below.

Validation mode: reconstructs the setups Zee already proof-read and reports how
well the current rulebook reproduces his valid/invalid verdicts (the case library).
Run: py monitor/rulebook_engine.py
"""
from __future__ import annotations
import json, sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
import screener_canonical_uhv_m1 as S

RB = Path(__file__).parent / "rulebook.json"


# ── feature helpers ──────────────────────────────────────────────────────
def humps_before(bars, o, lookback):
    day = bars[o].t.date(); lo = o
    while lo > 0 and (o - lo) < lookback and bars[lo - 1].t.date() == day: lo -= 1
    seg = bars[lo:o]
    if len(seg) < 5: return 0.0, 0.0
    up = 0.0; mn = seg[0].l
    for b in seg: mn = min(mn, b.l); up = max(up, b.h - mn)
    dn = 0.0; mx = seg[0].h
    for b in seg: mx = max(mx, b.h); dn = max(dn, mx - b.l)
    return up, dn

def prior_opp_extreme(bars, o, side):
    for k in range(o - 1, max(o - 12, -1), -1):
        if side == "BUY" and bars[k].is_bull: return bars[k].l
        if side == "SELL" and bars[k].is_bear: return bars[k].h
    return None


# ── rule checks: each returns True/False given ctx ───────────────────────
def c_trend_hump(bars, o, u, i, side, p):
    up, dn = humps_before(bars, o, int(p.get("lookback_bars", 45)))
    return (up if side == "BUY" else dn) >= p.get("min_hump_pts", 4.0)

def c_not_ranging(bars, o, u, i, side, p):
    up, dn = humps_before(bars, o, 45)
    s, opp = (up, dn) if side == "BUY" else (dn, up)
    return s >= opp * p.get("dominance", 1.6)

def c_valid_origin(bars, o, u, i, side, p):
    if side == "BUY" and not bars[o].is_bear: return False
    if side == "SELL" and not bars[o].is_bull: return False
    e = prior_opp_extreme(bars, o, side)
    return e is not None and (bars[o].c < e if side == "BUY" else bars[o].c > e)

def c_uhv_in_retrace(bars, o, u, i, side, p):
    U = bars[u]
    col = U.is_bear if side == "BUY" else U.is_bull
    if not col: return False
    if not (o <= u < i): return False
    if u - 1 >= 0 and bars[u - 1].v >= U.v: return False
    if u + 1 < len(bars) and bars[u + 1].v >= U.v: return False
    # highest-vol counter-trend candle in the retracement [o,i)
    for k in range(o, i):
        c = bars[k]; kcol = c.is_bear if side == "BUY" else c.is_bull
        if kcol and c.v > U.v: return False
    return True

def c_first_breakout(bars, o, u, i, side, p):
    lvl = bars[u].h if side == "BUY" else bars[u].l
    for k in range(u + 1, i):
        c = bars[k]
        if side == "BUY" and c.is_bull and c.c > lvl: return False
        if side == "SELL" and c.is_bear and c.c < lvl: return False
    b = bars[i]
    return (b.is_bull and b.c > lvl) if side == "BUY" else (b.is_bear and b.c < lvl)

def c_breakout_colour(bars, o, u, i, side, p):
    return bars[i].is_bull if side == "BUY" else bars[i].is_bear

def c_breakout_vol_lt(bars, o, u, i, side, p):
    return bars[i].v < bars[u].v * p.get("ratio", 1.0)

def c_breakout_body(bars, o, u, i, side, p):
    return bars[i].body_ratio >= p.get("min_body_ratio", 0.5)

def c_breakout_wick(bars, o, u, i, side, p):
    b = bars[i]; rng = b.rng
    wick = (b.h - b.c) if side == "BUY" else (b.c - b.l)
    return (wick / rng) <= p.get("max_wick_ratio", 0.45)

CHECKS = {
    "hump_before_origin": c_trend_hump, "not_both_legs": c_not_ranging,
    "origin_body_breaks_prior": c_valid_origin, "uhv_local_peak_in_retrace": c_uhv_in_retrace,
    "breakout_is_first_cross": c_first_breakout, "breakout_correct_colour": c_breakout_colour,
    "breakout_vol_lt_uhv": c_breakout_vol_lt, "breakout_body_ratio": c_breakout_body,
    "breakout_wick_ok": c_breakout_wick,
}


def evaluate(bars, o, u, i, side, rulebook):
    """Return (valid, failed_required, soft_flags)."""
    failed = []; soft = []
    for r in rulebook["rules"]:
        if not r.get("enabled", True): continue
        fn = CHECKS.get(r["check"])
        if fn is None: continue
        ok = fn(bars, o, u, i, side, r.get("params", {}))
        if not ok:
            if r.get("required", False): failed.append(r["id"])
            else: soft.append(r["id"])
    return (len(failed) == 0), failed, soft


# ── validation against Zee's labelled M5 cases (the real target) ─────────
sys.path.insert(0, str(Path(__file__).parent))
from build_entry_review_m5 import build_m5, detect_full

# Zee's M5 verdicts (from zee_labels.json m5_* proof-reads, 2026-07-24)
ZEE_M5_VALID = {5, 6, 7, 8, 11, 15, 19, 20, 21}
ZEE_M5_SKIP = {14}  # render bug: "no setup marked on photo" — not a rule verdict

def main():
    rb = json.loads(RB.read_text(encoding="utf-8"))
    bars = build_m5(sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))[-8:])
    setups = detect_full(bars)
    print(f"Rulebook v{rb['version']} — {sum(r.get('enabled') for r in rb['rules'])} rules enabled")
    print(f"M5 case library: {len(setups)} setups\n")
    correct = 0; total = 0
    for k, s in enumerate(setups, 1):
        if k in ZEE_M5_SKIP: continue
        valid, failed, soft = evaluate(bars, s["o"], s["u"], s["i"], s["side"], rb)
        zee = k in ZEE_M5_VALID
        match = (valid == zee); correct += match; total += 1
        tag = "OK " if match else "XX "
        print(f"{tag}m5_{k:03d} {s['side']}: engine={'VALID' if valid else 'INVALID'} zee={'valid' if zee else 'invalid'}"
              + ("" if valid else f"  fails={failed}"))
    print(f"\nRulebook reproduces Zee (M5): {correct}/{total} ({100*correct/max(total,1):.0f}%)")


if __name__ == "__main__":
    main()
