"""pattern_matcher.py — the real-time pattern-matching engine.

Uses the VALIDATED rule stencils (rules_stencil.json — all 6 confirmed by Zee
2026-07-26) to classify UHV-breakout setups as they form on the market. For each
candidate setup it extracts the feature signature and matches it against the
stencils:  "This is Rule 1 (Uptrend Momentum Breakout) -> TAKE"  or  "Rule 4
(Wick Breakout) -> SKIP".

- scan(bars)         : classify all completed setups on a bar series (backtest/replay)
- classify(f, side)  : match ONE setup's features -> (rule, action)
- live()             : poll the latest M5 tick CSV, emit a signal when a new setup
                       completes on the last CLOSED bar (writes case_signals.jsonl)

Live execution note: on this ARM64 box MT5 has no Python order API, so live() emits
signals to a file; an MT5 EA (or the sniper bridge) executes them. Detection = here.
"""
from __future__ import annotations
import json, sys, time
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "strategy_lab"))
from build_entry_review_m5 import build_m5, detect_full
from case_engine import extract_features, describe
import screener_canonical_uhv_m1 as S

HERE = Path(__file__).parent
STENCIL = json.loads((HERE / "rules_stencil.json").read_text(encoding="utf-8"))
TAKE = [r for r in STENCIL["rules"] if r["action"] == "TAKE"]
SKIP = [r for r in STENCIL["rules"] if r["action"] == "SKIP"]
SIGNALS = HERE / "case_signals.jsonl"
UHV_DOMINANT_MIN = 1.2


def _ok(val, cond):
    if isinstance(cond, bool): return bool(val) == cond
    if isinstance(cond, str):
        if cond in ("up", "down", "range"): return val == cond
        if cond.startswith(">="): return val >= float(cond[2:])
        if cond.startswith("<="): return val <= float(cond[2:])
        if cond.startswith(">"):  return val > float(cond[1:])
        if cond.startswith("<"):  return val < float(cond[1:])
    return True


def match_features(f, side):
    ranging = f["opp_leg"] >= 4 and f["dominance"] < 1.6
    trend = "range" if ranging else ("up" if side == "BUY" else "down")
    return {"trend": trend, "side_leg": f["side_leg"], "dominance": f["dominance"],
            "origin_valid": True,  # detect_full only emits body-break origins
            "uhv_dominant": f["uhv_vol_ratio"] >= UHV_DOMINANT_MIN,
            "uhv_is_peak": bool(f["uhv_is_peak"]), "brk_body": f["brk_body"],
            "brk_wick": f["brk_wick"], "brk_vol_ratio": f["brk_vol_ratio"],
            "brk_first": bool(f["brk_first"])}


def _rule_matches(mf, sig):
    return all(_ok(mf[k], c) for k, c in sig.items() if k in mf)


def classify(f, side):
    """-> (rule_dict, action) for one setup's features."""
    mf = match_features(f, side)
    for r in TAKE:
        if r.get("side") == side and _rule_matches(mf, r["signature"]):
            return r, "TAKE"
    for r in SKIP:
        if _rule_matches(mf, r["signature"]):
            return r, "SKIP"
    return {"id": "—", "name": "no clean match"}, "SKIP"


def scan(bars):
    """Classify every completed setup on a bar series. Returns list of signals."""
    out = []
    for s in detect_full(bars):
        f = extract_features(bars, s["o"], s["u"], s["i"], s["side"])
        rule, action = classify(f, s["side"])
        title, _ = describe(f, s["side"])
        out.append({"time": s["open_t"].strftime("%Y-%m-%d %H:%M"), "side": s["side"],
                    "entry": s["entry"], "sl": s["sl"], "rule": rule["id"],
                    "rule_name": rule["name"], "action": action, "pattern": title})
    return out


def live(poll_sec=20):
    """Poll the newest M5 tick CSV; emit a signal when a NEW setup completes on the
    last CLOSED bar. Emits to case_signals.jsonl (an executor EA acts on TAKE)."""
    seen = set()
    print("[matcher] live loop — watching newest tick CSV for completed setups")
    while True:
        csvs = sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))
        if csvs:
            bars = build_m5(csvs[-2:])
            if len(bars) > 5:
                last_closed_t = bars[-2].t   # -1 may be a forming bar
                for s in scan(bars):
                    key = f"{s['time']}_{s['side']}"
                    st = datetime.strptime(s["time"], "%Y-%m-%d %H:%M")
                    if key in seen or st < last_closed_t - timedelta(minutes=10):
                        continue
                    seen.add(key)
                    s["emitted_utc"] = datetime.utcnow().isoformat(timespec="seconds")
                    with SIGNALS.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(s) + "\n")
                    print(f"[matcher] {s['action']} {s['side']} {s['time']} — {s['rule']} {s['rule_name']}")
        time.sleep(poll_sec)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--days", type=int, default=12)
    args = ap.parse_args()
    if args.live:
        live()
        return
    bars = build_m5(sorted(S.TICK_DIR.glob("shano_ticks_2026-*.csv"))[-args.days:])
    sigs = scan(bars)
    take = [x for x in sigs if x["action"] == "TAKE"]
    print(f"scanned {len(bars)} M5 bars -> {len(sigs)} setups: {len(take)} TAKE / {len(sigs)-len(take)} SKIP\n")
    from collections import Counter
    for rid, n in Counter(x["rule"] for x in sigs).most_common():
        print(f"  {rid}: {n}")
    print("\nTAKE signals:")
    for x in take[:15]:
        print(f"  {x['side']} {x['time']} @{x['entry']} — {x['rule']} ({x['pattern']})")


if __name__ == "__main__":
    main()
