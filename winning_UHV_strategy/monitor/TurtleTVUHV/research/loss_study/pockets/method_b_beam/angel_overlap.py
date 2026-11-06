"""angel_overlap.py - DIAGNOSTIC: the simple conditions that DO carry over (replicate.py / posthoc.py) are mostly rules the angel already has.
spread >= 1.0 pip at the breakout = InpUhvMaxTrigSpread 1.0; NY 16:45-17:44 = InpUhvNoClose; NY 16:00-17:59 (+ Friday from 13:00) = zone
InpUhvZClose (uhv_filters.py). These were written by the earlier loss study over BOTH halves, so their test numbers are NOT clean out-of-sample;
the thin-volume ones (vol10 <= 40.15, uhv_v <= 54.5) were noticed in replicate.py while looking at test. So every union below is an
OPTIMISTIC upper bound for simple pockets. Run: cd .../pockets && py method_b_beam/angel_overlap.py"""
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
d = pd.read_csv(os.path.join(os.path.dirname(HERE), "features.csv"))
d["day"] = d.id.str[:4]
y = 1 - d.win
m = d.ny_min_of_day
P = {
    "spread >= 1.0 pip (angel InpUhvMaxTrigSpread)": d.spread_pips > 0.95,
    "NY 16:45-17:44 (angel InpUhvNoClose)": (m >= 1005) & (m < 1065),
    "NY 16:00-17:59 + Fri from 13:00 (zone ZClose)": ((m >= 960) & (m < 1080)) | ((d.weekday == 4) & (m >= 780)),
    "NY 16:00-17:59 (post-hoc depth-1 pick)": (d.ny_hour >= 16) & (d.ny_hour <= 17),
    "vol10 <= 40.15": d.vol10 <= 40.15,
    "uhv_v <= 54.5": d.uhv_v <= 54.5,
}
k = list(P)
U = {
    "angel pocket rules: spread>=1.0 | NoClose": P[k[0]] | P[k[1]],
    "+ ZClose": P[k[0]] | P[k[1]] | P[k[2]],
    "+ ZClose + vol10<=40.15": P[k[0]] | P[k[1]] | P[k[2]] | P[k[4]],
    "+ ZClose + vol10<=40.15 + uhv_v<=54.5": P[k[0]] | P[k[1]] | P[k[2]] | P[k[4]] | P[k[5]],
}
for h in ("train", "test"):
    H = d.half == h
    N, L = int(H.sum()), int(y[H].sum())
    print(f"--- {h}: {N} trades, {L} losses, base WR {100*(1-L/N):.2f}%")
    for name, p in list(P.items()) + list(U.items()):
        mm = p & H
        n, l = int(mm.sum()), int(y[mm].sum())
        ld = d.loc[mm & (y == 1), "day"].nunique()
        mx = int(d.loc[mm & (y == 1)].groupby("day").size().max()) if l else 0
        need = int(np.ceil(L - 0.007 * (N - n)))
        print(f"  {name:46s} {100*n/N:5.2f}% ({n:3d}) losses {l:2d}/{L} ({100*l/L:4.1f}%) rate {100*l/max(n,1):5.2f}% ({(l/max(n,1))/(L/N):5.2f}x) "
              f"loss-days {ld:2d} maxday {mx} untouched WR {100*(1-(L-l)/(N-n)):.2f}%  [99.3% needs >= {need}]")
print(f"overlap spread>=1.0 & NoClose (all trades): {int((P[k[0]] & P[k[1]]).sum())} of {int(P[k[0]].sum())} / {int(P[k[1]].sum())}")
