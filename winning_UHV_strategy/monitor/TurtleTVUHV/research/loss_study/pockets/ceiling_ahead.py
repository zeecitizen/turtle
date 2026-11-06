"""ceiling_ahead.py - the last angel loss 1023-145031-B bought 1.0 pip under a QUADRUPLE TOP at 1.12065 (14:15, 14:22, 14:23, 14:24 UTC) that
is NOT a round figure, on a Friday at 10:50 NY. Post-hoc screens on the zone trade lists (base / secure / tight), by half:
  ceiling   a level the highs (buy) / lows (sell) touched >= T times (each within W pip) in the last N candles, sitting STRICTLY ahead of the
            UHV level by dmin..dmax pips (dmin > 0 so the UHV candle's own high - the level itself - never counts as the ceiling)
  friday    Friday from H:00 New York
  rangetop  buying dmin..dmax pips under the N-candle high (selling above the N-candle low)
Reads only candles <= k. Run: py research/loss_study/pockets/ceiling_ahead.py"""
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
PIP = 1e-4
SPLIT = 1782864000
NY = ZoneInfo("America/New_York")
z = np.load(os.path.join(LS, "arrays.npz"))
h, l = z["h"], z["l"]
STK = {nm: json.load(open(os.path.join(LS, "tight", f"trades_{nm}.json"), encoding="utf-8")) for nm in ("base", "secure", "tight")}


def ceiling(tr, T, N, W, dmin, dmax):
    k, s, lev = tr["k"], tr["side"], tr["level"]
    ext = h[k - N + 1:k + 1] if s > 0 else l[k - N + 1:k + 1]
    for c in np.unique(np.round(ext / (0.1 * PIP))) * 0.1 * PIP:
        d = (c - lev) / PIP if s > 0 else (lev - c) / PIP
        if dmin - 1e-6 <= d <= dmax + 1e-6 and int(np.sum(np.abs(ext - c) <= W * PIP + 1e-9)) >= T:
            return True
    return False


def friday(tr, H):
    ny = dt.datetime.fromtimestamp(tr["t_dec"], NY)
    return ny.weekday() == 4 and ny.hour >= H


def rangetop(tr, N, dmin, dmax):
    k, s, lev = tr["k"], tr["side"], tr["level"]
    ext = h[k - N + 1:k + 1].max() if s > 0 else l[k - N + 1:k + 1].min()
    d = (ext - lev) / PIP if s > 0 else (lev - ext) / PIP
    return dmin - 1e-6 <= d <= dmax + 1e-6


def report(name, f):
    line = f"{name:48s}"
    for nm, S in STK.items():
        flag = np.array([f(t) for t in S]); win = np.array([t["win"] for t in S]); tt = np.array([t["t_dec"] for t in S])
        ins, il, L = int(flag.sum()), int((~win[flag]).sum()), int((~win).sum())
        lift = (il / max(ins, 1)) / max(L / max(len(S), 1), 1e-9)
        a, b = flag & (tt < SPLIT), flag & (tt >= SPLIT)
        ltr = (~win[a]).sum() / max(a.sum(), 1) / max((~win[tt < SPLIT]).mean(), 1e-9)
        lte = (~win[b]).sum() / max(b.sum(), 1) / max((~win[tt >= SPLIT]).mean(), 1e-9)
        extra = f" catches {[t['id'] for t, q in zip(S, flag) if q and not t['win']]} costs {ins - il}W" if nm == "tight" else ""
        line += f" | {nm}: {ins}/{len(S)} in, {il}/{L} L, x{lift:4.2f} (tr x{ltr:4.2f} te x{lte:4.2f}){extra}"
    print(line, flush=True)


print("=== tested ceiling STRICTLY ahead (any level)")
for T in (2, 3, 4):
    for N in (30, 60):
        for W in (0.1, 0.3):
            for dmin, dmax in ((0.3, 1.0), (0.3, 1.5), (0.5, 1.5), (0.5, 2.0)):
                report(f"ceiling x{T} in {N}, within {W}p, {dmin}-{dmax}p ahead", lambda t, T=T, N=N, W=W, a=dmin, b=dmax: ceiling(t, T, N, W, a, b))
print("=== Friday from H NY")
for H in (8, 9, 10, 11, 12, 13):
    report(f"Friday from {H} NY", lambda t, H=H: friday(t, H))
print("=== buying under the N-candle high (selling over the N-candle low)")
for N in (30, 60, 90):
    for dmin, dmax in ((0.5, 2.5), (1.0, 3.0), (1.5, 3.0)):
        report(f"N={N} extreme {dmin}-{dmax}p ahead", lambda t, N=N, a=dmin, b=dmax: rangetop(t, N, a, b))
