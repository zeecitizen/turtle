"""common.py - shared pieces for the clean-days stacking search (research/loss_study/stacks/cleandays).

Python tick replay = HYPOTHESIS only. MT5 or live fills promote (CLAUDE.md, monitor/doctrine.py).

  base_inputs()   the 97.7% setting (settings/saved/2026-11-05 05-45-38.json) with every engine default filled in for keys the saved file
                  predates (the loss filters, InpUhvNoClose, InpUhvMaxTrigSpread - all off at "0"), so the base runs exactly as saved.
  score(rows)     TRAIN / TEST / ALL: trades, losses, WR, net, FX days with a trade, loss-free days (and their share), loss keys.
                  TRAIN = entries before 2026-07-01 00:00 UTC (ts 1782864000), TEST = from then on. A "loss-free day" is an FX day
                  (17:00 New York -> 17:00 New York) with >= 1 trade and no losing trade (a trade with $ result < 0). Real trades only
                  (rows[:, 10] == 0; stood-aside ghosts are excluded but still block, as in the engine).
"""
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402

NY = ZoneInfo("America/New_York")
SPLIT = 1782864000                      # 2026-07-01 00:00 UTC
BASE_FILE = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")

# FX-day boundaries: 17:00 New York on every calendar day (DST-correct through zoneinfo). A trade at ts belongs to the FX day that
# started at the last boundary <= ts; that FX day is labelled by the NEXT calendar date (Sunday 17:00 NY opens Monday's FX day).
_d0 = dt.date(2026, 2, 20)
_BOUNDS = []
_LABELS = []
for i in range(0, 300):
    d = _d0 + dt.timedelta(days=i)
    _BOUNDS.append(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=NY).timestamp())
    _LABELS.append((d + dt.timedelta(days=1)).isoformat())
_BOUNDS = np.asarray(_BOUNDS)


def fxday(ts):
    """index of the FX day (17:00 NY -> 17:00 NY) for each UTC timestamp"""
    return np.searchsorted(_BOUNDS, np.asarray(ts, dtype=float), side="right") - 1


def fxlabel(idx):
    return _LABELS[int(idx)]


def base_inputs():
    import uhv_engine as U
    saved = json.load(open(BASE_FILE, encoding="utf-8"))["inputs"]
    d = {k: v[0] for k, v in U.UHV_DEFAULTS.items()}
    d.update(saved)
    return d


def score(rows):
    r = rows[rows[:, 10] == 0] if len(rows) else rows
    t = r[:, 1] if len(r) else np.zeros(0)
    pnl = r[:, 6] if len(r) else np.zeros(0)
    loss = pnl < 0
    day = fxday(t) if len(t) else np.zeros(0, dtype=int)
    out = {}
    for part, m in (("train", t < SPLIT), ("test", t >= SPLIT), ("all", np.ones(len(t), bool))):
        n = int(m.sum()); L = int(loss[m].sum())
        days = np.unique(day[m]); ldays = np.unique(day[m & loss])
        nd, nl = len(days), len(ldays)
        out[part] = {"n": n, "L": L, "wr": round(100.0 * (n - L) / n, 3) if n else 0.0, "net": round(float(pnl[m].sum()), 2),
                     "days": nd, "clean": nd - nl, "clean_pct": round(100.0 * (nd - nl) / nd, 3) if nd else 0.0,
                     "day_ids": [int(x) for x in days], "loss_day_ids": [int(x) for x in ldays]}
    out["loss_keys"] = sorted({(int(x[0]), int(round(x[1]))) for x in r[loss]}) if len(r) else []
    return out
