"""tickfeats.py (work_loss4b) - DECISION-TIME tick features for every trade of the three stacks, keyed by trade id, from the PrimeXBT
tick stream the engine replays (uhv_ticks). Only ticks STRICTLY BEFORE the breakout tick's timestamp are read (t < t_dec), so nothing
the EA could not know at the moment it decides is used. Writes tickfeats.json (no outcome fields).

d = (level - bid) * side in pips = the distance the bid still has to travel to break the level (> 0 short of it, <= 0 at / beyond it).
  at_N     ticks in the last N s with the bid ON the level (|d| < 0.05 pip)  - the level being tested
  near_N   ticks in the last N s with d <= 0.15 (within 0.1 pip of the level)
  dwell_N  share of the last N s (time-weighted) the bid spent within 0.1 pip of the level
  n_N      ticks in the last N s
  d0_N     d at the start of the window (how far away the bid was N s before the break)
  dmax_N   the farthest the bid was from the level in the window
  cyc_60   touch episodes in the last 60 s: the bid came to the level (d <= 0.05), went >= 0.2 pip away, and came back
  jump     the breakout tick's own bid move (pips, trade direction) vs the tick before it
  sp_prev  ask - bid on the tick before the breakout
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


def one(t):
    td, s, lev = float(t["t_dec"]), int(t["side"]), float(t["level"])
    jb = int(np.searchsorted(T, td - 1e-6))            # the breakout tick (first tick at t_dec); ticks [.. jb) are strictly before it
    f = {}
    for N in (5, 10, 30, 60, 120):
        a = int(np.searchsorted(T, td - N))
        tt, bb = T[a:jb], B[a:jb]
        d = np.round((lev - bb) * s / P, 1)
        f[f"n_{N}"] = int(len(bb))
        f[f"at_{N}"] = int(np.sum(np.abs(d) < 0.05))
        f[f"near_{N}"] = int(np.sum(d <= 0.15))
        if len(bb):
            # time-weighted dwell: each tick's state holds until the next tick (the last one until td)
            nxt = np.append(tt[1:], td)
            dur = np.clip(nxt - tt, 0, None)
            # the state at the window start is the tick before a (if any)
            pre_d = np.round((lev - B[a - 1]) * s / P, 1) if a > 0 else None
            pre_dur = (tt[0] - (td - N)) if a > 0 else 0.0
            tot = dur.sum() + pre_dur
            nearT = dur[d <= 0.15].sum() + (pre_dur if (pre_d is not None and pre_d <= 0.15) else 0.0)
            f[f"dwell_{N}"] = float(nearT / tot) if tot > 0 else 0.0
            f[f"d0_{N}"] = float(pre_d) if pre_d is not None else float(d[0])
            f[f"dmax_{N}"] = float(max(d.max(), pre_d if pre_d is not None else -9))
        else:
            pre_d = np.round((lev - B[a - 1]) * s / P, 1) if a > 0 else 0.0
            f[f"dwell_{N}"] = 1.0 if pre_d <= 0.15 else 0.0
            f[f"d0_{N}"] = float(pre_d); f[f"dmax_{N}"] = float(pre_d)
    a = int(np.searchsorted(T, td - 60))
    d = np.round((lev - B[a:jb]) * s / P, 1)
    cyc, armed = 0, True
    for x in d:
        if armed and x <= 0.05:
            cyc += 1; armed = False
        elif not armed and x >= 0.2:
            armed = True
    f["cyc_60"] = cyc
    f["jump"] = float(np.round((B[jb] - B[jb - 1]) * s / P, 1)) if jb > 0 else 0.0
    f["sp_prev"] = float(np.round((AS[jb - 1] - B[jb - 1]) / P, 1)) if jb > 0 else 0.0
    f["gap_prev"] = float(td - T[jb - 1]) if jb > 0 else 0.0
    return f


if __name__ == "__main__":
    out = {}
    for st in ("tight", "secure", "base"):
        for t in json.load(open(os.path.join(HERE, "..", f"trades_{st}.json"), encoding="utf-8")):
            if t["id"] not in out:
                out[t["id"]] = one(t)
    json.dump(out, open(os.path.join(HERE, "tickfeats.json"), "w"))
    print(len(out), "trades")
    for tid in ("1019-171329-S", "1023-145031-B", "1019-025421-S", "1020-091233-S", "1020-141441-S", "1022-150841-B", "1023-052230-B", "1023-141514-B", "0408-075606-B", "0723-001905-S"):
        f = out[tid]
        print(tid, {k: f[k] for k in ("at_10", "at_30", "at_60", "near_30", "dwell_10", "dwell_30", "dwell_60", "cyc_60", "d0_5", "d0_10", "d0_30", "n_30", "jump", "sp_prev")})
