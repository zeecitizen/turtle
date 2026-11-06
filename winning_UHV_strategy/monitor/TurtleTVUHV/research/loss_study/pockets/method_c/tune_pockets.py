"""tune_pockets.py - METHOD C (loss-cluster profiling, domain-led), step 2: one interpretable pocket per loss-cause cluster, cut points tuned
on TRAIN ONLY (Mar-Jun). This script never reads a test row: the CSV is filtered to half == 'train' at load.

Each cluster gets 1-3 small families of 1-2 conditions on features with a market reason (chosen from profile_clusters.py + the loss
comments), searched on coarse natural grids (NY clock in 15-min steps around market anchors, whole ATRs, integer humps, 0.1-pip ATR ...).
Score = ALL train losses in the pocket - 3.5 x base_train x trades in the pocket  (the angel cuts every loss in a pocket, so all losses
count; a cut is only worth it where its marginal loss rate is >= 3.5x the base = the lift the 99.3% bar needs). A pocket is VIABLE when
score > 0, >= 5 train losses and >= 4 distinct loss days (one bad afternoon is not a pocket).
Output: chosen_pockets.json (frozen; evaluate_pockets.py applies it to both halves), tune_pockets.txt. Python = HYPOTHESIS, NOT PROMOTED."""
import csv, itertools, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pocket_defs import FAMILIES, CLUSTERS, mask_of, describe  # noqa: E402

ROWS = [r for r in csv.DictReader(open(os.path.join(HERE, "..", "features.csv"), encoding="utf-8")) if r["half"] == "train"]
CAUSE = json.load(open(os.path.join(HERE, "causes_by_id.json")))
FEATS = [k for k in ROWS[0] if k not in ("id", "win", "pnl", "half")]
A = {f: np.array([float(r[f]) for r in ROWS]) for f in FEATS}
loss = np.array([r["win"] == "0" for r in ROWS])
cause = np.array([CAUSE.get(r["id"], "") for r in ROWS])
day = np.array([r["id"][:4] for r in ROWS])
MULT = float(sys.argv[1]) if len(sys.argv) > 1 else 3.5          # marginal-lift bar (3.5 = the 99.3% bar; 2.0 = relaxed sensitivity)
TAG = "" if MULT == 3.5 else f"_x{MULT:g}"
N, L = len(ROWS), int(loss.sum()); BASE = L / N; LAM = MULT * BASE
out = []
def say(s=""):
    print(s); out.append(s)

say(f"TRAIN ONLY: {N} trades, {L} losses, base loss rate {100*BASE:.2f}%  -> score = L_in - {LAM:.4f} x N_in (marginal lift >= {MULT:g}x)")
chosen = {}
for cl in CLUSTERS:
    ncl = int((loss & (cause == cl)).sum())
    say(f"\n=== {cl}: {ncl} train losses of this cause ===")
    cands = []
    for fam in FAMILIES[cl]:
        keys = list(fam["grid"])
        for vals in itertools.product(*(fam["grid"][k] for k in keys)):
            p = dict(zip(keys, vals))
            m = mask_of(fam["name"], p, A)
            n = int(m.sum())
            if n == 0:
                continue
            l = int((m & loss).sum()); lc = int((m & loss & (cause == cl)).sum()); nd = len(set(day[m & loss]))
            sc = l - LAM * n
            ok = (l >= 5) and (nd >= 4) and sc > 0
            cands.append({"family": fam["name"], "params": p, "n": n, "l": l, "lc": lc, "days": nd, "score": round(sc, 3), "viable": ok,
                          "nconds": fam["nconds"]})
    elig = [c for c in cands if c["l"] >= 5 and c["days"] >= 4]
    elig.sort(key=lambda c: (-c["score"], c["nconds"], c["n"]))
    for c in elig[:8]:
        say(f"   {'VIABLE ' if c['viable'] else 'no     '} score {c['score']:6.2f}  N {c['n']:4d} ({100*c['n']/N:4.1f}%)  L {c['l']:3d} "
            f"(own cause {c['lc']:2d}/{ncl})  rate {100*c['l']/c['n']:5.1f}%  lift x{c['l']/c['n']/BASE:4.2f}  days {c['days']:2d}  "
            f"{describe(c['family'], c['params'])}")
    fb = {}
    for c in elig:
        if c["family"] not in fb:
            fb[c["family"]] = c
    say("   best per family: " + " | ".join(f"{k} {v['score']:.2f} (N {v['n']}, L {v['l']})" for k, v in fb.items()))
    if not elig:
        say("   no configuration reaches 5 losses on 4 days"); continue
    best = elig[0]
    # plateau: configs of the same family within 80% of the best score (a lone spike = fitted noise)
    near = [c for c in elig if c["family"] == best["family"] and c["score"] >= 0.8 * best["score"]] if best["score"] > 0 else []
    say(f"   -> chosen: {describe(best['family'], best['params'])}  [{'VIABLE' if best['viable'] else 'NOT VIABLE (score <= 0)'}]"
        f"  plateau: {len(near)} same-family configs within 80% of the best score")
    chosen[cl] = dict(best, plateau=len(near), own_cause_train=ncl)
json.dump({"base_train": BASE, "lift_bar": MULT, "lambda": LAM, "pockets": chosen}, open(os.path.join(HERE, f"chosen_pockets{TAG}.json"), "w"), indent=1)
open(os.path.join(HERE, f"tune_pockets{TAG}.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
