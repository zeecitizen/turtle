"""carve_check.py - how special is a loss-free humps x ER16 box? Every box inside the secure zone (humps a..b within 2..5, ER16 lo..hi
on a 0.01 grid within 0.15..0.45), counted on the secure trades: how many boxes of >= 300 trades have ZERO losses? (HYPOTHESIS ONLY)"""
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
free, tot, best = [], 0, None
for a in range(2, 6):
    for b in range(a, 6):
        for i, lo in enumerate(grid):
            for hi in grid[i + 1:]:
                m = (hu >= a) & (hu <= b) & (er >= lo) & (er < hi)
                n = int(m.sum())
                if n < 300:
                    continue
                tot += 1
                if L[m].sum() == 0:
                    free.append((n, a, b, lo, hi))
free.sort(reverse=True)
print(f"boxes with >= 300 secure trades: {tot}; loss-free among them: {len(free)}")
for f in free[:10]:
    print("   n=%d humps %d-%d ER [%.2f, %.2f)" % f)
m = (hu >= 2) & (hu <= 3) & (er >= 0.30) & (er < 0.35)
print("zee100 box humps 2-3 ER [0.30,0.35):", int(m.sum()), "trades,", int(L[m].sum()), "losses; train", int((m & tr).sum()), "test", int((m & ~tr).sum()))
rate_tr, rate_te = L[tr].mean(), L[~tr].mean()
e = (m & tr).sum() * rate_tr + (m & ~tr).sum() * rate_te
print(f"expected losses at the secure zone's own per-half rates: {e:.2f} -> P(0) = {np.exp(-e):.3f}")
print("nearest losses to the box:", [(t["id"], t["humps"], t["er16"]) for t in T if not t["win"] and 0.28 <= t["er16"] <= 0.40])
m2 = er < 0.35
print("secure with 'skip ER16 >= 0.35':", int(m2.sum()), "trades,", int(L[m2].sum()), "losses ->", round(100 * (1 - L[m2].mean()), 2), "% (from", round(100 * (1 - L.mean()), 2), ")")
