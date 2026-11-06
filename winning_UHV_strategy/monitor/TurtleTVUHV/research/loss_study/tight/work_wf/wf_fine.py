"""wf_fine.py (work_wf) - the walk-forward at 0.01 ER resolution on humps 2-3 (engine): ER min 0.15-0.40 x ER max 0.30-0.60, each run once,
split at 2026-07-01 UTC (fill time). Pick = best in-sample WR with >= 120 in-sample trades, tie-break trades then net; report the other half."""
import json
import os

from common import run, summ, SPLIT, OUT

EMIN = [round(0.15 + 0.01 * i, 2) for i in range(26)]
EMAX = [round(0.30 + 0.01 * i, 2) for i in range(31)]
G = []
for a in EMIN:
    for b in EMAX:
        if a >= b - 1e-9:
            continue
        r = run({"InpUhvSafeErMin": f"{a:.2f}", "InpUhvSafeErMax": f"{b:.2f}"})
        G.append({"key": f"h2-3_er{a:.2f}-{b:.2f}", "mj": summ(r, hi=SPLIT), "jn": summ(r, lo=SPLIT), "all": summ(r)})
lines = [f"{len(G)} humps-2-3 combos at 0.01 ER resolution"]
for IS, OOS, li, lo in (("mj", "jn", "Mar-Jun", "Jul-Nov"), ("jn", "mj", "Jul-Nov", "Mar-Jun")):
    E = sorted([g for g in G if g[IS]["n"] >= 120], key=lambda g: (-g[IS]["wr"], -g[IS]["n"], -g[IS]["net"]))
    p = E[0]
    lines.append(f"choose on {li}: {p['key']} {li} {p[IS]['n']} tr {p[IS]['L']} L WR {p[IS]['wr']}% net {p[IS]['net']:+.2f} -> {lo} {p[OOS]['n']} tr {p[OOS]['L']} L WR {p[OOS]['wr']}% net {p[OOS]['net']:+.2f}")
    for g in E[1:6]:
        lines.append(f"     next: {g['key']} {li} {g[IS]['n']}/{g[IS]['L']}L -> {lo} {g[OOS]['n']}/{g[OOS]['L']}L WR {g[OOS]['wr']}% net {g[OOS]['net']:+.2f}")
    z = [g for g in E if g[IS]["L"] == 0]
    lines.append(f"   {len(z)} combos lossless on {li} (>= 120 tr); their {lo} losses: min {min(g[OOS]['L'] for g in z)}, max {max(g[OOS]['L'] for g in z)}; "
                 f"lossless on both halves: {sum(1 for g in z if g[OOS]['L'] == 0 and g[OOS]['n'] >= 1)}")
print("\n".join(lines))
json.dump(G, open(os.path.join(OUT, "wf_fine.json"), "w"))
open(os.path.join(OUT, "wf_fine.txt"), "w").write("\n".join(lines))
