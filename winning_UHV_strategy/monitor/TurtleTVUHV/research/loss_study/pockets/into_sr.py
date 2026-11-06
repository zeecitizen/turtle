"""into_sr.py - Zee 2026-11-06: "some of the losses came exactly when we sold right into us trying to break downwards a support level (support
being a line drawn from last low or the last to last low or before that) -> we must single out these losses".
For every trade of the 97.7% setting: the last 1..3 MAJOR swing lows (sells) / highs (buys) before the entry - swings confirmed with p
candles on each side (p = 3, 5, 10: real lows, not wiggles), all confirmed by the last closed candle k. A trade is INTO SUPPORT (sell) /
INTO RESISTANCE (buy) when its UHV level sits within X pips of one of those levels on the near side (or just through it by <= Y pips:
"trying to break" it). Prints, per definition: trades in the pocket, losses in it (of 172), loss rate and lift, by half - and lists the
losses it singles out. Run: py research/loss_study/pockets/into_sr.py"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
PIP = 1e-4
SPLIT = 1782864000
z = np.load(os.path.join(LS, "arrays.npz"))
h, l = z["h"], z["l"]
T = json.load(open(os.path.join(LS, "tight", "trades_base.json"), encoding="utf-8"))
n = len(h)


def pivots(p):
    ph = np.zeros(n, bool); pl = np.zeros(n, bool)
    for i in range(p, n - p):
        w_h, w_l = h[i - p:i + p + 1], l[i - p:i + p + 1]
        ph[i] = h[i] == w_h.max()
        pl[i] = l[i] == w_l.min()
    return np.flatnonzero(ph), np.flatnonzero(pl)


PIV = {p: pivots(p) for p in (3, 5, 10)}


def last_levels(p, k, side, m, look):
    """the last m major swing lows (side -1) / highs (side +1) confirmed by bar k (a p-pivot at j is known once j + p <= k)"""
    hi_idx, lo_idx = PIV[p]
    idx = lo_idx if side < 0 else hi_idx
    j = np.searchsorted(idx, k - p, side="right")
    sel = idx[max(0, j - m):j]
    sel = sel[sel >= k - look]
    return (l if side < 0 else h)[sel]


def pocket(p, m, x, y, look=480):
    out = []
    for t in T:
        lv = last_levels(p, t["k"], t["side"], m, look)
        if not len(lv):
            out.append(False); continue
        d = (t["level"] - lv) / PIP if t["side"] < 0 else (lv - t["level"]) / PIP   # + = the S/R is still ahead of the level (not yet broken)
        out.append(bool(np.any((d >= -y) & (d <= x))))
    return np.array(out)


win = np.array([t["win"] for t in T]); tt = np.array([t["t_dec"] for t in T]); N = len(T); L = int((~win).sum())
print(f"{N} trades, {L} losses ({100 * L / N:.2f}%)")
best = None
for p in (3, 5, 10):
    for m in (1, 2, 3):
        for x in (0.5, 1.0, 2.0, 3.0):
            for y in (0.0, 0.5, 1.0):
                pk = pocket(p, m, x, y)
                ins = pk.sum(); il = int((~win[pk]).sum())
                tr, te = pk & (tt < SPLIT), pk & (tt >= SPLIT)
                lr_tr = (~win[tr]).sum() / max(tr.sum(), 1); lr_te = (~win[te]).sum() / max(te.sum(), 1)
                b_tr = (~win[tt < SPLIT]).mean(); b_te = (~win[tt >= SPLIT]).mean()
                lift = (il / max(ins, 1)) / (L / N)
                print(f"swing p={p:2d} last {m} levels, within {x:3.1f} pips ahead / {y:3.1f} through: pocket {100 * ins / N:5.1f}% of trades, "
                      f"{il:3d}/{L} losses ({100 * il / L:4.1f}%), lift x{lift:4.2f} | train x{lr_tr / b_tr:4.2f} test x{lr_te / b_te:4.2f}", flush=True)
                if best is None or (lift > best[0] and il >= 15 and lr_tr / b_tr > 1.5 and lr_te / b_te > 1.5):
                    best = (lift, p, m, x, y, pk)
if best:
    lift, p, m, x, y, pk = best
    print(f"\nBEST (lift x{lift:.2f}, >= 15 losses, both halves > 1.5): swing p={p}, last {m}, within {x} ahead / {y} through")
    for t, k_ in zip(T, pk):
        if k_ and not t["win"]:
            print("   singled out:", t["id"], "pnl", round(t["pnl"]))
