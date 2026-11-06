"""density.py (work_wf) - where the losses sit in (humps, ER16) space, from the prepared stacks (../trades_*.json, decision-time facts).
Loss rate per cell on base (no risk manager, 7626 tr) and secure; the nearest losses to Zee's box (humps 2-3, 0.30 <= ER < 0.35)."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.dirname(HERE)
SPLIT = 1782864000
lines = []


def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); lines.append(s)


for st in ("base", "secure", "tight"):
    T = json.load(open(os.path.join(UP, f"trades_{st}.json")))
    P(f"\n=== {st}: {len(T)} trades, {sum(not t['win'] for t in T)} losses ===")
    edges = [0.0, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 1.01]
    hb = [(-99, 0, "<=0"), (1, 1, "1"), (2, 2, "2"), (3, 3, "3"), (4, 4, "4"), (5, 6, "5-6"), (7, 99, "7+")]
    P("humps \ ER  " + "".join(f"{edges[i]:.2f}-{edges[i+1]:.2f}".rjust(14) for i in range(len(edges) - 1)))
    for lo, hi, lab in hb:
        row = f"{lab:10s} "
        for i in range(len(edges) - 1):
            S = [t for t in T if lo <= t["humps"] <= hi and edges[i] <= t["er16"] < edges[i + 1]]
            n = len(S); L = sum(not t["win"] for t in S)
            row += (f"{L}/{n}" + (f" {100*L/n:.1f}%" if n else "")).rjust(14)
        P(row)
    # half by half for Zee's cell and its neighbours
    for lab, f in (("Zee box h2-3 ER[.30,.35)", lambda t: 2 <= t["humps"] <= 3 and 0.30 <= t["er16"] < 0.35),
                   ("h2-3 ER[.35,.45)", lambda t: 2 <= t["humps"] <= 3 and 0.35 <= t["er16"] < 0.45),
                   ("h2-3 ER[.20,.30)", lambda t: 2 <= t["humps"] <= 3 and 0.20 <= t["er16"] < 0.30),
                   ("h4-6 ER[.30,.35)", lambda t: 4 <= t["humps"] <= 6 and 0.30 <= t["er16"] < 0.35),
                   ("h1 ER[.30,.35)", lambda t: t["humps"] == 1 and 0.30 <= t["er16"] < 0.35),
                   ("all", lambda t: True)):
        S = [t for t in T if f(t)]
        a = [t for t in S if t["t_dec"] < SPLIT]; b = [t for t in S if t["t_dec"] >= SPLIT]
        La = sum(not t["win"] for t in a); Lb = sum(not t["win"] for t in b)
        P(f"   {lab:26s} Mar-Jun {La}/{len(a)} ({100*La/max(len(a),1):.2f}%)   Jul-Nov {Lb}/{len(b)} ({100*Lb/max(len(b),1):.2f}%)")
    # nearest losses to the box
    near = [t for t in T if not t["win"] and 1 <= t["humps"] <= 4 and 0.25 <= t["er16"] < 0.40]
    near.sort(key=lambda t: (t["humps"], t["er16"]))
    P("   losses with humps 1-4 and ER 0.25-0.40: " + ", ".join(f"{t['id']} h{t['humps']} ER{t['er16']:.3f} {t['pnl']:+.0f}" for t in near))

# the ER of Zee-box trades: how many sit within 0.01 of an edge
T = json.load(open(os.path.join(UP, "trades_tight.json")))
Z = [t for t in T if 0.30 <= t["er16"] < 0.35]
er = np.array([t["er16"] for t in Z])
P(f"\nZee-box trades inside tight: {len(Z)}; ER within 0.01 of 0.30: {int((er < 0.31).sum())}, within 0.01 of 0.35: {int((er >= 0.34).sum())}")
L = sorted([t for t in T if not t["win"]], key=lambda t: t["er16"])
P("tight losses: " + ", ".join(f"{t['id']} h{t['humps']} ER{t['er16']:.3f} {t['pnl']:+.1f}" for t in L))
open(os.path.join(HERE, "density_out.txt"), "w").write("\n".join(lines))
