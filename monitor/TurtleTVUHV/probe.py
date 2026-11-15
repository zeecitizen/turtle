"""probe.py - Risk Manager's Probe entry (Zee 2026-10-27: "take a small 0.01 probe trade -> if the trade fails we loose little -> if the trade
is going in our direction (crosses above the entry from below OR goes in our direction from start) -> we increase the lotsize only then").
EA v1.36 inputs InpProbeMode (0 off, 1 add once price moves InpProbeUsd our way, 2 add once it dipped InpProbeDipUsd against and came back
to InpProbeUsd), InpProbeLots (the probe), the rest of InpLots waits. Engine: sim_full (step 0 of the tick loop). Tester = hypothesis; MT5 decides."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import dexlab
import exitlab
import sim

KEYS = ("InpProbeMode", "InpProbeLots", "InpProbeUsd", "InpProbeDipUsd")
_CACHE = {}
_LOCK = threading.Lock()


def _run(inputs, ds, chart):
    k = json.dumps([inputs, ds, chart], sort_keys=True)
    with _LOCK:
        if k in _CACHE:
            return _CACHE[k]
    tr, _s, _st = sim.simulate(inputs, ds=ds, chart=chart)
    s = dexlab.stats(tr, exitlab.window_of(ds, inputs)[0])
    if s:
        s.pop("eq", None)
    with _LOCK:
        if len(_CACHE) > 200:
            _CACHE.clear()
        _CACHE[k] = s
    return s


def _with(inputs, p):
    return {**inputs, **{k: str(p[k]) for k in KEYS if k in p}}


def evaluate(inputs, ds="year1", mode="ea", p=None):
    """the loaded setting without the probe vs with these probe values"""
    chart = mode == "chart"
    off = {**inputs, "InpProbeMode": "0"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.map(lambda x: _run(x, ds, chart), (off, _with(inputs, p or {})))
    return {"off": a, "on": b, "sets": {k: str((p or {}).get(k, inputs.get(k, "0"))) for k in KEYS}}


def tune(inputs, ds="year1", mode="ea", p=None):
    """small grid around the sliders: confirm distance (and dip in mode 2) for the chosen probe mode; ranked by net, worst loss beside it"""
    chart = mode == "chart"
    p = dict(p or {})
    md = int(float(p.get("InpProbeMode", 1)) or 1)
    grid = []
    for u in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5):
        for d in ((0,) if md == 1 else (1, 2, 4, 6, 10)):
            grid.append({**p, "InpProbeMode": md, "InpProbeUsd": u, "InpProbeDipUsd": d})
    with ThreadPoolExecutor(max_workers=5) as pool:
        res = list(pool.map(lambda g: _run(_with(inputs, g), ds, chart), grid))
    rows = [{"sets": {k: str(g[k]) for k in KEYS if k in g}, "stats": s} for g, s in zip(grid, res) if s]
    rows.sort(key=lambda r: -r["stats"]["net"])
    return {"rows": rows[:12], "off": _run({**inputs, "InpProbeMode": "0"}, ds, chart)}
