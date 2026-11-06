"""risk_manager_eval.py - the Risk Manager (InpUhvRiskMgr, uhv_filters.secure) on the 97.7% setting, in the engine: trade only the secure
zone (mode 2), or loss filters only outside it (mode 1). Trades / losses / WR / loss-free days, all and by half. Hypothesis until MT5/live.
Run: py research/loss_study/risk_manager_eval.py"""
import os
import sys

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cause_settings_eval import B, SPLIT, U, nyday  # noqa: E402

import numpy as np  # noqa: E402


def row(name, x):
    tr, _, _ = U.simulate(dict(B, **x))
    r = tr[tr[:, 10] == 0]
    out = []
    for half, m in (("all", np.ones(len(r), bool)), ("Mar-Jun", r[:, 1] < SPLIT), ("Jul-Nov", r[:, 1] >= SPLIT)):
        q = r[m]; L = int((q[:, 6] < 0).sum())
        days = {}
        for x_ in q:
            k = nyday(x_[1]); days[k] = days.get(k, False) or bool(x_[6] < 0)
        clean = 100 * sum(1 for v in days.values() if not v) / max(len(days), 1)
        out.append(f"{half} {len(q):5d}tr {L:3d}L {100 * (1 - L / max(len(q), 1)):6.2f}% {clean:3.0f}%clean {len(days):3d}d")
    print(f"{name:52s} " + " | ".join(out), flush=True)


row("base (97.7%)", {})
row("RM2: secure only (2-5 humps, ER 0.15-0.45)", {"InpUhvRiskMgr": "2"})
row("RM2: tight secure (2-3 humps, ER 0.30-0.45)", {"InpUhvRiskMgr": "2", "InpUhvSafeHumpsMax": "3", "InpUhvSafeErMin": "0.3"})
row("RM2: secure + not a range (20 bars >= 3 ATR)", {"InpUhvRiskMgr": "2", "InpUhvSafeRangeAtr": "3"})
row("RM1: risky zone needs 2+ humps", {"InpUhvRiskMgr": "1", "InpUhvMinHumps": "2"})
row("RM1: risky zone no S/R just ahead (1.0)", {"InpUhvRiskMgr": "1", "InpUhvSRAhead": "1.0"})
row("RM1: risky zone S/R 0.5 + run 6 + Fri 13 NY", {"InpUhvRiskMgr": "1", "InpUhvSRAhead": "0.5", "InpUhvRunPips": "6", "InpUhvFriCutNY": "13"})
row("RM1: risky zone 2+ humps + S/R 1.0 + range 2ATR", {"InpUhvRiskMgr": "1", "InpUhvMinHumps": "2", "InpUhvSRAhead": "1.0", "InpUhvRangeAtr": "2"})
row("RM2 + NY rollover + spread 1.0", {"InpUhvRiskMgr": "2", "InpUhvNoClose": "1", "InpUhvMaxTrigSpread": "1.0"})
row("RM2 tight + NY rollover + spread 1.0", {"InpUhvRiskMgr": "2", "InpUhvSafeHumpsMax": "3", "InpUhvSafeErMin": "0.3", "InpUhvNoClose": "1", "InpUhvMaxTrigSpread": "1.0"})
