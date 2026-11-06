"""engine_extra.py (work_judge) - two engine receipts for the verdict. Python tick replay = HYPOTHESIS, NOT PROMOTED.
  1. Zee's last step (InpUhvSafeErMax 0.45 -> 0.35) applied to the WIDER secure zone (humps 2-5, ER 0.15-0.45): does the 0.35 cap carry?
  2. the save gate: zee100's own TEST half vs every setting-backed variant (from engine_runs.json)."""
import json
import os
import sys

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine_runs as E  # noqa: E402

E.run("secure", "AS SAVED (baseline)")
E.run("secure", "+ InpUhvSafeErMax 0.35 (Zee's last cut)", InpUhvSafeErMax=0.35)
E.run("secure", "+ InpUhvSafeErMax 0.35 + MaxTrigSpread 0.5", InpUhvSafeErMax=0.35, InpUhvMaxTrigSpread=0.5)
R = json.load(open(os.path.join(HERE, "engine_runs.json"), encoding="utf-8"))
z = R["zee100 | AS SAVED (baseline)"]["stats"]["test"]
print(f"\nSAVE GATE: zee100 TEST = {z['n']} trades / {z['L']} losses / {z['wr']}% / {z['net']:+.2f}; a new setting must have 0 test losses AND more than {z['n']} test trades")
for k, v in R.items():
    if k.startswith(("tight", "zee100")) and "AS SAVED" not in k and "RunPips" not in k and "NewsNY" not in k:
        t = v["stats"]["test"]
        ok = t["L"] <= z["L"] and (t["n"] > z["n"] or t["L"] < z["L"]) and t["wr"] >= z["wr"]
        print(f"  {k:62s} test {t['n']}/{t['L']}L {t['wr']}% {t['net']:+.2f} -> {'PASSES' if ok else 'fails'} the gate")
