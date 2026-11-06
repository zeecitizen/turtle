"""rt_common.py - scoring helpers for the red-team of the clean-days stack (research/loss_study/stacks/redteam_Maximisethe).

Python tick replay = HYPOTHESIS. NOT PROMOTED. Only MT5 or live fills decide (CLAUDE.md).

Written independently of cleandays/common.py (same definitions, own code):
  TRAIN = entries before 2026-07-01 00:00 UTC (ts 1782864000), TEST = from then on.
  FX day = 17:00 New York -> 17:00 New York (zoneinfo, DST-correct). A loss-free day has >= 1 real trade and no trade with $ result < 0.
  Real trades = rows[:, 10] == 0 (stood-aside ghosts excluded; they still block inside the engine).
  thin_exp = the loss-free share EXPECTED if, on each FX day, the config's trade count were drawn at random from the BASE's trades of that
             day (exact hypergeometric). excess = observed loss-free share - thin_exp: what is left after "just trading less"."""
import datetime as dt
import json
import os
import sys
from math import comb, lgamma, exp, log
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402

NY = ZoneInfo("America/New_York")
SPLIT = 1782864000
BASE_FILE = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
STACK = {"InpUhvMinHumps": "4", "InpUhvMinTicks": "40", "InpUhvFreshBreak": "8", "InpUhvMaxGapPips": "0.5"}

_d0 = dt.date(2026, 2, 20)
_B = np.asarray([dt.datetime(*(_d0 + dt.timedelta(days=i)).timetuple()[:3], 17, 0, tzinfo=NY).timestamp() for i in range(300)])


def fxday(ts):
    return np.searchsorted(_B, np.asarray(ts, dtype=float), side="right") - 1


def fxday_label(i):
    return (_d0 + dt.timedelta(days=int(i) + 1)).isoformat()      # the FX day that opens 17:00 NY on d is labelled d+1


def base_inputs():
    import uhv_engine as U
    saved = json.load(open(BASE_FILE, encoding="utf-8"))["inputs"]
    d = {k: v[0] for k, v in U.UHV_DEFAULTS.items()}
    d.update(saved)
    return d


def real(rows):
    return rows[rows[:, 10] == 0] if len(rows) else np.zeros((0, 20))


def perday_expect(t_f, t_b, loss_b):
    """exact expected loss-free share (%) of the config's trading days if its per-day counts were random picks from the base's trades that day"""
    bd = fxday(t_b)
    N = dict(zip(*[x.tolist() for x in np.unique(bd, return_counts=True)])) if len(bd) else {}
    Lc = dict(zip(*[x.tolist() for x in np.unique(bd[loss_b], return_counts=True)])) if loss_b.any() else {}
    ps = []
    if len(t_f):
        for d, c in zip(*np.unique(fxday(t_f), return_counts=True)):
            n_, l_ = N.get(int(d), 0), Lc.get(int(d), 0)
            if n_ == 0:
                ps.append(1.0)                        # no base trade that day (freed slot only): nothing to draw a loss from
                continue
            c = min(int(c), n_)
            ps.append(comb(n_ - l_, c) / comb(n_, c) if c <= n_ - l_ else 0.0)
    return 100.0 * float(np.mean(ps)) if ps else 0.0


def part_stats(r, m, rb=None, mb=None):
    t, pnl = r[m, 1], r[m, 6]
    loss = pnl < 0
    n, L = int(len(t)), int(loss.sum())
    days = np.unique(fxday(t)) if n else np.zeros(0, int)
    ldays = np.unique(fxday(t[loss])) if L else np.zeros(0, int)
    out = {"n": n, "L": L, "rate": round(100.0 * L / n, 4) if n else 0.0, "wr": round(100.0 * (n - L) / n, 3) if n else 0.0,
           "net": round(float(pnl.sum()), 2), "days": int(len(days)), "clean": int(len(days) - len(ldays)),
           "clean_pct": round(100.0 * (len(days) - len(ldays)) / len(days), 3) if len(days) else 0.0}
    if rb is not None:
        te = perday_expect(t, rb[mb, 1], rb[mb, 6] < 0)
        out["thin_exp"] = round(te, 3)
        out["excess"] = round(out["clean_pct"] - te, 3)
    return out


def masks(t):
    return {"train": t < SPLIT, "test": t >= SPLIT, "all": np.ones(len(t), bool)}


def score(rows, rb=None):
    r = real(rows)
    m = masks(r[:, 1])
    mb = masks(rb[:, 1]) if rb is not None else None
    return {p: part_stats(r, m[p], rb, mb[p] if mb else None) for p in ("train", "test", "all")}


# ---- exact small-sample statistics (no scipy needed)
def binom_cdf(k, n, p):
    return float(sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1)))


def clopper_pearson(x, n, alpha=0.05):
    def bis(f, lo, hi):
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if f(mid):
                hi = mid
            else:
                lo = mid
        return 0.5 * (lo + hi)
    lo = 0.0 if x == 0 else bis(lambda p: 1 - binom_cdf(x - 1, n, p) >= alpha / 2, 0.0, 1.0)   # P(X >= x | p) = a/2
    hi = 1.0 if x == n else bis(lambda p: binom_cdf(x, n, p) <= alpha / 2, 0.0, 1.0)          # P(X <= x | p) = a/2
    return lo, hi


def hypergeom_cdf(k, N, K, n):
    """P(X <= k) drawing n of N items of which K are 'losses', without replacement"""
    tot = comb(N, n)
    return float(sum(comb(K, i) * comb(N - K, n - i) for i in range(0, min(k, K, n) + 1)) / tot)
