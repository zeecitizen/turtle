"""scan.py - for every feature in feat.pkl: lift of its tails (top/bottom 2, 5, 10, 20 %) on train and test separately.
ANALYSIS ONLY (reads outcomes) - it picks which ideas deserve a rule; the rules themselves are scored by api.report."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_pickle(os.path.join(HERE, "feat.pkl"))
base = df.groupby("half")["loss"].mean()
skip = {"id", "half", "loss", "pnl", "why"}
feats = [c for c in df.columns if c not in skip]
only = sys.argv[1:] or None
out = []
for f in feats:
    if only and f not in only:
        continue
    x = df[f].astype(float)
    for q in (0.02, 0.05, 0.10, 0.20):
        for tail in ("hi", "lo"):
            thr = x.quantile(1 - q) if tail == "hi" else x.quantile(q)
            m = x >= thr if tail == "hi" else x <= thr
            if m.sum() < 20 or m.mean() > 0.5:
                continue
            res = {"feat": f, "tail": tail, "q": q, "thr": round(thr, 3), "n": int(m.sum()), "L": int(df.loss[m].sum())}
            for hf in ("train", "test"):
                mm = m & (df.half == hf)
                res[f"{hf}_L"] = int(df.loss[mm].sum())
                res[f"{hf}_n"] = int(mm.sum())
                res[f"{hf}_lift"] = round(df.loss[mm].mean() / base[hf], 2) if mm.sum() else np.nan
            res["minlift"] = min(res["train_lift"], res["test_lift"])
            out.append(res)
R = pd.DataFrame(out).sort_values("minlift", ascending=False)
pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 400)
print(R.head(60).to_string(index=False))
