"""Engine-native cures on 2026-10-25 05-58-25, m15 2023->now (the Overview's tester)."""
import json, sys, numpy as np
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim, exitlab
from concurrent.futures import ThreadPoolExecutor
S = json.load(open(r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved\2026-10-25 05-58-25.json"))
def run(g):
    name, kv, lab = g
    inp = server.full_inputs({**S["inputs"], **{k: str(v) for k, v in kv.items()}})
    lab = exitlab.clean(lab) if lab else None
    tr, _, _ = sim.simulate(inp, ds="m15", lab=lab)
    p = np.array([x[6] for x in tr if x[10] == 0]); t = np.array([x[1] for x in tr if x[10] == 0])
    eq = np.cumsum(p); dd = (np.maximum.accumulate(eq) - eq).max(); m = np.median(t)
    w, l = p[p > 0], p[p <= 0]
    return name, dict(n=len(p), wr=round(100*len(w)/len(p), 1), net=round(p.sum()), worst=round(p.min()), dd=round(dd),
                      aw=round(w.mean()), al=round(l.mean()) if len(l) else 0, h1=round(p[t < m].sum()), h2=round(p[t >= m].sum()))
G = [("baseline", {}, None)]
for n in (2, 3, 4, 6, 8, 12, 16): G.append((f"time stop {n} candles", {}, {"max_bars": n}))
for n in (4, 6, 8): G.append((f"stale stop {n} candles (< +0R)", {}, {"stale_bars": n, "stale_r": 0}))
G += [("TP 40 pips", {"InpFixTpPips": 40}, None),
      ("barbell half@20 half@40", {"InpFixTpPips": 40, "InpXP1R": 0.08, "InpXP1Frac": 0.5, "InpXP1Be": "false"}, None),
      ("barbell + BE after lot1", {"InpFixTpPips": 40, "InpXP1R": 0.08, "InpXP1Frac": 0.5, "InpXP1Be": "true"}, None),
      ("barbell half@20 half@60 + BE", {"InpFixTpPips": 60, "InpXP1R": 0.08, "InpXP1Frac": 0.5, "InpXP1Be": "true"}, None),
      ("inversion TP $25 SL $2", {"InpFixTpPips": 250, "InpSlUsd": 2, "InpXTgt": 1}, None)]
with ThreadPoolExecutor(6) as ex: res = list(ex.map(run, G))
json.dump(res, open(r"C:\Users\zeesh\turtle\monitor\saad_view\research\cure_engine.json", "w"), indent=1)
for n, s in res: print(f"{n:34s} {s}")
