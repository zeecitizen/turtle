"""zee_march_rules.py - Zee's March 2026 loss comments (settings/loss_comments.json, 2026-11-06) turned into rules and scored on every trade
of the 97.7% setting with api.py. Each rule reads only bars <= t["k"]. Run: py research/loss_study/zee_march_rules.py"""
import numpy as np

import api

PIP = api.PIP


def fresh_break(t, A, n_recent=3, n_swings=2):
    """"previous candle had broken last 2 humps high .. so we're in a now begun uptrend .. we shouldn't sell": a SELL is skipped when one of
    the last n_recent closed candles broke above the highest of the last n_swings swing highs before it (a BUY mirrors with lows)"""
    k = t["k"]
    hs, ls = A.pivots(k - n_recent, 1, 120)
    if t["side"] < 0:
        if len(hs) < n_swings:
            return False
        top = max(p for _, p in hs[-n_swings:])
        return float(A.h[k - n_recent + 1:k + 1].max()) > top
    if len(ls) < n_swings:
        return False
    bot = min(p for _, p in ls[-n_swings:])
    return float(A.l[k - n_recent + 1:k + 1].min()) < bot


def broke_many_highs(t, A, n=5, look=4):
    """"the last candle forming a high which broke at least 5 previous highs": SELL skipped when a candle in the last `look` closed candles
    made a high above the previous n swing highs (BUY mirrors)"""
    k = t["k"]
    hs, ls = A.pivots(k - look, 1, 240)
    if t["side"] < 0:
        return len(hs) >= n and float(A.h[k - look + 1:k + 1].max()) > max(p for _, p in hs[-n:])
    return len(ls) >= n and float(A.l[k - look + 1:k + 1].min()) < min(p for _, p in ls[-n:])


def exhausted(t, A, humps=5):
    """"bought after almost 6 upwards humps .. uptrend exhausted": skip when the camel has made `humps` or more humps of this colour in a row"""
    return abs(int(t["camStk"])) >= humps


def deep_retrace(t, A, frac=0.8, look=60):
    """"bought where price nearly retraced to its last low .. not enough momentum": BUY skipped when the retracement extreme is within
    (1-frac) of the swing range from the trend's last low to its last high (SELL mirrors)"""
    k = t["k"]
    hs, ls = A.pivots(k, 1, look)
    if len(hs) < 1 or len(ls) < 2:
        return False
    hi = max(p for _, p in hs)
    lo = min(p for _, p in ls[:-1]) if len(ls) > 1 else ls[0][1]
    if hi <= lo:
        return False
    if t["side"] > 0:
        return (hi - t["extreme"]) / (hi - lo) >= frac
    return (t["extreme"] - lo) / (hi - lo) >= frac


def htf5_against(t, A, n=12):
    """"maybe the 5 min timeframe could've confirmed the uptrend": skip when the 5-minute closes (the last n completed 5-minute candles,
    from the 1-minute bars up to k) slope against the trade"""
    k = t["k"]
    tt = A.t
    end = k
    while end >= 0 and (int(tt[end]) + 60) % 300 != 0:      # the last bar that closes a 5-minute candle
        end -= 1
    idx = [end - 5 * i for i in range(n)][::-1]
    if idx[0] < 0:
        return False
    closes = A.c[idx]
    slope = np.polyfit(np.arange(n), closes, 1)[0]
    return (slope < 0) if t["side"] > 0 else (slope > 0)


def htf5_ema_against(t, A, n=20):
    """the same idea with an EMA: skip when the last completed 5-minute close is on the wrong side of the n-period EMA of 5-minute closes"""
    k = t["k"]
    tt = A.t
    end = k
    while end >= 0 and (int(tt[end]) + 60) % 300 != 0:
        end -= 1
    idx = [end - 5 * i for i in range(3 * n)][::-1]
    if idx[0] < 0:
        return False
    closes = A.c[idx]
    a = 2.0 / (n + 1)
    e = closes[0]
    for x in closes[1:]:
        e = a * x + (1 - a) * e
    return (closes[-1] < e) if t["side"] > 0 else (closes[-1] > e)


if __name__ == "__main__":
    for nm, f in [("fresh_break 3c/2sw", fresh_break),
                  ("fresh_break 5c/2sw", lambda t, A: fresh_break(t, A, 5, 2)),
                  ("fresh_break 3c/3sw", lambda t, A: fresh_break(t, A, 3, 3)),
                  ("broke_5_highs look4", broke_many_highs),
                  ("broke_3_highs look4", lambda t, A: broke_many_highs(t, A, 3, 4)),
                  ("broke_5_highs look8", lambda t, A: broke_many_highs(t, A, 5, 8)),
                  ("exhausted >=5 humps", exhausted),
                  ("exhausted >=4 humps", lambda t, A: exhausted(t, A, 4)),
                  ("exhausted >=6 humps", lambda t, A: exhausted(t, A, 6)),
                  ("deep_retrace 0.8", deep_retrace),
                  ("deep_retrace 0.9", lambda t, A: deep_retrace(t, A, 0.9)),
                  ("htf5 slope12 against", htf5_against),
                  ("htf5 slope6 against", lambda t, A: htf5_against(t, A, 6)),
                  ("htf5 ema20 against", htf5_ema_against),
                  ("htf5 ema50 against", lambda t, A: htf5_ema_against(t, A, 50))]:
        api.report(f, nm)
