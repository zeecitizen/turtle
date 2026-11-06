"""posthoc.py - POST-HOC variant, run AFTER the frozen primary had failed on test and after replicate.py had shown that SINGLE conditions
carry over (train-vs-test Spearman +0.22, outside the null band) while 3-condition pockets do not. Same beam.py code and constraints, but
depth = 1 (each pocket = ONE condition), for K = 1.5 / 2 / 3, all reported (no picking). Pockets are still chosen on TRAIN only; the fork
(choosing to try depth 1 after looking at test) is disclosed, so treat these test numbers as optimistic. Nulls = the same within-feed
circular shift. Run: cd .../pockets && py method_b_beam/posthoc.py [--nperm 200]"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "beam.py"), encoding="utf-8").read()
head = src.split("# ----------------------------------------------------------------------------------------------------------------------------- real run")[0]
nperm = int(sys.argv[sys.argv.index("--nperm") + 1]) if "--nperm" in sys.argv else 200
sys.argv = [os.path.join(HERE, "beam.py")]
g = {"__file__": os.path.join(HERE, "beam.py"), "__name__": "beam_lib"}
exec(compile(head, "beam_lib", "exec"), g)
greedy, half_stats, summarize_run, perm_within, ctext = (g[k] for k in ("greedy", "half_stats", "summarize_run", "perm_within", "ctext"))
conds, TR, TE, y_tr, BASE_CFG, Y = (g[k] for k in ("conds", "TR", "TE", "y_tr", "BASE_CFG", "Y"))
DAYC = g["DAYC"]
rng = np.random.default_rng(424242)
out = {}
for K in (1.5, 2.0, 3.0):
    cfg = dict(BASE_CFG, depth=1, k=K)
    pk, nc = greedy(y_tr, cfg)
    rules = [p["rule"] for p in pk]
    st_tr, u_tr = half_stats(rules, TR)
    st_te, u_te = half_stats(rules, TE)
    print(f"\n=== depth 1, K = {K}: {len(pk)} pockets, {nc:,} candidates scored")
    rows = []
    for i, (p, a, b) in enumerate(zip(pk, st_tr, st_te)):
        txt = ctext(conds[p["rule"][0]])
        rows.append(dict(rule=txt, rule_idx=list(p["rule"]), train=a, test=b, search={k: v for k, v in p.items() if k not in ("mask", "rule")}))
        print(f"  P{i+1}: {txt}")
        for nm, s, u in (("train", a, u_tr), ("test ", b, u_te)):
            print(f"      {nm}: {100*s['share']:5.2f}% of trades ({s['n']}), losses {s['L']}/{u['Ltot']} ({100*s['Lshare']:.1f}%), rate "
                  f"{100*s['rate']:.2f}% = {s['rate']/u['base_rate']:.2f}x half base, {s['rate']/Y.mean():.2f}x 2.26%; untouched WR alone "
                  f"{100*s['untouched_wr_alone']:.2f}% | cumulative {100*s['cum_share']:.1f}% of trades, {s['cum_L']} losses, untouched WR "
                  f"{100*s['cum_untouched_wr']:.2f}% [loss-days {s['loss_days']}]")
    for nm, u in (("TRAIN", u_tr), ("TEST ", u_te)):
        print(f"  UNION {nm}: {100*u['share']:.1f}% of trades, {u['L']}/{u['Ltot']} losses ({100*u['Lshare']:.1f}%), pocket rate "
              f"{100*u['rate']:.2f}% ({u['rate']/u['base_rate']:.2f}x), untouched WR {100*u['untouched_wr']:.2f}% (base {100*u['base_wr']:.2f}%)")
    n, L, k = u_te["N"], u_te["Ltot"], u_te["n"]
    print(f"  random subset of test with the same coverage would hold {L*k/n:.1f} losses")
    real = summarize_run(pk, y_tr)
    res = []
    for _ in range(nperm):
        yp = perm_within(y_tr, rng, "shift")
        pk2, _ = greedy(yp, cfg)
        res.append(summarize_run(pk2, yp))
    nr = {}
    for s in ("S", "tr_L", "tr_unt_wr", "te_L", "te_lift", "te_unt_wr"):
        v = np.array([r[s] for r in res])
        nr[s] = dict(real=real[s], null_mean=float(v.mean()), null_p95=float(np.quantile(v, 0.95)),
                     p=(1 + int((v >= real[s] - 1e-12).sum())) / (1 + len(v)))
        print(f"   null-shift {s:9s} real {real[s]:.4f} | null mean {nr[s]['null_mean']:.4f} p95 {nr[s]['null_p95']:.4f} | p = {nr[s]['p']:.3f}")
    out[f"depth1_K{K}"] = dict(cfg=cfg, ncand=nc, pockets=rows, union=dict(train=u_tr, test=u_te), null_shift=nr, n_null=nperm)
with open(os.path.join(HERE, "results_posthoc_depth1.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("\nsaved results_posthoc_depth1.json  (post-hoc, test-informed fork disclosed; hypothesis, NOT PROMOTED)")
