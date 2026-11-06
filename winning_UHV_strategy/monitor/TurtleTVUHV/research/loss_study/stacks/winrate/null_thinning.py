"""null_thinning.py - honesty check for the win-rate stack (results.json): is it better than simply trading LESS?

1. Random thinning: keep the same number of trades as the final stack, drawn AT RANDOM from the base's trades of that half (5,000 draws), and
   score win rate and loss-free days (fixed denominator = the base's trading days). Fewer trades per day mechanically means more loss-free
   days, so the stack only shows skill where it beats this null - and only TEST counts (TRAIN chose the stack).
2. Per step, the trades the step itself removed (net, vs the previous step): their loss rate / the previous loss rate (marginal lift) and the
   hypergeometric chance of removing that many losers at random. Approximate: freed slots let a few new trades in.
Python tick replay = hypothesis. Run: cd monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/winrate/null_thinning.py"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402

import stack_winrate as W  # noqa: E402

R = json.load(open(W.RESULTS, encoding="utf-8"))


def hyper_ge(x, N, K, n):
    """P(X >= x): losers among n trades removed at random from N trades holding K losers"""
    den = math.comb(N, n)
    return min(1.0, sum(math.comb(K, i) * math.comb(N - K, n - i) / den for i in range(x, min(K, n) + 1)))


def main():
    rng = np.random.default_rng(20261106)
    base_tr, _, _ = W.U.simulate(dict(W.BASE))
    rb = base_tr[base_tr[:, 10] == 0]
    out = {"null": {}, "marginal": []}
    for part, m in (("train", rb[:, 1] < W.SPLIT), ("test", rb[:, 1] >= W.SPLIT)):
        r = rb[m]
        days = np.array([W.fxday(ts) for ts in r[:, 1]])
        loss = r[:, 6] < 0
        den = R["base"][part]["den"]
        F = R["final"][part]
        n_keep = F["n"]
        wr, lfd = [], []
        u, inv = np.unique(days, return_inverse=True)
        for _ in range(5000):
            pick = rng.choice(len(r), size=n_keep, replace=False)
            L = int(loss[pick].sum())
            traded = np.zeros(len(u), bool); traded[inv[pick]] = True
            lost = np.zeros(len(u), bool); lost[inv[pick][loss[pick]]] = True
            wr.append(100.0 * (n_keep - L) / n_keep)
            lfd.append(100.0 * int((traded & ~lost).sum()) / den)
        wr, lfd = np.array(wr), np.array(lfd)
        res = {"n_keep": n_keep, "stack_wr": F["wr"], "stack_lfd_pct": F["lfd_pct"], "null_wr_mean": float(wr.mean()),
               "null_wr_p5_p95": [float(np.percentile(wr, 5)), float(np.percentile(wr, 95))], "p_null_wr_ge_stack": float((wr >= F["wr"] - 1e-9).mean()),
               "null_lfd_mean": float(lfd.mean()), "null_lfd_p5_p95": [float(np.percentile(lfd, 5)), float(np.percentile(lfd, 95))],
               "p_null_lfd_ge_stack": float((lfd >= F["lfd_pct"] - 1e-9).mean())}
        out["null"][part] = res
        print(f"{part.upper():5s} keep {n_keep} of {len(r)} at random: WR {res['null_wr_mean']:.2f}% (5-95%: {res['null_wr_p5_p95'][0]:.2f}-"
              f"{res['null_wr_p5_p95'][1]:.2f}) vs stack {F['wr']:.2f}% -> P(random >= stack) {res['p_null_wr_ge_stack']:.3f} | loss-free days "
              f"{res['null_lfd_mean']:.1f}% (5-95%: {res['null_lfd_p5_p95'][0]:.1f}-{res['null_lfd_p5_p95'][1]:.1f}) vs stack {F['lfd_pct']:.1f}% -> "
              f"P(random >= stack) {res['p_null_lfd_ge_stack']:.3f}", flush=True)
    print("\nper step, the trades that step removed (net vs the step before):")
    prev = R["base"]
    for s in R["steps"]:
        row = {"step": s["step"], "move": f"{s['setting']}={s['value']}"}
        txt = []
        for part in ("train", "test"):
            a, b = prev[part], s[part]
            dn, dL = a["n"] - b["n"], a["L"] - b["L"]
            if dn > 0 and dL >= 0:
                lift = (dL / dn) / (a["L"] / a["n"]) if a["L"] else None
                p = hyper_ge(dL, a["n"], a["L"], dn)
            else:
                lift, p = None, None
            row[part] = {"removed": dn, "losers_removed": dL, "marginal_lift": lift, "hyper_p": p}
            txt.append(f"{part.upper()} removed {dn:5d} trades / {dL:3d} losers, lift {('%.2f' % lift) if lift is not None else '  - '}, "
                       f"p {('%.3g' % p) if p is not None else '-'}")
        out["marginal"].append(row)
        print(f"  {s['step']} {row['move']:24s} " + " | ".join(txt), flush=True)
        prev = {"train": s["train"], "test": s["test"]}
    with open(os.path.join(HERE, "null_thinning.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
