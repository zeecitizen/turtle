"""final_report.py - honesty checks on the clean-days stack found by stack_search.py (reads results.json).

  1. base vs final on TRAIN / TEST / ALL, and which of the base's 172 losses the stack removes / which new losses its freed slots add
  2. the "just trading less" nulls - fewer trades per day mechanically raises the share of loss-free days, so the stack is compared with
     (a) UNIFORM thinning: the stack's trade count drawn at random from the base's trades of that half, 2000 times
     (b) PER-DAY thinning: on every FX day, as many trades as the stack took that day, drawn at random from the base's trades of that day
     A stack that only trades less lands inside the null band; WR (the per-trade loss rate) cannot be faked by trading less.
  3. leave-one-out: the final stack without each of its settings (TRAIN and TEST)
  4. the doctrine haircut (monitor/doctrine.py) - Python tick replay = HYPOTHESIS, NOT PROMOTED
  5. the final stack saved in Turtle TV's saved-setting format, in THIS folder only (final_setting.json)
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/stacks/cleandays/final_report.py"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, r"C:/Users/zeesh/turtle/monitor")
import numpy as np  # noqa: E402
import common as C  # noqa: E402
import uhv_engine as U  # noqa: E402

R = json.load(open(os.path.join(HERE, "results.json"), encoding="utf-8"))
STACK = R["final_stack"]
B = C.base_inputs()
rng = np.random.default_rng(20261106)
NDRAW = 2000
OUT = {}


def real(rows):
    return rows[rows[:, 10] == 0]


def fmt(x):
    return f"{x['n']} / {x['L']} / {x['wr']:.2f}% / {x['clean_pct']:.1f}% ({x['clean']}/{x['days']}) / {x['net']:+,.0f}"


def clean_share(day, loss):
    if not len(day):
        return 0.0, 0
    d = np.unique(day); ld = np.unique(day[loss])
    return 100.0 * (len(d) - len(ld)) / len(d), len(d)


rb = real(U.simulate(B)[0]); rf = real(U.simulate(dict(B, **STACK))[0])
sb, sf = C.score(rb), C.score(rf)
print("Python tick replay = HYPOTHESIS. NOT PROMOTED. Only MT5 or live fills decide.\n")
print(f"final stack: {STACK}\n")
print(f"{'':6s} {'base: trades / losses / WR / loss-free days / net':60s} {'final stack':60s}")
for p in ("train", "test", "all"):
    print(f"{p.upper():6s} {fmt(sb[p]):60s} {fmt(sf[p]):60s}")
    OUT[p] = {"base": {k: sb[p][k] for k in ("n", "L", "wr", "net", "days", "clean", "clean_pct")},
              "final": {k: sf[p][k] for k in ("n", "L", "wr", "net", "days", "clean", "clean_pct")}}
assert sf["train"]["days"] + sf["test"]["days"] in (sf["all"]["days"], sf["all"]["days"] + 1)
if sf["train"]["days"] + sf["test"]["days"] != sf["all"]["days"]:
    print("  note: one FX day straddles the 2026-07-01 00:00 UTC split (counted in both halves)")

kb, kf = set(map(tuple, sb["loss_keys"])), set(map(tuple, sf["loss_keys"]))
gone, new = kb - kf, kf - kb
print(f"\nlosses: base {len(kb)}, final {len(kf)}; base losses removed {len(gone)}, new losses (freed slots) {len(new)}")
OUT["losses"] = {"base": len(kb), "final": len(kf), "removed": len(gone), "new": len(new)}

# ---- 2. the 'just trading less' nulls
print("\nNULLS - does the stack pick better trades, or only fewer? (2000 random draws from the base's own trades)")
for part, mb, mf in (("train", rb[:, 1] < C.SPLIT, rf[:, 1] < C.SPLIT), ("test", rb[:, 1] >= C.SPLIT, rf[:, 1] >= C.SPLIT)):
    b_day, b_loss = C.fxday(rb[mb, 1]), rb[mb, 6] < 0
    f_day, f_loss = C.fxday(rf[mf, 1]), rf[mf, 6] < 0
    obs, obs_days = clean_share(f_day, f_loss)
    n = int(mf.sum())
    uni, uni_wr = [], []
    for _ in range(NDRAW):
        idx = rng.choice(len(b_day), size=min(n, len(b_day)), replace=False)
        uni.append(clean_share(b_day[idx], b_loss[idx])[0]); uni_wr.append(100.0 * (1 - b_loss[idx].mean()))
    # per-day: as many trades as the stack took that day, drawn from the base's trades of that day
    cnt = {int(d): int(c) for d, c in zip(*np.unique(f_day, return_counts=True))}
    groups = {int(d): np.nonzero(b_day == d)[0] for d in np.unique(b_day)}
    pd_ = []
    for _ in range(NDRAW):
        clean = days = 0
        for d, c in cnt.items():
            g = groups.get(d)
            if g is None or not len(g):
                continue
            pick = rng.choice(g, size=min(c, len(g)), replace=False)
            days += 1; clean += int(not b_loss[pick].any())
        pd_.append(100.0 * clean / max(days, 1))
    uni, pd_, uni_wr = np.asarray(uni), np.asarray(pd_), np.asarray(uni_wr)
    wr_f, wr_b = 100.0 * (1 - f_loss.mean()) if n else 0.0, 100.0 * (1 - b_loss.mean())
    r = {"observed_clean_pct": round(obs, 2), "trades": n,
         "uniform_null_mean": round(float(uni.mean()), 2), "uniform_null_band": [round(float(np.percentile(uni, 2.5)), 2), round(float(np.percentile(uni, 97.5)), 2)],
         "uniform_p_ge": round(float((uni >= obs - 1e-9).mean()), 4),
         "perday_null_mean": round(float(pd_.mean()), 2), "perday_null_band": [round(float(np.percentile(pd_, 2.5)), 2), round(float(np.percentile(pd_, 97.5)), 2)],
         "perday_p_ge": round(float((pd_ >= obs - 1e-9).mean()), 4),
         "wr_final": round(wr_f, 3), "wr_base": round(wr_b, 3), "wr_uniform_band": [round(float(np.percentile(uni_wr, 2.5)), 3), round(float(np.percentile(uni_wr, 97.5)), 3)],
         "wr_p_ge": round(float((uni_wr >= wr_f - 1e-9).mean()), 4)}
    OUT[f"null_{part}"] = r
    print(f"  {part.upper():5s} stack loss-free {obs:.1f}% of {obs_days} days with {n} trades | uniform-thinning null {r['uniform_null_mean']:.1f}% "
          f"[{r['uniform_null_band'][0]:.1f}, {r['uniform_null_band'][1]:.1f}] p={r['uniform_p_ge']:.3f} | per-day null {r['perday_null_mean']:.1f}% "
          f"[{r['perday_null_band'][0]:.1f}, {r['perday_null_band'][1]:.1f}] p={r['perday_p_ge']:.3f}")
    print(f"        WR stack {wr_f:.2f}% vs base {wr_b:.2f}% (random thinning keeps WR in [{r['wr_uniform_band'][0]:.2f}, {r['wr_uniform_band'][1]:.2f}], p={r['wr_p_ge']:.3f})")

# ---- 2b. per step: the exact expectation of the loss-free share if the stack's per-day trade counts were random picks from the base's
#          trades of that day (hypergeometric: P(clean day) = C(N-L, c) / C(N, c), N / L = the base's trades / losses that FX day)
from math import comb  # noqa: E402


def perday_expect(rows_f, rows_b, m_f, m_b):
    bd, bl = C.fxday(rows_b[m_b, 1]), rows_b[m_b, 6] < 0
    N = {int(d): int(c) for d, c in zip(*np.unique(bd, return_counts=True))}
    Lc = {int(d): int(c) for d, c in zip(*np.unique(bd[bl], return_counts=True))} if bl.any() else {}
    fd = C.fxday(rows_f[m_f, 1])
    ps = []
    for d, c in zip(*np.unique(fd, return_counts=True)):
        n_, l_ = N.get(int(d), 0), Lc.get(int(d), 0)
        if n_ == 0:
            continue
        c = min(int(c), n_)
        ps.append(comb(n_ - l_, c) / comb(n_, c) if c <= n_ - l_ else 0.0)
    return 100.0 * float(np.mean(ps)) if ps else 0.0


print("\nPER STEP - observed loss-free share vs the share random per-day thinning would give at the same trade counts:")
steps_out = []
for st in [{"step": 0, "setting": "base", "value": "", "stack": {}}] + R["steps"]:
    rs = real(U.simulate(dict(B, **st["stack"]))[0])
    ss = C.score(rs)
    row = {"step": st["step"], "setting": st["setting"], "value": st["value"]}
    line = f"  step {st['step']} {st['setting'] + '=' + str(st['value']) if st['step'] else 'base':28s}"
    for part, mf, mb in (("train", rs[:, 1] < C.SPLIT, rb[:, 1] < C.SPLIT), ("test", rs[:, 1] >= C.SPLIT, rb[:, 1] >= C.SPLIT)):
        e = perday_expect(rs, rb, mf, mb)
        row[part] = {"obs": ss[part]["clean_pct"], "thinning_expect": round(e, 2), "excess_pt": round(ss[part]["clean_pct"] - e, 2), "wr": ss[part]["wr"], "n": ss[part]["n"]}
        line += f"  {part.upper()} {ss[part]['clean_pct']:5.1f}% vs thinning {e:5.1f}% ({ss[part]['clean_pct'] - e:+5.1f} pt, WR {ss[part]['wr']:.2f}%, {ss[part]['n']} trades)"
    steps_out.append(row)
    print(line)
OUT["per_step_thinning"] = steps_out

# ---- 3. leave-one-out
print("\nLEAVE-ONE-OUT (the final stack without one setting; knobs leave with their filter):")
KNOB = {"InpUhvSRLook": "InpUhvSRPips", "InpUhvRangeBars": "InpUhvRangeAtr", "InpUhvFreshSwings": "InpUhvFreshBreak", "InpUhvBrokeLook": "InpUhvBrokeHighs",
        "InpUhvHtf5N": "InpUhvHtf5", "InpUhvSRAheadLook": "InpUhvSRAhead", "InpUhvFigStep": "InpUhvBigFig", "InpUhvCounterBars": "InpUhvCounterAtr",
        "InpUhvRunBars": "InpUhvRunPips", "InpUhvNewsMins": "InpUhvNewsNY", "InpUhvSpikeBars": "InpUhvSpikeAtr"}
loo = []
for k in STACK:
    if k in KNOB and KNOB[k] in STACK:
        drop = {k}                                        # a knob alone: back to its default value, filter kept
    else:
        drop = {k} | {kk for kk, f in KNOB.items() if f == k and kk in STACK}
    st = {kk: v for kk, v in STACK.items() if kk not in drop}
    s = C.score(real(U.simulate(dict(B, **st))[0]))
    d_tr, d_te = s["train"]["clean_pct"] - sf["train"]["clean_pct"], s["test"]["clean_pct"] - sf["test"]["clean_pct"]
    loo.append({"without": sorted(drop), "train": {q: s["train"][q] for q in ("n", "L", "wr", "net", "days", "clean", "clean_pct")},
                "test": {q: s["test"][q] for q in ("n", "L", "wr", "net", "days", "clean", "clean_pct")}, "d_train_pt": round(d_tr, 2), "d_test_pt": round(d_te, 2)})
    print(f"  without {','.join(sorted(drop)):34s} TRAIN {fmt(s['train'])} ({d_tr:+.1f} pt)   TEST {fmt(s['test'])} ({d_te:+.1f} pt)")
OUT["leave_one_out"] = loo

# ---- 4. the doctrine haircut
pn = rf[:, 6]
wins, losses = pn[pn > 0], pn[pn < 0]
need = 100.0 * abs(losses.mean()) / (wins.mean() + abs(losses.mean())) if len(wins) and len(losses) else None
print("\nDOCTRINE (monitor/doctrine.py):")
try:
    from doctrine import python_says
    python_says(f"clean-days stack, ALL Mar-Nov ({len(pn)} trades)", win_pct=sf["all"]["wr"], need_pct=need)
except Exception as e:                                      # noqa: BLE001
    print("  doctrine import failed:", e)
print(f"  avg win ${wins.mean():.2f}, avg loss ${losses.mean():.2f} -> break-even WR {need:.2f}%" if need else "")
OUT["breakeven_wr"] = round(need, 3) if need else None

# ---- 5. the saved-setting JSON (this folder only)
cum = np.cumsum(pn); dd = float(np.max(np.maximum.accumulate(np.r_[0.0, cum]) - np.r_[0.0, cum])) if len(cum) else 0.0
gw, gl = float(wins.sum()), float(-losses.sum())
saved = json.load(open(C.BASE_FILE, encoding="utf-8"))
inputs = dict(B); inputs.update(STACK)                       # every engine default filled in (self-contained)
changed = dict(saved["changed"]); changed.update(STACK)
setting = {"name": "UHV 97.7% + clean-days stack (loss study, TRAIN Mar-Jun greedy; Python hypothesis)", "inputs": inputs, "changed": changed,
           "ds": "year1", "mode": "ea",
           "result": {"n": int(len(pn)), "net": round(float(pn.sum()), 2), "pf": round(gw / gl, 3) if gl else None, "wr": round(sf["all"]["wr"], 2),
                      "avg_loss": round(float(losses.mean()), 2) if len(losses) else 0, "worst_loss": round(float(losses.min()), 2) if len(losses) else 0,
                      "dd": round(dd, 2), "ret_dd": (float(pn.sum()) / dd) if dd else None},
           "lab": {}, "lab_describe": "", "source": {"kind": "loss_study_stack", "objective": "TRAIN loss-free-day share", "script": os.path.join(HERE, "stack_search.py"),
                                                    "train_until_utc": C.SPLIT, "promoted": False}}
with open(os.path.join(HERE, "final_setting.json"), "w", encoding="utf-8") as f:
    json.dump(setting, f, indent=1)
with open(os.path.join(HERE, "final_report.json"), "w", encoding="utf-8") as f:
    json.dump(OUT, f, indent=1)
print(f"\nsaved {os.path.join(HERE, 'final_setting.json')} and final_report.json")
