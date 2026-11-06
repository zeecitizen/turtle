"""features.py - batch 7: a causal feature table for every trade of the 97.7% setting (bars <= k + setup fields only).
Outcome columns (win, pnl, why) are attached ONLY for the analysis; rules never read them. Writes feats.pkl."""
import json
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
o, h, l, c, v, t1 = A.o, A.h, A.l, A.c, A.v, A.t
SPLIT = api.SPLIT


def ema(x, n):
    a = 2.0 / (n + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


E60, E240, E720 = ema(c, 60), ema(c, 240), ema(c, 720)
rows = []
for t in api.TRADES:
    s, k, kb, ku = t["side"], t["k"], t["kb"], t["ku"]
    f, L, X = t["fill"], t["level"], t["extreme"]
    d = {"id": t["id"], "side": s, "t_in": t["t_in"], "win": t["win"], "pnl": t["pnl"], "why": t["why"],
         "train": t["t_in"] < SPLIT}
    tin = t["t_in"]
    sod = tin % 86400
    d["hour"] = int(sod // 3600); d["minute"] = int((sod % 3600) // 60); d["sec"] = sod % 60
    d["dow"] = int(((tin // 86400) + 3) % 7)          # 0=Mon .. 4=Fri (1970-01-01 was a Thursday)
    d["mins_to_2100"] = ((21 * 3600 - sod) % 86400) / 60.0
    d["mins_since_2100"] = ((sod - 21 * 3600) % 86400) / 60.0
    d["slip"] = s * (f - L) / PIP
    d["uhv_v"] = t["uhv_v"]; d["brk"] = t["brk_ticks_so_far"]; d["brk_ratio"] = t["brk_ticks_so_far"] / max(t["uhv_v"], 1)
    d["box"] = t["box"]; d["camStk"] = t["camStk"] * s; d["acs"] = abs(t["camStk"])
    d["stop_pips"] = t["stop_pips"]
    d["ku_age"] = kb - ku
    d["lev_ext"] = s * (L - X) / PIP                  # level above the retracement extreme (buy), pips
    d["atr"] = A.atr[k] / PIP; d["adx"] = A.adx[k]
    for n in (30, 60, 120, 240):
        d[f"vm{n}"] = v[max(0, k - n + 1):k + 1].mean()
    d["uhv_rel"] = t["uhv_v"] / max(d["vm60"], 1)
    d["vk_rel"] = v[k] / max(d["vm60"], 1)
    d["vol_trend"] = d["vm30"] / max(d["vm240"], 1)
    d["atr_rel"] = A.atr[k] / max(np.mean(A.atr[max(0, k - 1440):k + 1]), 1e-9)
    for n in (3, 5, 10, 15, 30, 60, 120, 240, 480):
        d[f"ret{n}"] = s * (c[k] - c[max(0, k - n)]) / PIP
    for n in (10, 20, 30, 60, 120, 240, 480):
        a0 = max(0, k - n + 1)
        hi = h[a0:k + 1].max(); lo = l[a0:k + 1].min()
        r = max(hi - lo, 1e-9)
        d[f"rng{n}"] = r / PIP
        d[f"pos{n}"] = (f - lo) / r if s > 0 else (hi - f) / r
        d[f"room{n}"] = (hi - f) / PIP if s > 0 else (f - lo) / PIP      # >0: price was further in trade dir within n bars
        d[f"back{n}"] = (f - lo) / PIP if s > 0 else (hi - f) / PIP      # distance back to the opposite extreme
        rngs = (h[a0:k + 1] - l[a0:k + 1])
        d[f"maxbar{n}"] = rngs.max() / PIP
    d["ema60"] = s * (c[k] - E60[k]) / PIP; d["ema240"] = s * (c[k] - E240[k]) / PIP; d["ema720"] = s * (c[k] - E720[k]) / PIP
    d["ema60_slope"] = s * (E60[k] - E60[k - 30]) / PIP; d["ema240_slope"] = s * (E240[k] - E240[k - 60]) / PIP
    # touches of the fill zone (resistance for a buy / support for a sell) in the last 60 bars, excluding the last 2
    zone = 0.5 * PIP
    seg_h, seg_l = h[k - 60:k - 1], l[k - 60:k - 1]
    if s > 0:
        d["touch60"] = int(np.sum(np.abs(seg_h - f) <= zone)); d["beyond60"] = int(np.sum(seg_h >= f))
    else:
        d["touch60"] = int(np.sum(np.abs(seg_l - f) <= zone)); d["beyond60"] = int(np.sum(seg_l <= f))
    seg_h, seg_l = h[k - 20:k - 1], l[k - 20:k - 1]
    d["beyond20"] = int(np.sum(seg_h >= f)) if s > 0 else int(np.sum(seg_l <= f))
    # last closed bar shape (side-normalized)
    rk = max(h[k] - l[k], 1e-9)
    d["k_body"] = s * (c[k] - o[k]) / PIP; d["k_rng"] = rk / PIP
    d["k_closepos"] = (c[k] - l[k]) / rk if s > 0 else (h[k] - c[k]) / rk
    # UHV candle
    ru = max(h[ku] - l[ku], 1e-9)
    d["u_rng"] = ru / PIP; d["u_body"] = abs(c[ku] - o[ku]) / PIP
    # entry-bar so far
    d["brk_span"] = (t["brk_hi_so_far"] - t["brk_lo_so_far"]) / PIP
    d["pre_move"] = s * (f - o[kb]) / PIP            # how far the entry minute already moved in trade dir before the fill
    # humps known at k
    Hk = A.humps[A.humps[:, 7] <= k]
    if len(Hk) >= 2:
        b0, v0, bh, vh, b1, v1, tr, kn = Hk[-1]
        d["h_amp"] = (vh - min(v0, v1)) / PIP; d["h_dur"] = b1 - b0; d["h_age"] = k - kn; d["h_tr"] = tr * s
        d["h_lowdiff"] = s * (v1 - v0) / PIP
        pb0, pv0, pbh, pvh, pb1, pv1, ptr, pkn = Hk[-2]
        d["h_highdiff"] = s * (vh - pvh) / PIP       # higher high (buy) > 0
        d["ph_tr"] = ptr * s
    rows.append(d)
F = pd.DataFrame(rows)
F.to_pickle(os.path.join(HERE, "feats.pkl"))
print(F.shape)
