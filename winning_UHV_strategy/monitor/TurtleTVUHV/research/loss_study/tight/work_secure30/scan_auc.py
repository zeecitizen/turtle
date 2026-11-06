"""scan_auc.py - every feature's loss-vs-win AUC on secure and base, train and test halves (HYPOTHESIS ONLY)."""
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))


def auc(x, y):
    """P(loss value > win value) with ties half; y True = loss"""
    x = np.asarray(x, float); y = np.asarray(y, bool)
    xl, xw = x[y], x[~y]
    if len(xl) == 0 or len(xw) == 0:
        return np.nan
    allv = np.concatenate([xl, xw])
    from scipy.stats import rankdata
    r = rankdata(allv)
    rl = r[:len(xl)].sum()
    return (rl - len(xl) * (len(xl) + 1) / 2) / (len(xl) * len(xw))


keys = [k for k in D["secure"][0] if not k.startswith("_")]
res = []
for f in keys:
    cells = {}
    for st in ("secure", "base"):
        R = D[st]
        for part, sel in (("tr", lambda r: r["_tr"]), ("te", lambda r: not r["_tr"]), ("all", lambda r: True)):
            S = [r for r in R if sel(r)]
            x = [r[f] for r in S]; y = [not r["_win"] for r in S]
            cells[f"{st}_{part}"] = auc(x, y)
    a = np.array([cells["secure_tr"], cells["secure_te"], cells["base_tr"], cells["base_te"]]) - 0.5
    same = np.all(a > 0) or np.all(a < 0)
    score = np.min(np.abs(a)) if same else 0.0
    res.append((score, f, cells))
res.sort(key=lambda z: -z[0])
print(f"{'feature':18s} {'sec_tr':>7s} {'sec_te':>7s} {'sec_all':>7s} | {'base_tr':>7s} {'base_te':>7s} {'base_all':>8s}  minDev")
for score, f, c in res:
    print(f"{f:18s} {c['secure_tr']:7.3f} {c['secure_te']:7.3f} {c['secure_all']:7.3f} | {c['base_tr']:7.3f} {c['base_te']:7.3f} {c['base_all']:8.3f}  {score:.3f}")
