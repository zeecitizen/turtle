"""perm_oe.py - is the best O/E dose-response in scan_oe.py better than luck? Outcomes redrawn as Bernoulli(p0 * stack-half scale) (each
trade's own random-entry null, scaled so the expected count matches the real losses), the whole scan re-run, the MAX score kept per draw.
HYPOTHESIS ONLY."""
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
N = pickle.load(open(os.path.join(HERE, "emp_null_days_K40.pkl"), "rb"))
Q = 4
NS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
rng = np.random.default_rng(11)
cells = []
for st in ("secure", "base"):
    pm = {r[0]: r[4] / max(r[5], 1) for r in N[st]}
    for part in ("tr", "te"):
        R = [r for r in D[st] if r["_tr"] == (part == "tr")]
        p0 = np.array([pm[r["_id"]] for r in R])
        y = np.array([not r["_win"] for r in R])
        scale = y.sum() / p0.sum()
        cells.append((st, part, R, p0, y, np.clip(p0 * scale, 0, 1)))
keys = [k for k in D["secure"][0] if not k.startswith("_")]
pre = []
for f in keys:
    x_all = np.array([r[f] for r in D["base"]], float)
    edges = np.unique(np.quantile(x_all, np.linspace(0, 1, Q + 1)[1:-1]))
    cb = []
    for st, part, R, p0, y, ps in cells:
        x = np.array([r[f] for r in R], float)
        b = np.searchsorted(edges, x, side="right")
        nb = len(edges) + 1
        E = np.bincount(b, weights=p0, minlength=nb)
        cb.append((b, E, nb))
    pre.append((f, cb))


def score_all(ys):
    best, bestf, allsc = 0.0, None, {}
    for f, cb in pre:
        sig = []
        for (b, E, nb), y in zip(cb, ys):
            O = np.bincount(b, weights=y.astype(float), minlength=nb)
            ok = E > 0.5
            if ok.sum() < 3:
                sig.append(np.nan); continue
            oe = O[ok] / E[ok]
            idx = np.arange(nb)[ok]
            if oe.std() == 0:
                sig.append(0.0); continue
            sig.append(np.corrcoef(idx, oe)[0, 1])
        sig = np.array(sig)
        if np.any(np.isnan(sig)):
            sc = 0.0
        else:
            sc = np.min(np.abs(sig)) if (np.all(sig > 0) or np.all(sig < 0)) else 0.0
        allsc[f] = sc
        if sc > best:
            best, bestf = sc, f
    return best, bestf, allsc


obs, obsf, obs_all = score_all([c[4] for c in cells])
print("observed max", round(obs, 3), obsf)
mx = []
for i in range(NS):
    ys = [rng.random(len(c[5])) < c[5] for c in cells]
    m, f, _ = score_all(ys)
    mx.append(m)
mx = np.array(mx)
print(f"null max score over {len(keys)} features, {NS} draws: median {np.median(mx):.3f}  90% {np.quantile(mx, 0.9):.3f}  95% {np.quantile(mx, 0.95):.3f}  99% {np.quantile(mx, 0.99):.3f}")
print("p-value of observed max:", (np.sum(mx >= obs) + 1) / (NS + 1))
top = sorted(obs_all.items(), key=lambda z: -z[1])[:12]
print("observed top:", [(f, round(s, 2)) for f, s in top])
for f, s in top:
    print(f"  {f:16s} {s:.3f}  share of null draws whose MAX >= this: {np.mean(mx >= s):.3f}")
