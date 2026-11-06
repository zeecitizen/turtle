"""engine_spread.py (work_loss4b) - engine confirmation of the one rule that maps to an existing input: InpUhvMaxTrigSpread 1.0 -> 0.5
on the tight / zee100 / secure settings (the engine re-runs one-position blocking). Python replay = HYPOTHESIS, NOT PROMOTED."""
import json, os, sys
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import numpy as np
import uhv_engine as U
SPLIT = 1782864000
for nm, fn in (("tight", "2026-11-06 09-00-00.json"), ("zee100", "2026-11-06 07-33-17.json"), ("secure", "2026-11-06 09-10-00.json")):
    base = json.load(open(os.path.join("settings", "saved", fn), encoding="utf-8"))["inputs"]
    for sp in ("1.0", "0.5"):
        inp = dict(base); inp["InpUhvMaxTrigSpread"] = sp
        tr, _, _ = U.simulate(inp)
        R = tr[tr[:, 10] == 0]
        parts = []
        for lab, m in (("all", np.ones(len(R), bool)), ("tr", R[:, 1] < SPLIT), ("te", R[:, 1] >= SPLIT)):
            n = int(m.sum()); L = int((R[m, 6] < 0).sum())
            parts.append(f"{lab} {n} tr {L} L WR {100 * (1 - L / max(n, 1)):.2f}% net ${R[m, 6].sum():+,.0f}")
        print(f"{nm:7s} MaxTrigSpread {sp}: " + " | ".join(parts), flush=True)
