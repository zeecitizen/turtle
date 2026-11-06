"""final.py (pockets/method_a_trees) - METHOD A summary for Zee's risky-pocket study (2026-11-06).
1. BLIND table: every train-chosen Method A protocol (trees.py / trees2.py unions, themed trees, boosted top-q) with its TEST result, so
   the honest range is visible (no protocol was picked by its test number).
2. The CANDIDATE pocket set: the tree-found pockets that held (abnormal spread, counter-trend chop with a weak breakout, NY afternoon on
   thin volume) plus two reference pockets with a prior market reason (NY close / rollover hour, Friday afternoon). NOTE: which tree pockets
   "held" was read off TEST, so this union's test numbers are optimistic; the blind table is the honest bound.
Each pocket: train and test share, losses in it, loss rate, lift, binomial p, loss-days, untouched WR when skipped, WR with the angel
filtering only inside it.  Run (Git Bash): cd .../pockets && py method_a_trees/final.py  -> stdout + method_a_trees/final.json
Python replay = HYPOTHESIS, NOT PROMOTED."""
import json
import os
import sys
import warnings

import numpy as np
import xgboost as xgb
from sklearn.metrics import roc_auc_score

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

warnings.filterwarnings("ignore")
d, Y, TR, TE = C.d, C.Y, C.TR, C.TE
R1 = json.load(open(os.path.join(C.HERE, "results.json"), encoding="utf-8"))
R2 = json.load(open(os.path.join(C.HERE, "results2.json"), encoding="utf-8"))
OUT = {"note": "Python replay = HYPOTHESIS, NOT PROMOTED"}


def short(s):
    a, b = s["train"], s["test"]
    return (f"train {100 * a['share']:5.1f}% trades {100 * a['L_share']:4.0f}% L (lift {a['lift']:.2f}) | test {100 * b['share']:5.1f}% trades "
            f"{100 * b['L_share']:4.0f}% L (lift {b['lift']:.2f}, p={b['p_binom']:.3f}) untouched WR {b['wr_untouched']:.2f}%")


print("=" * 150)
print(f"BASE train WR {100 * (1 - Y[TR].mean()):.2f}% ({Y[TR].sum()} L / {TR.sum()}) | test WR {100 * (1 - Y[TE].mean()):.2f}% ({Y[TE].sum()} L / {TE.sum()})")
print(f"BAR  99.3% untouched: a 20% pocket set must hold {C.need(0.2, 'train')}/{Y[TR].sum()} train L (84%) and {C.need(0.2, 'test')}/{Y[TE].sum()} test L (60%)")
print("=" * 150)
print("1. BLIND - every train-chosen Method A protocol, test scored once")
blind = {}
for t in R1["trees"]:
    c = t["cfg"]
    blind[f"raw tree d{c['depth']} {c['min_leaf']} {c['crit']} {c['cw']} (LOMO lift {c['ho_lift']})"] = t["union"]
for t in R2["sf_trees"]:
    c = t["cfg"]
    blind[f"scale-free tree d{c['depth']} {c['min_leaf']} {c['crit']} {c['w']} (LOMO lift {c['ho_lift']})"] = t["union"]
for k, v in R2["cover"].items():
    if v["pockets"]:
        blind[f"covering {k} ({len(v['pockets'])} pockets)"] = v["union"]
for k, v in R2["themes_res"].items():
    blind[f"themed tree '{k}'"] = v["union"]
for q, s in R1["xgb"]["top_q"].items():
    blind[f"xgb raw top {int(100 * float(q))}% (test AUC {R1['xgb']['test_auc']})"] = s

# scale-free month-balanced xgb top-q (same model as trees2.py: depth/n chosen there by LOMO)
SF = R2["scale_free_features"]
xb = R2["xgb_sf_mbal"]
Xtr, Xte = d.loc[TR, SF].values.astype(float), d.loc[TE, SF].values.astype(float)
ytr, mtr = Y[TR], C.MON[TR]
w = np.ones(len(ytr))
for m in np.unique(mtr):
    k = mtr == m
    w[k & (ytr == 1)] = (k.sum() - ytr[k].sum()) / ytr[k].sum()
mdl = xgb.XGBClassifier(n_estimators=xb["n"], max_depth=xb["depth"], learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                        min_child_weight=5, reg_lambda=1.0, tree_method="hist", n_jobs=4, random_state=0, verbosity=0).fit(Xtr, ytr, sample_weight=w)
pte = mdl.predict_proba(Xte)[:, 1]
assert abs(roc_auc_score(Y[TE], pte) - xb["test_auc"]) < 1e-3, "xgb refit differs from trees2.py"
oof = np.zeros(len(ytr))                       # train side: each month scored by the model fit on the other three months
for m in C.MONTHS_TR:
    fit, ho = mtr != m, mtr == m
    wf = np.ones(int(fit.sum()))
    for mm in np.unique(mtr[fit]):
        k = mtr[fit] == mm
        wf[k & (ytr[fit] == 1)] = (k.sum() - ytr[fit][k].sum()) / ytr[fit][k].sum()
    fm = xgb.XGBClassifier(n_estimators=xb["n"], max_depth=xb["depth"], learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                           min_child_weight=5, reg_lambda=1.0, tree_method="hist", n_jobs=4, random_state=0, verbosity=0)
    oof[ho] = fm.fit(Xtr[fit], ytr[fit], sample_weight=wf).predict_proba(Xtr[ho])[:, 1]
tri = np.where(TR)[0]
for q in (0.10, 0.20):
    m_te = np.zeros(len(d), bool)
    m_te[np.where(TE)[0][pte >= np.quantile(pte, 1 - q)]] = True
    for m in C.MONTHS_TR:
        k = mtr == m
        m_te[tri[k & (oof >= np.quantile(oof[k], 1 - q))]] = True
    s = C.pstats(m_te)
    blind[f"xgb scale-free month-balanced top {int(100 * q)}% (test AUC {xb['test_auc']}; train = out-of-fold by month)"] = s
for k, s in blind.items():
    print(f"   {k:90s} {short(s)}")
caps = [(s["test"]["share"], s["test"]["L_share"]) for s in blind.values() if 0.08 <= s["test"]["share"] <= 0.22]
print(f"   -> at 8-22% of test trades the blind protocols hold {100 * min(c for _, c in caps):.0f}-{100 * max(c for _, c in caps):.0f}% of test losses "
      f"(median {100 * float(np.median([c for _, c in caps])):.0f}%); the bar needs ~60%")
OUT["blind"] = blind

print("=" * 150)
print("2. CANDIDATE pocket set (tree-found ones that held + market-prior references). Test is optimistic: 'held' was read off test.")
P = {
    "abnormal_spread": dict(cond="spread_excess > 0.275  (breakout spread > 0.275 pip above the median of the previous 50 trades)",
                            mask=(d["spread_excess"] > 0.275).values, origin="tree-found (liquidity theme root; raw depth-4 tree root)"),
    "ny_close_hour": dict(cond="16:00 <= New York time < 18:00  (ny_min_of_day 960-1079)",
                          mask=((d["ny_min_of_day"] >= 960) & (d["ny_min_of_day"] < 1080)).values,
                          origin="reference, market prior (the tight setting already guards 16:45-17:45)"),
    "friday_pm": dict(cond="weekday == 4 and New York time >= 12:00", mask=((d["weekday"] == 4) & (d["ny_min_of_day"] >= 720)).values,
                      origin="reference, market prior (Friday lift 1.7x on train alone)"),
    "countertrend_chop_weak_break": dict(cond="trend30_atr <= -1.905 and er30 <= 0.2065 and brk_ratio <= 0.5055",
                                         mask=((d["trend30_atr"] <= -1.905) & (d["er30"] <= 0.2065) & (d["brk_ratio"] <= 0.5055)).values,
                                         origin="tree-found (sequential covering, scale-free, month-balanced)"),
    "ny_afternoon_thin_volume": dict(cond="ny_min_of_day >= 870 and vol10_rel <= 0.8805 and atr_rel > 0.7715  (after 14:30 NY, 10-bar volume "
                                          "< 0.88x its 300-trade median, ATR not unusually low)",
                                     mask=((d["ny_min_of_day"] >= 870) & (d["vol10_rel"] <= 0.8805) & (d["atr_rel"] > 0.7715)).values,
                                     origin="tree-found (scale-free depth-4 gini tree leaf + gini covering)"),
}
un = np.zeros(len(d), bool)
OUT["candidates"] = {}
for k, p in P.items():
    s = C.pstats(p["mask"])
    un |= p["mask"]
    OUT["candidates"][k] = dict(cond=p["cond"], origin=p["origin"], stats=s)
    print(f"  {k}: {p['cond']}   [{p['origin']}]  angel keeps inside: train {s['train']['angel_kept_in_pocket']}, test {s['test']['angel_kept_in_pocket']}")
    print("     " + C.fmt(s, "train"))
    print("     " + C.fmt(s, "test"))
s = C.pstats(un)
OUT["candidates_union"] = s
print("  UNION of the 5")
print("     " + C.fmt(s, "train"))
print("     " + C.fmt(s, "test"))
tree_only = P["abnormal_spread"]["mask"] | P["countertrend_chop_weak_break"]["mask"] | P["ny_afternoon_thin_volume"]["mask"]
s3 = C.pstats(tree_only)
OUT["tree_found_union"] = s3
print("  UNION of the 3 tree-found pockets only")
print("     " + C.fmt(s3, "train"))
print("     " + C.fmt(s3, "test"))
print("  loss overlap (test losses shared by two pockets):")
keys = list(P)
for i in range(len(keys)):
    for j in range(i + 1, len(keys)):
        a, b = P[keys[i]]["mask"], P[keys[j]]["mask"]
        both = int((a & b & TE & (Y == 1)).sum())
        if both:
            print(f"     {keys[i]} & {keys[j]}: {both} test L, {int((a & b & TR & (Y == 1)).sum())} train L")
for h, H in (("train", TR), ("test", TE)):
    n, L = int(H.sum()), int(Y[H].sum())
    nu = int((un & H).sum()); Lu = int(Y[un & H].sum())
    print(f"  {h}: untouched zone {n - nu} trades / {L - Lu} L = loss rate {100 * (L - Lu) / (n - nu):.2f}%; 99.3% would allow "
          f"{int(0.007 * (n - nu))} L -> {L - Lu - int(0.007 * (n - nu))} losses too many")
json.dump(OUT, open(os.path.join(C.HERE, "final.json"), "w", encoding="utf-8"), indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("wrote", os.path.join(C.HERE, "final.json"))
