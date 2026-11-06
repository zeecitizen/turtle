"""feats2.py - extra decision-time features (relative spread from sim's per-minute spread, pivot double tops, fresh-extreme reversal UHVs)."""
import os
import pickle
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(HERE))
import api_tight as AT  # noqa: E402
import sim  # noqa: E402

A = AT.A
PIP = 1e-4
SP1 = np.asarray(sim.data("year1")["sp1"], dtype=float)
h, l, c, o, v = A.h, A.l, A.c, A.o, A.v


def pivots(k, p, look, lo_bar=None):
    """confirmed swing highs / lows with p bars each side, all bars <= k"""
    hs, ls = [], []
    for j in range(max(p, k - look), k - p + 1):
        if h[j] >= h[j - p:j].max() and h[j] >= h[j + 1:j + p + 1].max():
            hs.append((j, float(h[j])))
        if l[j] <= l[j - p:j].min() and l[j] <= l[j + 1:j + p + 1].min():
            ls.append((j, float(l[j])))
    return hs, ls


def feats2(t):
    k, ku, s, lv = t["k"], t["ku"], t["side"], t["level"]
    F = {}
    med = float(np.median(SP1[k - 59:k + 1])) / PIP
    F["sp_med60"] = med
    F["rel_spread"] = t["trig_spread_pips"] - med
    F["sp_ratio"] = (t["trig_spread_pips"] + 0.05) / (med + 0.05)
    for p, look in ((2, 120), (3, 240)):
        hs, ls = pivots(k, p, look)
        piv = [(b, x) for b, x in (hs if s > 0 else ls) if b < ku]        # swing extremes on the trade side, from before the UHV
        d = [((x - lv) * s / PIP, b) for b, x in piv]                      # + = beyond the level (overhead for a buy)
        F[f"piv{p}_near05"] = sum(1 for dd, b in d if -0.5 <= dd <= 0.5)
        F[f"piv{p}_near10"] = sum(1 for dd, b in d if -1.0 <= dd <= 1.0)
        F[f"piv{p}_near20"] = sum(1 for dd, b in d if -2.0 <= dd <= 2.0)
        above = [dd for dd, b in d if dd >= 0]
        F[f"piv{p}_overhead"] = min(above) if above else 99.0                # nearest swing extreme at / beyond the level
        F[f"piv{p}_n_overhead3"] = sum(1 for dd in above if dd <= 3.0)
    # fresh-extreme reversal: how many bars between the trade-side extreme of the last 30 bars and the UHV, and how far the level is from it
    n = 30
    seg_ext = h[k - n + 1:k + 1] if s > 0 else l[k - n + 1:k + 1]
    j_ext = k - n + 1 + (int(np.argmax(seg_ext)) if s > 0 else int(np.argmin(seg_ext)))
    F["ext30_to_uhv"] = ku - j_ext                                         # < 0: the extreme came before the UHV
    # the retracement's opposite extreme (the stop anchor) vs the last 30 bars' opposite extreme: a retracement that made a new opposite low
    seg_opp = l[k - n + 1:k + 1] if s > 0 else h[k - n + 1:k + 1]
    F["retr_new_opp30"] = int(((t["extreme"] - (seg_opp.min() if s > 0 else seg_opp.max())) * s) <= 0.05 * PIP)
    # count of bars in last 60 whose close was beyond the level (how often price already sat past it)
    F["closes_beyond60"] = int(np.sum((c[k - 59:k + 1] - lv) * s > 0))
    return F


if __name__ == "__main__":
    D = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
    for st in D:
        T = {t["id"]: t for t in AT.STACKS[st]}
        for r in D[st]:
            r.update(feats2(AT._blind(T[r["_id"]])))
    pickle.dump(D, open(os.path.join(HERE, "feat.pkl"), "wb"))
    print("ok", len(D["secure"][0]))
