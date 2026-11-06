"""sell_support.py - Zee 2026-11-06: "rescan the losses for the support thing ... selling at support levels -> it can help us avoid 1-2 losses".
SELLS only. For every sell of the 97.7% setting (and of the angel's zones), is its UHV level sitting on a SUPPORT just below - where price can
bounce back up? Support definitions (all known at the last closed candle k):
  swing p/m     the last m swing lows confirmed with p candles each side (p = 3, 5, 10; m = 1..3)
  touches       a level the lows touched >= T times (within 0.5 pip) in the last N candles - a tested floor
  daylow        the lowest low of the current FX day (17:00 New York) so far / of the previous FX day
  figure        a 00 / 50 round figure (1.1200, 1.1250)
A sell is AT SUPPORT when the support sits 0..X pips below the level (or the level is through it by <= Y pips). Reports, per definition, on
each stack (base sells, secure sells, tight sells): sells in the pocket, losses in it, the pocket loss rate vs the stack's sell loss rate
(lift), by half - and which of the tight zone's sell losses it catches and how many tight sell winners it would cost.
Run: py research/loss_study/pockets/sell_support.py"""
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
t1, h, l = z["t"], z["h"], z["l"]
n = len(h)
STK = {nm: [x for x in json.load(open(os.path.join(LS, "tight", f"trades_{nm}.json"), encoding="utf-8")) if x["side"] < 0]
       for nm in ("base", "secure", "tight")}

PIV = {}
for p in (3, 5, 10):
    lo = np.zeros(n, bool)
    for i in range(p, n - p):
        lo[i] = l[i] == l[i - p:i + p + 1].min()
    PIV[p] = np.flatnonzero(lo)
fxday = np.array([(dt.datetime.fromtimestamp(int(x), NY) + dt.timedelta(hours=7)).toordinal() for x in t1])


def supports(kind, k, prm):
    if kind == "swing":
        p, m = prm
        idx = PIV[p]
        j = np.searchsorted(idx, k - p, side="right")
        sel = idx[max(0, j - m):j]
        return l[sel[sel >= k - 720]]
    if kind == "touches":
        T, N = prm
        lows = l[k - N + 1:k + 1]
        out = []
        for v in np.unique(np.round(lows / (0.5 * PIP))):
            lv = v * 0.5 * PIP
            if int(np.sum(np.abs(lows - lv) <= 0.5 * PIP)) >= T:
                out.append(lv)
        return np.array(out)
    if kind == "daylow":
        d = fxday[k]
        cur = np.flatnonzero(fxday[max(0, k - 1500):k + 1] == d) + max(0, k - 1500)
        prev = np.flatnonzero(fxday[max(0, k - 3000):k + 1] == d - 1) + max(0, k - 3000)
        out = []
        if prm in ("today", "both") and len(cur) > 1:
            out.append(l[cur[:-1]].min() if len(cur) > 1 else l[cur].min())
        if prm in ("yesterday", "both") and len(prev):
            out.append(l[prev].min())
        return np.array(out)
    if kind == "figure":
        return None
    raise ValueError(kind)


def at_support(tr, kind, prm, x, y):
    lev = tr["level"]
    if kind == "figure":
        g = prm * PIP
        f = np.floor(lev / g + 1e-9) * g                       # the round figure at or below the level
        d = (lev - f) / PIP
        return -y <= d <= x
    sv = supports(kind, tr["k"], prm)
    if sv is None or not len(sv):
        return False
    d = (lev - sv) / PIP                                        # + = the support is still below the level
    return bool(np.any((d >= -y) & (d <= x)))


DEFS = [("swing", (3, 1)), ("swing", (5, 1)), ("swing", (5, 2)), ("swing", (10, 1)), ("swing", (10, 2)), ("swing", (10, 3)),
        ("touches", (2, 60)), ("touches", (3, 60)), ("touches", (3, 120)), ("touches", (4, 240)),
        ("daylow", "today"), ("daylow", "yesterday"), ("daylow", "both"), ("figure", 100), ("figure", 50)]
tight_losses = [x["id"] for x in STK["tight"] if not x["win"]]
print("sells:", {k: (len(v), sum(1 for x in v if not x["win"])) for k, v in STK.items()}, "tight sell losses:", tight_losses)
rows = []
for kind, prm in DEFS:
    for x in (0.5, 1.0, 2.0):
        for y in (0.0, 0.5):
            line = f"{kind:7s} {str(prm):10s} within {x:3.1f} below / {y:3.1f} through |"
            ok = True
            res = {}
            for nm, S in STK.items():
                flag = np.array([at_support(tr, kind, prm, x, y) for tr in S])
                win = np.array([tr["win"] for tr in S]); tt = np.array([tr["t_dec"] for tr in S])
                ins = int(flag.sum()); il = int((~win[flag]).sum()); L = int((~win).sum())
                lift = (il / max(ins, 1)) / max(L / len(S), 1e-9)
                tr_m, te_m = flag & (tt < SPLIT), flag & (tt >= SPLIT)
                ltr = (~win[tr_m]).sum() / max(tr_m.sum(), 1) / max((~win[tt < SPLIT]).mean(), 1e-9)
                lte = (~win[te_m]).sum() / max(te_m.sum(), 1) / max((~win[tt >= SPLIT]).mean(), 1e-9)
                res[nm] = (ins, il, lift, ltr, lte)
                extra = ""
                if nm == "tight":
                    caught = [tr["id"] for tr, f_ in zip(S, flag) if f_ and not tr["win"]]
                    extra = f" catches {caught} costs {ins - il} wins"
                line += f" {nm}: {ins}/{len(S)} sells, {il}/{L} L, lift x{lift:4.2f} (tr x{ltr:4.2f} te x{lte:4.2f}){extra} |"
            rows.append((res["base"][2], line))
            print(line, flush=True)
print("\nTOP by base lift (needs base lift > 1 on both halves to mean anything):")
for lift, line in sorted(rows, key=lambda r: -r[0])[:8]:
    print(" ", line)
