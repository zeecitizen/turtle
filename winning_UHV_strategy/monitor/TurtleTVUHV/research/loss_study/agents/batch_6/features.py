"""features.py - batch 6 study table: entry-moment and context features for the losses and their twins (only bars <= k + setup fields).
Run:  py agents/batch_6/features.py            (prints the losses / twins table)
      py agents/batch_6/features.py --uni     (univariate loss rates for every feature over all 7,626 trades, train / test)"""
import datetime as dt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
import api  # noqa: E402

A = api.A
PIP = 1e-4
PKT = dt.timezone(dt.timedelta(hours=5))
SPLIT = api.SPLIT


def feats(t):
    k, side, ku = t["k"], t["side"], t["ku"]
    o, h, l, c, v = A.o, A.h, A.l, A.c, A.v
    atr = float(A.atr[k])
    lvl = t["level"]
    f = {}
    tin = t["t_in"]
    u = dt.datetime.fromtimestamp(tin, dt.timezone.utc)
    f["wd"] = u.weekday()
    f["utc"] = u.strftime("%H:%M:%S")
    f["min_of_day"] = (int(tin) % 86400) / 60.0
    f["age"] = k - ku                                           # candles from the UHV to the last closed candle
    f["gap"] = side * (lvl - c[k]) / PIP                         # distance the last close sat from the level (+ = had to travel)
    f["ov_fill"] = side * (t["fill"] - lvl) / PIP
    f["ov_brk"] = ((t["brk_hi_so_far"] - lvl) if side > 0 else (lvl - t["brk_lo_so_far"])) / PIP
    f["brk_rng"] = (t["brk_hi_so_far"] - t["brk_lo_so_far"]) / PIP
    f["brk_ratio"] = t["brk_ticks_so_far"] / max(t["uhv_v"], 1)
    f["sec"] = tin % 60
    f["atr"] = atr / PIP
    f["adx"] = float(A.adx[k])
    f["v30"] = float(np.mean(v[k - 29:k + 1]))
    f["v240"] = float(np.mean(v[k - 239:k + 1]))
    f["vrel"] = f["v30"] / max(f["v240"], 1)
    f["uhv_rel30"] = t["uhv_v"] / max(f["v30"], 1)
    for n in (30, 60, 120):
        hi, lo = float(np.max(h[k - n + 1:k + 1])), float(np.min(l[k - n + 1:k + 1]))
        f[f"rng{n}"] = (hi - lo) / PIP
        pos = (lvl - lo) / max(hi - lo, 1e-9)
        f[f"pos{n}"] = pos if side > 0 else 1 - pos           # 1 = level at the trade-side extreme of the range (buy at top / sell at bottom)
        f[f"room{n}"] = ((hi - lvl) if side > 0 else (lvl - lo)) / PIP   # pips from the level to the n-bar extreme in the trade direction
    f["mom30"] = side * (c[k] - c[k - 30]) / PIP
    f["mom60"] = side * (c[k] - c[k - 60]) / PIP
    f["mom120"] = side * (c[k] - c[k - 120]) / PIP
    f["depth"] = abs(lvl - t["extreme"]) / PIP
    # hump just before entry
    H = A.humps_known(k)
    if len(H):
        b0, v0, bh, vh, b1, v1, tr, kn = H[-1]
        f["hump_amp"] = (vh - min(v0, v1)) / PIP
        f["hump_tr"] = int(tr)
        f["hump_age"] = k - int(b1)
    # the opposing move before the setup: for a buy, the biggest drop from a 120-bar high (max drawdown inside window ending at k)
    seg_h, seg_l = h[k - 119:k + 1], l[k - 119:k + 1]
    if side > 0:
        ih = int(np.argmax(seg_h)); f["opp"] = (seg_h[ih] - np.min(seg_l[ih:])) / PIP
    else:
        il = int(np.argmin(seg_l)); f["opp"] = (np.max(seg_h[il:]) - seg_l[il]) / PIP
    f["camStk"] = t["camStk"]
    f["box"] = t["box"]
    return f


def card_rows(batch):
    rows = []
    byid = {t["id"]: t for t in api.TRADES}
    for i, L in enumerate(batch["losses"]):
        rows.append(("LOSS", L["id"], byid[L["id"]]))
        for w in batch["twins"][2 * i:2 * i + 2]:
            rows.append(("twin", w["id"], byid[w["id"]]))
    return rows


COLS = ["utc", "wd", "age", "gap", "ov_fill", "ov_brk", "brk_rng", "brk_ratio", "sec", "atr", "adx", "v30", "vrel", "uhv_rel30", "rng60",
        "pos60", "room60", "pos120", "room120", "mom60", "mom120", "opp", "depth", "hump_amp", "hump_tr", "hump_age", "camStk", "box"]


def fmt(x):
    if isinstance(x, float):
        return f"{x:.2f}" if abs(x) < 100 else f"{x:.0f}"
    return str(x)


if __name__ == "__main__":
    if "--uni" not in sys.argv:
        b = json.load(open(os.path.join(LS, "batch_6.json"), encoding="utf-8"))
        print("kind id             " + " ".join(f"{c:>8s}" for c in COLS))
        for kind, tid, t in card_rows(b):
            f = feats(t)
            print(f"{kind:4s} {tid:15s} " + " ".join(f"{fmt(f.get(c, '')):>8s}" for c in COLS))
    else:
        F = [(feats(t), t) for t in api.TRADES]
        keys = [c for c in COLS if c not in ("utc",)] + ["min_of_day", "v240", "rng30", "rng120", "pos30", "room30", "mom30"]
        for key in keys:
            vals = np.array([f.get(key, np.nan) for f, _ in F], dtype=float)
            loss = np.array([not t["win"] for _, t in F])
            tr = np.array([t["t_in"] < SPLIT for _, t in F])
            qs = np.nanpercentile(vals, [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
            print(f"== {key}")
            for i in range(10):
                m = (vals >= qs[i]) & ((vals < qs[i + 1]) if i < 9 else (vals <= qs[i + 1]))
                if m.sum() == 0:
                    continue
                a = loss[m].mean() / loss.mean()
                trl = loss[m & tr].mean() / loss[tr].mean() if (m & tr).sum() else float('nan')
                tel = loss[m & ~tr].mean() / loss[~tr].mean() if (m & ~tr).sum() else float('nan')
                print(f"  [{qs[i]:9.3f},{qs[i + 1]:9.3f}]  n={m.sum():5d} L={loss[m].sum():3d}  lift {a:4.2f}  train {trl:4.2f} ({(loss & m & tr).sum()}L)  test {tel:4.2f} ({(loss & m & ~tr).sum()}L)")
