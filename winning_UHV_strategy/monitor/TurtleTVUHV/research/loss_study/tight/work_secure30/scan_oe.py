"""scan_oe.py - observed / expected losses by feature quintile, expected = each trade's own random-entry null (emp_null_K60.pkl).
A feature that only tracks the spread regime shows O/E ~ flat; adverse selection at the breakout shows O/E rising. HYPOTHESIS ONLY."""
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
N = pickle.load(open(os.path.join(HERE, "emp_null_K60.pkl"), "rb"))
Q = int(sys.argv[1]) if len(sys.argv) > 1 else 4
only = sys.argv[2:]
for st in ("secure", "base"):
    pm = {r[0]: r[4] / max(r[5], 1) for r in N[st]}
    for r in D[st]:
        r["_p0"] = pm[r["_id"]]
keys = [k for k in D["secure"][0] if not k.startswith("_")]
rows = []
for f in keys:
    if only and f not in only:
        continue
    x_all = np.array([r[f] for r in D["base"]], float)
    edges = np.unique(np.quantile(x_all, np.linspace(0, 1, Q + 1)[1:-1]))
    cells, sig = {}, []
    for st in ("secure", "base"):
        for part in ("tr", "te"):
            R = [r for r in D[st] if r["_tr"] == (part == "tr")]
            x = np.array([r[f] for r in R], float)
            b = np.searchsorted(edges, x, side="right")
            O = np.array([sum(1 for r, bb in zip(R, b) if bb == i and not r["_win"]) for i in range(len(edges) + 1)])
            E = np.array([sum(r["_p0"] for r, bb in zip(R, b) if bb == i) for i in range(len(edges) + 1)])
            n = np.array([int(np.sum(b == i)) for i in range(len(edges) + 1)])
            cells[f"{st}_{part}"] = (O, E, n)
            oe = O / np.maximum(E, 1e-9)
            ok = E > 0.5
            if ok.sum() >= 3:
                sig.append(np.corrcoef(np.arange(len(oe))[ok], oe[ok])[0, 1])
            else:
                sig.append(np.nan)
    sig = np.array(sig)
    same = np.all(sig > 0) or np.all(sig < 0)
    rows.append((np.nanmin(np.abs(sig)) if same else 0.0, f, edges, cells, sig))
rows.sort(key=lambda z: -z[0])
for score, f, edges, cells, sig in rows[: (len(rows) if only else 40)]:
    print(f"\n{f}  edges {np.round(edges, 3).tolist()}  trend-corr {np.round(sig, 2).tolist()}  score {score:.2f}")
    for key, (O, E, n) in cells.items():
        print(f"   {key:10s} " + "  ".join(f"[{i}] {o}/{e:.1f} n{nn} O/E {o / max(e, 1e-9):.2f}" for i, (o, e, nn) in enumerate(zip(O, E, n))))
