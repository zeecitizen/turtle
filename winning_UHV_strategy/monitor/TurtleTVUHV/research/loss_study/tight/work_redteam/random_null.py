"""random_null.py (work_redteam) - section 3 of final_checks.py re-run with 24-hour TIMEOUTS COUNTED AS LOSSES (the engine flattens a round
still open after 24 h at that tick and scores pnl <= 0 as a loss; a weekend inside the window does the same). Same ticks, same geometry:
0.1-pip target, 21-pip stop, 0.3 s latency, buy at the ask / sell at the bid, exits on the other side; entries with a spread >= 1.0 pip or
inside 16:45-17:45 New York are skipped (the setting's own guards). Python tick replay = HYPOTHESIS, NOT PROMOTED.
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/tight/work_redteam/random_null.py"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402
from numba import njit  # noqa: E402

import uhv_engine as U  # noqa: E402

SPLIT = 1782864000
SAVED = os.path.join(ROOT, "settings", "saved")
x = json.load(open(os.path.join(SAVED, "2026-11-06 07-33-17.json"), encoding="utf-8"))["inputs"]
rows, _, _ = U.simulate(x)
z = rows[rows[:, 10] == 0]
S, TK = U._setups(U.det_file(x))
T, B, A = TK["t"], TK["bid"], TK["ask"]


@njit(cache=False)
def play(T, B, A, starts, sides, lat, tp, sl, hold):
    """1 = target, -1 = stop, 0 = still open after `hold` s (flattened at the last tick: a loss), 8 = spread >= 1 pip, 9 = no tick"""
    out = np.zeros(len(starts), dtype=np.int8)
    for n in range(len(starts)):
        i = np.searchsorted(T, starts[n] + lat)
        if i >= len(T) or T[i] - starts[n] > 60.0:
            out[n] = 9
            continue
        if A[i] - B[i] >= 1.0e-4 - 1e-9:
            out[n] = 8
            continue
        s = sides[n]
        f = np.float64(A[i]) if s > 0 else np.float64(B[i])
        res = 0
        for j in range(i, len(T)):
            if T[j] - starts[n] > hold:
                break
            px = np.float64(B[j]) if s > 0 else np.float64(A[j])
            m = (px - f) * s / 1e-4
            if m <= -sl:
                res = -1
                break
            if m >= tp - 1e-3:
                res = 1
                break
        out[n] = res
    return out


NY = ZoneInfo("America/New_York")


def ok_time(ts):
    d = dt.datetime.fromtimestamp(ts, NY)
    m = d.hour * 60 + d.minute
    return not (16 * 60 + 45 <= m < 17 * 60 + 45)


def report(label, o, st):
    m = (o == 1) | (o == -1) | (o == 0)
    v, t = o[m], st[m]
    n0 = int(np.sum(v == 0))
    out = [f"  {label}: n {len(v)} (timeouts {n0}, counted as losses)"]
    for h, mm in (("all", np.ones(len(v), bool)), ("Mar-Jun", t < SPLIT), ("Jul-Nov", t >= SPLIT)):
        w = v[mm]
        out.append(f"{h} WR {100 * np.mean(w == 1):.2f}% (timeouts dropped instead: {100 * np.mean(w[w != 0] == 1):.2f}%)")
    print(" | ".join(out), flush=True)


rng = np.random.default_rng(11)
idx = rng.integers(0, len(T) - 1, 60000)
st_ = np.asarray(T)[idx].astype(np.float64)
keep = np.array([ok_time(v) for v in st_])
st_ = st_[keep][:40000]
sd = rng.choice(np.array([-1, 1]), len(st_))
report("(a) random tick + random side", play(T, B, A, st_, sd, 0.3, 0.1, 21.0, 86400.0), st_)

zt, zs = z[:, 1] - 0.3, z[:, 0].astype(np.int64)
rep = 60
off = rng.uniform(5 * 60, 90 * 60, len(zt) * rep) * rng.choice(np.array([-1, 1]), len(zt) * rep)
st2 = np.repeat(zt, rep) + off
sd2 = np.repeat(zs, rep)
keep = np.array([ok_time(v) for v in st2])
st2, sd2 = st2[keep], sd2[keep]
report("(b) zee100's side, 5-90 min from its own 308 entries (60 correlated offsets each)", play(T, B, A, st2, sd2, 0.3, 0.1, 21.0, 86400.0), st2)
print("  for comparison (engine, as saved): tight Jul-Nov 99.21%, secure Jul-Nov 99.32%, base Jul-Nov 98.60%; Mar-Jun 99.70 / 97.92 / 96.64%")
