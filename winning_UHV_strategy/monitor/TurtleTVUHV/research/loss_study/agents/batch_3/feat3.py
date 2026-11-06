"""feat3.py - level features: round numbers, day high/low, previous day high/low, 4-hour context."""
import os, pickle, sys, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402
A, PIP = api.A, api.PIP
R = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
byid = {t["id"]: api._blind(t) for t in api.TRADES}
day_start = {}
tt = A.t
for r in R:
    t = byid[r["id"]]; k, s, lv = t["k"], t["side"], t["level"]
    for step, nm in ((10, "rn10"), (50, "rn50"), (100, "rn100")):
        g = step * PIP
        if s > 0:
            nxt = math.ceil((lv + 1e-9) / g) * g; r[nm] = (nxt - lv) / PIP
        else:
            nxt = math.floor((lv - 1e-9) / g) * g; r[nm] = (lv - nxt) / PIP
    d0 = (int(tt[k]) // 86400) * 86400
    j0 = int(np.searchsorted(tt, d0))
    if j0 <= k:
        dh, dl = float(A.h[j0:k + 1].max()), float(A.l[j0:k + 1].min())
        r["day_room"] = ((dh - lv) if s > 0 else (lv - dl)) / PIP          # room to the day's extreme in the trade direction
        r["day_pos"] = (((dh - lv) if s > 0 else (lv - dl)) / (dh - dl)) if dh > dl else 0.5
    else:
        r["day_room"] = 0.0; r["day_pos"] = 0.5
    jp = int(np.searchsorted(tt, d0 - 86400))
    if jp < j0:
        ph, pl = float(A.h[jp:j0].max()), float(A.l[jp:j0].min())
        r["pd_room"] = ((ph - lv) if s > 0 else (lv - pl)) / PIP           # to the previous day's high (buy) / low (sell)
    else:
        r["pd_room"] = 99.0
    atr = max(float(A.atr[k]) / PIP, 0.05)
    r["trend240"] = (A.c[k] - A.c[k - 240]) * s / PIP / atr if k >= 240 else 0.0
    hi, lo = float(A.h[k - 239:k + 1].max()), float(A.l[k - 239:k + 1].min())
    r["pos240"] = (((lv - lo) if s < 0 else (hi - lv)) / (hi - lo)) if hi > lo else 0.5
    r["room240"] = ((lv - lo) if s < 0 else (hi - lv)) / PIP
pickle.dump(R, open(os.path.join(HERE, "feat.pkl"), "wb"))
print("ok")
