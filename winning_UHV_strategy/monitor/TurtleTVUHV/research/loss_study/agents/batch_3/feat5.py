"""feat5.py - the colour-setting hump as it was known at its last redraw (bar j <= k, per-bar camel state only: no hump-table leak)."""
import os, pickle, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402
A, PIP = api.A, api.PIP
R = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
byid = {t["id"]: api._blind(t) for t in api.TRADES}
LVa, HVa, L0a, STa = A.camLV, A.camHV, A.camL0V, A.camStk


def last_redraw(k):
    j = k
    while j > k - 400 and (LVa[j] == LVa[k] and STa[j] == STa[k]):
        j -= 1
    return j + 1                     # the first bar of the current (LV, Stk) state = the redraw bar


for r in R:
    t = byid[r["id"]]; k, s, ex, lv = t["k"], t["side"], t["extreme"], t["level"]
    j = last_redraw(k)
    HVj, LVj, L0j = float(HVa[j]), float(LVa[j]), float(L0a[j])
    atr = max(float(A.atr[k]) / PIP, 0.05)
    r["ch_age"] = k - j
    r["ch_amp"] = (HVj - LVj) / PIP                         # high of the colour hump down to its end low
    r["ch_rise"] = (HVj - L0j) / PIP                        # start low up to its high
    r["ch_amp_atr"] = r["ch_amp"] / atr
    r["ch_size"] = min(r["ch_amp"], r["ch_rise"])            # the smaller leg of the hump
    r["ch_lowdiff"] = abs(LVj - L0j) / PIP
    # structure broken vs the colour hump: sell - the retracement went above the red hump's high; buy - below the green hump's end low
    r["cbreak_pips"] = ((ex - HVj) if s < 0 else (LVj - ex)) / PIP
    r["cbreak"] = int(r["cbreak_pips"] > 0)
    # the retracement size relative to the colour hump: how much of the hump the pullback retraced
    r["ret_frac"] = (abs(ex - (LVj if s < 0 else HVj)) / max(abs(HVj - LVj), 1e-6))
pickle.dump(R, open(os.path.join(HERE, "feat.pkl"), "wb"))
print("ok")
