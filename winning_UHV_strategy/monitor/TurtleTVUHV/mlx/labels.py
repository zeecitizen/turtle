"""mlx/labels.py - Triple Barrier labels (de Prado) on the tester's M15 candles, as mlx/FEATURE_SPEC.md § Labels.

At bar i (close c[i]): upper = c + up * ATR[i], lower = c - dn * ATR[i], time = `bars` forward bars. Bars i+1 .. i+bars are walked in order;
h[j] >= upper touches the upper barrier, l[j] <= lower the lower one. Label 1 / -1 for the first touch, 0 when neither is touched in time.
Both in the same bar j: the 1-minute candles inside bar j decide (the first minute to touch one barrier; a minute touching both, or no minute
touching either - the M1 export does not always reach the M15 high - leaves it 0). Bars without `bars` forward bars get touch_k = -1 (dropped).
Also: touch_k = the bar that decided the label (i + bars for a time-out), for purging; ret_fwd = (c[i+bars] - c[i]) / ATR."""
import os

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np                                     # noqa: E402
from numba import njit                                 # noqa: E402


@njit(cache=True)
def _tb(h, l, c, atr, h1, l1, m0, m1, up, dn, bars):
    n = c.shape[0]
    label = np.zeros(n, np.int8)
    touch = np.full(n, -1, np.int64)
    ret = np.full(n, np.nan)
    st = np.zeros(4, np.int64)                      # same-bar ties, decided by a minute, same-minute ties, no minute touched
    for i in range(n - bars):
        a = atr[i] if atr[i] > 1e-6 else 1e-6
        u = c[i] + up * a
        d = c[i] - dn * a
        lab = 0
        tk = i + bars
        for j in range(i + 1, i + bars + 1):
            hu = h[j] >= u
            hd = l[j] <= d
            if hu and hd:
                st[0] += 1
                r = 0
                hit = False
                for m in range(m0[j], m1[j]):
                    mu = h1[m] >= u
                    md = l1[m] <= d
                    if mu and md:
                        st[2] += 1
                        hit = True
                        break
                    if mu:
                        r = 1
                        hit = True
                        st[1] += 1
                        break
                    if md:
                        r = -1
                        hit = True
                        st[1] += 1
                        break
                if not hit:
                    st[3] += 1
                lab = r
                tk = j
                break
            elif hu:
                lab = 1
                tk = j
                break
            elif hd:
                lab = -1
                tk = j
                break
        label[i] = lab
        touch[i] = tk
        ret[i] = (c[i + bars] - c[i]) / a
    return label, touch, ret, st


def triple_barrier(D, up=1.5, dn=1.5, bars=24, stats=None):
    """-> (label int8 [n], touch_k int64 [n] (-1 = no `bars` forward bars), ret_fwd float64 [n]); stats (a dict) receives the tie counts"""
    h, l, c, atr = (np.ascontiguousarray(D[k], dtype=np.float64) for k in ("h15", "l15", "c15", "atr"))
    h1, l1 = (np.ascontiguousarray(D[k], dtype=np.float64) for k in ("h1", "l1"))
    k1 = np.ascontiguousarray(D["k1"], dtype=np.int64)
    n = len(c)
    m0 = np.searchsorted(k1, np.arange(n), side="left")
    m1 = np.searchsorted(k1, np.arange(n), side="right")
    label, touch, ret, st = _tb(h, l, c, atr, h1, l1, m0, m1, float(up), float(dn), int(bars))
    if stats is not None:
        stats.update({"same_bar_ties": int(st[0]), "decided_by_minute": int(st[1]), "same_minute_tie": int(st[2]), "no_minute_touch": int(st[3]),
                      "up": float(up), "dn": float(dn), "bars": int(bars)})
    return label, touch, ret
