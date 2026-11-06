"""uhv_engine.py - the Turtle TV Tester's engine for Zee's UHV Diamond (TurtleTVUHV). Replaces sim.simulate() in this copy, so the Overview,
the Exit Lab (Test every exit / Find the best exit / Claude's Exit Research Lab) and the other tools all run the UHV strategy.

Zee 2026-11-05: "the individual saad settings we found can be reused mostly because i want to test if saad's settings work / effect our uhv
strategy -> its important that we have those original saad settings too for us to try on the uhv breakout candle".

ENTRIES  the UHV setups (uhv_setups.json: camel-hump trend -> retracement -> loudest counter-coloured candle -> first quieter candle closing
         beyond it), chosen by InpUhvMode (every setup / the EA v1.27's own picks / royal), InpUhvMinLaws, InpUhvMinEr; and - with InpUhvSaad
         on - Saad's own entry settings judged on the UHV BREAKOUT candle (candle shapes + range x ATR, ADX / ATR gates, EMA trend filters,
         higher timeframe, chop ER, session hours, weekday, spread, buys / sells, cool-down after a loss, day loss / target).
FILL     the first PrimeXBT tick InpUhvLatency s after the breakout candle closed: a buy at the ask, a sell at the bid.
EXITS    replayed tick by tick (a buy exits on the bid, a sell on the ask): the stop InpUhvSlPips, the target InpUhvTpPips, Saad's breakeven
         (InpBeUsd, as pips) and VSISA lock (InpLockAtUsd / InpLockUsd, as pips), and every Exit Lab exit that needs no candle closes:
         targets in R / ATR / pips, partials, breakeven, lock ladder, trails (pips / ATR / keep k%), loss cutters, decay stop, time and
         no-progress exits (N minutes). Not yet: EMA / candle-close exits (cx, fb, tr 4-8), ADX-faded, Friday close.
A round still open 24 h after the breakout closes at that tick ("time exit"). One position at a time (a round blocks later setups).
Returns the Saad tester's row format: [side, t_in, fill, sl, t_out, exit, $ profit, 0, 0, 0, ghost 0, 0, 0, why, R pips, best pips]."""
import json
import datetime as _dt
from zoneinfo import ZoneInfo as _ZI
import math
import os
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")   # the ARM laptop's LLVM needs the generic CPU model (as exitlab.py)
import numpy as np  # noqa: E402
from numba import njit  # noqa: E402

import uhv_diamond
import sim
import uhv_ticks
import uhv_ttd
import uhv_filters

HERE = Path(__file__).resolve().parent
PIP = 0.0001
MAX_HOLD_S = 24 * 3600     # a round still open after 24 h closes at that tick ("time exit")
_NY = _ZI("America/New_York")

UHV_DEFAULTS = {                          # the "UHV Diamond" settings group (shown first in the panel)
    "InpUhvMode": ("0", "which setups: 0 every UHV setup (Zee's full rule) · 1 only the ones the EA v1.27 itself takes · 2 only royal (EA + clean 15-minute market)"),
    "InpUhvMinLaws": ("0", "at least this many of the counted laws (sweep before the UHV · close beyond EMA-5 · clean quiet breakout), 0-3"),
    "InpUhvMinEr": ("0", "15-minute efficiency ratio over 16 candles at least this (0 = off; report section 34: 0.45)"),
    "InpUhvStopMode": ("1", "stop: 1 LAWS.md (beyond the retracement's lowest / highest point) · 2 beyond the BREAKOUT candle's low / high · 0 the game's fixed pips below; modes 1-2: target = R:R or UhvFixTp, breakeven UhvBeR"),
    "InpUhvSlBeyond": ("5", "stop modes 1-2: this many pips beyond the retracement's extreme (mode 1, his 5-7) or the breakout candle's low / high (mode 2)"),
    "InpUhvRR": ("2", "LAWS.md take profit: this many R (his 1:2)"),
    "InpUhvFixTp": ("0", "a fixed take profit in pips instead of R:R (0 = use R:R). The Diamond EA's tiny $1.00-of-gold target = about 0.6 pip on EUR/USD"),
    "InpUhvBeR": ("1", "LAWS.md breakeven: the stop to the entry at +this many R (his 1:1; 0 = off)"),
    "InpUhvEntry": ("1", "entry: 1 the INSTANT price breaks the UHV level (Zee 2026-11-05; momentum not judged, quieter = ticks so far) · 0 when the breakout candle CLOSES beyond it (LAWS.md)"),
    "InpUhvTpPips": ("2", "stop mode 0: take profit, pips from the fill (the game: 2)"),
    "InpUhvSlPips": ("2", "stop mode 0: stop loss, pips from the fill (the game: 2)"),
    "InpUhvLatency": ("0.3", "seconds from the breakout candle's close to the fill (the game's order delay)"),
    "InpUhvNoClose": ("0", "no new entries 16:45-17:45 New York, the daily rollover (1 = on). Loss study 2026-11-06: losers 5-10x as common there"),
    "InpUhvMaxTrigSpread": ("0", "skip when the spread at the breakout tick is this many pips or more (0 = off). Loss study: 1.0 pip, an MT5 candidate"),
    "InpUhvPreBreak": ("0", "instant entry: enter this many pips BEFORE the breakout level is touched (expecting the break; 0 = at the break)"),
    "InpUhvLossSecs": ("0", "close a round still IN LOSS after this many seconds, at market; winners keep running (0 = off; used when InpUhvMaxSecs is 0)"),
    "InpUhvMaxSecs": ("0", "close a round still open after this many seconds, at market - a win or a loss, whatever it is worth then (0 = off)"),
    "InpUhvLots": ("1", "EUR/USD lots: 1 = 100,000 EUR = $10 a pip (= 100 game coins: divide by 100 for the game; 0.01 = one coin, but the panels round to whole $)"),
    **uhv_filters.DEFAULTS,                                       # Zee 2026-11-06: the loss filters from his loss comments (all off at 0)
    "InpUhvSaad": ("false", "apply Saad's entry settings (candle shapes, ADX, EMA trend, session ...) to the UHV breakout candle"),
}
_S = {}
# Zee 2026-11-05: "in the scan every setting can u add max settings for camel humps ... also for UHV detection params, shape of UHV, shape of
# breakout candle". Each changes WHICH setups exist, so a non-default value finds every setup again (about a minute) into simdata/det_cache,
# once per combination; later runs read the file.
DET = {"InpDetCamPiv": ("CAM_PIV", "camel hump size: a swing needs this many candles on each side (1 = every swing counts)"),
       "InpDetCamConfirm": ("CAM_CONFIRM", "camel trend flips after this many humps of the new colour in a row"),
       "InpDetCamStrong": ("CAM_STRONG", "strong camel trend (this many humps in a row) lets the breakout be louder than the UHV (0 = never)"),
       "InpDetMaxHumps": ("MAX_HUMPS", "the EA takes setups only within this many humps of the trend (the 'ea' tag)"),
       "InpDetPivot": ("PIVOT", "retracement swing size, candles each side"),
       "InpDetTrendLook": ("TREND_LOOK", "candles back the trend / impulse is read over"),
       "InpDetRetraceBack": ("RETRACE_BACK", "candles back the retracement (and its UHV) is searched"),
       "InpDetUhvBody": ("UHV_BODY_MIN", "UHV shape: body at least this share of its range"),
       "InpDetMomBody": ("MOMENTUM_BODY", "breakout shape: body at least this share of its range (momentum candle; 0 = any)"),
       "InpDetCooldown": ("COOLDOWN_BARS", "candles after a setup before the next (the 'ea' tag)")}
DET_DEFAULT = {k: getattr(uhv_diamond, a) for k, (a, _) in DET.items()}


def det_file(inp):
    vals = {k: (fv(inp, k, DET_DEFAULT[k]) if str((inp or {}).get(k, "")).strip() != "" else DET_DEFAULT[k]) for k in DET}
    if all(abs(float(vals[k]) - float(DET_DEFAULT[k])) < 1e-9 for k in DET):
        return HERE / "simdata" / "uhv_setups.json"
    key = "_".join(f"{float(vals[k]):g}" for k in DET)
    f = HERE / "simdata" / "det_cache" / f"setups_{key}.json"
    if not f.exists():
        build_setups(vals, f)
    return f


def build_setups(vals, out_file):
    """the same scan as server.uhv_setups, with the detection constants set from vals"""
    import time
    D = sim.data("year1")
    old = {a: getattr(uhv_diamond, a) for a, _ in DET.values()}
    try:
        for k, (a, _) in DET.items():
            setattr(uhv_diamond, a, type(old[a])(vals[k]) if isinstance(old[a], int) else float(vals[k]))
        uhv_diamond.NEED = uhv_diamond.TREND_LOOK + uhv_diamond.PIVOT + 2
        rows = [[int(t), float(o), float(h), float(l), float(c), float(v)] for t, o, h, l, c, v in zip(D["t1"], D["o1"], D["h1"], D["l1"], D["c1"], D["v1"])]
        dia = uhv_diamond.Diamond(unit=0.00012)
        out, seen, t0, roughs = [], set(), time.time(), []
        for i in range(400, len(rows)):
            win = rows[i - 400:i + 1]
            dia.update(win, lambda b: b[5] or None, win[-1][0] + 30)
            rg = dia.rough
            if rg and not (dia.cut and dia.cut["t"] == win[-1][0]):
                roughs.append([int(win[-1][0]), int(rg["side"]), round(rg["level"], 5), round(rg["extreme"], 5), int(rg["uhv_t"]), float(rg["uhv_v"] or 0)])
            cut = dia.cut
            if cut and cut["t"] not in seen:
                seen.add(cut["t"])
                out.append({"t": int(cut["t"]), "side": cut["side"], "uhv_t": int(cut["uhv_t"]), "level": round(cut["level"], 5),
                            "extreme": round(cut["extreme"], 5), "laws": cut["laws"], "ea": bool(cut["ea"]), "royal": bool(cut["royal"]),
                            "er": None if cut["er"] is None else round(cut["er"], 3)})
    finally:
        for a, v in old.items():
            setattr(uhv_diamond, a, v)
        uhv_diamond.NEED = uhv_diamond.TREND_LOOK + uhv_diamond.PIVOT + 2
    ttd_features(D, out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_file.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"ds": "year1", "det": vals, "setups": out, "roughs": roughs, "secs": round(time.time() - t0, 1)}, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, out_file)


def ttd_features(D, setups):
    """Per setup, everything the Turtle Trader Desk indicator's entry filters and stops read (Zee 2026-11-05: "add all settings from the
    indicator code to the scanner"): the UHV candle and the breakout candle (o h l c volume), the candle before the breakout, candles between
    them, the colours of the 30 candles before the UHV, ATR at the UHV, the loudest volume of the N candles before the UHV, the swing lows /
    highs of the last 5-30 candles, the impulse's top / bottom (structural target) and the breakout's tick density vs its recent average."""
    t, o, h, l, c, v = (np.asarray(D[k]) for k in ("t1", "o1", "h1", "l1", "c1", "v1"))
    atr = np.asarray(D["atr"])
    rng = np.maximum(h - l, 1e-6)
    dens = v / (rng / 1e-4)                                   # ticks per pip of range (the indicator's participation density)
    for s in setups:
        kb = int(np.searchsorted(t, s["t"] - 60)); ku = int(np.searchsorted(t, s["uhv_t"]))
        if kb >= len(t) or ku >= len(t) or t[kb] != s["t"] - 60 or t[ku] != s["uhv_t"]:
            s["f"] = None
            continue
        pre = slice(max(0, ku - 500), ku)
        f = {"uo": float(o[ku]), "uh": float(h[ku]), "ul": float(l[ku]), "uc": float(c[ku]), "uv": float(v[ku]),
             "bo": float(o[kb]), "bh": float(h[kb]), "bl": float(l[kb]), "bc": float(c[kb]), "bv": float(v[kb]),
             "ph": float(h[kb - 1]), "pl": float(l[kb - 1]), "nb": int(kb - ku), "atr_u": float(atr[ku]), "atr_b": float(atr[kb]),
             "bg": [int(np.sign(c[j] - o[j])) for j in range(max(0, ku - 30), ku)],
             "vmax": {str(n): float(v[max(0, ku - n):ku].max()) if ku > 0 else 0.0 for n in (5, 10, 20, 50, 100, 200, 500)},
             "swl": {str(n): float(l[max(0, kb - n + 1):kb + 1].min()) for n in (5, 8, 11, 15, 20, 30)},
             "swh": {str(n): float(h[max(0, kb - n + 1):kb + 1].max()) for n in (5, 8, 11, 15, 20, 30)},
             "imp": float(h[max(0, ku - 20):ku + 1].max()) if s["side"] > 0 else float(l[max(0, ku - 20):ku + 1].min()),
             "dens": float(dens[kb]), "dsma": {str(n): float(dens[max(0, kb - n):kb].mean()) for n in (5, 10, 20, 50, 100)}}
        s["f"] = f
        _ = pre




def _setups(f=None):
    f = f or HERE / "simdata" / "uhv_setups.json"
    m = (str(f), f.stat().st_mtime)
    if _S.get("m") != m:
        S = json.loads(f.read_text(encoding="utf-8"))["setups"]
        _S.update(m=m, S=S)
    if "T" not in _S:
        _S["T"] = uhv_ticks.load()                               # the whole PrimeXBT tick stream (read once)
    return _S["S"], _S["T"]


def fv(inp, k, d=0.0):
    try:
        v = inp.get(k, d)
        if isinstance(v, str) and v.lower() in ("true", "false"):
            return 1.0 if v.lower() == "true" else 0.0
        return float(v)
    except (TypeError, ValueError):
        return float(d)


def _ema(c, n):
    a = 2.0 / (n + 1); out = np.empty_like(c); out[0] = c[0]
    for i in range(1, len(c)):
        out[i] = out[i - 1] + a * (c[i] - out[i - 1])
    return out


_IND = {}


def _ind(ds, nf, ns, htf, htf_ema, er_look):
    key = (ds, nf, ns, htf, htf_ema, er_look)
    if key in _IND:
        return _IND[key]
    D = sim.data(ds)
    c = np.asarray(D["c1"], dtype=np.float64)
    ef, es = _ema(c, nf), _ema(c, ns)
    t = np.asarray(D["t1"], dtype=np.int64)
    hup = np.zeros(len(c))
    if htf > 0:                                              # the higher timeframe's close and its EMA, known at each M1 bar (completed HTF bars only)
        g = t // (htf * 60)
        last = np.r_[g[1:] != g[:-1], True]
        hc = c[last]; he = _ema(hc, htf_ema)
        idx = np.cumsum(np.r_[0, (g[1:] != g[:-1]).astype(int)]) - 1          # the completed HTF bar before this M1 bar's bucket
        ok = idx >= 1
        ii = np.clip(idx, 1, None)
        hup = np.where(ok, np.sign(hc[ii] - he[ii]) * (np.sign(he[ii] - he[ii - 1]) == np.sign(hc[ii] - he[ii])), 0)
    er = np.zeros(len(c))
    if er_look > 0:
        d = np.abs(np.diff(c, prepend=c[0]))
        cs = np.cumsum(d)
        n = er_look
        net = np.abs(c - np.r_[np.full(n, c[0]), c[:-n]])
        path = cs - np.r_[np.zeros(n), cs[:-n]]
        er = np.where(path > 0, net / np.maximum(path, 1e-12), 0)
    _IND[key] = (ef, es, hup, er)
    if len(_IND) > 12:
        _IND.pop(next(iter(_IND)))
    return _IND[key]


def _shape_ok(o, h, l, c, side, inp, atr):
    """Saad's setup-candle rules, on the UHV breakout candle: it must be one of the accepted shapes (pin / marubozu / hammer / star)."""
    rng = h - l
    if rng <= 0:
        return False
    mra = fv(inp, "InpMinRangeAtr")
    if mra > 0 and atr > 0 and rng < mra * atr:
        return False
    body = abs(c - o); up = h - max(o, c); dn = min(o, c) - l
    if not any(fv(inp, k, 1) > 0.5 for k in ("InpUsePin", "InpMarubozu", "InpHammer" if side > 0 else "InpStar")):
        return True                                            # no candle shape ticked: the shape rules are off (only the range x ATR above)
    ok = False
    if fv(inp, "InpUsePin", 1) > 0.5:
        lw, sw = (dn, up) if side > 0 else (up, dn)
        pin = lw >= fv(inp, "InpWickMin", 0.45) * rng and body <= fv(inp, "InpBodyMax", 0.6) * rng and sw <= fv(inp, "InpNoseMax", 0.35) * rng
        if pin and fv(inp, "InpPinColor") > 0.5:
            pin = (c > o) if side > 0 else (c < o)
        ok = ok or pin
    if fv(inp, "InpMarubozu", 1) > 0.5:
        ok = ok or (body >= fv(inp, "InpMaruBody", 0.53) * rng and ((c > o) if side > 0 else (c < o)))
    hr, hn = fv(inp, "InpHamRatio", 2.5), fv(inp, "InpHamNose", 0.5)
    if side > 0 and fv(inp, "InpHammer", 1) > 0.5:
        ok = ok or (dn >= hr * max(body, 1e-12) and up <= hn * rng)
    if side < 0 and fv(inp, "InpStar", 1) > 0.5:
        ok = ok or (up >= hr * max(body, 1e-12) and dn <= hn * rng)
    return ok


@njit(cache=True)
def _play(T, B, A, a, b, t0, side, lat, sl, tp, be_r, be_off, lock_r, tr, tr_k, tr_act, p1_r, p1_f, p1_be, p2_r, p2_f, lcap, lp_r, lp_f,
          dc_s, dc_r, max_s, stale_s, stale_r, atr_p, saad_be, lock_at, lock_px):
    """one round on its ticks (all distances in pips; R = sl). Returns (pnl pips weighted, t_in, fill, t_out, exit, why, best pips)."""
    i = a
    while i < b and T[i] - t0 < lat:
        i += 1
    if i >= b:
        return 0.0, -1.0, 0.0, 0.0, 0.0, -1, 0.0, 0.0, 0
    fill = A[i] if side > 0 else B[i]
    t_in = T[i] - t0
    R = sl
    stop = -sl if lcap <= 0 else -min(sl, lcap)
    left, pnl, best, worst, parts = 1.0, 0.0, -1e9, 1e9, 0
    p1_done, p2_done, lp_done, why = False, False, False, 0
    for j in range(i, b):
        px = B[j] if side > 0 else A[j]
        m = (px - fill) * side / 0.0001
        el = T[j] - t0 - t_in
        if m > best:
            best = m
        if m < worst:
            worst = m
        # stop and target first (the price they need to touch), then the rules that move the stop
        if m <= stop:                                         # filled at the real tick that reached the stop (a jump past it costs more)
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, why if why > 0 else 1, best, worst, parts
        if tp > 0 and m >= tp:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 5, best, worst, parts
        if lp_r > 0 and not lp_done and m <= -lp_r * R:
            pnl += lp_f * left * m; left -= lp_f * left; lp_done = True; parts += 1
            if left <= 1e-9:
                return pnl, t_in, fill, T[j] - t0, px, 17, best, worst, parts
        if p1_r > 0 and not p1_done and m >= p1_r * R:
            pnl += p1_f * left * m; left -= p1_f * left; p1_done = True; parts += 1
            if p1_be and stop < 0:
                stop = 0.0; why = 7
            if left <= 1e-9:
                return pnl, t_in, fill, T[j] - t0, px, 11, best, worst, parts
        if p2_r > 0 and p1_done and not p2_done and m >= p2_r * R:
            pnl += p2_f * left * m; left -= p2_f * left; p2_done = True; parts += 1
            if left <= 1e-9:
                return pnl, t_in, fill, T[j] - t0, px, 11, best, worst, parts
        if saad_be > 0 and best >= saad_be and stop < 0:
            stop = 0.0; why = 7
        if lock_at > 0 and best >= lock_at and stop < lock_px:
            stop = lock_px; why = 7
        if be_r > 0 and best >= be_r * R and stop < be_off * R:
            stop = be_off * R; why = 7
        if lock_r > 0 and best >= 2 * lock_r * R:
            lv = (math.floor(best / (lock_r * R)) - 1) * lock_r * R
            if lv > stop:
                stop = lv; why = 7
        if tr > 0 and best >= tr_act * R:
            if tr == 1:
                ts = best - tr_k
            elif tr == 2:
                ts = best - tr_k * atr_p
            else:
                ts = best * (tr_k / 100.0) if best > 0 else -1e9
            if ts > stop:
                stop = ts; why = 6
        if dc_s > 0 and el >= dc_s and stop < dc_r * R:
            stop = dc_r * R; why = 16
        if (max_s > 0 and el >= max_s) or (max_s < 0 and el >= -max_s and m < 0):   # max_s < 0: losers only (InpUhvLossSecs)
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 8, best, worst, parts
        if stale_s > 0 and el >= stale_s and best < stale_r * R:
            pnl += left * m
            return pnl, t_in, fill, T[j] - t0, px, 13, best, worst, parts
    px = B[b - 1] if side > 0 else A[b - 1]
    m = (px - fill) * side / 0.0001
    pnl += left * m
    return pnl, t_in, fill, T[b - 1] - t0, px, 8, best, worst, parts


def max_secs(lab_s, inp_s):
    """the tighter of the Exit Lab's time exit and InpUhvMaxSecs (0 = off for either)"""
    v = [x for x in (lab_s, inp_s) if x and x > 0]
    return min(v) if v else 0.0


_INST = {}


def _instant_setups(TK, shift=0.0, f=None):
    """Zee 2026-11-05: "change it to exactly at time it breaks". Every minute with a UHV level waiting (the scan's roughs): the first tick whose
    bid crosses it (above the UHV high for a buy, below its low for a sell) is the breakout - if the ticks so far in that minute are fewer than the
    UHV's (quieter). One breakout per UHV. The minute's low / high up to the crossing = 'the breakout candle' for stop mode 2."""
    f = f or HERE / "simdata" / "uhv_setups.json"
    m = (str(f), f.stat().st_mtime)
    if _INST.get("m") == m and _INST.get("shift") == shift:
        return _INST["S"]
    R = json.loads(f.read_text(encoding="utf-8")).get("roughs") or []
    T, B, AS = TK["t"], TK["bid"], TK["ask"]
    used, S = set(), []
    for t, side, level, extreme, uhv_t, uhv_v in R:
        if uhv_t in used:
            continue
        a, b = int(np.searchsorted(T, t)), int(np.searchsorted(T, t + 60))
        if b <= a:
            continue
        seg = B[a:b]
        lv = level - side * shift * PIP                           # the indicator's pre (+) / post (-) breakout offset
        hit = np.nonzero(seg > lv)[0] if side > 0 else np.nonzero(seg < lv)[0]
        if not len(hit):
            continue
        j = int(hit[0])
        used.add(uhv_t)
        if uhv_v and j + 1 >= uhv_v:                           # the minute's ticks up to the break already as loud as the UHV: not his breakout
            continue
        S.append({"t": float(T[a + j]), "side": int(side), "level": level, "extreme": extreme, "uhv_t": uhv_t, "laws": 0, "ea": False,
                  "royal": False, "er": None, "bar": int(t), "lo": float(seg[:j + 1].min()), "hi": float(seg[:j + 1].max()), "bv": j + 1, "bc": float(seg[j]), "sp": float(AS[a + j] - seg[j]), "uv": float(uhv_v or 0)})
    _INST.update(m=m, S=S, shift=shift)
    return S


def simulate(inputs, ds="year1", chart=False, lab=None, lego=None, skip_idle_ticks=True, prune=(), **extra):
    """The UHV strategy in the Saad tester's shape: (trade rows, setups [(bar k, side, kind)], skip counts)."""
    dfile = det_file(inputs or {})
    S, TK = _setups(dfile)
    instant = int(fv(inputs or {}, "InpUhvEntry", 1)) == 1
    ttd = uhv_ttd.fv(inputs or {}, "InpTtdOn") > 0.5
    if instant:
        S = _instant_setups(TK, (uhv_ttd.fv(inputs or {}, "InpTtd_uPBD") - uhv_ttd.fv(inputs or {}, "InpTtd_uPBsD")) if ttd else fv(inputs or {}, "InpUhvPreBreak"), dfile)
    D = sim.data("year1")
    t1 = np.asarray(D["t1"], dtype=np.int64)
    o1, h1, l1, c1 = (np.asarray(D[k]) for k in ("o1", "h1", "l1", "c1"))
    atr, adx, sp1 = np.asarray(D["atr"]), np.asarray(D["adx"]), np.asarray(D["sp1"])
    inp = dict(inputs or {})
    if not lab:                                                    # the Exit Lab exit as the EA's own settings (InpX*), as the scan and MT5 send it
        import sim_full
        lab = {f: fv(inp, k) for f, k in sim_full.XFIELDS.items() if k in inp and fv(inp, k) != 0}
    lab = lab or {}
    L = lambda k, d=0.0: float(lab.get(k, d))
    mode, minl, miner = int(fv(inp, "InpUhvMode")), int(fv(inp, "InpUhvMinLaws")), fv(inp, "InpUhvMinEr")
    sl, tp0, lat = fv(inp, "InpUhvSlPips", 2), fv(inp, "InpUhvTpPips", 2), fv(inp, "InpUhvLatency", 0.3)
    stop_mode = int(fv(inp, "InpUhvStopMode", 1))
    laws_stop = stop_mode in (1, 2)
    beyond, rr, be_rr = fv(inp, "InpUhvSlBeyond", 5), fv(inp, "InpUhvRR", 2), fv(inp, "InpUhvBeR", 1)
    fix_tp = fv(inp, "InpUhvFixTp", 0)
    lots = fv(inp, "InpUhvLots", 0.01)
    usd_pip = lots * 100000 * PIP                                    # EUR/USD: $ per pip at these lots
    saad = fv(inp, "InpUhvSaad") > 0.5
    nf, ns = int(fv(inp, "InpEmaFast", 16)), int(fv(inp, "InpEmaSlow", 32))
    ef, es, hup, er = _ind("year1", nf, ns, int(fv(inp, "InpHtfMin")) if saad else 0, int(fv(inp, "InpHtfEma", 90)), int(fv(inp, "InpChopErLook", 16)) if saad else 0)
    tgt, tgt_k = int(L("tgt")), L("tgt_k", 2)
    tr_kind = int(L("tr")); tr_kind = tr_kind if tr_kind in (1, 2, 3) else 0
    cnt = {"setups": 0, "no_break": 0, "risk": 0, "adx": 0, "atr_band": 0, "band_skip": 0, "gap": 0, "spread_reject": 0, "open_at_end": 0, "open_since": 0,
           "loss_filter": 0}
    lf_on = uhv_filters.active(fv, inp)
    rows, su, busy, cool_until, day, dnet = [], [], -1.0, -1.0, None, 0.0
    ttd_cd_until = -1.0
    TT, BB, AA = TK["t"], TK["bid"], TK["ask"]
    for i, s in enumerate(S):
        bar_t = s["bar"] - 60 if instant else s["t"] - 60       # instant: the last CLOSED candle before the break (filters read closed candles)
        k = int(np.searchsorted(t1, bar_t))
        if k >= len(t1) or t1[k] != bar_t:
            continue
        side = int(s["side"])
        cnt["setups"] += 1
        su.append((k, side, 1 if s["ea"] else 0))
        if fv(inp, "InpUhvNoClose") > 0.5:                         # the daily rollover 16:45-17:45 New York (loss study 2026-11-06, 172 losses:
            _ny = _dt.datetime.fromtimestamp(s["t"], _NY)             # x5.3 / x10 the normal loss rate on both halves; NY time follows US DST)
            if 16 * 60 + 45 <= _ny.hour * 60 + _ny.minute < 17 * 60 + 45:
                cnt["band_skip"] += 1; continue
        if fv(inp, "InpUhvMaxTrigSpread") > 0 and instant and s.get("sp", 0.0) >= fv(inp, "InpUhvMaxTrigSpread") * PIP - 1e-12:
            cnt["spread_reject"] += 1; continue                     # the spread at the breakout tick (the moment the entry is decided)
        rm = int(fv(inp, "InpUhvRiskMgr"))
        if rm > 0:                                                 # the Risk Manager (Zee 2026-11-06): secure zone vs risky zone
            sec = uhv_filters.secure(fv, inp, D, side, k)
            if rm >= 2 and not sec:
                cnt["loss_filter"] += 1; continue
        else:
            sec = False
        if lf_on and not sec and uhv_filters.skip(fv, inp, D, side, k, s["level"] if instant else float(c1[k]), float(atr[k]), float(s["extreme"]),
                                      level=float(s["level"]), ku=int(np.searchsorted(t1, s["uhv_t"])), ts=float(s["t"]),
                                      uhv_v=float(s.get("uv") or 0) or None, brk_ticks=s.get("bv") if instant else None,
                                      brk_px=float(s["bc"]) if instant and "bc" in s else None):
            cnt["loss_filter"] += 1; continue
        if (mode == 1 and not s["ea"]) or (mode == 2 and not s["royal"]) or s["laws"] < minl or (miner > 0 and (s["er"] is None or s["er"] < miner)):
            cnt["band_skip"] += 1; continue
        if saad:
            hr, dow = (s["t"] // 3600) % 24, ((s["t"] // 86400) + 4) % 7       # server time = UTC; 1970-01-01 was a Thursday
            f_, t_ = int(fv(inp, "InpSessFrom")), int(fv(inp, "InpSessTo", 24))
            reason = None
            if (side > 0 and fv(inp, "InpBuys", 1) < 0.5) or (side < 0 and fv(inp, "InpSells", 1) < 0.5):
                reason = "band_skip"
            elif not (f_ <= hr < t_ if f_ < t_ else (hr >= f_ or hr < t_)) and not (f_ == 0 and t_ in (0, 24)):
                reason = "band_skip"
            elif int(fv(inp, "InpSkipDow", -1)) == dow:
                reason = "band_skip"
            elif fv(inp, "InpAdxMin") > 0 and adx[k] < fv(inp, "InpAdxMin"):
                reason = "adx"
            elif (fv(inp, "InpAtrMinUsd") > 0 and atr[k] < fv(inp, "InpAtrMinUsd")) or (fv(inp, "InpAtrMaxUsd") > 0 and atr[k] > fv(inp, "InpAtrMaxUsd")):
                reason = "atr_band"
            elif not _shape_ok(o1[k], h1[k], l1[k], c1[k], side, inp, atr[k]):
                reason = "no_break"
            elif fv(inp, "InpTrendAlign") > 0.5 and (ef[k] - es[k]) * side <= 0:
                reason = "band_skip"
            elif fv(inp, "InpPriceSide") > 0.5 and (c1[k] - es[k]) * side <= 0:
                reason = "band_skip"
            elif fv(inp, "InpSlopePips") > 0 and k >= int(fv(inp, "InpSlopeLook", 5)) and (es[k] - es[k - int(fv(inp, "InpSlopeLook", 5))]) * side < fv(inp, "InpSlopePips") * PIP:
                reason = "band_skip"
            elif fv(inp, "InpEmaGapPips") > 0 and abs(ef[k] - es[k]) < fv(inp, "InpEmaGapPips") * PIP:
                reason = "band_skip"
            elif fv(inp, "InpHtfMin") > 0 and hup[k] != side:
                reason = "band_skip"
            elif fv(inp, "InpChopEr") > 0 and er[k] < fv(inp, "InpChopEr"):
                reason = "band_skip"
            elif fv(inp, "InpMaxSpreadPts") > 0 and sp1[k] / 0.00001 > fv(inp, "InpMaxSpreadPts"):
                reason = "spread_reject"
            if reason:
                cnt[reason] += 1; continue
        if s["t"] + lat < busy or s["t"] < cool_until:
            continue
        F = None
        if ttd:                                                    # Zee's Turtle Trader Desk indicator: its entry filters
            ku = int(np.searchsorted(t1, s["uhv_t"]))
            kb = k + 1 if instant else k
            if ku >= len(t1) or t1[ku] != s["uhv_t"] or kb >= len(t1) or kb <= ku:
                continue
            part = (float(o1[kb]), s["hi"], s["lo"], s["bc"], float(s["bv"])) if instant else None
            F = uhv_ttd.features(D, side, kb, ku, part)
            why_skip = uhv_ttd.entry_ok(F, side, inp, float(adx[k]), int((s["t"] // 3600) % 24))
            if why_skip is None and uhv_ttd.fv(inp, "InpTtd_uCd") > 0 and s["t"] < ttd_cd_until:
                why_skip = "band_skip"
            if why_skip:
                cnt[why_skip] += 1; continue
            ttd_cd_until = s["t"] + uhv_ttd.fv(inp, "InpTtd_uCd") * 60
        # Range boxes (Saad v1.25-1.27): where the entry sits in the last N closed candles' range (BUY: low 0% .. high 100%; SELL: high 0% ..
        # low 100%), 21 boxes of 5% (the last = beyond 100%). An unticked box: InpBandOff 1 = STAND ASIDE (a ghost that still blocks), 0 = skip.
        nb = int(fv(inp, "InpRangeLook" if side > 0 else "InpRangeLookS", 7))
        hi_, lo_ = float(h1[max(0, k - nb + 1):k + 1].max()), float(l1[max(0, k - nb + 1):k + 1].min())
        px_e = s["level"] if instant else c1[k]                  # the entry price: the break level (instant) / the breakout candle's close
        pct = ((px_e - lo_) if side > 0 else (hi_ - px_e)) / (hi_ - lo_) if hi_ > lo_ else 0.5
        box = min(20, max(0, int(pct * 20))) if pct <= 1.0 else 20
        bands = str(inp.get("InpBandsB" if side > 0 else "InpBandsS", "1" * 21)).ljust(21, "1")
        aside = bands[box] == "0"
        if aside and int(fv(inp, "InpBandOff", 1)) == 0:
            cnt["band_skip"] += 1; continue
        dkey = s["t"] // 86400
        if dkey != day:
            day, dnet = dkey, 0.0
        if saad and ((fv(inp, "InpDayLossUsd") > 0 and dnet <= -fv(inp, "InpDayLossUsd")) or (fv(inp, "InpDayTargetUsd") > 0 and dnet >= fv(inp, "InpDayTargetUsd"))):
            continue
        t0 = float(s["t"])
        a, b = int(np.searchsorted(TT, t0)), int(np.searchsorted(TT, t0 + MAX_HOLD_S))   # this round's ticks: from the breakout close, up to MAX_HOLD_S
        if laws_stop:                                              # LAWS.md: the stop beyond the retracement's extreme -> R; target R:R; breakeven at 1:1
            j0 = a
            while j0 < b and TT[j0] - t0 < lat:
                j0 += 1
            if j0 >= b:
                continue
            f0 = AA[j0] if side > 0 else BB[j0]
            if stop_mode == 1:
                anchor = s["extreme"]
            elif instant:                                          # mode 2, instant: the breakout minute's low (buy) / high (sell) up to the break
                anchor = s["lo"] if side > 0 else s["hi"]
            else:                                                  # mode 2: the breakout candle's low (buy) / high (sell)
                anchor = l1[k] if side > 0 else h1[k]
            sl_t = max((f0 - anchor) * side / PIP, 0.0) + beyond
            tp_t, be_t, be_off_t = (fix_tp if fix_tp > 0 else rr * sl_t), be_rr, 0.0
        else:
            sl_t, tp_t, be_t, be_off_t = sl, tp0, L("be_r"), L("be_off")
        sl_t = max(sl_t, 0.1)                                      # 2026-11-06: a 0-pip stop (stop beyond 0 + a fill on its anchor) crashed the scan
        tp = tp_t if tgt == 0 else 0.0 if tgt == 1 else tgt_k * sl_t if tgt == 2 else tgt_k * atr[k] / PIP if tgt == 3 else tgt_k
        if laws_stop and L("be_r") > 0:
            be_t, be_off_t = L("be_r"), L("be_off")
        lock_at, lock_px = fv(inp, "InpLockAtUsd") if saad else 0.0, fv(inp, "InpLockUsd") if saad else 0.0
        if ttd:
            j0 = int(np.searchsorted(TT, t0 + lat)) if a < b else a
            if j0 >= b:
                continue
            f0 = float(AA[j0] if side > 0 else BB[j0])
            sl_t, tp, be_t, be_s, inv = uhv_ttd.geometry(F, side, f0, s["extreme"], inp, D)
            pnl, t_in, fill, t_out, ex, why, best, worst, parts = uhv_ttd.play(
                TT, BB, AA, a, b, t0, side, lat, sl_t, tp, be_t, be_s, inv, uhv_ttd.fv(inp, "InpTtd_uMAEPips"),
                uhv_ttd.fv(inp, "InpTtd_uMAEDol") / max(usd_pip, 1e-9), uhv_ttd.fv(inp, "InpTtd_uKillSec"), uhv_ttd.fv(inp, "InpTtd_uKillLossSec"),
                uhv_ttd.fv(inp, "InpTtd_ptpPips") if uhv_ttd.fv(inp, "InpTtd_ptpOn") > 0.5 else 0.0, uhv_ttd.fv(inp, "InpTtd_ptpPct") / 100.0,
                uhv_ttd.fv(inp, "InpTtd_pcTDist"), uhv_ttd.fv(inp, "InpTtd_pcTTrig"), uhv_ttd.fv(inp, "InpTtd_pcTStep"), uhv_ttd.fv(inp, "InpTtd_pSlip"))
        else:
          pnl, t_in, fill, t_out, ex, why, best, worst, parts = _play(TT, BB, AA, a, b, t0, side, lat, sl_t, tp, be_t, be_off_t, L("lock_r"), tr_kind, L("tr_k", 2),
                                                      L("tr_act"), L("p1_r"), L("p1_frac", 0.5), L("p1_be") > 0.5, L("p2_r"), L("p2_frac", 0.25),
                                                      L("lcap"), L("lp_r"), L("lp_frac", 0.5), L("dc_bars") * 60.0, L("dc_r", -0.5),
                                                      (max_secs(L("max_bars") * 60.0, fv(inp, "InpUhvMaxSecs")) or -fv(inp, "InpUhvLossSecs")), L("stale_bars") * 60.0, L("stale_r", 0.5), atr[k] / PIP,
                                                      fv(inp, "InpBeUsd") if saad else 0.0, lock_at, lock_px)
        if why < 0:
            continue
        busy = t0 + t_out
        usd = pnl * usd_pip
        if aside:                                                  # stood aside: a ghost (shown grey, "would have made"); it blocks, its result is not money
            cnt["band_skip"] += 1
        else:
            dnet += usd
            if saad and usd < 0 and fv(inp, "InpCoolBars") > 0:
                cool_until = busy + fv(inp, "InpCoolBars") * 60
        rows.append([side, t0 + t_in, fill, fill - side * sl_t * PIP, t0 + t_out, ex, round(usd, 4), 0, box + (0 if side > 0 else 21), 0, 1 if aside else 0, 0, 0, why, pnl,
                     best / sl_t, min(worst, 0.0) / sl_t, sl_t * usd_pip, 0, parts])      # 15 best move (R) · 16 deepest dip (R) · 17 risk $ · 19 partial closes
    tr = np.array(rows, dtype=np.float64) if rows else np.zeros((0, 20))
    return tr, su, cnt
