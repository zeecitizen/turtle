"""feats.py (work_loss4b) - decision-time features for every trade of the four stacks (bars <= k + the setup fields only; no outcome),
written to feats_<stack>.json next to this file, plus a univariate loss-rate table per feature (secure / base, all / train / test).
Python replay = HYPOTHESIS ONLY."""
import json
import os
import sys
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import api_tight as api  # noqa: E402

A = api.A
P = 1e-4
NY = ZoneInfo("America/New_York")


def er(c, k, n):
    cc = c[k - n:k + 1]
    p = float(np.abs(np.diff(cc)).sum())
    return abs(float(cc[-1] - cc[0])) / p if p > 0 else 0.0


def feats(t):
    k, s, lev = t["k"], t["side"], t["level"]
    h, l, c, v, atr = A.h, A.l, A.c, A.v, A.atr
    f = {}
    f["sp"] = t["trig_spread_pips"]
    f["ratio"] = t["brk_ticks"] / max(t["uhv_v"], 1)
    f["sec"] = t["t_dec"] % 60
    f["rate"] = t["brk_ticks"] / max(f["sec"], 1.0)
    f["brkrng"] = (t["brk_hi"] - t["brk_lo"]) / P
    f["runmin"] = ((lev - t["brk_lo"]) if s > 0 else (t["brk_hi"] - lev)) / P
    f["ret"] = (lev - t["extreme"]) * s / P
    f["kku"] = k - t["ku"]
    f["humps"] = t["humps"]; f["er16"] = t["er16"]; f["atr"] = t["atr_pips"]; f["box"] = t["box"]
    for n in (8, 30, 60):
        f[f"er{n}"] = er(c, k, n)
    for n in (5, 10, 20, 30, 60, 90):
        ext = h[k - n + 1:k + 1].max() if s > 0 else l[k - n + 1:k + 1].min()
        f[f"beyond{n}"] = (lev - ext) * s / P                     # >0: the level is a fresh n-bar extreme; <0: the n-bar extreme sits ahead
    for n in (30, 90):
        hi, lo = h[k - n + 1:k + 1].max(), l[k - n + 1:k + 1].min()
        f[f"rng{n}_atr"] = (hi - lo) / max(atr[k], 1e-6)
        f[f"pos{n}"] = ((lev - lo) if s > 0 else (hi - lev)) / max(hi - lo, 1e-6)
    f["uhv_loud60"] = t["uhv_v"] / max(np.mean(v[k - 59:k + 1]), 1)
    f["uhv_loud15"] = t["uhv_v"] / max(np.mean(v[k - 14:k + 1]), 1)
    f["vtrend"] = np.mean(v[k - 9:k + 1]) / max(np.mean(v[k - 59:k + 1]), 1)
    f["v10"] = float(np.mean(v[k - 9:k + 1]))
    for n in (15, 30, 60, 120):
        f[f"tr{n}"] = (c[k] - c[k - n]) * s / max(atr[k], 1e-6)  # move in the trade direction, ATRs
    f["adx"] = float(A.adx[k])
    for tol in (0.3, 0.5, 1.0):
        if s > 0:
            f[f"touch{tol}"] = int(np.sum(np.abs(h[k - 59:k + 1] - lev) <= tol * P))
        else:
            f[f"touch{tol}"] = int(np.sum(np.abs(l[k - 59:k + 1] - lev) <= tol * P))
    d = dt.datetime.fromtimestamp(t["t_dec"], NY)
    f["nyh"] = d.hour + d.minute / 60.0
    f["wd"] = d.weekday()
    f["close_k_vs_lev"] = (lev - c[k]) * s / P                     # how far the last close sits short of the level
    f["k_dir"] = float(np.sign(c[k] - A.o[k]) * s)                 # the last closed candle in the trade direction (+1) or against (-1)
    f["k_body"] = abs(c[k] - A.o[k]) / max(h[k] - l[k], 1e-6)
    return f


def load():
    out = {}
    for st in ("tight", "secure", "base"):
        rows = []
        for t in api.STACKS[st]:
            f = feats(api._blind(t))
            f.update(id=t["id"], win=t["win"], train=t["t_dec"] < api.SPLIT, pnl=t["pnl"])
            rows.append(f)
        out[st] = rows
    return out


if __name__ == "__main__":
    F = load()
    for st, rows in F.items():
        json.dump(rows, open(os.path.join(HERE, f"feats_{st}.json"), "w"), default=float)
    keys = [k for k in F["tight"][0] if k not in ("id", "win", "train", "pnl")]
    for key in keys:
        print(f"== {key}")
        for st in ("secure", "base"):
            R = F[st]
            x = np.array([r[key] for r in R], float); w = np.array([r["win"] for r in R]); tr = np.array([r["train"] for r in R])
            qs = np.unique(np.quantile(x, [0, .2, .4, .6, .8, .9, .95, 1.0]))
            line = []
            for a, b in zip(qs[:-1], qs[1:]):
                m = (x >= a) & ((x < b) if b < qs[-1] else (x <= b))
                n = int(m.sum()); L = int((~w[m]).sum())
                Ltr = int((~w[m & tr]).sum()); ntr = int((m & tr).sum()); Lte = int((~w[m & ~tr]).sum()); nte = int((m & ~tr).sum())
                line.append(f"[{a:.3g},{b:.3g}] {n} L{L} {100*L/max(n,1):.1f}% (tr {100*Ltr/max(ntr,1):.1f} te {100*Lte/max(nte,1):.1f})")
            print(f"  {st:6s} " + " | ".join(line))
        # tight losses' values
        print("  tight losses: " + ", ".join(f"{r['id']}={r[key]:.3g}" for r in F["tight"] if not r["win"]))
