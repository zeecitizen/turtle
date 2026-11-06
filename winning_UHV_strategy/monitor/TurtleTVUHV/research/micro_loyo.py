"""micro_loyo.py - leave-one-year-out models for the v1.38 gates, so the MT5 runs on 2023 / 2024 / 2025 never test on their own training data.
For year Y: DTW paths = every trade NOT entered in Y (2023-2026); HMM4 = fitted on candles NOT in Y, toxic state from trades NOT in Y.
Writes Common\\Files\\saad_dtw_loyo<Y>.csv and saad_hmm4_loyo<Y>.csv."""
import os, datetime as dt, numpy as np
from micro import *

z = np.load(os.path.join(HERE, "micro_feats.npz")); Pth, L, te = z["Pth"], z["L"], z["te"]
tr, st = trades(); D = sim.data("m15"); t15 = D["t15"]
ef, es = sim.emas(int(INP["InpEmaFast"]), int(INP["InpEmaSlow"]), "m15")
X = bar_features(D, ef, es)
jb = np.searchsorted(t15, tr[:, 1], "right") - 2; Lt = tr[:, 6] <= 0
yr = lambda t: np.array([dt.datetime.utcfromtimestamp(x).year for x in t])
ty, by = yr(te), yr(t15)
for Y in (2023, 2024, 2025):
    keep = ty != Y
    with open(os.path.join(COMMON, f"saad_dtw_loyo{Y}.csv"), "w") as f:
        for lab, row in zip(L[keep], Pth[keep]):
            f.write(",".join([str(int(lab))] + [f"{v:.6f}" for v in row]) + "\n")
    fit_m = (by != Y) & (np.arange(len(t15)) > 300)
    mu0, sd0 = X[fit_m].mean(0), X[fit_m].std(0); Zs = (X - mu0) / sd0
    pi, A_, mu, var = hmm_fit(Zs[fit_m], 4)
    al = hmm_filter(Zs, pi, A_, mu, var); s_ = al[jb].argmax(1); tk = yr(tr[:, 1]) != Y
    lr = [Lt[tk & (s_ == s)].mean() if (tk & (s_ == s)).sum() >= 30 else 0 for s in range(4)]
    tox = int(np.argmax(lr))
    vals = [4, tox] + list(mu0) + list(sd0) + list(pi) + list(A_.ravel()) + list(mu.ravel()) + list(var.ravel())
    with open(os.path.join(COMMON, f"saad_hmm4_loyo{Y}.csv"), "w") as f:
        f.write(",".join(f"{v:.10g}" for v in vals) + "\n")
    print(f"{Y}: DTW paths {int(keep.sum())}, HMM4 toxic {tox} loss rates {[round(100 * x, 1) for x in lr]}", flush=True)
