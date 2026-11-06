"""mlx/shap_select.py - SHAP feature reduction for the Machine Learning tab: of the FEATURE_SPEC's per-bar features keep the 20-50 that matter.

The initial booster (lightgbm when importable, else xgboost - this ARM64 laptop has no lightgbm wheel) is fitted on the TRAIN rows of each
purged fold and its SHAP values are taken on that fold's TEST rows (the shap library when importable, else the booster's own TreeSHAP:
XGBoost Booster.predict(pred_contribs=True) / LightGBM predict(pred_contrib=True)); for the 3 classes |contrib| is summed over the classes.
mean |SHAP| per feature is averaged over the folds, so no bar's own test fold ever ranks it at full-data level. Rule: drop a feature whose
mean |SHAP| is below 2% of the largest; keep at least 20 and at most 50 (the top ones by mean |SHAP|). spread_pts is not a candidate unless
use_spread is on (the caller decides). Every number here is a hypothesis-generator (CLAUDE.md)."""
import time

import numpy as np

SEED = 1


def booster_kind():
    try:
        import lightgbm  # noqa: F401
        return "lightgbm"
    except Exception:                                   # noqa: BLE001
        return "xgboost"


def shap_kind():
    try:
        import shap  # noqa: F401
        return "shap"
    except Exception:                                   # noqa: BLE001
        return "builtin"


def fit_booster(X, y, n_jobs=6, seed=SEED, n_estimators=300):
    """the initial booster (multiclass, labels 0..2)"""
    if booster_kind() == "lightgbm":
        import lightgbm as lgb
        m = lgb.LGBMClassifier(n_estimators=n_estimators, learning_rate=0.05, num_leaves=31, min_child_samples=200, subsample=0.8, subsample_freq=1,
                               colsample_bytree=0.8, reg_lambda=1.0, n_jobs=n_jobs, random_state=seed, verbose=-1)
    else:
        import xgboost as xgb
        m = xgb.XGBClassifier(n_estimators=n_estimators, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=50,
                              reg_lambda=1.0, tree_method="hist", objective="multi:softprob", n_jobs=n_jobs, random_state=seed, verbosity=0)
    m.fit(X, y)
    return m


def shap_mean_abs(model, X):
    """-> (mean over rows of sum over classes |SHAP| per feature, method string)"""
    n_feat = X.shape[1]
    if shap_kind() == "shap":
        import shap
        sv = shap.TreeExplainer(model).shap_values(X)
        arr = np.stack(sv, axis=-1) if isinstance(sv, list) else np.asarray(sv)          # (n, feat, class) in both shap generations
        if arr.ndim == 2:
            arr = arr[:, :, None]
        return np.abs(arr).sum(axis=2).mean(axis=0), "shap.TreeExplainer, mean |SHAP| summed over the 3 classes, out-of-fold bars"
    if booster_kind() == "lightgbm":
        c = np.asarray(model.predict(X, pred_contrib=True))                               # (n, class * (feat + 1)), bias last in each block
        c = c.reshape(len(X), -1, n_feat + 1)[:, :, :n_feat]
        return np.abs(c).sum(axis=1).mean(axis=0), "LightGBM TreeSHAP (predict pred_contrib), mean |SHAP| summed over the 3 classes, out-of-fold bars"
    import xgboost as xgb
    c = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)                 # (n, class, feat + 1) for multi:softprob
    if c.ndim == 2:
        c = c[:, None, :]
    c = c[:, :, :n_feat]
    return np.abs(c).sum(axis=1).mean(axis=0), "XGBoost TreeSHAP (Booster.predict pred_contribs), mean |SHAP| summed over the 3 classes, out-of-fold bars"


def _spearman(a, b):
    ra, rb = np.argsort(np.argsort(-a)), np.argsort(np.argsort(-b))
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def select(X, y, folds, names, candidates=None, min_keep=20, max_keep=50, frac=0.02, n_jobs=6, seed=SEED, n_estimators=300, progress_cb=None):
    """X float32 [n, all features] in FEATURE_SPEC order, y in 0..2, folds = [(train_idx, test_idx)], names = all feature names.
    candidates = the names allowed in (default: all). -> dict(kept, dropped, ranking, method, rule, per_fold, stability, secs)"""
    names = list(names)
    cand = [n for n in (candidates if candidates is not None else names) if n in names]
    cols = np.array([names.index(n) for n in cand])
    t0 = time.time()
    per_fold = []
    method = ""
    for f, (tr, te) in enumerate(folds):
        if progress_cb:
            progress_cb("purged CV + SHAP", f, len(folds))
        m = fit_booster(X[tr][:, cols], y[tr], n_jobs=n_jobs, seed=seed, n_estimators=n_estimators)
        v, method = shap_mean_abs(m, X[te][:, cols])
        per_fold.append(np.asarray(v, dtype=np.float64))
    per_fold = np.vstack(per_fold)                                                      # (folds, candidates)
    mean_abs = per_fold.mean(axis=0)
    order = np.argsort(-mean_abs, kind="stable")
    thr = frac * float(mean_abs.max()) if len(mean_abs) else 0.0
    n_rule = int((mean_abs >= thr).sum())
    n_keep = min(max(n_rule, min_keep), max_keep, len(cand))
    kept = [cand[i] for i in order[:n_keep]]
    kept_in_order = [n for n in names if n in set(kept)]                                # FEATURE_SPEC order - the ONNX tensor follows it
    ranking = [{"name": cand[i], "mean_abs": round(float(mean_abs[i]), 6), "kept": cand[i] in set(kept)} for i in order]
    ranking += [{"name": n, "mean_abs": 0.0, "kept": False, "excluded": True} for n in names if n not in set(cand)]
    pairs = [(_spearman(per_fold[i], per_fold[j])) for i in range(len(per_fold)) for j in range(i + 1, len(per_fold))]
    return {"kept": kept_in_order, "dropped": [n for n in names if n not in set(kept)], "ranking": ranking, "method": method,
            "rule": "drop a feature whose mean |SHAP| (averaged over the %d purged folds, each scored on its own test bars) is below %d%% of the largest; "
                    "keep at least %d and at most %d -> %d passed the 2%% rule, %d kept" % (len(folds), round(100 * frac), min_keep, max_keep, n_rule, n_keep),
            "booster": booster_kind(), "threshold": round(thr, 6), "n_rule": n_rule, "n_candidates": len(cand),
            "per_fold": {cand[i]: [round(float(v), 6) for v in per_fold[:, i]] for i in order[:n_keep]},
            "stability": round(float(np.mean(pairs)), 3) if pairs else None,           # mean Spearman between the folds' rankings
            "secs": round(time.time() - t0, 1)}
