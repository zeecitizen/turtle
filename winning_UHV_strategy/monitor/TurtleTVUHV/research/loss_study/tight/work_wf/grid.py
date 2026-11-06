"""grid.py (work_wf) - every secure-zone combo of the walk-forward grid, run ONCE by the engine on the full period (Mar 6 - Nov 4 2026),
on Zee's 100% file (2026-11-06 07-33-17.json) with only the four zone bounds changed. Both walk-forward directions are derived from this
cache (wf.py): the engine reads only closed candles and one position at a time only lets a trade block LATER ones, so the Mar-Jun trades of
a full run are exactly the trades of a Mar-Jun-only run (the Jul-Nov ones can differ by at most the single round spanning Jul 1).
Split = the fill time (breakout tick + 0.3 s) vs 2026-07-01 00:00 UTC.
Writes grid_cache.npz (per combo: t, usd) and grid_summary.json."""
import itertools
import json
import time

import numpy as np

from common import run, summ, SPLIT, OUT
import os

HUMPS_MIN = [1, 2, 3]
HUMPS_MAX = [2, 3, 4, 5, 6]
ER_MIN = [0.15, 0.20, 0.25, 0.30, 0.32, 0.35, 0.40]
ER_MAX = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]


def key(hmin, hmax, emin, emax):
    return f"h{hmin}-{hmax}_er{emin:.2f}-{emax:.2f}"


if __name__ == "__main__":
    t0 = time.time()
    arrs, out = {}, []
    combos = [(a, b, c, d) for a, b, c, d in itertools.product(HUMPS_MIN, HUMPS_MAX, ER_MIN, ER_MAX) if a <= b and c < d - 1e-9]
    print(len(combos), "combos", flush=True)
    for i, (a, b, c, d) in enumerate(combos):
        r = run({"InpUhvSafeHumpsMin": a, "InpUhvSafeHumpsMax": b, "InpUhvSafeErMin": f"{c:.2f}", "InpUhvSafeErMax": f"{d:.2f}"})
        kk = key(a, b, c, d)
        arrs[kk + "_t"] = np.asarray(r["t"]); arrs[kk + "_u"] = np.asarray(r["usd"])
        out.append({"key": kk, "hmin": a, "hmax": b, "emin": c, "emax": d, "all": summ(r), "mj": summ(r, hi=SPLIT), "jn": summ(r, lo=SPLIT)})
        if i % 50 == 0:
            print(i, kk, out[-1]["all"], round(time.time() - t0, 1), "s", flush=True)
    np.savez_compressed(os.path.join(OUT, "grid_cache.npz"), **arrs)
    json.dump(out, open(os.path.join(OUT, "grid_summary.json"), "w"), indent=0)
    print("done", len(out), round(time.time() - t0, 1), "s")
