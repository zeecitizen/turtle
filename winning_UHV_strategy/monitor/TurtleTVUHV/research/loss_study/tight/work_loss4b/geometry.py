"""geometry.py (work_loss4b) - ANALYSIS, not a rule: how many losses does the bare geometry (0.1-pip target, ~20-pip stop) predict?
Zero-drift random walk from the decision tick: P(loss) = (spread + 0.1) / (stop + 0.1) (the target must first cross the spread; same
formula as rule_trigger_spread's docstring in ../../final/rules_final.py). Reads stop/fill (outcome-side) - fine for calibration only.
Python replay = HYPOTHESIS ONLY."""
import json, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = 1782864000
P = 1e-4
rng = np.random.default_rng(1)
for st in ("tight", "zee100", "secure", "base"):
    T = json.load(open(os.path.join(HERE, "..", f"trades_{'tight' if st == 'zee100' else st}.json"), encoding="utf-8"))
    if st == "zee100":
        T = [t for t in T if 0.30 <= t["er16"] < 0.35]
    out = []
    for part, f in (("all", lambda t: True), ("train", lambda t: t["t_dec"] < SPLIT), ("test", lambda t: t["t_dec"] >= SPLIT)):
        S = [t for t in T if f(t)]
        p = np.clip(np.array([(t["trig_spread_pips"] + 0.1) / (abs(t["fill"] - t["stop"]) / P + 0.1) for t in S]), 0.0, 0.999)
        L = sum(1 for t in S if not t["win"])
        stops = sum(1 for t in S if not t["win"] and t["pnl"] < -100)
        p0 = float(np.exp(np.sum(np.log1p(-p))))
        out.append(f"{part}: n {len(S)} actual L {L} (stop-outs {stops}) expected {p.sum():.1f}  ratio {L / max(p.sum(), 1e-9):.2f}  P(0 L) {p0:.3f}")
    print(f"{st:7s} " + " | ".join(out))
# zee100 vs the rest of tight by the ER16 cut: how often would a random 300-trade slice of tight be loss-free?
T = json.load(open(os.path.join(HERE, "..", "trades_tight.json"), encoding="utf-8"))
er = np.array([t["er16"] for t in T]); w = np.array([t["win"] for t in T])
print("tight losses' ER16:", sorted(er[~w]), " zee100 n =", int(((er >= 0.30) & (er < 0.35)).sum()))
# probability that the lowest of 4 losses lands above the 0.35 cut if losses are spread like the trades (by ER rank):
q = float(np.mean(er >= 0.35))
print(f"share of tight trades with ER16 >= 0.35: {q:.3f}  -> P(all 4 losses there by chance) = {q**4:.3f}")
# hypergeometric-style: random 300 of 714 with 4 losses -> P(0 losses in the slice)
from math import comb
n, K, m = len(T), int((~w).sum()), int(((er >= 0.30) & (er < 0.35)).sum())
print(f"random slice of {m} of {n} trades with {K} losses: P(0 losses) = {comb(n - K, m) / comb(n, m):.3f}")
