"""losses_and_daynull.py - (1) the stack's own losing trades (TRAIN and TEST), with New York time, and whether the base had the same trade;
(2) the loss-free-day null with the day structure kept: on each FX day, draw the stack's trade count at random from the BASE's trades of that
day (exact hypergeometric) -> expected loss-free days and the exact distribution (Poisson-binomial), vs the stack's observed count;
(3) the per-day matched null for the loss COUNT: on each TEST FX day, the stack's count drawn at random from that day's base trades.
Reads runs_cache.npz written by redteam.py (no new simulation). Python tick replay = HYPOTHESIS.
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && py research/loss_study/stacks/redteam_Maximisethe/winrate_stack_redteam/losses_and_daynull.py"""
import datetime as dt
import json
import os
from math import comb
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
NY = ZoneInfo("America/New_York")
SPLIT = 1782864000
STACK_KEY = "|".join(f"{k}={v}" for k, v in sorted({"InpUhvFriCutNY": "10", "InpUhvDeepRet": "0.5", "InpUhvMaxHumps": "3", "InpUhvRunPips": "8",
                                                     "InpUhvSpikeAtr": "2", "InpUhvHtf5": "1", "InpUhvMaxGapPips": "0.3", "InpUhvBrokeHighs": "5"}.items()))


def fxday(ts):
    return (dt.datetime.fromtimestamp(float(ts), NY) + dt.timedelta(hours=7)).date().isoformat()


def poisson_binomial(ps):
    """distribution of the number of successes of independent Bernoulli(p_i)"""
    d = np.zeros(len(ps) + 1); d[0] = 1.0
    for p in ps:
        d[1:] = d[1:] * (1 - p) + d[:-1] * p
        d[0] *= (1 - p)
    return d


def main():
    z = np.load(os.path.join(HERE, "runs_cache.npz"))
    B, S = z["BASE"], z[STACK_KEY]
    out = {}
    bset = {round(float(t), 3): float(p) for t, p in B}
    L = []
    for t, p in S:
        if p < 0:
            ny = dt.datetime.fromtimestamp(float(t), NY)
            L.append({"half": "TRAIN" if t < SPLIT else "TEST", "entry_utc": dt.datetime.utcfromtimestamp(float(t)).strftime("%Y-%m-%d %H:%M:%S"),
                      "entry_ny": ny.strftime("%a %Y-%m-%d %H:%M"), "usd": round(float(p), 2),
                      "same_trade_in_base": round(float(t), 3) in bset})
    out["stack_losses"] = L
    print("the stack's losing trades:")
    for x in L:
        print(f"  {x['half']:5s} {x['entry_ny']}  {x['usd']:+8.2f}  base had it: {x['same_trade_in_base']}")
    for half, sel_b, sel_s in (("TRAIN", B[:, 0] < SPLIT, S[:, 0] < SPLIT), ("TEST", B[:, 0] >= SPLIT, S[:, 0] >= SPLIT)):
        b, s = B[sel_b], S[sel_s]
        nb, lb = {}, {}
        for t, p in b:
            d = fxday(t); nb[d] = nb.get(d, 0) + 1; lb[d] = lb.get(d, 0) + (p < 0)
        ns, ls = {}, {}
        for t, p in s:
            d = fxday(t); ns[d] = ns.get(d, 0) + 1; ls[d] = ls.get(d, 0) + (p < 0)
        ps, exp_loss, var_loss = [], 0.0, 0.0
        for d, c in ns.items():
            n_, l_ = nb.get(d, 0), lb.get(d, 0)
            if n_ == 0:
                ps.append(1.0); continue
            c = min(c, n_)
            ps.append(comb(n_ - l_, c) / comb(n_, c) if c <= n_ - l_ else 0.0)
            exp_loss += c * l_ / n_
            var_loss += c * (l_ / n_) * (1 - l_ / n_) * ((n_ - c) / (n_ - 1) if n_ > 1 else 0.0)
        obs_clean = sum(1 for d in ns if ls.get(d, 0) == 0)
        dist = poisson_binomial(ps)
        p_ge = float(dist[obs_clean:].sum())
        obs_L = int((s[:, 1] < 0).sum())
        # exact per-day matched distribution of the loss count (convolution of per-day hypergeometrics)
        conv = np.zeros(1); conv[0] = 1.0
        for d, c in ns.items():
            n_, l_ = nb.get(d, 0), lb.get(d, 0)
            c = min(c, n_)
            if n_ == 0 or c == 0:
                continue
            pm = np.array([comb(l_, i) * comb(n_ - l_, c - i) / comb(n_, c) for i in range(0, min(l_, c) + 1)])
            conv = np.convolve(conv, pm)
        p_le = float(conv[:obs_L + 1].sum())
        out[half] = {"stack_days": len(ns), "observed_clean_days": obs_clean, "expected_clean_days_perday_thinning": round(float(sum(ps)), 2),
                     "P_clean_ge_observed": p_ge, "observed_losses": obs_L, "expected_losses_perday_thinning": round(exp_loss, 2),
                     "P_losses_le_observed_perday_thinning": p_le}
        print(f"\n{half}: stack traded {len(ns)} FX days; clean {obs_clean}; per-day random thinning expects {sum(ps):.1f} clean days, "
              f"P(>= {obs_clean}) = {p_ge:.3f}")
        print(f"{half}: stack losses {obs_L}; per-day random thinning (same trades per day, picked at random from that day's base trades) "
              f"expects {exp_loss:.2f}; P(<= {obs_L}) = {p_le:.3f}")
    json.dump(out, open(os.path.join(HERE, "losses_and_daynull.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
