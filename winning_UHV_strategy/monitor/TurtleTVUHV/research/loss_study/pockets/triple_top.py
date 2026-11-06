"""triple_top.py - Zee 2026-11-06, the loss of 8 April 12:56 PKT: bought at 1.16999 right under a TRIPLE TOP (highs 1.16996 / 1.16997 / 1.17000)
sitting on the 1.1700 figure; the 0.1-pip target was exactly that ceiling. Rule family: a BUY whose level sits 0..X pips below a level that
the HIGHS touched >= T times (each within W pips of it) in the last N closed candles - a tested ceiling (a SELL mirrors with lows: a tested
floor). Optional: only when that ceiling is also near a round figure. Scored per zone (base / secure / tight) with halves, the tight losses it
catches and the winners it costs. Reads only candles <= k. Run: py research/loss_study/pockets/triple_top.py"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
PIP = 1e-4
SPLIT = 1782864000
z = np.load(os.path.join(LS, "arrays.npz"))
h, l = z["h"], z["l"]
STK = {nm: json.load(open(os.path.join(LS, "tight", f"trades_{nm}.json"), encoding="utf-8")) for nm in ("base", "secure", "tight")}


def tested(tr, T, N, W, X, fig=None):
    k, s, lev = tr["k"], tr["side"], tr["level"]
    ext = h[k - N + 1:k + 1] if s > 0 else l[k - N + 1:k + 1]      # candle highs (buy) / lows (sell)
    # candidate ceilings: each candle extreme in the window
    for c in np.unique(np.round(ext / (0.1 * PIP))) * 0.1 * PIP:
        d = (c - lev) / PIP if s > 0 else (lev - c) / PIP            # + = the tested level is still ahead of the entry
        if not (0 <= d <= X):
            continue
        if int(np.sum(np.abs(ext - c) <= W * PIP)) >= T:
            if fig is None:
                return True
            g = fig * PIP
            f = round(c / g) * g
            if abs(c - f) <= 1.0 * PIP:
                return True
    return False


def report(name, f, side=None):
    line = f"{name:46s}"
    for nm, S in STK.items():
        S = [t for t in S if side is None or t["side"] == side]
        flag = np.array([f(t) for t in S]); win = np.array([t["win"] for t in S]); tt = np.array([t["t_dec"] for t in S])
        ins, il, L = int(flag.sum()), int((~win[flag]).sum()), int((~win).sum())
        lift = (il / max(ins, 1)) / max(L / max(len(S), 1), 1e-9)
        a, b = flag & (tt < SPLIT), flag & (tt >= SPLIT)
        ltr = (~win[a]).sum() / max(a.sum(), 1) / max((~win[tt < SPLIT]).mean(), 1e-9)
        lte = (~win[b]).sum() / max(b.sum(), 1) / max((~win[tt >= SPLIT]).mean(), 1e-9)
        extra = f" catches {[t['id'] for t, q in zip(S, flag) if q and not t['win']]} costs {ins - il}W" if nm == "tight" else ""
        line += f" | {nm}: {ins}/{len(S)} in, {il}/{L} L, x{lift:4.2f} (tr x{ltr:4.2f} te x{lte:4.2f}){extra}"
    print(line, flush=True)


for T in (2, 3, 4):
    for N in (30, 60, 120):
        for W in (0.2, 0.5):
            for X in (0.5, 1.0):
                report(f"tested x{T} in {N} bars, within {W}p, ahead <= {X}p", lambda t, T=T, N=N, W=W, X=X: tested(t, T, N, W, X))
print("--- the same, only when the tested level is on a round 00 figure (+-1 pip)")
for T in (2, 3):
    for N in (60, 120):
        report(f"tested x{T} in {N} bars + 00 figure, ahead <= 1p", lambda t, T=T, N=N: tested(t, T, N, 0.5, 1.0, fig=100))
