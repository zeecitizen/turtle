"""redteam.py - RED TEAM of the win-rate stack (research/loss_study/stacks/winrate): try to REFUTE it as overfit.

The stack (chosen by greedy forward stacking on TRAIN = entries before 2026-07-01 00:00 UTC, objective "max TRAIN win rate, >= 600 TRAIN
trades", 829 candidate moves scored over 8 steps):
  InpUhvFriCutNY=10  InpUhvDeepRet=0.5  InpUhvMaxHumps=3  InpUhvRunPips=8  InpUhvSpikeAtr=2  InpUhvHtf5=1  InpUhvMaxGapPips=0.3  InpUhvBrokeHighs=5
on the "97.7%" setting (settings/saved/2026-11-05 05-45-38.json).

Checks (all scored with this file's OWN scoring code, not the search's):
  (a) re-run base + stack, confirm the reported numbers (base must give 7631 / 172 / -25,525.97)
  (b) TEST loss RATE vs the base's TEST loss rate: exact hypergeometric (random thinning to the same trade count), binomial, a paired
      FX-day block bootstrap of the loss-rate ratio, and the same tests for steps 2-8 on top of step 1 (the Friday cut) alone
  (c) every numeric threshold one scan.py grid step either way (+ off-grid probes where the chosen value sits at the grid's lowest
      non-zero value, + the 4 implicit tuning knobs left at their defaults)
  (d) TEST month by month, base vs stack
  (e) leave-one-out: the stack minus each setting (+ each setting alone on the base)
A loss = rows[:, 6] < 0 on real rows (rows[:, 10] == 0); entry time rows[:, 1]. Loss-free day = FX day (17:00 NY -> 17:00 NY, labelled by
its closing date) with >= 1 trade and no losing trade; % uses the BASE's trading days in that period as a fixed denominator.

Python tick replay = a HYPOTHESIS. Nothing here promotes anything; only MT5's Strategy Tester or live fills can.
Run (Git Bash): cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/redteam_Maximisethe/winrate_stack_redteam/redteam.py"""
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from zoneinfo import ZoneInfo

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))    # monitor/TurtleTVUHV (this file: stacks/redteam_Maximisethe/winrate_stack_redteam/)
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402

import uhv_engine as U  # noqa: E402
import scan as SC  # noqa: E402

BASE_FILE = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")
SPLIT = 1782864000                     # 2026-07-01 00:00 UTC
NY = ZoneInfo("America/New_York")
EXPECT_BASE = (7631, 172, -25525.97)
STACK = {"InpUhvFriCutNY": "10", "InpUhvDeepRet": "0.5", "InpUhvMaxHumps": "3", "InpUhvRunPips": "8", "InpUhvSpikeAtr": "2",
         "InpUhvHtf5": "1", "InpUhvMaxGapPips": "0.3", "InpUhvBrokeHighs": "5"}
ORDER = list(STACK)                    # the order the greedy search took them (step 1 .. 8)
KNOBS = {"InpUhvRunBars": "InpUhvRunPips", "InpUhvSpikeBars": "InpUhvSpikeAtr", "InpUhvHtf5N": "InpUhvHtf5", "InpUhvBrokeLook": "InpUhvBrokeHighs"}
REPORTED = {"train": (610, 5, -63.08, 77), "test": (764, 7, -384.82, 85), "all": (1374, 12, -447.9, 162)}
ENGINE_FILES = ["uhv_engine.py", "uhv_filters.py", "uhv_diamond.py", "uhv_ticks.py", "sim.py", "scan.py"]
OUT = os.path.join(HERE, "redteam_results.json")
CACHE_F = os.path.join(HERE, "runs_cache.npz")
DEN = {}
DEN_M = {}


def sha1(p):
    with open(p, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def load_base():
    B = dict(json.load(open(BASE_FILE, encoding="utf-8"))["inputs"])
    for k, d in U.UHV_DEFAULTS.items():                         # saved before the loss filters existed: their defaults (all off)
        B.setdefault(k, d[0])
    return B


BASE = load_base()
_HC = {}


def fxday(ts):
    """FX day label: the New York date of (entry + 7 h), i.e. the day that closes at the next 17:00 New York"""
    h = int(ts // 3600)                                         # NY offsets (and DST jumps) are whole hours -> constant within a UTC hour
    if h not in _HC:
        _HC[h] = (dt.datetime.fromtimestamp(h * 3600, NY) + dt.timedelta(hours=7)).date().isoformat()
    return _HC[h]


# ------------------------------------------------------------------ runs (cached on disk: key -> (t_in, pnl) of real trades)
RUNS = {}
if os.path.exists(CACHE_F):
    _z = np.load(CACHE_F, allow_pickle=False)
    for _k in _z.files:
        RUNS[_k] = _z[_k]


def key_of(stack):
    return "|".join(f"{k}={stack[k]}" for k in sorted(stack)) or "BASE"


def run(stack):
    k = key_of(stack)
    if k not in RUNS:
        t0 = time.time()
        tr, _, _ = U.simulate(dict(BASE, **stack))
        r = tr[tr[:, 10] == 0]
        RUNS[k] = np.stack([r[:, 1], r[:, 6]], axis=1) if len(r) else np.zeros((0, 2))
        np.savez(CACHE_F, **RUNS)
        print(f"   sim {k[:110]:110s} {len(r):5d} trades  {time.time() - t0:5.1f}s", flush=True)
    a = RUNS[k]
    return a[:, 0], a[:, 1]


# ------------------------------------------------------------------ scoring
def summ(t, p, den):
    n, L = int(len(p)), int((p < 0).sum())
    days = {}
    for ts, x in zip(t, p):
        d = fxday(ts)
        days[d] = days.get(d, False) or bool(x < 0)
    lfd = sum(1 for v in days.values() if not v)
    return {"n": n, "L": L, "wr": round(100.0 * (n - L) / n, 4) if n else None, "loss_rate": round(100.0 * L / n, 4) if n else None,
            "net": round(float(p.sum()), 2), "days": len(days), "lfd": lfd, "den": den, "lfd_pct": round(100.0 * lfd / den, 2) if den else None}


def score(stack):
    t, p = run(stack)
    tr, te = t < SPLIT, t >= SPLIT
    out = {"train": summ(t[tr], p[tr], DEN["train"]), "test": summ(t[te], p[te], DEN["test"]), "all": summ(t, p, DEN["all"])}
    labels = np.array([fxday(x)[:7] for x in t]) if len(t) else np.array([], dtype=str)
    out["test_months"] = {m: summ(t[te & (labels == m)], p[te & (labels == m)], DEN_M[m]) for m in sorted(DEN_M)}
    return out


def fmt(h):
    if not h["n"]:
        return "    0 trades"
    return (f"{h['n']:5d} / {h['L']:3d} / {h['wr']:6.2f}% (loss rate {h['loss_rate']:.3f}%) / clean days {h['lfd']}/{h['den']} = "
            f"{h['lfd_pct']:.1f}% / {h['net']:+,.0f}")


def hyp_le(x, N, K, n):
    """P(X <= x): losses among n trades drawn at random (no replacement) from N trades holding K losses"""
    n = min(n, N)
    den = math.comb(N, n)
    return sum(math.comb(K, i) * math.comb(N - K, n - i) for i in range(max(0, n - (N - K)), min(x, K, n) + 1)) / den


def binom_le(x, n, q):
    return sum(math.comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(0, x + 1))


def boot_ratio(tb, pb, ts_, ps, B=20000, seed=20261106):
    """paired FX-day block bootstrap of (stack loss rate) / (base loss rate) on the same resampled TEST days"""
    days = sorted({fxday(x) for x in tb} | {fxday(x) for x in ts_})
    ix = {d: i for i, d in enumerate(days)}
    nb = np.zeros(len(days)); Lb = np.zeros(len(days)); ns = np.zeros(len(days)); Ls = np.zeros(len(days))
    for x, y in zip(tb, pb):
        i = ix[fxday(x)]; nb[i] += 1; Lb[i] += y < 0
    for x, y in zip(ts_, ps):
        i = ix[fxday(x)]; ns[i] += 1; Ls[i] += y < 0
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(days), size=(B, len(days)))
    snb, sLb, sns, sLs = nb[pick].sum(1), Lb[pick].sum(1), ns[pick].sum(1), Ls[pick].sum(1)
    ok = (sLb > 0) & (sns > 0)
    ratio = (sLs[ok] / sns[ok]) / (sLb[ok] / snb[ok])
    return {"days": len(days), "point": float((Ls.sum() / ns.sum()) / (Lb.sum() / nb.sum())),
            "p5": float(np.percentile(ratio, 5)), "p50": float(np.percentile(ratio, 50)), "p95": float(np.percentile(ratio, 95)),
            "p2_5": float(np.percentile(ratio, 2.5)), "p97_5": float(np.percentile(ratio, 97.5)), "P_ratio_ge_1": float((ratio >= 1).mean()),
            "P_ratio_ge_0_8": float((ratio >= 0.8).mean())}


def overlap(t_a, t_b):
    """how many entries of run a are also entries (same entry time) of run b"""
    sb = set(np.round(t_b, 3).tolist())
    return int(sum(1 for x in np.round(t_a, 3).tolist() if x in sb))


def grid_neighbours(k, v):
    spec = SC.SPEC[k]
    vals = [float(x) for x in spec[1]]
    i = min(range(len(vals)), key=lambda j: abs(vals[j] - float(v)))
    out = []
    if i > 0:
        out.append(("down", vals[i - 1]))
    if i < len(vals) - 1:
        out.append(("up", vals[i + 1]))
    return out


def main():
    T0 = time.time()
    hashes0 = {f: sha1(os.path.join(ROOT, f)) for f in ENGINE_FILES}
    R = {"script": os.path.abspath(__file__), "started": dt.datetime.now().isoformat(timespec="seconds"), "engine_hashes": hashes0,
         "stack": STACK, "doctrine": "Python tick replay = HYPOTHESIS; nothing promoted. TRAIN chose the stack; TEST is untouched here too."}
    # ---- (a) base must reproduce exactly (re-simulated, never from the cache)
    tr_, _, _ = U.simulate(dict(BASE))
    rb = tr_[tr_[:, 10] == 0]
    got = (int(len(rb)), int((rb[:, 6] < 0).sum()), round(float(rb[:, 6].sum()), 2))
    print("BASE re-simulated:", got, "expected", EXPECT_BASE, flush=True)
    if got != EXPECT_BASE:
        raise SystemExit("STOP: the base does not reproduce - engine or data changed")
    RUNS["BASE"] = np.stack([rb[:, 1], rb[:, 6]], axis=1)
    np.savez(CACHE_F, **RUNS)
    tb, pb = rb[:, 1], rb[:, 6]
    DEN["train"] = len({fxday(x) for x in tb[tb < SPLIT]})
    DEN["test"] = len({fxday(x) for x in tb[tb >= SPLIT]})
    DEN["all"] = len({fxday(x) for x in tb})
    dm = {}
    for x in tb[tb >= SPLIT]:
        dm.setdefault(fxday(x)[:7], set()).add(fxday(x))
    DEN_M.update({m: len(v) for m, v in dm.items()})
    print("fixed denominators:", DEN, "TEST months:", DEN_M, flush=True)
    base = score({})
    stk = score(STACK)
    R["a_reproduce"] = {"base": {p: base[p] for p in ("train", "test", "all")}, "stack": {p: stk[p] for p in ("train", "test", "all")},
                        "reported_n_L_net_lfd": REPORTED,
                        "match": all(stk[p]["n"] == REPORTED[p][0] and stk[p]["L"] == REPORTED[p][1] and abs(stk[p]["net"] - REPORTED[p][2]) < 0.01
                                     and stk[p]["lfd"] == REPORTED[p][3] for p in ("train", "test", "all"))}
    print("\n(a) REPRODUCE", "MATCH" if R["a_reproduce"]["match"] else "MISMATCH", flush=True)
    for p in ("train", "test", "all"):
        print(f"   {p.upper():5s} base  {fmt(base[p])}\n         stack {fmt(stk[p])}   reported n/L/net/lfd {REPORTED[p]}", flush=True)

    # ---- (b) TEST loss rate vs the base's
    t_s, p_s = run(STACK)
    teb, tes = tb >= SPLIT, t_s >= SPLIT
    B_, S_ = base["test"], stk["test"]
    step1 = score({"InpUhvFriCutNY": "10"})
    t1, p1 = run({"InpUhvFriCutNY": "10"})
    te1 = t1 >= SPLIT
    S1 = step1["test"]
    b = {"base_test": B_, "stack_test": S_, "rate_ratio": S_["loss_rate"] / B_["loss_rate"],
         "expected_losses_at_base_rate": S_["n"] * B_["L"] / B_["n"],
         "hyper_P_L_le_stack_random_thinning": hyp_le(S_["L"], B_["n"], B_["L"], S_["n"]),
         "hyper_P_L_le_stack_minus_1": hyp_le(S_["L"] - 1, B_["n"], B_["L"], S_["n"]),
         "binom_P_L_le_stack": binom_le(S_["L"], S_["n"], B_["L"] / B_["n"]),
         "stack_test_trades_also_in_base": overlap(t_s[tes], tb[teb]),
         "day_bootstrap_ratio": boot_ratio(tb[teb], pb[teb], t_s[tes], p_s[tes]),
         "step1_only_test": S1,
         "step1_vs_base": {"rate_ratio": S1["loss_rate"] / B_["loss_rate"], "hyper_P": hyp_le(S1["L"], B_["n"], B_["L"], S1["n"]),
                           "day_bootstrap_ratio": boot_ratio(tb[teb], pb[teb], t1[te1], p1[te1])},
         "steps2to8_vs_step1": {"rate_ratio": S_["loss_rate"] / S1["loss_rate"], "expected_losses_at_step1_rate": S_["n"] * S1["L"] / S1["n"],
                                "hyper_P_L_le_stack": hyp_le(S_["L"], S1["n"], S1["L"], S_["n"]),
                                "stack_test_trades_also_in_step1": overlap(t_s[tes], t1[te1]),
                                "day_bootstrap_ratio": boot_ratio(t1[te1], p1[te1], t_s[tes], p_s[tes])}}
    b["train_rate_ratio_in_sample"] = stk["train"]["loss_rate"] / base["train"]["loss_rate"]
    b["train_hyper_P_in_sample"] = hyp_le(stk["train"]["L"], base["train"]["n"], base["train"]["L"], stk["train"]["n"])
    R["b_test_loss_rate"] = b
    print(f"\n(b) TEST loss rate: base {B_['loss_rate']:.3f}% ({B_['L']}/{B_['n']}) -> stack {S_['loss_rate']:.3f}% ({S_['L']}/{S_['n']}) = "
          f"x{b['rate_ratio']:.2f}; expected losses at the base rate {b['expected_losses_at_base_rate']:.1f}, got {S_['L']}", flush=True)
    print(f"    random thinning P(<= {S_['L']} losses) = {b['hyper_P_L_le_stack_random_thinning']:.3f}  (binomial {b['binom_P_L_le_stack']:.3f}; "
          f"P(<= {S_['L'] - 1}) = {b['hyper_P_L_le_stack_minus_1']:.3f})", flush=True)
    bb = b["day_bootstrap_ratio"]
    print(f"    day bootstrap of the rate ratio: median {bb['p50']:.2f}, 90% CI {bb['p5']:.2f}-{bb['p95']:.2f}, 95% CI {bb['p2_5']:.2f}-"
          f"{bb['p97_5']:.2f}, P(ratio >= 1) = {bb['P_ratio_ge_1']:.3f}", flush=True)
    print(f"    stack TEST trades that are also base TEST trades: {b['stack_test_trades_also_in_base']} of {S_['n']}", flush=True)
    s1 = b["step1_vs_base"]
    print(f"    step 1 alone (FriCut 10) TEST {fmt(S1)}  x{s1['rate_ratio']:.2f} vs base, P={s1['hyper_P']:.3f}, bootstrap 90% CI "
          f"{s1['day_bootstrap_ratio']['p5']:.2f}-{s1['day_bootstrap_ratio']['p95']:.2f}", flush=True)
    s2 = b["steps2to8_vs_step1"]
    print(f"    steps 2-8 on top of step 1: x{s2['rate_ratio']:.2f} the step-1 rate; expected {s2['expected_losses_at_step1_rate']:.1f}"
          f" losses, got {S_['L']}; random thinning P = {s2['hyper_P_L_le_stack']:.3f}; bootstrap 90% CI {s2['day_bootstrap_ratio']['p5']:.2f}-"
          f"{s2['day_bootstrap_ratio']['p95']:.2f}, P(ratio >= 1) {s2['day_bootstrap_ratio']['P_ratio_ge_1']:.3f}", flush=True)
    print(f"    TRAIN (in-sample) rate ratio x{b['train_rate_ratio_in_sample']:.2f}, hyper P {b['train_hyper_P_in_sample']:.2g}", flush=True)

    # ---- (c) one grid step either way, off-grid probes, implicit knobs
    plan = []
    for k, v in STACK.items():
        for d, nv in grid_neighbours(k, v):
            plan.append(("grid", k, v, d, f"{nv:g}"))
    probes = {"InpUhvFriCutNY": ["8", "9", "11"], "InpUhvDeepRet": ["0.4", "0.45", "0.55"], "InpUhvSpikeAtr": ["1.5", "2.5"],
              "InpUhvMaxGapPips": ["0.2", "0.25", "0.35", "0.4"], "InpUhvRunPips": ["7", "9"]}
    for k, vs in probes.items():
        for nv in vs:
            plan.append(("off-grid", k, STACK[k], "down" if float(nv) < float(STACK[k]) else "up", nv))
    for kn in KNOBS:
        d0 = U.UHV_DEFAULTS[kn][0]
        for d, nv in grid_neighbours(kn, d0):
            plan.append(("knob", kn, d0, d, f"{nv:g}"))
    print(f"\n(c) {len(plan)} perturbations", flush=True)
    pert = []
    for kind, k, v0, d, nv in plan:
        s = dict(STACK)
        loo = float(nv) == 0 and k in STACK
        if loo:
            s.pop(k)
        else:
            s[k] = nv
        sc = score(s)
        e = {"kind": kind, "setting": k, "from": v0, "to": nv, "dir": d, "is_leave_one_out": loo,
             "train": sc["train"], "test": sc["test"], "all": sc["all"],
             "test_rate_ratio_vs_base": (sc["test"]["loss_rate"] / B_["loss_rate"]) if sc["test"]["n"] else None,
             "test_hyper_P_vs_base": hyp_le(sc["test"]["L"], B_["n"], B_["L"], sc["test"]["n"]) if sc["test"]["n"] else None}
        pert.append(e)
        print(f"  {kind:8s} {k:18s} {v0:>4s} -> {nv:<5s} TRAIN {fmt(sc['train'])}\n  {'':47s} TEST  {fmt(sc['test'])}  "
              f"x{e['test_rate_ratio_vs_base']:.2f} P={e['test_hyper_P_vs_base']:.3f}", flush=True)
    R["c_perturbation"] = pert

    # ---- (d) TEST month by month
    R["d_months"] = {"base": base["test_months"], "stack": stk["test_months"], "step1_only": step1["test_months"]}
    print("\n(d) TEST months   base n/L/WR/clean            stack n/L/WR/clean            rate ratio", flush=True)
    for m in sorted(DEN_M):
        a, c = base["test_months"][m], stk["test_months"][m]
        rr = (c["loss_rate"] / a["loss_rate"]) if (a["L"] and c["n"]) else None
        print(f"   {m}  {a['n']:5d}/{a['L']:3d}/{a['wr']:6.2f}%/{a['lfd']:2d} of {a['den']:2d}    {c['n']:4d}/{c['L']:2d}/"
              f"{(c['wr'] or 0):6.2f}%/{c['lfd']:2d} of {c['den']:2d}    {('x%.2f' % rr) if rr is not None else '-'}   "
              f"P={hyp_le(c['L'], a['n'], a['L'], c['n']):.3f}", flush=True)

    # ---- (e) leave-one-out
    loo_out = []
    print("\n(e) leave-one-out (stack minus one setting)", flush=True)
    for k in ORDER:
        s = {kk: vv for kk, vv in STACK.items() if kk != k}
        sc = score(s)
        e = {"dropped": k, "train": sc["train"], "test": sc["test"], "all": sc["all"],
             "test_rate_ratio_vs_base": sc["test"]["loss_rate"] / B_["loss_rate"],
             "test_rate_ratio_vs_stack": sc["test"]["loss_rate"] / S_["loss_rate"],
             "test_hyper_P_vs_base": hyp_le(sc["test"]["L"], B_["n"], B_["L"], sc["test"]["n"]),
             "test_months": sc["test_months"]}
        loo_out.append(e)
        print(f"  - {k:18s} TRAIN {fmt(sc['train'])}\n  {'':20s} TEST  {fmt(sc['test'])}  x{e['test_rate_ratio_vs_base']:.2f} vs base", flush=True)
    R["e_leave_one_out"] = loo_out
    solo = []
    print("\n(e2) each setting ALONE on the base", flush=True)
    for k in ORDER:
        sc = score({k: STACK[k]})
        e = {"setting": k, "value": STACK[k], "train": sc["train"], "test": sc["test"],
             "test_rate_ratio_vs_base": sc["test"]["loss_rate"] / B_["loss_rate"],
             "test_hyper_P_vs_base": hyp_le(sc["test"]["L"], B_["n"], B_["L"], sc["test"]["n"]),
             "train_rate_ratio_vs_base": sc["train"]["loss_rate"] / base["train"]["loss_rate"]}
        solo.append(e)
        print(f"  {k}={STACK[k]:<4s} TRAIN {fmt(sc['train'])}  x{e['train_rate_ratio_vs_base']:.2f}\n  {'':24s} TEST  {fmt(sc['test'])}  "
              f"x{e['test_rate_ratio_vs_base']:.2f} P={e['test_hyper_P_vs_base']:.3f}", flush=True)
    R["e2_alone"] = solo
    R["engine_hashes_at_end"] = {f: sha1(os.path.join(ROOT, f)) for f in ENGINE_FILES}
    R["engine_changed_during_run"] = R["engine_hashes_at_end"] != hashes0
    R["minutes"] = round((time.time() - T0) / 60, 1)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(R, f, indent=1)
    print(f"\nengine changed during run: {R['engine_changed_during_run']}; {R['minutes']} min; wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
