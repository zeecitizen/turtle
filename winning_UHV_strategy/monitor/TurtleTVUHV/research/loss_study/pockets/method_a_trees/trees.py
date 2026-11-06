"""trees.py (pockets/method_a_trees) - METHOD A of Zee's risky-pocket study (2026-11-06: "10% risky trades zone -> here the angel only
cuts some of them ... 80% non-risky trades (no angel) -> there's no cut on these trades ... isolate the risky zones further by breaking
them down into chunks").
Shallow decision trees + a small boosted model, fit on TRAIN (Mar-Jun) only, look for small pockets (together <= ~20% of trades) that hold
most of the losses; TEST (Jul-Nov) is scored once, untouched.
  1. leave-one-month-out (Mar/Apr/May/Jun) CV inside train picks the tree's depth / min leaf / criterion / class weight by how much the
     picked leaves' loss share beats their trade share on the held-out month;
  2. the chosen trees are refit on all of train; their leaves (explicit conditions) are scored on train and test;
  3. sequential covering: depth-3 tree on what is left, best leaf by Wilson lower bound (lift >= 1.5, losses in >= 3 of 4 train months,
     <= 10% of trades), remove it, repeat up to a 20% union;
  4. xgboost (depth 2-3, eta 0.05, scale_pos_weight ~29): LOMO AUC picks the size; test AUC with bootstrap CI and a permutation null
     (100 refits on shuffled train labels); top-10% / top-20% score pockets;
  5. L2 logistic regression as an AUC sanity baseline.
Run (Git Bash): cd .../pockets && py method_a_trees/trees.py  -> report on stdout + method_a_trees/results.json
Python replay = HYPOTHESIS, NOT PROMOTED."""
import json
import math
import os
import sys
import warnings

import numpy as np
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

warnings.filterwarnings("ignore")
OUT = {"note": "Python replay = HYPOTHESIS, NOT PROMOTED", "features": C.FEATS}
Xtr, ytr, mtr = C.X[C.TR], C.Y[C.TR], C.MON[C.TR]
Xte, yte = C.X[C.TE], C.Y[C.TE]
NTR = len(ytr)
P0 = ytr.mean()
MB = {m: ytr[mtr == m].mean() for m in C.MONTHS_TR}


def line(title, s):
    print(f"  {title}")
    print("     " + C.fmt(s, "train"))
    print("     " + C.fmt(s, "test"))


print("=" * 150)
print(f"BASE  train {NTR} trades {ytr.sum()} L (WR {100 * (1 - P0):.2f}%) | test {len(yte)} trades {yte.sum()} L (WR {100 * (1 - yte.mean()):.2f}%)")
print(f"BAR   untouched zone at 99.3% WR: a 20% pocket must hold {C.need(0.2, 'train')}/{ytr.sum()} train L, {C.need(0.2, 'test')}/{yte.sum()} test L; "
      f"a 10% pocket {C.need(0.1, 'train')} / {C.need(0.1, 'test')}")
print(f"ANGEL approx keeps {C.ANGEL.sum()} trades / {C.Y[C.ANGEL].sum()} L of the base rows (engine: 714 / 4)")

# ---------------------------------------------------------------- 0. prior-knowledge reference pockets (market reason first)
print("=" * 150)
print("0. REFERENCE pockets with a prior market reason (rollover / abnormal spread are the tight setting's own guards; Friday pm = weekend risk)")
d = C.d
REF = {
    "rollover 16:45-17:45 NY": C.ROLL.values,
    "abnormal spread (spread_excess >= 0.45)": (d["spread_excess"] >= 0.45).values,
    "NY 16:00-17:59": ((d["ny_min_of_day"] >= 960) & (d["ny_min_of_day"] < 1080)).values,
    "Friday NY afternoon (weekday 4, NY >= 12:00)": ((d["weekday"] == 4) & (d["ny_min_of_day"] >= 720)).values,
    "Friday all day": (d["weekday"] == 4).values,
}
OUT["reference"] = {}
for k, m in REF.items():
    s = C.pstats(m)
    OUT["reference"][k] = s
    line(k, s)
ref_union = REF["NY 16:00-17:59"] | REF["abnormal spread (spread_excess >= 0.45)"] | REF["Friday NY afternoon (weekday 4, NY >= 12:00)"]
s = C.pstats(ref_union)
OUT["reference"]["UNION NY16-18 | abnormal spread | Friday pm"] = s
line("UNION  NY 16:00-17:59 | abnormal spread | Friday pm", s)

# ---------------------------------------------------------------- 1. LOMO CV over shallow trees
print("=" * 150)
print("1. TREE GRID - leave-one-month-out inside train; leaves picked on the fit months (desc loss rate, lift >= 1.2, union <= 20%)")


def pick(leaf, y, max_share=0.20, min_lift=1.2):
    n, p0 = len(y), y.mean()
    ids, cnt = np.unique(leaf, return_counts=True)
    st = sorted(((i, c, int(y[leaf == i].sum())) for i, c in zip(ids, cnt)), key=lambda s: -(s[2] / s[1]))
    chosen, cum = [], 0.0
    for i, c, L in st:
        if (L / c) / p0 < min_lift:
            break
        if cum + c / n > max_share + 1e-9:
            continue
        chosen.append(int(i)); cum += c / n
    return chosen


CW = {"balanced": "balanced", "w10": {0: 1, 1: 10}}
grid = []
for dep in (2, 3, 4):
    for mlf in (0.01, 0.02, 0.03):
        for crit in ("gini", "entropy"):
            for cwn in ("balanced", "w10"):
                capL = expL = capN = totN = totL = 0
                folds = {}
                for m in C.MONTHS_TR:
                    fit, ho = mtr != m, mtr == m
                    clf = DecisionTreeClassifier(max_depth=dep, min_samples_leaf=max(5, int(mlf * fit.sum())), criterion=crit,
                                                 class_weight=CW[cwn], random_state=0).fit(Xtr[fit], ytr[fit])
                    ch = pick(clf.apply(Xtr[fit]), ytr[fit])
                    inp = np.isin(clf.apply(Xtr[ho]), ch)
                    cL = int(ytr[ho][inp].sum())
                    capL += cL; capN += int(inp.sum()); totN += int(ho.sum()); totL += int(ytr[ho].sum())
                    expL += inp.sum() * ytr[ho].mean()
                    folds[m] = [int(inp.sum()), int(ho.sum()), cL, int(ytr[ho].sum())]
                grid.append(dict(depth=dep, min_leaf=mlf, crit=crit, cw=cwn, ho_share=round(capN / totN, 4), ho_capture=round(capL / totL, 4),
                                 ho_lift=round(capL / expL, 3) if expL else 0.0, folds=folds))
grid.sort(key=lambda g: -(g["ho_lift"] if 0.05 <= g["ho_share"] <= 0.25 else g["ho_lift"] - 9))
OUT["tree_grid"] = grid
for g in grid[:12]:
    print(f"   depth {g['depth']} min_leaf {g['min_leaf']:.2f} {g['crit']:7s} {g['cw']:8s} | held-out share {100 * g['ho_share']:5.1f}% "
          f"capture {100 * g['ho_capture']:5.1f}% lift {g['ho_lift']:.2f} | folds (in/n, Lin/L) " +
          " ".join(f"{m}:{v[0]}/{v[1]},{v[2]}/{v[3]}" for m, v in g["folds"].items()))
print("   ... worst 3:")
for g in grid[-3:]:
    print(f"   depth {g['depth']} min_leaf {g['min_leaf']:.2f} {g['crit']:7s} {g['cw']:8s} | held-out share {100 * g['ho_share']:5.1f}% "
          f"capture {100 * g['ho_capture']:5.1f}% lift {g['ho_lift']:.2f}")
lifts = np.array([g["ho_lift"] for g in grid])
print(f"   all {len(grid)} configs: held-out lift median {np.median(lifts):.2f}, IQR {np.percentile(lifts, 25):.2f}-{np.percentile(lifts, 75):.2f}")

# ---------------------------------------------------------------- 2. refit chosen trees on all train, read the leaves
print("=" * 150)
print("2. REFIT on all train - every leaf as an explicit condition, train vs test (pocket leaves = picked on train)")
OUT["trees"] = []
seen = set()
chosen_cfgs = []
for g in grid:
    key = (g["depth"], g["min_leaf"])
    if key in seen or not (0.05 <= g["ho_share"] <= 0.25):
        continue
    seen.add(key); chosen_cfgs.append(g)
    if len(chosen_cfgs) == 3:
        break
for g in chosen_cfgs:
    clf = DecisionTreeClassifier(max_depth=g["depth"], min_samples_leaf=max(5, int(g["min_leaf"] * NTR)), criterion=g["crit"],
                                 class_weight=CW[g["cw"]], random_state=0).fit(Xtr, ytr)
    leaf_all = clf.apply(C.X)
    ch = pick(clf.apply(Xtr), ytr)
    paths = C.leaf_paths(clf)
    print(f" TREE depth {g['depth']} min_leaf {g['min_leaf']} {g['crit']} {g['cw']} (LOMO held-out lift {g['ho_lift']})")
    rows = []
    for leaf, conds in paths.items():
        b = C.round_bounds(C.bounds(conds))
        m = C.bmask(b)
        mism = int((m != (leaf_all == leaf)).sum())
        s = C.pstats(m)
        rows.append(dict(leaf=int(leaf), cond=C.bstr(b), picked=leaf in ch, mismatch=mism, stats=s))
    rows.sort(key=lambda r: -r["stats"]["train"]["loss_rate"])
    for r in rows:
        tr_, te_ = r["stats"]["train"], r["stats"]["test"]
        print(f"   {'*' if r['picked'] else ' '} train {100 * tr_['share']:5.1f}% {tr_['L']:3d}L lift {tr_['lift']:4.2f} up {tr_['months_up']}/4 | "
              f"test {100 * te_['share']:5.1f}% {te_['L']:3d}L lift {te_['lift']:4.2f} p={te_['p_binom']:.3f} up {te_['months_up']}/5 | "
              f"{r['cond']}" + (f"  [MISMATCH {r['mismatch']}]" if r["mismatch"] else ""))
    pm = np.isin(leaf_all, ch)
    s = C.pstats(pm)
    line(f"   UNION of picked (*) leaves", s)
    OUT["trees"].append(dict(cfg={k: g[k] for k in ("depth", "min_leaf", "crit", "cw", "ho_lift", "ho_share", "ho_capture")},
                             leaves=rows, union=s, text=export_text(clf, feature_names=C.FEATS, decimals=3)))

# ---------------------------------------------------------------- 3. sequential covering
print("=" * 150)
print("3. SEQUENTIAL COVERING - depth-3 tree on the trades not yet covered; best leaf by Wilson lower bound with lift >= 1.5, losses in")
print("   >= 3 of 4 train months, <= 10% of train trades; remove it; repeat to a 20% union.")


def seq_cover(depth=3, mlf=0.02, crit="entropy", cw="balanced", min_lift=1.5, min_months=3, max_pocket=0.10, max_union=0.20):
    rem = np.ones(NTR, bool)
    pockets, cum = [], 0.0
    for _ in range(10):
        clf = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=max(5, int(mlf * NTR)), criterion=crit, class_weight=CW[cw],
                                     random_state=0).fit(Xtr[rem], ytr[rem])
        best = None
        for leaf, conds in C.leaf_paths(clf).items():
            b = C.round_bounds(C.bounds(conds))
            mt = C.bmask(b)[C.TR] & rem
            n_, L_ = int(mt.sum()), int(ytr[mt].sum())
            if n_ == 0 or L_ == 0:
                continue
            lift = (L_ / n_) / P0
            up = sum(1 for m in C.MONTHS_TR if (mt & (mtr == m)).sum() and ytr[mt & (mtr == m)].mean() > MB[m])
            if lift < min_lift or up < min_months or n_ / NTR > max_pocket or cum + n_ / NTR > max_union + 0.01:
                continue
            sc = C.wilson_lb(L_, n_)
            if best is None or sc > best[0]:
                best = (sc, b, n_, L_, lift, up)
        if best is None:
            break
        pockets.append(best[1]); rem &= ~C.bmask(best[1])[C.TR]; cum += best[2] / NTR
    return pockets


OUT["seq_cover"] = []
for depth, mlf, crit in ((3, 0.02, "entropy"), (3, 0.03, "entropy"), (2, 0.02, "entropy"), (3, 0.02, "gini")):
    P = seq_cover(depth, mlf, crit)
    print(f" COVER depth {depth} min_leaf {mlf} {crit}: {len(P)} pockets")
    un = np.zeros(len(C.d), bool)
    res = []
    for i, b in enumerate(P, 1):
        m = C.bmask(b)
        un |= m
        s = C.pstats(m)
        res.append(dict(cond=C.bstr(b), stats=s))
        line(f"P{i}: {C.bstr(b)}", s)
    s = C.pstats(un)
    line("UNION", s)
    OUT["seq_cover"].append(dict(cfg=dict(depth=depth, min_leaf=mlf, crit=crit), pockets=res, union=s))

# ---------------------------------------------------------------- 4. boosted model
print("=" * 150)
print("4. XGBOOST - LOMO AUC picks depth / trees; test AUC + bootstrap CI + permutation null; top-q score pockets")
SPW = float((ytr == 0).sum() / ytr.sum())


def xgbm(n, depth, seed=0):
    return xgb.XGBClassifier(n_estimators=n, max_depth=depth, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                             reg_lambda=1.0, scale_pos_weight=SPW, tree_method="hist", n_jobs=4, random_state=seed, eval_metric="auc",
                             verbosity=0)


NS = (25, 50, 100, 150, 200, 300, 400)
curve = {}
oof = {}
for depth in (2, 3):
    aucs = {n: [] for n in NS}
    oof[depth] = {n: np.zeros(NTR) for n in NS}
    for m in C.MONTHS_TR:
        fit, ho = mtr != m, mtr == m
        mdl = xgbm(max(NS), depth).fit(Xtr[fit], ytr[fit])
        for n in NS:
            p = mdl.predict_proba(Xtr[ho], iteration_range=(0, n))[:, 1]
            aucs[n].append(roc_auc_score(ytr[ho], p))
            oof[depth][n][ho] = p
    curve[depth] = {n: [round(float(np.mean(a)), 4)] + [round(float(x), 3) for x in a] for n, a in aucs.items()}
    print(f"   depth {depth}: " + "  ".join(f"n{n}: {v[0]:.3f} ({'/'.join(f'{x:.2f}' for x in v[1:])})" for n, v in curve[depth].items()))
OUT["xgb_lomo_auc"] = {str(k): {str(n): v for n, v in c.items()} for k, c in curve.items()}
bd, bn = max(((dd, n) for dd in curve for n in NS), key=lambda t: curve[t[0]][t[1]][0])
print(f"   chosen: depth {bd}, {bn} trees (LOMO mean AUC {curve[bd][bn][0]:.3f})")
final = xgbm(bn, bd).fit(Xtr, ytr)
pte = final.predict_proba(Xte)[:, 1]
ptr_in = final.predict_proba(Xtr)[:, 1]
auc_te = roc_auc_score(yte, pte)
rng = np.random.default_rng(7)
boots = []
idx = np.arange(len(yte))
for _ in range(2000):
    s_ = rng.choice(idx, len(idx), replace=True)
    if yte[s_].sum() == 0:
        continue
    boots.append(roc_auc_score(yte[s_], pte[s_]))
lo95, hi95 = np.percentile(boots, [2.5, 97.5])
null = []
for i in range(100):
    yp = rng.permutation(ytr)
    null.append(roc_auc_score(yte, xgbm(bn, bd, seed=i).fit(Xtr, yp).predict_proba(Xte)[:, 1]))
null = np.array(null)
p_perm = float((np.sum(null >= auc_te) + 1) / (len(null) + 1))
print(f"   TEST AUC {auc_te:.3f}  (bootstrap 95% CI {lo95:.3f}-{hi95:.3f}) | permutation null mean {null.mean():.3f}, 95th pct "
      f"{np.percentile(null, 95):.3f}, p = {p_perm:.3f} | train in-sample AUC {roc_auc_score(ytr, ptr_in):.3f}")
gain = final.get_booster().get_score(importance_type="gain")
gain = sorted(((C.FEATS[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k, v) for k, v in gain.items()), key=lambda t: -t[1])
tot = sum(v for _, v in gain)
print("   gain importance: " + ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in gain[:10]))
OUT["xgb"] = dict(depth=bd, n=bn, lomo_auc=curve[bd][bn][0], test_auc=round(auc_te, 4), test_auc_ci95=[round(lo95, 4), round(hi95, 4)],
                  perm_null_mean=round(float(null.mean()), 4), perm_null_p95=round(float(np.percentile(null, 95)), 4), perm_p=round(p_perm, 4),
                  train_in_sample_auc=round(roc_auc_score(ytr, ptr_in), 4), gain=[(k, round(100 * v / tot, 1)) for k, v in gain])
OUT["xgb"]["top_q"] = {}
for q in (0.10, 0.20):
    thr_te = np.quantile(pte, 1 - q)
    m_te = np.zeros(len(C.d), bool); m_te[np.where(C.TE)[0][pte >= thr_te]] = True
    # train side: out-of-fold scores, top q within each held-out month (fair, no in-sample)
    m_tr = np.zeros(len(C.d), bool)
    po = oof[bd][bn]
    tri = np.where(C.TR)[0]
    for mo in C.MONTHS_TR:
        k = mtr == mo
        thr = np.quantile(po[k], 1 - q)
        m_tr[tri[k & (po >= thr)]] = True
    s = C.pstats(m_tr | m_te)
    OUT["xgb"]["top_q"][str(q)] = s
    line(f"top {int(100 * q)}% boosted score (train = out-of-fold by month, test = label-free top-q of the final model)", s)

# ---------------------------------------------------------------- 5. logistic baseline
lr_ = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, class_weight="balanced", max_iter=5000)).fit(Xtr, ytr)
auc_lr = roc_auc_score(yte, lr_.predict_proba(Xte)[:, 1])
lomo_lr = []
for m in C.MONTHS_TR:
    fit, ho = mtr != m, mtr == m
    mm = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, class_weight="balanced", max_iter=5000)).fit(Xtr[fit], ytr[fit])
    lomo_lr.append(roc_auc_score(ytr[ho], mm.predict_proba(Xtr[ho])[:, 1]))
print(f"5. LOGISTIC (L2, C=0.05) LOMO AUC {np.mean(lomo_lr):.3f} ({'/'.join(f'{a:.2f}' for a in lomo_lr)}) | TEST AUC {auc_lr:.3f}")
OUT["logistic"] = dict(lomo_auc=round(float(np.mean(lomo_lr)), 4), lomo_folds=[round(a, 3) for a in lomo_lr], test_auc=round(auc_lr, 4))

json.dump(OUT, open(os.path.join(C.HERE, "results.json"), "w", encoding="utf-8"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("wrote", os.path.join(C.HERE, "results.json"))
