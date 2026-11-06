"""canary_ticks.py - look-ahead audit of the instant setups' own fields (uhv_engine._instant_setups): t (the breakout tick), sp (spread at it,
used by InpUhvMaxTrigSpread), bc (its bid, InpUhvMaxGapPips), bv (ticks so far, InpUhvLoudBrk), lo / hi (stop mode 2), and the clock that
InpUhvNoClose / FriCutNY / SunOpenMins / NewsNY / Holiday read. In EVERY minute where a UHV level is first crossed (accepted or 'too loud'),
every tick AFTER the crossing tick is replaced by random quotes on both sides of the level -> the setups must be identical, field by field.
Control: perturbing the ticks BEFORE / AT the crossing must change them (proves the cache was cleared and the comparison has teeth).
Output: out_ticks.json"""
import time, json
from _common import *          # noqa: F401,F403
import numpy as np
import uhv_engine

t0 = time.time()
base = base_inputs()
dfile = uhv_engine.det_file(base)
_S, TK = uhv_engine._setups(dfile)
T, B, A = TK["t"], TK["bid"], TK["ask"]
R = json.loads(open(dfile, encoding="utf-8").read())["roughs"]
PIP = 1e-4
# the first crossing of every UHV, replicated from _instant_setups (to know which ticks come after the decision)
used, first = set(), []
for t, side, level, extreme, uhv_t, uhv_v in R:
    if uhv_t in used:
        continue
    a, b = int(np.searchsorted(T, t)), int(np.searchsorted(T, t + 60))
    if b <= a:
        continue
    seg = B[a:b]
    hit = np.nonzero(seg > level)[0] if side > 0 else np.nonzero(seg < level)[0]
    if not len(hit):
        continue
    used.add(uhv_t)
    first.append((a, a + int(hit[0]), b, side, level))
FIELDS = ("t", "side", "level", "extreme", "uhv_t", "bar", "lo", "hi", "bv", "bc", "sp", "uv")


def setups(TKx):
    clear_caches()
    return [dict(s) for s in uhv_engine._instant_setups(TKx, 0.0, dfile)]


def compare(S0, S1):
    if len(S0) != len(S1):
        return {"count": [len(S0), len(S1)]}
    diff = {}
    for x, y in zip(S0, S1):
        for f in FIELDS:
            if x.get(f) != y.get(f):
                diff[f] = diff.get(f, 0) + 1
    return diff


S0 = setups(TK)
rng = np.random.default_rng(3)
res = {"setups": len(S0), "first_crossings": len(first)}
# 1) after the crossing tick: random quotes both sides of the level
Bp, Ap = B.copy(), A.copy()
nt = 0
for a, jj, b, side, level in first:
    L = b - (jj + 1)
    if L <= 0:
        continue
    bid = level + rng.uniform(-4, 4, L) * PIP
    Bp[jj + 1:b] = bid; Ap[jj + 1:b] = bid + rng.uniform(0.05, 3, L) * PIP
    nt += L
S1 = setups({"t": T, "bid": Bp, "ask": Ap})
res["after_crossing"] = {"ticks_perturbed": int(nt), "differences": compare(S0, S1)}
print("after the crossing tick:", res["after_crossing"])
del Bp, Ap
# 2) control: the ticks before / at the crossing (a fraction of the minutes) - must change things
Bc, Ac = B.copy(), A.copy()
nc = 0
for a, jj, b, side, level in first[::3]:
    L = jj + 1 - a
    bid = level + rng.uniform(-4, 4, L) * PIP
    Bc[a:jj + 1] = bid; Ac[a:jj + 1] = bid + rng.uniform(0.05, 3, L) * PIP
    nc += L
S2 = setups({"t": T, "bid": Bc, "ask": Ac})
res["control_before_crossing"] = {"ticks_perturbed": int(nc), "differences": compare(S0, S2) if len(S0) == len(S2) else {"count": [len(S0), len(S2)]}}
print("control (before / at the crossing):", res["control_before_crossing"])
del Bc, Ac
# 3) the spread field = ask - bid AT the breakout tick, and t = that tick (the decision moment); the fill is >= t + latency
ok_sp = sum(abs(s["sp"] - float(A[np.searchsorted(T, s["t"])] - B[np.searchsorted(T, s["t"])])) < 1e-9 for s in S0
            if T[np.searchsorted(T, s["t"])] == s["t"])
res["sp_equals_spread_at_trigger_tick"] = int(ok_sp)
res["trigger_after_bar_close"] = int(sum(s["t"] >= s["bar"] for s in S0))
res["secs"] = round(time.time() - t0, 1)
print(json.dumps({k: v for k, v in res.items() if k not in ("after_crossing", "control_before_crossing")}))
json.dump(res, open(os.path.join(HERE, "out_ticks.json"), "w"), indent=1)
