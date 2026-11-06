"""trees2.py (pockets/method_a_trees) - METHOD A, second pass, after trees.py showed the first-pass trees learn the Mar-May regime:
  (a) SCALE-FREE features: absolute levels that drift between the halves (atr_pips, vol10, uhv_v, pip distances) are replaced by ratios that
      are still decision-time: stop/room/gap/figure distance in ATRs, uhv_v / vol10, and atr / vol10 against the median of the previous
      300 trades (atr_rel, vol10_rel); spread_excess as in common.py;
  (b) MONTH-BALANCED weights: in every month the losses weigh as much as the wins, so a tree cannot score by isolating the 4%-loss Mar-May
      regime; it has to find trades that are riskier than their own month;
  (c) SEQUENTIAL COVERING over every node of a depth-3 tree (not only leaves): best node by the Poisson lower bound of its month-adjusted
      lift, with lift >= 1.5, losses in >= 3 of 4 train months, <= 10% of train trades; remove it; repeat to a 20% union;
  (d) THEMED shallow trees (calendar / liquidity / trend / setup), so every pocket reads as one market idea.
Everything is chosen on TRAIN (leave-one-month-out inside Mar-Jun); TEST (Jul-Nov) is scored once.
Run (Git Bash): cd .../pockets && py method_a_trees/trees2.py  -> stdout + method_a_trees/results2.json
Python replay = HYPOTHESIS, NOT PROMOTED."""
import json
import os
import sys
import warnings

import numpy as np
import xgboost as xgb
from scipy.stats import chi2
from sklearn.metrics import roc_auc_score
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

warnings.filterwarnings("ignore")
d = C.d   # scale-free columns are added in common.add_scale_free
SF = ["side", "humps", "er8", "er16", "er30", "er60", "adx", "trend30_atr", "trend90_atr", "trend240_atr", "ny_hour", "ny_min_of_day",
      "weekday", "spread_excess", "brk_ratio", "uhv_rel", "stop_atr", "bars_since_uhv", "box", "room60_atr", "room240_atr", "pos60",
      "range20_atr", "range60_atr", "struct_with", "uhv_body", "last_body_dir", "fig_ahead_atr", "vol_ratio10_60", "gap_atr", "atr_rel",
      "vol10_rel"]
THEMES = {
    "calendar": ["ny_min_of_day", "weekday"],
    "liquidity": ["spread_excess", "gap_atr", "vol10_rel", "vol_ratio10_60", "brk_ratio", "uhv_rel"],
    "trend": ["er8", "er16", "er30", "er60", "adx", "trend30_atr", "trend90_atr", "trend240_atr", "struct_with", "humps", "range20_atr",
              "range60_atr", "pos60", "box", "room60_atr", "room240_atr", "atr_rel"],
    "setup": ["side", "uhv_body", "last_body_dir", "bars_since_uhv", "stop_atr", "fig_ahead_atr"],
}
Y, MON, TR, TE = C.Y, C.MON, C.TR, C.TE
ytr, mtr = Y[TR], MON[TR]
NTR = int(TR.sum())
P0 = ytr.mean()
MB = {m: ytr[mtr == m].mean() for m in C.MONTHS_TR}
OUT = {"note": "Python replay = HYPOTHESIS, NOT PROMOTED", "scale_free_features": SF, "themes": THEMES}


def mbal_weights(y, mon):
    w = np.ones(len(y))
    for m in np.unique(mon):
        k = mon == m
        L = y[k].sum()
        if L:
            w[k & (y == 1)] = (k.sum() - L) / L
    return w


def fit_tree(Xf, yf, mf, depth, mlf, crit, wmode):
    clf = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=max(5, int(mlf * len(yf))), criterion=crit, random_state=0,
                                 class_weight="balanced" if wmode == "balanced" else None)
    return clf.fit(Xf, yf, sample_weight=mbal_weights(yf, mf) if wmode == "mbal" else None)


def pick(leaf, y, mon, max_share=0.20, min_lift=1.2):
    """leaves in order of month-adjusted lift on the fit set, lift >= min_lift, union <= max_share."""
    n = len(y)
    base = {m: y[mon == m].mean() for m in np.unique(mon)}
    exp_i = np.array([base[m] for m in mon])
    st = []
    for i in np.unique(leaf):
        k = leaf == i
        st.append((int(i), int(k.sum()), int(y[k].sum()), y[k].sum() / max(exp_i[k].sum(), 1e-9)))
    st.sort(key=lambda s: -s[3])
    chosen, cum = [], 0.0
    for i, c, L, lift in st:
        if lift < min_lift:
            break
        if cum + c / n > max_share + 1e-9:
            continue
        chosen.append(i); cum += c / n
    return chosen


def lomo_grid(feats, depths=(2, 3, 4), mlfs=(0.01, 0.02, 0.03), crits=("gini", "entropy"), wmodes=("balanced", "mbal")):
    Xtr = d.loc[TR, feats].values.astype(float)
    res = []
    for dep in depths:
        for mlf in mlfs:
            for crit in crits:
                for wm in wmodes:
                    capL = expL = capN = totN = totL = 0
                    for m in C.MONTHS_TR:
                        fit, ho = mtr != m, mtr == m
                        clf = fit_tree(Xtr[fit], ytr[fit], mtr[fit], dep, mlf, crit, wm)
                        ch = pick(clf.apply(Xtr[fit]), ytr[fit], mtr[fit])
                        inp = np.isin(clf.apply(Xtr[ho]), ch)
                        capL += int(ytr[ho][inp].sum()); capN += int(inp.sum()); totN += int(ho.sum()); totL += int(ytr[ho].sum())
                        expL += inp.sum() * ytr[ho].mean()
                    res.append(dict(depth=dep, min_leaf=mlf, crit=crit, w=wm, ho_share=round(capN / totN, 4),
                                    ho_capture=round(capL / totL, 4), ho_lift=round(capL / expL, 3) if expL else 0.0))
    res.sort(key=lambda g: -(g["ho_lift"] if 0.03 <= g["ho_share"] <= 0.25 else g["ho_lift"] - 9))
    return res


def leaves_report(feats, g, label, show=True):
    Xtr = d.loc[TR, feats].values.astype(float)
    Xall = d[feats].values.astype(float)
    clf = fit_tree(Xtr, ytr, mtr, g["depth"], g["min_leaf"], g["crit"], g["w"])
    leaf_all = clf.apply(Xall)
    ch = pick(clf.apply(Xtr), ytr, mtr)
    rows = []
    for leaf, conds in C.leaf_paths(clf, feats).items():
        b = C.round_bounds(C.bounds(conds))
        m = C.bmask(b)
        rows.append(dict(cond=C.bstr(b), picked=leaf in ch, mismatch=int((m != (leaf_all == leaf)).sum()), stats=C.pstats(m)))
    rows.sort(key=lambda r: -r["stats"]["train"]["lift_month_adj"])
    if show:
        print(f" {label}: depth {g['depth']} min_leaf {g['min_leaf']} {g['crit']} {g['w']} | LOMO held-out share {100 * g['ho_share']:.1f}% "
              f"capture {100 * g['ho_capture']:.1f}% lift {g['ho_lift']:.2f}")
        for r in rows:
            a, b_ = r["stats"]["train"], r["stats"]["test"]
            if not r["picked"] and a["lift_month_adj"] < 1.0:
                continue
            print(f"   {'*' if r['picked'] else ' '} train {100 * a['share']:5.1f}% {a['L']:3d}L m-adj lift {a['lift_month_adj']:4.2f} up {a['months_up']}/4 | "
                  f"test {100 * b_['share']:5.1f}% {b_['L']:3d}L lift {b_['lift']:4.2f} p={b_['p_binom']:.3f} up {b_['months_up']}/5 | {r['cond']}"
                  + (f" [MISMATCH {r['mismatch']}]" if r["mismatch"] else ""))
    pm = np.isin(leaf_all, ch)
    s = C.pstats(pm)
    if show:
        print("     UNION picked  " + C.fmt(s, "train"))
        print("                   " + C.fmt(s, "test"))
    return dict(cfg=g, leaves=rows, union=s, mask=pm)


def node_paths(clf, feats):
    t = clf.tree_
    paths = {}

    def rec(node, conds):
        paths[node] = conds
        if t.children_left[node] != -1:
            f, thr = feats[t.feature[node]], float(t.threshold[node])
            rec(t.children_left[node], conds + [(f, "<=", thr)])
            rec(t.children_right[node], conds + [(f, ">", thr)])

    rec(0, [])
    return paths


def seq_cover(feats, depth=3, mlf=0.02, crit="entropy", wmode="mbal", min_lift=1.5, min_months=3, max_pocket=0.10, max_union=0.20):
    Xtr = d.loc[TR, feats].values.astype(float)
    rem = np.ones(NTR, bool)
    exp_i = np.array([MB[m] for m in mtr])
    pockets, cum = [], 0.0
    for _ in range(12):
        clf = fit_tree(Xtr[rem], ytr[rem], mtr[rem], depth, mlf, crit, wmode)
        best = None
        for node, conds in node_paths(clf, feats).items():
            if node == 0:
                continue
            b = C.round_bounds(C.bounds(conds))
            mt = C.bmask(b)[TR] & rem
            n_, L_ = int(mt.sum()), int(ytr[mt].sum())
            if n_ == 0 or L_ == 0:
                continue
            E = exp_i[mt].sum()
            lift = L_ / E
            up = sum(1 for m in C.MONTHS_TR if (mt & (mtr == m)).sum() and ytr[mt & (mtr == m)].mean() > MB[m])
            if lift < min_lift or up < min_months or n_ / NTR > max_pocket or cum + n_ / NTR > max_union + 0.01:
                continue
            sc = (chi2.ppf(0.05, 2 * L_) / 2) / E        # Poisson 95% lower bound of the month-adjusted lift
            if best is None or sc > best[0]:
                best = (sc, b, n_)
        if best is None:
            break
        pockets.append(best[1]); rem &= ~C.bmask(best[1])[TR]; cum += best[2] / NTR
    return pockets


def show_cover(label, P):
    print(f" {label}: {len(P)} pockets")
    un = np.zeros(len(d), bool)
    res = []
    for i, b in enumerate(P, 1):
        m = C.bmask(b)
        un |= m
        s = C.pstats(m)
        res.append(dict(cond=C.bstr(b), stats=s))
        print(f"   P{i}: {C.bstr(b)}")
        print("       " + C.fmt(s, "train"))
        print("       " + C.fmt(s, "test"))
    s = C.pstats(un)
    print("   UNION " + C.fmt(s, "train"))
    print("         " + C.fmt(s, "test"))
    return dict(pockets=res, union=s, mask=un)


# ------------------------------------------------------------------------------------------------ (a)+(b) full scale-free trees
print("=" * 150)
print("A. SCALE-FREE feature trees, LOMO grid over depth / min leaf / criterion / weights (balanced vs month-balanced)")
G = lomo_grid(SF)
OUT["sf_grid"] = G
for g in G[:8]:
    print(f"   depth {g['depth']} min_leaf {g['min_leaf']:.2f} {g['crit']:7s} {g['w']:8s} | held-out share {100 * g['ho_share']:5.1f}% "
          f"capture {100 * g['ho_capture']:5.1f}% lift {g['ho_lift']:.2f}")
lifts = np.array([g["ho_lift"] for g in G])
print(f"   all {len(G)} configs: held-out lift median {np.median(lifts):.2f}, IQR {np.percentile(lifts, 25):.2f}-{np.percentile(lifts, 75):.2f}")
OUT["sf_trees"] = []
seen = set()
for g in G:
    if (g["depth"], g["w"]) in seen or not (0.03 <= g["ho_share"] <= 0.25):
        continue
    seen.add((g["depth"], g["w"]))
    r = leaves_report(SF, g, "SF TREE")
    r.pop("mask")
    OUT["sf_trees"].append(r)
    if len(seen) == 3:
        break

# ------------------------------------------------------------------------------------------------ (c) sequential covering
print("=" * 150)
print("C. SEQUENTIAL COVERING over all nodes (Poisson lower bound of month-adjusted lift; >= 1.5x, >= 3/4 months, <= 10% each, <= 20% union)")
OUT["cover"] = {}
COVERS = {}
for lab, feats, dep, mlf, crit, wm in (("SF d3 2% entropy mbal", SF, 3, 0.02, "entropy", "mbal"),
                                       ("SF d3 3% entropy mbal", SF, 3, 0.03, "entropy", "mbal"),
                                       ("SF d3 2% gini balanced", SF, 3, 0.02, "gini", "balanced"),
                                       ("RAW d3 2% entropy mbal", C.FEATS, 3, 0.02, "entropy", "mbal")):
    r = show_cover(lab, seq_cover(feats, dep, mlf, crit, wm))
    COVERS[lab] = r.pop("mask")
    OUT["cover"][lab] = r

# ------------------------------------------------------------------------------------------------ (d) themed trees
print("=" * 150)
print("D. THEMED shallow trees (month-balanced weights), LOMO over depth 1-3 x min leaf 2/3/5%")
OUT["themes_res"] = {}
TMASK = {}
for th, feats in THEMES.items():
    G = lomo_grid(feats, depths=(1, 2, 3), mlfs=(0.02, 0.03, 0.05), crits=("entropy",), wmodes=("mbal",))
    g = G[0]
    r = leaves_report(feats, g, f"THEME {th}")
    TMASK[th] = r.pop("mask")
    r["grid_top"] = G[:5]
    OUT["themes_res"][th] = r

# ------------------------------------------------------------------------------------------------ boosted model on scale-free + month-balanced
print("=" * 150)
print("B. XGBOOST on scale-free features with month-balanced weights")
Xtr = d.loc[TR, SF].values.astype(float); Xte = d.loc[TE, SF].values.astype(float); yte = Y[TE]


def xgbm(n, depth, seed=0):
    return xgb.XGBClassifier(n_estimators=n, max_depth=depth, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                             reg_lambda=1.0, tree_method="hist", n_jobs=4, random_state=seed, verbosity=0)


NS = (25, 50, 100, 200, 300)
curve = {}
for depth in (2, 3):
    aucs = {n: [] for n in NS}
    for m in C.MONTHS_TR:
        fit, ho = mtr != m, mtr == m
        mdl = xgbm(max(NS), depth).fit(Xtr[fit], ytr[fit], sample_weight=mbal_weights(ytr[fit], mtr[fit]))
        for n in NS:
            aucs[n].append(roc_auc_score(ytr[ho], mdl.predict_proba(Xtr[ho], iteration_range=(0, n))[:, 1]))
    curve[depth] = {n: round(float(np.mean(a)), 4) for n, a in aucs.items()}
    print(f"   depth {depth} LOMO AUC: " + "  ".join(f"n{n}: {v:.3f}" for n, v in curve[depth].items()))
bd, bn = max(((dd, n) for dd in curve for n in NS), key=lambda t: curve[t[0]][t[1]])
final = xgbm(bn, bd).fit(Xtr, ytr, sample_weight=mbal_weights(ytr, mtr))
pte = final.predict_proba(Xte)[:, 1]
auc = roc_auc_score(yte, pte)
rng = np.random.default_rng(11)
boots = [roc_auc_score(yte[s], pte[s]) for s in (rng.choice(len(yte), len(yte)) for _ in range(2000)) if yte[s].sum()]
null = np.array([roc_auc_score(yte, xgbm(bn, bd, i).fit(Xtr, (yp := rng.permutation(ytr)), sample_weight=mbal_weights(yp, mtr))
                               .predict_proba(Xte)[:, 1]) for i in range(100)])
print(f"   chosen depth {bd}, {bn} trees (LOMO {curve[bd][bn]:.3f}) | TEST AUC {auc:.3f} (95% CI {np.percentile(boots, 2.5):.3f}-"
      f"{np.percentile(boots, 97.5):.3f}) | null mean {null.mean():.3f} 95th {np.percentile(null, 95):.3f} p={(np.sum(null >= auc) + 1) / 101:.3f}")
gain = final.get_booster().get_score(importance_type="gain")
gain = sorted(((SF[int(k[1:])], v) for k, v in gain.items()), key=lambda t: -t[1])
tot = sum(v for _, v in gain)
print("   gain: " + ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in gain[:10]))
OUT["xgb_sf_mbal"] = dict(depth=bd, n=bn, lomo=curve, test_auc=round(auc, 4), ci95=[round(float(np.percentile(boots, 2.5)), 4),
                          round(float(np.percentile(boots, 97.5)), 4)], null_mean=round(float(null.mean()), 4),
                          null_p95=round(float(np.percentile(null, 95)), 4), gain=[(k, round(100 * v / tot, 1)) for k, v in gain])

json.dump(OUT, open(os.path.join(C.HERE, "results2.json"), "w", encoding="utf-8"), indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("wrote", os.path.join(C.HERE, "results2.json"))
