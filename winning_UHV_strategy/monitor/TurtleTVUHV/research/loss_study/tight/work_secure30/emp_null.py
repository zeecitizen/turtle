"""emp_null.py - EMPIRICAL random-entry null on the real PrimeXBT ticks: for every trade of a stack, K entries on the SAME side with the
SAME stop distance and the same 0.1-pip target / 0.3 s latency, at random ticks within +-90 min of the trade (spread < 1.0 pip, not in the
NY rollover hour, not within 2 min of the real entry). If the stack's loss rate ~= this null, its entries have no edge beyond geometry.
Python tick replay = HYPOTHESIS, NOT PROMOTED.   Run: NUMBA_CPU_NAME=generic py emp_null.py [K]"""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(HERE))
import api_tight as AT  # noqa: E402
import uhv_engine as U  # noqa: E402
import uhv_ticks  # noqa: E402

PIP = 1e-4
NY = ZoneInfo("America/New_York")
TK = uhv_ticks.load()
TT, BB, AA = TK["t"], TK["bid"], TK["ask"]
K = int(sys.argv[1]) if len(sys.argv) > 1 else 10
rng = np.random.default_rng(7)


def play(t0, side, sl):
    a, b = int(np.searchsorted(TT, t0)), int(np.searchsorted(TT, t0 + U.MAX_HOLD_S))
    r = U._play(TT, BB, AA, a, b, t0, side, 0.3, sl, 0.1, 0.0, 0.0, 0.0, 0, 2.0, 0.0, 0.0, 0.5, False, 0.0, 0.25, 0.0, 0.0, 0.5,
                0.0, -0.5, 0.0, 0.0, 0.5, 1.0, 0.0, 0.0, 0.0)
    return r


def ok_time(t0):
    i = int(np.searchsorted(TT, t0))
    if i >= len(TT) or AA[i] - BB[i] >= 1.0 * PIP - 1e-12:
        return False
    ny = dt.datetime.fromtimestamp(t0, NY)
    return not (16 * 60 + 45 <= ny.hour * 60 + ny.minute < 17 * 60 + 45)


if __name__ == "__main__":
    out = {}
    for st in sys.argv[2:] or ("secure", "tight", "base"):
        T = AT.STACKS[st]
        res = []
        for t in T:
            sl = abs(t["fill"] - t["stop"]) / PIP
            # the real trade replayed through the same play (sanity)
            real = play(t["t_dec"], t["side"], sl)
            nl, n = 0, 0
            tries = 0
            while n < K and tries < 10 * K:
                tries += 1
                t0 = t["t_dec"] + rng.uniform(-5400, 5400)
                if abs(t0 - t["t_dec"]) < 120 or not ok_time(t0):
                    continue
                # start at a real tick time (the null decides on a tick like the engine)
                i = int(np.searchsorted(TT, t0))
                if i >= len(TT):
                    continue
                r = play(float(TT[i]), t["side"], sl)
                if r[5] < 0:
                    continue
                n += 1; nl += r[0] < 0
            res.append((t["id"], t["t_dec"] < AT.SPLIT, not t["win"], real[0] < 0, nl, n))
        out[st] = res
        for part, f in (("all", lambda r: True), ("train", lambda r: r[1]), ("test", lambda r: not r[1])):
            R = [r for r in res if f(r)]
            n = len(R); L = sum(r[2] for r in R); Lr = sum(r[3] for r in R)
            nl = sum(r[4] for r in R); nn = sum(r[5] for r in R)
            print(f"{st:7s} {part:5s} trades {n:5d} real losses {L:4d} ({100*L/n:.2f}%)  replay {Lr:4d} | random-entry null: {nl}/{nn} = {100*nl/max(nn,1):.2f}% "
                  f"-> expected {n*nl/max(nn,1):.1f} losses", flush=True)
    import pickle  # noqa: E402
    pickle.dump(out, open(os.path.join(HERE, f"emp_null_K{K}.pkl"), "wb"))
