"""camel_tune.py - Zee 2026-11-05: "market is going up .. we took a sell.. coz our camel humps started showing red lines .. the camel humps need
tuning. test the tuning". One camel setting per run: finds the UHV setups again with that camel (hump size CAM_PIV, flip after CAM_CONFIRM
humps in a row), plays them through the tick engine for two exits, prints one JSON line. Python tick replay = a hypothesis (CLAUDE.md).
Run: py camel_tune.py <cam_piv> <cam_confirm>"""
import json
import os
import sys
import time

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import uhv_diamond as UD  # noqa: E402

UD.CAM_PIV, UD.CAM_CONFIRM = int(sys.argv[1]), int(sys.argv[2])
import sim  # noqa: E402
import uhv_engine as U  # noqa: E402

t0 = time.time()
D = sim.data("year1")
rows = [[int(t), float(o), float(h), float(l), float(c), float(v)] for t, o, h, l, c, v in zip(D["t1"], D["o1"], D["h1"], D["l1"], D["c1"], D["v1"])]
dia = UD.Diamond(unit=0.00012)
S, seen = [], set()
for i in range(400, len(rows)):
    win = rows[i - 400:i + 1]
    dia.update(win, lambda b: b[5] or None, win[-1][0] + 30)
    cut = dia.cut
    if cut and cut["t"] not in seen:
        seen.add(cut["t"])
        S.append({"t": int(cut["t"]), "side": cut["side"], "uhv_t": int(cut["uhv_t"]), "level": cut["level"], "extreme": cut["extreme"],
                  "laws": cut["laws"], "ea": bool(cut["ea"]), "royal": bool(cut["royal"]), "er": cut["er"]})
U._S.update(m="tune", S=S)
U._setups = lambda: (U._S["S"], U._S.setdefault("T", U.uhv_ticks.load()))
split = 1782864000
out = {"piv": UD.CAM_PIV, "confirm": UD.CAM_CONFIRM, "setups": len(S)}
for name, inp in (("tiny", {"InpUhvFixTp": "0.6", "InpUhvBeR": "0"}), ("rr2", {"InpUhvBeR": "0"})):
    tr, _, _ = U.simulate(dict(inp, InpUhvLots="0.01", InpBandsB="1" * 21, InpBandsS="1" * 21))
    r = tr[tr[:, 10] == 0]
    for part, m in (("A", r[:, 1] < split), ("B", r[:, 1] >= split)):
        x = r[m]
        out[f"{name}_{part}"] = [int(len(x)), round(float(100 * (x[:, 6] > 0).mean()) if len(x) else 0.0, 1), round(float(x[:, 6].sum()), 2)]
out["secs"] = round(time.time() - t0)
print(json.dumps(out), flush=True)
