"""feats.py - decision-time features for every trade of the loss-study stacks (work_secure30, 2026-11-06).
Reads ONLY t's decision fields and bars <= t["k"] (plus the breakout-minute tick fields brk_* known at the decision tick).
Python replay = HYPOTHESIS, NOT PROMOTED."""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import api_tight as AT  # noqa: E402

A = AT.A
PIP = 1e-4
NY = ZoneInfo("America/New_York")
LDN = ZoneInfo("Europe/London")
o, h, l, c, v, atr, adx = A.o, A.h, A.l, A.c, A.v, A.atr, A.adx


def er(k, n):
    cc = c[k - n:k + 1]
    p = float(np.abs(np.diff(cc)).sum())
    return abs(float(cc[-1] - cc[0])) / p if p > 0 else 0.0


def feats(t):
    k, ku, s = t["k"], t["ku"], t["side"]
    lv, ex = t["level"], t["extreme"]
    F = {}
    d = dt.datetime.fromtimestamp(t["t_dec"], dt.timezone.utc)
    ny = d.astimezone(NY)
    F["hour_utc"] = d.hour + d.minute / 60
    F["ny_min"] = ny.hour * 60 + ny.minute
    F["dow"] = d.weekday()
    F["minute"] = d.minute
    F["side"] = s
    F["humps"] = t["humps"]
    F["er16"] = t["er16"]
    for n in (5, 8, 12, 24, 30, 45, 60, 90, 120, 240):
        F[f"er{n}"] = er(k, n)
        F[f"mv{n}"] = (c[k] - c[k - n]) * s / PIP                  # signed move over n bars (+ = with the trade)
    F["atr"] = t["atr_pips"]
    F["adx"] = float(adx[k])
    F["atr_rel240"] = float(atr[k] / max(np.mean(atr[k - 240:k + 1]), 1e-9))
    F["box"] = t["box"]
    F["spread"] = t["trig_spread_pips"]
    F["brk_ticks"] = t["brk_ticks"]
    F["uhv_v"] = t["uhv_v"]
    F["loud"] = t["brk_ticks"] / max(t["uhv_v"], 1)
    F["ext_dist"] = (lv - ex) * s / PIP                             # level beyond the retracement's extreme (stop = this + 19 pips)
    F["bars_since_uhv"] = k - ku
    F["gap"] = (t["brk_bid"] - lv) * s / PIP                        # how far past the level the crossing bid printed
    F["run_in"] = (t["brk_bid"] - c[k]) * s / PIP                   # last close -> crossing bid
    F["brk_rng"] = (t["brk_hi"] - t["brk_lo"]) / PIP
    F["brk_dip"] = ((c[k] - t["brk_lo"]) if s > 0 else (t["brk_hi"] - c[k])) / PIP   # adverse dip inside the breakout minute before the break
    F["lvl_vs_close"] = (lv - c[k]) * s / PIP                       # level beyond the last close
    # UHV candle
    rg = max(h[ku] - l[ku], 1e-9)
    F["uhv_col"] = np.sign(c[ku] - o[ku]) * s                       # -1 = counter-coloured (the canonical red UHV for a buy)
    F["uhv_body"] = abs(c[ku] - o[ku]) / rg
    F["uhv_rng_atr"] = rg / max(atr[k], 1e-9)
    F["uhv_cl"] = ((c[ku] - l[ku]) / rg) if s > 0 else ((h[ku] - c[ku]) / rg)   # close location toward the trade (1 = closed at the trade-side end)
    F["uhv_vrel20"] = v[ku] / max(np.mean(v[ku - 20:ku]), 1)
    F["uhv_vrel60"] = v[ku] / max(np.mean(v[ku - 60:ku]), 1)
    # last closed candle
    rk = max(h[k] - l[k], 1e-9)
    F["k_col"] = np.sign(c[k] - o[k]) * s
    F["k_body"] = abs(c[k] - o[k]) / rk
    F["k_rng_atr"] = rk / max(atr[k], 1e-9)
    F["k_cl"] = ((c[k] - l[k]) / rk) if s > 0 else ((h[k] - c[k]) / rk)
    F["k_vrel20"] = v[k] / max(np.mean(v[k - 20:k]), 1)
    F["v15_v120"] = np.mean(v[k - 14:k + 1]) / max(np.mean(v[k - 119:k + 1]), 1)
    F["v5_v60"] = np.mean(v[k - 4:k + 1]) / max(np.mean(v[k - 59:k + 1]), 1)
    F["vol_lvl60"] = float(np.mean(v[k - 59:k + 1]))
    # structure: room to the recent extreme on the trade side, distance from the opposite extreme
    for n in (5, 10, 15, 20, 30, 60, 120, 240):
        hi, lo = float(h[k - n + 1:k + 1].max()), float(l[k - n + 1:k + 1].min())
        if s > 0:
            F[f"room{n}"] = (hi - lv) / PIP                         # > 0: the level is below the n-bar high (overhead)
            F[f"run{n}"] = (lv - lo) / PIP                          # how far above the n-bar low
            F[f"since_ext{n}"] = k - (k - n + 1 + int(np.argmax(h[k - n + 1:k + 1])))
            F[f"since_opp{n}"] = k - (k - n + 1 + int(np.argmin(l[k - n + 1:k + 1])))
        else:
            F[f"room{n}"] = (lv - lo) / PIP
            F[f"run{n}"] = (hi - lv) / PIP
            F[f"since_ext{n}"] = k - (k - n + 1 + int(np.argmin(l[k - n + 1:k + 1])))
            F[f"since_opp{n}"] = k - (k - n + 1 + int(np.argmax(h[k - n + 1:k + 1])))
        F[f"pos{n}"] = F[f"run{n}"] / max(F[f"run{n}"] + F[f"room{n}"], 1e-9)
        F[f"rng{n}_atr"] = (hi - lo) / max(atr[k], 1e-9)
        F[f"rng{n}"] = (hi - lo) / PIP
    # touches of the level (bars whose trade-side extreme came within x pips of the level, before the UHV)
    for n in (30, 60, 120):
        seg = h[k - n + 1:k + 1] if s > 0 else l[k - n + 1:k + 1]
        F[f"touch{n}_05"] = int(np.sum(np.abs(seg - lv) <= 0.5 * PIP))
        F[f"touch{n}_10"] = int(np.sum(np.abs(seg - lv) <= 1.0 * PIP))
        F[f"beyond{n}"] = int(np.sum((seg - lv) * s > 0))               # bars that already traded beyond the level
    # the biggest single candle against the trade in the last 15 / 30 bars, in ATRs
    for n in (15, 30):
        mv = (c[k - n + 1:k + 1] - o[k - n + 1:k + 1]) * s
        F[f"maxagainst{n}"] = float(-mv.min() / max(atr[k], 1e-9))
        F[f"maxwith{n}"] = float(mv.max() / max(atr[k], 1e-9))
    # retracement length: bars from the n-bar trade-side extreme to k
    return F


def table(stack):
    T = AT.STACKS[stack]
    rows = []
    for t in T:
        F = feats(AT._blind(t))
        F["_id"] = t["id"]; F["_win"] = t["win"]; F["_tr"] = t["t_dec"] < AT.SPLIT; F["_pnl"] = t["pnl"]
        rows.append(F)
    return rows


if __name__ == "__main__":
    import pickle
    out = {st: table(st) for st in ("secure", "base", "tight")}
    pickle.dump(out, open(os.path.join(HERE, "feat.pkl"), "wb"))
    print({k: len(v) for k, v in out.items()})
