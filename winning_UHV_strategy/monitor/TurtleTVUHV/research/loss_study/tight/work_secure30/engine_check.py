"""engine_check.py - the finalist rule through the ENGINE (freed slots included): the range-bound test as the engine's own knobs.
secure / tight / zee100: InpUhvSafeRangeAtr=9.2 + InpUhvSafeRangeBars=120 (inside uhv_filters.secure); base: InpUhvRangeAtr=9.2 +
InpUhvRangeBars=120 (the loss filter). Python tick replay = HYPOTHESIS, NOT PROMOTED.  Run: NUMBA_CPU_NAME=generic py engine_check.py"""
import json
import os
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402
import sim  # noqa: E402

SPLIT = 1782864000
SAVED = os.path.join(ROOT, "settings", "saved")
D = sim.data("year1")
Z = np.load(os.path.join(ROOT, "research", "loss_study", "arrays.npz"))
print("atr arrays identical:", bool(np.allclose(np.asarray(D["atr"], float), Z["atr"], equal_nan=True)), flush=True)


def stats(rows):
    R = rows[rows[:, 10] == 0]
    out = []
    for nm, m in (("all", np.ones(len(R), bool)), ("tr", R[:, 1] < SPLIT), ("te", R[:, 1] >= SPLIT)):
        n = int(m.sum()); L = int((R[m, 6] <= 0).sum())
        out.append(f"{nm} {n}/{L}L {100 * (1 - L / max(n, 1)):.2f}% ${R[m, 6].sum():+,.0f}")
    return " | ".join(out)


CASES = [("secure", "2026-11-06 09-10-00.json", {"InpUhvSafeRangeAtr": "9.2", "InpUhvSafeRangeBars": "120"}),
         ("tight", "2026-11-06 09-00-00.json", {"InpUhvSafeRangeAtr": "9.2", "InpUhvSafeRangeBars": "120"}),
         ("zee100", "2026-11-06 07-33-17.json", {"InpUhvSafeRangeAtr": "9.2", "InpUhvSafeRangeBars": "120"}),
         ("base", "2026-11-05 05-45-38.json", {"InpUhvRangeAtr": "9.2", "InpUhvRangeBars": "120"})]
for name, fn, extra in CASES:
    inp = json.load(open(os.path.join(SAVED, fn), encoding="utf-8"))["inputs"]
    r0, _, _ = U.simulate(inp)
    r1, _, _ = U.simulate({**inp, **extra})
    print(f"{name:7s} as saved : {stats(r0)}", flush=True)
    print(f"{name:7s} + range  : {stats(r1)}", flush=True)
