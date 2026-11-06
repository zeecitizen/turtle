"""mlx/run.py - the Machine Learning tab's pipeline, end to end (Zee 2026-11-01), writing simdata/mlx_results.json for the page:
  labels                 simdata/mlx_dataset.npz (data.py: FEATURE_SPEC features + Triple Barrier labels 1.5 / 1.5 ATR / 24 bars) is loaded and checked
  purged CV + SHAP       PurgedKFold(5, embargo 24) -> SHAP ranking on each fold's test bars -> the 20-50 features that matter
  stacking               nested out-of-fold probabilities of the whole stack (scaler + LightGBM|HGB + CatBoost|XGB -> LogisticRegression),
                         the MAIN model on every bar, 4 leave-one-year-out models (simdata/mlx_models/main, loyo_<year>)
  ONNX                   base_1.onnx / base_2.onnx + meta.json per model, verified with onnxruntime
  trading translation    the EA's trades (setting B and the setup UNIVERSE) all vs the ones P > thr lets through, OOF probabilities only
  + Combinatorial Purged CV (6 groups, 2 test groups, 15 splits, 5 paths) on one base learner as a robustness extra
run(progress_cb) is what server.py's POST /api/mlx calls (cb(phase, i, n)); CLI: py mlx/run.py [--quick] [--no-cpcv] [--jobs N] [--trees N]
CLAUDE.md: every number here is a HYPOTHESIS. Only MT5's Strategy Tester promotes; the page says so."""
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEW = HERE.parent
if str(VIEW) not in sys.path:
    sys.path.insert(0, str(VIEW))
os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np                                     # noqa: E402

from mlx import report, shap_select, train             # noqa: E402
from mlx.cv import CombinatorialPurgedCV, PurgedKFold  # noqa: E402

SIMDATA = VIEW / "simdata"
DATASET = SIMDATA / "mlx_dataset.npz"
ENTRIES = SIMDATA / "mlx_entries.npz"
FEATURES = SIMDATA / "mlx_features.json"
RESULTS = SIMDATA / "mlx_results.json"
MODELS = SIMDATA / "mlx_models"
BARRIERS = {"up_atr": 1.5, "dn_atr": 1.5, "time_bars": 24}
EMBARGO, FOLDS, THRESHOLD, USE_SPREAD = 24, 5, 0.75, False
CPCV_GROUPS, CPCV_TEST = 6, 2
PHASES = ("labels", "purged CV + SHAP", "stacking", "ONNX", "trading translation")


def _log(msg):
    print(datetime.now().strftime("%H:%M:%S"), msg, flush=True)


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return v if np.isfinite(v) else None
    if isinstance(o, float) and not np.isfinite(o):
        return None
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, Path):
        return str(o)
    return o


def _years(t15):
    return np.array([datetime.fromtimestamp(int(t), timezone.utc).year for t in t15], dtype=np.int64)


def _label_by_year(years, label):
    out = {}
    for y in np.unique(years):
        m = years == y
        out[str(int(y))] = {"n": int(m.sum()), "up": int((label[m] == 1).sum()), "down": int((label[m] == -1).sum()), "none": int((label[m] == 0).sum())}
    return out


def _versions():
    out = {"python": platform.python_version(), "machine": platform.machine()}
    for m in ("numpy", "sklearn", "xgboost", "lightgbm", "catboost", "shap", "onnx", "skl2onnx", "onnxmltools", "onnxruntime"):
        try:
            out[m] = __import__(m).__version__
        except Exception:                               # noqa: BLE001
            out[m] = None
    return out


def _rel(p):
    try:
        return str(Path(p).relative_to(VIEW)).replace("\\", "/")
    except ValueError:
        return str(p)


# ---------------------------------------------------------------- the data
def load_dataset(path=DATASET, last=None):
    """-> dict of the dataset's arrays after the sanity checks; a precise error when the file is missing or broken"""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("%s is missing - build it first: py -m mlx.data  (from monitor/saad_view)" % _rel(path))
    z = np.load(path, allow_pickle=False)
    need = ("X", "names", "t15", "k15", "label", "touch_k", "atr", "close")
    missing = [k for k in need if k not in z.files]
    if missing:
        raise ValueError("%s lacks the arrays %s - rebuild it: py -m mlx.data" % (_rel(path), missing))
    d = {k: z[k] for k in z.files}
    d["names"] = [str(n) for n in d["names"]]
    n, w = d["X"].shape
    bad = []
    if len(d["names"]) != w:
        bad.append("names (%d) != X columns (%d)" % (len(d["names"]), w))
    for k in ("t15", "k15", "label", "touch_k", "atr", "close"):
        if len(d[k]) != n:
            bad.append("%s has %d rows, X has %d" % (k, len(d[k]), n))
    if not np.isfinite(d["X"]).all():
        bad.append("X has NaN / inf cells")
    if not set(np.unique(d["label"]).tolist()) <= {-1, 0, 1}:
        bad.append("labels outside {-1, 0, 1}: %s" % np.unique(d["label"]).tolist())
    if np.any(np.diff(d["k15"]) <= 0):
        bad.append("k15 is not strictly increasing")
    if np.any(d["touch_k"] < d["k15"] + 1) or np.any(d["touch_k"] > d["k15"] + BARRIERS["time_bars"]):
        bad.append("touch_k outside k15 + 1 .. k15 + %d" % BARRIERS["time_bars"])
    if bad:
        raise ValueError("%s is broken: %s" % (_rel(path), "; ".join(bad)))
    if last:
        d = {k: (v[-last:] if isinstance(v, np.ndarray) else v) for k, v in d.items()}
    return d


def load_entries(path=ENTRIES):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError("%s is missing - build it: py -m mlx.data --only-entries" % _rel(path))
    z = np.load(path, allow_pickle=False)
    need = ("k15", "side", "entry_t", "pnl", "src")
    missing = [k for k in need if k not in z.files]
    if missing:
        raise ValueError("%s lacks %s" % (_rel(path), missing))
    return {k: z[k] for k in z.files}


# ---------------------------------------------------------------- the pipeline
def run(progress_cb=None, out=RESULTS, models_dir=MODELS, features_json=FEATURES, n_jobs=None, quick=False, cpcv=True, n_trees=None, dataset=DATASET,
        entries_file=ENTRIES):
    """the whole pipeline -> the results dict (also written to `out`); progress_cb(phase, i, n) is optional"""
    T0 = time.time()
    timings, notes = {}, []
    n_jobs = int(n_jobs or max(2, (os.cpu_count() or 4) - 2))
    n_trees = int(n_trees or (40 if quick else train.N_TREES))
    shap_trees = 40 if quick else 300

    def cb(phase, i=0, n=0):
        _log("%s %s/%s" % (phase, i, n))
        if progress_cb:
            try:
                progress_cb(phase, i, n)
            except Exception:                           # noqa: BLE001
                pass

    # ---- labels
    t0 = time.time()
    cb(PHASES[0], 0, 1)
    d = load_dataset(dataset, last=30000 if quick else None)
    E = load_entries(entries_file)
    names = d["names"]
    X, label, k15, touch_k, t15 = d["X"], d["label"].astype(np.int64), d["k15"].astype(np.int64), d["touch_k"].astype(np.int64), d["t15"]
    y = (label + 1).astype(np.int64)                    # -1/0/1 -> 0/1/2 (XGBoost wants 0-based classes); train.CLASSES says so
    years = _years(t15)
    n = len(y)
    data_block = {"bars": int(n), "train_years": [str(int(v)) for v in np.unique(years)], "years": _label_by_year(years, label),
                  "from": datetime.fromtimestamp(int(t15[0]), timezone.utc).strftime("%Y-%m-%d %H:%M"),
                  "to": datetime.fromtimestamp(int(t15[-1]), timezone.utc).strftime("%Y-%m-%d %H:%M"), "features_in_file": len(names),
                  "label_total": {"up": int((label == 1).sum()), "down": int((label == -1).sum()), "none": int((label == 0).sum())},
                  "entries": {"B": int((E["src"] == 0).sum()), "universe": int((E["src"] == 1).sum())}}
    timings["labels"] = round(time.time() - t0, 1)
    cb(PHASES[0], 1, 1)
    if quick:
        notes.append("QUICK smoke run: the last %d rows only, %d trees - not a result" % (n, n_trees))

    # ---- purged CV + SHAP
    t0 = time.time()
    pk = PurgedKFold(FOLDS, EMBARGO)
    folds = pk.split(k15, touch_k)
    purge_rows = pk.describe(k15, touch_k)
    candidates = [nm for nm in names if USE_SPREAD or nm != "spread_pts"]
    sh = shap_select.select(X, y, folds, names, candidates=candidates, n_jobs=n_jobs, n_estimators=shap_trees, progress_cb=cb)
    kept = sh["kept"]
    cols = np.array([names.index(nm) for nm in kept])
    Xk = np.ascontiguousarray(X[:, cols], dtype=np.float32)
    cb(PHASES[1], FOLDS, FOLDS)
    timings["shap"] = round(time.time() - t0, 1)
    _log("SHAP kept %d of %d candidates (%s)" % (len(kept), len(candidates), sh["booster"]))
    Path(features_json).write_text(json.dumps({"all": names, "kept": kept, "scaler": None, "built": datetime.now().isoformat(timespec="seconds")}, indent=1), encoding="utf-8")

    # ---- stacking: nested OOF, the main model, the leave-one-year-out models
    t0 = time.time()
    loyo_years = [int(v) for v in np.unique(years) if (years == v).sum() >= 500]
    if len(loyo_years) < 2:
        loyo_years = []
    total = FOLDS + 1 + len(loyo_years)
    P, B, fold_rows = train.nested_oof(Xk, y, k15, touch_k, folds, FOLDS, EMBARGO, n_jobs, train.SEED, n_trees, t15=t15, progress_cb=cb, phase=PHASES[2])
    oof = train.metrics(y, P)
    from sklearn.metrics import log_loss
    baseline = float(log_loss(y, B, labels=[0, 1, 2]))
    cal = train.calibration(P[:, train.UP], (y == train.UP).astype(float))
    cal_dn = train.calibration(P[:, train.DN], (y == train.DN).astype(float))
    timings["cv"] = round(time.time() - t0, 1)
    cb(PHASES[2], FOLDS, total)
    t1 = time.time()
    L = train.learners(n_jobs, train.SEED, n_trees)
    scaler, stack, _ = train.fit_full(Xk, y, k15, touch_k, FOLDS, EMBARGO, n_jobs, train.SEED, n_trees)
    main_dir = Path(models_dir) / "main"
    main_files = train.save_models(main_dir, scaler, stack, kept, names, {"trained_rows": int(n), "train_years": data_block["train_years"], "holdout_year": None,
                                                                          "built": datetime.now().isoformat(timespec="seconds"), "threshold": THRESHOLD, "n_trees": n_trees})
    models = {"main": {"dir": _rel(main_dir), "files": main_files, "rows": int(n), "years": data_block["train_years"]}, "loyo": {}}
    Path(features_json).write_text(json.dumps({"all": names, "kept": kept, "scaler": {"mean": [float(v) for v in scaler.mean_], "scale": [float(v) for v in scaler.scale_]},
                                               "built": datetime.now().isoformat(timespec="seconds"), "model": _rel(main_dir)}, indent=1), encoding="utf-8")
    timings["main_model"] = round(time.time() - t1, 1)
    cb(PHASES[2], FOLDS + 1, total)
    t1 = time.time()
    loyo_models = {}
    for j, yr in enumerate(loyo_years):
        tr, held = train.loyo_rows(k15, touch_k, years, yr, EMBARGO)
        sc, st, _ = train.fit_full(Xk[tr], y[tr], k15[tr], touch_k[tr], FOLDS, EMBARGO, n_jobs, train.SEED, n_trees)
        Ph = train.predict(sc, st, Xk[held])
        ddir = Path(models_dir) / ("loyo_%d" % yr)
        files = train.save_models(ddir, sc, st, kept, names, {"trained_rows": int(len(tr)), "train_years": [str(v) for v in loyo_years if v != yr], "holdout_year": yr,
                                                              "built": datetime.now().isoformat(timespec="seconds"), "threshold": THRESHOLD, "n_trees": n_trees})
        hm = train.metrics(y[held], Ph)
        hm["baseline_logloss"] = float(log_loss(y[held], np.tile(np.bincount(y[tr], minlength=3) / len(tr), (len(held), 1)), labels=[0, 1, 2]))
        models["loyo"][str(yr)] = {"dir": _rel(ddir), "files": files, "train_rows": int(len(tr)), "purged": int(n - len(tr) - len(held)), "holdout_rows": int(len(held)),
                                   "holdout": hm, "kept": "the main model's kept list"}
        loyo_models[yr] = (sc, st, held)
        cb(PHASES[2], FOLDS + 2 + j, total)
    timings["loyo"] = round(time.time() - t1, 1)
    # every bar's probabilities, for the MT5 parity step: OOF (nested), the MAIN model (in-sample), the LOYO model of the bar's own year (out-of-year)
    P_main = train.predict(scaler, stack, Xk)
    P_loyo = np.full((n, 3), np.nan)
    for yr, (sc, st, held) in loyo_models.items():
        P_loyo[held] = train.predict(sc, st, Xk[held])
    pred_file = Path(models_dir) / "predictions.npz"
    np.savez_compressed(pred_file, k15=k15, t15=t15, label=label, P_oof=P.astype(np.float32), P_main=P_main.astype(np.float32), P_loyo=P_loyo.astype(np.float32),
                        kept=np.array(kept), classes=np.array(train.CLASSES))
    models["predictions"] = {"file": _rel(pred_file), "arrays": ["k15", "t15", "label", "P_oof", "P_main", "P_loyo", "kept", "classes"],
                             "note": "P columns = P(-1), P(0), P(1) at the bar's close; P_oof = nested out-of-fold, P_main = the main model (saw the bar), "
                                     "P_loyo = the leave-one-year-out model of the bar's year (never saw it) - the MT5 EA with loyo_<year> must reproduce P_loyo"}
    timings["stack"] = round(time.time() - t0, 1)
    notes.append("the leave-one-year-out models reuse the MAIN model's SHAP-kept feature list (%d features); each has its own scaler and coefficients in its meta.json" % len(kept))

    # ---- ONNX
    t0 = time.time()
    cb(PHASES[3], 0, 1 + len(loyo_models))
    onnx_main = train.export_onnx(main_dir, scaler, stack, Xk)
    onnx = {"status": onnx_main["status"], "files": list(onnx_main["files"]), "max_abs_diff": onnx_main["max_abs_diff"], "runtime": onnx_main["runtime"],
            "per_model": {"main": onnx_main["per_model"]}, "converters": onnx_main["converters"], "opset": {"": 15, "ai.onnx.ml": 3}}
    for j, (yr, (sc, st, held)) in enumerate(sorted(loyo_models.items())):
        cb(PHASES[3], 1 + j, 1 + len(loyo_models))
        o = train.export_onnx(Path(models_dir) / ("loyo_%d" % yr), sc, st, Xk[held])
        onnx["files"] += o["files"]
        onnx["per_model"]["loyo_%d" % yr] = {**o["per_model"], "status": o["status"]}
        if o["max_abs_diff"] is not None:
            onnx["max_abs_diff"] = max(onnx["max_abs_diff"] or 0.0, o["max_abs_diff"])
        if not o["status"].startswith("ok"):
            onnx["status"] += " · loyo_%d: %s" % (yr, o["status"])
    for key in list(models["loyo"]):
        models["loyo"][key]["files"] = sorted(p.name for p in (Path(models_dir) / ("loyo_%s" % key)).iterdir())
    models["main"]["files"] = sorted(p.name for p in main_dir.iterdir())
    cb(PHASES[3], 1 + len(loyo_models), 1 + len(loyo_models))
    timings["onnx"] = round(time.time() - t0, 1)
    if not onnx["status"].startswith("ok"):
        notes.append("ONNX: " + onnx["status"])

    # ---- trading translation
    t0 = time.time()
    cb(PHASES[4], 0, 1)
    trading = report.translate(E, k15, P)
    for nm in ("B", "universe"):
        if trading.get(nm):
            _log("%s: %d trades, %d without an OOF row; P>%g keeps %d" % (nm, trading[nm]["all"]["total"]["n"], trading[nm]["no_oof"], THRESHOLD,
                                                                           trading[nm]["at"]["%g" % THRESHOLD]["total"]["n"]))
    cb(PHASES[4], 1, 1)
    timings["trading"] = round(time.time() - t0, 1)
    # how far the OOF probabilities reach on EVERY bar (not only the EA's entries) - the gate is dead if 0.75 is never reached
    reach = {"max_p_up": round(float(P[:, train.UP].max()), 4), "max_p_down": round(float(P[:, train.DN].max()), 4),
             "bars_p_up_gt": {("%g" % t): int((P[:, train.UP] > t).sum()) for t in report.THRESHOLDS},
             "bars_p_down_gt": {("%g" % t): int((P[:, train.DN] > t).sum()) for t in report.THRESHOLDS}}
    oof["reach"] = reach
    n_up, n_dn = reach["bars_p_up_gt"]["%g" % THRESHOLD], reach["bars_p_down_gt"]["%g" % THRESHOLD]
    notes.append("the gate P > %g is reached out-of-fold on %d bars for BUY and %d for SELL of %d (max OOF P(up) %.3f, P(down) %.3f)%s" % (
        THRESHOLD, n_up, n_dn, n, reach["max_p_up"], reach["max_p_down"],
        " - at this threshold the EA would take NO trade; the first threshold that lets anything through is the honest one to read" if n_up + n_dn == 0 else ""))
    lead = ", ".join(t["name"] for t in sh["ranking"][:4])
    notes.append("where the lift lives: AUC of the no-touch class %.3f vs direction up %.3f / down %.3f; the SHAP leaders are %s - the model mostly tells quiet bars "
                 "(no barrier in 24 bars) from active ones, and only weakly which barrier comes first" % (oof.get("auc_none") or 0, oof.get("auc_up") or 0, oof.get("auc_down") or 0, lead))

    # ---- the extra: Combinatorial Purged CV on one base learner
    cpcv_block, cpcv_rows = None, None
    if cpcv:
        t0 = time.time()
        phase = PHASES[1] + " (combinatorial extra)"
        cp = CombinatorialPurgedCV(CPCV_GROUPS, CPCV_TEST, EMBARGO)
        splits = cp.split(k15, touch_k)
        blocks = cp.groups(n)
        learner = L[-1]                                  # base learner 2 (CatBoost or its XGBoost stand-in) - the stack would cost 12x
        preds = []
        for s, (tr, te) in enumerate(splits):
            cb(phase, s, len(splits))
            est = train.learners(n_jobs, train.SEED, n_trees)[-1]["est"]
            sc = train.StandardScaler().fit(Xk[tr])
            with train._limits(n_jobs):
                est.fit(sc.transform(Xk[tr]).astype(np.float32), y[tr])
            preds.append(est.predict_proba(sc.transform(Xk[te]).astype(np.float32)))
        path_rows = []
        for p_i, members in enumerate(cp.paths()):
            Pp = np.full((n, 3), np.nan)
            for s, g in members:
                te = splits[s][1]
                pos = {int(v): i for i, v in enumerate(te)}
                b = blocks[g]
                Pp[b] = preds[s][[pos[int(v)] for v in b]]
            ok = np.isfinite(Pp[:, 0])
            r = {"path": p_i + 1, **train.metrics(y[ok], Pp[ok])}
            path_rows.append(r)
        cb(phase, len(splits), len(splits))
        ll = np.array([r["logloss"] for r in path_rows])
        au = np.array([r["auc_up"] for r in path_rows], dtype=float)
        ad = np.array([r["auc_down"] for r in path_rows], dtype=float)
        cpcv_block = {"groups": CPCV_GROUPS, "test_groups": CPCV_TEST, "splits": len(splits), "paths": len(path_rows), "embargo_bars": EMBARGO,
                      "model": "%s alone (base learner 2) on the scaled kept features - not the full stack" % learner["name"],
                      "logloss_mean": round(float(ll.mean()), 4), "logloss_std": round(float(ll.std()), 4), "logloss_worst_path": round(float(ll.max()), 4),
                      "acc_mean": round(float(np.mean([r["acc"] for r in path_rows])), 4),
                      "auc_up_mean": round(float(np.nanmean(au)), 4), "auc_up_std": round(float(np.nanstd(au)), 4), "auc_up_min": round(float(np.nanmin(au)), 4),
                      "auc_down_mean": round(float(np.nanmean(ad)), 4), "auc_down_std": round(float(np.nanstd(ad)), 4), "auc_down_min": round(float(np.nanmin(ad)), 4),
                      "baseline_logloss": round(baseline, 4), "secs": round(time.time() - t0, 1)}
        cpcv_rows = {"paths": path_rows, "splits": [{"split": s + 1, "test_groups": [g + 1 for g in c], "n_train": int(len(tr)), "n_test": int(len(te))}
                                                    for s, (c, (tr, te)) in enumerate(zip(cp.combos(), splits))]}
        timings["cpcv"] = round(time.time() - t0, 1)

    # ---- the results file
    for d_ in L:
        d_.pop("est", None)
    if any(d_["substitute"] for d_ in L):
        notes.append("LightGBM / CatBoost have no ARM64 wheels on this laptop: %s stood in; an x64 machine runs the real ones (the code prefers them when importable)"
                     % " and ".join("%s for %s" % (d_["name"], d_["role"]) for d_ in L if d_["substitute"]))
    notes.append("SHAP: %s" % sh["method"])
    notes.append("spread_pts is excluded from training (use_spread=false); volume is excluded on purpose (the Strategy Tester overwrites tick volume)")
    if len(names) != 86:
        notes.append("FEATURE_SPEC.md's table has %d columns although its text says 86; the pipeline uses the dataset's names (len(names)) everywhere" % len(names))
    notes.append("the OOF probabilities are nested: for each of the %d outer purged folds the whole stack (scaler, base learners with their own inner purged folds, "
                 "meta-learner) was fitted on the training rows only; the trading translation and the calibration table use them" % FOLDS)
    notes.append("every P&L / WR here is a Turtle TV Tester hypothesis (CLAUDE.md): only MT5's Strategy Tester promotes - the MT5 step fills 'mt5'")
    timings["total"] = round(time.time() - T0, 1)
    res = {"built": datetime.now().isoformat(timespec="seconds"),
           "settings": {"barriers": BARRIERS, "embargo_bars": EMBARGO, "folds": FOLDS, "cpcv": cpcv_block, "features_all": len(names), "features_kept": len(kept),
                        "kept": kept, "base_learners": [{k: v for k, v in d_.items() if k != "key"} for d_ in L], "meta": "LogisticRegression",
                        "meta_params": {"C": 1.0, "max_iter": 2000}, "threshold": THRESHOLD, "use_spread": USE_SPREAD, "shap_method": sh["method"],
                        "n_trees": n_trees, "n_jobs": n_jobs, "seed": train.SEED, "quick": bool(quick)},
           "data": data_block,
           "cv": {"folds": fold_rows, "oof": oof, "calibration": cal, "calibration_down": cal_dn, "baseline_logloss": baseline, "purge": purge_rows, "cpcv": cpcv_rows},
           "shap": {"method": sh["method"], "top": sh["ranking"], "kept": kept, "dropped": sh["dropped"], "rule": sh["rule"], "stability": sh["stability"],
                    "booster": sh["booster"], "threshold": sh["threshold"], "per_fold": sh["per_fold"], "secs": sh["secs"]},
           "trading": trading, "onnx": onnx, "models": models, "mt5": None, "timings": timings, "versions": _versions(), "notes": notes}
    res = _jsonable(res)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    _log("wrote %s (%.0f s)" % (_rel(out), timings["total"]))
    return res


def summary(res):
    """the numbers worth a glance after a run"""
    o, s, t = res["cv"]["oof"], res["settings"], res["trading"]
    lines = ["kept %d/%d features | OOF logloss %.4f vs baseline %.4f | acc %.3f | AUC up %.3f down %.3f none %.3f" % (
        s["features_kept"], s["features_all"], o["logloss"], res["cv"]["baseline_logloss"], o["acc"], o["auc_up"] or 0, o["auc_down"] or 0, o.get("auc_none") or 0)]
    for nm in ("B", "universe"):
        if t.get(nm):
            a, at = t[nm]["all"]["total"], t[nm]["at"]["%g" % s["threshold"]]["total"]
            lines.append("%s: all %d | %.1f%% | %.0f  ||  P>%g: %d | %.1f%% | %.0f  (no OOF row: %d)" % (nm, a["n"], a["wr"], a["net"], s["threshold"], at["n"], at["wr"], at["net"], t[nm]["no_oof"]))
    lines.append("ONNX: %s | max|diff| %s" % (res["onnx"]["status"], res["onnx"]["max_abs_diff"]))
    if s.get("cpcv"):
        lines.append("CPCV: logloss %.4f +- %.4f | AUC up %.3f | down %.3f over %d paths" % (s["cpcv"]["logloss_mean"], s["cpcv"]["logloss_std"], s["cpcv"]["auc_up_mean"], s["cpcv"]["auc_down_mean"], s["cpcv"]["paths"]))
    lines.append("timings: " + ", ".join("%s %.0fs" % kv for kv in res["timings"].items()))
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="smoke run: last 30,000 rows, 40 trees (writes wherever --out / --models point)")
    ap.add_argument("--no-cpcv", action="store_true")
    ap.add_argument("--jobs", type=int, default=None)
    ap.add_argument("--trees", type=int, default=None)
    ap.add_argument("--out", default=str(RESULTS))
    ap.add_argument("--models", default=str(MODELS))
    ap.add_argument("--features-json", default=str(FEATURES))
    a = ap.parse_args(argv)
    res = run(out=a.out, models_dir=a.models, features_json=a.features_json, n_jobs=a.jobs, quick=a.quick, cpcv=not a.no_cpcv, n_trees=a.trees)
    print(summary(res))
    return res


if __name__ == "__main__":
    main()
