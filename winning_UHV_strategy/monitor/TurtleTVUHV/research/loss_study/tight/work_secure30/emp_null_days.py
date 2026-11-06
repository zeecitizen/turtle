"""emp_null_days.py - random-entry null WITHOUT path sharing: the same side / stop / 0.1-pip target at the same time of day (+-30 min) on
OTHER weekdays within +-10 days (spread < 1.0, not in the NY rollover hour). Removes the bias of entries placed inside the same price swing.
HYPOTHESIS ONLY.   Run: NUMBA_CPU_NAME=generic py emp_null_days.py K stacks..."""
import datetime as dt
import os
import pickle
import sys
from zoneinfo import ZoneInfo

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from emp_null import TT, AT, play, ok_time  # noqa: E402

K = int(sys.argv[1]) if len(sys.argv) > 1 else 30
rng = np.random.default_rng(5)
out = {}
for st in sys.argv[2:] or ("secure", "base"):
    T = AT.STACKS[st]
    res = []
    for t in T:
        sl = abs(t["fill"] - t["stop"]) / 1e-4
        nl = n = tries = 0
        while n < K and tries < 20 * K:
            tries += 1
            dd = int(rng.integers(-10, 11))
            if dd == 0:
                continue
            t0 = t["t_dec"] + dd * 86400 + rng.uniform(-1800, 1800)
            wd = dt.datetime.fromtimestamp(t0, dt.timezone.utc).weekday()
            if wd >= 5 or not ok_time(t0):
                continue
            i = int(np.searchsorted(TT, t0))
            if i >= len(TT) or TT[i] - t0 > 120:
                continue
            r = play(float(TT[i]), t["side"], sl)
            if r[5] < 0:
                continue
            n += 1; nl += r[0] < 0
        res.append((t["id"], t["t_dec"] < AT.SPLIT, not t["win"], None, nl, n))
    out[st] = res
    for part, f in (("all", lambda r: True), ("train", lambda r: r[1]), ("test", lambda r: not r[1])):
        R = [r for r in res if f(r)]
        n = len(R); L = sum(r[2] for r in R); nl = sum(r[4] for r in R); nn = sum(r[5] for r in R)
        print(f"{st:7s} {part:5s} trades {n:5d} real losses {L:4d} ({100*L/n:.2f}%) | other-days null {100*nl/max(nn,1):.2f}% -> expected {n*nl/max(nn,1):.1f}", flush=True)
pickle.dump(out, open(os.path.join(HERE, f"emp_null_days_K{K}.pkl"), "wb"))
