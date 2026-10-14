"""bread_winner ML (hypothesis generator, NOT promotion): learn which MOMENTS win a $1 target before the stop.

Data: testing/bread_lab_<tag>.csv from the bread_lab EA: every 3 minutes, a 0.01-lot BUY and SELL, each a real MT5
fill, with ~45 readings at the moment of entry. Train on Jan-Jun (tag 1), judge on Jul-Oct (tag 2).
Policy replay: one shot per PKT day = the FIRST sample inside the window whose predicted P(win) >= thr; its MT5
outcome x (lots / 0.01). A 'bread day' = >= $10. Prints the threshold table for XGBoost and an MLP.
    py bread_ml.py [--win 18.5 24] [--lots 0.11]"""
import argparse, json
import numpy as np, pandas as pd
from pathlib import Path

T = Path(r"C:\Users\zeesh\turtle\testing")
ap = argparse.ArgumentParser()
ap.add_argument("--win", nargs=2, type=float, default=[18.5, 24.0])
ap.add_argument("--lots", type=float, default=0.11)
ap.add_argument("--train", default="1"); ap.add_argument("--test", default="2")
ap.add_argument("--model", default="xgb")
a = ap.parse_args()


def load(tag):
    d = pd.read_csv(T / f"bread_lab_{tag}.csv")
    d["t"] = pd.to_datetime(d.pkt_time, format="%Y.%m.%d %H:%M")
    d["day"] = d.t.dt.date
    d["win"] = (d.net > 0).astype(int)
    return d


tr, te = load(a.train), load(a.test)
FEATS = [c for c in tr.columns if c not in ("pkt_time", "t", "day", "win", "net", "secs")]
print(f"train {len(tr)} rows WR {tr.win.mean():.3f} | test {len(te)} rows WR {te.win.mean():.3f} | feats {len(FEATS)}")
inwin = lambda d: d[(d.pkt_hour >= a.win[0]) & (d.pkt_hour < a.win[1])]
print(f"in window {a.win}: train WR {inwin(tr).win.mean():.3f}  test WR {inwin(te).win.mean():.3f}")

X, y = tr[FEATS].values.astype(np.float32), tr.win.values
if a.model == "xgb":
    import xgboost as xgb
    # time-ordered validation inside Jan-Jun: last 20% as early stopping
    n = len(X); cut = int(n * 0.8)
    m = xgb.XGBClassifier(n_estimators=600, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.7,
                          min_child_weight=20, reg_lambda=5.0, eval_metric="logloss", early_stopping_rounds=50, n_jobs=8)
    m.fit(X[:cut], y[:cut], eval_set=[(X[cut:], y[cut:])], verbose=False)
    ptr = m.predict_proba(X)[:, 1]; pte = m.predict_proba(te[FEATS].values.astype(np.float32))[:, 1]
    imp = sorted(zip(FEATS, m.feature_importances_), key=lambda z: -z[1])[:15]
    print("top features:", ", ".join(f"{k} {v:.3f}" for k, v in imp))
else:
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(X)
    m = MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=200, early_stopping=True, random_state=1)
    m.fit(sc.transform(X), y)
    ptr = m.predict_proba(sc.transform(X))[:, 1]; pte = m.predict_proba(sc.transform(te[FEATS].values.astype(np.float32)))[:, 1]

from sklearn.metrics import roc_auc_score
print(f"AUC train {roc_auc_score(y, ptr):.3f}  test {roc_auc_score(te.win.values, pte):.3f}")
tr["p"], te["p"] = ptr, pte


def policy(d, thr, label):
    w = inwin(d).sort_values("t")
    days = sorted(d.day.unique())
    res = []
    for day, g in w.groupby("day"):
        hit = g[g.p >= thr]
        res.append(hit.iloc[0].net * a.lots / 0.01 if len(hit) else None)
    shots = [r for r in res if r is not None]
    n = len(days)
    bread = sum(1 for r in shots if r >= 10)
    red = sum(1 for r in shots if r < 0)
    return {"set": label, "thr": thr, "days": n, "shots": len(shots), "wr": round(100 * np.mean([r > 0 for r in shots]), 1) if shots else 0,
            "bread": bread, "bread_pct": round(100 * bread / n, 1), "red": red, "net": round(sum(shots), 2), "worst": round(min(shots), 2) if shots else 0}


rows = []
for thr in (0.80, 0.85, 0.88, 0.90, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98):
    for d, lab in ((tr, "Jan-Jun"), (te, "Jul-Oct")):
        rows.append(policy(d, thr, lab))
print(pd.DataFrame(rows).to_string(index=False))
