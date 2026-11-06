"""redteam.py - try to REFUTE the clean-days stack {MinHumps 4, MinTicks 40, FreshBreak 8, MaxGapPips 0.5} as overfit.

Python tick replay = HYPOTHESIS. NOT PROMOTED. Only MT5 or live fills decide (CLAUDE.md).
Engine and filter files are only READ (uhv_engine.simulate); the random-skip null swaps uhv_filters.skip/active IN MEMORY for this process.

 (a) re-run base + stack, confirm the reported numbers; freed-slot trades (stack trades not in the base) and their losses
 (b) TEST loss RATE vs the base's: exact one-sided binomial, Clopper-Pearson 95% CI, uniform-thinning (hypergeometric) null, kept-vs-removed
 (c) the full {down, chosen, up} neighbourhood of the 5 live thresholds (MinHumps, MinTicks, FreshBreak, FreshSwings, MaxGapPips): 3^5 runs
 (d) month by month on TEST (UTC month of the entry; Nov = 1-4 Nov only, also shown merged into Oct)
 (e) leave-one-out, each setting alone on the base, and the greedy path step by step
 (f) in-engine random-skip null: a filter that skips setups at random (freed slots + one-position blocking included), tuned to the stack's
     trade count, many seeds
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/redteam_Maximisethe/redteam.py"""
import datetime as dt
import itertools
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rt_common as C  # noqa: E402
import numpy as np  # noqa: E402
import uhv_engine as U  # noqa: E402
import uhv_filters as UF  # noqa: E402

T0 = time.time()
B = C.base_inputs()
STACK = dict(C.STACK)
CACHE_F = os.path.join(HERE, "cache_runs.json")
OUT_F = os.path.join(HERE, "redteam_results.json")
LOG_F = os.path.join(HERE, "redteam_run.log")
cache = json.load(open(CACHE_F, encoding="utf-8")) if os.path.exists(CACHE_F) else {}
OUT = {"note": "Python tick replay = HYPOTHESIS. NOT PROMOTED. Only MT5 or live fills decide.", "stack": STACK}
_log = open(LOG_F, "w", encoding="utf-8")
NL = chr(10)


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    _log.write(s + NL)
    _log.flush()


def save_json(obj, f):
    tmp = f + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, f)


RB = C.real(U.simulate(B)[0])                     # the base's real trades (thinning reference for every config)


def run(changes, keep_rows=False):
    key = json.dumps(sorted(changes.items()))
    if key in cache and not keep_rows:
        return cache[key]
    rows = U.simulate(dict(B, **changes))[0]
    s = C.score(rows, RB)
    cache[key] = s
    if len(cache) % 20 == 0:
        save_json(cache, CACHE_F)
    return (s, C.real(rows)) if keep_rows else s


def f3(x):
    e = f" excess {x['excess']:+5.1f}" if "excess" in x else ""
    return f"{x['n']:5d} / {x['L']:3d} / rate {x['rate']:.2f}% / clean {x['clean_pct']:5.1f}% ({x['clean']}/{x['days']}){e} / {x['net']:+,.0f}"


def feasible(s):
    return s["train"]["days"] >= 59 and s["train"]["n"] >= 400


def tkey(r):
    return set(zip(r[:, 0].astype(int).tolist(), np.round(r[:, 1], 3).tolist()))


# =============================================================== (a)
say("Python tick replay = HYPOTHESIS. NOT PROMOTED.")
say("")
sb, rb = run({}, keep_rows=True)
sf, rf = run(STACK, keep_rows=True)
REPORTED = {"train": (405, 9, 74, 83, -1350), "test": (423, 5, 84, 89, -512), "all": (828, 14, 158, 172, -1862)}
REPORTED_BASE = {"train": (3336, 112, 18, 83, -20127), "test": (4295, 60, 46, 92, -5399), "all": (7631, 172, 64, 175, -25526)}
say("(a) RE-RUN")
chk = {}
for p in ("train", "test", "all"):
    for nm, s, rep in (("base", sb, REPORTED_BASE), ("stack", sf, REPORTED)):
        got = (s[p]["n"], s[p]["L"], s[p]["clean"], s[p]["days"], round(s[p]["net"]))
        ok = got[:4] == rep[p][:4] and abs(got[4] - rep[p][4]) <= 1
        chk[f"{nm}_{p}"] = {"got": got, "reported": rep[p], "match": ok}
        say(f"   {nm:5s} {p.upper():5s} {f3(s[p])}   reported n/L/clean/days/net {rep[p]}  {'MATCH' if ok else 'MISMATCH'}")
kb, kf = tkey(rb), tkey(rf)
lb, lf = tkey(rb[rb[:, 6] < 0]), tkey(rf[rf[:, 6] < 0])
new = kf - kb
fs = {"stack_trades": len(kf), "also_in_base": len(kf & kb), "freed_slot_trades": len(new), "freed_slot_losses": len(lf - lb),
      "base_losses_removed": len(lb - lf), "base_losses_kept": len(lb & lf)}
say(f"   freed slots: {fs}")
OUT["a_rerun"] = {"checks": chk, "base": sb, "stack": sf, "freed_slots": fs}

# =============================================================== (b)
say("")
say("(b) TEST LOSS RATE vs THE BASE'S")
bres = {}
for p in ("train", "test", "all"):
    nb_, Lb_ = sb[p]["n"], sb[p]["L"]
    n_, L_ = sf[p]["n"], sf[p]["L"]
    p0 = Lb_ / nb_
    lo, hi = C.clopper_pearson(L_, n_)
    pb = C.binom_cdf(L_, n_, p0)
    ph = C.hypergeom_cdf(L_, nb_, Lb_, n_)
    m = C.masks(rb[:, 1])[p]                       # the base's trades of this part: the ones the stack also takes vs the ones it removes
    rr = rb[m]
    kk = np.array([(int(a), round(float(b_), 3)) in kf for a, b_ in zip(rr[:, 0], rr[:, 1])], bool)
    lossm = rr[:, 6] < 0
    kept = (int(kk.sum()), int((kk & lossm).sum()))
    rem = (int((~kk).sum()), int((~kk & lossm).sum()))
    bres[p] = {"base_rate_pct": round(100 * p0, 4), "stack_rate_pct": round(100 * L_ / n_, 4), "stack_n": n_, "stack_L": L_,
               "expected_L_at_base_rate": round(n_ * p0, 2), "rate_ratio": round((L_ / n_) / p0, 3),
               "clopper_pearson_95_pct": [round(100 * lo, 3), round(100 * hi, 3)], "base_rate_inside_ci": bool(lo <= p0 <= hi),
               "binom_p_le_one_sided": round(pb, 4), "hypergeom_uniform_thinning_p_le": round(ph, 4),
               "kept_base_trades": {"n": kept[0], "L": kept[1], "rate_pct": round(100 * kept[1] / max(kept[0], 1), 3)},
               "removed_base_trades": {"n": rem[0], "L": rem[1], "rate_pct": round(100 * rem[1] / max(rem[0], 1), 3)}}
    say(f"   {p.upper():5s} base {Lb_}/{nb_} = {100*p0:.3f}%   stack {L_}/{n_} = {100*L_/n_:.3f}%  (expect {n_*p0:.1f} losses at the base rate, ratio {bres[p]['rate_ratio']:.2f})"
        f"  CP95 [{100*lo:.2f}%, {100*hi:.2f}%]  base inside: {lo <= p0 <= hi}  P(X<={L_}) binom {pb:.3f} / thinning {ph:.3f}")
    say(f"          the base's own trades: KEPT by the stack {kept[1]}/{kept[0]} = {100*kept[1]/max(kept[0],1):.2f}%   REMOVED {rem[1]}/{rem[0]} = {100*rem[1]/max(rem[0],1):.2f}%")
OUT["b_loss_rate"] = bres

rng = np.random.default_rng(20261106)               # uniform-thinning loss-free nulls (draws) for the stack
nul = {}
for p in ("train", "test"):
    mb = C.masks(rb[:, 1])[p]
    mf = C.masks(rf[:, 1])[p]
    bd, bl = C.fxday(rb[mb, 1]), rb[mb, 6] < 0
    n = int(mf.sum())
    obs = sf[p]["clean_pct"]
    sh = []
    for _ in range(5000):
        idx = rng.choice(len(bd), size=n, replace=False)
        d = np.unique(bd[idx])
        ld = np.unique(bd[idx][bl[idx]])
        sh.append(100.0 * (len(d) - len(ld)) / len(d))
    sh = np.asarray(sh)
    nul[p] = {"observed": obs, "uniform_mean": round(float(sh.mean()), 2), "uniform_95": [round(float(np.percentile(sh, 2.5)), 2), round(float(np.percentile(sh, 97.5)), 2)],
              "uniform_p_ge": round(float((sh >= obs - 1e-9).mean()), 4), "perday_exact_expect": sf[p]["thin_exp"], "excess_over_perday": sf[p]["excess"],
              "base_clean_pct": sb[p]["clean_pct"]}
    say(f"   {p.upper():5s} loss-free days: base {sb[p]['clean_pct']:.1f}% -> stack {obs:.1f}%   random thinning to {n} trades gives {sh.mean():.1f}% "
        f"[{np.percentile(sh, 2.5):.1f}, {np.percentile(sh, 97.5):.1f}] p={nul[p]['uniform_p_ge']:.3f}; per-day exact expectation {sf[p]['thin_exp']:.1f}% (excess {sf[p]['excess']:+.1f} pt)")
OUT["b_loss_free_nulls"] = nul
save_json(OUT, OUT_F)

# =============================================================== (e) leave-one-out, alone, greedy path
say("")
say("(e) LEAVE-ONE-OUT / ALONE / GREEDY PATH   (n / losses / loss rate / loss-free days / excess over per-day thinning / net)")
E = {"loo": {}, "alone": {}, "path": []}
for k in STACK:
    s = run({a: b_ for a, b_ in STACK.items() if a != k})
    E["loo"][k] = s
    say(f"   without {k:18s} TRAIN {f3(s['train'])}  |  TEST {f3(s['test'])}  feasible={feasible(s)}")
for k in STACK:
    s = run({k: STACK[k]})
    E["alone"][k] = s
    say(f"   alone   {k:18s} TRAIN {f3(s['train'])}  |  TEST {f3(s['test'])}  feasible={feasible(s)}")
acc = {}
for k in [None] + list(STACK):
    if k:
        acc[k] = STACK[k]
    s = run(dict(acc))
    E["path"].append({"added": k, "stack": dict(acc), "score": s})
    say(f"   path +{str(k):18s} TRAIN {f3(s['train'])}  |  TEST {f3(s['test'])}")
OUT["e_loo"] = E
save_json(OUT, OUT_F)

# =============================================================== (d) months on TEST
say("")
say("(d) MONTH BY MONTH ON TEST (UTC month of the entry)")


def month_of(t):
    return np.array([dt.datetime.fromtimestamp(float(x), dt.timezone.utc).strftime("%Y-%m") for x in t])


Dm = {}
mb_all, mf_all = month_of(rb[:, 1]), month_of(rf[:, 1])
for label, months in (("2026-07", ["2026-07"]), ("2026-08", ["2026-08"]), ("2026-09", ["2026-09"]), ("2026-10", ["2026-10"]),
                      ("2026-11 (1-4 Nov only)", ["2026-11"]), ("2026-10+11", ["2026-10", "2026-11"]), ("TRAIN 2026-03", ["2026-03"]),
                      ("TRAIN 2026-04", ["2026-04"]), ("TRAIN 2026-05", ["2026-05"]), ("TRAIN 2026-06", ["2026-06"])):
    mb = np.isin(mb_all, months)
    mf = np.isin(mf_all, months)
    b = C.part_stats(rb, mb, rb, mb)
    f = C.part_stats(rf, mf, rb, mb)
    exp_l = f["n"] * (b["L"] / b["n"]) if b["n"] else 0.0
    Dm[label] = {"base": b, "stack": f, "expected_stack_L_at_base_month_rate": round(exp_l, 2),
                 "binom_p_le": round(C.binom_cdf(f["L"], f["n"], b["L"] / b["n"]), 4) if b["n"] and f["n"] else None}
    say(f"   {label:24s} base {b['L']:3d}/{b['n']:4d} = {b['rate']:.2f}%  clean {b['clean_pct']:5.1f}% ({b['clean']}/{b['days']})   ||   stack {f['L']}/{f['n']} = {f['rate']:.2f}%"
        f" (expect {exp_l:.1f} at base rate)  clean {f['clean_pct']:5.1f}% ({f['clean']}/{f['days']}) thin-exp {f.get('thin_exp', 0):.1f}% excess {f.get('excess', 0):+.1f}")
OUT["d_months"] = Dm
lt = rf[(rf[:, 6] < 0) & (rf[:, 1] >= C.SPLIT)]       # the stack's TEST losses, one by one
OUT["d_test_losses"] = [{"t_utc": dt.datetime.fromtimestamp(float(x[1]), dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "side": int(x[0]),
                         "usd": round(float(x[6]), 2), "fx_day": C.fxday_label(C.fxday([x[1]])[0]), "in_base": (int(x[0]), round(float(x[1]), 3)) in kb} for x in lt]
for x in OUT["d_test_losses"]:
    say(f"      TEST loss {x}")
save_json(OUT, OUT_F)

# =============================================================== (c) neighbourhood
say("")
say("(c) NEIGHBOURHOOD {down, chosen, up}^5  (* = off the scan.py grid)")
AX = {"InpUhvMinHumps": ["3", "4", "5*"], "InpUhvMinTicks": ["30", "40", "50*"], "InpUhvFreshBreak": ["5", "8", "10*"],
      "InpUhvFreshSwings": ["1", "2", "3"], "InpUhvMaxGapPips": ["0.3", "0.5", "0.6"]}
CHOSEN = {"InpUhvMinHumps": "4", "InpUhvMinTicks": "40", "InpUhvFreshBreak": "8", "InpUhvFreshSwings": "2", "InpUhvMaxGapPips": "0.5"}
grid = []
t1 = time.time()
for combo in itertools.product(*AX.values()):
    ch = {k: v.rstrip("*") for k, v in zip(AX, combo)}
    ch_run = {k: v for k, v in ch.items() if not (k == "InpUhvFreshSwings" and v == "2")}   # FreshSwings 2 = its default (the stack's own run)
    s = run(ch_run)
    moved = [k for k in AX if ch[k] != CHOSEN[k]]
    grid.append({"values": ch, "off_grid": [k for k, v in zip(AX, combo) if v.endswith("*")], "n_moved": len(moved), "moved": moved,
                 "feasible": feasible(s), "score": s})
save_json(cache, CACHE_F)
say(f"   {len(grid)} runs in {time.time() - t1:.0f}s")
p0_test = sb["test"]["L"] / sb["test"]["n"]
p0_train = sb["train"]["L"] / sb["train"]["n"]


def summ(sel, label):
    if not sel:
        return {}
    te_rate = np.array([g["score"]["test"]["rate"] for g in sel])
    tr_rate = np.array([g["score"]["train"]["rate"] for g in sel])
    te_exc = np.array([g["score"]["test"]["excess"] for g in sel])
    tr_exc = np.array([g["score"]["train"]["excess"] for g in sel])
    te_clean = np.array([g["score"]["test"]["clean_pct"] for g in sel])
    te_L = np.array([g["score"]["test"]["L"] for g in sel])
    te_n = np.array([g["score"]["test"]["n"] for g in sel])
    pooled = 100.0 * te_L.sum() / te_n.sum()
    r = {"runs": len(sel), "feasible": int(sum(g["feasible"] for g in sel)),
         "test_rate_median": round(float(np.median(te_rate)), 3), "test_rate_range": [round(float(te_rate.min()), 3), round(float(te_rate.max()), 3)],
         "test_rate_below_base_share": round(float((te_rate < 100 * p0_test).mean()), 3), "test_pooled_rate_pct": round(pooled, 3),
         "train_rate_median": round(float(np.median(tr_rate)), 3), "train_rate_below_base_share": round(float((tr_rate < 100 * p0_train).mean()), 3),
         "train_excess_median": round(float(np.median(tr_exc)), 2), "test_excess_median": round(float(np.median(te_exc)), 2),
         "test_excess_range": [round(float(te_exc.min()), 2), round(float(te_exc.max()), 2)], "test_clean_median": round(float(np.median(te_clean)), 2)}
    say(f"   {label:30s} runs {r['runs']:3d} feasible {r['feasible']:3d} | TEST rate median {r['test_rate_median']:.2f}% [{r['test_rate_range'][0]:.2f}, {r['test_rate_range'][1]:.2f}] "
        f"below base {100*r['test_rate_below_base_share']:.0f}% (pooled {pooled:.2f}% vs base {100*p0_test:.2f}%) | TRAIN rate median {r['train_rate_median']:.2f}% (base {100*p0_train:.2f}%)"
        f" | excess median TRAIN {r['train_excess_median']:+.1f} TEST {r['test_excess_median']:+.1f} [{r['test_excess_range'][0]:+.1f}, {r['test_excess_range'][1]:+.1f}]")
    return r


CS = {"all_243": summ(grid, "all 243"), "on_grid_only": summ([g for g in grid if not g["off_grid"]], "on-grid only"),
      "one_step_moves": summ([g for g in grid if g["n_moved"] == 1], "single one-step moves (10)"),
      "feasible_only": summ([g for g in grid if g["feasible"]], "feasible only")}
say("   single-axis one-step moves:")
for g in sorted([g for g in grid if g["n_moved"] <= 1], key=lambda g: (g["moved"], json.dumps(g["values"]))):
    s = g["score"]
    tag = (g["moved"][0] + "=" + g["values"][g["moved"][0]] + ("*" if g["off_grid"] else "")) if g["moved"] else "CHOSEN"
    say(f"     {tag:24s} TRAIN {f3(s['train'])} feas={g['feasible']!s:5s} | TEST {f3(s['test'])}")
fe = [g for g in grid if g["feasible"]]


def rank_of(lst):
    for i, g in enumerate(lst):
        if g["n_moved"] == 0:
            return i + 1
    return None


rank_tr = rank_of(sorted(fe, key=lambda g: (g["score"]["train"]["clean_pct"], g["score"]["train"]["wr"], g["score"]["train"]["n"]), reverse=True))
rank_te = rank_of(sorted(fe, key=lambda g: (g["score"]["test"]["clean_pct"], g["score"]["test"]["wr"]), reverse=True))
rank_te_rate = rank_of(sorted(fe, key=lambda g: g["score"]["test"]["rate"]))
rank_te_exc = rank_of(sorted(fe, key=lambda g: g["score"]["test"]["excess"], reverse=True))
tr_e = np.array([g["score"]["train"]["excess"] for g in grid])
te_e = np.array([g["score"]["test"]["excess"] for g in grid])
tr_r = np.array([g["score"]["train"]["rate"] for g in grid])
te_r = np.array([g["score"]["test"]["rate"] for g in grid])
te_n = np.array([g["score"]["test"]["n"] for g in grid])
CS["chosen_rank_among_feasible"] = {"feasible": len(fe), "by_train_objective": rank_tr, "by_test_clean_share": rank_te, "by_test_loss_rate": rank_te_rate,
                                    "by_test_excess": rank_te_exc}
CS["corr_train_vs_test_excess"] = round(float(np.corrcoef(tr_e, te_e)[0, 1]), 3)
CS["corr_train_vs_test_rate"] = round(float(np.corrcoef(tr_r, te_r)[0, 1]), 3)
CS["corr_test_clean_vs_test_trades"] = round(float(np.corrcoef([g["score"]["test"]["clean_pct"] for g in grid], te_n)[0, 1]), 3)
say(f"   chosen point among {len(fe)} feasible neighbours: rank {rank_tr} by the TRAIN objective, {rank_te} by TEST loss-free share, {rank_te_rate} by TEST loss rate, {rank_te_exc} by TEST excess")
say(f"   across the 243: corr(TRAIN excess, TEST excess) = {CS['corr_train_vs_test_excess']:+.2f}; corr(TRAIN rate, TEST rate) = {CS['corr_train_vs_test_rate']:+.2f};"
    f" corr(TEST loss-free share, TEST trades) = {CS['corr_test_clean_vs_test_trades']:+.2f}")
OUT["c_neighbourhood"] = {"axes": AX, "summary": CS, "runs": grid}
save_json(OUT, OUT_F)

# =============================================================== (f) in-engine random-skip null
say("")
say("(f) IN-ENGINE RANDOM-SKIP NULL (a filter that skips setups at random; freed slots and one-position blocking included)")
_orig = (UF.active, UF.skip)
M64 = (1 << 64) - 1


def u01(seed, ts):
    z = (int(round(ts * 1000)) * 0x9E3779B97F4A7C15 + seed * 0xBF58476D1CE4E5B9 + 0x94D049BB133111EB) & M64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
    z ^= z >> 31
    return (z & ((1 << 53) - 1)) / float(1 << 53)


def rand_run(q, seed):
    UF.active = lambda fv, inp: True
    UF.skip = lambda fv, inp, D, side, k, *a, ts=None, **kw: ("random" if u01(seed, ts) < q else None)
    try:
        rows = U.simulate(dict(B))[0]
    finally:
        UF.active, UF.skip = _orig
    return C.score(rows, RB)


target = sf["all"]["n"]
lo_q, hi_q = 0.5, 0.995
for _ in range(14):                                  # bisection on seed 1 for the stack's trade count
    q = 0.5 * (lo_q + hi_q)
    n = rand_run(q, 1)["all"]["n"]
    if n > target:
        lo_q = q
    else:
        hi_q = q
q = 0.5 * (lo_q + hi_q)
say(f"   skip probability q = {q:.4f} gives ~{target} trades")
R = []
t1 = time.time()
for seed in range(1, 201):
    R.append(rand_run(q, seed))
say(f"   200 seeds in {time.time() - t1:.0f}s")
F = {"q": round(q, 5), "seeds": len(R)}
for p in ("train", "test", "all"):
    arr = {m: np.array([r[p][m] for r in R], float) for m in ("n", "L", "rate", "clean_pct", "excess", "net")}
    obs = sf[p]
    F[p] = {m: {"mean": round(float(arr[m].mean()), 3), "p2.5": round(float(np.percentile(arr[m], 2.5)), 3), "p97.5": round(float(np.percentile(arr[m], 97.5)), 3)} for m in arr}
    F[p]["stack"] = {m: obs[m] for m in ("n", "L", "rate", "clean_pct", "excess", "net")}
    F[p]["share_random_at_least_as_clean"] = round(float((arr["clean_pct"] >= obs["clean_pct"] - 1e-9).mean()), 4)
    F[p]["share_random_rate_at_most_stack"] = round(float((arr["rate"] <= obs["rate"] + 1e-9).mean()), 4)
    say(f"   {p.upper():5s} random: trades {arr['n'].mean():.0f} [{np.percentile(arr['n'],2.5):.0f},{np.percentile(arr['n'],97.5):.0f}]  loss rate {arr['rate'].mean():.2f}% "
        f"[{np.percentile(arr['rate'],2.5):.2f},{np.percentile(arr['rate'],97.5):.2f}]  loss-free {arr['clean_pct'].mean():.1f}% [{np.percentile(arr['clean_pct'],2.5):.1f},{np.percentile(arr['clean_pct'],97.5):.1f}]"
        f"  || stack {obs['n']} / {obs['rate']:.2f}% / {obs['clean_pct']:.1f}%   P(random >= stack clean) = {F[p]['share_random_at_least_as_clean']:.3f}, P(random rate <= stack) = {F[p]['share_random_rate_at_most_stack']:.3f}")
OUT["f_random_skip_null"] = F
OUT["secs"] = round(time.time() - T0, 1)
save_json(OUT, OUT_F)
save_json(cache, CACHE_F)
say("")
say(f"saved {OUT_F}  ({OUT['secs']:.0f}s)")
