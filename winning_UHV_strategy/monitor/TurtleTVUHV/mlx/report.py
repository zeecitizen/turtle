"""mlx/report.py - the trading translation of the Machine Learning tab: the EA's own trades, all vs the ones the model lets through.

Entries = simdata/mlx_entries.npz (data.py): setting B (src 0) and the setup UNIVERSE (src 1). A trade entered during bar k is scored with the
OUT-OF-FOLD probabilities of bar k-1 (the last closed bar before the entry) - never a probability from a model that saw that bar. A BUY is kept
when P(up) > thr, a SELL when P(down) > thr. Per year and total: n, WR, net, for all trades and for each threshold. Trades whose bar k-1 has no
dataset row (the first 600 warm-up bars) count in "all" and are reported as no_oof - the model cannot pass them. Tester P&L = hypothesis."""
from datetime import datetime, timezone

import numpy as np

THRESHOLDS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.9)
RULE = "BUY if P(up) > thr, SELL if P(down) > thr, features of the last closed bar before the entry, OOF probabilities"
SRC = {0: "B", 1: "universe"}


def _years(t):
    return np.array([datetime.fromtimestamp(int(v), timezone.utc).year for v in t], dtype=np.int64)


def agg(pnl):
    n = int(len(pnl))
    return {"n": n, "wr": round(100.0 * float((pnl > 0).mean()), 1) if n else 0.0, "net": round(float(pnl.sum()), 2) if n else 0.0}


def by_year(pnl, years, all_years):
    out = {str(int(y)): agg(pnl[years == y]) for y in all_years}
    out["total"] = agg(pnl)
    return out


def row_lookup(k15_rows):
    """dataset bar index -> row index (-1 when the bar has no row)"""
    k15_rows = np.asarray(k15_rows, dtype=np.int64)

    def look(k):
        k = np.asarray(k, dtype=np.int64)
        i = np.searchsorted(k15_rows, k)
        i = np.clip(i, 0, len(k15_rows) - 1)
        return np.where(k15_rows[i] == k, i, -1)
    return look


def translate(entries, k15_rows, P, thresholds=THRESHOLDS, up=2, dn=0):
    """entries: the npz (or a dict of its arrays); k15_rows: the dataset's k15; P [rows, 3] OOF probabilities (P(-1), P(0), P(1)).
    -> {"rule", "thresholds", "B": {"all", "at", "no_oof", ...}, "universe": {...}}"""
    look = row_lookup(k15_rows)
    out = {"rule": RULE + "; trades whose bar k-1 has no dataset row (warm-up) are in 'all' only (no_oof)", "thresholds": list(thresholds)}
    src_all, k_all, side_all, pnl_all, t_all = (np.asarray(entries[k]) for k in ("src", "k15", "side", "pnl", "entry_t"))
    for s, name in SRC.items():
        m = src_all == s
        if not m.any():
            out[name] = None
            continue
        k, side, pnl, yrs = k_all[m] - 1, side_all[m], pnl_all[m], _years(t_all[m])
        rows = look(k)
        has = rows >= 0
        p_up = np.where(has, P[np.where(has, rows, 0), up], np.nan)
        p_dn = np.where(has, P[np.where(has, rows, 0), dn], np.nan)
        all_years = sorted(set(int(y) for y in yrs))
        blk = {"all": by_year(pnl, yrs, all_years), "at": {}, "no_oof": int((~has).sum()), "matched": int(has.sum()),
               "buys": int((side > 0).sum()), "sells": int((side < 0).sum())}
        p_side = np.where(side > 0, p_up, p_dn)                                   # the probability the entry's own side needs
        blk["p_side"] = {"mean": round(float(np.nanmean(p_side)), 4) if has.any() else None,
                         "median": round(float(np.nanmedian(p_side)), 4) if has.any() else None,
                         "max": round(float(np.nanmax(p_side)), 4) if has.any() else None}
        for thr in thresholds:
            keep = has & (p_side > thr)
            yb = by_year(pnl[keep], yrs[keep], all_years)
            yb["total"]["buys"], yb["total"]["sells"] = int((keep & (side > 0)).sum()), int((keep & (side < 0)).sum())
            blk["at"][("%g" % thr)] = yb
        # the model's view vs the EA's: the win rate of the matched trades by P(side) decile, so the page can see whether P orders the P&L
        if has.any():
            q = np.nanpercentile(p_side[has], [0, 20, 40, 60, 80, 100])
            dec = []
            for a, b in zip(q[:-1], q[1:]):
                mm = has & (p_side >= a) & (p_side <= b)
                dec.append({"p_side": "%.3f-%.3f" % (a, b), **agg(pnl[mm])})
            blk["by_p_quintile"] = dec
        out[name] = blk
    return out
