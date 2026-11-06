import json, sys, numpy as np
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import sim
from concurrent.futures import ThreadPoolExecutor
INP = json.load(open(r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved\2026-10-27 23-50-31.json"))["inputs"]
def run(kv):
    tr, su, st = sim.simulate({**INP, **{k: str(v) for k, v in kv.items()}}, ds="m15")
    t = np.array([x for x in tr if x[10] == 0]); p = t[:, 6]
    eq = np.cumsum(p); dd = (np.maximum.accumulate(eq) - eq).max()
    return f"{len(p):5d}  WR {100*(p>0).mean():5.1f}%  net {p.sum():+12,.0f}  worst {p.min():+9,.0f}  DD {dd:9,.0f}"
G = [("saved, no probe", {"InpProbeMode": 0})]
for be in (0, 1):
    for u in (5, 10, 15, 20, 25):
        G.append((f"4c >${u:<2} stop {'ghost entry' if be else 'original   '}", {"InpProbeMode": 3, "InpProbeBars": 4, "InpProbeUsd": u, "InpProbeLots": 0.01, "InpProbeBe": be}))
with ThreadPoolExecutor(4) as ex:
    for (n, _), r in zip(G, ex.map(lambda g: run(g[1]), G)): print(f"{n:32s} {r}")
