"""features.py (batch_3) - one row of pre-entry features per trade of the 97.7% setting, from bars <= k only, for binning loss
rates on the train and test halves. Nothing here reads an outcome field except to label the row (win / half) for the tables."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402

A = api.A
PIP = api.PIP


def feats(t):
    k, ku, s = t["k"], t["ku"], t["side"]
    lv, ex = t["level"], t["extreme"]
    h, l, c, o, v = A.h, A.l, A.c, A.o, A.v
    atr = float(A.atr[k]) / PIP
    f = {}
    f["side"] = s
    f["dow"] = int((t["t_in"] // 86400 + 4) % 7)
    f["mod"] = (t["t_in"] % 86400) / 60.0                       # minute of the UTC day
    f["hour"] = int(f["mod"] // 60)
    f["uhv_age"] = k - ku
    f["atr"] = atr
    f["adx"] = float(A.adx[k])
    f["box"] = t["box"]
    f["stk"] = abs(t["camStk"])
    f["brk_ratio"] = t["brk_ticks_so_far"] / max(t["uhv_v"], 1)
    f["uhv_v"] = t["uhv_v"]
    f["uhv_rel"] = t["uhv_v"] / max(np.mean(v[k - 59:k + 1]), 1)
    f["stop_pips"] = t["stop_pips"]
    f["ret_pips"] = abs(ex - lv) / PIP                           # UHV level to the retracement extreme
    for N in (3, 5, 10, 20, 30, 60, 120):
        hi, lo = float(h[k - N + 1:k + 1].max()), float(l[k - N + 1:k + 1].min())
        f[f"room{N}"] = ((lv - lo) if s < 0 else (hi - lv)) / PIP    # pips from the level to the N-bar extreme in the trade direction
        f[f"ext{N}"] = ((hi - lv) if s < 0 else (lv - lo)) / PIP / max(atr, 0.05)   # move already made toward the level, in ATR
        rng = hi - lo
        f[f"pos{N}"] = (((lv - lo) if s < 0 else (hi - lv)) / rng) if rng > 0 else 0.5
        f[f"rng{N}"] = rng / PIP
    f["trend60"] = (c[k] - c[k - 60]) * s / PIP / max(atr, 0.05)
    f["trend30"] = (c[k] - c[k - 30]) * s / PIP / max(atr, 0.05)
    f["trend120"] = (c[k] - c[k - 120]) * s / PIP / max(atr, 0.05)
    HV, LV, L0V, T = float(A.camHV[k]), float(A.camLV[k]), float(A.camL0V[k]), int(A.camT[k])
    f["camT"] = T * s                                            # +1 = last swing is in the trade direction's "top" sense for buys
    f["sbreak"] = int((ex > HV) if s < 0 else (ex < LV))          # retracement went beyond the camel's opposite swing
    f["sbreak_pips"] = ((ex - HV) if s < 0 else (LV - ex)) / PIP
    f["sbreak0"] = int((ex > HV) if s < 0 else (ex < L0V))
    f["hump_amp"] = (HV - LV) / PIP / max(atr, 0.05)
    f["hump_amp_p"] = (HV - LV) / PIP
    f["hump_leg"] = (abs(LV - L0V)) / PIP                        # how much lower (red) / higher (green) the last low is
    # level vs the camel's last low/high (where is the level inside the hump)
    f["lv_vs_LV"] = ((lv - LV) if s < 0 else (HV - lv)) / PIP
    f["vol5_60"] = float(np.mean(v[k - 4:k + 1])) / max(float(np.mean(v[k - 59:k + 1])), 1)
    f["vol_k"] = float(v[k])
    f["vol60"] = float(np.mean(v[k - 59:k + 1]))
    # touches: bars in the last N whose extreme in the trade direction came within X pips of the level (support for sells / resistance for buys)
    for N in (30, 60):
        seg = (l[k - N + 1:k + 1] if s < 0 else h[k - N + 1:k + 1])
        d = ((seg - lv) if s < 0 else (lv - seg)) / PIP             # >0 = the bar did not reach the level; <0 = went beyond it
        f[f"touch{N}"] = int(np.sum((d <= 1.0) & (d >= -1.0)))
        f[f"beyond{N}"] = int(np.sum(d < -1.0))
    # the impulse leg before the retracement: from the retracement extreme back to the opposite extreme of the previous 30 bars
    f["imp_speed10"] = ((h[k - 9:k + 1].max() - l[k - 9:k + 1].min())) / PIP / max(atr, 0.05)
    f["body_k"] = (c[k] - o[k]) * s / PIP
    f["range_k"] = (h[k] - l[k]) / PIP
    return f


def table():
    rows = []
    for t in api.TRADES:
        f = feats(api._blind(t))
        f["win"] = bool(t["win"]); f["train"] = t["t_in"] < api.SPLIT; f["id"] = t["id"]; f["t_in"] = t["t_in"]
        rows.append(f)
    return rows


if __name__ == "__main__":
    import pickle
    R = table()
    pickle.dump(R, open(os.path.join(HERE, "feat.pkl"), "wb"))
    print(len(R), "rows; keys", list(R[0].keys()))
