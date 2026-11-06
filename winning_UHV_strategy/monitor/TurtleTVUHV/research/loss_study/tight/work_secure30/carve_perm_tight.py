"""carve_perm_tight.py - the same carving test for the TIGHT box: if the 30 secure losses fell on random secure trades (22 train + 8 test),
how often would SOME humps x ER16 box (humps a..b within 2..5, ER16 on a 0.01 grid within 0.15..0.45) of >= 714 trades hold <= 4
losses? And how special is the real tight box (humps 2-3, ER [0.30, 0.45)) inside the secure trades? (HYPOTHESIS ONLY)"""
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
                m = (hu >= a) & (hu <= b) & (er >= lo) & (er < hi + (1e-9 if hi >= 0.45 else 0))
                if m.sum() >= 714:
                    M.append(m)
M = np.array(M, dtype=np.float32)
real = M @ L.astype(np.float32)
print("boxes >= 714 secure trades:", len(M), "| real data: boxes with <= 4 losses:", int(np.sum(real <= 4)), "| min losses in any:", int(real.min()))
m = (hu >= 2) & (hu <= 3) & (er >= 0.30) & (er < 0.45)
e = (m & tr).sum() * L[tr].mean() + (m & ~tr).sum() * L[~tr].mean()
print(f"tight box inside secure: {int(m.sum())} trades, {int(L[m].sum())} losses; expected at the secure zone's own per-half rates {e:.2f}")
rng = np.random.default_rng(4)
itr, ite = np.nonzero(tr)[0], np.nonzero(~tr)[0]
ntr, nte = int(L[tr].sum()), int(L[~tr].sum())
NS = 2000
hit4, hit_le_real = 0, 0
for _ in range(NS):
    y = np.zeros(len(T), np.float32)
    y[rng.choice(itr, ntr, replace=False)] = 1
    y[rng.choice(ite, nte, replace=False)] = 1
    z = M @ y
    hit4 += bool(np.any(z <= 4))
print(f"random placement: some box of >= 714 trades holds <= 4 losses in {hit4}/{NS} = {100 * hit4 / NS:.1f}% of draws")
