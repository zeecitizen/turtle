"""common.py - the red team's OWN scorer for the "Maximise TRAIN net $" loss-cure stack (written independently of stacks/net/stack_net.py).

Engine files are only IMPORTED, never edited. TRAIN = entries before 2026-07-01 00:00 UTC (1782864000), TEST = from then on (entry time =
rows[:, 1]). A loss = a real trade (rows[:, 10] == 0) with $ result < 0. Loss-free day = an FX day (17:00 New York -> 17:00 New York, found per
trade with zoneinfo) with >= 1 trade and no losing trade, counted within each split. Python tick replay = HYPOTHESIS, NOT PROMOTED."""
import datetime as dt
import hashlib
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))            # monitor/TurtleTVUHV
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

ENGINE_FILES = ("uhv_engine.py", "uhv_filters.py", "uhv_diamond.py", "scan.py", "sim.py")


def engine_hash():
    h = hashlib.sha1()
    for f in ENGINE_FILES:
        with open(os.path.join(ROOT, f), "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:10]


H0 = engine_hash()
import uhv_engine as U  # noqa: E402
import uhv_filters as UF  # noqa: E402
import scan  # noqa: E402

NY = ZoneInfo("America/New_York")
SPLIT = 1782864000
BASE_FILE = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
RAW = json.load(open(BASE_FILE, encoding="utf-8"))
BASE = dict(RAW["inputs"])
for _k, (_d, _) in U.UHV_DEFAULTS.items():            # loss-cure settings are absent from the saved base: their defaults (all off)
    BASE.setdefault(_k, _d)

STACK = {"InpUhvSRPips": "5", "InpUhvDeepRet": "0.8", "InpUhvFreshBreak": "1", "InpUhvNoClose": "true", "InpUhvFriCutNY": "15",
         "InpUhvLoudBrk": "0.95"}
STACK_ORDER = ["InpUhvSRPips", "InpUhvDeepRet", "InpUhvFreshBreak", "InpUhvNoClose", "InpUhvFriCutNY", "InpUhvLoudBrk"]

_DAY = {}


def fxday(ts):
    """FX day label (date string) of one UTC timestamp: New York local time + 7 h, so 17:00 NY starts the next label"""
    key = int(ts)
    d = _DAY.get(key)
    if d is None:
        d = (dt.datetime.fromtimestamp(key, NY) + dt.timedelta(hours=7)).strftime("%Y-%m-%d")
        _DAY[key] = d
    return d


def month(ts):
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m")


def stats(r):
    n = int(len(r))
    if n == 0:
        return dict(n=0, L=0, zero=0, loss_rate=0.0, wr=0.0, net=0.0, npt=0.0, days=0, clean=0, clean_pct=0.0, avg_win=0.0, avg_loss=0.0)
    p = r[:, 6]
    loss = p < 0
    days = [fxday(x) for x in r[:, 1]]
    alld = set(days)
    bad = {d for d, lz in zip(days, loss) if lz}
    L = int(loss.sum())
    return dict(n=n, L=L, zero=int((p == 0).sum()), loss_rate=100.0 * L / n, wr=100.0 * (n - L) / n, net=float(p.sum()),
                npt=float(p.sum()) / n, days=len(alld), clean=len(alld - bad), clean_pct=100.0 * len(alld - bad) / len(alld),
                avg_win=float(p[~loss].mean()) if (~loss).any() else 0.0, avg_loss=float(p[loss].mean()) if L else 0.0)


def result_block(r):
    p = r[:, 6]
    eq = np.cumsum(p[np.argsort(r[:, 4], kind="stable")])
    dd = float((np.maximum.accumulate(np.r_[0.0, eq])[1:] - eq).max()) if len(eq) else 0.0
    gw, gl = float(p[p > 0].sum()), float(-p[p < 0].sum())
    n, L = len(p), int((p < 0).sum())
    return {"n": int(n), "net": round(float(p.sum()), 2), "pf": round(gw / gl, 3) if gl > 0 else None, "wr": round(100 * (n - L) / max(n, 1), 2),
            "avg_loss": round(float(p[p < 0].mean()), 2) if L else 0.0, "worst_loss": round(float(p.min()), 2) if n else 0.0,
            "dd": round(dd, 2)}


def run(changes):
    """simulate base + changes; returns (real-trade rows, skip counts)"""
    tr, _, cnt = U.simulate(dict(BASE, **changes))
    return tr[tr[:, 10] == 0], {k: int(v) for k, v in cnt.items()}


def split(r):
    return r[r[:, 1] < SPLIT], r[r[:, 1] >= SPLIT]


def score(r):
    a, b = split(r)
    return {"train": stats(a), "test": stats(b), "all": stats(r)}


def excess(base_s, s):
    """net gain beyond a random cut of the same number of trades at the base's $/trade (> 0 = the cut picked better than random)"""
    return (s["net"] - base_s["net"]) + (base_s["n"] - s["n"]) * base_s["npt"]


def wilson(k, n, z=1.959964):
    if n == 0:
        return (0.0, 0.0)
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def rnd(d):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def line(s):
    return (f"{s['n']:5d} tr {s['L']:4d} L  loss rate {s['loss_rate']:5.2f}%  WR {s['wr']:6.2f}%  clean {s['clean']:3d}/{s['days']:3d} "
            f"({s['clean_pct']:5.1f}%)  net {s['net']:>10,.0f} ({s['npt']:+.2f}/tr)")
