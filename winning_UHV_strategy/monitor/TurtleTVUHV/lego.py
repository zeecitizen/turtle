"""lego.py - Strategy Lego (Zee 2026-10-21: "we work on the core fundamentals of the strategy visually ... it breaks down the strategy so much that it
becomes like lego pieces. and we can turn off a piece or change it replace it with multiple options").

The EA's core pieces, as the engine sees them:
  1. the moving averages   (which lines define the trend and the location)        -> ef / es arrays
  2. the location          (where the setup candle must be: on an EMA, ...)       -> OL: per candle, may it be a BUY (bit 1) / SELL (bit 2) setup
  3. the setup candle      (pin bar / hammer / star / marubozu, or another shape)  -> OS: per candle, 1 BUY, -1 SELL, 2 either side, 0 none
  4-7. the filters, the trigger, the stop and the exit are the EA's own inputs (and the Exit Lab).
Pieces 1-3 that are not the EA's are "Lab only": the tester runs them, MT5 cannot until they are built into the EA."""
import numpy as np
from numba import njit

import sim
import sim_full

MA = {"ema": "EMA (the EA's)", "sma": "SMA - simple average", "wma": "WMA - weighted average"}
LOC = {"ea": "On an EMA (the EA's rule: the candle touches it)", "near_fast": "Near the fast line (within k x ATR)", "near_slow": "Near the slow line (within k x ATR)",
       "trend": "Trend side only (BUY above the slow line, SELL below)", "any": "Anywhere (no location rule)"}
CANDLE = {"ea": "The EA's shapes (pin bar, hammer, shooting star, marubozu)", "ea_engulf": "The EA's shapes + engulfing", "engulfing": "Engulfing",
          "inside": "Inside bar (breaks either way)", "outside": "Outside bar", "momentum": "Momentum candle (big body, big range)", "any": "Any candle (its colour gives the side)"}


@njit(cache=True)
def _ea_shapes(o, h, l, c, atr, P):
    n = o.shape[0]
    out = np.zeros(n, dtype=np.int64)
    for i in range(n):
        s, _k = sim_full._shape(o[i], h[i], l[i], c[i], atr[i], P)
        out[i] = s
    return out


def _ma(c, n, kind, seed_arr):
    n = max(1, int(n))
    if kind == "sma":
        cs = np.cumsum(np.insert(c, 0, 0.0))
        out = np.empty_like(c)
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
        out[:n - 1] = [c[:i + 1].mean() for i in range(n - 1)]
        return out
    if kind == "wma":
        w = np.arange(1, n + 1, dtype=np.float64)
        out = np.convolve(c, w[::-1] / w.sum(), mode="full")[:len(c)]
        out[:n - 1] = [np.average(c[:i + 1], weights=np.arange(1, i + 2)) for i in range(n - 1)]
        return out
    return seed_arr


def pieces(lego, inputs, ds, P, ef, es):
    D = sim.data(ds)
    o, h, l, c, atr = D["o15"], D["h15"], D["l15"], D["c15"], D["atr"]
    n = len(c)
    ma = lego.get("ma", "ema")
    if ma != "ema":
        ef, es = _ma(c, P[0], ma, ef), _ma(c, P[1], ma, es)
    OS = np.full(n, 9, dtype=np.int64)
    OL = np.full(n, 9, dtype=np.int64)
    cd = lego.get("candle", "ea")
    if cd != "ea":
        po, ph, pl, pc = np.r_[o[0], o[:-1]], np.r_[h[0], h[:-1]], np.r_[l[0], l[:-1]], np.r_[c[0], c[:-1]]
        col = np.sign(c - o).astype(np.int64)
        rng = np.maximum(h - l, 1e-9)
        if cd in ("engulfing", "ea_engulf"):
            bull = (c > o) & (pc < po) & (c >= po) & (o <= pc)
            bear = (c < o) & (pc > po) & (c <= po) & (o >= pc)
            s = np.where(bull, 1, np.where(bear, -1, 0)).astype(np.int64)
            if cd == "ea_engulf":
                e = _ea_shapes(o, h, l, c, atr, P)
                s = np.where(e != 0, e, s)
        elif cd == "inside":
            s = np.where((h < ph) & (l > pl), 2, 0).astype(np.int64)
        elif cd == "outside":
            s = np.where((h > ph) & (l < pl), col, 0).astype(np.int64)
        elif cd == "momentum":
            kb, ka = float(lego.get("mom_body", 0.6)), float(lego.get("mom_atr", 1.0))
            s = np.where((np.abs(c - o) >= kb * rng) & (rng >= ka * atr), col, 0).astype(np.int64)
        else:
            s = col
        OS = s
    lc = lego.get("loc", "ea")
    if lc != "ea":
        k = float(lego.get("loc_k", 0.5))
        if lc == "near_fast":
            m = np.where(np.abs(c - ef) <= k * atr, 3, 0)
        elif lc == "near_slow":
            m = np.where(np.abs(c - es) <= k * atr, 3, 0)
        elif lc == "trend":
            m = np.where(c > es, 1, np.where(c < es, 2, 0))
        else:
            m = np.full(n, 3)
        OL = m.astype(np.int64)
    return ef, es, OS, OL
