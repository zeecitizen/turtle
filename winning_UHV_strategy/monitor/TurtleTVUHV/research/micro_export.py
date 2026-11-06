"""micro_export.py - writes the EA's v1.38 model files (trained on 2023-2025 only) to MT5's Common\\Files:
saad_dtw_paths.csv (label, 32 points per training path) and saad_hmm3.csv / saad_hmm4.csv (S, toxic state, scaling, pi, A, means, variances)."""
import os, numpy as np
import micro
from micro import *

z = np.load(os.path.join(HERE, "micro_feats.npz"))
TR, Pth, L = z["TR"], z["Pth"], z["L"]
with open(os.path.join(COMMON, "saad_dtw_paths.csv"), "w") as f:
    for lab, row in zip(L[TR], Pth[TR]):
        f.write(",".join([str(int(lab))] + [f"{v:.6f}" for v in row]) + "\n")
print("DTW paths:", int(TR.sum()))

tr, st = trades(); D = sim.data("m15"); t15 = D["t15"]
ef, es = sim.emas(int(INP["InpEmaFast"]), int(INP["InpEmaSlow"]), "m15")
X = bar_features(D, ef, es); fit_m = (t15 < T26) & (np.arange(len(t15)) > 300)
mu0, sd0 = X[fit_m].mean(0), X[fit_m].std(0); Zs = (X - mu0) / sd0
jb = np.searchsorted(t15, tr[:, 1], "right") - 2; Lt = (tr[:, 6] <= 0); TRt = tr[:, 1] < T26
for S in (3, 4):
    pi, A_, mu, var = hmm_fit(Zs[fit_m], S)
    al = hmm_filter(Zs, pi, A_, mu, var); st_ = al[jb].argmax(1)
    lr = [Lt[TRt & (st_ == s)].mean() if (TRt & (st_ == s)).sum() >= 30 else 0 for s in range(S)]
    tox = int(np.argmax(lr))
    vals = [S, tox] + list(mu0) + list(sd0) + list(pi) + list(A_.ravel()) + list(mu.ravel()) + list(var.ravel())
    with open(os.path.join(COMMON, f"saad_hmm{S}.csv"), "w") as f:
        f.write(",".join(f"{v:.10g}" for v in vals) + "\n")
    np.save(os.path.join(HERE, f"micro_hmm{S}_ptox.npy"), al[:, tox])
    print(f"HMM{S}: toxic {tox}, loss rates {[round(100 * x, 1) for x in lr]}")
