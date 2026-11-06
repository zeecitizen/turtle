"""bounce_levels.py - two checks (Zee 2026-11-06):
1. MAJOR S/R both sides: a SELL within X pips above the last m major swing lows (p-candle swings), a BUY within X pips below the last m major
   swing highs - per zone (base / secure / tight), with the tight losses caught and the winners it costs.
2. BOUNCE LEVELS ("sometimes there's a price level from which the price gives a shooting star -> whenever price comes to that level it gives a
   loooonng candle upwards -> mark these areas from the past 2-3 trends"): in the last N candles (before k), every LONG candle (range > A x ATR)
   in the direction AGAINST our trade (a long green candle for a sell, a long red one for a buy) marks a bounce level at its low (high). A sell
   whose level sits 0..X pips above a bounce level (a buy 0..X below) is "selling into a bounce level".
All reads are bars <= k. Run: py research/loss_study/pockets/bounce_levels.py"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
PIP = 1e-4
SPLIT = 1782864000
z = np.load(os.path.join(LS, "arrays.npz"))
o, h, l, c, atr = z["o"], z["h"], z["l"], z["c"], z["atr"]
n = len(h)
STK = {nm: json.load(open(os.path.join(LS, "tight", f"trades_{nm}.json"), encoding="utf-8")) for nm in ("base", "secure", "tight")}
PIVH, PIVL = {}, {}
for p in (5, 10, 20):
    ph = np.zeros(n, bool); pl = np.zeros(n, bool)
    for i in range(p, n - p):
        ph[i] = h[i] == h[i - p:i + p + 1].max(); pl[i] = l[i] == l[i - p:i + p + 1].min()
    PIVH[p], PIVL[p] = np.flatnonzero(ph), np.flatnonzero(pl)


def major(tr, p, m, x):
    k, s, lev = tr["k"], tr["side"], tr["level"]
    idx = PIVL[p] if s < 0 else PIVH[p]
    j = np.searchsorted(idx, k - p, side="right")
    sel = idx[max(0, j - m):j]
    sel = sel[sel >= k - 720]
    if not len(sel):
        return False
    d = (lev - l[sel]) / PIP if s < 0 else (h[sel] - lev) / PIP
    return bool(np.any((d >= 0) & (d <= x)))


def bounce(tr, N, A, x):
    k, s, lev = tr["k"], tr["side"], tr["level"]
    a = atr[k - N + 1:k + 1]
    rng = h[k - N + 1:k + 1] - l[k - N + 1:k + 1]
    body = (c[k - N + 1:k + 1] - o[k - N + 1:k + 1]) * (-s)          # + = a candle against our trade (green for a sell)
    big = (rng > A * np.maximum(a, 1e-6)) & (body > 0.6 * rng)
    if not big.any():
        return False
    lv = (l[k - N + 1:k + 1] if s < 0 else h[k - N + 1:k + 1])[big]   # where the long counter-candle started
    d = (lev - lv) / PIP if s < 0 else (lv - lev) / PIP
    return bool(np.any((d >= 0) & (d <= x)))


def report(name, f, side=None):
    line = f"{name:44s}"
    for nm, S in STK.items():
        S = [t for t in S if side is None or t["side"] == side]
        flag = np.array([f(t) for t in S]); win = np.array([t["win"] for t in S]); tt = np.array([t["t_dec"] for t in S])
        ins, il, L = int(flag.sum()), int((~win[flag]).sum()), int((~win).sum())
        lift = (il / max(ins, 1)) / max(L / max(len(S), 1), 1e-9)
        ltr = (~win[flag & (tt < SPLIT)]).sum() / max((flag & (tt < SPLIT)).sum(), 1) / max((~win[tt < SPLIT]).mean(), 1e-9)
        lte = (~win[flag & (tt >= SPLIT)]).sum() / max((flag & (tt >= SPLIT)).sum(), 1) / max((~win[tt >= SPLIT]).mean(), 1e-9)
        extra = f" catches {[t['id'] for t, q in zip(S, flag) if q and not t['win']]} costs {ins - il}W" if nm == "tight" else ""
        line += f" | {nm}: {ins}/{len(S)} in, {il}/{L} L, x{lift:4.2f} (tr x{ltr:4.2f} te x{lte:4.2f}){extra}"
    print(line, flush=True)


print("=== 1. MAJOR S/R - buys into the last major swing highs (mirror of the sell result)")
for p in (5, 10, 20):
    for m in (1, 2, 3):
        for x in (0.5, 1.0, 2.0):
            report(f"BUY p={p} last {m} within {x}", lambda t, p=p, m=m, x=x: major(t, p, m, x), side=1)
print("=== 1b. MAJOR S/R - sells into the last major swing lows (p=20 added)")
for m in (1, 2, 3):
    for x in (0.5, 1.0, 2.0):
        report(f"SELL p=20 last {m} within {x}", lambda t, m=m, x=x: major(t, 20, m, x), side=-1)
print("=== 2. BOUNCE LEVELS (long counter-candles in the last N candles) - both sides")
for N in (120, 240, 480, 720):
    for A in (2.0, 3.0, 4.0):
        for x in (0.5, 1.0, 2.0):
            report(f"bounce N={N} long>{A}ATR within {x}", lambda t, N=N, A=A, x=x: bounce(t, N, A, x))
