"""feats.py - batch 4 exploration: per-trade features computed ONLY from bars <= k and the setup fields (no outcome),
used to check visual hypotheses on the TRAIN half before writing rules. Run from the loss_study folder."""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402

A = api.A
PIP = api.PIP


def feats(t):
    k, kb, ku, s = t["k"], t["kb"], t["ku"], t["side"]
    h, l, c, o, v = A.h, A.l, A.c, A.o, A.v
    atr = max(float(A.atr[k]), 1e-6)
    lev = t["level"]
    f = {}
    f["secs"] = t["t_in"] - float(A.t[kb])
    f["ratio"] = t["brk_ticks_so_far"] / max(t["uhv_v"], 1)
    f["proj"] = t["brk_ticks_so_far"] * 60.0 / max(f["secs"], 1.0) / max(t["uhv_v"], 1)
    f["jump"] = (t["fill"] - lev) * s / PIP
    f["atr_p"] = atr / PIP
    f["adx"] = float(A.adx[k])
    f["hour"] = (t["t_in"] % 86400) / 3600.0
    f["uhv_rel60"] = t["uhv_v"] / max(np.median(v[k - 59:k + 1]), 1)
    f["vol10_rel"] = np.median(v[k - 9:k + 1]) / max(np.median(v[k - 120:k - 9]), 1)
    f["med10"] = float(np.median(v[k - 9:k + 1]))
    f["retr"] = abs(lev - t["extreme"]) / PIP
    f["bars_uhv"] = kb - ku
    for N in (10, 20, 30, 60, 90):
        if s > 0:
            f[f"room{N}"] = (h[k - N + 1:k + 1].max() - lev) / PIP
        else:
            f[f"room{N}"] = (lev - l[k - N + 1:k + 1].min()) / PIP
    for N in (15, 30, 60, 120):
        f[f"ext{N}"] = (c[k] - c[k - N]) * s / atr
        f[f"str{N}"] = (lev - c[k - N + 1:k + 1].mean()) * s / atr
    f["spike"] = (h[k] - l[k]) / atr
    f["run3"] = ((lev - l[k - 2:k + 1].min()) if s > 0 else (h[k - 2:k + 1].max() - lev)) / atr
    f["camstk"] = abs(t["camStk"])
    if s > 0:
        rn50 = math.ceil(lev / 0.0050 - 1e-9) * 0.0050
        rn10 = math.ceil(lev / 0.0010 - 1e-9) * 0.0010
    else:
        rn50 = math.floor(lev / 0.0050 + 1e-9) * 0.0050
        rn10 = math.floor(lev / 0.0010 + 1e-9) * 0.0010
    f["rn50"] = abs(rn50 - lev) / PIP
    f["rn10"] = abs(rn10 - lev) / PIP
    f["brk_rng"] = (t["brk_hi_so_far"] - t["brk_lo_so_far"]) / PIP
    f["brk_run"] = ((t["fill"] - t["brk_lo_so_far"]) if s > 0 else (t["brk_hi_so_far"] - t["fill"])) / PIP
    f["box"] = t["box"]
    f["stop_pips"] = t["stop_pips"]
    return f


def table():
    rows = []
    for t in api.TRADES:
        f = feats(t)
        f["win"] = t["win"]; f["train"] = t["t_in"] < api.SPLIT; f["side"] = t["side"]; f["id"] = t["id"]
        rows.append(f)
    return rows


if __name__ == "__main__":
    rows = table()
    keys = [k for k in rows[0] if k not in ("win", "train", "side", "id")]
    which = sys.argv[1] if len(sys.argv) > 1 else "train"
    R = [r for r in rows if (r["train"] if which == "train" else (not r["train"]) if which == "test" else True)]
    base = sum(not r["win"] for r in R) / len(R)
    print(f"{which}: {len(R)} trades, base loss {100*base:.2f}%")
    for kname in keys:
        x = np.array([r[kname] for r in R], dtype=float); y = np.array([not r["win"] for r in R])
        qs = np.unique(np.nanpercentile(x, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]))
        out = []
        for a, b in zip(qs[:-1], qs[1:]):
            m = (x >= a) & ((x < b) if b < qs[-1] else (x <= b))
            if m.sum():
                out.append(f"[{a:.3g},{b:.3g}]{m.sum()}:{100*y[m].mean():.1f}")
        print(f"{kname:10s} " + "  ".join(out))
