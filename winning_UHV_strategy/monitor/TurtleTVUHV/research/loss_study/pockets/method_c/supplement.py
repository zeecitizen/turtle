"""supplement.py - METHOD C context for 'how close can pockets get':
 (a) the session-edge core alone (weekly-close + rollover pockets, the only two that held on test), train and test;
 (b) a CEILING check, not a pocket: a flexible model (sklearn gradient boosting) fitted on TRAIN with all 32 decision-time features,
     scored on TEST - if even this cannot pack the test losses into its riskiest 10-20% of trades, no 1-2-condition pocket can.
     Train numbers for (b) come from day-blocked 5-fold cross-validation inside train (never the fitted-on rows).
Python engine outcomes = HYPOTHESIS, NOT PROMOTED."""
import csv, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pocket_defs import mask_of, describe  # noqa: E402

ROWS = list(csv.DictReader(open(os.path.join(HERE, "..", "features.csv"), encoding="utf-8")))
FEATS = [k for k in ROWS[0] if k not in ("id", "win", "pnl", "half")]
A = {f: np.array([float(r[f]) for r in ROWS]) for f in FEATS}
X = np.column_stack([A[f] for f in FEATS])
y = np.array([r["win"] == "0" for r in ROWS]).astype(int)
tr = np.array([r["half"] == "train" for r in ROWS]); te = ~tr
day = np.array([r["id"][:4] for r in ROWS])
P = json.load(open(os.path.join(HERE, "chosen_pockets.json")))["pockets"]
out = []


def say(s=""):
    print(s); out.append(s)


def line(m, h, nm):
    N, L = int(h.sum()), int(y[h].sum()); n, l = int((m & h).sum()), int(y[m & h].sum())
    say(f"   {nm:5s}: {100*n/N:4.1f}% of trades ({n}), {l}/{L} losses = {100*l/L:4.1f}%, loss rate {100*l/max(n,1):5.2f}% "
        f"(lift x{(l/max(n,1))/(L/N):.2f}), untouched WR {100*(1-(L-l)/(N-n)):.2f}% (base {100*(1-L/N):.2f}%)")


say("(a) session-edge core = weekly_close OR rollover_dead_book")
core = mask_of(P["weekly_close"]["family"], P["weekly_close"]["params"], A) | \
    mask_of(P["rollover_dead_book"]["family"], P["rollover_dead_book"]["params"], A)
say(f"   {describe(P['weekly_close']['family'], P['weekly_close']['params'])}  OR  "
    f"{describe(P['rollover_dead_book']['family'], P['rollover_dead_book']['params'])}")
line(core, tr, "train"); line(core, te, "test")

say("\n(b) CEILING check: gradient boosting on all 32 features (fit on train; train = day-blocked 5-fold CV, test = untouched)")
try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
except ImportError as e:
    say(f"   sklearn missing: {e}"); sys.exit(0)


def model():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=40,
                                          l2_regularization=1.0, random_state=7)


# day-blocked CV inside train
tri = np.where(tr)[0]; udays = np.array(sorted(set(day[tri])))
rng = np.random.default_rng(7); fold_of_day = dict(zip(udays, rng.permutation(len(udays)) % 5))
fold = np.array([fold_of_day[d] for d in day[tri]])
oof = np.zeros(len(tri))
for k in range(5):
    fit, hold = fold != k, fold == k
    oof[hold] = model().fit(X[tri[fit]], y[tri[fit]]).predict_proba(X[tri[hold]])[:, 1]
m = model().fit(X[tr], y[tr]); pte = m.predict_proba(X[te])[:, 1]
say(f"   AUC train (out-of-fold) {roc_auc_score(y[tr], oof):.3f}   AUC test {roc_auc_score(y[te], pte):.3f}   (0.5 = no skill)")
for nm, score, yy in (("train", oof, y[tr]), ("test", pte, y[te])):
    order = np.argsort(-score); N, L = len(yy), int(yy.sum())
    cells = []
    for sh in (0.05, 0.10, 0.15, 0.20):
        k = int(round(sh * N)); l = int(yy[order[:k]].sum())
        cells.append(f"top {int(sh*100)}%: {l}/{L} losses ({100*l/L:.0f}%), untouched WR {100*(1-(L-l)/(N-k)):.2f}%")
    say(f"   {nm:5s}: " + " | ".join(cells))
say("   (the 99.3% bar on test needs ~33-35 of 60 test losses inside a 10-20% pocket)")
open(os.path.join(HERE, "supplement.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")
