"""supplement.py - follow-ups on redteam_results.json (research/loss_study/stacks/redteam_Maximisethe).

Python tick replay = HYPOTHESIS. NOT PROMOTED. Only MT5 or live fills decide (CLAUDE.md).

 1. the neighbourhood's corr(TRAIN excess, TEST excess) - is it only the MinHumps axis (trade count)? recomputed WITHIN each MinHumps level,
    and against the TEST trade count
 2. the greedy path in LOSSES: how many TRAIN vs TEST losses each step removed, and how many trades it cost
 3. freed-slot trades (stack trades the base never took) split TRAIN / TEST, with their losses
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/redteam_Maximisethe/supplement.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import rt_common as C  # noqa: E402

R = json.load(open(os.path.join(HERE, "redteam_results.json"), encoding="utf-8"))
OUT = {}
grid = R["c_neighbourhood"]["runs"]

# ---- 1. correlation within MinHumps levels
print("1. TRAIN-vs-TEST excess across the neighbourhood, within each MinHumps level")
c1 = {}
for lv in ("3", "4", "5"):
    sel = [g for g in grid if g["values"]["InpUhvMinHumps"] == lv]
    tr = np.array([g["score"]["train"]["excess"] for g in sel]); te = np.array([g["score"]["test"]["excess"] for g in sel])
    trr = np.array([g["score"]["train"]["rate"] for g in sel]); ter = np.array([g["score"]["test"]["rate"] for g in sel])
    n_te = np.array([g["score"]["test"]["n"] for g in sel]); L_te = np.array([g["score"]["test"]["L"] for g in sel])
    c = float(np.corrcoef(tr, te)[0, 1]) if tr.std() > 0 and te.std() > 0 else float("nan")
    cr = float(np.corrcoef(trr, ter)[0, 1]) if trr.std() > 0 and ter.std() > 0 else float("nan")
    c1[lv] = {"runs": len(sel), "corr_train_test_excess": round(c, 3), "corr_train_test_rate": round(cr, 3),
              "train_excess_median": round(float(np.median(tr)), 2), "test_excess_median": round(float(np.median(te)), 2),
              "test_trades_median": int(np.median(n_te)), "test_pooled_rate_pct": round(100.0 * L_te.sum() / n_te.sum(), 3),
              "test_losses_range": [int(L_te.min()), int(L_te.max())]}
    print(f"   MinHumps={lv}: {c1[lv]}")
alln = np.array([g["score"]["test"]["n"] for g in grid]); alle_tr = np.array([g["score"]["train"]["excess"] for g in grid])
alle_te = np.array([g["score"]["test"]["excess"] for g in grid])
c1["corr_test_excess_vs_test_trades_all"] = round(float(np.corrcoef(alle_te, alln)[0, 1]), 3)
c1["corr_train_excess_vs_test_trades_all"] = round(float(np.corrcoef(alle_tr, alln)[0, 1]), 3)
print(f"   all 243: corr(TEST excess, TEST trades) = {c1['corr_test_excess_vs_test_trades_all']:+.2f}, corr(TRAIN excess, TEST trades) = {c1['corr_train_excess_vs_test_trades_all']:+.2f}")
OUT["within_minhumps"] = c1

# ---- 2. the greedy path in losses
print("\n2. the greedy path in LOSSES removed (TRAIN chooses; TEST untouched)")
path = R["e_loo"]["path"]
steps = []
for a, b in zip(path[:-1], path[1:]):
    d = {p: {"trades_cut": a["score"][p]["n"] - b["score"][p]["n"], "losses_cut": a["score"][p]["L"] - b["score"][p]["L"],
             "excess_gain": round(b["score"][p]["excess"] - a["score"][p]["excess"], 2)} for p in ("train", "test")}
    steps.append({"added": b["added"], **d})
    print(f"   +{b['added']:18s} TRAIN: cut {d['train']['trades_cut']:5d} trades / {d['train']['losses_cut']:3d} losses (excess {d['train']['excess_gain']:+.1f})"
          f"   TEST: cut {d['test']['trades_cut']:5d} trades / {d['test']['losses_cut']:3d} losses (excess {d['test']['excess_gain']:+.1f})")
OUT["path_losses"] = steps

# ---- 3. freed slots by half (needs the trades: rerun base + stack)
import uhv_engine as U  # noqa: E402
B = C.base_inputs()
rb = C.real(U.simulate(B)[0]); rf = C.real(U.simulate(dict(B, **C.STACK))[0])
kb = set(zip(rb[:, 0].astype(int).tolist(), np.round(rb[:, 1], 3).tolist()))
inb = np.array([(int(a), round(float(t), 3)) in kb for a, t in zip(rf[:, 0], rf[:, 1])], bool)
fr = {}
for p, m in C.masks(rf[:, 1]).items():
    lossm = rf[:, 6] < 0
    fr[p] = {"stack_trades": int(m.sum()), "in_base": {"n": int((m & inb).sum()), "L": int((m & inb & lossm).sum())},
             "freed_slot": {"n": int((m & ~inb).sum()), "L": int((m & ~inb & lossm).sum())}}
    fs = fr[p]["freed_slot"]; ib = fr[p]["in_base"]
    p0 = {"train": 112 / 3336, "test": 60 / 4295, "all": 172 / 7631}[p]
    fr[p]["freed_slot"]["p_zero_or_fewer_at_base_rate"] = round(C.binom_cdf(fs["L"], fs["n"], p0), 4) if fs["n"] else None
    print(f"   {p.upper():5s} stack {m.sum()} trades: also in the base {ib['n']} ({ib['L']} losses = {100*ib['L']/max(ib['n'],1):.2f}%)"
          f"   freed-slot {fs['n']} ({fs['L']} losses = {100*fs['L']/max(fs['n'],1):.2f}%; P(<= that many at the base rate) = {fr[p]['freed_slot']['p_zero_or_fewer_at_base_rate']})")
OUT["freed_slots_by_half"] = fr
tmp = os.path.join(HERE, "supplement_results.json.tmp")
json.dump(OUT, open(tmp, "w", encoding="utf-8"), indent=1)
os.replace(tmp, os.path.join(HERE, "supplement_results.json"))
print("\nsaved supplement_results.json")
