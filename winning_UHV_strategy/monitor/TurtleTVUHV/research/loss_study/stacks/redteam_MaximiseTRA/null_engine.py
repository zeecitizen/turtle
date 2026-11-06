"""null_engine.py - ENGINE-LEVEL random-thinning null for the "Maximise TRAIN net $" stack: is the stack better than skipping setups at
random? Unlike a subsample of the base's trades, this skips SETUPS at random inside the engine, so a skipped setup frees the slot for a
later one exactly as the real filters do (one position at a time). The engine files are not edited: uhv_filters.active / uhv_filters.skip
are replaced IN THIS PROCESS ONLY by a keyed coin flip (splitmix64 of seed and the setup's breakout tick time), one skip probability per
split, calibrated so the mean trade count matches the stack's (601 TRAIN, 405 TEST).
Python tick replay = HYPOTHESIS, NOT PROMOTED.
Run (Git Bash): cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/redteam_MaximiseTRA/null_engine.py"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import numpy as np  # noqa: E402

MASK = (1 << 64) - 1
ST = {"seed": 0, "p": (0.0, 0.0)}


def u01(seed, ts):
    x = (seed * 0x9E3779B97F4A7C15 + int(round(ts * 1000)) + 0x9E3779B97F4A7C15) & MASK
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & MASK
    return (x ^ (x >> 31)) / 2.0 ** 64


def rskip(fv, inp, D, side, k, px, atr_k, extreme, level=None, ku=None, ts=None, uhv_v=None, brk_ticks=None, brk_px=None):
    p = ST["p"][0] if ts < C.SPLIT else ST["p"][1]
    return "random" if u01(ST["seed"], ts) < p else None


def counts(p, seeds):
    ST["p"] = p
    a, b = [], []
    for s in seeds:
        ST["seed"] = s
        r, _ = C.run({})
        tr, te = C.split(r)
        a.append(len(tr)); b.append(len(te))
    return float(np.mean(a)), float(np.mean(b))


def main():
    t0 = time.time()
    rs, _ = C.run(C.STACK)                                  # the real stack (real filters) BEFORE patching
    S = C.score(rs)
    rb, _ = C.run({})
    B = C.score(rb)
    real_active, real_skip = C.UF.active, C.UF.skip
    C.UF.active = lambda fv, inp: True
    C.UF.skip = rskip
    try:
        ST["p"] = (0.0, 0.0); ST["seed"] = 1
        r0, _ = C.run({})
        assert len(r0) == 7631, "patched engine with p = 0 must reproduce the base"
        target = (S["train"]["n"], S["test"]["n"])
        lo, hi = [0.5, 0.5], [0.99, 0.995]
        cal_seeds = [101, 102, 103]
        for it in range(9):                                 # bisection, both splits at once (they hardly interact)
            mid = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
            na, nb = counts(mid, cal_seeds)
            for j, (n, tg) in enumerate(((na, target[0]), (nb, target[1]))):
                if n > tg:
                    lo[j] = mid[j]
                else:
                    hi[j] = mid[j]
            print(f"  calibrate {it}: p = ({mid[0]:.4f}, {mid[1]:.4f}) -> mean trades ({na:.0f}, {nb:.0f}) target {target}", flush=True)
        p = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
        ST["p"] = p
        draws = {"train": [], "test": []}
        NSEED = 200
        for s in range(NSEED):
            ST["seed"] = 1000 + s
            r, _ = C.run({})
            sc = C.score(r)
            for part in ("train", "test"):
                x = sc[part]
                draws[part].append([x["n"], x["L"], x["loss_rate"], x["net"], x["npt"], x["clean"], x["days"], x["clean_pct"]])
    finally:
        C.UF.active, C.UF.skip = real_active, real_skip
    out = {"skip_p": {"train": round(p[0], 5), "test": round(p[1], 5)}, "seeds": NSEED, "stack": {k: C.rnd(S[k]) for k in ("train", "test")},
           "base": {k: C.rnd(B[k]) for k in ("train", "test")}}
    for part in ("train", "test"):
        A = np.array(draws[part])
        n, L, lr, net, npt, cl, dy, cp = A.T
        s = S[part]
        near = np.abs(n - s["n"]) <= 0.05 * s["n"]
        rec = {"null_trades_mean": round(float(n.mean()), 1), "null_trades_p5_p95": [float(np.percentile(n, 5)), float(np.percentile(n, 95))],
               "null_losses_mean": round(float(L.mean()), 2), "null_loss_rate_mean": round(float(lr.mean()), 3),
               "null_loss_rate_p5_p95": [round(float(np.percentile(lr, 5)), 3), round(float(np.percentile(lr, 95)), 3)],
               "p_null_loss_rate_le_stack": round(float((lr <= s["loss_rate"] + 1e-9).mean()), 3),
               "null_npt_mean": round(float(npt.mean()), 3), "p_null_npt_ge_stack": round(float((npt >= s["npt"] - 1e-9).mean()), 3),
               "null_net_mean": round(float(net.mean()), 1), "p_null_net_ge_stack": round(float((net >= s["net"] - 1e-9).mean()), 3),
               "null_clean_pct_mean": round(float(cp.mean()), 2), "null_clean_pct_p5_p95": [round(float(np.percentile(cp, 5)), 2), round(float(np.percentile(cp, 95)), 2)],
               "p_null_clean_pct_ge_stack": round(float((cp >= s["clean_pct"] - 1e-9).mean()), 3),
               "near_count_draws": int(near.sum()),
               "near_p_null_clean_pct_ge_stack": round(float((cp[near] >= s["clean_pct"] - 1e-9).mean()), 3) if near.any() else None,
               "near_p_null_loss_rate_le_stack": round(float((lr[near] <= s["loss_rate"] + 1e-9).mean()), 3) if near.any() else None}
        out[part] = rec
        print(f"{part.upper():5s} stack {s['n']} tr {s['L']} L ({s['loss_rate']:.2f}%), {s['npt']:+.2f}/tr, loss-free days {s['clean_pct']:.1f}%  |  random "
              f"setup-skipping (p {p[0 if part == 'train' else 1]:.4f}, {NSEED} seeds): {rec['null_trades_mean']:.0f} tr, {rec['null_losses_mean']:.1f} L, loss rate "
              f"{rec['null_loss_rate_mean']:.2f}% (5-95% {rec['null_loss_rate_p5_p95']}), P(random loss rate <= stack) {rec['p_null_loss_rate_le_stack']:.3f}; "
              f"$/tr {rec['null_npt_mean']:+.2f}, P(random $/tr >= stack) {rec['p_null_npt_ge_stack']:.3f}; loss-free days {rec['null_clean_pct_mean']:.1f}% "
              f"(5-95% {rec['null_clean_pct_p5_p95']}), P(random >= stack) {rec['p_null_clean_pct_ge_stack']:.3f} "
              f"[draws within 5% of the stack's count: {rec['near_count_draws']}, P {rec['near_p_null_clean_pct_ge_stack']}]", flush=True)
    out["minutes"] = round((time.time() - t0) / 60, 2)
    with open(os.path.join(C.HERE, "null_engine.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote null_engine.json in {out['minutes']} min. Python tick replay = hypothesis, NOT PROMOTED.")


if __name__ == "__main__":
    main()
