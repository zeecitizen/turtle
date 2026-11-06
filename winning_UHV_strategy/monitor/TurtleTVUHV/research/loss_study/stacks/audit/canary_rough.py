"""canary_rough.py - look-ahead audit of the setups' level / extreme / uhv_t / uhv_v (uhv_setups.json 'roughs', built by
uhv_engine.build_setups with uhv_diamond.Diamond.update(window, ..., now) where the window's LAST bar is the forming minute = the breakout
minute). Two Diamonds run in lockstep over a segment: A gets the real forming bar, B the same minute with random o/h/l/c/v. Their roughs
(and fires) must be identical at every step. A's roughs must also reproduce the stored file's roughs for the segment (replication check)."""
import json, sys, time
from _common import *          # noqa: F401,F403
import numpy as np
import sim, uhv_diamond

N_END = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
t0 = time.time()
D = sim.data("year1")
rows = [[int(t), float(o), float(h), float(l), float(c), float(v)] for t, o, h, l, c, v in zip(D["t1"], D["o1"], D["h1"], D["l1"], D["c1"], D["v1"])]
stored = json.loads(open(os.path.join(ROOT, "simdata", "uhv_setups.json"), encoding="utf-8").read())["roughs"]
rng = np.random.default_rng(9)
A, Bd = uhv_diamond.Diamond(unit=0.00012), uhv_diamond.Diamond(unit=0.00012)
vol = lambda b: b[5] or None
mine, diff_rough, diff_cut = [], 0, 0
for i in range(400, min(N_END, len(rows))):
    win = rows[i - 400:i + 1]
    f = win[-1]
    o = f[1] + rng.normal(0, 5e-4); c = o + rng.normal(0, 8e-4)
    fake = [f[0], o, max(o, c) + abs(rng.normal(0, 5e-4)), min(o, c) - abs(rng.normal(0, 5e-4)), c, float(rng.integers(1, 900))]
    A.update(win, vol, f[0] + 30)
    Bd.update(win[:-1] + [fake], vol, f[0] + 30)
    ra, rb = A.rough, Bd.rough
    if ra != rb:
        diff_rough += 1
    if (A.cut or {}).get("t") != (Bd.cut or {}).get("t"):
        diff_cut += 1
    if ra and not (A.cut and A.cut["t"] == f[0]):
        mine.append([int(f[0]), int(ra["side"]), round(ra["level"], 5), round(ra["extreme"], 5), int(ra["uhv_t"]), float(ra["uhv_v"] or 0)])
tmax = rows[min(N_END, len(rows)) - 1][0]
ref = [r for r in stored if r[0] <= tmax]
same = sum(1 for x, y in zip(mine, ref) if x == y)
out = {"steps": min(N_END, len(rows)) - 400, "rough_differs_real_vs_fake_forming_bar": diff_rough, "cut_differs": diff_cut,
       "roughs_replicated": len(mine), "roughs_in_file_for_segment": len(ref), "identical_rows": same, "secs": round(time.time() - t0, 1)}
print(out)
json.dump(out, open(os.path.join(HERE, "out_rough.json"), "w"), indent=1)
