"""scan.py - tail loss rates of every feature on train and test (hypothesis generation only)."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
z = np.load(os.path.join(HERE, "feat.npz"))
X, keys, y, tr, ids = z["X"], list(z["keys"]), z["y"], z["train"], list(z["ids"])
base = y.mean()


def tail(col, thr, above):
    m = X[:, col] >= thr if above else X[:, col] <= thr
    out = []
    for part in (np.ones_like(tr), tr, ~tr):
        mm = m & part
        n, L = mm.sum(), y[mm].sum()
        bl = y[part].mean()
        out.append((n, L, (L / n / bl) if n else 0))
    return out


if __name__ == "__main__":
    want = sys.argv[1:] or keys
    for kname in want:
        col = keys.index(kname)
        x = X[:, col]
        qs = np.unique(np.percentile(x, [2, 5, 10, 20, 80, 90, 95, 98]))
        line = []
        for q in qs:
            for above in (False, True):
                if (above and q < np.median(x)) or (not above and q > np.median(x)):
                    continue
                a, b, c_ = tail(col, q, above)
                if a[0] < 30:
                    continue
                line.append(f"{'>=' if above else '<='}{q:.3g}: n{a[0]} L{a[1]} x{a[2]:.2f} [tr x{b[2]:.2f} {b[1]}L te x{c_[2]:.2f} {c_[1]}L]")
        print(f"== {kname}")
        for s in line:
            print("    " + s)
