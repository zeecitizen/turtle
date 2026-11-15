"""Turtle TV tester (HYPOTHESIS engine) - the base vs exit variants motivated by the paper
"Hierarchical Execution Architectures ... Dynamic Sub-Trade Lot Allocation" (Aremu 2026).
The paper splits one signal into sub-trades: fixed-pip trails (fast / slow) and ATR trails
(1x / 2.5x / 5x). The EA has two partials (InpXP1*, InpXP2*) + one trail on the remainder
(InpXTr*) and an ATR stop mode (InpSlMode 1) - that is the mapping. Nothing here is a verdict.
"""
import sys, json, datetime as dt
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import numpy as np
import server, sim

BASE = r"C:\Users\zeesh\turtle\monitor\saad_view\settings\saved\2026-11-01 08-38-10.json"
base = json.load(open(BASE, encoding="utf-8"))

D = sim.data("m15")
yrs = np.array([dt.datetime.utcfromtimestamp(t).year for t in D["t15"]])
print("ATR(14) M15 in $ by year (p25 / median / p75):")
for y in sorted(set(yrs)):
    a = D["atr"][yrs == y]; a = a[a > 0]
    print(" ", y, [round(float(np.percentile(a, p)), 2) for p in (25, 50, 75)])
a = D["atr"][D["atr"] > 0]
print("  all", [round(float(np.percentile(a, p)), 2) for p in (25, 50, 75)], "k for median stop $26 =", round(26 / float(np.median(a)), 2))


def run(name, changes):
    inputs = dict(base["inputs"]); inputs.update({k: str(v) for k, v in changes.items()})
    trades, setups, stats = sim.simulate(server.full_inputs(inputs), ds="m15")
    real = trades[trades[:, 10] == 0]
    s = sim.score(real)
    years = np.array([dt.datetime.utcfromtimestamp(t).year for t in real[:, 1]])
    py = {}
    for y in sorted(set(years)):
        r = real[years == y]; py[int(y)] = (len(r), round(100 * (r[:, 6] > 0).mean(), 1), round(float(r[:, 6].sum())))
    print(f"\n== {name}  {changes}")
    print("   ", {k: s[k] for k in ("n", "net", "pf", "wr", "avg_loss", "worst_loss", "dd")}, "ret_dd", round(s["ret_dd"], 1))
    print("    per year", py)
    return s, py


V = {
 "V0 base": {},
 # Paper's architecture: no all-close target; 60% off at the base's 1:1 ($26 = 1R) [Matt+Mark], 25% at 2R [Luke], 15% rides on a 2xATR trail [John]; stop to BE after the first partial
 "V1 tranches 60/25/15 keep EMA-cross exit": {"InpXTgt": 1, "InpXP1R": 1.0, "InpXP1Frac": 0.6, "InpXP1Be": "true", "InpXP2R": 2.0, "InpXP2Frac": 0.25, "InpXTr": 2, "InpXTrK": 2, "InpXTrAct": 0},
 "V2 tranches 60/25/15 no EMA-cross exit": {"InpXTgt": 1, "InpXP1R": 1.0, "InpXP1Frac": 0.6, "InpXP1Be": "true", "InpXP2R": 2.0, "InpXP2Frac": 0.25, "InpXTr": 2, "InpXTrK": 2, "InpXTrAct": 0, "InpXCx": 0},
 # Paper's lot split 40 fixed / 60 adaptive: 40% at 1R (fixed anchor), 30% at 1.5R (Mark, low ATR), 30% rides 2xATR (Luke/John)
 "V3 tranches 40/30/30": {"InpXTgt": 1, "InpXP1R": 1.0, "InpXP1Frac": 0.4, "InpXP1Be": "true", "InpXP2R": 1.5, "InpXP2Frac": 0.3, "InpXTr": 2, "InpXTrK": 2, "InpXTrAct": 0},
 # Half fixed at 1R, half rides on the ATR trail (the simplest two-subtrade version), no BE
 "V4 half at 1R half ATR trail no BE": {"InpXTgt": 1, "InpXP1R": 1.0, "InpXP1Frac": 0.5, "InpXP1Be": "false", "InpXTr": 2, "InpXTrK": 2, "InpXTrAct": 0},
 # Matt: fast fixed-$ trail from the best price on top of the base (early-impulse capture) - the base's target stays
 "V5 base + fast $ trail 8 from +0.5R": {"InpXTr": 1, "InpXTrK": 8, "InpXTrAct": 0.5},
 # Adaptive stop AND adaptive target (1:1 kept in ATR units): the stop breathes with volatility - geometry changes, said in the verdict
 "V6 ATR stop+target k=4": {"InpSlMode": 1, "InpSlAtrMult": 4, "InpXTgt": 3, "InpXTgtK": 4},
 "V7 ATR stop+target k=3": {"InpSlMode": 1, "InpSlAtrMult": 3, "InpXTgt": 3, "InpXTgtK": 3},
 # Adaptive stop only, fixed $26 target kept
 "V8 ATR stop k=4 fixed $26 target": {"InpSlMode": 1, "InpSlAtrMult": 4},
}
res = {}
for k, v in V.items():
    try:
        res[k] = run(k, v)
    except Exception as e:
        print("\n== ", k, "FAILED", repr(e))
json.dump({k: {"score": s, "per_year": {str(y): list(t) for y, t in py.items()}, "changes": V[k]} for k, (s, py) in res.items()},
          open(r"C:\Users\zeesh\turtle\monitor\saad_view\papers\store\2026-11-01 20-19-35-HierarchicalExecutionArchitecturesinTran\tester_variants.json", "w"), indent=1)
