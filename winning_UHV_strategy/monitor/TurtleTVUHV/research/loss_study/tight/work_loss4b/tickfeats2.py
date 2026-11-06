"""tickfeats2.py (work_loss4b) - more DECISION-TIME tick features (ticks strictly before the breakout tick), merged into tickfeats.json.
  vel_N     bid change over the last N s up to the tick before the break, trade direction, pips (momentum INTO the level)
  imb_N     bid upticks minus downticks in the trade direction over the last N s, as a share of the bid changes
  spm_N     mean ask-bid over the last N s (pips)
  at_uhv    ticks with the bid ON the level since the UHV candle closed
  near_uhv  ticks within 0.1 pip of the level since the UHV candle closed
  secs_uhv  seconds from the UHV candle's close to the break
  prior_N   minutes back (N = 15, 30, 60) - did the bid already trade beyond the level BEFORE the UHV candle opened? the deepest such
            excursion in pips (0 = never: a fresh level)
Python replay = HYPOTHESIS ONLY."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
import uhv_ticks  # noqa: E402

P = 1e-4
TK = uhv_ticks.load()
T = TK["t"]; B = TK["bid"].astype(np.float64); AS = TK["ask"].astype(np.float64)
TF = json.load(open(os.path.join(HERE, "tickfeats.json")))
Z = np.load(os.path.join(HERE, "..", "..", "arrays.npz"))
t1 = Z["t"]


def one(t, f):
    td, s, lev = float(t["t_dec"]), int(t["side"]), float(t["level"])
    jb = int(np.searchsorted(T, td - 1e-6))
    b_prev = B[jb - 1]
    for N in (1, 2, 5, 10, 30):
        a = int(np.searchsorted(T, td - N))
        a = max(0, min(a, jb - 1))
        f[f"vel_{N}"] = float(np.round((b_prev - B[a - 1 if a > 0 else 0]) * s / P, 1))
    for N in (10, 30, 60):
        a = int(np.searchsorted(T, td - N))
        bb = B[a:jb]
        dd = np.sign(np.diff(bb)) * s
        nz = dd[dd != 0]
        f[f"imb_{N}"] = float(nz.sum() / len(nz)) if len(nz) else 0.0
        f[f"spm_{N}"] = float(np.mean(AS[a:jb] - B[a:jb]) / P) if jb > a else 0.0
    ku_t = int(t1[t["ku"]])
    a = int(np.searchsorted(T, ku_t + 60))                      # after the UHV candle closed
    d = np.round((lev - B[a:jb]) * s / P, 1)
    f["at_uhv"] = int(np.sum(np.abs(d) < 0.05))
    f["near_uhv"] = int(np.sum(d <= 0.15))
    f["secs_uhv"] = float(td - (ku_t + 60))
    for N in (15, 30, 60):
        a0 = int(np.searchsorted(T, ku_t - N * 60)); a1 = int(np.searchsorted(T, ku_t))
        if a1 > a0:
            ex = (B[a0:a1] - lev) * s / P                             # > 0 = beyond the level in the trade direction
            f[f"prior_{N}"] = float(max(0.0, np.round(ex.max(), 1)))
        else:
            f[f"prior_{N}"] = 0.0
    return f


if __name__ == "__main__":
    seen = set()
    for st in ("tight", "secure", "base"):
        for t in json.load(open(os.path.join(HERE, "..", f"trades_{st}.json"), encoding="utf-8")):
            if t["id"] in seen:
                continue
            seen.add(t["id"])
            one(t, TF[t["id"]])
    json.dump(TF, open(os.path.join(HERE, "tickfeats.json"), "w"))
    for tid in ("1019-171329-S", "1023-145031-B", "1019-025421-S", "1020-091233-S", "1020-141441-S", "1022-150841-B", "1023-052230-B", "1023-141514-B"):
        f = TF[tid]
        print(tid, {k: f[k] for k in ("vel_1", "vel_2", "vel_5", "vel_10", "imb_10", "imb_30", "spm_30", "at_uhv", "near_uhv", "secs_uhv", "prior_15", "prior_30", "prior_60")})
