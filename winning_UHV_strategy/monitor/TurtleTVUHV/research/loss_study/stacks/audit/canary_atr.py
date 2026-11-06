"""canary_atr.py - look-ahead audit: where does the stored year1 'atr' come from? The engine passes atr[k] to skip() as a scalar and secure()
reads D['atr'][k] directly, so the read-trace cannot see a leak hidden INSIDE the stored array. Compare it elementwise to causal / shifted /
centred recomputations (TradingView ta.sma(ta.tr(true), n) = sim._atr_adx)."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import numpy as np
import sim
D = sim.data("year1")
o, h, l, c = (np.asarray(D[k], dtype=float) for k in ("o1", "h1", "l1", "c1"))
atr = np.asarray(D["atr"], dtype=float)
m = len(c)
tr = np.empty(m); tr[0] = h[0] - l[0]; tr[1:] = np.maximum(h[1:], c[:-1]) - np.minimum(l[1:], c[:-1])
cs = np.r_[0.0, np.cumsum(tr)]
def sma(n, shift=0):               # window ending at i+shift
    out = np.full(m, np.nan)
    for i in range(m):
        e = i + shift
        if e < 0 or e >= m:
            continue
        a = max(0, e - n + 1)
        out[i] = (cs[e + 1] - cs[a]) / (e - a + 1)
    return out
res = {}
ref = sim._atr_adx(o, h, l, c, 14)[0]
res["max|stored - sim._atr_adx(14)|"] = float(np.nanmax(np.abs(atr - ref)))
for n in (14,):
    for sh in (-1, 1, 7):
        alt = sma(n, sh)
        res[f"max|stored - sma{n} window ending i{sh:+d}|"] = float(np.nanmax(np.abs(atr - alt)))
# Wilder RMA as another candidate
rma = np.empty(m); rma[0] = tr[0]
for i in range(1, m):
    rma[i] = rma[i - 1] + (tr[i] - rma[i - 1]) / 14
res["max|stored - Wilder RMA14|"] = float(np.max(np.abs(atr - rma)))
# truncation: the causal formula on bars [0..m0] gives the same atr[m0]
rng = np.random.default_rng(7)
bad = 0
for m0 in rng.integers(500, m - 10, 30):
    a2 = sim._atr_adx(o[:m0 + 1], h[:m0 + 1], l[:m0 + 1], c[:m0 + 1], 14)[0]
    bad += int(abs(a2[-1] - atr[m0]) > 1e-12)
res["truncation mismatches (30 cut points)"] = bad
for k_, v in res.items():
    print(f"{k_:55s} {v}")
json.dump(res, open(os.path.join(HERE, "out_atr.json"), "w"), indent=1)
