"""common.py (work_wf) - run Turtle TV UHV's engine on Zee's saved settings with overrides; nothing here edits the engine.
run(over) -> dict with the REAL trades (rows[:,10]==0): entry time, side, $ (1 lot), plus summaries by half / month."""
import datetime as dt
import json
import os
import sys
import time

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))       # .../monitor/TurtleTVUHV
sys.path.insert(0, ROOT)
OUT = HERE                               # every output stays in work_wf (no chdir: the engine resolves its own paths)
import numpy as np  # noqa: E402

import uhv_engine as U  # noqa: E402

SAVED = os.path.join(ROOT, "settings", "saved")
SPLIT = 1782864000                       # 2026-07-01 00:00 UTC (the harness' train / test split)
ZEE = json.load(open(os.path.join(SAVED, "2026-11-06 07-33-17.json"), encoding="utf-8"))["inputs"]


def run(over=None, base=None):
    inp = dict(base or ZEE)
    for k, v in (over or {}).items():
        inp[k] = str(v)
    t0 = time.time()
    rows, _, cnt = U.simulate(inp)
    R = rows[rows[:, 10] == 0] if len(rows) else rows
    tin = R[:, 1] if len(R) else np.zeros(0)
    usd = R[:, 6] if len(R) else np.zeros(0)
    return {"t": tin.tolist(), "side": (R[:, 0].astype(int).tolist() if len(R) else []), "usd": usd.tolist(),
            "ghosts": int((rows[:, 10] == 1).sum()) if len(rows) else 0, "secs": round(time.time() - t0, 2)}


def summ(res, lo=None, hi=None):
    t = np.asarray(res["t"]); u = np.asarray(res["usd"])
    m = np.ones(len(t), bool)
    if lo is not None:
        m &= t >= lo
    if hi is not None:
        m &= t < hi
    n = int(m.sum()); L = int((u[m] <= 0).sum())
    return {"n": n, "L": L, "wr": round(100 * (1 - L / n), 2) if n else None, "net": round(float(u[m].sum()), 2)}


def month(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m")
