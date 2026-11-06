"""random_stacks.py - extra red-team null for the win-rate stack: is the TRAIN-chosen stack better ON TEST than RANDOM stacks of 8 settings
drawn from the same menu (scan.G["loss filters"] + the scan.G["cause: ..."] groups, primary settings only, a random non-zero grid value each,
tuning knobs left at their defaults) that thin TEST to a similar trade count?

Also: across the random stacks, does a better TRAIN loss rate predict a better TEST loss rate (Spearman)? If not, maximising the TRAIN win
rate selects noise.
Python tick replay = HYPOTHESIS. Run (Git Bash):
  cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/redteam_Maximisethe/winrate_stack_redteam/random_stacks.py [N]"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402

import redteam as RT  # noqa: E402

KNOBSET = {"InpUhvSRLook", "InpUhvRangeBars", "InpUhvFreshSwings", "InpUhvBrokeLook", "InpUhvHtf5N", "InpUhvSRAheadLook", "InpUhvFigStep",
           "InpUhvCounterBars", "InpUhvRunBars", "InpUhvNewsMins", "InpUhvSpikeBars"}
GROUPS = ["loss filters"] + [g for g in RT.SC.G if g.startswith("cause: ")]
PRIMARY = [k for g in GROUPS for k in RT.SC.G[g] if k not in KNOBSET]
OUT = os.path.join(HERE, "random_stacks.json")


def values(k):
    spec = RT.SC.SPEC[k]
    if spec == "bool":
        return ["1"]
    return [f"{float(v):g}" for v in spec[1] if float(v) != 0]


def ranks(x):
    o = np.argsort(x, kind="mergesort")
    r = np.empty(len(x)); r[o] = np.arange(len(x))
    # average ties
    xs = np.asarray(x)[o]
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        r[o[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = ranks(np.asarray(a, float)), ranks(np.asarray(b, float))
    return float(np.corrcoef(ra, rb)[0, 1])


def score_direct(stack):
    """simulate without touching redteam.py's on-disk cache (300 random runs would bloat it)"""
    tr, _, _ = RT.U.simulate(dict(RT.BASE, **stack))
    r = tr[tr[:, 10] == 0]
    t, p = r[:, 1], r[:, 6]
    m = t < RT.SPLIT
    return {"train": RT.summ(t[m], p[m], RT.DEN["train"]), "test": RT.summ(t[~m], p[~m], RT.DEN["test"])}


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    rng = np.random.default_rng(1106)
    tr_, _, _ = RT.U.simulate(dict(RT.BASE))
    rb = tr_[tr_[:, 10] == 0]
    assert (len(rb), int((rb[:, 6] < 0).sum()), round(float(rb[:, 6].sum()), 2)) == RT.EXPECT_BASE
    tb = rb[:, 1]
    RT.DEN["train"] = len({RT.fxday(x) for x in tb[tb < RT.SPLIT]})
    RT.DEN["test"] = len({RT.fxday(x) for x in tb[tb >= RT.SPLIT]})
    RT.DEN["all"] = len({RT.fxday(x) for x in tb})
    for x in tb[tb >= RT.SPLIT]:
        RT.DEN_M.setdefault(RT.fxday(x)[:7], set()).add(RT.fxday(x))
    for m in list(RT.DEN_M):
        RT.DEN_M[m] = len(RT.DEN_M[m]) if isinstance(RT.DEN_M[m], set) else RT.DEN_M[m]
    base = RT.score({})
    stk = RT.score(RT.STACK)
    res = json.load(open(OUT, encoding="utf-8"))["draws"] if os.path.exists(OUT) else []
    seen = {json.dumps(d["stack"], sort_keys=True) for d in res}
    t0 = time.time()
    while len(res) < N:
        ks = list(rng.choice(PRIMARY, size=8, replace=False))
        s = {k: str(rng.choice(values(k))) for k in ks}
        sig = json.dumps(s, sort_keys=True)
        if sig in seen:
            continue
        seen.add(sig)
        sc = score_direct(s)
        res.append({"stack": s, "train": sc["train"], "test": sc["test"]})
        if len(res) % 25 == 0:
            print(f"  {len(res)}/{N} draws, {time.time() - t0:.0f}s", flush=True)
            json.dump({"draws": res}, open(OUT, "w", encoding="utf-8"))
    json.dump({"draws": res}, open(OUT, "w", encoding="utf-8"))
    # ---- analysis
    S_te, B_te = stk["test"], base["test"]
    band = [d for d in res if 500 <= d["test"]["n"] <= 1100 and d["train"]["n"] >= 300]
    lr = np.array([100.0 * d["test"]["L"] / d["test"]["n"] for d in band]) if band else np.zeros(0)
    allok = [d for d in res if d["test"]["n"] >= 100 and d["train"]["n"] >= 100]
    out = {"n_draws": len(res), "primary_settings": PRIMARY, "stack_test": S_te, "base_test": B_te,
           "band_rule": "random stacks with 500 <= TEST trades <= 1100 and TRAIN trades >= 300",
           "band_n": len(band)}
    if len(band):
        out.update({"band_test_loss_rate_median": float(np.median(lr)), "band_test_loss_rate_p10_p90": [float(np.percentile(lr, 10)), float(np.percentile(lr, 90))],
                    "band_share_with_test_loss_rate_le_stack": float((lr <= S_te["loss_rate"] + 1e-9).mean()),
                    "band_test_rate_ratio_vs_base_median": float(np.median(lr) / B_te["loss_rate"])})
    # does TRAIN predict TEST? (all draws with >= 100 trades in both halves)
    if len(allok) >= 3:
        a = [100.0 * d["train"]["L"] / d["train"]["n"] for d in allok]
        b = [100.0 * d["test"]["L"] / d["test"]["n"] for d in allok]
        out["spearman_train_vs_test_loss_rate_all"] = spearman(a, b)
        out["n_allok"] = len(allok)
        # partial out thinning: residual of each rate vs log(trades kept) in its half
        la = np.log([d["train"]["n"] for d in allok]); lb = np.log([d["test"]["n"] for d in allok])
        ra = np.asarray(a) - np.polyval(np.polyfit(la, a, 1), la)
        rb_ = np.asarray(b) - np.polyval(np.polyfit(lb, b, 1), lb)
        out["spearman_train_vs_test_loss_rate_after_thinning"] = spearman(ra, rb_)
        out["spearman_test_n_vs_test_loss_rate"] = spearman(list(lb), b)
        # the best-TRAIN random stacks (TRAIN >= 600, the search's own constraint): how do they do on TEST?
        feas = sorted([d for d in res if d["train"]["n"] >= 600], key=lambda d: d["train"]["L"] / d["train"]["n"])
        out["top10_train_feasible"] = [{"stack": d["stack"], "train": [d["train"]["n"], d["train"]["L"], d["train"]["wr"]],
                                        "test": [d["test"]["n"], d["test"]["L"], d["test"]["wr"]]} for d in feas[:10]]
    if band:
        a = [100.0 * d["train"]["L"] / d["train"]["n"] for d in band]
        b = [100.0 * d["test"]["L"] / d["test"]["n"] for d in band]
        out["spearman_train_vs_test_loss_rate_band"] = spearman(a, b)
    json.dump({"draws": res, "summary": out}, open(OUT, "w", encoding="utf-8"), indent=0)
    print(json.dumps({k: v for k, v in out.items() if k not in ("primary_settings", "top10_train_feasible")}, indent=1))
    print("top-10 TRAIN-feasible random stacks (TRAIN n/L/WR | TEST n/L/WR):")
    for d in out.get("top10_train_feasible", []):
        print("  ", d["train"], "|", d["test"], d["stack"])


if __name__ == "__main__":
    main()
