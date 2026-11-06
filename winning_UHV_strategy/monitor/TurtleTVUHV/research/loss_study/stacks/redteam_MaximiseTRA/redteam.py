"""redteam.py - try to REFUTE the "Maximise TRAIN net $" loss-cure stack as overfit (Zee 2026-11-06 loss study).

Stack (changes from the base "97.7%" setting 2026-11-05 05-45-38): SRPips 5, DeepRet 0.8, FreshBreak 1, NoClose on, FriCutNY 15, LoudBrk 0.95,
chosen greedily on TRAIN (Mar 6 - Jun 30) by stacks/net/stack_net.py. Checks:
 (a) re-run base + stack, assert the reported numbers;  (b) TEST loss RATE vs the base's (binomial, Fisher, Wilson, the kept / new / removed
 split of the TEST trades, net beyond a random cut);  (path) the greedy steps re-run, the loss rate of the trades each step removed;
 (c) every numeric threshold (and the hidden knobs SRLook, FreshSwings) one scan.py grid step either way;  (d) month by month;
 (e) leave-one-out and each setting alone.
Writes results.json + report.txt here. Python tick replay = HYPOTHESIS, NOT PROMOTED (only MT5 / live fills promote).
Run (Git Bash): cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/redteam_MaximiseTRA/redteam.py"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402
import numpy as np  # noqa: E402
from scipy import stats as SS  # noqa: E402

OUT = []


def say(s=""):
    print(s, flush=True)
    OUT.append(s)


_RUNS = {}


def run(changes):
    key = json.dumps(sorted(changes.items()))
    if key not in _RUNS:
        _RUNS[key] = C.run(changes)
    return _RUNS[key]


def keyset(r):
    """trade identity = (side, entry time); the outcome of a setup does not depend on earlier trades, so equal keys = the same trade"""
    return {(int(x[0]), round(float(x[1]), 3)): float(x[6]) for x in r}


def main():
    t0 = time.time()
    res = {"engine_hash": C.H0, "stack": C.STACK, "split_utc": C.SPLIT, "base_file": C.BASE_FILE}
    say(f"engine hash {C.H0} (stack_net.py ran on 3a81c704b4)")
    assert C.H0 == "3a81c704b4", "engine changed since the stack was chosen"

    # ---------------- (a) reproduce
    rb, cb = run({})
    rs, cs = run(C.STACK)
    B, S = C.score(rb), C.score(rs)
    blk_b, blk_s = C.result_block(rb), C.result_block(rs)
    say("\n(a) RE-RUN")
    for p in ("train", "test", "all"):
        say(f"  BASE  {p.upper():5s} {C.line(B[p])}")
    for p in ("train", "test", "all"):
        say(f"  STACK {p.upper():5s} {C.line(S[p])}")
    say(f"  base result block {blk_b}   (saved file: {C.RAW['result']})")
    say(f"  stack result block {blk_s}")
    claims = {("train", "n"): 601, ("train", "L"): 13, ("train", "clean"): 72, ("train", "days"): 83, ("test", "n"): 405, ("test", "L"): 7,
              ("test", "clean"): 79, ("test", "days"): 86, ("all", "n"): 1006, ("all", "L"): 20, ("all", "clean"): 151, ("all", "days"): 169}
    ok_a = all(S[p][f] == v for (p, f), v in claims.items())
    ok_a &= abs(S["train"]["net"] - (-1828.82)) < 1 and abs(S["test"]["net"] - (-924.86)) < 1 and abs(S["all"]["net"] - (-2753.68)) < 0.01
    ok_a &= blk_s["pf"] == 0.377 and abs(blk_s["worst_loss"] - (-271.01)) < 0.01 and abs(blk_s["dd"] - 2908.69) < 0.01
    ok_a &= B["all"]["n"] == 7631 and B["all"]["L"] == 172 and abs(B["all"]["net"] - (-25525.97)) < 0.01 and abs(blk_b["dd"] - 25588.96) < 0.01
    ok_a &= (B["train"]["n"], B["train"]["L"], B["test"]["n"], B["test"]["L"]) == (3336, 112, 4295, 60)
    be = 100 * abs(S["all"]["avg_loss"]) / (abs(S["all"]["avg_loss"]) + S["all"]["avg_win"])
    say(f"  every reported number reproduced: {ok_a}; zero-$ trades base {B['all']['zero']}, stack {S['all']['zero']}; "
        f"break-even WR {be:.2f}% (avg win {S['all']['avg_win']:+.2f}, avg loss {S['all']['avg_loss']:+.2f})")
    res["a"] = {"reproduced": bool(ok_a), "base": {p: C.rnd(B[p]) for p in B}, "stack": {p: C.rnd(S[p]) for p in S},
                "base_block": blk_b, "stack_block": blk_s, "break_even_wr": round(be, 3), "stack_skip_counts": cs}

    # ---------------- (b) loss rate vs base
    say("\n(b) LOSS RATE, stack vs base")
    b_out = {}
    for i, p in enumerate(("train", "test")):
        bb, ss = C.split(rb)[i], C.split(rs)[i]
        sb, sx = C.stats(bb), C.stats(ss)
        kb, ks = keyset(bb), keyset(ss)
        kept = [k for k in ks if k in kb]
        new = [k for k in ks if k not in kb]
        removed = [k for k in kb if k not in ks]
        same_pnl = all(abs(ks[k] - kb[k]) < 1e-9 for k in kept)
        Lk, Ln, Lr = sum(ks[k] < 0 for k in kept), sum(ks[k] < 0 for k in new), sum(kb[k] < 0 for k in removed)
        p0 = sb["L"] / sb["n"]
        p_binom = float(SS.binom.cdf(sx["L"], sx["n"], p0))
        crit = max([x for x in range(0, sx["L"] + 30) if SS.binom.cdf(x, sx["n"], p0) < 0.05], default=-1)
        fis = SS.fisher_exact([[sx["L"], sx["n"] - sx["L"]], [Lr, len(removed) - Lr]], alternative="less")   # independent samples
        p_hyp_kept = float(SS.hypergeom.cdf(Lk, sb["n"], sb["L"], len(kept)))
        ex = C.excess(sb, sx)
        wil_s, wil_b = C.wilson(sx["L"], sx["n"]), C.wilson(sb["L"], sb["n"])
        rec = {"base": C.rnd(sb), "stack": C.rnd(sx), "loss_rate_ratio": round(sx["loss_rate"] / sb["loss_rate"], 3),
               "wilson95_stack": [round(x, 3) for x in wil_s], "wilson95_base": [round(x, 3) for x in wil_b],
               "p_binom_le_observed_at_base_rate": round(p_binom, 4), "max_losses_for_p_lt_0.05": crit,
               "expected_losses_at_base_rate": round(sx["n"] * p0, 2),
               "fisher_stack_vs_removed_base_less_p": round(float(fis.pvalue), 4),
               "kept_base_trades": [len(kept), int(Lk)], "new_trades_from_freed_slots": [len(new), int(Ln)],
               "removed_base_trades": [len(removed), int(Lr)], "kept_pnl_identical": bool(same_pnl),
               "p_hypergeom_kept_losses_le": round(p_hyp_kept, 4), "net_beyond_random_cut": round(ex, 1),
               "clean_days": [sx["clean"], sx["days"]], "base_clean_days": [sb["clean"], sb["days"]]}
        b_out[p] = rec
        say(f"  {p.upper():5s} base {sb['L']}/{sb['n']} = {sb['loss_rate']:.3f}% (Wilson95 {wil_b[0]:.2f}-{wil_b[1]:.2f})  stack {sx['L']}/{sx['n']} = "
            f"{sx['loss_rate']:.3f}% (Wilson95 {wil_s[0]:.2f}-{wil_s[1]:.2f})  ratio x{rec['loss_rate_ratio']:.2f}")
        say(f"        expected losses at the base rate {sx['n'] * p0:.2f}, observed {sx['L']}; P(X <= {sx['L']}) binomial {p_binom:.3f}; "
            f"p < 0.05 would need <= {crit} losses; Fisher (stack vs the {len(removed)} removed base trades, one-sided) p = {fis.pvalue:.3f}")
        say(f"        kept base trades {len(kept)} ({Lk} L = {100 * Lk / max(len(kept), 1):.2f}%), new from freed slots {len(new)} ({Ln} L = "
            f"{100 * Ln / max(len(new), 1):.2f}%), removed base trades {len(removed)} ({Lr} L = {100 * Lr / max(len(removed), 1):.2f}%); "
            f"P(kept losses <= {Lk} | random keep) = {p_hyp_kept:.3f}; matched pnl identical: {same_pnl}")
        say(f"        net {sb['net']:,.0f} -> {sx['net']:,.0f}; $/trade {sb['npt']:+.2f} -> {sx['npt']:+.2f}; beyond a random cut of the same size: "
            f"{ex:+,.0f}; loss-free days {sb['clean']}/{sb['days']} -> {sx['clean']}/{sx['days']}")
    res["b"] = b_out

    # ---------------- the greedy path re-run: what each step removed
    say("\nPATH - the greedy steps re-run (loss rate of the trades each step REMOVED vs the stack before it)")
    prev, path = {}, []
    for i, k in enumerate(C.STACK_ORDER, 1):
        cur = dict(prev, **{k: C.STACK[k]})
        rp, _ = run(prev)
        rc, _ = run(cur)
        rec = {"step": i, "add": f"{k}={C.STACK[k]}"}
        for j, p in enumerate(("train", "test")):
            a, b_ = C.split(rp)[j], C.split(rc)[j]
            ka, kb_ = keyset(a), keyset(b_)
            rem = [x for x in ka if x not in kb_]
            add = [x for x in kb_ if x not in ka]
            Lrem, Ladd = sum(ka[x] < 0 for x in rem), sum(kb_[x] < 0 for x in add)
            sa, sb2 = C.stats(a), C.stats(b_)
            rec[p] = {"before": [sa["n"], sa["L"], round(sa["loss_rate"], 3)], "after": [sb2["n"], sb2["L"], round(sb2["loss_rate"], 3)],
                      "removed": [len(rem), int(Lrem), round(100 * Lrem / max(len(rem), 1), 3)], "added": [len(add), int(Ladd)],
                      "p_hypergeom_removed_ge": round(float(SS.hypergeom.sf(Lrem - 1, sa["n"], sa["L"], len(rem))), 4) if rem else None,
                      "net_after": round(sb2["net"], 1), "beyond_random_cut": round(C.excess(sa, sb2), 1)}
        path.append(rec)
        tr_, te_ = rec["train"], rec["test"]
        say(f"  step {i} + {k}={C.STACK[k]:<5s} TRAIN {tr_['before'][0]}/{tr_['before'][1]} ({tr_['before'][2]:.2f}%) -> {tr_['after'][0]}/{tr_['after'][1]} "
            f"({tr_['after'][2]:.2f}%), removed {tr_['removed'][0]} with {tr_['removed'][1]} L ({tr_['removed'][2]:.2f}%), added {tr_['added'][0]}/{tr_['added'][1]} L, "
            f"beyond random {tr_['beyond_random_cut']:+,.0f}")
        say(f"  {'':22s} TEST  {te_['before'][0]}/{te_['before'][1]} ({te_['before'][2]:.2f}%) -> {te_['after'][0]}/{te_['after'][1]} "
            f"({te_['after'][2]:.2f}%), removed {te_['removed'][0]} with {te_['removed'][1]} L ({te_['removed'][2]:.2f}%), added {te_['added'][0]}/{te_['added'][1]} L, "
            f"beyond random {te_['beyond_random_cut']:+,.0f}")
        prev = cur
    res["path"] = path

    # ---------------- (c) one grid step either way
    say("\n(c) PERTURBATION - one scan.py grid step either way (on top of the full stack)")
    grid = {k: v for g in ["loss filters"] + [g for g in C.scan.G if g.startswith("cause:")] for k, v in C.scan.G[g].items()}
    pert = [("InpUhvSRPips", "4", "grid"), ("InpUhvSRPips", "6", "OFF-GRID (5 is the grid top)"),
            ("InpUhvSRLook", "30", "grid (hidden knob, default 60)"), ("InpUhvSRLook", "120", "grid (hidden knob, default 60)"),
            ("InpUhvDeepRet", "0.7", "grid"), ("InpUhvDeepRet", "0.9", "grid"),
            ("InpUhvFreshBreak", "2", "grid (1 -> 0 = off = leave-one-out)"),
            ("InpUhvFreshSwings", "1", "grid (hidden knob, default 2)"), ("InpUhvFreshSwings", "3", "grid (hidden knob, default 2)"),
            ("InpUhvFriCutNY", "14", "grid"), ("InpUhvFriCutNY", "16", "grid"),
            ("InpUhvLoudBrk", "0.9", "grid"), ("InpUhvLoudBrk", "0.975", "OFF-GRID (0.95 is the grid top)")]
    say(f"  grids: SRPips {grid['InpUhvSRPips']}, SRLook {grid['InpUhvSRLook']}, DeepRet {grid['InpUhvDeepRet']}, FreshBreak {grid['InpUhvFreshBreak']}, "
        f"FreshSwings {grid['InpUhvFreshSwings']}, FriCutNY {grid['InpUhvFriCutNY']}, LoudBrk {grid['InpUhvLoudBrk']}")
    gain_wr = S["train"]["wr"] - B["train"]["wr"]
    gain_ex = C.excess(B["train"], S["train"])
    say(f"  the stack's TRAIN gain over base: WR {gain_wr:+.3f} pts, net {S['train']['net'] - B['train']['net']:+,.0f}, beyond a random cut {gain_ex:+,.0f}; "
        f"TEST beyond a random cut {C.excess(B['test'], S['test']):+,.0f}")
    c_out = []
    for k, v, note in pert:
        r, _ = run(dict(C.STACK, **{k: v}))
        sc = C.score(r)
        tr_, te_ = sc["train"], sc["test"]
        rec = {"setting": k, "value": v, "from": C.STACK.get(k, C.BASE.get(k)), "note": note,
               "train": C.rnd(tr_), "test": C.rnd(te_),
               "train_wr_gain_kept_pct": round(100 * (tr_["wr"] - B["train"]["wr"]) / gain_wr, 1),
               "train_beyond_random": round(C.excess(B["train"], tr_), 1), "test_beyond_random": round(C.excess(B["test"], te_), 1),
               "test_loss_rate_below_base": bool(te_["loss_rate"] < B["test"]["loss_rate"])}
        c_out.append(rec)
        say(f"  {k[6:]:>12s} {rec['from']:>5s}->{v:<6s} TRAIN {tr_['n']:4d}/{tr_['L']:3d} L {tr_['loss_rate']:5.2f}% WR {tr_['wr']:6.2f}% net {tr_['net']:>8,.0f} "
            f"(WR gain kept {rec['train_wr_gain_kept_pct']:5.1f}%, beyond rnd {rec['train_beyond_random']:+7,.0f}) | TEST {te_['n']:4d}/{te_['L']:2d} L "
            f"{te_['loss_rate']:5.2f}% net {te_['net']:>7,.0f} ({te_['npt']:+.2f}/tr, beyond rnd {rec['test_beyond_random']:+6,.0f})  [{note}]")
    res["c"] = c_out

    # ---------------- (d) month by month
    say("\n(d) MONTH BY MONTH (UTC calendar month of the entry; Nov = Nov 1-4 only, partial)")
    mb = np.array([C.month(x) for x in rb[:, 1]])
    ms = np.array([C.month(x) for x in rs[:, 1]])
    d_out = []
    for m in sorted(set(mb) | set(ms)):
        b_, s_ = rb[mb == m], rs[ms == m]
        sb, sx = C.stats(b_), C.stats(s_)
        exp = sx["n"] * sb["L"] / sb["n"] if sb["n"] else 0.0
        part = "TRAIN" if m < "2026-07" else "TEST"
        rec = {"month": m, "part": part, "base": [sb["n"], sb["L"], round(sb["loss_rate"], 3), round(sb["net"], 1)],
               "stack": [sx["n"], sx["L"], round(sx["loss_rate"], 3), round(sx["net"], 1)],
               "expected_stack_losses_at_base_rate": round(exp, 2), "losses_saved_vs_random": round(exp - sx["L"], 2),
               "beyond_random_cut": round(C.excess(sb, sx), 1), "clean": [sx["clean"], sx["days"]], "base_clean": [sb["clean"], sb["days"]],
               "partial": m == "2026-11"}
        d_out.append(rec)
        say(f"  {m} {part:5s} base {sb['n']:4d}/{sb['L']:3d} L ({sb['loss_rate']:5.2f}%) net {sb['net']:>8,.0f} | stack {sx['n']:4d}/{sx['L']:2d} L "
            f"({sx['loss_rate']:5.2f}%) net {sx['net']:>7,.0f} | expected L at base rate {exp:5.2f} -> saved {exp - sx['L']:+5.2f} | beyond rnd "
            f"{rec['beyond_random_cut']:+7,.0f} | loss-free days {sx['clean']}/{sx['days']} (base {sb['clean']}/{sb['days']}){'  PARTIAL' if m == '2026-11' else ''}")
    res["d"] = d_out

    # ---------------- (e) leave-one-out + alone
    say("\n(e) LEAVE-ONE-OUT (stack minus one) and ALONE (base plus one)")
    e_out = []
    for k in C.STACK_ORDER:
        loo = {kk: vv for kk, vv in C.STACK.items() if kk != k}
        r1, _ = run(loo)
        r2, _ = run({k: C.STACK[k]})
        s1, s2 = C.score(r1), C.score(r2)
        rec = {"setting": k, "value": C.STACK[k], "loo": {p: C.rnd(s1[p]) for p in ("train", "test")}, "alone": {p: C.rnd(s2[p]) for p in ("train", "test")}}
        for p in ("train", "test"):
            dn, dl = s1[p]["n"] - S[p]["n"], s1[p]["L"] - S[p]["L"]
            rec[f"{p}_contrib"] = {"trades_it_removes": dn, "losses_it_removes": dl,
                                   "loss_rate_of_what_it_removes": round(100 * dl / dn, 3) if dn else None,
                                   "net_it_adds": round(S[p]["net"] - s1[p]["net"], 1),
                                   "alone_beyond_random": round(C.excess(B[p], s2[p]), 1)}
        e_out.append(rec)
        ct, ce = rec["train_contrib"], rec["test_contrib"]
        say(f"  {k[6:]:>11s}={C.STACK[k]:<5s} LOO TRAIN {s1['train']['n']:4d}/{s1['train']['L']:3d} L ({s1['train']['loss_rate']:5.2f}%) net {s1['train']['net']:>8,.0f} "
            f"| TEST {s1['test']['n']:4d}/{s1['test']['L']:2d} L ({s1['test']['loss_rate']:5.2f}%) net {s1['test']['net']:>7,.0f}")
        say(f"  {'':17s} it removes TRAIN {ct['trades_it_removes']:4d} tr / {ct['losses_it_removes']:3d} L ({ct['loss_rate_of_what_it_removes']}%), net {ct['net_it_adds']:+7,.0f} "
            f"| TEST {ce['trades_it_removes']:4d} tr / {ce['losses_it_removes']:2d} L ({ce['loss_rate_of_what_it_removes']}%), net {ce['net_it_adds']:+6,.0f}")
        say(f"  {'':17s} ALONE TRAIN {s2['train']['n']:4d}/{s2['train']['L']:3d} L ({s2['train']['loss_rate']:5.2f}%) beyond rnd {ct['alone_beyond_random']:+7,.0f} "
            f"| TEST {s2['test']['n']:4d}/{s2['test']['L']:2d} L ({s2['test']['loss_rate']:5.2f}%) beyond rnd {ce['alone_beyond_random']:+6,.0f}")
    res["e"] = e_out
    res["minutes"] = round((time.time() - t0) / 60, 2)
    with open(os.path.join(C.HERE, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    say(f"\nwrote results.json in {res['minutes']} min. Python tick replay = hypothesis, NOT PROMOTED.")
    with open(os.path.join(C.HERE, "report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
