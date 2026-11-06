"""uhv_ttd.py - Zee's Turtle Trader Desk indicator (pine, "Turtle Trader Desk v1.0") as settings of the UHV engine (TurtleTVUHV).

Zee 2026-11-05: "add all settings from the indicator code to the scanner" ... "skip the settings not relevant to UHV strategy (from the
indicator) -> or if they're requiring too big a change". With InpTtdOn the engine takes the indicator's ENTRY FILTERS and EXITS instead of the
UHV Diamond group's stop / target. The indicator's "$" distances (built for gold) are read as PIPS on EUR/USD, with its own default numbers.
Skipped: display, account / lot sizing, broker pip size, latency list, the breakout-test labels, the indicator's EMA 34/89 trend-strength engine
(mTS / aTS / sTC / uHTD / rSwT) and the detection settings that need a fresh scan per value (camOn / camPiv / camRet / camStrong / bRW / bRWW /
bRWLB / uVTOn as detection)."""
import math

import numpy as np
from numba import njit

PIP = 0.0001
# name: (default, kind, help) - kind: bool / enum / num
TTD = {
    "InpTtdOn": ("false", "bool", "use the Turtle Trader Desk indicator's entry filters and exits (this group) instead of the UHV Diamond stop / target"),
    "InpTtd_uDir": ("0", "enum", "trade direction: 0 both, 1 bull only, 2 bear only"),
    "InpTtd_rUS": ("false", "bool", "a candle must wick through / break the UHV low (high for sells) before the breakout"),
    "InpTtd_rULV": ("false", "bool", "the breakout candle must have lower volume than the UHV candle"),
    "InpTtd_uVTOn": ("false", "bool", "the UHV must be louder than the last N candles"),
    "InpTtd_uVLB": ("20", "num", "N for the UHV-louder-than test"),
    "InpTtd_uSBgOn": ("false", "bool", "background context: most of the last N candles before the UHV are red (buys) / green (sells)"),
    "InpTtd_uSBgN": ("5", "num", "background lookback, candles"),
    "InpTtd_uWSpOn": ("false", "bool", "wide-spread UHV: its range exceeds X x ATR(14)"),
    "InpTtd_uWSpK": ("1.5", "num", "wide-spread multiplier"),
    "InpTtd_uUHVWkOn": ("false", "bool", "UHV candle: its wicks together at most X% of its range"),
    "InpTtd_uUHVWkPct": ("60", "num", "UHV max combined wick %"),
    "InpTtd_uUHVBdOn": ("false", "bool", "UHV candle: its body at least X% of its range"),
    "InpTtd_uUHVBdPct": ("40", "num", "UHV min body %"),
    "InpTtd_uSB": ("0", "num", "candles that must pass after the UHV before the entry"),
    "InpTtd_uPBD": ("0", "num", "instant entry: fire this many pips BEFORE the breakout level (indicator default 1.0 $)"),
    "InpTtd_uPBsD": ("0", "num", "instant entry: wait for this many pips PAST the breakout level"),
    "InpTtd_uTM": ("0", "enum", "take profit: 0 R:R · 1 structural high / low · 2 fixed pips"),
    "InpTtd_uT1": ("7", "num", "take profit R:R"),
    "InpTtd_uTD": ("1.1", "num", "take profit fixed pips (method 2)"),
    "InpTtd_uSHLOff": ("0.5", "num", "structural target: this many pips before the level"),
    "InpTtd_uST": ("2", "enum", "stop: 0 UHV · 1 ATR · 2 breakout wick · 3 swing low · 4 fixed pips · 5 retracement min/max · 6 previous candle"),
    "InpTtd_uSBf": ("0.4", "num", "stop offset beyond its level, pips (+ = further away)"),
    "InpTtd_uSMn": ("0.2", "num", "the stop never closer than this to the entry, pips (not for the candle-anchored stops)"),
    "InpTtd_uSAm": ("1.0", "num", "ATR stop: x ATR"),
    "InpTtd_uSDo": ("2.0", "num", "fixed-pips stop distance (method 4)"),
    "InpTtd_uSSw": ("11", "num", "swing-low stop: candles back"),
    "InpTtd_uSLPips": ("15", "num", "stop override: fixed pips from the entry (0 = off, use the method)"),
    "InpTtd_uTPPips": ("52", "num", "take-profit override: fixed pips from the entry (0 = off, use the method)"),
    "InpTtd_uBEon": ("true", "bool", "breakeven: the stop to the entry when price reaches X% of the TP"),
    "InpTtd_uBEPct": ("10", "num", "breakeven trigger: % of the TP distance"),
    "InpTtd_uBERR": ("0.1", "num", "breakeven at R (0 = off; overrides the % above)"),
    "InpTtd_uBELkTP": ("false", "bool", "at breakeven lock the stop at the trigger price instead of the entry"),
    "InpTtd_uBELkR": ("0", "num", "at breakeven lock the stop at +X R (0 = off)"),
    "InpTtd_useInvalidation": ("true", "bool", "invalidation exit: close when a 1-minute candle closes back past the level below"),
    "InpTtd_iExOff": ("0.3", "num", "invalidation tolerance, pips"),
    "InpTtd_iExMode": ("1", "enum", "invalidation level: 0 the UHV range · 1 the UHV's midpoint · 2 the breakout body's midpoint"),
    "InpTtd_iExModeOff": ("1.0", "num", "invalidation offset, pips (adds to the tolerance)"),
    "InpTtd_uMAEPips": ("60", "num", "emergency stop: close at X pips against (0 = off)"),
    "InpTtd_uMAEDol": ("0", "num", "emergency stop: close at $X loss (0 = off; off once breakeven fires)"),
    "InpTtd_uKillSec": ("5", "num", "kill timer: close after X seconds (0 = off; off once breakeven fires)"),
    "InpTtd_uKillLossSec": ("0", "num", "kill timer, losers only: close if still in loss after X seconds (0 = off)"),
    "InpTtd_ptpOn": ("false", "bool", "partial take-profit + runner (the runner then has breakeven)"),
    "InpTtd_ptpPips": ("40", "num", "partial TP at +X pips"),
    "InpTtd_ptpPct": ("50", "num", "partial TP: % of the position closed"),
    "InpTtd_uMomB": ("false", "bool", "momentum breakout: body at least X% of its range"),
    "InpTtd_uMomBR": ("80", "num", "momentum min body %"),
    "InpTtd_uMomW": ("false", "bool", "momentum breakout: wicks at most X%"),
    "InpTtd_uMomWkD": ("30", "num", "max wick in the breakout direction, %"),
    "InpTtd_uMomWkO": ("30", "num", "max wick opposite the breakout, %"),
    "InpTtd_uBrkVROn": ("false", "bool", "the breakout's volume at least X% below the UHV's"),
    "InpTtd_uBrkVR": ("5", "num", "volume drop %"),
    "InpTtd_uTVOn": ("false", "bool", "tick velocity: the breakout's ticks per pip above K x its N-candle average"),
    "InpTtd_uTVK": ("1.2", "num", "tick velocity multiplier K"),
    "InpTtd_uTVN": ("5", "num", "tick velocity lookback N"),
    "InpTtd_uCd": ("0", "num", "cooldown: candles after a signal before another can fire"),
    "InpTtd_sFilt": ("false", "bool", "only London + New York (8-12 and 13-17 GMT)"),
    "InpTtd_avoidRng": ("false", "bool", "avoid ranging markets (ADX below the threshold)"),
    "InpTtd_rngTh": ("14", "num", "ranging threshold, ADX"),
    "InpTtd_pcTDist": ("0", "num", "trailing stop: X pips behind the price (0 = off)"),
    "InpTtd_pcTTrig": ("0", "num", "trailing starts after X pips of profit"),
    "InpTtd_pcTStep": ("3", "num", "the trail moves every X pips gained"),
    "InpTtd_pSlip": ("0", "num", "slippage per round, pips (added to the cost)"),
}


def fv(inp, k):
    v = inp.get(k, TTD[k][0])
    s = str(v).strip().lower()
    if s in ("true", "false"):
        return 1.0 if s == "true" else 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        d = TTD[k][0]
        return (1.0 if d == "true" else 0.0) if d in ("true", "false") else float(d)


def features(D, side, kb, ku, partial=None):
    """the UHV candle (ku), the breakout candle (kb) and their surroundings; partial = (open, high, low, close, ticks) of an unfinished breakout
    minute (the instant entry)"""
    o, h, l, c, v, atr = D["o1"], D["h1"], D["l1"], D["c1"], D["v1"], D["atr"]
    bo, bh, bl, bc, bv = (float(o[kb]), float(h[kb]), float(l[kb]), float(c[kb]), float(v[kb])) if partial is None else partial
    seg_l, seg_h = l[ku + 1:kb], h[ku + 1:kb]
    sweep = bool(len(seg_l)) and bool(float(seg_l.min()) < l[ku] if side > 0 else float(seg_h.max()) > h[ku])
    lo_, hi_ = max(0, kb - 100), kb
    rng = np.maximum(h[lo_:hi_] - l[lo_:hi_], 1e-6)
    return {"uo": float(o[ku]), "uh": float(h[ku]), "ul": float(l[ku]), "uc": float(c[ku]), "uv": float(v[ku]),
            "bo": bo, "bh": bh, "bl": bl, "bc": bc, "bv": bv, "ph": float(h[kb - 1]), "pl": float(l[kb - 1]), "nb": int(kb - ku),
            "atr_u": float(atr[ku]), "atr_b": float(atr[kb - 1]), "sweep": sweep,
            "bg": np.sign(c[max(0, ku - 30):ku] - o[max(0, ku - 30):ku]), "vprev": v[max(0, ku - 500):ku],
            "kb": kb, "imp": float(h[max(0, ku - 20):ku + 1].max()) if side > 0 else float(l[max(0, ku - 20):ku + 1].min()),
            "dens": bv / (max(bh - bl, 1e-6) / PIP), "dhist": v[lo_:hi_] / (rng / PIP)}


def entry_ok(F, side, inp, adx_b, hour_utc):
    """the indicator's entry filters -> None (pass) or the skip reason"""
    d = int(fv(inp, "InpTtd_uDir"))
    if (d == 1 and side < 0) or (d == 2 and side > 0):
        return "band_skip"
    if fv(inp, "InpTtd_rUS") > 0.5 and not F["sweep"]:
        return "no_break"
    if fv(inp, "InpTtd_rULV") > 0.5 and not F["bv"] < F["uv"]:
        return "no_break"
    if fv(inp, "InpTtd_uVTOn") > 0.5:
        n = max(1, int(fv(inp, "InpTtd_uVLB")))
        if len(F["vprev"]) and F["uv"] <= float(F["vprev"][-n:].max()):
            return "no_break"
    if fv(inp, "InpTtd_uSBgOn") > 0.5:
        n = max(1, int(fv(inp, "InpTtd_uSBgN")))
        bg = F["bg"][-n:]
        if (bg == (-1 if side > 0 else 1)).sum() <= n / 2:
            return "no_break"
    ur = max(F["uh"] - F["ul"], 1e-9)
    if fv(inp, "InpTtd_uWSpOn") > 0.5 and not ur > fv(inp, "InpTtd_uWSpK") * F["atr_u"]:
        return "no_break"
    if fv(inp, "InpTtd_uUHVWkOn") > 0.5 and (ur - abs(F["uc"] - F["uo"])) / ur * 100 > fv(inp, "InpTtd_uUHVWkPct"):
        return "no_break"
    if fv(inp, "InpTtd_uUHVBdOn") > 0.5 and abs(F["uc"] - F["uo"]) / ur * 100 < fv(inp, "InpTtd_uUHVBdPct"):
        return "no_break"
    if F["nb"] < fv(inp, "InpTtd_uSB"):
        return "no_break"
    br = max(F["bh"] - F["bl"], 1e-9)
    if fv(inp, "InpTtd_uMomB") > 0.5 and abs(F["bc"] - F["bo"]) / br * 100 < fv(inp, "InpTtd_uMomBR"):
        return "no_break"
    if fv(inp, "InpTtd_uMomW") > 0.5:
        wd = (F["bh"] - F["bc"]) if side > 0 else (F["bc"] - F["bl"])
        wo = (F["bo"] - F["bl"]) if side > 0 else (F["bh"] - F["bo"])
        if wd / br * 100 > fv(inp, "InpTtd_uMomWkD") or wo / br * 100 > fv(inp, "InpTtd_uMomWkO"):
            return "no_break"
    if fv(inp, "InpTtd_uBrkVROn") > 0.5 and not F["bv"] <= F["uv"] * (1 - fv(inp, "InpTtd_uBrkVR") / 100):
        return "no_break"
    if fv(inp, "InpTtd_uTVOn") > 0.5:
        n = max(1, int(fv(inp, "InpTtd_uTVN")))
        hist = F["dhist"][-n:]
        if len(hist) and not F["dens"] > fv(inp, "InpTtd_uTVK") * float(hist.mean()):
            return "no_break"
    if fv(inp, "InpTtd_sFilt") > 0.5 and not (8 <= hour_utc < 12 or 13 <= hour_utc < 17):
        return "band_skip"
    if fv(inp, "InpTtd_avoidRng") > 0.5 and adx_b < fv(inp, "InpTtd_rngTh"):
        return "adx"
    return None


def geometry(F, side, fill, extreme, inp, D):
    """the indicator's stop and target -> (stop pips, target pips, breakeven trigger pips, breakeven stop pips, invalidation price or 0)"""
    st = int(fv(inp, "InpTtd_uST"))
    off = fv(inp, "InpTtd_uSBf") * PIP
    if st == 0:
        lvl = (F["ul"] - off) if side > 0 else (F["uh"] + off)
    elif st == 1:
        lvl = fill - side * F["atr_b"] * fv(inp, "InpTtd_uSAm")
    elif st == 2:
        lvl = (F["bl"] - off) if side > 0 else (F["bh"] + off)
    elif st == 3:
        n = max(1, int(fv(inp, "InpTtd_uSSw")))
        kb = F["kb"]
        lvl = (float(D["l1"][max(0, kb - n):kb + 1].min()) - off) if side > 0 else (float(D["h1"][max(0, kb - n):kb + 1].max()) + off)
    elif st == 4:
        lvl = fill - side * fv(inp, "InpTtd_uSDo") * PIP
    elif st == 5:
        lvl = (extreme - off) if side > 0 else (extreme + off)
    else:
        lvl = (F["pl"] - off) if side > 0 else (F["ph"] + off)
    sl = (fill - lvl) * side / PIP
    if st not in (2, 6):                                           # the candle-anchored stops ignore the minimum distance, as the indicator does
        sl = max(sl, fv(inp, "InpTtd_uSMn"))
    sl = max(sl, 0.1)
    if fv(inp, "InpTtd_uSLPips") > 0:
        sl = fv(inp, "InpTtd_uSLPips")
    tm = int(fv(inp, "InpTtd_uTM"))
    if tm == 0:
        tp = fv(inp, "InpTtd_uT1") * sl
    elif tm == 1:
        tp = max((F["imp"] - fill) * side / PIP - fv(inp, "InpTtd_uSHLOff"), 0.1)
    else:
        tp = fv(inp, "InpTtd_uTD")
    if fv(inp, "InpTtd_uTPPips") > 0:
        tp = fv(inp, "InpTtd_uTPPips")
    be_t, be_s = 0.0, 0.0
    if fv(inp, "InpTtd_uBEon") > 0.5:
        be_t = fv(inp, "InpTtd_uBERR") * sl if fv(inp, "InpTtd_uBERR") > 0 else fv(inp, "InpTtd_uBEPct") / 100.0 * tp
        be_s = be_t if fv(inp, "InpTtd_uBELkTP") > 0.5 else (fv(inp, "InpTtd_uBELkR") * sl if fv(inp, "InpTtd_uBELkR") > 0 else 0.0)
    inv = 0.0
    if fv(inp, "InpTtd_useInvalidation") > 0.5:
        m = int(fv(inp, "InpTtd_iExMode"))
        base = (F["uh"] if side > 0 else F["ul"]) if m == 0 else (F["uh"] + F["ul"]) / 2 if m == 1 else (F["bo"] + F["bc"]) / 2
        inv = base - side * (fv(inp, "InpTtd_iExOff") + fv(inp, "InpTtd_iExModeOff")) * PIP
    return sl, tp, be_t, be_s, inv


@njit(cache=True)
def play(T, B, A, a, b, t0, side, lat, sl, tp, be_t, be_s, inv, mae_p, mae_usd_p, kill_s, kill_loss_s, ptp_p, ptp_f, tr_d, tr_trig, tr_step, slip):
    """one round with the indicator's exits (pips; R = sl) -> (pnl pips, t_in, fill, t_out, exit price, why, best, worst, partials)"""
    i = a
    while i < b and T[i] - t0 < lat:
        i += 1
    if i >= b:
        return 0.0, -1.0, 0.0, 0.0, 0.0, -1, 0.0, 0.0, 0
    fill = A[i] if side > 0 else B[i]
    t_in = T[i] - t0
    stop, left, pnl, best, worst, parts, why = -sl, 1.0, -slip, -1e9, 1e9, 0, 0
    be_done, ptp_done = False, False
    minute = math.floor(T[i] / 60.0)
    for j in range(i, b):
        px = B[j] if side > 0 else A[j]
        mj = math.floor(T[j] / 60.0)
        if inv != 0.0 and mj > minute and j > i:                    # a 1-minute candle just closed: its close = the previous tick's bid
            cl = B[j - 1]
            if (cl - inv) * side < 0:
                m0 = (px - fill) * side / 0.0001
                pnl += left * m0
                return pnl, t_in, fill, T[j] - t0, px, 12, best, worst, parts
        minute = mj
        m = (px - fill) * side / 0.0001
        el = T[j] - t0 - t_in
        if m > best:
            best = m
        if m < worst:
            worst = m
        if m <= stop:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, why if why > 0 else 1, best, worst, parts
        if tp > 0 and m >= tp:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 5, best, worst, parts
        if mae_p > 0 and m <= -mae_p:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 17, best, worst, parts
        if mae_usd_p > 0 and not be_done and m <= -mae_usd_p:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 17, best, worst, parts
        if kill_s > 0 and not be_done and el >= kill_s:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 8, best, worst, parts
        if kill_loss_s > 0 and not be_done and el >= kill_loss_s and m < 0:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 8, best, worst, parts
        if ptp_p > 0 and not ptp_done and m >= ptp_p:
            pnl += ptp_f * left * m
            left -= ptp_f * left
            ptp_done = True
            parts += 1
            if stop < 0:
                stop = 0.0
                why = 7
                be_done = True
            if left <= 1e-9:
                return pnl, t_in, fill, T[j] - t0, px, 11, best, worst, parts
        if be_t > 0 and not be_done and best >= be_t:
            be_done = True
            if be_s > stop:
                stop = be_s
                why = 7
        if tr_d > 0 and best >= tr_trig:
            lvl = best - tr_d
            if tr_step > 0:
                lvl = math.floor(lvl / tr_step) * tr_step
            if lvl > stop:
                stop = lvl
                why = 6
    px = B[b - 1] if side > 0 else A[b - 1]
    m = (px - fill) * side / 0.0001
    pnl += left * m
    return pnl, t_in, fill, T[b - 1] - t0, px, 8, best, worst, parts
