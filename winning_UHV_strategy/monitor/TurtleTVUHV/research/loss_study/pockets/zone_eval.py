"""zone_eval.py - Zee's zone model (2026-11-06), each risky zone alone and combined, in the engine (InpUhvRiskMgr 4 = skip the risky zones):
share of trades inside the zone, losses inside (of 172), the untouched zone's trades / win rate, by half; and the trend harvest rule.
Run: py research/loss_study/pockets/zone_eval.py"""
import json
import os
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402

SPLIT = 1782864000
B = json.load(open(os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json"), encoding="utf-8"))["inputs"]


def run(x):
    tr, _, _ = U.simulate(dict(B, **x))
    r = tr[tr[:, 10] == 0]
    return r


base = run({})
bk = {(int(x[0]), round(x[1])): x[6] < 0 for x in base}
N0, L0 = len(base), int((base[:, 6] < 0).sum())


def show(name, x):
    r = run(x)
    keys = {(int(q[0]), round(q[1])) for q in r}
    gone = [k for k in bk if k not in keys]
    gl = sum(1 for k in gone if bk[k])
    parts = []
    for half, m in (("all", np.ones(len(r), bool)), ("Mar-Jun", r[:, 1] < SPLIT), ("Jul-Nov", r[:, 1] >= SPLIT)):
        q = r[m]; L = int((q[:, 6] < 0).sum())
        parts.append(f"{half} {len(q):5d}tr {L:3d}L {100 * (1 - L / max(len(q), 1)):6.2f}%")
    print(f"{name:44s} zone holds {100 * len(gone) / N0:5.1f}% of trades and {gl:3d}/{L0} losses ({100 * gl / L0:4.1f}%) | untouched: " + " | ".join(parts), flush=True)


print(f"BASE: {N0} trades, {L0} losses, WR {100 * (1 - L0 / N0):.2f}%")
show("start of trend (< 2 humps)", {"InpUhvRiskMgr": "4", "InpUhvZStart": "1"})
show("end of trend (> 4 humps)", {"InpUhvRiskMgr": "4", "InpUhvZEnd": "1"})
show("end of trend (> 3 humps)", {"InpUhvRiskMgr": "4", "InpUhvZEnd": "1", "InpUhvZEndHumps": "3"})
show("inside a range box (20 bars < 3 ATR)", {"InpUhvRiskMgr": "4", "InpUhvZRange": "1"})
show("inside a range box (20 bars < 2 ATR)", {"InpUhvRiskMgr": "4", "InpUhvZRange": "1", "InpUhvZRangeAtr": "2"})
show("near S/R 1 pip (60 bars)", {"InpUhvRiskMgr": "4", "InpUhvZSR": "1"})
show("near S/R 0.5 pip (60 bars)", {"InpUhvRiskMgr": "4", "InpUhvZSR": "0.5"})
show("near S/R 2 pips (60 bars)", {"InpUhvRiskMgr": "4", "InpUhvZSR": "2"})
show("news minute / spike", {"InpUhvRiskMgr": "4", "InpUhvZNews": "1"})
show("near the close (16-18 NY, Fri 13+)", {"InpUhvRiskMgr": "4", "InpUhvZClose": "1"})
show("near an open (London/NY/stocks/Sunday)", {"InpUhvRiskMgr": "4", "InpUhvZOpen": "1"})
show("ALL zones together", {"InpUhvRiskMgr": "4", "InpUhvZStart": "1", "InpUhvZEnd": "1", "InpUhvZRange": "1", "InpUhvZSR": "1",
                            "InpUhvZNews": "1", "InpUhvZClose": "1", "InpUhvZOpen": "1"})
show("all but start-of-trend", {"InpUhvRiskMgr": "4", "InpUhvZEnd": "1", "InpUhvZRange": "1", "InpUhvZSR": "1", "InpUhvZNews": "1",
                                "InpUhvZClose": "1", "InpUhvZOpen": "1"})
show("harvest: 2 wins per trend (stop on loss)", {"InpUhvHarvestWins": "2"})
show("harvest: 3 wins per trend (stop on loss)", {"InpUhvHarvestWins": "3"})
show("harvest: 3 wins per trend (no stop on loss)", {"InpUhvHarvestWins": "3", "InpUhvHarvestStopLoss": "0"})
show("harvest 3 + close + news + open zones", {"InpUhvHarvestWins": "3", "InpUhvRiskMgr": "4", "InpUhvZClose": "1", "InpUhvZNews": "1", "InpUhvZOpen": "1"})
