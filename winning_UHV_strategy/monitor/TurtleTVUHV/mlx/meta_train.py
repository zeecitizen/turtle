"""mlx/meta_train.py - META-LABELLING of the strategy's own trades with gradient boosting (agent T, tabular).

The if-else strategy (setting C with every hand entry-filter OFF = UNIVERSE-C, 12,579 trades) proposes setup + side; the model learns
P(this trade WINS) from simdata/mlx_meta.npz: the 75 strategy-state features of the setup (meta_features.py) + the 85 per-bar features of
the last closed bar + side. Every out-of-sample number is LEAVE-ONE-YEAR-OUT: hold out one calendar year by entry_t (Dec 29-30 2022's 27
trades fold into 2023), train on the other years minus a 2-day embargo on both sides of the held-out year and minus every training trade
whose exit_t falls inside the held-out window; hyper-parameters are tuned on an INNER leave-one-training-year-out split (never on the
held-out year) and the Platt calibration, when used, is fitted on the inner out-of-fold predictions only.

Learners: XGBoost (hist) and sklearn HistGradientBoosting; feature sets full (setup + bar + side), bar-only (no setup-state block), setup-only,
time-only (hour, dow, bar_of_day, side - the baseline the ML must beat); class weights plain and balanced (losses up-weighted to the wins'
mass). Common evaluation: pooled OOS AUC / log-loss vs the class-frequency baseline; the frontier (thresholds on P and top-N by P) with
n / WR / net / worst / full stops per held-out year and pooled; baselines (random subset, time-only model, setting C in-sample); the score of
C's own trades vs the trades C rejected; permutation importance (OOS). Best configuration -> ONNX (opset 15 / ai.onnx.ml 3, zipmap off,
one model with side as a feature) into simdata/mlx_meta_models/main and loyo_<year> with a meta.json for the MQL5 side.

Outputs: simdata/mlx_meta_results_tab.json, simdata/mlx_meta_pred_tab.npz (P, entry_t, side, src, year, pnl, y), simdata/mlx_meta_models/**.
CLI: py -m mlx.meta_train [--quick] [--no-export] [--jobs 6]     (from monitor/saad_view)
CLAUDE.md: every P&L / WR here is a Turtle TV Tester hypothesis; MT5's Strategy Tester promotes, nothing else."""
import argparse
import json
import pickle
import sys
import time
import warnings
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIEW = HERE.parent
if str(VIEW) not in sys.path:
    sys.path.insert(0, str(VIEW))
import numpy as np                                                       # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier              # noqa: E402
from sklearn.linear_model import LogisticRegression                      # noqa: E402
from sklearn.metrics import log_loss, roc_auc_score                      # noqa: E402

from mlx.train import to_onnx, _ort_probs                                # noqa: E402

SIMDATA = VIEW / "simdata"
META = SIMDATA / "mlx_meta.npz"
OUT_JSON = SIMDATA / "mlx_meta_results_tab.json"
OUT_NPZ = SIMDATA / "mlx_meta_pred_tab.npz"
MODELS = SIMDATA / "mlx_meta_models"
SEED = 1
EMBARGO_S = 2 * 86400
FULL_STOP = -4000.0
YEARS = (2023, 2024, 2025, 2026)
THRS = (0.90, 0.93, 0.95, 0.96, 0.97, 0.98, 0.985, 0.99)
TOPS = (800, 1000, 1200, 1615, 2000, 2500, 3000, 4000)
DROP_SETUP = ("on_fast", "stop_pips", "stop_usd", "tp_over_stop", "buy_rule")      # constant / duplicates of side (meta_features problems list)
TIME_ONLY = ("hour", "dow", "bar_of_day", "side")
# the feature family setting C's hand filters read (EMA gap / alignment / slow-EMA slope / price side, chop ER, ADX, ATR, spread, session, dow, positions, day P&L)
HAND = ("e_gap_pips", "e_gap_atr", "e_align_rel", "s_align_rel", "s_c_es_rel", "s_es_slope4_rel", "s_es_slope16_rel", "s_ef_slope16_rel", "s_chop_er10", "s_chop_er16",
        "s_chop_er20", "s_adx", "s_atr_r_e", "spread_pts", "hour", "dow", "n_open", "n_open_same", "n_open_opp", "day_pnl", "day_closed_n", "side")
# setting C, in-sample (Zee's standard, 2026-11-01), Turtle TV Tester
C_STANDARD = {"n": 1615, "wr": 0.9715, "net": 402831.0, "pf": 2.79, "worst": -5574.0, "full_stops": 43,
              "per_year": {"2023": {"n": 256, "wr": 0.9727, "net": 64757.0}, "2024": {"n": 432, "wr": 0.9722, "net": 107117.0},
                           "2025": {"n": 498, "wr": 0.9639, "net": 97680.0}, "2026": {"n": 424, "wr": 0.9788, "net": 130927.0}},
              "note": "IN-SAMPLE: hand-optimised on these four years; 5 trades of Dec 29-30 2022 (+$2,350) sit outside the per-year rows"}

XGB_GRID = [dict(max_depth=d, min_child_weight=w, n_estimators=n, learning_rate=0.03, subsample=0.8, colsample_bytree=0.7, reg_lambda=2.0)
            for d, w, n in ((3, 50, 400), (4, 20, 400), (4, 50, 600), (4, 100, 600), (6, 50, 400), (6, 200, 600))]
HGB_GRID = [dict(max_leaf_nodes=l, min_samples_leaf=m, max_iter=n, learning_rate=0.03, l2_regularization=1.0)
            for l, m, n in ((8, 50, 400), (15, 50, 400), (15, 100, 600), (31, 100, 400), (31, 200, 600), (63, 200, 600))]


def _limits(n_jobs):
    try:
        from threadpoolctl import threadpool_limits
        return threadpool_limits(limits=int(n_jobs))
    except Exception:                                   # noqa: BLE001
        import contextlib
        return contextlib.nullcontext()


# ---------------------------------------------------------------- data
def load():
    z = np.load(META, allow_pickle=False)
    d = {k: z[k] for k in z.files}
    d["setup_names"] = [str(v) for v in d["setup_names"]]
    d["bar_names"] = [str(v) for v in d["bar_names"]]
    d["yfold"] = np.where(d["year"] <= 2023, 2023, d["year"]).astype(np.int64)
    X = np.hstack([d["X_setup"], d["X_bar"]]).astype(np.float32)
    names = d["setup_names"] + d["bar_names"]
    # X_bar of the 92 rows without a dataset row: whatever meta_features wrote there (0) stays - the EA always has live bars
    d["X_all"], d["names_all"] = X, names
    d["nan_cells"] = int(np.isnan(X).sum() + np.isinf(X).sum())
    X[~np.isfinite(X)] = 0.0
    return d


def feature_sets(names_all, setup_names):
    """-> {set name: [column indices]}; 'side' lives in the setup block and is appended to every set"""
    idx = {n: i for i, n in enumerate(names_all)}
    setup = [idx[n] for n in setup_names if n not in DROP_SETUP]
    bar = [idx[n] for n in names_all if n not in setup_names] + [idx["side"]]
    full = sorted(set(setup) | set(bar))
    time_only = [idx[n] for n in TIME_ONLY]
    hand = [idx[n] for n in HAND]
    return {"full": full, "bar": bar, "setup": setup, "time": time_only, "hand": hand}


def loyo_split(entry_t, exit_t, yfold, year):
    """test = the held-out year; train = the others minus the 2-day embargo on entry_t and minus trades whose exit_t falls in the window"""
    te = yfold == year
    lo, hi = int(entry_t[te].min()) - EMBARGO_S, int(entry_t[te].max()) + EMBARGO_S
    tr = ~te & ~((entry_t >= lo) & (entry_t <= hi)) & ~((exit_t >= lo) & (exit_t <= hi))
    return np.nonzero(tr)[0], np.nonzero(te)[0]


# ---------------------------------------------------------------- learners
def make(learner, params, n_jobs):
    if learner == "xgb":
        import xgboost as xgb
        return xgb.XGBClassifier(tree_method="hist", objective="binary:logistic", n_jobs=n_jobs, random_state=SEED, verbosity=0, **params)
    return HistGradientBoostingClassifier(early_stopping=False, random_state=SEED, **params)


def weights(y, balanced):
    if not balanced:
        return None
    w = np.ones(len(y), dtype=np.float64)
    w[y == 0] = (y == 1).sum() / max(1, (y == 0).sum())                   # the losses carry the wins' total mass
    return w


def fit(learner, params, X, y, w, n_jobs):
    m = make(learner, params, n_jobs)
    with _limits(n_jobs), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit(X, y, sample_weight=w)
    return m


def proba(m, X):
    return np.clip(m.predict_proba(X)[:, 1], 1e-6, 1 - 1e-6)


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


class Platt:
    """p_cal = sigmoid(a * logit(p) + b), fitted on inner out-of-fold predictions (the EA can apply it from meta.json)"""

    def __init__(self):
        self.a, self.b = 1.0, 0.0

    def fit(self, p, y):
        lr = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(p).reshape(-1, 1), y)
        self.a, self.b = float(lr.coef_[0, 0]), float(lr.intercept_[0])
        return self

    def apply(self, p):
        return 1.0 / (1.0 + np.exp(-(self.a * _logit(p) + self.b)))

    def json(self):
        return {"type": "platt_on_logit", "a": self.a, "b": self.b, "rule": "p_cal = 1 / (1 + exp(-(a * ln(p / (1 - p)) + b)))"}


def inner_oof(learner, params, X, y, w, entry_t, exit_t, yfold, n_jobs):
    """leave-one-TRAINING-year-out predictions inside the training rows (same purge + embargo) -> P_inner (NaN where a year has one fold)"""
    P = np.full(len(y), np.nan)
    yrs = [Y for Y in np.unique(yfold) if (yfold == Y).sum() >= 100]
    if len(yrs) < 2:
        return P
    for Y in yrs:
        tr, te = loyo_split(entry_t, exit_t, yfold, Y)
        if len(tr) < 500 or y[tr].min() == y[tr].max():
            continue
        m = fit(learner, params, X[tr], y[tr], None if w is None else w[tr], n_jobs)
        P[te] = proba(m, X[te])
    return P


def tune(learner, grid, X, y, w, entry_t, exit_t, yfold, n_jobs, log):
    """inner purged LOYO log-loss per grid row -> (best params, table). Never sees the outer held-out year."""
    rows = []
    for params in grid:
        P = inner_oof(learner, params, X, y, w, entry_t, exit_t, yfold, n_jobs)
        ok = ~np.isnan(P)
        ll = float(log_loss(y[ok], P[ok])) if ok.sum() else np.inf
        auc = float(roc_auc_score(y[ok], P[ok])) if ok.sum() and 0 < y[ok].sum() < ok.sum() else None
        rows.append({"params": params, "inner_logloss": ll, "inner_auc": auc, "n_inner": int(ok.sum())})
        log("    %s %s inner ll %.4f auc %s" % (learner, params, ll, "%.4f" % auc if auc else "-"))
    # balanced weights distort the probability scale: pick by inner AUC there, by log-loss when plain
    key = (lambda r: -(r["inner_auc"] or 0)) if w is not None else (lambda r: r["inner_logloss"])
    best = min(rows, key=key)
    return best["params"], rows


# ---------------------------------------------------------------- the LOYO run
def run_loyo(d, U, cols, learner, grid, balanced, n_jobs, log, tuned=None, calibrate=True):
    """-> dict(P_raw, P_cal, per_fold [{year, params, n_train, ...}], models {year: (model, platt)})"""
    X = d["X_all"][:, cols]
    y = d["y_win"].astype(int)
    entry_t, exit_t, yfold = d["entry_t"], d["exit_t"], d["yfold"]
    train_ok = (d["same_tick_exit"] == 0) & (d["setup_ok"] == 1)        # same-second fills / the 74-bar setup: never trained on
    n = len(y)
    P_raw = np.full(n, np.nan)
    P_cal = np.full(n, np.nan)
    folds, models = [], {}
    for Y in YEARS:
        t0 = time.time()
        trU, teU = loyo_split(entry_t[U], exit_t[U], yfold[U], Y)
        tr = U[trU]
        tr = tr[train_ok[tr]]
        te_all = np.nonzero(d["yfold"] == Y)[0]                            # every row of the year, universe AND C, scored by this model
        w = weights(y[tr], balanced)
        if tuned is not None and Y in tuned:
            params, table = tuned[Y], None
        else:
            params, table = tune(learner, grid, X[tr], y[tr], w, entry_t[tr], exit_t[tr], yfold[tr], n_jobs, log)
        m = fit(learner, params, X[tr], y[tr], w, n_jobs)
        p_te = proba(m, X[te_all])
        P_raw[te_all] = p_te
        platt = None
        if calibrate:
            Pin = inner_oof(learner, params, X[tr], y[tr], w, entry_t[tr], exit_t[tr], yfold[tr], n_jobs)
            ok = ~np.isnan(Pin)
            if ok.sum() > 200:
                platt = Platt().fit(Pin[ok], y[tr][ok])
        P_cal[te_all] = platt.apply(p_te) if platt else p_te
        teU_rows = U[teU]
        r = {"year": int(Y), "params": params, "n_train": int(len(tr)), "n_test_universe": int(len(teU)), "secs": round(time.time() - t0, 1),
             "auc_raw": float(roc_auc_score(y[teU_rows], P_raw[teU_rows])), "logloss_raw": float(log_loss(y[teU_rows], P_raw[teU_rows])),
             "logloss_cal": float(log_loss(y[teU_rows], P_cal[teU_rows])), "baseline_logloss": float(log_loss(y[teU_rows], np.full(len(teU_rows), y[tr].mean()))),
             "platt": platt.json() if platt else None, "tuning": table}
        folds.append(r)
        models[int(Y)] = (m, platt, params)
        log("  LOYO %d: train %d test %d auc %.4f ll raw %.4f cal %.4f base %.4f (%ss)" % (Y, len(tr), len(teU), r["auc_raw"], r["logloss_raw"], r["logloss_cal"], r["baseline_logloss"], r["secs"]))
    return {"P_raw": P_raw, "P_cal": P_cal, "folds": folds, "models": models}


# ---------------------------------------------------------------- evaluation
def _stats(pnl, y):
    n = int(len(pnl))
    return {"n": n, "wr": round(float(y.mean()), 4) if n else None, "net": round(float(pnl.sum()), 0), "worst": round(float(pnl.min()), 0) if n else None,
            "full_stops": int((pnl <= FULL_STOP).sum())}


def frontier(P, y, pnl, yfold, label_extra=None):
    rows = []
    for thr in THRS:
        k = P >= thr
        r = {"kind": "thr", "value": thr, **_stats(pnl[k], y[k]), "per_year": {str(Y): _stats(pnl[k & (yfold == Y)], y[k & (yfold == Y)]) for Y in YEARS}}
        rows.append(r)
    o = np.argsort(-P, kind="stable")
    for N in TOPS:
        s = o[:N]
        k = np.zeros(len(P), bool)
        k[s] = True
        r = {"kind": "top", "value": N, **_stats(pnl[k], y[k]), "min_p": round(float(P[s].min()), 4),
             "per_year": {str(Y): _stats(pnl[k & (yfold == Y)], y[k & (yfold == Y)]) for Y in YEARS}}
        rows.append(r)
    return rows


def pooled_oos(P, y):
    return {"auc": round(float(roc_auc_score(y, P)), 4), "logloss": round(float(log_loss(y, P)), 4),
            "baseline_logloss": round(float(log_loss(y, np.full(len(y), y.mean()))), 4), "n": int(len(y)), "wr": round(float(y.mean()), 4)}


def random_baseline(y, pnl, yfold, rng, draws=300):
    out = {"note": "random subset of the universe, same size: expected WR = universe WR; %d Monte-Carlo draws" % draws, "rows": []}
    n_all = len(y)
    for N in TOPS:
        wr, net, worst, fs = [], [], [], []
        for _ in range(draws):
            s = rng.choice(n_all, N, replace=False)
            wr.append(y[s].mean()); net.append(pnl[s].sum()); worst.append(pnl[s].min()); fs.append((pnl[s] <= FULL_STOP).sum())
        out["rows"].append({"kind": "top", "value": N, "n": N, "wr": round(float(np.mean(wr)), 4), "wr_p5": round(float(np.percentile(wr, 5)), 4),
                            "wr_p95": round(float(np.percentile(wr, 95)), 4), "net": round(float(np.mean(net)), 0), "worst": round(float(np.mean(worst)), 0),
                            "full_stops": round(float(np.mean(fs)), 1),
                            "per_year": {str(Y): {"n": int(round(N * (yfold == Y).mean())), "wr": round(float(y[yfold == Y].mean()), 4),
                                                  "net": round(float(N * (yfold == Y).mean() * pnl[yfold == Y].mean()), 0)} for Y in YEARS}})
    return out


def c_scores(d, U, P, y, pnl, yfold):
    """(d): do C's own trades get a high P? what does the top-1615 reach on the trades C rejected?"""
    C = np.nonzero(d["src"] == 0)[0]
    keyU = {(int(k), int(s)): i for i, (k, s) in enumerate(zip(d["k15"][U], d["side"][U]))}
    inC = np.zeros(len(U), bool)
    for i in C:
        j = keyU.get((int(d["k15"][i]), int(d["side"][i])))
        if j is not None:
            inC[j] = True
    PC_direct = P[C]                                                         # C's rows scored by the LOYO model of their year
    o = np.argsort(-P[U], kind="stable")
    top = np.zeros(len(U), bool)
    top[o[:1615]] = True
    rej = ~inC
    out = {"c_trades": int(len(C)), "c_matched_in_universe": int(inC.sum()), "match_rule": "same entry bar k15 and side; the other C trades have no universe twin (the universe's one-pending-setup queue or its 8-position cap changed the sequence)",
           "p_c_matched_mean": round(float(P[U][inC].mean()), 4), "p_c_matched_median": round(float(np.median(P[U][inC])), 4),
           "p_rejected_mean": round(float(P[U][rej].mean()), 4), "p_rejected_median": round(float(np.median(P[U][rej])), 4),
           "p_c_rows_direct_mean": round(float(PC_direct.mean()), 4),
           "auc_is_c_trade": round(float(roc_auc_score(inC.astype(int), P[U])), 4),
           "c_matched_in_top1615": int((inC & top).sum()), "c_matched_share_in_top1615": round(float((inC & top).sum() / max(1, inC.sum())), 4),
           "c_matched_stats": _stats(pnl[inC], y[inC]), "rejected_stats": _stats(pnl[rej], y[rej]),
           "top1615_on_rejected": _stats(pnl[top & rej], y[top & rej]), "top1615_on_c": _stats(pnl[top & inC], y[top & inC]),
           "rejected_by_threshold": {str(t): _stats(pnl[rej & (P[U] >= t)], y[rej & (P[U] >= t)]) for t in THRS},
           "c_matched_by_threshold": {str(t): _stats(pnl[inC & (P[U] >= t)], y[inC & (P[U] >= t)]) for t in THRS},
           "c_matched_per_year": {str(Y): _stats(pnl[inC & (yfold == Y)], y[inC & (yfold == Y)]) for Y in YEARS}}
    return out, inC


def permutation_importance(d, U, cols, names, models, n_jobs, rng, n_top=30):
    """OOS: for each held-out year, permute one column of the test rows, AUC drop of that year's model; averaged over the years"""
    X = d["X_all"][U][:, cols]
    y = d["y_win"][U].astype(int)
    yfold = d["yfold"][U]
    drops = np.zeros((len(YEARS), len(cols)))
    for yi, Y in enumerate(YEARS):
        m, platt, _ = models[Y]
        te = yfold == Y
        Xt = X[te]
        base = roc_auc_score(y[te], proba(m, Xt))
        for j in range(len(cols)):
            Xp = Xt.copy()
            Xp[:, j] = Xp[rng.permutation(len(Xp)), j]
            drops[yi, j] = base - roc_auc_score(y[te], proba(m, Xp))
    mean = drops.mean(axis=0)
    order = np.argsort(-mean)
    setup_set = set(d["setup_names"])
    block = lambda nm: "time" if nm in TIME_ONLY else ("setup" if nm in setup_set else "bar")   # noqa: E731,E501
    rows = [{"feature": names[j], "block": block(names[j]), "auc_drop_mean": round(float(mean[j]), 5),
             "auc_drop_per_year": {str(Y): round(float(drops[yi, j]), 5) for yi, Y in enumerate(YEARS)}} for j in order[:n_top]]
    by_block = {}
    for j, nm in enumerate(names):
        by_block.setdefault(block(nm), []).append(float(mean[j]))
    return {"method": "permutation importance, OOS (held-out year's rows, that year's LOYO model), AUC drop averaged over the 4 years",
            "top": rows, "block_sum_of_drops": {k: round(float(np.sum(v)), 4) for k, v in by_block.items()},
            "block_mean_drop": {k: round(float(np.mean(v)), 5) for k, v in by_block.items()}}


# ---------------------------------------------------------------- ONNX
def export_models(d, U, cols, names, learner, best, n_jobs, log, X_check):
    """main (all universe years) + loyo_<year> -> model.onnx + meta.json; verifies onnxruntime vs the python model"""
    MODELS.mkdir(parents=True, exist_ok=True)
    X = d["X_all"][:, cols]
    y = d["y_win"].astype(int)
    train_ok = (d["same_tick_exit"] == 0) & (d["setup_ok"] == 1)
    info = {"dirs": {}, "max_abs_diff": 0.0, "model": "one model for both sides, 'side' (+1 buy / -1 sell) is a feature",
            "opset": {"": 15, "ai.onnx.ml": 3}, "zipmap": False, "outputs": ["label", "probabilities"], "class_order": [0, 1],
            "p_win_column": 1}
    jobs = [("main", None)] + [("loyo_%d" % Y, Y) for Y in YEARS]
    for name, Y in jobs:
        out = MODELS / name
        out.mkdir(parents=True, exist_ok=True)
        if Y is None:
            tr = U[train_ok[U]]
            params = best["main_params"]
            platt = None
            w = weights(y[tr], best["balanced"])
            m = fit(learner, params, X[tr], y[tr], w, n_jobs)
            if best["calibrate"]:
                Pin = inner_oof(learner, params, X[tr], y[tr], w, d["entry_t"][tr], d["exit_t"][tr], d["yfold"][tr], n_jobs)
                ok = ~np.isnan(Pin)
                platt = Platt().fit(Pin[ok], y[tr][ok])
        else:
            m, platt, params = best["models"][Y]
        path = out / "model.onnx"
        try:
            conv = to_onnx(m, len(cols), path)
        except Exception as e:                                             # noqa: BLE001
            info["dirs"][name] = {"status": "FAILED: %s" % str(e)[:300]}
            log("  ONNX %s FAILED %s" % (name, e))
            continue
        Xs = X_check.astype(np.float32)
        po = _ort_probs(path, Xs)[:, 1]
        pp = m.predict_proba(Xs)[:, 1]
        diff = float(np.abs(po - pp).max())
        info["max_abs_diff"] = max(info["max_abs_diff"], diff)
        (out / "model.pkl").write_bytes(pickle.dumps(m))
        meta = {"approach": "meta-labelling: P(win) of a setup+breakout the if-else strategy proposes", "learner": type(m).__name__, "params": params,
                "kept": [names[j] for j in range(len(cols))], "n_in": len(cols), "scaler": None,
                "input": "the kept features in this order, raw float32 [1, n_in] (trees: no scaling); NaN / inf -> 0",
                "onnx_io": {"input": "input", "outputs": ["label", "probabilities"], "probabilities_shape": "[1, 2] = [P(loss), P(win)]"},
                "classes": [0, 1], "p_win": "probabilities[1]", "calibration": platt.json() if platt else None,
                "balanced_weights": bool(best["balanced"]), "trained_on": "UNIVERSE-C trades, all years" if Y is None else "UNIVERSE-C trades, year %d held out (LOYO)" % Y,
                "converter": conv, "onnxruntime_max_abs_diff": diff, "threshold_hint": best.get("threshold_hint"),
                "side_convention": "+1 buy / -1 sell; _rel features already multiplied by side (simdata/mlx_meta_spec.json)",
                "feature_spec": "simdata/mlx_meta_spec.json (setup block) + mlx/FEATURE_SPEC.md (bar block of bar k15-1)",
                "hypothesis": "Turtle TV Tester numbers only; MT5's Strategy Tester promotes"}
        (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        info["dirs"][name] = {"status": "ok", "converter": conv, "bytes": path.stat().st_size, "max_abs_diff": diff, "n_train": int(len(tr)) if Y is None else None}
        log("  ONNX %s: %s, %d bytes, max |ort - py| %.2e" % (name, conv, path.stat().st_size, diff))
    return info


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="one grid row per learner, fewer MC draws")
    ap.add_argument("--no-export", action="store_true")
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args(argv)
    t_start = time.time()
    logs = []

    def log(s):
        print(s, flush=True)
        logs.append(s)

    d = load()
    U = np.nonzero(d["src"] == 1)[0]
    y = d["y_win"].astype(int)
    pnl = d["pnl"]
    yfold = d["yfold"]
    yU, pU, fU = y[U], pnl[U], yfold[U]
    sets = feature_sets(d["names_all"], d["setup_names"])
    log("universe %d trades, WR %.4f, net %.0f; C %d; nan/inf cells zeroed %d; feature sets %s" % (
        len(U), yU.mean(), pU.sum(), (d["src"] == 0).sum(), d["nan_cells"], {k: len(v) for k, v in sets.items()}))
    xgrid = XGB_GRID[:1] if a.quick else XGB_GRID
    hgrid = HGB_GRID[:1] if a.quick else HGB_GRID
    rng = np.random.default_rng(SEED)

    # 1. tuned LOYO on the full set, both learners, plain and balanced  (the tuning happens here; ablations reuse each fold's params)
    variants = {}
    for learner, grid in (("xgb", xgrid), ("hgb", hgrid)):
        for balanced in (False, True):
            key = "%s_full_%s" % (learner, "bal" if balanced else "plain")
            log("== %s" % key)
            res = run_loyo(d, U, sets["full"], learner, grid, balanced, a.jobs, log)
            variants[key] = {"learner": learner, "set": "full", "balanced": balanced, "res": res}
            tuned = {f["year"]: f["params"] for f in res["folds"]}
            for sname in ("bar", "setup", "time", "hand"):
                k2 = "%s_%s_%s" % (learner, sname, "bal" if balanced else "plain")
                log("== %s (params of the full run)" % k2)
                r2 = run_loyo(d, U, sets[sname], learner, grid, balanced, a.jobs, log, tuned=tuned)
                variants[k2] = {"learner": learner, "set": sname, "balanced": balanced, "res": r2}

    # 1b. IN-SAMPLE fit check (pipeline sanity, NOT evidence): one XGBoost on every universe year, scored on the same rows
    train_ok = (d["same_tick_exit"] == 0) & (d["setup_ok"] == 1)
    trI = U[train_ok[U]]
    mI = fit("xgb", XGB_GRID[2], d["X_all"][trI][:, sets["full"]], y[trI], None, a.jobs)
    PI = proba(mI, d["X_all"][U][:, sets["full"]])
    frI = frontier(PI, yU, pU, fU)
    in_sample_check = {"note": "IN-SAMPLE (trained and scored on the same universe rows) - proves the pipeline can fit, says nothing about skill",
                       "auc": round(float(roc_auc_score(yU, PI)), 4), "logloss": round(float(log_loss(yU, PI)), 4),
                       "top1615": {k: v for k, v in next(r for r in frI if r["kind"] == "top" and r["value"] == 1615).items() if k != "per_year"}}
    log("in-sample fit check: %s" % in_sample_check)
    # loss clustering: how many independent loss events the learner really sees
    fsU = pU <= FULL_STOP
    xs = np.sort(d["exit_t"][U][fsU])
    clustering = {"full_stops": int(fsU.sum()), "days_with_full_stop": int(len(np.unique(d["entry_t"][U][fsU] // 86400))),
                  "clusters_1h_by_exit": int(1 + (np.diff(xs) > 3600).sum()), "trading_days": int(len(np.unique(d["entry_t"][U] // 86400))),
                  "median_hold_min_winners": round(float(np.median((d["exit_t"][U] - d["entry_t"][U])[yU == 1]) / 60), 1),
                  "median_hold_min_losers": round(float(np.median((d["exit_t"][U] - d["entry_t"][U])[yU == 0]) / 60), 1)}

    # 2. summary of every variant: pooled OOS + the top-1615 / thr rows that matter
    summary = {}
    for key, v in variants.items():
        res = v["res"]
        for which in ("raw", "cal"):
            P = res["P_" + which][U]
            fr = frontier(P, yU, pU, fU)
            t1615 = next(r for r in fr if r["kind"] == "top" and r["value"] == 1615)
            thr_n = {str(r["value"]): r["n"] for r in fr if r["kind"] == "thr"}
            summary["%s_%s" % (key, which)] = {**pooled_oos(P, yU), "top1615": {k: t1615[k] for k in ("wr", "net", "worst", "full_stops", "min_p")},
                                               "thr_n": thr_n, "per_year_auc": {str(f["year"]): round(f["auc_raw"], 4) for f in res["folds"]}}
    # the ranking criterion: pooled OOS top-1615 net (the standard's trade count) on calibrated P, then AUC
    cands = {k: s for k, s in summary.items() if k.endswith("_cal") and ("_full_" in k or "_bar_" in k)}
    best_key = max(cands, key=lambda k: (cands[k]["top1615"]["net"], cands[k]["auc"]))
    base_key = best_key.replace("_full_", "_%s_" % "time").replace("_bar_", "_time_")
    bk = best_key[:-4]
    bv = variants[bk]
    log("best variant by OOS top-1615 net: %s  (%s)" % (best_key, summary[best_key]))

    # 3. the common evaluation on the best variant
    P_best = bv["res"]["P_cal"]
    fr_best = frontier(P_best[U], yU, pU, fU)
    time_res = variants[base_key[:-4]]["res"]
    fr_time = frontier(time_res["P_cal"][U], yU, pU, fU)
    rnd = random_baseline(yU, pU, fU, rng, draws=100 if a.quick else 300)
    cs, inC = c_scores(d, U, P_best, yU, pU, fU)
    imp = permutation_importance(d, U, sets[bv["set"]], [d["names_all"][j] for j in sets[bv["set"]]], bv["res"]["models"], a.jobs, rng)
    t1615 = next(r for r in fr_best if r["kind"] == "top" and r["value"] == 1615)
    t1615_time = next(r for r in fr_time if r["kind"] == "top" and r["value"] == 1615)
    # the threshold that gives ~1,615 trades
    Pu = P_best[U]
    thr_1615 = float(np.sort(Pu)[::-1][1614])
    beats_time = (t1615["net"] > t1615_time["net"]) and (t1615["wr"] >= t1615_time["wr"])
    rnd_1615 = next(r for r in rnd["rows"] if r["value"] == 1615)
    beats_random = t1615["wr"] > rnd_1615["wr_p95"]                           # outside the 90% band of a random subset of the same size
    usable = bool(beats_time and beats_random)
    # gain importance of the main-style model: use the 2026 fold model (xgb) if available
    gain = None
    m2026 = bv["res"]["models"][2026][0]
    if hasattr(m2026, "feature_importances_"):
        fi = m2026.feature_importances_
        nm = [d["names_all"][j] for j in sets[bv["set"]]]
        gain = [{"feature": nm[j], "gain_share": round(float(fi[j]), 4)} for j in np.argsort(-fi)[:25]]

    # 4. export
    why = "it beats neither" if not (beats_time or beats_random) else ("it beats time-only but sits inside the random band" if beats_time else "it clears the random band but not time-only")
    export = {"status": "not exported: the ML top-1615 must beat BOTH the time-only model and the random band (WR > p95 of a random subset of 1,615) - " + why, "usable": False}
    if usable and not a.no_export:
        params_main = bv["res"]["models"][2026][2]                              # the params the latest fold chose; main refits on all years
        best = {"models": bv["res"]["models"], "main_params": params_main, "balanced": bv["balanced"], "calibrate": True,
                "threshold_hint": {"p_for_1615_trades_pooled_oos": round(thr_1615, 4), "frontier": [{k: r[k] for k in ("kind", "value", "n", "wr", "net", "worst", "full_stops")} for r in fr_best]}}
        X_check = d["X_all"][U][:, sets[bv["set"]]]
        export = export_models(d, U, sets[bv["set"]], d["names_all"], bv["learner"], best, a.jobs, log, X_check)
        export["usable"] = True
    elif usable:
        export = {"status": "skipped (--no-export)", "usable": False}

    # 5. per-year side-by-side: C (in-sample) vs ML top-1615 (OOS) vs time-only top-1615 (OOS)
    side_by_side = {str(Y): {"C_in_sample": C_STANDARD["per_year"][str(Y)], "ml_top1615_oos": t1615["per_year"][str(Y)],
                             "time_only_top1615_oos": t1615_time["per_year"][str(Y)],
                             "universe": _stats(pU[fU == Y], yU[fU == Y])} for Y in YEARS}

    s_best = summary[best_key]
    verdict = ("Meta-labelling the strategy's own trades with %s on %d features (%s block%s): pooled LOYO OOS AUC(win) %.3f, log-loss %.4f vs "
               "class-frequency %.4f. Top-1615 OOS: WR %.1f%%, net $%s, worst $%s, %d full stops (time-only baseline top-1615: WR %.1f%%, net $%s). "
               "Setting C in-sample: 1,615 / 97.2%% / +$402,831 / 43 full stops. %s. All figures Turtle TV Tester hypotheses; MT5 promotes." % (
                   bv["learner"], len(sets[bv["set"]]), bv["set"], ", balanced weights" if bv["balanced"] else "", s_best["auc"], s_best["logloss"], s_best["baseline_logloss"],
                   100 * t1615["wr"], format(int(t1615["net"]), ","), int(t1615["worst"]), t1615["full_stops"], 100 * t1615_time["wr"], format(int(t1615_time["net"]), ","),
                   "The ML beats time-of-day AND the random band at the same count, so it learned something" if usable else
                   "The ML is inside the random-subset band (random top-1615 WR %.1f%% [%.1f, %.1f]) - NO usable entry filter; the win/loss of these setups is not predictable from the state at entry" % (
                       100 * rnd_1615["wr"], 100 * rnd_1615["wr_p5"], 100 * rnd_1615["wr_p95"])))

    out = {
        "approach": "meta-labelling (de Prado): the if-else strategy (UNIVERSE-C = setting C with every hand entry-filter off) proposes setup + side, "
                    "gradient boosting (XGBoost hist / HistGradientBoosting) learns P(win) from 70 setup-state + 85 bar features + side; LOYO with 2-day "
                    "embargo + exit-in-year purge; inner leave-one-training-year-out tuning; Platt calibration fitted on inner OOF",
        "data": {"file": str(META.relative_to(VIEW)).replace("\\", "/"), "universe_n": int(len(U)), "universe_wr": round(float(yU.mean()), 4), "universe_net": round(float(pU.sum()), 0),
                 "universe_full_stops": int((pU <= FULL_STOP).sum()), "universe_worst": round(float(pU.min()), 0),
                 "per_year_universe": {str(Y): _stats(pU[fU == Y], yU[fU == Y]) for Y in YEARS},
                 "year_fold_note": "2023 fold includes the 27 universe (5 C) trades of Dec 29-30 2022",
                 "training_excludes": "same_tick_exit == 1 (89 universe rows) and setup_ok == 0 (1 row); both still scored and counted in the evaluation",
                 "dropped_columns": list(DROP_SETUP), "feature_sets": {k: len(v) for k, v in sets.items()}, "time_only_features": list(TIME_ONLY), "hand_features": list(HAND)},
        "protocol": {"loyo": "hold out one calendar year by entry_t; train on the others minus 2-day embargo on entry_t both sides and minus trades whose exit_t falls in the window",
                     "tuning": "inner leave-one-training-year-out (same purge) over a %d-row grid per learner, chosen by inner log-loss (plain) / inner AUC (balanced)" % len(xgrid),
                     "calibration": "Platt on logit(p), fitted on the inner OOF predictions of the chosen params; applied to the held-out year",
                     "selection_of_best_variant": "pooled OOS net of the top-1615 (calibrated P), ties by AUC - over the full and bar-only sets of both learners"},
        "best_variant": best_key, "time_baseline_variant": base_key,
        "in_sample_fit_check": in_sample_check, "loss_clustering": clustering,
        "oos": {"best": s_best, "all_variants": summary, "per_fold_best": [{k: v for k, v in f.items() if k != "tuning"} for f in bv["res"]["folds"]],
                "tuning_tables_best": [{"year": f["year"], "tuning": f["tuning"]} for f in bv["res"]["folds"]]},
        "frontier": fr_best,
        "threshold_for_1615_trades": round(thr_1615, 4),
        "baselines": {"random": rnd, "time_only_model": {"variant": base_key, "oos": summary[base_key], "frontier": fr_time},
                      "setting_C_in_sample": C_STANDARD, "per_year_side_by_side": side_by_side,
                      "ml_beats_time_only_at_1615": bool(beats_time), "ml_beats_random_band_at_1615": bool(beats_random), "usable": usable},
        "b_scores": cs,
        "features": {"permutation_oos": imp, "gain_2026_fold": gain},
        "export": export,
        "verdict": verdict,
        "notes": [
            "Every WR / P&L here is a Turtle TV Tester hypothesis (real-tick fills in the tester); nothing is promoted until MT5's Strategy Tester confirms it.",
            "Setting C's 1,615 / 97.2% / +$402,831 is IN-SAMPLE (hand-optimised on 2023-2026); the ML rows beside it are out-of-sample (LOYO).",
            "Geometry is fixed: TP 20 pips (+$400 at 2 lots), stop InpSlMode 2 / $26 -> $5,200; nothing here changes the stop or the TP.",
            "The top-N rows rank the pooled calibrated OOS P across the four LOYO models; the threshold rows apply one fixed P to every year (what an EA would do).",
            "The time-only baseline is the same learner / same per-fold params on hour, dow, bar_of_day, side only.",
            "Pooled top-N mixes four different models' probabilities; Platt calibration (fitted on inner OOF) makes them comparable.",
            "Log: " + " | ".join(logs[-6:]),
        ],
        "problems": [],
        "secs": round(time.time() - t_start, 1),
    }
    # honest problem list
    if not usable:
        out["problems"].append("The ML top-1615 OOS (WR %.2f%%) does not clear the random-subset band (p95 %.2f%%) and/or the time-only model - no usable ONNX." % (100 * t1615["wr"], 100 * rnd_1615["wr_p95"]))
    neg = [f["year"] for f in bv["res"]["folds"] if f["platt"] and f["platt"]["a"] < 0]
    if neg:
        out["problems"].append("Platt slope NEGATIVE in folds %s: the inner-year OOF predictions were anti-correlated with the outcome (year-specific patterns reverse) - anti-learning, not weak learning." % neg)
    if s_best["auc"] < 0.6:
        out["problems"].append("Pooled OOS AUC(win) %.3f is weak: the setups' win/loss is mostly not predictable from the state at entry." % s_best["auc"])
    if t1615["wr"] < 0.972:
        out["problems"].append("Top-1615 OOS WR %.1f%% is below setting C's 97.2%% (in-sample) - the ML does not reproduce the hand filters out of sample." % (100 * t1615["wr"]))
    same_tick_in_top = int(d["same_tick_exit"][U][np.argsort(-Pu, kind="stable")[:1615]].sum())
    if same_tick_in_top:
        out["problems"].append("%d of the ML's top-1615 trades are same-second tester fills (same_tick_exit=1) whose outcome MT5 may not reproduce." % same_tick_in_top)
    OUT_JSON.write_text(json.dumps(out, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)), encoding="utf-8")
    np.savez(OUT_NPZ, P=P_best.astype(np.float64), P_raw=bv["res"]["P_raw"].astype(np.float64), P_time=time_res["P_cal"].astype(np.float64),
             entry_t=d["entry_t"], side=d["side"], src=d["src"], year=yfold, pnl=pnl, y=y, k15=d["k15"], in_c_universe_mask=inC,
             variant=np.array(best_key))
    log("wrote %s and %s in %.0fs" % (OUT_JSON, OUT_NPZ, time.time() - t_start))
    return out


if __name__ == "__main__":
    main()
