"""case_engine.py — Case-Based Reasoning DB for UHV-breakout setups (Zee's vision).

Each validated setup becomes a CASE with a feature signature + verdict. A new
setup is classified by matching against the nearest cases (kNN): "this looks like
Case 17 (valid) → take entry." Zee grows the DB by clicking Correct/Wrong on
Claude-proposed labels.

This file:
  - extract_features(bars, o, u, i, side)  -> the signature
  - build_cases()  -> seed the DB from Zee's M5 proof-reads
  - knn_verdict(feat, cases, k)  -> (valid?, nearest_case_id, confidence)
  - main()  -> leave-one-out accuracy of case-matching vs Zee's labels
"""
from __future__ import annotations
import json, sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from build_entry_review_m5 import build_m5, detect_full, retr_zone_start
from rulebook_engine import humps_before, prior_opp_extreme
import screener_canonical_uhv_m1 as S

CASES_FILE = Path(__file__).parent / "cases.json"
FEATS = ["side_leg", "opp_leg", "dominance", "origin_margin", "uhv_vol_ratio",
         "uhv_is_peak", "brk_body", "brk_first", "brk_vol_ratio", "brk_wick", "retr_len"]


def extract_features(bars, o, u, i, side):
    up, dn = humps_before(bars, o, 45)
    side_leg, opp_leg = (up, dn) if side == "BUY" else (dn, up)
    ext = prior_opp_extreme(bars, o, side)
    origin_margin = abs(bars[o].c - ext) if ext is not None else 0.0
    U = bars[u]
    # uhv vol vs 2nd-highest counter-trend candle in retracement
    rs = retr_zone_start(bars, o, side)
    others = [bars[k].v for k in range(rs, i)
              if (bars[k].is_bear if side == "BUY" else bars[k].is_bull) and k != u]
    second = max(others) if others else 1
    uhv_vol_ratio = U.v / max(second, 1)
    is_peak = 1.0 if ((u - 1 < 0 or bars[u-1].v < U.v) and (u + 1 >= len(bars) or bars[u+1].v < U.v)) else 0.0
    b = bars[i]
    lvl = U.h if side == "BUY" else U.l
    first = all(not ((bars[k].is_bull and bars[k].c > lvl) if side == "BUY"
                     else (bars[k].is_bear and bars[k].c < lvl)) for k in range(u + 1, i))
    brk_vol_ratio = b.v / max(U.v, 1)
    brk_wick = ((b.h - b.c) if side == "BUY" else (b.c - b.l)) / max(b.rng, 1e-6)
    return {"side_leg": side_leg, "opp_leg": opp_leg, "dominance": side_leg / max(opp_leg, 0.1),
            "origin_margin": origin_margin, "uhv_vol_ratio": uhv_vol_ratio, "uhv_is_peak": is_peak,
            "brk_body": b.body_ratio, "brk_first": 1.0 if first else 0.0,
            "brk_vol_ratio": brk_vol_ratio, "brk_wick": brk_wick, "retr_len": float(i - o)}


def describe(f, side):
    """Human-readable TITLE + per-feature observations, so Zee can verify Claude
    is noticing the right things and reference setups by name."""
    dirw = "uptrend" if side == "BUY" else "downtrend"
    leg, dom, opp = f["side_leg"], f["dominance"], f["opp_leg"]
    if opp >= 4 and dom < 1.6:      trend_t, trend_w = "ranging/choppy", "Ranging"
    elif leg >= 6 and dom >= 2:     trend_t, trend_w = f"strong {dirw}", f"Strong {dirw}"
    elif leg >= 4:                  trend_t, trend_w = f"mild {dirw}", dirw.capitalize()
    else:                           trend_t, trend_w = "weak/unclear trend", "Weak-trend"
    bb, bw, bv = f["brk_body"], f["brk_wick"], f["brk_vol_ratio"]
    if bb >= 0.55 and bw < 0.35:    brk_t, brk_w = "momentum breakout", "momentum-breakout"
    elif bw >= 0.4:                 brk_t, brk_w = "wick/indecision breakout", "wick-breakout"
    else:                           brk_t, brk_w = "weak-bodied breakout", "weak-breakout"
    uv = f["uhv_vol_ratio"]
    notes = [
        f"trend: {trend_t} (leg {leg:.1f}pt, {dom:.1f}x opp)",
        f"origin: {'valid body-break' if f['origin_margin'] > 0 else 'NO body-break'} ({f['origin_margin']:.1f}pt)",
        f"UHV: {'dominant' if uv >= 1.2 else 'marginal'} ({uv:.2f}x next-vol), {'local-peak' if f['uhv_is_peak'] else 'NOT peak'}",
        f"breakout: {brk_t} (body {bb:.2f}, wick {bw:.2f}, vol {bv:.2f}x UHV{' HIGH!' if bv >= 1 else ''})",
    ]
    title = f"{trend_w} · {brk_w}"
    return title, notes


def _stats(cases):
    mu = {}; sd = {}
    for f in FEATS:
        xs = [c["features"][f] for c in cases]
        m = sum(xs) / len(xs); v = sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1)
        mu[f] = m; sd[f] = math.sqrt(v) or 1.0
    return mu, sd

def _dist(fa, fb, mu, sd):
    return math.sqrt(sum(((fa[f] - fb[f]) / sd[f]) ** 2 for f in FEATS))

def knn_verdict(feat, cases, k=3, side=None):
    # side-aware: a BUY candidate is only matched against BUY cases (and SELL vs SELL),
    # because the pattern reasons are side-specific. Fall back to all if too few.
    if side is not None:
        same = [c for c in cases if c.get("side") == side]
        if len(same) >= k: cases = same
    mu, sd = _stats(cases)
    ranked = sorted(cases, key=lambda c: _dist(feat, c["features"], mu, sd))
    top = ranked[:k]
    votes = sum(1 for c in top if c["verdict"] == "valid")
    valid = votes > k / 2
    verdict = "valid" if valid else "invalid"
    # nearest case that AGREES with the majority verdict (so display never contradicts)
    near = next((c["id"] for c in ranked if c["verdict"] == verdict), ranked[0]["id"])
    agree = votes if valid else (k - votes)
    return valid, near, agree / k


# ── seed DB from Zee's M5 proof-reads ────────────────────────────────────
ZEE_M5_VALID = {5, 6, 7, 8, 11, 15, 19, 20, 21}
ZEE_M5_SKIP = {14}
M5_REASON = {  # Zee's words (short)
    1: "wick breakout, indecision", 2: "ranging, no clear trend", 3: "wick not body close",
    4: "wick not body close", 5: "strong bodied breakout", 6: "strong bodied breakout",
    7: "valid", 8: "valid", 9: "breakout not momentum", 10: "selling in uptrend",
    11: "valid", 12: "wick breakout, weak", 13: "invalid origin (no body break)",
    15: "valid", 16: "not proper downtrend", 17: "not proper downtrend",
    18: "choppy, no clear downtrend", 19: "valid but weak-bodied breakout",
    20: "valid", 21: "valid", 22: "not a strong downtrend",
}

def build_cases():
    bars = build_m5(sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))[-8:])
    setups = detect_full(bars)
    cases = []
    for k, s in enumerate(setups, 1):
        if k in ZEE_M5_SKIP: continue
        f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
        cases.append({"id": f"C{k:03d}", "side": s["side"],
                      "verdict": "valid" if k in ZEE_M5_VALID else "invalid",
                      "reason": M5_REASON.get(k, ""), "source": "zee_m5", "features": f})
    return cases


def main():
    cases = build_cases()
    CASES_FILE.write_text(json.dumps({"version": 1, "cases": cases}, indent=2), encoding="utf-8")
    print(f"Case DB seeded: {len(cases)} cases "
          f"({sum(c['verdict']=='valid' for c in cases)} valid / {sum(c['verdict']=='invalid' for c in cases)} invalid)")
    # leave-one-out accuracy of case-matching
    ok = 0
    for idx, c in enumerate(cases):
        rest = cases[:idx] + cases[idx+1:]
        valid, nid, conf = knn_verdict(c["features"], rest, k=3, side=c["side"])
        truth = c["verdict"] == "valid"
        ok += (valid == truth)
    print(f"Leave-one-out case-match accuracy: {ok}/{len(cases)} ({100*ok/len(cases):.0f}%)")


if __name__ == "__main__":
    main()
