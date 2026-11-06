"""Summarise testing/hybrid_blend_runs.jsonl: per run, Saad / VSISA / combined win rate per position + net."""
import json, re
from pathlib import Path

rows = {}
for ln in open(Path(r"C:\Users\zeesh\turtle\testing\hybrid_blend_runs.jsonl"), encoding="utf-8"):
    r = json.loads(ln)
    rows[(r["variant"], r["per"])] = r          # last run of a variant wins


def eng(r, name):
    for h in r.get("hybrid", []):
        m = re.search(rf"\[HYBRID-TAG\] {name} \| all \| trades (\d+) wins (\d+) WR [\d.]+% net ([-\d.]+)", h)
        if m:
            return int(m[1]), int(m[2]), float(m[3])
    return 0, 0, 0.0


for per in ("julo", "full"):
    print(f"\n=== {per} ===")
    print(f"{'variant':16} {'saad n':>6} {'WR':>6} {'vsisa n':>7} {'WR':>6} {'comb n':>6} {'WR':>6} {'net':>10} {'dd':>18} {'net/dd':>6}")
    for (v, p), r in rows.items():
        if p != per:
            continue
        sn, sw, _ = eng(r, "SAAD"); vn, vw, _ = eng(r, "VSISA")
        cn, cw = sn + vn, sw + vw
        f = lambda w, n: f"{100 * w / n:5.1f}%" if n else "   -  "
        print(f"{v:16} {sn:6} {f(sw, sn)} {vn:7} {f(vw, vn)} {cn:6} {f(cw, cn)} {r['net']:10.0f} {r['dd']:>18} {r.get('net_per_dd') or 0:6}")

print("\n=== tag splits (no gates: side_by_side) ===")
for per in ("julo", "full"):
    r = rows.get(("side_by_side", per))
    if r:
        print(f"-- {per}")
        for h in r["hybrid"]:
            if "HYBRID-TAG" in h and "gate:" not in h:
                print("  " + h.replace("[HYBRID-TAG] ", ""))
