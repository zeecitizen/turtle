"""common.py (pockets/method_a_trees) - shared loading + scoring for METHOD A (trees / boosting) of Zee's risky-pocket study (2026-11-06).
Loads ../features.csv (one row per base-setting trade, decision-time features; win / pnl / half are outcomes and NEVER inputs), sorts by the
decision time encoded in the id (MMDD-HHMMSS UTC, 2026) and adds:
  spread_excess = breakout spread minus the median breakout spread of the previous 50 trades (decision-time: earlier trades only). The feed's
                  spread steps from ~0.5 to ~0.1 pip on 2026-06-09, inside train, so raw spread_pips only marks the regime; it is NOT an input.
  ANGEL         = approximation of the tight angel (humps 2-3, er16 0.30-0.45, not 16:45-17:45 New York, breakout spread < 1.0 pip). On the
                  base rows it keeps 495 trades / 3 losses vs the engine's 714 / 4 (RiskMgr 2 changes which trades exist) -> approximate.
pstats(mask) scores a pocket on train and test: share of trades, losses in it (of the half's total), loss rate, lift vs the half's own loss
rate, one-sided binomial p P(X >= losses), distinct New York loss-days, the untouched zone's WR when the pocket is skipped entirely, and the
WR when the angel only filters inside the pocket.  Python replay = HYPOTHESIS, NOT PROMOTED."""
import math
import os

import numpy as np
import pandas as pd
from scipy.stats import binom

HERE = os.path.dirname(os.path.abspath(__file__))
POCK = os.path.dirname(HERE)
MONTHS_TR = ("03", "04", "05", "06")
MONTHS_TE = ("07", "08", "09", "10", "11")

_cols = list(pd.read_csv(os.path.join(POCK, "features.csv"), nrows=0).columns)
RAW = _cols[1:-3]
assert len(RAW) == 32 and _cols[-3:] == ["win", "pnl", "half"], _cols
FEATS = [f for f in RAW if f != "spread_pips"] + ["spread_excess"]
INTF = {"side", "humps", "ny_hour", "ny_min_of_day", "weekday", "bars_since_uhv", "box", "struct_with"}

d = pd.read_csv(os.path.join(POCK, "features.csv"))
d["loss"] = 1 - d["win"]
d["ts"] = pd.to_datetime("2026" + d["id"].str[:11], format="%Y%m%d-%H%M%S", utc=True)
d = d.sort_values("ts", kind="stable").reset_index(drop=True)
d["ny_date"] = d["ts"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
d["month"] = d["ts"].dt.strftime("%m")
_prev = d["spread_pips"].shift(1).rolling(50, min_periods=1).median().fillna(d["spread_pips"].iloc[0])
d["spread_excess"] = (d["spread_pips"] - _prev).round(3)
ROLL = (d["ny_min_of_day"] >= 16 * 60 + 45) & (d["ny_min_of_day"] < 17 * 60 + 45)
ANGEL = (d["humps"].isin([2, 3]) & (d["er16"] >= 0.30) & (d["er16"] <= 0.45) & ~ROLL & (d["spread_pips"] < 1.0)).values



def add_scale_free(df):
    """ratios that stay comparable across the Jun-9 feed change (decision-time: rolling medians read earlier trades only)."""
    roll_med = lambda s, n: s.shift(1).rolling(n, min_periods=1).median().fillna(s)  # noqa: E731  (first trade: its own value)
    df["stop_atr"] = (df["stop_pips"] / df["atr_pips"]).round(3)
    df["room60_atr"] = (df["room60_pips"] / df["atr_pips"]).round(3)
    df["room240_atr"] = (df["room240_pips"] / df["atr_pips"]).round(3)
    df["gap_atr"] = (df["gap_pips"] / df["atr_pips"]).round(3)
    df["fig_ahead_atr"] = (df["fig_ahead_pips"] / df["atr_pips"]).round(3)
    df["uhv_rel"] = (df["uhv_v"] / df["vol10"].clip(lower=1)).round(3)
    df["atr_rel"] = (df["atr_pips"] / roll_med(df["atr_pips"], 300)).round(3)
    df["vol10_rel"] = (df["vol10"] / roll_med(df["vol10"], 300)).round(3)
    return df


add_scale_free(d)
TR = (d["half"] == "train").values
TE = (d["half"] == "test").values
Y = d["loss"].values.astype(int)
MON = d["month"].values
X = d[FEATS].values.astype(float)


def pval(k, n, p):
    return float(binom.sf(k - 1, n, p)) if k > 0 and n > 0 else 1.0


def wilson_lb(k, n, z=1.645):
    if n == 0:
        return 0.0
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


def pstats(mask):
    mask = np.asarray(mask, bool)
    out = {}
    for h, H in (("train", TR), ("test", TE)):
        m = mask & H
        n, L = int(H.sum()), int(Y[H].sum())
        nr, Lr = int(m.sum()), int(Y[m].sum())
        p0 = L / n
        lr = Lr / nr if nr else 0.0
        un_n, un_L = n - nr, L - Lr
        ma = m & ANGEL
        months = MONTHS_TR if h == "train" else MONTHS_TE
        an_n, an_L = un_n + int(ma.sum()), un_L + int(Y[ma].sum())
        mon = {}
        for mo in months:
            mm = H & (MON == mo)
            k = m & mm
            mon[mo] = [int(k.sum()), int(Y[k].sum()), round((Y[k].mean() / Y[mm].mean()) if k.sum() and Y[mm].mean() > 0 else 0.0, 2)]
        exp_m = sum(int((m & (MON == mo)).sum()) * Y[H & (MON == mo)].mean() for mo in months if (H & (MON == mo)).sum())
        out[h] = dict(n=nr, n_half=n, share=round(nr / n, 4), L=Lr, L_half=L, L_share=round(Lr / L, 4), loss_rate=round(lr, 4),
                      lift=round(lr / p0, 2) if nr else 0.0, lift_month_adj=round(Lr / exp_m, 2) if exp_m else 0.0,
                      p_binom=round(pval(Lr, nr, p0), 5),
                      loss_days=int(d.loc[m & (Y == 1), "ny_date"].nunique()),
                      wr_base=round(100 * (1 - p0), 2), wr_untouched=round(100 * (1 - un_L / un_n), 2),
                      wr_angel_inside=round(100 * (1 - an_L / an_n), 2), angel_kept_in_pocket=int(ma.sum()), months=mon,
                      months_up=sum(1 for v in mon.values() if v[2] > 1.0))
    return out


def fmt(s, h):
    x = s[h]
    return (f"{h:5s} {100 * x['share']:5.1f}% trades ({x['n']:4d}) | {x['L']:3d}/{x['L_half']} L ({100 * x['L_share']:4.0f}%) | LR {100 * x['loss_rate']:5.2f}% "
            f"lift {x['lift']:4.2f}x (m-adj {x['lift_month_adj']:4.2f}) p={x['p_binom']:.3g} | {x['loss_days']:2d} loss-days | months up {x['months_up']}/{len(x['months'])} | "
            f"untouched WR {x['wr_untouched']:.2f}% (base {x['wr_base']:.2f}) angel-inside {x['wr_angel_inside']:.2f}%")


def need(share, h):
    """losses a pocket of this share must hold for the untouched zone to reach 99.3% WR (0.7% losses)."""
    H = TR if h == "train" else TE
    n, L = int(H.sum()), int(Y[H].sum())
    return max(0, math.ceil(L - 0.007 * n * (1 - share)))


def bounds(conds):
    b = {}
    for f, op, thr in conds:
        lo, hi = b.get(f, (-math.inf, math.inf))
        if op == "<=":
            hi = min(hi, thr)
        else:
            lo = max(lo, thr)
        b[f] = (lo, hi)
    return b


def bmask(b, df=None):
    df = d if df is None else df
    m = np.ones(len(df), bool)
    for f, (lo, hi) in b.items():
        x = df[f].values
        if lo > -math.inf:
            m &= x > lo
        if hi < math.inf:
            m &= x <= hi
    return m


def bstr(b):
    parts = []
    for f, (lo, hi) in b.items():
        if f in INTF:
            lo_i = math.floor(lo) + 1 if lo > -math.inf else None
            hi_i = math.floor(hi) if hi < math.inf else None
            if lo_i is not None and hi_i is not None:
                parts.append(f"{f} == {lo_i}" if lo_i == hi_i else f"{lo_i} <= {f} <= {hi_i}")
            elif lo_i is not None:
                parts.append(f"{f} >= {lo_i}")
            else:
                parts.append(f"{f} <= {hi_i}")
        else:
            if lo > -math.inf and hi < math.inf:
                parts.append(f"{lo:.4g} < {f} <= {hi:.4g}")
            elif lo > -math.inf:
                parts.append(f"{f} > {lo:.4g}")
            else:
                parts.append(f"{f} <= {hi:.4g}")
    return " and ".join(parts) if parts else "ALL"


def round_bounds(b):
    """thresholds rounded to 4 significant digits, as printed; membership is re-checked against the tree."""
    r = {}
    for f, (lo, hi) in b.items():
        r[f] = (float(f"{lo:.4g}") if lo > -math.inf else lo, float(f"{hi:.4g}") if hi < math.inf else hi)
    return r


def leaf_paths(clf, feats=FEATS):
    t = clf.tree_
    paths = {}

    def rec(node, conds):
        if t.children_left[node] == -1:
            paths[node] = conds
            return
        f, thr = feats[t.feature[node]], float(t.threshold[node])
        rec(t.children_left[node], conds + [(f, "<=", thr)])
        rec(t.children_right[node], conds + [(f, ">", thr)])

    rec(0, [])
    return paths
