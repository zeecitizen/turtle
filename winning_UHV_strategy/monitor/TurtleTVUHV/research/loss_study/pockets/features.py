"""features.py - one row per trade of the 97.7% setting with everything known at the DECISION tick (the breakout), for finding the risky
POCKETS (Zee 2026-11-06: "10% risky trades zone -> here the angel only cuts some of them ... 80% non-risky trades (no angel) -> there's no
cut on these trades ... isolate the risky zones further by breaking them down into chunks").
Input: ../tight/trades_base.json (engine-built, decision-time k) + ../arrays.npz (bars). Output: features.csv (one row per trade; the outcome
columns win / pnl / half are LAST and must never be used as inputs). Every feature reads only bars <= k (the last closed candle before the
breakout minute) and the setup's own fields up to the breakout tick. Run: py research/loss_study/pockets/features.py"""
import csv
import datetime as dt
import json
import math
import os
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
PIP = 1e-4
NY = ZoneInfo("America/New_York")
SPLIT = 1782864000

z = np.load(os.path.join(LS, "arrays.npz"))
t, o, h, l, c, v, atr, adx = (z[k] for k in ("t", "o", "h", "l", "c", "v", "atr", "adx"))
T = json.load(open(os.path.join(LS, "tight", "trades_base.json"), encoding="utf-8"))
n = len(t)
ph = np.zeros(n, bool); pl = np.zeros(n, bool)
ph[1:-1] = (h[1:-1] >= h[:-2]) & (h[1:-1] >= h[2:])
pl[1:-1] = (l[1:-1] <= l[:-2]) & (l[1:-1] <= l[2:])
idx = np.arange(n)
lastH = np.maximum.accumulate(np.where(ph, idx, -1))
lastL = np.maximum.accumulate(np.where(pl, idx, -1))


def er(k, m):
    cc = c[k - m:k + 1]
    p = float(np.abs(np.diff(cc)).sum())
    return abs(float(cc[-1] - cc[0])) / p if p > 0 else 0.0


def swings(last, k, m):
    out, j = [], last[k - 1]
    while j >= 0 and len(out) < m:
        out.append(j); j = last[j - 1] if j >= 1 else -1
    return out[::-1]


rows = []
for tr in T:
    k, ku, s = tr["k"], tr["ku"], tr["side"]
    if k < 260:
        continue
    lev, ext = tr["level"], tr["extreme"]
    a = float(atr[k]) or 1e-6
    nyd = dt.datetime.fromtimestamp(tr["t_dec"], NY)
    hi20, lo20 = h[k - 19:k + 1].max(), l[k - 19:k + 1].min()
    hi60, lo60 = h[k - 59:k + 1].max(), l[k - 59:k + 1].min()
    hi240, lo240 = h[k - 239:k + 1].max(), l[k - 239:k + 1].min()
    room60 = ((hi60 - lev) if s > 0 else (lev - lo60)) / PIP        # pips from the level to the 60-bar extreme in the trade direction
    room240 = ((hi240 - lev) if s > 0 else (lev - lo240)) / PIP
    pos60 = ((lev - lo60) / (hi60 - lo60) if hi60 > lo60 else 0.5) if s > 0 else ((hi60 - lev) / (hi60 - lo60) if hi60 > lo60 else 0.5)
    hs, ls = swings(lastH, k, 3), swings(lastL, k, 3)
    hh = (h[hs[-1]] > h[hs[-2]]) if len(hs) >= 2 else False
    hl = (l[ls[-1]] > l[ls[-2]]) if len(ls) >= 2 else False
    struct_with = (hh and hl) if s > 0 else ((not hh) and (not hl))
    rng_u = h[ku] - l[ku]
    body_u = abs(c[ku] - o[ku]) / rng_u if rng_u > 0 else 0
    rng_k = h[k] - l[k]
    body_k = (c[k] - o[k]) * s / rng_k if rng_k > 0 else 0          # +1 = the last closed candle went the trade's way in full
    fig = 0.01
    d_fig = ((math.ceil(lev / fig - 1e-9) * fig - lev) if s > 0 else (lev - math.floor(lev / fig + 1e-9) * fig)) / PIP
    vol10, vol60 = float(v[k - 9:k + 1].mean()), float(v[k - 59:k + 1].mean())
    row = {
        "id": tr["id"], "side": s, "humps": tr["humps"], "er8": round(er(k, 8), 3), "er16": round(er(k, 16), 3), "er30": round(er(k, 30), 3),
        "er60": round(er(k, 60), 3), "atr_pips": round(a / PIP, 2), "adx": round(float(adx[k]), 1),
        "trend30_atr": round((c[k] - c[k - 30]) * s / a, 2), "trend90_atr": round((c[k] - c[k - 90]) * s / a, 2),
        "trend240_atr": round((c[k] - c[k - 240]) * s / a, 2),
        "ny_hour": nyd.hour, "ny_min_of_day": nyd.hour * 60 + nyd.minute, "weekday": nyd.weekday(),
        "spread_pips": tr["trig_spread_pips"], "brk_ratio": round(tr["brk_ticks"] / max(tr["uhv_v"], 1), 3), "uhv_v": tr["uhv_v"],
        "stop_pips": round(abs(lev - ext) / PIP, 2), "bars_since_uhv": k - ku + 1, "box": tr["box"],
        "room60_pips": round(room60, 2), "room240_pips": round(room240, 2), "pos60": round(pos60, 3),
        "range20_atr": round((hi20 - lo20) / a, 2), "range60_atr": round((hi60 - lo60) / a, 2),
        "struct_with": int(struct_with), "uhv_body": round(body_u, 3), "last_body_dir": round(body_k, 3),
        "fig_ahead_pips": round(d_fig, 2), "vol10": round(vol10, 1), "vol_ratio10_60": round(vol10 / max(vol60, 1e-6), 3),
        "gap_pips": round(((tr["brk_bid"] - lev) * s) / PIP, 2) if tr.get("brk_bid") else 0.0,
        # outcome (never an input)
        "win": int(tr["win"]), "pnl": round(tr["pnl"], 2), "half": "train" if tr["t_dec"] < SPLIT else "test",
    }
    rows.append(row)
with open(os.path.join(HERE, "features.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
L = sum(1 - r["win"] for r in rows)
print(f"{len(rows)} trades, {L} losses, {len(rows[0]) - 4} features -> features.csv")
