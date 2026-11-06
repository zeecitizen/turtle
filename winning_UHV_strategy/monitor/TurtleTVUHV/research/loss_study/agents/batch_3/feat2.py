"""feat2.py - extra features (breakout minute, spread proxy, session clocks) appended to feat.pkl rows."""
import os, pickle, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import api  # noqa: E402
A, PIP = api.A, api.PIP
R = pickle.load(open(os.path.join(HERE, "feat.pkl"), "rb"))
byid = {t["id"]: api._blind(t) for t in api.TRADES}
for r in R:
    t = byid[r["id"]]; k, s, lv = t["k"], t["side"], t["level"]
    c = A.c
    r["sec"] = t["t_in"] % 60
    r["brk_span"] = (t["brk_hi_so_far"] - t["brk_lo_so_far"]) / PIP
    r["brk_back"] = ((t["brk_hi_so_far"] - c[k]) if s < 0 else (c[k] - t["brk_lo_so_far"])) / PIP   # first moved against, in the break minute
    r["gap_ck"] = ((c[k] - lv) if s < 0 else (lv - c[k])) / PIP
    r["slip"] = (t["fill"] - lv) * s / PIP                                       # buys: ~ the spread; sells: ~ -0.1
    r["tickrate"] = t["brk_ticks_so_far"] / max(r["sec"], 1) * 60 / max(t["uhv_v"], 1)
    w = t["t_in"] % (7 * 86400)                   # seconds since Thursday 00:00 UTC (epoch was a Thursday)
    r["min_to_fri_close"] = ((1 * 86400 + 21 * 3600) - w) / 60.0                  # Friday 21:00 UTC = Thu + 1d 21h
    r["min_from_sun_open"] = (w - (3 * 86400 + 21 * 3600)) / 60.0                 # Sunday 21:00 UTC = Thu + 3d 21h
    r["camStk_raw"] = t["camStk"]
pickle.dump(R, open(os.path.join(HERE, "feat.pkl"), "wb"))
print("ok", len(R))
