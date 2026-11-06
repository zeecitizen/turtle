"""eval_variant.py - (1) per-pocket train/test detail for the ONE pre-registered sensitivity variant that showed test skill
(onesided_depth2_minsup3%_K2: one-sided thresholds only, <= 2 conditions, support >= 3%, K = 2; defined in beam.py's SENS before any test
outcome was seen), and (2) a FAMILY-WISE null for 'the best of the 14 configurations on test': for each permutation of the train outcomes
(circular shift within feed regime) ALL 14 configurations are re-run and the best test z-score is kept, so picking the best variant after
looking at test is charged for. z = (test losses in union - expected at that coverage) / hypergeometric sd.
Run: cd .../pockets && py method_b_beam/eval_variant.py [--nperm 100]"""
import gc
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "beam.py"), encoding="utf-8").read()
head = src.split("# ----------------------------------------------------------------------------------------------------------------------------- real run")[0]
nperm = int(sys.argv[sys.argv.index("--nperm") + 1]) if "--nperm" in sys.argv else 100
sys.argv = [os.path.join(HERE, "beam.py")]
g = {"__file__": os.path.join(HERE, "beam.py"), "__name__": "beam_lib"}
exec(compile(head, "beam_lib", "exec"), g)
greedy, half_stats, perm_within, ctext = (g[k] for k in ("greedy", "half_stats", "perm_within", "ctext"))
conds, TR, TE, y_tr, BASE_CFG, Y, NTR = (g[k] for k in ("conds", "TR", "TE", "y_tr", "BASE_CFG", "Y", "NTR"))

CFGS = {
    "PRIMARY": dict(BASE_CFG),
    "K1.5": dict(BASE_CFG, k=1.5), "K2": dict(BASE_CFG, k=2.0), "K4": dict(BASE_CFG, k=4.0),
    "minsup2%": dict(BASE_CFG, nmin=int(math.ceil(0.02 * NTR))), "depth2": dict(BASE_CFG, depth=2),
    "plain_K3": dict(BASE_CFG, score="plain"), "plain_K2": dict(BASE_CFG, score="plain", k=2.0),
    "no_day_rule": dict(BASE_CFG, min_days=1, max_day_share=1.0),
    "onesided": dict(BASE_CFG, allowed="onesided"), "onesided_K2": dict(BASE_CFG, allowed="onesided", k=2.0),
    "depth2_minsup2%": dict(BASE_CFG, depth=2, nmin=int(math.ceil(0.02 * NTR))),
    "depth2_minsup2%_K2": dict(BASE_CFG, depth=2, nmin=int(math.ceil(0.02 * NTR)), k=2.0),
    "onesided_depth2_minsup3%_K2": dict(BASE_CFG, allowed="onesided", depth=2, nmin=int(math.ceil(0.03 * NTR)), k=2.0),
}
VAR = "onesided_depth2_minsup3%_K2"
NTE, LTE = int(TE.sum()), int(Y[TE].sum())


def zscore(te_n, te_L):
    if te_n == 0:
        return 0.0
    p = LTE / NTE
    mu = te_n * p
    sd = math.sqrt(te_n * p * (1 - p) * (NTE - te_n) / (NTE - 1))
    return (te_L - mu) / sd if sd > 0 else 0.0


# ---- (1) the variant in detail
pk, nc = greedy(y_tr, CFGS[VAR])
rules = [p["rule"] for p in pk]
st_tr, u_tr = half_stats(rules, TR)
st_te, u_te = half_stats(rules, TE)
print(f"VARIANT {VAR}: {len(pk)} pockets, {nc:,} candidates scored")
detail = []
for i, (p, a, b) in enumerate(zip(pk, st_tr, st_te)):
    txt = " and ".join(ctext(conds[c]) for c in p["rule"])
    drift = b["share"] / a["share"]
    detail.append(dict(rule=txt, train=a, test=b, drift=drift, search={k: v for k, v in p.items() if k not in ("mask", "rule")}))
    print(f"  S{i+1}: {txt}   (search: n={p['n']} L={p['L']} E={p['E']:.2f} score={p['score']:.2f} loss-days={p['days']} maxday={p['maxday']})")
    for nm, s, u in (("train", a, u_tr), ("test ", b, u_te)):
        print(f"      {nm}: {100*s['share']:5.2f}% of trades ({s['n']}), losses {s['L']}/{u['Ltot']} ({100*s['Lshare']:.1f}%), rate "
              f"{100*s['rate']:.2f}% = {s['rate']/u['base_rate']:.2f}x half base, {s['rate']/Y.mean():.2f}x 2.26%; untouched WR alone "
              f"{100*s['untouched_wr_alone']:.2f}% | incremental n={s['n_inc']} L={s['L_inc']} | cumulative {100*s['cum_share']:.1f}%, "
              f"{s['cum_L']} losses, untouched WR {100*s['cum_untouched_wr']:.2f}% [loss-days {s['loss_days']}]")
    print(f"      coverage drift test/train = {drift:.2f}")
for nm, u in (("TRAIN", u_tr), ("TEST ", u_te)):
    need = int(math.ceil(u["Ltot"] - 0.007 * (u["N"] - u["n"])))
    print(f"  UNION {nm}: {100*u['share']:.1f}% of trades ({u['n']}), {u['L']}/{u['Ltot']} losses ({100*u['Lshare']:.1f}%), pocket rate "
          f"{100*u['rate']:.2f}% ({u['rate']/u['base_rate']:.2f}x), untouched WR {100*u['untouched_wr']:.2f}% (base {100*u['base_wr']:.2f}%) "
          f"[99.3% needs >= {need}]")
print(f"  random subset of test at this coverage: {LTE*u_te['n']/NTE:.1f} losses expected")

# ---- (2) real z of every configuration, then the family-wise null
real = {}
for nm, cfg in CFGS.items():
    pkr, _ = greedy(y_tr, cfg)
    _, ut = half_stats([p["rule"] for p in pkr], TE)
    real[nm] = dict(te_n=ut["n"], te_L=ut["L"], z=zscore(ut["n"], ut["L"]))
best_real = max(real.values(), key=lambda r: r["z"])["z"]
print("\nreal test z per configuration: " + ", ".join(f"{k} {v['z']:+.2f} ({v['te_L']}/{v['te_n']})" for k, v in real.items()))
rng = np.random.default_rng(99)
maxz, varz = [], []
t0 = time.time()
PART = os.path.join(HERE, "results_variant_fwer_partial.json")


def run_cfg(yp, cfg):
    for attempt in range(6):                                   # the machine is shared and nearly out of commit memory: wait and retry
        try:
            pkn, _ = greedy(yp, cfg)
            _, ut = half_stats([p["rule"] for p in pkn], TE)
            return zscore(ut["n"], ut["L"])
        except MemoryError:
            gc.collect()
            print(f"    MemoryError, retry {attempt+1} in 30s", flush=True)
            time.sleep(30)
    raise MemoryError("gave up after 6 retries")


for b in range(nperm):
    yp = perm_within(y_tr, rng, "shift")
    zs = {nm: run_cfg(yp, cfg) for nm, cfg in CFGS.items()}
    maxz.append(max(zs.values()))
    varz.append(zs[VAR])
    if (b + 1) % 5 == 0:
        json.dump(dict(best_real_z=best_real, var_real_z=real[VAR]["z"], null_maxz=maxz, null_varz=varz), open(PART, "w"))
        print(f"  family-wise null {b+1}/{nperm} ({time.time()-t0:.0f}s)", flush=True)
maxz, varz = np.array(maxz), np.array(varz)
p_fw = (1 + int((maxz >= best_real - 1e-12).sum())) / (1 + len(maxz))
p_var = (1 + int((varz >= real[VAR]["z"] - 1e-12).sum())) / (1 + len(varz))
print(f"\nbest real test z = {best_real:+.2f} ({VAR} z = {real[VAR]['z']:+.2f})")
print(f"  per-variant null (this variant only): mean z {varz.mean():+.2f}, p95 {np.quantile(varz,.95):+.2f}, p = {p_var:.3f}")
print(f"  FAMILY-WISE null (best of {len(CFGS)} configurations per permutation): mean {maxz.mean():+.2f}, p95 {np.quantile(maxz,.95):+.2f}, "
      f"p = {p_fw:.3f}")
json.dump(dict(variant=VAR, pockets=detail, union=dict(train=u_tr, test=u_te), real=real, best_real_z=best_real,
               null_maxz=maxz.tolist(), null_varz=varz.tolist(), p_familywise=p_fw, p_variant=p_var, nperm=nperm),
          open(os.path.join(HERE, "results_variant_fwer.json"), "w", encoding="utf-8"), indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("saved results_variant_fwer.json  (hypothesis, NOT PROMOTED)")
