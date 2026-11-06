"""carve_perm.py - if the 30 secure losses fell on random secure trades (same count per half), how often would SOME humps x ER16 box of
>= 287 trades (the zee100 box size) be loss-free? (HYPOTHESIS ONLY)"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import api_tight as AT  # noqa: E402

T = AT.STACKS["secure"]
hu = np.array([t["humps"] for t in T]); er = np.array([t["er16"] for t in T]); L = np.array([not t["win"] for t in T])
tr = np.array([t["t_dec"] < AT.SPLIT for t in T])
grid = np.round(np.arange(0.15, 0.4501, 0.01), 2)
M = []
for a in range(2, 6):
    for b in range(a, 6):
        for i, lo in enumerate(grid):
            for hi in grid[i + 1:]:
                m = (hu >= a) & (hu <= b) & (er >= lo) & (er < hi)
                if m.sum() >= 287:
                    M.append(m)
M = np.array(M, dtype=np.float32)
print("boxes >= 287 trades:", len(M), " loss-free in the real data:", int(np.sum(M @ L.astype(np.float32) == 0)))
rng = np.random.default_rng(3)
itr, ite = np.nonzero(tr)[0], np.nonzero(~tr)[0]
ntr, nte = int(L[tr].sum()), int(L[~tr].sum())
hits = 0
NS = 2000
for _ in range(NS):
    y = np.zeros(len(T), np.float32)
    y[rng.choice(itr, ntr, replace=False)] = 1
    y[rng.choice(ite, nte, replace=False)] = 1
    hits += bool(np.any(M @ y == 0))
print(f"random placement of the same 22 + 8 losses: a loss-free box of >= 287 trades exists in {hits}/{NS} = {100 * hits / NS:.1f}% of draws")
