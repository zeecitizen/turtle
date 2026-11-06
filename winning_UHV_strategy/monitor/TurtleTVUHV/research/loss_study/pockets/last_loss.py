"""last_loss.py - the angel zone's last loss (1023-145031-B, Fri 23 Oct 10:50 NY, closed by the weekly flatten at -40$).
1. FRIDAY cut-off: no Friday entries from H:00 New York (H = 8, 9, 10, 12, 13) - in the ENGINE, on the angel zone (+ the two fixes) and on the
   base, by half.
2. Zee's FAKE BREAKOUT check: "it broke the last higher high of the last hump but closed below it .. it broke with a wick" - before the entry:
   one of the last W closed candles poked above the last swing high (p-candle swing, confirmed before it) with its wick but CLOSED below it
   (a buy); a sell mirrors with lows. Post-hoc on the zone trade lists, by half.
Run: py research/loss_study/pockets/last_loss.py"""
import json
import os
import sys

import numpy as np

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(LS))
sys.path.insert(0, ROOT)
import uhv_engine as U  # noqa: E402

SPLIT = 1782864000
SAVED = os.path.join(ROOT, "settings", "saved")


def eng(fn, x):
    B = json.load(open(os.path.join(SAVED, fn), encoding="utf-8"))["inputs"]
    tr, _, _ = U.simulate(dict(B, **x))
    r = tr[tr[:, 10] == 0]
    L = r[:, 6] < 0; a = r[:, 1] < SPLIT
    return f"{len(r):5d} tr {int(L.sum()):3d} L WR {100 * (1 - L.mean()):6.2f}% (Mar-Jun {100 * (1 - L[a].mean()):6.2f} / Jul-Nov {100 * (1 - L[~a].mean()):6.2f}) net {r[:, 6].sum():+8.0f}"


print("=== 1. Friday cut-off (engine)")
ANGEL = "2026-11-06 15-00-00.json"           # angel tight zone + sell-support + wall
for h in (0, 8, 9, 10, 12, 13):
    x = {"InpUhvFriCutNY": str(h)} if h else {}
    print(f"Friday from {h:2d} NY | angel zone: {eng(ANGEL, x)} | no angel: {eng('2026-11-05 05-45-38.json', x)}", flush=True)

print("=== 2. Zee's fake breakout (a wick through the last swing, close back inside) - post-hoc")
z = np.load(os.path.join(LS, "arrays.npz"))
h_, l_, c_ = z["h"], z["l"], z["c"]
n = len(h_)
PIV = {}
for p in (1, 3, 5):
    ph = np.zeros(n, bool); pl = np.zeros(n, bool)
    for i in range(p, n - p):
        ph[i] = h_[i] == h_[i - p:i + p + 1].max(); pl[i] = l_[i] == l_[i - p:i + p + 1].min()
    PIV[p] = (np.flatnonzero(ph), np.flatnonzero(pl))
STK = {nm: json.load(open(os.path.join(LS, "tight", f"trades_{nm}.json"), encoding="utf-8")) for nm in ("base", "secure", "tight")}


def fake(t, p, W):
    k, s = t["k"], t["side"]
    hi, lo = PIV[p]
    for q in range(k - W + 1, k + 1):                          # each of the last W closed candles
        idx = hi if s > 0 else lo
        j = int(np.searchsorted(idx, q - p, side="right")) - 1  # the last swing confirmed BEFORE candle q
        if j < 0:
            continue
        sw = idx[j]
        if s > 0 and h_[q] > h_[sw] and c_[q] < h_[sw]:
            return True
        if s < 0 and l_[q] < l_[sw] and c_[q] > l_[sw]:
            return True
    return False


for p in (1, 3, 5):
    for W in (1, 2, 3, 5):
        line = f"swing p={p} wick-fake in last {W} candles"
        for nm, S in STK.items():
            flag = np.array([fake(t, p, W) for t in S]); win = np.array([t["win"] for t in S]); tt = np.array([t["t_dec"] for t in S])
            ins, il, L = int(flag.sum()), int((~win[flag]).sum()), int((~win).sum())
            lift = (il / max(ins, 1)) / max(L / len(S), 1e-9)
            a, b = flag & (tt < SPLIT), flag & (tt >= SPLIT)
            ltr = (~win[a]).sum() / max(a.sum(), 1) / max((~win[tt < SPLIT]).mean(), 1e-9)
            lte = (~win[b]).sum() / max(b.sum(), 1) / max((~win[tt >= SPLIT]).mean(), 1e-9)
            ex = f" catches {[t['id'] for t, q in zip(S, flag) if q and not t['win']]} costs {ins - il}W" if nm == "tight" else ""
            line += f" | {nm}: {ins}/{len(S)} in, {il}/{L} L, x{lift:4.2f} (tr x{ltr:4.2f} te x{lte:4.2f}){ex}"
        print(line, flush=True)
