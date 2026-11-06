"""recompute.py (pockets/audit) - ADVERSARIAL AUDIT of the three risky-pocket hunts (Zee 2026-11-06: "10% risky trades zone -> the angel
only cuts some of them ... 80% non-risky trades (no angel) ... isolate the risky zones further").

Every pocket of Method A (trees/boosting), Method B (beam rule lists) and Method C (loss-cluster profiling) is re-computed here from
../features.csv alone (derived inputs rebuilt independently, X1 boosted score refitted and checked against the reported test AUC), then:
  1. per pocket, TRAIN (Mar-Jun) and TEST (Jul-Nov): trades, share, losses, loss rate, lift vs 2.26% (all-data base) and vs the half's own
     base, binomial p, loss-days, untouched WR (pocket skipped) - and an ASSERT that the recomputed counts equal the claimed counts;
  2. SURVIVAL (strict, as the task words it): TEST loss rate >= 2 x 2.26% and >= 5 TEST losses.  Looser sensitivity: >= 2 x the TEST base
     (1.40%);
  3. NEAR-DUPLICATES: trade Jaccard / containment, shared test losses / min(losses), and RESIDUAL tests (A minus B still passes?);
  4. GREEDY UNION on TRAIN from the survivors at train-coverage caps 10/15/20/25% (best marginal train loss rate first; a pocket is added only
     if its marginal train loss rate beats the current untouched rate) -> TEST capture, untouched WR, losses needed for 99.3%;
  5. PERMUTATION nulls (200 draws, wins shuffled within each half):
       (a) LITERAL (as asked): survivor masks fixed, greedy redone on shuffled TRAIN, TEST capture recorded.  CIRCULAR: survivors were
           screened on the real TEST labels, so (a) is ~certain to "beat chance";
       (b) SELECTION-AWARE (headline): the survival screen is ALSO re-run on the shuffled TEST labels, then the same greedy;
       (c) FULLY BLIND: survivors screened on TRAIN only (lift >= 2 vs train base, >= 5 losses, >= 4 loss-days, no day > 1/3 of losses),
           greedy on TRAIN, TEST scored once; null = the same pipeline on shuffled labels.
     Statistics: raw TEST losses captured AND excess = captured - (union test share x 60), because null unions are often smaller.
     p = (1 + #null >= real) / (1 + 200).  No permutation can repair that the candidate pool itself was partly built with TEST in view.
Python replay = HYPOTHESIS, NOT PROMOTED (CLAUDE.md); win rates go through doctrine.python_says.  No P&L is computed or quoted.
Run (Git Bash): cd .../pockets && py audit/recompute.py > audit/recompute.out   -> also writes audit/recompute.json"""
import json
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.stats import binom

warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__))
POCK = os.path.dirname(HERE)
MONITOR = os.path.abspath(os.path.join(POCK, "..", "..", "..", ".."))   # .../turtle/monitor (pockets -> loss_study -> research -> TurtleTVUHV -> monitor)
assert os.path.exists(os.path.join(MONITOR, "doctrine.py")), MONITOR
sys.path.insert(0, MONITOR)
from doctrine import python_says  # noqa: E402

NPERM = 200
CAPS = (0.10, 0.15, 0.20, 0.25)
NEED_WR = 0.993
SEED = 20261106

# ---------------------------------------------------------------- data + derived inputs (decision-time; earlier trades only)
d = pd.read_csv(os.path.join(POCK, "features.csv"))
assert list(d.columns[-3:]) == ["win", "pnl", "half"]
d["loss"] = 1 - d["win"]
d["ts"] = pd.to_datetime("2026" + d["id"].str[:11], format="%Y%m%d-%H%M%S", utc=True)
d = d.sort_values("ts", kind="stable").reset_index(drop=True)
d["ny_date"] = d["ts"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
d["month"] = d["ts"].dt.strftime("%m")
prev50 = d["spread_pips"].shift(1).rolling(50, min_periods=1).median().fillna(d["spread_pips"].iloc[0])
d["spread_excess"] = (d["spread_pips"] - prev50).round(3)


def roll_med(s, n):
    return s.shift(1).rolling(n, min_periods=1).median().fillna(s)


d["stop_atr"] = (d["stop_pips"] / d["atr_pips"]).round(3)
d["room60_atr"] = (d["room60_pips"] / d["atr_pips"]).round(3)
d["room240_atr"] = (d["room240_pips"] / d["atr_pips"]).round(3)
d["gap_atr"] = (d["gap_pips"] / d["atr_pips"]).round(3)
d["fig_ahead_atr"] = (d["fig_ahead_pips"] / d["atr_pips"]).round(3)
d["uhv_rel"] = (d["uhv_v"] / d["vol10"].clip(lower=1)).round(3)
d["atr_rel"] = (d["atr_pips"] / roll_med(d["atr_pips"], 300)).round(3)
d["vol10_rel"] = (d["vol10"] / roll_med(d["vol10"], 300)).round(3)

N = len(d)
Y = d["loss"].values.astype(int)
TR = (d["half"] == "train").values
TE = (d["half"] == "test").values
MON = d["month"].values
DAYS = pd.factorize(d["ny_date"])[0]
NTR, NTE = int(TR.sum()), int(TE.sum())
LTR, LTE = int(Y[TR].sum()), int(Y[TE].sum())
assert (N, int(Y.sum()), NTR, LTR, NTE, LTE) == (7626, 172, 3335, 112, 4291, 60), (N, Y.sum(), NTR, LTR, NTE, LTE)
BASE_ALL = Y.mean()                  # 172/7626 = 2.2554%  (the task's "2.26%")
BASE_TR, BASE_TE = LTR / NTR, LTE / NTE
mod, wd, hr = d["ny_min_of_day"].values, d["weekday"].values, d["ny_hour"].values
c = {k: d[k].values for k in d.columns}

# ---------------------------------------------------------------- X1: Method A's boosted risk score, refitted
import xgboost as xgb  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

SF = ["side", "humps", "er8", "er16", "er30", "er60", "adx", "trend30_atr", "trend90_atr", "trend240_atr", "ny_hour", "ny_min_of_day",
      "weekday", "spread_excess", "brk_ratio", "uhv_rel", "stop_atr", "bars_since_uhv", "box", "room60_atr", "room240_atr", "pos60",
      "range20_atr", "range60_atr", "struct_with", "uhv_body", "last_body_dir", "fig_ahead_atr", "vol_ratio10_60", "gap_atr", "atr_rel",
      "vol10_rel"]


def mbal(y, mon):
    w = np.ones(len(y))
    for m in np.unique(mon):
        k = mon == m
        L = y[k].sum()
        if L:
            w[k & (y == 1)] = (k.sum() - L) / L
    return w


def xgbm(nj=4):
    # NOTE: xgboost 'hist' output depends on the THREAD COUNT here (1/2/4/8 threads -> test AUC 0.617/0.618/0.628/0.638);
    # n_jobs=4 is what Method A ran and is the only setting that reproduces its reported 0.6282.
    return xgb.XGBClassifier(n_estimators=25, max_depth=2, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
                             reg_lambda=1.0, tree_method="hist", n_jobs=nj, random_state=0, verbosity=0)


Xtr, Xte = d.loc[TR, SF].values.astype(float), d.loc[TE, SF].values.astype(float)
ytr, mtr = Y[TR], MON[TR]
tri = np.where(TR)[0]


def x1_mask(nj):
    pt = xgbm(nj).fit(Xtr, ytr, sample_weight=mbal(ytr, mtr)).predict_proba(Xte)[:, 1]
    of = np.zeros(len(ytr))
    for m in ("03", "04", "05", "06"):
        fit, ho = mtr != m, mtr == m
        of[ho] = xgbm(nj).fit(Xtr[fit], ytr[fit], sample_weight=mbal(ytr[fit], mtr[fit])).predict_proba(Xtr[ho])[:, 1]
    mk = np.zeros(N, bool)
    mk[np.where(TE)[0][pt >= np.quantile(pt, 0.9)]] = True
    for m in ("03", "04", "05", "06"):
        k = mtr == m
        mk[tri[k & (of >= np.quantile(of[k], 0.9))]] = True
    return mk, float(roc_auc_score(Y[TE], pt))


X1, X1_AUC = x1_mask(4)
assert abs(X1_AUC - 0.6282) < 1e-3, f"X1 refit test AUC {X1_AUC:.4f} != reported 0.6282"
X1_THREADS = {}
for nj in (1, 2, 8):
    mk, au = x1_mask(nj)
    X1_THREADS[nj] = dict(auc=au, test_n=int((mk & TE).sum()), test_L=int(Y[mk & TE].sum()), train_L=int(Y[mk & TR].sum()),
                          overlap_with_4=float((mk & X1).sum() / max(1, (mk | X1).sum())))

# ---------------------------------------------------------------- the pockets, with the hunts' exact edge semantics
E = 1e-9
P = {}   # name -> (condition text, mask, official?)


def add(name, cond, mask, official=True):
    P[name] = (cond, np.asarray(mask, bool), official)


add("A-P1 abnormal breakout spread", "spread_excess > 0.275", c["spread_excess"] > 0.275)
add("A-P2 NY close/rollover 16-18", "960 <= ny_min_of_day < 1080 (16:00-17:59 NY)", (mod >= 960) & (mod < 1080))
add("A-P3 Friday afternoon", "weekday == 4 and ny_min_of_day >= 720 (Fri from 12:00 NY)", (wd == 4) & (mod >= 720))
add("A-P4 counter-trend chop weak break", "trend30_atr <= -1.905 and er30 <= 0.2065 and brk_ratio <= 0.5055",
    (c["trend30_atr"] <= -1.905) & (c["er30"] <= 0.2065) & (c["brk_ratio"] <= 0.5055))
add("A-P5 NY afternoon thin volume", "ny_min_of_day >= 870 and vol10_rel <= 0.8805 and atr_rel > 0.7715",
    (mod >= 870) & (c["vol10_rel"] <= 0.8805) & (c["atr_rel"] > 0.7715))
add("A-X1 xgb top-10% risk score", "xgboost d2/25 trees/eta .05, scale-free + month-balanced; top 10% (train OOF by month, test top decile)", X1)
add("A-F1 shallow stop in chop", "stop_atr <= 0.8145 and er60 <= 0.158 and er30 > 0.1575",
    (c["stop_atr"] <= 0.8145) & (c["er60"] <= 0.158) & (c["er30"] > 0.1575))
add("A-F2 chop + gap + little room", "er16 <= 0.1785 and gap_atr > 0.2035 and room60_atr <= 2.38",
    (c["er16"] <= 0.1785) & (c["gap_atr"] > 0.2035) & (c["room60_atr"] <= 2.38))
add("A-F3 first protocol top leaf", "brk_ratio <= 0.3665 and fig_ahead_pips > 76.35 and er30 > 0.1205 and stop_pips <= 2.35",
    (c["brk_ratio"] <= 0.3665) & (c["fig_ahead_pips"] > 76.35) & (c["er30"] > 0.1205) & (c["stop_pips"] <= 2.35))
add("B-P1 late NY wide stop", "16 <= ny_hour <= 18 and stop_pips > 1.95 and trend240_atr > -9.19",
    (hr >= 16) & (hr <= 18) & (c["stop_pips"] > 1.95) & (c["trend240_atr"] > -9.19))
add("B-P2 narrow chop band", "0.1015 < er16 <= 0.1335 and range20_atr > 4.935 and 0.4555 < pos60 <= 0.9095",
    (c["er16"] > 0.1015) & (c["er16"] <= 0.1335) & (c["range20_atr"] > 4.935) & (c["pos60"] > 0.4555) & (c["pos60"] <= 0.9095))
add("B-P3 fading volume mid trend", "vol_ratio10_60 <= 0.7275 and 76.75 < vol10 <= 119.55 and 17.75 < adx <= 30.15",
    (c["vol_ratio10_60"] <= 0.7275) & (c["vol10"] > 76.75) & (c["vol10"] <= 119.55) & (c["adx"] > 17.75) & (c["adx"] <= 30.15))
add("B-P4 weak breakout minute", "0.1855 < er8 <= 0.2395 and brk_ratio <= 0.1285 and 110.5 < uhv_v <= 304.5",
    (c["er8"] > 0.1855) & (c["er8"] <= 0.2395) & (c["brk_ratio"] <= 0.1285) & (c["uhv_v"] > 110.5) & (c["uhv_v"] <= 304.5))
add("B-P5 strong ADX modest 4h move", "adx > 43.95 and 0.995 < trend240_atr <= 6.635 and 0.0205 < er8 <= 0.3635",
    (c["adx"] > 43.95) & (c["trend240_atr"] > 0.995) & (c["trend240_atr"] <= 6.635) & (c["er8"] > 0.0205) & (c["er8"] <= 0.3635))
add("B-P6 near extreme in tight chop", "0.25 < room60_pips <= 0.65 and range20_atr <= 3.975 and er16 <= 0.1705",
    (c["room60_pips"] > 0.25) & (c["room60_pips"] <= 0.65) & (c["range20_atr"] <= 3.975) & (c["er16"] <= 0.1705))
add("C-P1 weekly close (Fri pm)", "weekday == 4 and ny_min_of_day >= 870 (Fri from 14:30 NY)", (wd == 4) & (mod >= 870))
add("C-P2 rollover or spread blow-out", "1005 <= ny_min_of_day < 1035 (16:45-17:14 NY) OR spread_pips >= 1.6",
    ((mod >= 1005) & (mod < 1035)) | (c["spread_pips"] >= 1.6 - E))
add("C-P3 dead chop", "atr_pips <= 0.6 and er30 <= 0.10", (c["atr_pips"] <= 0.6 + E) & (c["er30"] <= 0.10 + E))
add("C-P4 exhausted move", "humps >= 7 and trend30_atr >= 3", (c["humps"] >= 7) & (c["trend30_atr"] >= 3))
add("C-P5 news slot vol up", "|ny_min_of_day - 510| <= 30 (08:00-09:00 NY, Mon-Fri) and vol_ratio10_60 >= 1.2",
    (np.abs(mod - 510) <= 30) & (wd <= 4) & (c["vol_ratio10_60"] >= 1.2))
add("C-P6 counter-structure", "trend90_atr <= -8 and pos60 <= 0.2", (c["trend90_atr"] <= -8) & (c["pos60"] <= 0.2 + E))
add("C-P7 figure ahead", "fig_ahead_pips <= 4", c["fig_ahead_pips"] <= 4 + E)
# supplementary (named in Method B's notes; NOT in the hunts' pocket lists; used only in the 'extended pool' sensitivity)
add("B-S1 Fri from 12 (variant)", "weekday == 4 and ny_hour >= 12", (wd == 4) & (hr >= 12), False)
add("B-S2 fading vol low ADX (variant)", "vol_ratio10_60 <= 0.7275 and adx <= 27.25", (c["vol_ratio10_60"] <= 0.7275) & (c["adx"] <= 27.25), False)
add("B-S3 Asia chop (variant)", "ny_hour <= 2 and er16 <= 0.1705", (hr <= 2) & (c["er16"] <= 0.1705), False)
add("B-S4 high ATR short stop (variant)", "atr_pips > 2.805 and stop_pips <= 4.25", (c["atr_pips"] > 2.805) & (c["stop_pips"] <= 4.25), False)
add("B-S5 dead er60 low ADX (variant)", "er60 <= 0.0215 and adx <= 24.85", (c["er60"] <= 0.0215) & (c["adx"] <= 24.85), False)
add("B-D1 spread >= 1.0 (diagnostic)", "spread_pips >= 1.0", c["spread_pips"] >= 1.0 - E, False)
add("B-D2 NY 16:45-17:44 (diagnostic)", "1005 <= ny_min_of_day < 1065", (mod >= 1005) & (mod < 1065), False)
add("B-D5 vol10 <= 40.15 (diagnostic)", "vol10 <= 40.15", c["vol10"] <= 40.15, False)
add("B-D6 uhv_v <= 54.5 (diagnostic)", "uhv_v <= 54.5", c["uhv_v"] <= 54.5, False)

# claimed (train n, train L, test n, test L) from the hunts' reports; None = not reported
CLAIMED = {
    "A-P1": (77, 10, 74, 9), "A-P2": (126, 13, 172, 9), "A-P3": (124, 15, 196, 9), "A-P4": (235, 20, 345, 10), "A-P5": (114, 15, 128, 5),
    "A-X1": (None, 19, None, 18), "A-F1": (96, 13, 100, 0), "A-F2": (77, 10, 116, 2), "A-F3": (119, 18, 220, 2),
    "B-P1": (64, 14, 53, 1), "B-P2": (44, 11, 65, 1), "B-P3": (45, 10, 56, 0), "B-P4": (39, 10, 51, 1), "B-P5": (40, 9, 53, 0),
    "B-P6": (36, 9, 61, 0),
    "C-P1": (51, 11, 92, 6), "C-P2": (58, 11, 73, 8), "C-P3": (54, 7, 141, 5), "C-P4": (29, 5, 33, 1), "C-P5": (70, 6, 81, 1),
    "C-P6": (87, 5, 113, 1), "C-P7": (146, 6, 166, 4),
    "B-S1": (124, 15, 196, 9), "B-S2": (172, 16, 258, 5), "B-S3": (168, 14, 267, 4), "B-S4": (105, 10, 59, 0), "B-S5": (123, 9, 205, 4),
    "B-D1": (None, None, 47, 8), "B-D2": (None, None, 57, 8), "B-D5": (None, None, 247, 9), "B-D6": (None, None, 347, 8),
}
NAMES = list(P)
SHORT = {n: n.split(" ")[0] for n in NAMES}
M = np.array([P[n][1] for n in NAMES])           # pockets x trades
OFFICIAL = [n for n in NAMES if P[n][2]]
assert len(OFFICIAL) == 22


# ---------------------------------------------------------------- scoring helpers
def half_stats(mask, H, y=Y):
    m = mask & H
    nh, Lh = int(H.sum()), int(y[H].sum())
    n, L = int(m.sum()), int(y[m].sum())
    lr = L / n if n else 0.0
    dl = DAYS[m & (y == 1)]
    if L:
        u, cnt = np.unique(dl, return_counts=True)
        nd, mx, mxday = len(u), int(cnt.max()), d["ny_date"].values[np.where(DAYS == u[cnt.argmax()])[0][0]]
    else:
        nd, mx, mxday = 0, 0, ""
    return dict(n=n, share=n / nh, L=L, L_half=Lh, L_share=L / Lh if Lh else 0.0, lr=lr, lift_all=lr / BASE_ALL,
                lift_half=lr / (Lh / nh), p=float(binom.sf(L - 1, n, Lh / nh)) if (L and n) else 1.0, loss_days=nd, max_day=mx,
                max_day_date=mxday, wr_untouched=1 - (Lh - L) / (nh - n), wr_base=1 - Lh / nh, expected=n / nh * Lh)


def stats(mask, y=Y):
    return {"train": half_stats(mask, TR, y), "test": half_stats(mask, TE, y)}


def line(s):
    return (f"{100 * s['share']:5.1f}% ({s['n']:4d}) | {s['L']:3d}/{s['L_half']} L ({100 * s['L_share']:4.1f}%) | LR {100 * s['lr']:5.2f}% | "
            f"lift {s['lift_all']:4.2f}x vs 2.26% / {s['lift_half']:4.2f}x vs half | p={s['p']:.2g} | {s['loss_days']:2d} loss-days "
            f"(max {s['max_day']} on {s['max_day_date'] or '-'}) | untouched WR {100 * s['wr_untouched']:.2f}%")


def strict_ok(s):        # task rule: TEST loss rate >= 2 x 2.26% with >= 5 TEST losses
    return s["L"] >= 5 and s["lr"] >= 2 * BASE_ALL


def loose_ok(s):         # sensitivity: lift >= 2 vs the TEST half's own base (1.40%)
    return s["L"] >= 5 and s["lr"] >= 2 * BASE_TE


def train_ok(s):         # fully blind screen (c), TRAIN only, with a loss-day guard (Good Friday etc.)
    return s["L"] >= 5 and s["lr"] >= 2 * BASE_TR and s["loss_days"] >= 4 and s["max_day"] <= s["L"] / 3 + 1e-9


OUT = {"note": "Python replay = HYPOTHESIS, NOT PROMOTED. No P&L computed.", "base": dict(
    all=BASE_ALL, train=BASE_TR, test=BASE_TE, n_train=NTR, L_train=LTR, n_test=NTE, L_test=LTE), "x1_test_auc": X1_AUC}
BAR = "=" * 168
print(BAR)
print(f"BASE  all {N} trades / {Y.sum()} L = {100 * BASE_ALL:.3f}%  | TRAIN {NTR} / {LTR} L = {100 * BASE_TR:.2f}% (WR {100 * (1 - BASE_TR):.2f}%) | "
      f"TEST {NTE} / {LTE} L = {100 * BASE_TE:.2f}% (WR {100 * (1 - BASE_TE):.2f}%)")
print(f"STRICT survival: TEST loss rate >= {100 * 2 * BASE_ALL:.2f}% (2 x {100 * BASE_ALL:.3f}%) and >= 5 TEST losses.  LOOSER: TEST loss rate >= "
      f"{100 * 2 * BASE_TE:.2f}% (2 x test base) and >= 5.  X1 refit: test AUC {X1_AUC:.4f} (reported 0.6282) - reproduced.")
print(BAR)

# ---------------------------------------------------------------- 1. recompute every pocket + check the claims
print("1. EVERY POCKET RE-COMPUTED (claimed counts asserted)   [* = official pocket of a hunt; supplementary ones are from Method B's notes]")
ST, mismatch = {}, []
for n in NAMES:
    s = stats(P[n][1])
    ST[n] = s
    cl = CLAIMED[SHORT[n]]
    got = (s["train"]["n"], s["train"]["L"], s["test"]["n"], s["test"]["L"])
    bad = [(i, a, b) for i, (a, b) in enumerate(zip(cl, got)) if a is not None and a != b]
    if bad:
        mismatch.append((n, cl, got))
    tag = "MATCH" if not bad else f"MISMATCH claimed {cl} got {got}"
    print(f"{'*' if P[n][2] else ' '} {n:38s} [{tag}]  {P[n][0]}")
    print(f"     train {line(s['train'])}")
    print(f"     test  {line(s['test'])}   -> strict {'PASS' if strict_ok(s['test']) else 'fail'} / looser "
          f"{'PASS' if loose_ok(s['test']) else 'fail'}")
print(f"   claimed-count check: {len(NAMES) - len(mismatch)}/{len(NAMES)} pockets reproduce exactly" +
      ("" if not mismatch else f"; MISMATCHES: {mismatch}"))
# Method B's S2-S5 'search' counts come from a greedy LIST (each pocket searched after removing the earlier pockets' trades):
# re-check them incrementally; only official-pocket mismatches are fatal.
_prev = np.zeros(N, bool)
explained = []
for s_ in ("B-S1", "B-S2", "B-S3", "B-S4", "B-S5"):
    nm = [n for n in NAMES if SHORT[n] == s_][0]
    inc = P[nm][1] & ~_prev
    got_inc = (int((inc & TR).sum()), int(Y[inc & TR].sum()))
    if any(nm == x[0] for x in mismatch):
        ok = got_inc == CLAIMED[s_][:2]
        print(f"   {s_}: incremental train count after removing the earlier S-pockets = {got_inc} vs claimed {CLAIMED[s_][:2]} -> "
              f"{'EXPLAINED (greedy-list counting, not an error)' if ok else 'STILL DIFFERENT'}")
        if ok:
            explained.append(nm)
    _prev |= P[nm][1]
fatal = [x for x in mismatch if P[x[0]][2] or x[0] not in explained]
OUT["claim_check"] = dict(mismatches=[x[0] for x in mismatch], explained_incremental=explained, fatal=[x[0] for x in fatal])
print("   X1 FRAGILITY - the same model refitted with other xgboost thread counts (4 = Method A's run):")
for nj, v in X1_THREADS.items():
    print(f"     n_jobs {nj}: test AUC {v['auc']:.4f} | top-10% test {v['test_L']}/60 L in {v['test_n']} trades | train OOF top-10% {v['train_L']}/112 L | "
          f"Jaccard with the n_jobs=4 pocket {v['overlap_with_4']:.2f}")
OUT["x1_thread_sensitivity"] = X1_THREADS
assert not fatal, fatal
OUT["pockets"] = {n: dict(cond=P[n][0], official=P[n][2], **ST[n]) for n in NAMES}

STRICT = [n for n in OFFICIAL if strict_ok(ST[n]["test"])]
LOOSE = [n for n in OFFICIAL if loose_ok(ST[n]["test"])]
EXT_STRICT = [n for n in NAMES if strict_ok(ST[n]["test"])]
EXT_LOOSE = [n for n in NAMES if loose_ok(ST[n]["test"])]
BLIND = [n for n in OFFICIAL if train_ok(ST[n]["train"])]
borderline = [n for n in NAMES if ST[n]["test"]["L"] >= 5 and 2 * BASE_ALL <= ST[n]["test"]["lr"] < 0.0452 + 1e-12]
print(BAR)
print("2. SURVIVAL")
print(f"   STRICT survivors (official pool of 22): {[SHORT[n] for n in STRICT]}")
print(f"   LOOSER survivors (official pool):        {[SHORT[n] for n in LOOSE]}")
print(f"   extended pool (+ Method B note pockets): strict {[SHORT[n] for n in EXT_STRICT]} | looser {[SHORT[n] for n in EXT_LOOSE]}")
print(f"   pockets between 2 x 2.2554% and 4.52% (rounding-sensitive): {[SHORT[n] for n in borderline] or 'none'}")
for n in NAMES:
    t = ST[n]["test"]
    if t["L"] >= 5 and not strict_ok(t):
        print(f"   near miss {SHORT[n]}: test {t['L']}/{t['n']} = {100 * t['lr']:.2f}% needs >= {100 * 2 * BASE_ALL:.2f}% "
              f"-> {math.ceil(2 * BASE_ALL * t['n'] - 1e-9)} losses (has {t['L']})")
print(f"   BLIND screen on TRAIN (lift >= 2 vs train base, >= 5 L, >= 4 loss-days, no day > 1/3): {[SHORT[n] for n in BLIND]}")
for n in STRICT + [x for x in LOOSE if x not in STRICT]:
    m = P[n][1]
    per = []
    for mo in ("07", "08", "09", "10", "11"):
        k = m & TE & (MON == mo)
        per.append(f"{mo}:{int(Y[k].sum())}/{int(k.sum())}")
    print(f"   {SHORT[n]:6s} test losses/trades by month  " + "  ".join(per))
OUT["survivors"] = dict(strict=STRICT, looser=LOOSE, ext_strict=EXT_STRICT, ext_looser=EXT_LOOSE, blind_train=BLIND)

# ---------------------------------------------------------------- 3. near-duplicates + residuals
print(BAR)
print("3. NEAR-DUPLICATES  (near-dup = trade Jaccard >= 0.5 OR containment >= 0.8 OR shared TEST losses >= 2/3 of the smaller pocket's)")


def pair(a, b):
    A, B = P[a][1], P[b][1]
    inter, uni = int((A & B).sum()), int((A | B).sum())
    jac = inter / uni if uni else 0.0
    cont = inter / min(A.sum(), B.sum()) if min(A.sum(), B.sum()) else 0.0
    la, lb = int(Y[A & TE].sum()), int(Y[B & TE].sum())
    sh = int(Y[A & B & TE].sum())
    shr = sh / min(la, lb) if min(la, lb) else 0.0
    return dict(jac=jac, cont=cont, shared_test_L=sh, shared_ratio=shr, near=(jac >= 0.5 or cont >= 0.8 or (min(la, lb) > 0 and shr >= 2 / 3)))


for a in NAMES:
    best = max((b for b in NAMES if b != a), key=lambda b: (pair(a, b)["cont"], pair(a, b)["jac"]))
    pr = pair(a, best)
    print(f"   {SHORT[a]:5s} nearest {SHORT[best]:5s} containment {pr['cont']:.2f} Jaccard {pr['jac']:.2f} shared test L {pr['shared_test_L']}"
          f" -> {'NEAR-DUPLICATE' if pr['near'] else 'distinct'}")
pool_dup = sorted(set(EXT_LOOSE))
print("   pairwise among looser/extended survivors (Jaccard / containment / shared test L of min):")
dup_pairs = []
for i, a in enumerate(pool_dup):
    for b in pool_dup[i + 1:]:
        pr = pair(a, b)
        if pr["near"] or pr["shared_test_L"] >= 2:
            dup_pairs.append((a, b, pr))
            print(f"     {SHORT[a]:5s} ~ {SHORT[b]:5s}  J {pr['jac']:.2f}  C {pr['cont']:.2f}  shared test L {pr['shared_test_L']} "
                  f"({100 * pr['shared_ratio']:.0f}% of min) {'NEAR-DUP' if pr['near'] else ''}")
print("   RESIDUAL tests on TEST (pocket A with pocket B's trades removed; strict rule = >= 5 L and LR >= 4.51%):")
RESID = []
for a, b, pr in dup_pairs:
    for x, y_ in ((a, b), (b, a)):
        r = half_stats(P[x][1] & ~P[y_][1], TE)
        rt = half_stats(P[x][1] & ~P[y_][1], TR)
        RESID.append(dict(a=x, minus=y_, test=r, train=rt))
        print(f"     {SHORT[x]:5s} minus {SHORT[y_]:5s}: test {r['L']}/{r['n']} = {100 * r['lr']:5.2f}% (lift {r['lift_all']:.2f}x) "
              f"{'still PASSES' if strict_ok(r) else 'FAILS alone'} | train {rt['L']}/{rt['n']} = {100 * rt['lr']:.2f}%")
OUT["near_duplicates"] = [dict(a=a, b=b, **pr) for a, b, pr in dup_pairs]
OUT["residuals"] = RESID


# ---------------------------------------------------------------- 4. greedy union on TRAIN
def greedy(pool, y, cap):
    """best marginal TRAIN loss rate first; add only if it fits the train-coverage cap and beats the current untouched train loss rate."""
    idx = [NAMES.index(n) for n in pool]
    union = np.zeros(N, bool)
    picked = []
    ltr = int(y[TR].sum())
    while True:
        cur_n = int((union & TR).sum())
        cur_L = int(y[union & TR].sum())
        unt = (ltr - cur_L) / (NTR - cur_n)
        best = None
        for i in idx:
            if i in picked:
                continue
            addm = M[i] & ~union & TR
            na = int(addm.sum())
            if na == 0 or (cur_n + na) / NTR > cap + 1e-12:
                continue
            la = int(y[addm].sum())
            rate = la / na
            if rate <= unt:
                continue
            key = (rate, la)
            if best is None or key > best[0]:
                best = (key, i)
        if best is None:
            return picked, union
        picked.append(best[1])
        union |= M[best[1]]


def union_report(union, y=Y):
    s = stats(union, y)
    tr, te = s["train"], s["test"]
    need = max(0, math.ceil(LTE - (1 - NEED_WR) * (NTE - te["n"]) - 1e-9))
    need_tr = max(0, math.ceil(LTR - (1 - NEED_WR) * (NTR - tr["n"]) - 1e-9))
    return dict(train_share=tr["share"], train_L=tr["L"], train_untouched_wr=tr["wr_untouched"], train_need=need_tr,
                test_share=te["share"], test_n=te["n"], test_L=te["L"], test_L_share=te["L_share"], test_untouched_wr=te["wr_untouched"],
                test_need=need, test_expected=te["expected"], test_excess=te["L"] - te["expected"])


print(BAR)
print("4. GREEDY UNION on TRAIN (cap = share of TRAIN trades); TEST scored once.  'need' = losses the union must hold for the untouched zone to "
      "reach 99.3%")
UNIONS = {}
for label, pool in (("STRICT survivors", STRICT), ("LOOSER survivors (lift>=2 vs test base)", LOOSE),
                    ("EXTENDED strict (+B notes)", EXT_STRICT), ("EXTENDED looser (+B notes)", EXT_LOOSE),
                    ("BLIND train-screened (fully out-of-sample)", BLIND)):
    UNIONS[label] = {}
    allu = np.zeros(N, bool)
    for n in pool:
        allu |= P[n][1]
    sat = union_report(allu)
    UNIONS[label]["all"] = sat
    print(f" {label}: pool {[SHORT[n] for n in pool]} | ALL of them together: train {100 * sat['train_share']:.1f}% / test "
          f"{100 * sat['test_share']:.1f}% of trades, test {sat['test_L']}/60 L (random {sat['test_expected']:.1f}), test untouched WR "
          f"{100 * sat['test_untouched_wr']:.2f}% (99.3% needs {sat['test_need']} L inside) | train {sat['train_L']}/112 L, untouched "
          f"{100 * sat['train_untouched_wr']:.2f}%")
    for cap in CAPS:
        picked, union = greedy(pool, Y, cap)
        r = union_report(union)
        r["picked"] = [SHORT[NAMES[i]] for i in picked]
        UNIONS[label][str(cap)] = r
        satur = " (pool saturated below the cap)" if r["train_share"] < cap - 0.01 else ""
        print(f"   cap {int(100 * cap):2d}%: picked {r['picked']}{satur}")
        print(f"      train {100 * r['train_share']:5.1f}% trades, {r['train_L']:3d}/{LTR} L ({100 * r['train_L'] / LTR:4.1f}%), untouched WR "
              f"{100 * r['train_untouched_wr']:.2f}% (need {r['train_need']} L)")
        print(f"      TEST  {100 * r['test_share']:5.1f}% trades ({r['test_n']}), {r['test_L']:3d}/{LTE} L captured ({100 * r['test_L_share']:4.1f}%; a random "
              f"set this size holds {r['test_expected']:.1f}), untouched WR {100 * r['test_untouched_wr']:.2f}% | 99.3% needs {r['test_need']} L "
              f"inside -> short by {max(0, r['test_need'] - r['test_L'])}")
OUT["unions"] = UNIONS


# ---------------------------------------------------------------- 5. permutation nulls
def shuffled(rng):
    y = Y.copy()
    y[TR] = rng.permutation(Y[TR])
    y[TE] = rng.permutation(Y[TE])
    return y


def screen(pool, y, rule, H):
    return [n for n in pool if rule(half_stats(P[n][1], H, y))]


def run_null(kind, pool_fixed, rule_test, real):
    """literal  : pool fixed, both halves shuffled, greedy redone on shuffled TRAIN (the task's recipe);
       selection: the TEST survival screen is re-run on the shuffled TEST labels over the 22 official pockets, then the same greedy.
       (A 're-screen fixed pockets on shuffled TRAIN' null for the blind pipeline is NOT used: those pockets were found by searching the
        real train labels, so under shuffling almost none pass and the null collapses to zero - far too lenient.)"""
    rng = np.random.default_rng(SEED)
    rec = {str(cap): {"L": [], "ex": [], "share": [], "k": []} for cap in CAPS}
    for _ in range(NPERM):
        y = shuffled(rng)
        if kind == "literal":
            pool = pool_fixed
        else:  # selection-aware
            pool = screen(OFFICIAL, y, rule_test, TE)
        for cap in CAPS:
            picked, union = greedy(pool, y, cap) if pool else ([], np.zeros(N, bool))
            nte = int((union & TE).sum())
            L = int(y[union & TE].sum())
            ex = L - nte / NTE * LTE
            r = rec[str(cap)]
            r["L"].append(L)
            r["ex"].append(ex)
            r["share"].append(nte / NTE)
            r["k"].append(len(pool))
    res = {}
    for cap in CAPS:
        r = rec[str(cap)]
        L, ex = np.array(r["L"]), np.array(r["ex"])
        rl = real[str(cap)]
        res[str(cap)] = dict(real_L=rl["test_L"], real_excess=round(rl["test_excess"], 2), real_share=rl["test_share"],
                             null_L_mean=float(L.mean()), null_L_p95=float(np.percentile(L, 95)), null_L_max=int(L.max()),
                             null_ex_mean=float(ex.mean()), null_ex_p95=float(np.percentile(ex, 95)), null_ex_max=float(ex.max()),
                             null_share_mean=float(np.mean(r["share"])), null_pool_mean=float(np.mean(r["k"])),
                             null_frac_empty=float(np.mean(np.array(r["k"]) == 0)),
                             p_raw=(1 + int((L >= rl["test_L"]).sum())) / (1 + NPERM),
                             p_excess=(1 + int((ex >= rl["test_excess"] - 1e-9).sum())) / (1 + NPERM))
    return res


print(BAR)
print(f"5. PERMUTATION NULLS ({NPERM} draws; wins shuffled within each half; p = (1 + #null >= real) / {NPERM + 1})")
PERM = {}
for label, kind, pool, rule, ulabel in (
        ("(a) LITERAL, strict survivors fixed [CIRCULAR - survivors were screened on real TEST]", "literal", STRICT, None, "STRICT survivors"),
        ("(b) SELECTION-AWARE strict: screen re-run on shuffled TEST, then greedy on shuffled TRAIN [HEADLINE]", "selection", None, strict_ok,
         "STRICT survivors"),
        ("(a') LITERAL, looser survivors fixed [CIRCULAR]", "literal", LOOSE, None, "LOOSER survivors (lift>=2 vs test base)"),
        ("(b') SELECTION-AWARE looser", "selection", None, loose_ok, "LOOSER survivors (lift>=2 vs test base)"),
        ("(c) FULLY BLIND: pool screened on TRAIN only (test never seen) -> literal recipe is VALID here", "literal", BLIND, None,
         "BLIND train-screened (fully out-of-sample)")):
    res = run_null(kind, pool, rule, UNIONS[ulabel])
    PERM[label] = res
    print(f" {label}")
    for cap in CAPS:
        r = res[str(cap)]
        print(f"   cap {int(100 * cap):2d}%: REAL test {r['real_L']:2d}/60 L (excess {r['real_excess']:+5.1f}, test share {100 * r['real_share']:4.1f}%) | NULL "
              f"captured mean {r['null_L_mean']:4.1f} p95 {r['null_L_p95']:4.1f} max {r['null_L_max']:2d}; excess mean {r['null_ex_mean']:+5.2f} p95 "
              f"{r['null_ex_p95']:+5.2f} max {r['null_ex_max']:+5.1f}; null pool size {r['null_pool_mean']:.1f} (empty in "
              f"{100 * r['null_frac_empty']:.0f}%), null test share {100 * r['null_share_mean']:.1f}% | p_raw {r['p_raw']:.3f}  p_excess {r['p_excess']:.3f}")
from scipy.stats import hypergeom  # noqa: E402

print(" (c2) cross-check for the blind unions: union FIXED as chosen on real TRAIN, exact hypergeometric p of its TEST capture "
      "(TEST labels exchangeable)")
for cap in CAPS:
    r = UNIONS["BLIND train-screened (fully out-of-sample)"][str(cap)]
    ph = float(hypergeom.sf(r["test_L"] - 1, NTE, LTE, r["test_n"]))
    PERM.setdefault("(c2) blind fixed-union hypergeometric", {})[str(cap)] = dict(test_L=r["test_L"], test_n=r["test_n"],
                                                                                 expected=r["test_expected"], p=ph)
    print(f"   cap {int(100 * cap):2d}%: {r['test_L']}/60 L in {r['test_n']} test trades (random {r['test_expected']:.1f}) -> p = {ph:.3f}")
OUT["permutation"] = PERM

# ---------------------------------------------------------------- 5b. overlap with the angel's existing guards
print(BAR)
GUARD = ((mod >= 1005) & (mod < 1065)) | (c["spread_pips"] >= 1.0 - E)   # InpUhvNoClose 16:45-17:44 NY + InpUhvMaxTrigSpread 1.0
print("5b. How much of each survivor the angel ALREADY blocks by its session/spread guards (not 16:45-17:44 NY; breakout spread < 1.0 pip)")
for n in EXT_LOOSE:
    m = P[n][1]
    tl = int(Y[m & TE].sum())
    gl = int(Y[m & TE & GUARD].sum())
    tr_n = int((m & TE).sum())
    g_n = int((m & TE & GUARD).sum())
    print(f"   {SHORT[n]:5s} test trades inside the guards {g_n}/{tr_n} ({100 * g_n / max(tr_n, 1):3.0f}%) | test losses inside the guards {gl}/{tl}")
for label in ("STRICT survivors", "LOOSER survivors (lift>=2 vs test base)"):
    allu = np.zeros(N, bool)
    for n in (STRICT if label.startswith("STRICT") else LOOSE):
        allu |= P[n][1]
    rest = allu & ~GUARD
    print(f"   {label}: union holds {int(Y[allu & TE].sum())}/60 test L; OUTSIDE the existing guards it holds {int(Y[rest & TE].sum())} L in "
          f"{int((rest & TE).sum())} test trades ({100 * (rest & TE).sum() / NTE:.1f}%)")
gs = stats(GUARD)
print(f"   REFERENCE - skip ONLY the angel's existing session/spread guards: train {100 * gs['train']['share']:.1f}% trades {gs['train']['L']}/112 L, "
      f"untouched {100 * gs['train']['wr_untouched']:.2f}% | test {100 * gs['test']['share']:.1f}% trades {gs['test']['L']}/60 L, untouched "
      f"{100 * gs['test']['wr_untouched']:.2f}%")
OUT["guard_overlap"] = {n: dict(test_L=int(Y[P[n][1] & TE].sum()), test_L_in_guard=int(Y[P[n][1] & TE & GUARD].sum())) for n in EXT_LOOSE}
OUT["guard_only"] = gs

# ---------------------------------------------------------------- 6. doctrine
print(BAR)
print("6. doctrine.python_says (CLAUDE.md: the only sanctioned way to quote a Python win rate; its 16-point haircut was measured on a different "
      "payoff geometry, but it is mandatory)")
for label in ("STRICT survivors", "LOOSER survivors (lift>=2 vs test base)", "BLIND train-screened (fully out-of-sample)"):
    for cap in (0.10, 0.25):
        r = UNIONS[label][str(cap)]
        python_says(f"TEST untouched zone, {label}, cap {int(100 * cap)}% (pockets skipped)", win_pct=100 * r["test_untouched_wr"],
                    need_pct=100 * NEED_WR)
json.dump(OUT, open(os.path.join(HERE, "recompute.json"), "w", encoding="utf-8"), indent=1,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("wrote", os.path.join(HERE, "recompute.json"))
