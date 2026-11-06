import json, os, sys, datetime as dt
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import numpy as np
import uhv_engine as U
inp = json.load(open("settings/saved/2026-11-06 09-00-00.json", encoding="utf-8"))["inputs"]
tr, su, cnt = U.simulate(inp)
R = tr[tr[:, 10] == 0]
print(len(R), "real rows; counts", cnt)
L = R[R[:, 6] < 0]
for x in L:
    print(dt.datetime.fromtimestamp(x[1], dt.timezone.utc), "side", int(x[0]), "pnl", round(x[6], 1), "why", int(x[13]), "hold_h", round((x[4]-x[1])/3600, 2), "best_R", round(x[15], 3), "worst_R", round(x[16], 3))
whys = {}
for x in R:
    whys[int(x[13])] = whys.get(int(x[13]), 0) + 1
print("exit reasons:", whys)
