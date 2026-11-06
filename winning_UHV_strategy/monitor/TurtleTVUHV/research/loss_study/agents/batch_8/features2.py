"""features2.py (batch_8 study) - more blind features (structure around the level). Reads only bars <= k. Writes features2.pkl."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
import api  # noqa: E402

A = api.A
PIP = api.PIP
o, h, l, c, v = A.o, A.h, A.l, A.c, A.v


def piv_hi(j, p):
    return all(h[j] >= h[j - d] and h[j] >= h[j + d] for d in range(1, p + 1))


def piv_lo(j, p):
    return all(l[j] <= l[j - d] and l[j] <= l[j + d] for d in range(1, p + 1))


rows = []
for t in api.TRADES:
    k, ku, s, lv, ex, fill = t["k"], t["ku"], t["side"], t["level"], t["extreme"], t["fill"]
    r = {"id": t["id"]}
    # pre-UHV extreme in the trade direction (the swing the retracement came from), vs the level
    for W in (10, 20, 30, 60):
        a = max(0, ku - W)
        if s > 0:
            r[f"peak_pre{W}"] = (h[a:ku].max() - lv) / PIP if ku > a else np.nan
        else:
            r[f"peak_pre{W}"] = (lv - l[a:ku].min()) / PIP if ku > a else np.nan
    # pivots (p=2, confirmed by k) sitting at the level: equal highs (buy) / equal lows (sell), excluding the UHV bar
    for W in (30, 60, 120):
        cnt05, cnt03, cnt10 = 0, 0, 0
        for j in range(max(2, k - W), k - 1):
            if j == ku:
                continue
            if s > 0 and piv_hi(j, 2):
                d = (h[j] - lv) / PIP
            elif s < 0 and piv_lo(j, 2):
                d = (lv - l[j]) / PIP
            else:
                continue
            cnt03 += (-0.3 <= d <= 0.3)
            cnt05 += (-0.2 <= d <= 0.6)
            cnt10 += (-0.3 <= d <= 1.0)
        r[f"eqp{W}_03"], r[f"eqp{W}_05"], r[f"eqp{W}_10"] = cnt03, cnt05, cnt10
    # the retracement: its extreme bar and length; the impulse before it
    a = max(0, ku - 30)
    if s > 0:
        jx = a + int(np.argmin(l[a:k + 1]))     # the lowest low from 30 bars before the UHV up to k
        jp = a + int(np.argmax(h[a:ku + 1]))    # the swing high before/at the UHV
        r["ret_len"] = k - jp
        r["leg"] = (h[jp] - l[max(0, jp - 30):jp + 1].min()) / PIP
    else:
        jx = a + int(np.argmax(h[a:k + 1]))
        jp = a + int(np.argmin(l[a:ku + 1]))
        r["ret_len"] = k - jp
        r["leg"] = (h[max(0, jp - 30):jp + 1].max() - l[jp]) / PIP
    # efficiency ratio (chop) over N bars
    for N in (20, 30, 60):
        dsum = np.abs(np.diff(c[k - N:k + 1])).sum()
        r[f"er{N}"] = abs(c[k] - c[k - N]) / dsum if dsum > 0 else 0.0
    r["sec_in_min"] = t["t_in"] % 60
    r["vk_uhv"] = v[k] / max(t["uhv_v"], 1)
    # the last 3 closed candles all against the trade (pullback still running) / with it
    r["k3_with"] = int(sum(np.sign(c[k - i] - o[k - i]) * s > 0 for i in range(3)))
    # distance of the close k from the level, pips (how far below the level a buy's last close sits)
    r["close_gap"] = (lv - c[k]) / PIP if s > 0 else (c[k] - lv) / PIP
    # max bar range in the last 30 bars vs ATR (a spike nearby)
    r["spike30"] = ((h[k - 29:k + 1] - l[k - 29:k + 1]).max()) / max(A.atr[k], 1e-9)
    rows.append(r)
pd.DataFrame(rows).to_pickle(os.path.join(HERE, "features2.pkl"))
print("ok", len(rows))
