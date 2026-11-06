"""scan.py - batch 7: univariate tail scan. For each feature and each tail (top/bottom q), loss rate among trades in the tail on
train and test vs base. Prints the tails with lift >= 1.8 on BOTH halves and >= 6 losers."""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
F = pd.read_pickle(os.path.join(HERE, "feats.pkl"))
F["loss"] = ~F["win"]
base_tr = F.loc[F.train, "loss"].mean(); base_te = F.loc[~F.train, "loss"].mean(); base = F["loss"].mean()
print(f"base all {base:.4f} train {base_tr:.4f} test {base_te:.4f}  n_train {F.train.sum()} n_test {(~F.train).sum()}")
skip = {"id", "side", "t_in", "win", "pnl", "why", "train", "loss"}
out = []
for col in F.columns:
    if col in skip:
        continue
    x = F[col].astype(float)
    if x.isna().all():
        continue
    for q in (0.02, 0.05, 0.10, 0.20, 0.33):
        for tail in ("hi", "lo"):
            thr = x.quantile(1 - q) if tail == "hi" else x.quantile(q)
            m = (x >= thr) if tail == "hi" else (x <= thr)
            m = m & x.notna()
            n = m.sum()
            if n < 20:
                continue
            Lm = F.loc[m, "loss"]; tr = F.loc[m & F.train, "loss"]; te = F.loc[m & ~F.train, "loss"]
            lift = Lm.mean() / base; ltr = tr.mean() / base_tr if len(tr) else np.nan; lte = te.mean() / base_te if len(te) else np.nan
            out.append((col, tail, q, round(thr, 3), int(n), int(Lm.sum()), round(lift, 2), round(ltr, 2), round(lte, 2), int(tr.sum()), int(te.sum())))
R = pd.DataFrame(out, columns=["feat", "tail", "q", "thr", "n", "losers", "lift", "lift_tr", "lift_te", "L_tr", "L_te"])
R["minlift"] = R[["lift_tr", "lift_te"]].min(axis=1)
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 400)
G = R[(R.minlift >= 1.6) & (R.losers >= 6)].sort_values("minlift", ascending=False)
print(G.to_string(index=False))
R.to_csv(os.path.join(HERE, "scan_out.csv"), index=False)
