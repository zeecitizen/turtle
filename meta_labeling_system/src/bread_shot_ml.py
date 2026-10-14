"""Meta-label the STRUCTURAL shots (hypothesis stage): which Diamond / Saad / VSISA setups win the $1 before the $6.
Data: census shot logs (every trigger fired, each a real MT5 position, readings at entry). Train Jan-Jun, test Jul-Oct.
Policy: per weekday, the first shot (chronological across all scouts) with P(win) >= thr."""
import sys
import numpy as np, pandas as pd
from pathlib import Path
import xgboost as xgb
from sklearn.metrics import roc_auc_score

T = Path(r"C:\Users\zeesh\turtle\testing")
SRC = {"census_dsv": None, "census_vAD": {3: 8}, "census_vD_body25": {3: 9}}
HOL = {"2026-04-03"}


def weekdays(a, b):
    d, out = pd.Timestamp(a), []
    while d < pd.Timestamp(b):
        if d.weekday() < 5 and str(d.date()) not in HOL: out.append(d.date())
        d += pd.Timedelta(days=1)
    return out


parts = []
for n, remap in SRC.items():
    f = T / f"bread_shots_{n}_full.csv"
    if not f.exists(): print("missing", n); continue
    d = pd.read_csv(f)
    if remap: d["trig"] = d.trig.map(remap).fillna(d.trig)
    parts.append(d)
A = pd.concat(parts, ignore_index=True)
A["t"] = pd.to_datetime(A.pkt_time, format="%Y.%m.%d %H:%M"); A["day"] = A.t.dt.date
A["hr"] = A.t.dt.hour + A.t.dt.minute / 60; A["dow"] = A.t.dt.dayofweek
A = A.dropna(subset=["er"]).sort_values("t")
A["win"] = (A.net > 0).astype(int)
for k in sorted(A.trig.unique()): A[f"is{int(k)}"] = (A.trig == k).astype(int)
FE = ["side", "er", "px_e50", "e9_e50", "e50_slope", "vs_dir", "vs_age", "regime", "hr", "er_net", "dow"] + [c for c in A.columns if c.startswith("is")]
tr, te = A[A.t < "2026-07-01"], A[A.t >= "2026-07-01"]
print(f"shots: train {len(tr)} WR {tr.win.mean():.3f} | test {len(te)} WR {te.win.mean():.3f}")
m = xgb.XGBClassifier(n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8, min_child_weight=10, reg_lambda=5.0, n_jobs=8)
m.fit(tr[FE].values, tr.win.values)
A["p"] = m.predict_proba(A[FE].values)[:, 1]
tr, te = A[A.t < "2026-07-01"], A[A.t >= "2026-07-01"]
print(f"AUC train {roc_auc_score(tr.win, tr.p):.3f}  test {roc_auc_score(te.win, te.p):.3f}")
print("importance:", ", ".join(f"{a} {b:.2f}" for a, b in sorted(zip(FE, m.feature_importances_), key=lambda z: -z[1])[:8]))
for name, d, days in (("Jan-Jun (train)", tr, weekdays("2026-01-06", "2026-07-01")), ("Jul-Oct (TEST)", te, weekdays("2026-07-01", "2026-10-08"))):
    print(f"\n{name}: weekdays {len(days)}")
    for thr in (0.0, 0.80, 0.85, 0.88, 0.90, 0.92, 0.94):
        first = d[d.p >= thr].groupby("day").head(1).set_index("day").net
        v = [first.get(x) for x in days]; s = [x for x in v if x is not None]
        print(f"  thr {thr:.2f}: shots {len(s):3d} WR {100 * np.mean([x > 0 for x in s]) if s else 0:5.1f}% bread {sum(x >= 10 for x in s):3d} red {sum(x < 0 for x in s):2d} net {sum(s):8.1f}")
