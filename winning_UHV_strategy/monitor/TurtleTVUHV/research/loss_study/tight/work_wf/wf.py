"""wf.py (work_wf) - the walk-forward, from grid_summary.json (grid.py's 588 engine runs).
Direction A: choose the zone on Mar-Jun (fill time < 2026-07-01 UTC) = best Mar-Jun win rate among combos with >= 120 Mar-Jun trades,
tie-break more trades, then higher net; run it on Jul-Nov untouched. Direction B: the same the other way round.
Also: does choosing carry ANY out-of-sample skill? (Spearman of in-sample vs out-of-sample WR over all eligible combos - descriptive only,
nested zones share trades; the pooled out-of-sample WR of the in-sample-100% family vs the eligible average.) Writes wf_out.json / wf_out.txt."""
import json
import os
HERE = os.path.dirname(os.path.abspath(__file__))

import numpy as np

G = json.load(open(os.path.join(HERE, "grid_summary.json")))
ZEE = "h2-3_er0.30-0.35"
MIN_N = 120
lines = []


def P(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True); lines.append(s)


def rank_avg(x):
    x = np.asarray(x, float)
    o = np.argsort(x, kind="mergesort")
    r = np.empty(len(x)); r[o] = np.arange(len(x), dtype=float)
    for v in np.unique(x):                                   # average ranks for ties
        m = x == v
        r[m] = r[m].mean()
    return r


def spearman(a, b):
    ra, rb = rank_avg(a), rank_avg(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def fmt(s):
    return f"{s['n']:4d} tr {s['L']:2d} L WR {s['wr'] if s['wr'] is not None else float('nan'):6.2f}% net {s['net']:+9.2f}"


res = {}
for name, IS, OOS, lab_is, lab_oos in (("A", "mj", "jn", "Mar-Jun", "Jul-Nov"), ("B", "jn", "mj", "Jul-Nov", "Mar-Jun")):
    E = [g for g in G if g[IS]["n"] >= MIN_N]
    E.sort(key=lambda g: (-g[IS]["wr"], -g[IS]["n"], -g[IS]["net"]))
    pick = E[0]
    P(f"\n=== Direction {name}: choose on {lab_is} (>= {MIN_N} {lab_is} trades; {len(E)} of {len(G)} combos eligible), test on {lab_oos} ===")
    P(f"CHOSEN {pick['key']}:  {lab_is} {fmt(pick[IS])}  ->  {lab_oos} {fmt(pick[OOS])}   (whole period {fmt(pick['all'])})")
    P(f"top 15 by {lab_is} WR (tie: trades, net):")
    for g in E[:15]:
        P(f"   {g['key']:20s} {lab_is} {fmt(g[IS])}  |  {lab_oos} {fmt(g[OOS])}")
    fam = [g for g in E if g[IS]["L"] == 0]
    fn, fL = sum(g[OOS]["n"] for g in fam), sum(g[OOS]["L"] for g in fam)
    en, eL = sum(g[OOS]["n"] for g in E), sum(g[OOS]["L"] for g in E)
    owr = [g[OOS]["wr"] for g in fam if g[OOS]["n"]]
    P(f"family of {len(fam)} combos with 0 {lab_is} losses (>= {MIN_N} tr): {lab_oos} pooled {fn} tr {fL} L = WR {100*(1-fL/max(fn,1)):.2f}%  "
      f"(per combo {lab_oos} WR min {min(owr):.2f} / median {np.median(owr):.2f} / max {max(owr):.2f}; "
      f"{sum(1 for g in fam if g[OOS]['L']==0)} of {len(fam)} stay at 0 losses)")
    P(f"all {len(E)} eligible combos: {lab_oos} pooled {en} tr {eL} L = WR {100*(1-eL/max(en,1)):.2f}%  (mean of combo WRs {np.mean([g[OOS]['wr'] for g in E if g[OOS]['n']]):.2f})")
    a = [g[IS]["wr"] for g in E if g[OOS]["n"]]; b = [g[OOS]["wr"] for g in E if g[OOS]["n"]]
    rho = spearman(a, b)
    a2 = [g[IS]["L"] / g[IS]["n"] for g in E if g[OOS]["n"]]; b2 = [g[OOS]["L"] / g[OOS]["n"] for g in E if g[OOS]["n"]]
    P(f"Spearman(in-sample WR, out-of-sample WR) over the {len(a)} eligible combos = {rho:+.3f} (descriptive: nested zones share trades)")
    # quintiles of in-sample WR -> out-of-sample WR
    q = np.quantile(a, [0.2, 0.4, 0.6, 0.8])
    for lo_, hi_, lab in ((-1, q[0], "Q1 worst"), (q[0], q[1], "Q2"), (q[1], q[2], "Q3"), (q[2], q[3], "Q4"), (q[3], 101, "Q5 best")):
        S = [g for g in E if g[OOS]["n"] and (lo_ < g[IS]["wr"] <= hi_)]
        if S:
            n_, L_ = sum(g[OOS]["n"] for g in S), sum(g[OOS]["L"] for g in S)
            P(f"   in-sample WR quintile {lab:8s} ({len(S):3d} combos, IS WR {min(g[IS]['wr'] for g in S):.2f}-{max(g[IS]['wr'] for g in S):.2f}): "
              f"OOS pooled WR {100*(1-L_/n_):.2f}%  mean OOS WR {np.mean([g[OOS]['wr'] for g in S]):.2f}")
    z = next(g for g in G if g["key"] == ZEE)
    rk = next((i + 1 for i, g in enumerate(E) if g["key"] == ZEE), None)
    E2 = sorted([g for g in G if g[OOS]["n"] >= MIN_N], key=lambda g: (-g[OOS]["wr"], -g[OOS]["n"], -g[OOS]["net"]))
    rk2 = next((i + 1 for i, g in enumerate(E2) if g["key"] == ZEE), None)
    P(f"Zee's zone {ZEE}: {lab_is} {fmt(z[IS])} rank {rk}/{len(E)} ; {lab_oos} {fmt(z[OOS])} rank {rk2}/{len(E2)}")
    res[name] = {"chosen": pick, "family_n": len(fam), "family_oos": {"n": fn, "L": fL}, "eligible_oos": {"n": en, "L": eL}, "spearman": rho,
                 "zee_rank_is": rk, "zee_rank_oos": rk2, "eligible": len(E)}

# the zones with 0 losses on BOTH halves (>= 120 trades each) - how many, how big
both = [g for g in G if g["mj"]["n"] >= MIN_N and g["jn"]["n"] >= MIN_N and g["mj"]["L"] == 0 and g["jn"]["L"] == 0]
P(f"\ncombos with 0 losses in BOTH halves (>= {MIN_N} each): {len(both)}: " + ", ".join(f"{g['key']}({g['all']['n']})" for g in sorted(both, key=lambda g: -g['all']['n'])))
whole0 = sorted([g for g in G if g["all"]["L"] == 0], key=lambda g: -g["all"]["n"])
P(f"combos with 0 losses over the whole period: {len(whole0)}; largest: " + ", ".join(f"{g['key']}({g['all']['n']} tr, {g['all']['net']:+.0f})" for g in whole0[:8]))
json.dump(res, open(os.path.join(HERE, "wf_out.json"), "w"), indent=1)
open(os.path.join(HERE, "wf_out.txt"), "w").write("\n".join(lines))
