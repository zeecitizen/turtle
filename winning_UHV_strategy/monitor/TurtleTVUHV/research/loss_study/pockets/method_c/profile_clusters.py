"""profile_clusters.py - METHOD C step 1: for each loss-cause cluster, compare its TRAIN losses with all TRAIN winners on every
decision-time feature (median, AUC, best one-sided cut at <=5% / <=10% of train trades). Test rows are never read for tuning."""
import csv, json, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
R = list(csv.DictReader(open(os.path.join(HERE, "..", "features.csv"), encoding="utf-8")))
CAUSE = json.load(open(os.path.join(HERE, "causes_by_id.json")))
FEATS = [k for k in R[0] if k not in ("id", "win", "pnl", "half")]
X = np.array([[float(r[f]) for f in FEATS] for r in R])
win = np.array([int(r["win"]) for r in R]); half = np.array([r["half"] for r in R])
cause = np.array([CAUSE.get(r["id"], "") for r in R])
tr = half == "train"
print("train", tr.sum(), "losses", (tr & (win == 0)).sum(), " test", (~tr).sum(), "losses", ((~tr) & (win == 0)).sum())
cl = sorted(set(cause[win == 0]))
for c in cl:
    print(f"  {c:22s} train {(tr & (cause == c)).sum():3d}  test {((~tr) & (cause == c)).sum():3d}")

def auc(a, b):
    # P(a > b) + 0.5 P(a == b)
    allv = np.concatenate([a, b]); ranks = allv.argsort().argsort().astype(float)
    # average ties
    order = np.argsort(allv); sv = allv[order]; rk = np.empty(len(allv))
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        rk[order[i:j + 1]] = (i + j) / 2 + 1; i = j + 1
    ra = rk[:len(a)].sum()
    return (ra - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))

W = tr & (win == 1); NTR = tr.sum(); LTR = (tr & (win == 0)).sum()
for c in cl:
    m = tr & (cause == c)
    if m.sum() < 3:
        continue
    print(f"\n=== {c}  ({m.sum()} train losses) ===")
    rows = []
    for j, f in enumerate(FEATS):
        a, b = X[m, j], X[W, j]
        A = auc(a, b)
        # best one-sided cut (side chosen by AUC) maximizing cluster losses captured with share <= 5% and <= 10%
        best = {}
        u = np.unique(X[tr, j]); vals = u if len(u) <= 200 else np.unique(np.quantile(X[tr, j], np.linspace(0, 1, 201)))
        for cap in (0.05, 0.10):
            bb = None
            for v in vals:
                for sgn in (1, -1):
                    p = (X[tr, j] >= v) if sgn > 0 else (X[tr, j] <= v)
                    sh = p.mean()
                    if sh > cap or sh == 0:
                        continue
                    lc = (p & (cause[tr] == c)).sum(); la = (p & (win[tr] == 0)).sum()
                    if bb is None or (lc, -sh) > (bb[0], -bb[2]):
                        bb = (lc, la, sh, (">=" if sgn > 0 else "<=") + f"{v:g}")
            best[cap] = bb
        rows.append((abs(A - 0.5), f, np.median(a), np.median(b), A, best))
    rows.sort(reverse=True)
    for _, f, ma, mb, A, best in rows[:12]:
        b5, b10 = best[0.05] or (0, 0, 0.0, "-"), best[0.10] or (0, 0, 0.0, "-")
        print(f"  {f:16s} med L {ma:8.3f}  W {mb:8.3f}  AUC {A:.2f}  | <=5%: {b5[3]:>10s} cl {b5[0]:2d} all {b5[1]:2d} sh {b5[2]*100:4.1f}%"
              f"  | <=10%: {b10[3]:>10s} cl {b10[0]:2d} all {b10[1]:2d} sh {b10[2]*100:4.1f}%")
