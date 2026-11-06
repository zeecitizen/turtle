"""raw.py FEATURE [edges...] - raw loss counts and rates per bin (secure / base x train / test) + O/E vs the random-entry null."""
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
N = pickle.load(open(os.path.join(HERE, "emp_null_K60.pkl"), "rb"))
for st in ("secure", "base"):
    pm = {r[0]: r[4] / max(r[5], 1) for r in N[st]}
    for r in D[st]:
        r["_p0"] = pm[r["_id"]]


def show(f, edges=None, Q=5, stacks=("secure", "base")):
    if edges is None:
        x_all = np.array([r[f] for r in D["secure"]], float)
        edges = np.unique(np.quantile(x_all, np.linspace(0, 1, Q + 1)[1:-1]))
    print(f"{f} edges {np.round(edges, 3).tolist()}")
    for st in stacks:
        for part in ("tr", "te"):
            R = [r for r in D[st] if r["_tr"] == (part == "tr")]
            x = np.array([r[f] if not callable(f) else f(r) for r in R], float)
            b = np.searchsorted(edges, x, side="right")
            cells = []
            for i in range(len(edges) + 1):
                S = [r for r, bb in zip(R, b) if bb == i]
                L = sum(1 for r in S if not r["_win"]); E = sum(r["_p0"] for r in S)
                cells.append(f"{L:3d}/{len(S):4d} {100 * L / max(len(S), 1):4.1f}% oe{L / max(E, 1e-9):4.2f}")
            print(f"  {st:6s} {part}  " + " | ".join(cells))


if __name__ == "__main__":
    f = sys.argv[1]
    e = [float(z) for z in sys.argv[2:]] or None
    show(f, e)
