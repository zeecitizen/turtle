"""ml.py - the Machine Learning tab of the Turtle TV Tester (Zee 2026-10-21: "create a new machine learning section ... We already tried ML algos.
Give access to them here. We should be able to run an ML algo and see its winrate. have all types of ML algos").

What it does (meta-labelling, the approach of VSISA's ML filters): the EA keeps finding its setups; a model learns, from what was known at the
entry (the last closed candle, the setup candle, the EMAs, ADX, ATR, the hour...), whether THAT trade will win. Only the trades the model trusts
are taken. Trained on the first half, judged on the unseen half - the only number that counts. Python, so a hypothesis until MT5 runs it."""
import os
import threading
import time
from datetime import datetime, timezone

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np  # noqa: E402

import exitlab  # noqa: E402
import sim  # noqa: E402

FEATS = ["BUY (1) / SELL (0)", "hour", "weekday", "ADX", "ATR ($)", "ATR vs its 96-candle mean", "stop distance (R) in ATR", "setup candle range / ATR",
         "setup candle body / range", "upper wick / range", "lower wick / range", "close vs fast EMA (ATR)", "close vs slow EMA (ATR)", "fast - slow EMA (ATR)",
         "slow EMA slope, 8 candles (ATR)", "return of the last 4 candles (ATR)", "return of the last 16 candles (ATR)", "return of the last 96 candles (ATR)",
         "position in the 7-candle range", "range box", "spread ($)"]


def _algos():
    from sklearn.ensemble import (AdaBoostClassifier, ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier)
    from sklearn.linear_model import LogisticRegression
    from sklearn.naive_bayes import GaussianNB
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    from sklearn.tree import DecisionTreeClassifier
    out = {
        "Logistic regression": lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000)),
        "Decision tree": lambda: DecisionTreeClassifier(max_depth=4, min_samples_leaf=25, random_state=1),
        "Random forest": lambda: RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=15, random_state=1, n_jobs=-1),
        "Extra trees": lambda: ExtraTreesClassifier(n_estimators=300, max_depth=6, min_samples_leaf=15, random_state=1, n_jobs=-1),
        "Gradient boosting (sklearn)": lambda: HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=25, random_state=1),
        "AdaBoost": lambda: AdaBoostClassifier(n_estimators=150, learning_rate=0.5, random_state=1),
        "k-nearest neighbours": lambda: make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=41)),
        "Naive Bayes": lambda: make_pipeline(StandardScaler(), GaussianNB()),
        "Support vector machine": lambda: make_pipeline(StandardScaler(), SVC(C=0.5, probability=True, random_state=1)),
        "Neural network (MLP)": lambda: make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-2, max_iter=600, early_stopping=True, random_state=1)),
    }
    try:
        from xgboost import XGBClassifier
        out["XGBoost"] = lambda: XGBClassifier(n_estimators=250, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, eval_metric="logloss", random_state=1, n_jobs=4)
    except Exception:                                             # noqa: BLE001
        pass
    return out


ALGOS = list(_algos().keys())


def dataset(inputs, ds):
    """one row per trade of the EA: what was known at the entry -> did it win"""
    tr, setups, _ = sim.simulate(inputs, ds=ds)
    real = tr[tr[:, 10] == 0]
    D = sim.data(ds)
    P, _, _ = sim.pvec_all(inputs)
    ef, es = sim.emas(P[0], P[1], ds)
    o, h, l, c, atr, adx = D["o15"], D["h15"], D["l15"], D["c15"], D["atr"], D["adx"]
    sp = D["sp1"]
    rows, meta = [], []
    for x in real:
        k = int(x[11])
        i = k - 1                                                 # the last closed candle at the entry (the setup candle with BreakBars 1)
        if i < 100:
            continue
        a = max(atr[i], 1e-6)
        rng = max(h[i] - l[i], 1e-6)
        t = datetime.fromtimestamp(int(x[1]), timezone.utc)
        lo7, hi7 = l[i - 6:i + 1].min(), h[i - 6:i + 1].max()
        j1 = int(np.searchsorted(D["t1"], int(x[1]) - int(x[1]) % 60))
        rows.append([1.0 if x[0] > 0 else 0.0, t.hour, t.weekday(), adx[i], a, a / max(atr[i - 96:i].mean(), 1e-6), x[17] / a, rng / a,
                     abs(c[i] - o[i]) / rng, (h[i] - max(o[i], c[i])) / rng, (min(o[i], c[i]) - l[i]) / rng, (c[i] - ef[i]) / a, (c[i] - es[i]) / a,
                     (ef[i] - es[i]) / a, (es[i] - es[i - 8]) / a, (c[i] - c[i - 4]) / a, (c[i] - c[i - 16]) / a, (c[i] - c[i - 96]) / a,
                     (c[i] - lo7) / max(hi7 - lo7, 1e-6), float(x[8]) % 21, float(sp[min(j1, len(sp) - 1)])])
        meta.append((int(x[1]), int(x[0]), float(x[6])))
    X = np.array(rows, dtype=np.float64)
    m = np.array(meta, dtype=np.float64)
    # side-aware direction: for a SELL, "price above the EMA" means the opposite of a BUY
    s = np.where(X[:, 0] > 0, 1.0, -1.0)
    for f in (11, 12, 13, 14, 15, 16, 17):
        X[:, f] *= s
    X[:, 18] = np.where(X[:, 0] > 0, X[:, 18], 1 - X[:, 18])
    return X, (m[:, 2] > 0).astype(int), m


def _res(pnl, take):
    p = pnl[take]
    return {"n": int(take.sum()), "wr": round(float(100 * (p > 0).mean()), 1) if len(p) else 0.0, "net": round(float(p.sum())),
            "pf": round(float(p[p > 0].sum() / max(1e-9, -p[p <= 0].sum())), 2) if (p <= 0).any() else 99.0}


class Job:
    def __init__(self, inputs, ds, algos, thr):
        self.inputs, self.ds, self.algos, self.thr = inputs, ("year" if ds == "tv" else ds), algos or ALGOS, float(thr or 0.5)
        self.running, self.done, self.error, self.phase, self.progress, self.total, self.result, self.t0, self._stop = False, False, None, "starting", 0, 0, None, None, False
        self.jid = f"ml-{time.time_ns()}"

    def stop(self):
        self._stop = True

    def state(self):
        return {"jid": self.jid, "running": self.running, "done": self.done, "error": self.error, "phase": self.phase, "progress": self.progress, "total": self.total,
                "seconds": round(time.time() - self.t0, 1) if self.t0 else 0, "result": self.result, "ds": self.ds}

    def run(self):
        self.running, self.t0 = True, time.time()
        try:
            self.result = self._run()
        except Exception as e:                                    # noqa: BLE001
            import traceback
            self.error, self.tb = str(e), traceback.format_exc()
        finally:
            self.running, self.done = False, True

    def _run(self):
        from sklearn.inspection import permutation_importance
        from sklearn.metrics import roc_auc_score
        self.phase = "building the dataset (the EA's trades + what was known at each entry)"
        X, y, m = dataset(self.inputs, self.ds)
        win, labels = exitlab.window_of(self.ds, self.inputs)
        a = (m[:, 0] >= win[0]) & (m[:, 0] < win[1])
        b = (m[:, 0] >= win[2]) & (m[:, 0] < win[3])
        pnl = m[:, 2]
        base = {"train": _res(pnl[a], np.ones(a.sum(), bool)), "test": _res(pnl[b], np.ones(b.sum(), bool))}
        if a.sum() < 60 or b.sum() < 30:
            raise RuntimeError(f"too few trades to learn from ({a.sum()} to train on, {b.sum()} to test) - use the 4 years")
        F = _algos()
        names = [n for n in self.algos if n in F]
        self.total = len(names)
        out = []
        for n in names:
            if self._stop:
                break
            self.phase = f"training {n}"
            t0 = time.time()
            mdl = F[n]()
            mdl.fit(X[a], y[a])
            pa, pb = mdl.predict_proba(X[a])[:, 1], mdl.predict_proba(X[b])[:, 1]
            curve = []
            for th in np.round(np.arange(0.30, 0.71, 0.025), 3):
                curve.append({"thr": float(th), "train": _res(pnl[a], pa >= th), "test": _res(pnl[b], pb >= th)})
            r = {"algo": n, "seconds": round(time.time() - t0, 2),
                 "auc_train": round(float(roc_auc_score(y[a], pa)), 3), "auc_test": round(float(roc_auc_score(y[b], pb)), 3),
                 "acc_test": round(float(100 * ((pb >= 0.5) == y[b]).mean()), 1),
                 "at_thr": {"train": _res(pnl[a], pa >= self.thr), "test": _res(pnl[b], pb >= self.thr)}, "curve": curve}
            # the threshold chosen on the TRAIN half only (best net there), then judged on the unseen half
            best = max(curve, key=lambda c: c["train"]["net"] if c["train"]["n"] >= 30 else -1e18)
            r["chosen"] = best
            out.append(r)
            self.progress += 1
        # what the best model looks at (permutation importance on the unseen half)
        imp = []
        if out:
            top = max(out, key=lambda r: r["auc_test"])
            self.phase = f"what {top['algo']} looks at"
            mdl = F[top["algo"]]()
            mdl.fit(X[a], y[a])
            pi = permutation_importance(mdl, X[b], y[b], n_repeats=5, random_state=1, scoring="roc_auc")
            imp = sorted([{"feature": FEATS[i], "importance": round(float(pi.importances_mean[i]), 4)} for i in range(len(FEATS))], key=lambda d: -d["importance"])
            imp = {"algo": top["algo"], "features": imp}
        return {"labels": labels, "n_train": int(a.sum()), "n_test": int(b.sum()), "wr_train": round(float(100 * y[a].mean()), 1), "wr_test": round(float(100 * y[b].mean()), 1),
                "base": base, "thr": self.thr, "results": out, "importance": imp, "features": FEATS}


def start(inputs, ds, algos=None, thr=0.5):
    j = Job(inputs, ds, algos, thr)
    threading.Thread(target=j.run, daemon=True).start()
    return j
