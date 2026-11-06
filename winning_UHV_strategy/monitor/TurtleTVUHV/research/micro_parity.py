"""micro_parity.py - do the EA (v1.38, MT5) and research/micro.py compute the same gate scores? Reads Common\\Files\\saad_micro_log.csv
(time, side, DTW score, VPIN, flow, HMM3 P(toxic)) written by the MT5 run with InpMicroLog, recomputes each in Python at the same time."""
import os, numpy as np
from micro import *

rows = np.loadtxt(os.path.join(COMMON, "saad_micro_log.csv"), delimiter=",", ndmin=2)
z = np.load(os.path.join(HERE, "micro_feats.npz")); TR = z["TR"]; Ptr, Ltr = z["Pth"][TR], z["L"][TR]
D = sim.data("m15"); t15 = D["t15"]; ph3 = np.load(os.path.join(HERE, "micro_hmm3_ptox.npy"))
out = []
for t, sd, dsc, v, f, ph in rows[:300, :6]:
    te = t + 0.999                                       # the EA logs whole seconds; its ticks run up to the current one
    q = path(te, sd)
    pd = knn_score(q, Ptr, Ltr, K, BAND, -1) if q is not None else -1
    pv, pf = vpin(te, sd)
    j = np.searchsorted(t15, t, "right") - 2
    out.append((dsc, pd, v, pv, f, pf, ph, ph3[j]))
o = np.array(out)
def rep(n, a, b):
    m = (a >= 0) & np.isfinite(b)
    print(f"{n:12s} n {m.sum():4d}  corr {np.corrcoef(a[m], b[m])[0, 1]:.3f}  mean |diff| {np.abs(a[m] - b[m]).mean():.4f}  exact-ish (<1e-3) {100 * (np.abs(a[m] - b[m]) < 1e-3).mean():.0f}%")
rep("DTW score", o[:, 0], o[:, 1]); rep("VPIN", o[:, 2], o[:, 3]); rep("flow", o[:, 4], o[:, 5]); rep("HMM3 P(tox)", o[:, 6], o[:, 7])

# v1.38 range boxes (columns 6..11 when the EA logged them): entry price, Keltner, value area, VWAP, Asian range, Initial Balance
if rows.shape[1] >= 12:
    import rbox
    ef_, es_ = sim.emas(int(INP["InpEmaFast"]), int(INP["InpEmaSlow"]), "m15")
    FB = rbox.with_disp(rbox.features("m15", D), ef_, es_, D["atr"])
    fam = {"kelt": 3, "va": 5, "vwap": 0, "asia": 8, "ib": 1}
    for col, (name, f) in zip(range(7, 12), fam.items()):
        same = []
        for r in rows:
            j = int(np.searchsorted(t15, r[0], "right")) - 2
            same.append(int(rbox.box_of(FB, rbox.EDGES, rbox.NE, j, f, float(r[6]))) == int(r[col]))
        print(f"box {name:5s} same box in EA and tester: {100 * np.mean(same):.1f}% of {len(same)} entries")
