import json, sys, numpy as np
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import sim
S = json.load(open(r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved\2026-10-25 05-58-25.json"))
INP = S["inputs"]
def trades(inp=INP, ds="m15", **kw):
    tr, su, st = sim.simulate(inp, ds=ds, **kw)
    return np.array([x for x in tr if x[10] == 0]), st
