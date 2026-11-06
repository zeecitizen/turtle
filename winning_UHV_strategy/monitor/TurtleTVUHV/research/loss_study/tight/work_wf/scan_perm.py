"""scan_perm.py (work_wf) - would a loss-free box as big as Zee's appear by CHANCE? (a scan statistic; counting only, no P&L simulated)
Family of boxes = what a researcher could have drawn: humps [hmin, hmax] x ER16 [emin, emax) on a 0.01 grid. Statistic = the most trades in
any box with 0 losses. Null = loss labels shuffled among the trades WITHIN each humps value (keeps humps-specific loss rates, destroys any ER
structure). Stacks from ../trades_*.json (decision-time humps / er16 + outcome)."""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
UP = os.path.dirname(HERE)
rng = np.random.default_rng(20261106)
lines = []


def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); lines.append(s)


def best_zero_box(h, e, loss, hvals, egrid, min_trades=0):
    """the largest 0-loss box: returns (n, hmin, hmax, emin, emax)"""
    best = (0, None, None, None, None)
    eg = np.asarray(egrid)
    for i, a in enumerate(hvals):
        for b in hvals[i:]:
            m = (h >= a) & (h <= b)
            ee, ll = e[m], loss[m]
            o = np.argsort(ee, kind="mergesort"); ee, ll = ee[o], ll[o]
            pos = np.searchsorted(ee, eg - 1e-9, side="left")             # index of the first trade with ER >= grid value
            cl = np.concatenate([[0], np.cumsum(ll)])
            N = pos[None, :] - pos[:, None]                              # trades in [eg_i, eg_j)
            Lc = cl[pos][None, :] - cl[pos][:, None]
            ok = (np.triu(np.ones_like(N, bool), 1)) & (Lc == 0) & (N >= min_trades)
            if ok.any():
                k = np.argmax(np.where(ok, N, -1))
                ii, jj = np.unravel_index(k, N.shape)
                if N[ii, jj] > best[0]:
                    best = (int(N[ii, jj]), a, b, float(eg[ii]), float(eg[jj]))
    return best


def run(stack, hvals, elo, ehi, nperm, zee_box):
    T = json.load(open(os.path.join(UP, f"trades_{stack}.json")))
    T = [t for t in T if hvals[0] <= t["humps"] <= hvals[-1] and elo <= t["er16"] < ehi]
    h = np.array([t["humps"] for t in T]); e = np.array([t["er16"] for t in T]); loss = np.array([0 if t["win"] else 1 for t in T])
    egrid = [round(elo + 0.01 * i, 2) for i in range(int(round((ehi - elo) / 0.01)) + 1)]
    obs = best_zero_box(h, e, loss, hvals, egrid)
    zm = (h >= zee_box[0]) & (h <= zee_box[1]) & (e >= zee_box[2]) & (e < zee_box[3])
    P(f"\n=== {stack}: {len(T)} trades, {loss.sum()} losses in humps {hvals[0]}-{hvals[-1]}, ER [{elo}, {ehi}) ===")
    P(f"observed largest 0-loss box: {obs[0]} trades = humps {obs[1]}-{obs[2]}, ER [{obs[3]:.2f}, {obs[4]:.2f}); Zee's box here: {int(zm.sum())} trades, {int(loss[zm].sum())} losses")
    strata = [np.nonzero(h == v)[0] for v in np.unique(h)]
    null = []
    for _ in range(nperm):
        lp = loss.copy()
        for idx in strata:
            lp[idx] = rng.permutation(loss[idx])
        null.append(best_zero_box(h, e, lp, hvals, egrid)[0])
    null = np.array(null)
    P(f"null ({nperm} shuffles within humps): largest 0-loss box median {np.median(null):.0f}, 90th pct {np.percentile(null, 90):.0f}, 95th {np.percentile(null, 95):.0f}; "
      f"P(null >= observed {obs[0]}) = {np.mean(null >= obs[0]):.3f};  P(null >= Zee's {int(zm.sum())}) = {np.mean(null >= zm.sum()):.3f}")
    return {"stack": stack, "observed": obs, "zee_n": int(zm.sum()), "null_median": float(np.median(null)), "null_p95": float(np.percentile(null, 95)),
            "p_obs": float(np.mean(null >= obs[0])), "p_zee": float(np.mean(null >= zm.sum()))}


out = [run("secure", [2, 3, 4, 5], 0.15, 0.45, 1000, (2, 3, 0.30, 0.35)),
       run("base", [1, 2, 3, 4, 5, 6], 0.15, 0.60, 300, (2, 3, 0.30, 0.35)),
       run("tight", [2, 3], 0.30, 0.45, 2000, (2, 3, 0.30, 0.35))]
json.dump(out, open(os.path.join(HERE, "scan_perm_out.json"), "w"), indent=1)
open(os.path.join(HERE, "scan_perm_out.txt"), "w").write("\n".join(lines))
