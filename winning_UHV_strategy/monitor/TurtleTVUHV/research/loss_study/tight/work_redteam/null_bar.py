"""null_bar.py (work_judge) - how often does a RANDOM rule (skip each trade id with probability f, the same decision for the same id on
every stack) pass (a) the task's LITERAL bar (WR up on both halves of secure, or of base) and (b) the STRICT bar used in rescore.py (lift > 1
and hypergeometric p < 0.05 on both halves of secure or base_g)? 4000 draws per skip fraction. Python replay = HYPOTHESIS.
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/tight/work_judge/null_bar.py"""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
from scipy.stats import hypergeom

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import api_tight  # noqa: E402

NY = ZoneInfo("America/New_York")
SPLIT = api_tight.SPLIT


def guarded(t):
    ny = dt.datetime.fromtimestamp(t["t_dec"], NY)
    m = ny.hour * 60 + ny.minute
    return (16 * 60 + 45 <= m < 17 * 60 + 45) or t["trig_spread_pips"] >= 1.0 - 1e-9


ST = {"secure": api_tight.STACKS["secure"], "base": api_tight.STACKS["base"]}
ST["base_g"] = [t for t in ST["base"] if not guarded(t)]
ids = sorted({t["id"] for T in ST.values() for t in T})
pos = {i: j for j, i in enumerate(ids)}
ARR = {}
for nm, T in ST.items():
    ix = np.array([pos[t["id"]] for t in T]); loss = np.array([not t["win"] for t in T]); tr = np.array([t["t_dec"] < SPLIT for t in T])
    ARR[nm] = (ix, loss, tr)
rng = np.random.default_rng(20261106)
NDRAW = 4000
print("Random-skip null for the two bars (Python replay = HYPOTHESIS). Columns: skip fraction | P(literal pass) | P(strict pass)")
for f in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7):
    lit = strict = 0
    for _ in range(NDRAW):
        u = rng.random(len(ids)) < f
        ok_lit, ok_strict = False, False
        for nm in ("secure", "base", "base_g"):
            ix, loss, tr = ARR[nm]
            sk = u[ix]
            up, sig = [], []
            for h in (tr, ~tr):
                N, K = int(h.sum()), int((loss & h).sum())
                n, x = int((sk & h).sum()), int((sk & loss & h).sum())
                up.append((1 - (K - x) / max(N - n, 1)) > (1 - K / max(N, 1)))
                sig.append(n > 0 and x * N > n * K and hypergeom.sf(x - 1, N, K, n) < 0.05)
            if nm in ("secure", "base") and all(up):
                ok_lit = True
            if nm in ("secure", "base_g") and all(sig):
                ok_strict = True
        lit += ok_lit; strict += ok_strict
    print(f"  f = {f:.2f} | literal {100 * lit / NDRAW:5.1f}% | strict {100 * strict / NDRAW:5.2f}%", flush=True)
