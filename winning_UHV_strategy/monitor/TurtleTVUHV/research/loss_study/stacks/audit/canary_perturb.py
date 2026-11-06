"""canary_perturb.py - look-ahead audit, END-TO-END PERTURBATION: for a sample of real setups (the exact arguments the engine sends), every
bar AFTER k is replaced by an adversarial random walk (o h l c, ticks, ATR) - or the data is simply cut after k - and every scanner grid value
of every loss setting (+ companions) and the Risk Manager's secure() is re-evaluated. The returned filter NAME must not change. This needs no
assumption about how _prep's arrays are meant to be read (it would catch a leak inside _prep or inside the stored ATR).
Positive control: the same path with a leaky _swings (lastH[k] - a pivot AT k, unconfirmed) must show changed decisions.  Output: out_perturb.json"""
import time, json, sys
from _common import *          # noqa: F401,F403
import numpy as np
import sim, uhv_filters

NS = int(sys.argv[1]) if len(sys.argv) > 1 else 240
t0 = time.time()
D = sim.data("year1")
full = {k: np.asarray(D[k]) for k in ("t1", "o1", "h1", "l1", "c1", "v1", "atr")}
n = len(full["t1"])
Z = np.load(os.path.join(HERE, "calls.npz"))           # the engine's exact skip() arguments, saved by record_calls.py (no ticks loaded here:
cols = [str(x) for x in Z["cols"]]                      #  the machine is short of memory while the other stacks run)
calls = []
for row in Z["calls"]:
    d = dict(zip(cols, row.tolist()))
    for kk in ("side", "k", "ku", "brk_ticks"):
        d[kk] = int(d[kk])
    for kk in ("uhv_v", "brk_ticks", "brk_px", "level", "ts", "ku"):
        if d[kk] == -1:
            d[kk] = None
    calls.append(d)
cfgs, scfgs = skip_configs(), secure_configs()
rng = np.random.default_rng(5)
# sample: half random, half from setups where at least one filter config fires on the original data (so a change is visible)
idx_all = np.arange(len(calls))
samp = sorted(set(rng.choice(idx_all, NS, replace=False).tolist()))


def decide(Dx, a):
    out = []
    for main, d in cfgs:
        out.append(uhv_filters.skip(fv, d, Dx, a["side"], a["k"], a["px"], a["atr_k"], a["extreme"], level=a["level"], ku=a["ku"], ts=a["ts"],
                                    uhv_v=a["uhv_v"], brk_ticks=a["brk_ticks"], brk_px=a["brk_px"]))
    for d in scfgs:
        out.append(bool(uhv_filters.secure(fv, d, Dx, a["side"], a["k"])))
    return out


W = {kk: v.copy() for kk, v in full.items()}             # one working copy, refilled in place for every sample (no new big arrays)


def perturbed(k, seed):
    r = np.random.default_rng(seed)
    for kk in W:
        W[kk][:] = full[kk]
    Dm = W
    L = n - (k + 1)
    c0 = full["c1"][k]
    cp = c0 + np.cumsum(r.normal(0, 4e-4, L))
    op = np.r_[c0, cp[:-1]]
    Dm["o1"][k + 1:] = op; Dm["c1"][k + 1:] = cp
    Dm["h1"][k + 1:] = np.maximum(op, cp) + r.uniform(0, 8e-4, L)
    Dm["l1"][k + 1:] = np.minimum(op, cp) - r.uniform(0, 8e-4, L)
    Dm["v1"][k + 1:] = r.integers(0, 800, L)
    Dm["atr"][k + 1:] = r.uniform(1e-5, 5e-3, L)
    return Dm


def run(label, sample):
    names = [m for m, _ in cfgs] + ["RiskMgr secure()"] * len(scfgs)
    clear_caches()
    D0 = full
    orig = {i: decide(D0, calls[i]) for i in sample}          # one _prep for all originals
    chg = {"perturb": {}, "trunc": {}}
    fired = {}
    for i in sample:
        a = calls[i]; k = a["k"]
        for o, nm in zip(orig[i], names):
            fired[nm] = fired.get(nm, 0) + (o not in (None, True))
        for mode in ("perturb", "trunc"):
            Dm = perturbed(k, 1000 + i) if mode == "perturb" else {kk: v[:k + 1] for kk, v in full.items()}
            clear_caches()
            try:
                new = decide(Dm, a)
            except Exception as e:                            # an index past the cut data would raise here = a leak
                chg[mode]["EXCEPTION " + type(e).__name__] = chg[mode].get("EXCEPTION " + type(e).__name__, 0) + 1
                continue
            for o, x, nm in zip(orig[i], new, names):
                if o != x:
                    chg[mode][nm] = chg[mode].get(nm, 0) + 1
    print(f"[{label}] sample {len(sample)}  changed decisions: perturb {chg['perturb']}  trunc {chg['trunc']}  ({time.time() - t0:.0f}s)")
    return {"sample": len(sample), "configs": len(names), "evaluations_per_mode": len(sample) * len(names), "changed": chg,
            "fired_on_original": fired}


res = {"sample": len(samp)}
res["main"] = run("filters as shipped", samp)
real = uhv_filters._swings


def leaky(last, k, nn):
    out, j = [], (last[k] if k >= 0 else -1)
    while j >= 0 and len(out) < nn:
        out.append(j); j = last[j - 1] if j >= 1 else -1
    return out[::-1]


uhv_filters._swings = leaky
try:
    res["positive_control_leaky_swings"] = run("positive control: leaky _swings", samp[:120])
finally:
    uhv_filters._swings = real
res["secs"] = round(time.time() - t0, 1)
json.dump(res, open(os.path.join(HERE, "out_perturb.json"), "w"), indent=1, default=str)
