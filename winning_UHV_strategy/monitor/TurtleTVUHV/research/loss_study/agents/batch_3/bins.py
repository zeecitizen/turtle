"""bins.py - loss rate by feature bin, train vs test (lift = bin loss rate / that half's base)."""
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
R = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
BASE = {True: np.mean([not r["win"] for r in R if r["train"]]), False: np.mean([not r["win"] for r in R if not r["train"]])}


def show(key, nb=10, rows=None, edges=None):
    rows = rows or R
    x = np.array([r[key] for r in rows], dtype=float)
    if edges is None:
        u = np.unique(x)
        if len(u) <= 12:
            edges = list(u) + [u[-1] + 1]
            labels = [f"={e:g}" for e in u]
        else:
            edges = list(np.unique(np.quantile(x, np.linspace(0, 1, nb + 1))))
            edges[-1] += 1e-9
            labels = [f"[{edges[i]:.3g},{edges[i+1]:.3g})" for i in range(len(edges) - 1)]
    else:
        labels = [f"[{edges[i]:.3g},{edges[i+1]:.3g})" for i in range(len(edges) - 1)]
    print(f"--- {key}")
    for i in range(len(edges) - 1):
        m = (x >= edges[i]) & (x < edges[i + 1])
        out = []
        for half in (True, False):
            sel = [r for r, mm in zip(rows, m) if mm and r["train"] == half]
            n = len(sel); L = sum(not r["win"] for r in sel)
            lift = (L / n) / BASE[half] if n else float("nan")
            out.append(f"{'tr' if half else 'te'} n{n:5d} L{L:3d} x{lift:4.2f}")
        print(f"  {labels[i]:22s} " + "   ".join(out))


if __name__ == "__main__":
    keys = sys.argv[1:] or [k for k in R[0] if k not in ("win", "train", "id", "t_in")]
    for k in keys:
        show(k)
