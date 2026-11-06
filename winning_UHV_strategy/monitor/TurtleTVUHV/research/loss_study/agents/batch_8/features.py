"""features.py (batch_8 study) - blind per-trade features for the loss study. Every feature reads ONLY bars <= t["k"] and the setup
fields (no outcome). Used to look for what separates the losses from the winners; the rules themselves live in rules.py.
Run:  py agents/batch_8/features.py   (from research/loss_study) -> writes agents/batch_8/features.pkl"""
import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
LS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, LS)
import api  # noqa: E402

A = api.A
PIP = api.PIP
o, h, l, c, v, t1 = A.o, A.h, A.l, A.c, A.v, A.t


# ---------------------------------------------------------------- camel replay with the previous hump's high (only past bars)
def camel_hist():
    """Replays build.py's camel loop (CAM_PIV 1) and records, after every closed bar i, the latest COMPLETED hump (l0, hh, l1) and the high of
    the hump before it - so a rule can ask Zee's question 'was the green hump a higher low AND a higher high?'."""
    N = len(h)
    p = 1
    lastH = np.full(N, np.nan); prevH = np.full(N, np.nan); lastL0 = np.full(N, np.nan); lastL1 = np.full(N, np.nan)
    lastHB = np.full(N, -1); lastB1 = np.full(N, -1)
    T, HB, HV, L0B, L0V, LB, LV = 0, None, None, None, None, None, None
    comp = []          # completed humps [l0, hh, l1, hb, b1]
    for i in range(2 * p, N):
        cc = i - p
        ph = all(not (h[cc] < h[cc + d] or h[cc] < h[cc - d]) for d in range(1, p + 1))
        pl = all(not (l[cc] > l[cc + d] or l[cc] > l[cc - d]) for d in range(1, p + 1))
        if ph:
            if T == 1:
                if h[cc] >= HV:
                    HB, HV = cc, h[cc]
            else:
                L0B, L0V, HB, HV, T = LB, LV, cc, h[cc], 1
        if pl:
            redraw = False
            if T == 1:
                LB, LV, T, redraw = cc, l[cc], -1, True
            elif T == -1 and l[cc] <= LV:
                LB, LV, redraw = cc, l[cc], True
            elif T == 0:
                LB, LV, T = cc, l[cc], -1
            if redraw and HB is not None and L0B is not None:
                row = [L0V, HV, LV, HB, LB]
                if comp and comp[-1][3] == HB:
                    comp[-1] = row
                else:
                    comp.append(row)
        if comp:
            lastL0[i], lastH[i], lastL1[i], lastHB[i], lastB1[i] = comp[-1][0], comp[-1][1], comp[-1][2], comp[-1][3], comp[-1][4]
            if len(comp) >= 2:
                prevH[i] = comp[-2][1]
    return lastL0, lastH, lastL1, prevH, lastHB, lastB1


def us_open_utc(ts):
    """8:30 New York in UTC seconds-of-day for that date (US DST 2026: Mar 8 - Nov 1 -> 12:30 UTC, else 13:30 UTC)."""
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc).date()
    dst = dt.date(2026, 3, 8) <= d < dt.date(2026, 11, 1)
    return (12 if dst else 13) * 3600 + 1800


def build():
    lastL0, lastH, lastL1, prevH, lastHB, lastB1 = camel_hist()
    rows = []
    for t in api.TRADES:
        k, ku, s = t["k"], t["ku"], t["side"]
        lv, ex, fill = t["level"], t["extreme"], t["fill"]
        sod = t["t_in"] % 86400
        dow = int(((t["t_in"] // 86400) + 4) % 7)          # 0 Mon .. 6 Sun (1970-01-01 Thursday -> 3)
        r = {"id": t["id"], "side": s, "t_in": t["t_in"], "win": t["win"], "pnl": t["pnl"], "why": t["why"],
             "train": t["t_in"] < api.SPLIT, "hour": sod / 3600.0, "dow": dow,
             "camStk": t["camStk"], "camEff": t["camEff"], "box": t["box"], "uhv_v": t["uhv_v"], "brk": t["brk_ticks_so_far"],
             "brk_ratio": t["brk_ticks_so_far"] / max(t["uhv_v"], 1), "stop_pips": t["stop_pips"],
             "depth": (lv - ex) * s / PIP if s > 0 else (ex - lv) / PIP,     # UHV level to the retracement extreme
             "spread_px": (fill - lv) * s / PIP,                              # ask-over-level (buy) / level-over-bid (sell)
             "bars_since_uhv": k - ku, "atr": A.atr[k] / PIP, "adx": A.adx[k]}
        r["depth"] = abs(lv - ex) / PIP
        # minutes to the US 8:30 release (positive = before)
        r["min_to_us830"] = (us_open_utc(t["t_in"]) - sod) / 60.0
        r["min_to_1400"] = ((us_open_utc(t["t_in"]) + 5400) - sod) / 60.0
        # room to the recent extreme beyond the level in the trade direction
        for N in (5, 10, 20, 30, 60, 120):
            if s > 0:
                r[f"room{N}"] = (h[k - N + 1:k + 1].max() - fill) / PIP
            else:
                r[f"room{N}"] = (fill - l[k - N + 1:k + 1].min()) / PIP
        # position of the level in the last N bars' range (0 = against, 1 = the extreme in the trade direction)
        for N in (30, 60, 120):
            hi, lo = h[k - N + 1:k + 1].max(), l[k - N + 1:k + 1].min()
            r[f"pos{N}"] = ((lv - lo) / (hi - lo) if s > 0 else (hi - lv) / (hi - lo)) if hi > lo else 0.5
            r[f"rng{N}"] = (hi - lo) / PIP
        # trend: price change in the trade direction
        for N in (15, 30, 60, 120, 240):
            r[f"mom{N}"] = (c[k] - c[k - N]) * s / PIP
        # touches: bars in the last N whose extreme (high for buy / low for sell) sits within x pips beyond the level
        for N in (30, 60):
            seg_h, seg_l = h[k - N + 1:k + 1], l[k - N + 1:k + 1]
            if s > 0:
                d = (seg_h - lv) / PIP
            else:
                d = (lv - seg_l) / PIP
            r[f"touch{N}_05"] = int(((d >= -0.2) & (d <= 0.5)).sum())
            r[f"touch{N}_10"] = int(((d >= -0.2) & (d <= 1.0)).sum())
            r[f"beyond{N}"] = int((d > 0.0).sum())                         # bars that traded beyond the level already
        # volume context
        r["uhv_rel60"] = t["uhv_v"] / max(np.median(v[k - 59:k + 1]), 1)
        r["vol10_60"] = v[k - 9:k + 1].mean() / max(v[k - 59:k + 1].mean(), 1)
        r["vol_k_rel"] = v[k] / max(np.median(v[k - 59:k + 1]), 1)
        r["vol_med60"] = float(np.median(v[k - 59:k + 1]))
        # Zee's camel-hump fix at k: the latest completed hump - higher low AND higher high (green) / lower low AND lower high (red)
        L0, HH, L1, PH = lastL0[k], lastH[k], lastL1[k], prevH[k]
        r["hump_hl"] = (L1 - L0) / PIP
        r["hump_hh"] = (HH - PH) / PIP
        r["hump_age"] = k - lastB1[k]
        if s > 0:
            r["hump_ok"] = bool(L1 > L0 and HH > PH)
        else:
            r["hump_ok"] = bool(L1 < L0 and HH < PH)
        # last closed candle shape
        rngk = h[k] - l[k]
        r["k_body"] = abs(c[k] - o[k]) / rngk if rngk > 0 else 0.0
        r["k_dir"] = np.sign(c[k] - o[k]) * s
        r["k_rng"] = rngk / PIP
        # breakout-minute so far
        r["brk_rng"] = (t["brk_hi_so_far"] - t["brk_lo_so_far"]) / PIP
        r["gap_open"] = (o[k + 1] - c[k]) * s / PIP if False else 0.0          # (k+1 open is the entry minute: not used)
        rows.append(r)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build()
    df.to_pickle(os.path.join(HERE, "features.pkl"))
    print(df.shape)
    print(df.groupby("win")[["room5", "room10", "room20", "depth", "spread_px", "bars_since_uhv", "uhv_rel60", "brk_ratio"]].median())
