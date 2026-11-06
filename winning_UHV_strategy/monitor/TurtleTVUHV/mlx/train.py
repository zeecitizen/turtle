"""mlx/train.py - the stacked classifier of the Machine Learning tab and its ONNX export.

StandardScaler -> sklearn StackingClassifier(base learners, final_estimator=LogisticRegression(C=1.0, max_iter=2000), cv=the purged folds,
stack_method='predict_proba', passthrough=False) on the SHAP-kept features, multiclass over the labels {-1, 0, 1} (fitted as 0, 1, 2 because
XGBoost wants 0-based classes; meta.json says so). Base learners: LightGBM and CatBoost when importable (an x64 machine), else their stand-ins
HistGradientBoostingClassifier (LightGBM's histogram algorithm) and XGBClassifier - every results file records which ran.
nested_oof(): the honest out-of-fold probabilities - for each outer purged fold the WHOLE stack (scaler, base learners with their own inner
purged folds, meta-learner) is fitted on the training rows only and scores the test rows. fit_full(): one model on given rows (the MAIN model
on every bar; the leave-one-year-out models on the other years, purged around the held-out year).
export_onnx(): each base learner -> base_1.onnx / base_2.onnx taking the SCALED kept features float32 [None, n_kept] (skl2onnx for the
sklearn learner, onnxmltools' converters registered into skl2onnx for XGBoost / LightGBM, CatBoost's own save_model), zipmap off, checked
against sklearn with onnxruntime; meta.json carries the kept list, the scaler, the meta-learner's coefficients and the class order, so the
EA can finish the stack itself: softmax(meta_coef @ [P_base1, P_base2] + meta_intercept). Hypotheses only (CLAUDE.md); MT5 judges."""
import json
import pickle
import sys
import time
import warnings
from pathlib import Path

if str(Path(__file__).resolve().parent.parent) not in sys.path:          # py mlx/train.py --verify ... from monitor/saad_view
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np                                                       # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, StackingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression                      # noqa: E402
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler                         # noqa: E402

from mlx.cv import PurgedKFold, purge_mask                               # noqa: E402

CLASSES = [-1, 0, 1]                                    # column order of every probability array: P(-1), P(0), P(1)
UP, DN = 2, 0                                           # the columns the EA reads: P(upper barrier first) and P(lower barrier first)
SEED = 1
N_TREES = 400


def _limits(n_jobs):
    try:
        from threadpoolctl import threadpool_limits
        return threadpool_limits(limits=int(n_jobs))
    except Exception:                                   # noqa: BLE001
        import contextlib
        return contextlib.nullcontext()


# ---------------------------------------------------------------- the learners
def learners(n_jobs=6, seed=SEED, n_trees=N_TREES):
    """-> [{"key", "role", "name", "substitute", "params", "est"}, ...] - the real LightGBM / CatBoost when importable, else the stand-ins"""
    out = []
    try:
        import lightgbm as lgb
        p = {"n_estimators": n_trees, "learning_rate": 0.05, "num_leaves": 31, "min_child_samples": 200, "subsample": 0.8, "subsample_freq": 1,
             "colsample_bytree": 0.8, "reg_lambda": 1.0}
        out.append({"key": "base_1", "role": "LightGBM", "name": "LGBMClassifier", "substitute": False, "params": p,
                    "est": lgb.LGBMClassifier(n_jobs=n_jobs, random_state=seed, verbose=-1, **p)})
    except Exception:                                   # noqa: BLE001
        p = {"max_iter": n_trees, "learning_rate": 0.05, "max_leaf_nodes": 31, "min_samples_leaf": 200, "l2_regularization": 1.0}
        out.append({"key": "base_1", "role": "LightGBM", "name": "HistGradientBoostingClassifier", "substitute": True, "params": p,
                    "est": HistGradientBoostingClassifier(early_stopping=False, random_state=seed, **p)})
    try:
        import catboost as cb
        p = {"iterations": n_trees, "depth": 6, "learning_rate": 0.05, "l2_leaf_reg": 3.0}
        out.append({"key": "base_2", "role": "CatBoost", "name": "CatBoostClassifier", "substitute": False, "params": p,
                    "est": cb.CatBoostClassifier(loss_function="MultiClass", verbose=0, thread_count=n_jobs, random_seed=seed, allow_writing_files=False, **p)})
    except Exception:                                   # noqa: BLE001
        import xgboost as xgb
        p = {"n_estimators": n_trees, "max_depth": 5, "learning_rate": 0.05, "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 50, "reg_lambda": 1.0}
        out.append({"key": "base_2", "role": "CatBoost", "name": "XGBClassifier", "substitute": True, "params": p,
                    "est": xgb.XGBClassifier(tree_method="hist", objective="multi:softprob", n_jobs=n_jobs, random_state=seed, verbosity=0, **p)})
    return out


def make_stack(folds, n_jobs=6, seed=SEED, n_trees=N_TREES):
    L = learners(n_jobs, seed, n_trees)
    return StackingClassifier(estimators=[(d["key"], d["est"]) for d in L], final_estimator=LogisticRegression(C=1.0, max_iter=2000),
                              cv=list(folds), stack_method="predict_proba", passthrough=False, n_jobs=1)


def fit_full(X, y, k15, touch_k, n_splits=5, embargo=24, n_jobs=6, seed=SEED, n_trees=N_TREES):
    """scaler + stack on these rows; the stack's inner cv = purged folds over these rows. -> (scaler, stack, inner_folds)"""
    inner = PurgedKFold(n_splits, embargo).split(k15, touch_k)
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X).astype(np.float32)
    stack = make_stack(inner, n_jobs, seed, n_trees)
    with _limits(n_jobs), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        stack.fit(Xs, y)
    return scaler, stack, inner


def predict(scaler, stack, X):
    return stack.predict_proba(scaler.transform(X).astype(np.float32))


# ---------------------------------------------------------------- scoring
def metrics(y, P):
    """y in 0..2, P [n, 3] -> logloss / accuracy / AUC up / AUC down / Brier up / Brier down (None where a class is absent)"""
    out = {"n": int(len(y)), "logloss": float(log_loss(y, P, labels=[0, 1, 2])), "acc": float(accuracy_score(y, P.argmax(axis=1)))}
    for nm, col in (("up", UP), ("down", DN), ("none", 1)):
        t = (y == col).astype(int)
        out["auc_" + nm] = float(roc_auc_score(t, P[:, col])) if 0 < t.sum() < len(t) else None
        if nm != "none":
            out["brier_" + nm] = float(brier_score_loss(t, P[:, col]))
    return out


def calibration(p, hit, bins=10):
    """10-bin reliability table of a probability column against its 0/1 outcome"""
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, bins - 1)
    rows = []
    for b in range(bins):
        m = idx == b
        n = int(m.sum())
        rows.append({"bin": "%.1f-%.1f" % (edges[b], edges[b + 1]), "n": n, "pred": round(float(p[m].mean()), 4) if n else None,
                     "actual": round(float(hit[m].mean()), 4) if n else None})
    return rows


def nested_oof(X, y, k15, touch_k, folds, n_splits=5, embargo=24, n_jobs=6, seed=SEED, n_trees=N_TREES, t15=None, progress_cb=None, phase="stacking"):
    """out-of-fold probabilities of the whole stack: per outer fold, scaler + stack (inner purged folds) fitted on the train rows only.
    -> (P [n, 3], baseline P [n, 3] = the train rows' class frequencies, per-fold metric rows)"""
    n = len(y)
    P = np.full((n, 3), np.nan)
    B = np.full((n, 3), np.nan)
    rows = []
    for f, (tr, te) in enumerate(folds):
        if progress_cb:
            progress_cb(phase, f, len(folds))
        t0 = time.time()
        scaler, stack, _ = fit_full(X[tr], y[tr], k15[tr], touch_k[tr], n_splits, embargo, n_jobs, seed, n_trees)
        P[te] = predict(scaler, stack, X[te])
        B[te] = np.bincount(y[tr], minlength=3) / len(tr)
        r = {"fold": f + 1, "n_train": int(len(tr)), "n_purged": int(n - len(tr) - len(te)), "n_test": int(len(te)), "secs": round(time.time() - t0, 1)}
        if t15 is not None:
            r["test_from"], r["test_to"] = _day(t15[te[0]]), _day(t15[te[-1]])
        r.update(metrics(y[te], P[te]))
        r["baseline_logloss"] = float(log_loss(y[te], B[te], labels=[0, 1, 2]))
        rows.append(r)
    return P, B, rows


def _day(t):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(int(t), timezone.utc).strftime("%Y-%m-%d")


def loyo_rows(k15, touch_k, years, year, embargo=24):
    """the training rows of the leave-one-year-out model of `year`: the other years, purged around the held-out year and embargoed after it"""
    held = years == year
    keep = purge_mask(k15, touch_k, int(k15[held].min()), int(k15[held].max()), embargo) & ~held
    return np.nonzero(keep)[0], np.nonzero(held)[0]


# ---------------------------------------------------------------- saving + ONNX
def _patch_skl2onnx():
    """skl2onnx 1.20 hands protobuf a numpy bool for HGB's missing_go_to_left; protobuf wants an int"""
    import skl2onnx.common.tree_ensemble as te
    if getattr(te.add_node, "_mlx", False):
        return
    orig = te.add_node

    def add_node(*a, **k):
        if "nodes_missing_value_tracks_true" in k:
            k["nodes_missing_value_tracks_true"] = int(k["nodes_missing_value_tracks_true"])
        return orig(*a, **k)
    add_node._mlx = True
    te.add_node = add_node


def _register_converters():
    from skl2onnx import update_registered_converter
    from skl2onnx.common.shape_calculator import calculate_linear_classifier_output_shapes
    opts = {"nocl": [True, False], "zipmap": [True, False, "columns"]}
    try:
        import xgboost as xgb
        from onnxmltools.convert.xgboost.operator_converters.XGBoost import convert_xgboost
        update_registered_converter(xgb.XGBClassifier, "XGBoostXGBClassifier", calculate_linear_classifier_output_shapes, convert_xgboost, options=opts)
    except Exception:                                   # noqa: BLE001
        pass
    try:
        import lightgbm as lgb
        from onnxmltools.convert.lightgbm.operator_converters.LightGbm import convert_lightgbm
        update_registered_converter(lgb.LGBMClassifier, "LightGbmLGBMClassifier", calculate_linear_classifier_output_shapes, convert_lightgbm, options=opts)
    except Exception:                                   # noqa: BLE001
        pass


def to_onnx(est, n_in, path):
    """one fitted base learner -> an ONNX file taking float32 [None, n_in] (the scaled kept features), outputs label + probabilities [None, 3]"""
    name = type(est).__name__
    if name == "CatBoostClassifier":
        est.save_model(str(path), format="onnx", export_parameters={"onnx_domain": "ai.catboost", "onnx_graph_name": "mlx_base"})
        return "catboost save_model(format=onnx)"
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    _patch_skl2onnx()
    _register_converters()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = convert_sklearn(est, initial_types=[("input", FloatTensorType([None, int(n_in)]))], options={id(est): {"zipmap": False}},
                                target_opset={"": 15, "ai.onnx.ml": 3})
    Path(path).write_bytes(model.SerializeToString())
    return "skl2onnx" if name.startswith("Hist") else "onnxmltools via skl2onnx"


def _ort_probs(path, Xs):
    import onnxruntime as ort
    s = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    inp = s.get_inputs()[0].name
    outs = [o.name for o in s.get_outputs()]
    pick = outs.index("probabilities") if "probabilities" in outs else len(outs) - 1
    res = []
    for i in range(0, len(Xs), 20000):
        res.append(np.asarray(s.run([outs[pick]], {inp: np.ascontiguousarray(Xs[i:i + 20000], dtype=np.float32)})[0]))
    return np.vstack(res)


def _softmax(z):
    e = np.exp(z - z.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def meta_json(scaler, stack, kept, names_all, extra=None):
    lr = stack.final_estimator_
    out = {"kept": list(kept), "scaler": {"mean": [float(v) for v in scaler.mean_], "scale": [float(v) for v in scaler.scale_]},
           "meta_coef": [[float(v) for v in row] for row in lr.coef_], "meta_intercept": [float(v) for v in lr.intercept_], "classes": CLASSES,
           "base_names": [type(e).__name__ for e in stack.estimators_], "base_files": ["base_%d.onnx" % (i + 1) for i in range(len(stack.estimators_))],
           "features_all": list(names_all), "input": "the kept features in this order, (x - mean) / scale, float32 [1, n_kept]",
           "meta_input": "[base_1 P(-1), P(0), P(1), base_2 P(-1), P(0), P(1)] - each ONNX file's 'probabilities' output, in base_files order",
           "meta_rule": "P = softmax(meta_coef @ meta_input + meta_intercept) over classes [-1, 0, 1]; P(up) = P[2], P(down) = P[0]",
           "onnx_io": {"input": "input", "outputs": ["label", "probabilities"]}, "fitted_as": "labels -1/0/1 fitted as 0/1/2 (XGBoost wants 0-based classes)"}
    out.update(extra or {})
    return out


def save_models(outdir, scaler, stack, kept, names_all, extra=None):
    """pickles + meta.json into outdir -> the file list"""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for i, e in enumerate(stack.estimators_):
        (outdir / ("base_%d.pkl" % (i + 1))).write_bytes(pickle.dumps(e))
    (outdir / "meta.pkl").write_bytes(pickle.dumps(stack.final_estimator_))
    (outdir / "scaler.pkl").write_bytes(pickle.dumps(scaler))
    (outdir / "stack.pkl").write_bytes(pickle.dumps(stack))
    (outdir / "meta.json").write_text(json.dumps(meta_json(scaler, stack, kept, names_all, extra), indent=1), encoding="utf-8")
    return sorted(p.name for p in outdir.iterdir())


def export_onnx(outdir, scaler, stack, X_check):
    """base_i.onnx for every base learner + the onnxruntime check on X_check (raw kept features): per-model max |ONNX - sklearn| and the
    max difference of the stacked probability when the EA's own meta step runs on the ONNX outputs. Never raises: the status says what failed."""
    outdir = Path(outdir)
    info = {"status": "", "files": [], "max_abs_diff": None, "runtime": None, "per_model": {}, "converters": []}
    try:
        import onnx  # noqa: F401
        import skl2onnx  # noqa: F401
    except Exception as e:                              # noqa: BLE001
        info["status"] = "not exported - onnx / skl2onnx not importable here (%s): needs the x64 VM" % e
        return info
    Xs = scaler.transform(X_check).astype(np.float32)
    n_in = Xs.shape[1]
    for i, est in enumerate(stack.estimators_):
        path = outdir / ("base_%d.onnx" % (i + 1))
        try:
            info["converters"].append(to_onnx(est, n_in, path))
            info["files"].append({"path": str(path.relative_to(outdir.parent.parent.parent)).replace("\\", "/") if "simdata" in path.parts else str(path),
                                  "bytes": path.stat().st_size, "learner": type(est).__name__})
        except Exception as e:                          # noqa: BLE001
            info["status"] = "FAILED on %s: %s" % (type(est).__name__, str(e)[:300])
            return info
    try:
        import onnxruntime as ort
        info["runtime"] = "onnxruntime " + ort.__version__
    except Exception as e:                              # noqa: BLE001
        info["status"] = "exported %d files, NOT verified - onnxruntime not importable (%s)" % (len(info["files"]), e)
        return info
    try:
        Z = []
        worst = 0.0
        for i, est in enumerate(stack.estimators_):
            po = _ort_probs(outdir / ("base_%d.onnx" % (i + 1)), Xs)
            ps = est.predict_proba(Xs)
            d = float(np.abs(po - ps).max())
            info["per_model"]["base_%d" % (i + 1)] = {"learner": type(est).__name__, "max_abs_diff": d, "mean_abs_diff": float(np.abs(po - ps).mean())}
            worst = max(worst, d)
            Z.append(po)
        lr = stack.final_estimator_
        P_onnx = _softmax(np.hstack(Z) @ lr.coef_.T + lr.intercept_)
        d_stack = float(np.abs(P_onnx - stack.predict_proba(Xs)).max())
        info["per_model"]["stacked"] = {"max_abs_diff": d_stack, "note": "softmax(meta_coef @ ONNX probabilities + intercept) vs stack.predict_proba"}
        info["max_abs_diff"] = max(worst, d_stack)
        info["status"] = "ok - %d base learners exported (%s), checked against sklearn with %s on %d bars" % (
            len(info["files"]), " / ".join(sorted(set(info["converters"]))), info["runtime"], len(Xs))
    except Exception as e:                              # noqa: BLE001
        info["status"] = "exported %d files, the onnxruntime check FAILED: %s" % (len(info["files"]), str(e)[:300])
    return info


# ---------------------------------------------------------------- the EA's recipe, from the files alone
def scale32(X32, mean, scale):
    """StandardScaler.transform on a float32 matrix exactly as numpy's in-place ops do it (and as the EA's MlBar does since 2026-11-01):
    float32(float64(x) - mean) then float32(float64(that) / scale) - one rounding per step, not a single float64 expression."""
    X = np.asarray(X32, dtype=np.float32).copy()
    X -= np.asarray(mean, dtype=np.float64)
    X /= np.asarray(scale, dtype=np.float64)
    return X


def verify_dir(outdir, X_all=None, names=None, rows=5000, thr=0.75):
    """what the EA does, from meta.json + base_*.onnx only (no sklearn in the loop): kept raw features -> (x - mean) / scale -> the two
    ONNX files -> softmax(meta_coef @ [P1, P2] + meta_intercept) -> P(-1), P(0), P(1); compared with stack.pkl + scaler.pkl on `rows` bars.
    X_all / names default to simdata/mlx_dataset.npz (the last `rows` bars)."""
    import onnxruntime as ort
    outdir = Path(outdir)
    m = json.loads((outdir / "meta.json").read_text(encoding="utf-8"))
    if X_all is None:
        z = np.load(Path(__file__).resolve().parent.parent / "simdata" / "mlx_dataset.npz", allow_pickle=False)
        X_all, names = z["X"], [str(v) for v in z["names"]]
    names = list(names)
    X = np.asarray(X_all)[-int(rows):][:, [names.index(k) for k in m["kept"]]].astype(np.float32)
    Xs = scale32(X, m["scaler"]["mean"], m["scaler"]["scale"])                 # the EA's recipe (two float32 roundings), see scale32
    Z = []
    for f in m["base_files"]:
        s = ort.InferenceSession(str(outdir / f), providers=["CPUExecutionProvider"])
        Z.append(np.asarray(s.run(["probabilities"], {"input": Xs})[0]))
    P = _softmax(np.hstack(Z) @ np.array(m["meta_coef"]).T + np.array(m["meta_intercept"]))
    out = {"dir": str(outdir), "rows": int(len(X)), "n_kept": len(m["kept"]), "classes": m["classes"],
           "p_up_gt_thr": int((P[:, UP] > thr).sum()), "p_down_gt_thr": int((P[:, DN] > thr).sum()), "max_p_up": float(P[:, UP].max()), "max_p_down": float(P[:, DN].max())}
    if (outdir / "stack.pkl").is_file() and (outdir / "scaler.pkl").is_file():
        stack = pickle.loads((outdir / "stack.pkl").read_bytes())
        scaler = pickle.loads((outdir / "scaler.pkl").read_bytes())
        out["max_abs_diff_vs_sklearn"] = float(np.abs(P - stack.predict_proba(scaler.transform(X).astype(np.float32))).max())
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="py mlx/train.py --verify simdata/mlx_models/main  - the EA's files-only recipe against sklearn")
    ap.add_argument("--verify", required=True, help="a model directory (meta.json + base_1.onnx + base_2.onnx [+ stack.pkl, scaler.pkl])")
    ap.add_argument("--rows", type=int, default=5000)
    a = ap.parse_args()
    print(json.dumps(verify_dir(a.verify, rows=a.rows), indent=1))
