"""feat4.py - spike / volatility-expansion features from bars <= k."""
import os, pickle, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402
A, PIP = api.A, api.PIP
R = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
byid = {t["id"]: api._blind(t) for t in api.TRADES}
for r in R:
    t = byid[r["id"]]; k, s = t["k"], t["side"]
    atr = max(float(A.atr[k]), 1e-6)
    rg = A.h[k - 59:k + 1] - A.l[k - 59:k + 1]
    r["maxrng5_atr"] = float((A.h[k - 4:k + 1] - A.l[k - 4:k + 1]).max()) / atr
    r["maxrng5_med60"] = float((A.h[k - 4:k + 1] - A.l[k - 4:k + 1]).max()) / max(float(np.median(rg)), 1e-6)
    r["maxv5_v60"] = float(A.v[k - 4:k + 1].max()) / max(float(np.mean(A.v[k - 59:k + 1])), 1)
    r["rng15_rng60"] = float(A.h[k - 14:k + 1].max() - A.l[k - 14:k + 1].min()) / max(float(A.h[k - 59:k + 1].max() - A.l[k - 59:k + 1].min()), 1e-6)
    r["atr_ratio"] = atr / max(float(np.mean(A.atr[k - 239:k + 1])), 1e-6)     # ATR now vs its 4-hour mean
    r["v60_v1440"] = float(np.mean(A.v[k - 59:k + 1])) / max(float(np.mean(A.v[max(0, k - 1439):k + 1])), 1)
    r["uhv_v_v60"] = t["uhv_v"] / max(float(np.mean(A.v[k - 59:k + 1])), 1)
pickle.dump(R, open(os.path.join(HERE, "feat.pkl"), "wb"))
print("ok")
