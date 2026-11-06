"""features.py - batch 5 study: per-trade features computed ONLY from bars <= t["k"] and the setup fields (no outcome).
Used to look for separations between losers and winners before writing rules. Run: py agents/batch_5/features.py"""
import datetime as dt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import api  # noqa: E402

A = api.A
PIP = A.PIP
o, h, l, c, v = A.o, A.h, A.l, A.c, A.v


def piv(k, p, look, side):
    """confirmed swing highs (side +1) or lows (side -1) with bar index <= k - p (no future)."""
    out = []
    for j in range(max(p, k - look), k - p + 1):
        if side > 0:
            if all(h[j] >= h[j - d] and h[j] >= h[j + d] for d in range(1, p + 1)):
                out.append((j, h[j]))
        else:
            if all(l[j] <= l[j - d] and l[j] <= l[j + d] for d in range(1, p + 1)):
                out.append((j, l[j]))
    return out


def feats(t):
    k, side, lvl = t["k"], t["side"], t["level"]
    f = {}
    f["ovs"] = (t["fill"] - lvl) * side / PIP
    f["sod"] = t["t_in"] % 86400
    f["dow"] = dt.datetime.fromtimestamp(t["t_in"], dt.timezone.utc).weekday()
    f["atr"] = A.atr[k] / PIP
    f["adx"] = float(A.adx[k])
    f["uhv_v"] = t["uhv_v"]
    for n in (30, 60):
        f[f"uhv_rel{n}"] = t["uhv_v"] / max(np.mean(v[k - n + 1:k + 1]), 1)
    f["vmean30"] = float(np.mean(v[k - 29:k + 1]))
    f["vtrend"] = float(np.mean(v[k - 9:k + 1]) / max(np.mean(v[k - 59:k - 9]), 1))
    f["brk_ratio"] = t["brk_ticks_so_far"] / max(t["uhv_v"], 1)
    f["depth"] = abs(lvl - t["extreme"]) / PIP
    f["depth_atr"] = abs(lvl - t["extreme"]) / max(A.atr[k], 1e-9)
    f["age"] = k - t["ku"]
    f["camStk"] = t["camStk"]
    f["box"] = t["box"]
    for n in (15, 30, 60, 90, 120):
        f[f"tr{n}"] = (c[k] - c[k - n]) * side / PIP                     # + = price moved in the trade direction
    for n in (30, 60, 120, 240):
        hi, lo = h[k - n + 1:k + 1].max(), l[k - n + 1:k + 1].min()
        rng = max(hi - lo, 1e-9)
        f[f"pos{n}"] = (lvl - lo) / rng if side > 0 else (hi - lvl) / rng  # 1 = level at the extreme in the trade direction
        f[f"room{n}"] = (hi - lvl) / PIP if side > 0 else (lvl - lo) / PIP  # pips to the N-bar extreme ahead (<=0 = new extreme)
        f[f"run{n}"] = (lvl - lo) / PIP if side > 0 else (hi - lvl) / PIP   # pips the price ran from the opposite extreme
        f[f"rng{n}"] = rng / PIP
    # touches of the level zone by prior swing points ahead of the trade (resistance for buys, support for sells)
    for p in (1, 2):
        for look in (60, 120):
            ps = piv(k, p, look, side)
            ps = [(j, x) for j, x in ps if j < t["ku"]]                     # before the UHV candle
            for tol in (0.5, 1.0, 2.0):
                f[f"touch_p{p}_l{look}_t{tol}"] = sum(1 for j, x in ps if abs(x - lvl) <= tol * PIP)
                f[f"ahead_p{p}_l{look}_t{tol}"] = sum(1 for j, x in ps if 0 <= (x - lvl) * side <= tol * PIP)
    # level chop: closed bars in the last N whose range contains the level
    for n in (10, 20, 30, 60):
        seg_h, seg_l = h[k - n + 1:k + 1], l[k - n + 1:k + 1]
        f[f"chop{n}"] = int(np.sum((seg_h >= lvl) & (seg_l <= lvl)))
    # round number distance (pips) from the level to the next 50-pip line ahead
    q = lvl / (50 * PIP)
    nxt = (np.ceil(q) if side > 0 else np.floor(q)) * 50 * PIP
    f["rn50_ahead"] = abs(nxt - lvl) / PIP
    q = lvl / (100 * PIP)
    nxt = (np.ceil(q) if side > 0 else np.floor(q)) * 100 * PIP
    f["rn100_ahead"] = abs(nxt - lvl) / PIP
    # where the UHV candle sits: distance of the UHV candle's far end from the N-bar extreme behind (climax at the low/high)
    ku = t["ku"]
    f["uhv_is_max60"] = int(v[ku] >= v[k - 59:k + 1].max())
    f["uhv_is_max30"] = int(v[ku] >= v[k - 29:k + 1].max())
    f["uhv_body"] = abs(c[ku] - o[ku]) / PIP
    f["uhv_rngp"] = (h[ku] - l[ku]) / PIP
    # extension of the move into the level in ATR units
    f["run60_atr"] = f["run60"] * PIP / max(A.atr[k], 1e-9)
    return f


if __name__ == "__main__":
    rows, y, half, ids = [], [], [], []
    for t in api.TRADES:
        rows.append(feats(api._blind(t)))
        y.append(not t["win"]); half.append(t["t_in"] < api.SPLIT); ids.append(t["id"])
    keys = list(rows[0].keys())
    X = np.array([[r[k_] for k_ in keys] for r in rows], dtype=float)
    np.savez(os.path.join(HERE, "feat.npz"), X=X, keys=np.array(keys), y=np.array(y), train=np.array(half), ids=np.array(ids))
    print(X.shape, len(keys))
