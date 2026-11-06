"""my_engine.py (work_redteam) - INDEPENDENT engine re-run of the verdict's numbers (own stats code, not the judge's).
Python tick replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md). Split 2026-07-01 00:00 UTC.
Run: cd C:/Users/zeesh/turtle/monitor/TurtleTVUHV && NUMBA_CPU_NAME=generic py research/loss_study/tight/work_redteam/my_engine.py"""
import json, os, sys, time
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
ROOT = r"C:/Users/zeesh/turtle/monitor/TurtleTVUHV"
sys.path.insert(0, ROOT)
import numpy as np
import uhv_engine as U

SPLIT = 1782864000
SAVED = os.path.join(ROOT, "settings", "saved")
OUT = os.path.dirname(os.path.abspath(__file__))
def inp(fn): return json.load(open(os.path.join(SAVED, fn + ".json"), encoding="utf-8"))["inputs"]
SET = {"base": inp("2026-11-05 05-45-38"), "secure": inp("2026-11-06 09-10-00"), "tight": inp("2026-11-06 09-00-00"), "zee100": inp("2026-11-06 07-33-17")}
RES = {}

def real(rows): return rows[rows[:, 10] == 0]

def st(R):
    def one(m):
        p = R[m, 6]; n = len(p); L = int((p <= 0).sum())
        return dict(n=n, L=L, wr=round(100 * (1 - L / n), 2) if n else None, net=round(float(p.sum()), 2))
    tin = R[:, 1]
    return {"all": one(np.ones(len(R), bool)), "train": one(tin < SPLIT), "test": one(tin >= SPLIT)}

def line(name, s):
    return f"{name:58s} " + "  ".join(f"{h} {s[h]['n']}/{s[h]['L']}L {s[h]['wr']}% {s[h]['net']:+.2f}" for h in ("all", "train", "test"))

def run(name, base, **chg):
    x = dict(SET[base]); x.update({k: str(v) for k, v in chg.items()})
    rows, su, cnt = U.simulate(x)
    R = real(rows); s = st(R)
    RES[name] = {"base": base, "chg": chg, "stats": s, "losses": [[float(r[1]), int(r[0]), round(float(r[6]), 2)] for r in R if r[6] <= 0]}
    print(line(name, s), flush=True)
    return R

t0 = time.time()
print("== the four stacks as saved")
Rb = run("base 05-45-38", "base")
Rs = run("secure 09-10-00", "secure")
Rt = run("tight 09-00-00", "tight")
Rz = run("zee100 07-33-17", "zee100")
print("== Zee's three logged steps, from secure")
run("step0 secure", "secure")
run("step1 secure + ErMin 0.30", "secure", InpUhvSafeErMin=0.3)
run("step2 + HumpsMax 3", "secure", InpUhvSafeErMin=0.3, InpUhvSafeHumpsMax=3)
run("step3 + ErMax 0.35", "secure", InpUhvSafeErMin=0.3, InpUhvSafeHumpsMax=3, InpUhvSafeErMax=0.35)
print("== verdict's variants")
run("zee100 + MaxTrigSpread 0.5", "zee100", InpUhvMaxTrigSpread=0.5)
run("tight + MaxTrigSpread 0.5", "tight", InpUhvMaxTrigSpread=0.5)
run("secure + MaxTrigSpread 0.5", "secure", InpUhvMaxTrigSpread=0.5)
run("zee100 + SafeRange 9.2/120", "zee100", InpUhvSafeRangeAtr=9.2, InpUhvSafeRangeBars=120)
run("tight + SafeRange 9.2/120", "tight", InpUhvSafeRangeAtr=9.2, InpUhvSafeRangeBars=120)
run("secure + SafeRange 9.2/120", "secure", InpUhvSafeRangeAtr=9.2, InpUhvSafeRangeBars=120)
run("secure + MaxTrig 0.5 + SafeRange 9.2/120", "secure", InpUhvMaxTrigSpread=0.5, InpUhvSafeRangeAtr=9.2, InpUhvSafeRangeBars=120)
run("secure + ErMax 0.35", "secure", InpUhvSafeErMax=0.35)
run("zee100 + RunPips 8.1/60 (inert?)", "zee100", InpUhvRunPips=8.1, InpUhvRunBars=60)
run("zee100 + NewsNY 1 (inert?)", "zee100", InpUhvNewsNY=1)
print("== knife-edge claims (work_wf)")
for nm, ch in [("ErMax 0.36", dict(InpUhvSafeErMax=0.36)), ("ErMin 0.28", dict(InpUhvSafeErMin=0.28)), ("ErMin 0.29", dict(InpUhvSafeErMin=0.29)),
               ("humps 1-3", dict(InpUhvSafeHumpsMin=1)), ("humps 2-4", dict(InpUhvSafeHumpsMax=4)), ("ErBars 12", dict(InpUhvSafeErBars=12)),
               ("ErBars 15", dict(InpUhvSafeErBars=15)), ("ErBars 17", dict(InpUhvSafeErBars=17)), ("ErBars 20", dict(InpUhvSafeErBars=20)),
               ("latency 0.0", dict(InpUhvLatency=0.0)), ("latency 0.1", dict(InpUhvLatency=0.1)), ("latency 0.5", dict(InpUhvLatency=0.5)),
               ("latency 1.0", dict(InpUhvLatency=1.0)), ("FixTp 0.15 (~0.05 pip worse fill)", dict(InpUhvFixTp=0.15)),
               ("FixTp 0.2 (~0.1 pip worse fill)", dict(InpUhvFixTp=0.2)), ("FixTp 0.3 (~0.2 pip worse fill)", dict(InpUhvFixTp=0.3))]:
    run("zee100 " + nm, "zee100", **ch)
print("== neighbour bands of the box (humps 2-3), each as its own zone")
for lo, hi in [(0.20, 0.25), (0.25, 0.30), (0.30, 0.35), (0.35, 0.40), (0.40, 0.45)]:
    run(f"h2-3 ER[{lo:.2f},{hi:.2f})", "zee100", InpUhvSafeErMin=lo, InpUhvSafeErMax=hi)
run("h1-1 ER[0.30,0.35)", "zee100", InpUhvSafeHumpsMin=1, InpUhvSafeHumpsMax=1)
run("h4-5 ER[0.30,0.35)", "zee100", InpUhvSafeHumpsMin=4, InpUhvSafeHumpsMax=5)

# ---- payoff: what the engine credits on a win, vs a take-profit filled at exactly +0.1 pip
print("\n== PAYOFF (engine credits the crossing tick's full move on a target hit: _play 'pnl += left * m')")
for nm, R in (("zee100", Rz), ("tight", Rt), ("secure", Rs)):
    W = R[R[:, 6] > 0]; Ls = R[R[:, 6] <= 0]
    wp = np.round(W[:, 14], 3)
    vals, cnts = np.unique(wp, return_counts=True)
    top = ", ".join(f"{v:.1f}p x{c}" for v, c in list(zip(vals, cnts))[:8])
    risk = R[:, 17]
    print(f"{nm}: wins {len(W)}: mean ${W[:,6].mean():.3f} (pips mean {wp.mean():.3f}, median {np.median(wp):.2f}, share exactly 0.1p {100*np.mean(np.isclose(wp,0.1)):.1f}%) | {top}")
    print(f"     net as engine {R[:,6].sum():+.2f}; net if every win = +0.1 pip ($1.00/lot) {len(W)*1.0 + Ls[:,6].sum():+.2f}; "
          f"losses {len(Ls)} mean ${Ls[:,6].mean() if len(Ls) else 0:.2f}; risk$ (stop if hit) median {np.median(risk):.1f} mean {risk.mean():.1f} p10 {np.percentile(risk,10):.1f} p90 {np.percentile(risk,90):.1f}")
    for wl, lab in ((W[:, 6].mean(), "engine avg win"), (1.0, "TP exactly +0.1 pip")):
        for Lval, labl in ((np.median(risk), "median risk"), (Ls[:, 6].mean() if len(Ls) else np.median(risk), "mean actual loss")):
            Lval = abs(Lval)
            print(f"     break-even WR with {lab} ${wl:.2f} vs {labl} ${Lval:.0f}: {100*Lval/(Lval+wl):.2f}%")
months = (Rz[:, 1].max() - Rz[:, 1].min()) / (30.44 * 86400)
print(f"zee100 trades/month: {len(Rz)/months:.1f} over {months:.2f} months")

# ---- harness zee100 (tight trades with ER16 in [0.30,0.35)) vs the engine's zee100
T = json.load(open(os.path.join(os.path.dirname(OUT), "trades_tight.json"), encoding="utf-8"))
hz = [t for t in T if 0.30 <= t["er16"] < 0.35]
fz = set(np.round(Rz[:, 2] * 0 + Rz[:, 1], 1))
fill_t = {round(float(r[1]), 1): r for r in Rz}
# map harness trades to engine rows by fill time (t_dec + ~latency): nearest engine fill within 5 s after t_dec
ez = np.sort(Rz[:, 1])
matched = 0
for t in hz:
    j = np.searchsorted(ez, t["t_dec"])
    if j < len(ez) and ez[j] - t["t_dec"] < 5:
        matched += 1
print(f"harness zee100: {len(hz)} trades ({sum(1 for t in hz if not t['win'])} losses); matched in engine zee100: {matched}; engine zee100 trades {len(Rz)}")
tt = np.sort(np.array([t["t_dec"] for t in hz]))
extra = [r for r in Rz if not np.any(np.abs(tt - (r[1] - 0.3)) < 5)]
print(f"engine zee100 trades not in harness zee100: {len(extra)}; their results: {[round(float(r[6]),2) for r in extra]}")
print(f"split-sensitivity: engine zee100 fills within 10 s after the split: {int(np.sum((Rz[:,1]>=SPLIT)&(Rz[:,1]<SPLIT+10)))}")
json.dump(RES, open(os.path.join(OUT, "my_engine.json"), "w"), indent=1)
print(f"done in {time.time()-t0:.0f}s")
