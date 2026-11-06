"""null_check.py - is the net-stack better than throwing trades away at random? For TRAIN and TEST: the final stack's trades / losses /
loss-free days against RANDOM subsamples of the base's own trades of the same size (5,000 draws, seed 7) and the exact hypergeometric
chance of so few losses. Also: how many of the stack's trades are base trades (the rest come from slots the filters freed).
Python tick replay = hypothesis, NOT PROMOTED. Run: cd monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/net/null_check.py"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stack_net as S  # noqa: E402

final = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))["final_stack"]
_, base = S.run({})
_, fin = S.run(final)
rng = np.random.default_rng(7)
out = {"final_stack": final}


def hyper_le(N, K, n, k):
    """P(X <= k), X = losses in n trades drawn without replacement from N trades holding K losses"""
    tot = math.comb(N, n)
    return sum(math.comb(K, i) * math.comb(N - K, n - i) for i in range(0, min(k, K, n) + 1)) / tot


for name, cond in (("TRAIN", lambda r: r[:, 1] < S.SPLIT), ("TEST", lambda r: r[:, 1] >= S.SPLIT)):
    b, f = base[cond(base)], fin[cond(fin)]
    sb, sf = S.stats(b), S.stats(f)
    n = len(f)
    lossb = b[:, 6] < 0
    dayb = S.fxday(b[:, 1])
    Ls, cps = np.empty(5000), np.empty(5000)
    for i in range(5000):
        idx = rng.choice(len(b), n, replace=False)
        lz, dd = lossb[idx], dayb[idx]
        Ls[i] = lz.sum()
        days = np.unique(dd)
        cps[i] = 100.0 * (len(days) - len(np.unique(dd[lz]))) / len(days)
    keys = {(int(x[0]), round(float(x[1]))) for x in b}
    inbase = sum(1 for x in f if (int(x[0]), round(float(x[1]))) in keys)
    rec = {"base": {k: sf_ for k, sf_ in S.rnd(sb).items() if k in ("n", "L", "wr", "clean_pct", "net", "npt")},
           "stack": {k: sf_ for k, sf_ in S.rnd(sf).items() if k in ("n", "L", "wr", "clean_pct", "net", "npt")},
           "random_cut_expected_losses": round(float(Ls.mean()), 2), "p_losses_le_observed_hypergeom": round(hyper_le(len(b), int(lossb.sum()), n, sf["L"]), 4),
           "random_cut_expected_clean_pct": round(float(cps.mean()), 1), "random_cut_clean_pct_p5_p95": [round(float(np.percentile(cps, 5)), 1), round(float(np.percentile(cps, 95)), 1)],
           "p_clean_ge_observed": round(float((cps >= sf["clean_pct"] - 1e-9).mean()), 4),
           "stack_trades_that_are_base_trades": f"{inbase}/{n}"}
    out[name] = rec
    print(f"{name}: stack {sf['n']} trades, {sf['L']} losses, WR {sf['wr']:.2f}%, loss-free days {sf['clean_pct']:.1f}%   |   a random cut of the base to "
          f"{n} trades: {Ls.mean():.1f} losses expected (P(<= {sf['L']}) = {rec['p_losses_le_observed_hypergeom']:.3f}), loss-free days "
          f"{cps.mean():.1f}% expected (5-95%: {rec['random_cut_clean_pct_p5_p95']}, P(>= observed) = {rec['p_clean_ge_observed']:.3f}); "
          f"{inbase}/{n} stack trades are base trades", flush=True)
json.dump(out, open(os.path.join(HERE, "null_check.json"), "w", encoding="utf-8"), indent=1)
print("NOT PROMOTED - Python tick replay; MT5 or live fills decide.")
