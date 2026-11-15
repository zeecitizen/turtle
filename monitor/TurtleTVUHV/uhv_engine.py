"""uhv_engine.py - the Turtle TV Tester's engine for Zee's UHV Diamond (TurtleTVUHV). Replaces sim.simulate() in this copy, so the Overview,
the Exit Lab (Test every exit / Find the best exit / Claude's Exit Research Lab) and the other tools all run the UHV strategy.

Zee 2026-11-05: "the individual saad settings we found can be reused mostly because i want to test if saad's settings work / effect our uhv
strategy -> its important that we have those original saad settings too for us to try on the uhv breakout candle".

ENTRIES  the UHV setups (uhv_setups.json: camel-hump trend -> retracement -> loudest counter-coloured candle -> first quieter candle closing
         beyond it), chosen by InpUhvMode (every setup / the EA v1.27's own picks / royal), InpUhvMinLaws, InpUhvMinEr; and - with InpUhvSaad
         on - Saad's own entry settings judged on the UHV BREAKOUT candle (candle shapes + range x ATR, ADX / ATR gates, EMA trend filters,
         higher timeframe, chop ER, session hours, weekday, spread, buys / sells, cool-down after a loss, day loss / target).
FILL     InpUhvExec 1 (default, 2026-11-14): as MT5's Strategy Tester with random delay - the order goes out on the signal tick and fills 0-18
         whole seconds later at the price of that moment; the target is held at the broker (_play_mt5; checked by mt5_parity.py).
         InpUhvExec 0: the first PrimeXBT tick InpUhvLatency s after the signal: a buy at the ask, a sell at the bid.
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
    "InpUhvLatency": ("0.3", "seconds from the breakout candle's close to the fill (the game's order delay; only with InpUhvExec 0)"),
    "InpUhvRetEnd": ("0", "instant entry: wait for the retracement to END before a break counts - 1 = a trend-coloured candle has closed since the UHV candle, "
                          "2 = the last closed candle is trend-coloured, 3 = the retracement's extreme was followed by a closed candle that held it. Until then the UHV "
                          "level stays waiting, and a louder counter-coloured candle takes its place (0 = off: the first tick near the level is the break)"),
    "InpUhvCamExit": ("0", "exit: 1 = close at market when the camel hump line turns AGAINST the trade (a buy: a red hump is confirmed; checked when each candle "
                           "opens, from the second candle after the entry) - 2 = when the hump line is no longer WITH the trade (against, or no colour) - 0 = off"),
    "InpUhvExec": ("1", "how a trade is executed: 1 = as MT5's Strategy Tester with RANDOM DELAY and the target held at the broker (the order fills 0-18 whole seconds "
                        "after the signal at the price of that moment; the stop is the order's own; the target is a touch in whole points from MT5's fill, inside a trade "
                        "session, and pays exactly the target) - 0 = the old tester (fill at the signal tick + InpUhvLatency)"),
    "InpUhvDelaySeed": ("1", "InpUhvExec 1: which random-delay run to show (every trade's delay is fixed by its entry time and this number, so a setting always gives the same "
                             "run; another number = another MT5 run). The Overview also shows the average over every delay"),
    "InpUhvNoClose": ("0", "no new entries 16:45-17:45 New York, the daily rollover (1 = on). Loss study 2026-11-06: losers 5-10x as common there"),
    "InpUhvMaxTrigSpread": ("0", "skip when the spread at the breakout tick is this many pips or more (0 = off). Loss study: 1.0 pip, an MT5 candidate"),
    "InpUhvPreBreak": ("0", "instant entry: enter this many pips BEFORE the breakout level is touched (expecting the break; 0 = at the break)"),
    "InpUhvPreBreakFrac": ("0", "instant entry: the pre-break is at most this share of the UHV candle's range (0.5 = price must be back past half the UHV candle; 0 = off)"),
    "InpUhvLossSecs": ("0", "close a round still IN LOSS after this many seconds, at market; winners keep running (0 = off; used when InpUhvMaxSecs is 0)"),
    "InpUhvMaxSecs": ("0", "close a round still open after this many seconds, at market - a win or a loss, whatever it is worth then (0 = off)"),
    "InpUhvLots": ("1", "EUR/USD lots: 1 = 100,000 EUR = $10 a pip (= 100 game coins: divide by 100 for the game; 0.01 = one coin, but the panels round to whole $)"),
    **uhv_filters.DEFAULTS,                                       # Zee 2026-11-06: the loss filters from his loss comments (all off at 0)
    "InpUhvSaad": ("false", "apply Saad's entry settings (candle shapes, ADX, EMA trend, session ...) to the UHV breakout candle"),
    # Zee 2026-11-07: "instead of packaging them as one setting, can u make separate setting suggestions in the scanner for each" - each switch
    # turns on ONE of Saad's filters (with Saad's own values in his settings); InpUhvSaad true still turns them all on
    "InpUhvSaadShape": ("false", "Saad filter alone: the breakout candle's shape (marubozu body etc., InpMarubozu ...)"),
    "InpUhvSaadTrend": ("false", "Saad filter alone: EMA trend (InpTrendAlign, InpPriceSide, InpSlopePips, InpEmaGapPips, InpHtfMin)"),
    "InpUhvSaadAdx": ("false", "Saad filter alone: ADX at least InpAdxMin"),
    "InpUhvSaadAtr": ("false", "Saad filter alone: ATR between InpAtrMinUsd and InpAtrMaxUsd"),
    "InpUhvSaadSession": ("false", "Saad filter alone: session hours InpSessFrom..InpSessTo and InpSkipDow"),
    "InpUhvSaadSides": ("false", "Saad filter alone: InpBuys / InpSells"),
    "InpUhvSaadChop": ("false", "Saad filter alone: chop - efficiency ratio at least InpChopEr"),
    "InpUhvSaadSpread": ("false", "Saad filter alone: spread at most InpMaxSpreadPts"),
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
       "InpDetCooldown": ("COOLDOWN_BARS", "candles after a setup before the next (the 'ea' tag)"),
       "InpDetCamBoth": ("CAM_BOTH", "camel trend needs BOTH a higher high and a higher low for green (both lower for red); mixed = no trend, no setup (1 = on)"),
       "InpDetRetStart": ("RET_START", "retracement starts at the first counter-coloured candle after the extreme (the body break only validates it), so the UHV can be that first candle (1 = on)"),
       "InpDetDojiUhv": ("DOJI_UHV", "a doji (close = open) inside the retracement can be the UHV, as the chart shows it; 0 = only counter-coloured candles (1 = on)")}
DET_DEFAULT = {k: getattr(uhv_diamond, a) for k, (a, _) in DET.items()}


def det_file(inp):
    vals = {k: (fv(inp, k, DET_DEFAULT[k]) if str((inp or {}).get(k, "")).strip() != "" else DET_DEFAULT[k]) for k in DET}
    if all(abs(float(vals[k]) - float(DET_DEFAULT[k])) < 1e-9 for k in DET):
        return HERE / "simdata" / "uhv_setups.json"
    key = "_".join(f"{float(vals[k]):g}" for k in DET if k not in ("InpDetCamBoth", "InpDetRetStart", "InpDetDojiUhv")) + ("_both" if float(vals["InpDetCamBoth"]) > 0.5 else "") + ("_rs" if float(vals["InpDetRetStart"]) > 0.5 else "") + ("_dj" if float(vals["InpDetDojiUhv"]) > 0.5 else "")   # older cache names stay valid
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


@njit(cache=True)
def _in_session(t):
    """EURUSDp's trade sessions in PrimeXBT's MT5 (SymbolInfoSessionTrade, server time = the tick time): Sunday from 22:06, Monday-Thursday
    00:00-21:59 and 22:06-24:00, Friday 00:00-21:59. A quote outside them cannot fill a target."""
    s = int(t) % 86400
    d = (int(t) // 86400 + 4) % 7                                 # 0 = Sunday (1970-01-01 was a Thursday)
    if d == 6:
        return False
    if d == 0:
        return s >= 79560
    if d == 5:
        return s < 79140
    return s < 79140 or s >= 79560


@njit(cache=True)
def _play_mt5(T, B, A, a, b, t0, side, D, slp, sl, tp, be_r, be_off, lock_r, tr, tr_k, tr_act, p1_r, p1_f, p1_be, p2_r, p2_f, lcap, lp_r, lp_f,
              dc_s, dc_r, max_s, stale_s, stale_r, atr_p, saad_be, lock_at, lock_px):
    """_play as MT5's Strategy Tester executes it with a delay of D whole seconds and the target held at the broker (measured on 20 x 25,534 and
    6 x 29,560 replayed entries, 2026-11-14: every outcome reproduced from MT5's own fill; expected stops 509.7 vs MT5's 508.6 and 553.9 vs 552.5):
    the order is sent on tick a and fills D s later at the price of that moment (the last tick at or before it); slp = the order's stop price in
    points (absolute); the target is a touch of tp in WHOLE points from that fill, inside a trade session, and pays exactly tp. Prices in points
    (the ticks are float32). Returns _play's tuple; t_in = the send tick (the moment of the decision), so a trade keeps its entry time."""
    if a >= b:
        return 0.0, -1.0, 0.0, 0.0, 0.0, -1, 0.0, 0.0, 0
    ts = T[a]
    i = a
    while i + 1 < b and T[i + 1] <= ts + D + 1e-6:
        i += 1
    fp = np.floor((A[i] if side > 0 else B[i]) * 1e5 + 0.5)
    tpp = np.floor(tp * 10.0 + 0.5)
    if tp > 0 and tpp < 1:
        tpp = 1.0
    t_in = ts - t0
    R = sl
    dist = (fp - slp) * side / 10.0                               # pips from MT5's fill to the order's stop
    stop = -dist if lcap <= 0 else -min(dist, lcap)
    left, pnl, best, worst, parts = 1.0, 0.0, -1e9, 1e9, 0
    p1_done, p2_done, lp_done, why = False, False, False, 0
    for j in range(i + 1, b):
        pp = np.floor((B[j] if side > 0 else A[j]) * 1e5 + 0.5)
        px = pp / 1e5
        m = (pp - fp) * side / 10.0
        el = T[j] - ts - D
        if m > best:
            best = m
        if m < worst:
            worst = m
        if m <= stop:
            pnl += left * m
            return pnl, t_in, fp / 1e5, T[j] - t0, px, why if why > 0 else 1, best, worst, parts
        if tpp > 0 and (pp - fp) * side >= tpp and _in_session(T[j]):
            pnl += left * tpp / 10.0
            return pnl, t_in, fp / 1e5, T[j] - t0, (fp + side * tpp) / 1e5, 5, best, worst, parts
        if lp_r > 0 and not lp_done and m <= -lp_r * R:
            pnl += lp_f * left * m; left -= lp_f * left; lp_done = True; parts += 1
            if left <= 1e-9:
                return pnl, t_in, fp / 1e5, T[j] - t0, px, 17, best, worst, parts
        if p1_r > 0 and not p1_done and m >= p1_r * R:
            pnl += p1_f * left * m; left -= p1_f * left; p1_done = True; parts += 1
            if p1_be and stop < 0:
                stop = 0.0; why = 7
            if left <= 1e-9:
                return pnl, t_in, fp / 1e5, T[j] - t0, px, 11, best, worst, parts
        if p2_r > 0 and p1_done and not p2_done and m >= p2_r * R:
            pnl += p2_f * left * m; left -= p2_f * left; p2_done = True; parts += 1
            if left <= 1e-9:
                return pnl, t_in, fp / 1e5, T[j] - t0, px, 11, best, worst, parts
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
                ts_ = best - tr_k
            elif tr == 2:
                ts_ = best - tr_k * atr_p
            else:
                ts_ = best * (tr_k / 100.0) if best > 0 else -1e9
            if ts_ > stop:
                stop = ts_; why = 6
        if dc_s > 0 and el >= dc_s and stop < dc_r * R:
            stop = dc_r * R; why = 16
        if (max_s > 0 and el >= max_s) or (max_s < 0 and el >= -max_s and m < 0):
            pnl += left * m
            return pnl, t_in, fp / 1e5, T[j] - t0, px, 8, best, worst, parts
        if stale_s > 0 and el >= stale_s and best < stale_r * R:
            pnl += left * m
            return pnl, t_in, fp / 1e5, T[j] - t0, px, 13, best, worst, parts
    j = b                                                         # 24 h: the EA closes at market - which waits for the next trade session (a Friday trade: Sunday 22:06)
    while j < len(T) and not _in_session(T[j]):
        j += 1
    if j >= len(T):
        j = b - 1
    pp = np.floor((B[j] if side > 0 else A[j]) * 1e5 + 0.5)
    m = (pp - fp) * side / 10.0
    if tpp > 0 and (pp - fp) * side >= tpp and m > stop and _in_session(T[j]):
        pnl += left * tpp / 10.0
        return pnl, t_in, fp / 1e5, T[j] - t0, (fp + side * tpp) / 1e5, 5, best, worst, parts
    pnl += left * m
    return pnl, t_in, fp / 1e5, T[j] - t0, pp / 1e5, 8, best, worst, parts


LAST_EXP = None
MT5_W = tuple([0.1] * 9 + [0.01] * 10)                            # MT5's random delay: a digit 0-9 = seconds; a 9 adds one more digit (0-18 s; measured on 29,565 fills)
_M64 = (1 << 64) - 1


def _mt5_delay(ms, side, seed=1):
    """the delay (whole seconds) of the trade decided at tick time ms: fixed by the entry and the seed, distributed as MT5's random delay"""
    x = (int(ms) * 0x9E3779B97F4A7C15 + int(seed) * 0xBF58476D1CE4E5B9 + (0x94D049BB133111EB if side > 0 else 0)) & _M64
    x ^= x >> 30; x = (x * 0xBF58476D1CE4E5B9) & _M64; x ^= x >> 27; x = (x * 0x94D049BB133111EB) & _M64; x ^= x >> 31
    k = int((x >> 11) / float(1 << 53) * 100.0)
    return k // 10 if k < 90 else 9 + (k - 90)


def _exec(X, T, B, A, a, b, t0, side, lat, sl, tp, *rest):
    """one round: the old tester (X is None), or MT5's execution - the shown run's delay, and the average over every delay into X's tally"""
    if X is None:
        return _play(T, B, A, a, b, t0, side, lat, sl, tp, *rest)
    slp, D, acc, real = X
    out, pw, ev, w = None, 0.0, 0.0, 0.0
    for d, wd in enumerate(MT5_W):
        r = _play_mt5(T, B, A, a, b, t0, side, float(d), float(slp), sl, tp, *rest)
        if d == D:
            out = r
        if r[5] >= 0:
            w += wd; ev += wd * r[0]
            if r[0] > 0:
                pw += wd
    if out is not None and out[5] >= 0 and w > 0:
        pw, ev = pw / w, ev / w
        acc[4].append((pw, ev) if real else (float("nan"), float("nan")))   # per row, in the rows' order (LAST_EXP)
        if real:
            acc[0] += 1; acc[1] += pw; acc[2] += ev; acc[3] += pw * (1.0 - pw)
    return out


def max_secs(lab_s, inp_s):
    """the tighter of the Exit Lab's time exit and InpUhvMaxSecs (0 = off for either)"""
    v = [x for x in (lab_s, inp_s) if x and x > 0]
    return min(v) if v else 0.0


_INST = {}


def _instant_setups(TK, shift=0.0, f=None, frac=0.0, retend=0):
    """Zee 2026-11-05: "change it to exactly at time it breaks". Every minute with a UHV level waiting (the scan's roughs): the first tick whose
    bid crosses it (above the UHV high for a buy, below its low for a sell) is the breakout - if the ticks so far in that minute are fewer than the
    UHV's (quieter). One breakout per UHV. The minute's low / high up to the crossing = 'the breakout candle' for stop mode 2."""
    f = f or HERE / "simdata" / "uhv_setups.json"
    m = (str(f), f.stat().st_mtime)
    if _INST.get("m") == m and _INST.get("shift") == (shift, frac, retend):
        return _INST["S"]
    R = json.loads(f.read_text(encoding="utf-8")).get("roughs") or []
    T, B, AS = TK["t"], TK["bid"], TK["ask"]
    used, S = set(), []
    if frac > 0:
        D1 = sim.data("year1"); t1_ = np.asarray(D1["t1"], dtype=np.int64); rg1 = np.asarray(D1["h1"]) - np.asarray(D1["l1"])
    if retend > 0:                                                # Zee 2026-11-14: "we should wait for a retracement to end first"
        D2 = sim.data("year1"); t2_ = np.asarray(D2["t1"], dtype=np.int64); h2_, l2_ = np.asarray(D2["h1"]), np.asarray(D2["l1"])
        col2_ = np.sign(np.asarray(D2["c1"]) - np.asarray(D2["o1"])).astype(np.int8)
    for t, side, level, extreme, uhv_t, uhv_v in R:
        if uhv_t in used:
            continue
        if retend > 0:
            k_ = int(np.searchsorted(t2_, t - 60)); u_ = int(np.searchsorted(t2_, uhv_t))
            if k_ >= len(t2_) or t2_[k_] != t - 60 or u_ > k_:
                continue
            if retend == 1:
                ok_ = bool((col2_[u_ + 1:k_ + 1] == side).any())
            elif retend == 2:
                ok_ = col2_[k_] == side and k_ > u_
            else:
                x_ = l2_[u_:k_ + 1] if side > 0 else -h2_[u_:k_ + 1]
                j_ = int(np.argmin(x_))
                ok_ = j_ < len(x_) - 1
            if not ok_:
                continue                                          # the level keeps waiting (not used up)
        a, b = int(np.searchsorted(T, t)), int(np.searchsorted(T, t + 60))
        if b <= a:
            continue
        seg = B[a:b]
        lv = level - side * shift * PIP                           # the indicator's pre (+) / post (-) breakout offset
        if frac > 0:                                              # Zee 2026-11-13: "the price didnt even go until lower than half the previous candle"
            ku = int(np.searchsorted(t1_, uhv_t))
            if ku < len(t1_) and t1_[ku] == uhv_t:
                lv = level - side * min(shift * PIP, frac * float(rg1[ku]))
        segp = np.round(seg.astype(np.float64) * 1e5)             # 2026-11-14: whole points, as the EA (ZeeUHV v1.05) - the ticks are float32, so a bid
        hit = np.nonzero(segp > lv * 1e5 + 1e-6)[0] if side > 0 else np.nonzero(segp < lv * 1e5 - 1e-6)[0]   # exactly on the level read as beyond it at random
        if not len(hit):
            continue
        j = int(hit[0])
        used.add(uhv_t)
        if uhv_v and j + 1 >= uhv_v:                           # the minute's ticks up to the break already as loud as the UHV: not his breakout
            continue
        S.append({"t": float(T[a + j]), "side": int(side), "level": level, "extreme": extreme, "uhv_t": uhv_t, "laws": 0, "ea": False,
                  "royal": False, "er": None, "bar": int(t), "lo": round(float(seg[:j + 1].min()), 5), "hi": round(float(seg[:j + 1].max()), 5), "bv": j + 1, "bc": round(float(seg[j]), 5),
                  "sp": round(round(float(AS[a + j]), 5) - round(float(seg[j]), 5), 5), "uv": float(uhv_v or 0)})
    _INST.update(m=m, S=S, shift=(shift, frac, retend))
    return S


def simulate(inputs, ds="year1", chart=False, lab=None, lego=None, skip_idle_ticks=True, prune=(), **extra):
    """The UHV strategy in the Saad tester's shape: (trade rows, setups [(bar k, side, kind)], skip counts)."""
    dfile = det_file(inputs or {})
    S, TK = _setups(dfile)
    instant = int(fv(inputs or {}, "InpUhvEntry", 1)) == 1
    ttd = uhv_ttd.fv(inputs or {}, "InpTtdOn") > 0.5
    if instant:
        S = _instant_setups(TK, (uhv_ttd.fv(inputs or {}, "InpTtd_uPBD") - uhv_ttd.fv(inputs or {}, "InpTtd_uPBsD")) if ttd else fv(inputs or {}, "InpUhvPreBreak"), dfile, 0.0 if ttd else fv(inputs or {}, "InpUhvPreBreakFrac"), 0 if ttd else int(fv(inputs or {}, "InpUhvRetEnd")))
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
    _sw = {k: saad or fv(inp, "InpUhvSaad" + k) > 0.5 for k in ("Shape", "Trend", "Adx", "Atr", "Session", "Sides", "Chop", "Spread")}
    nf, ns = int(fv(inp, "InpEmaFast", 16)), int(fv(inp, "InpEmaSlow", 32))
    ef, es, hup, er = _ind("year1", nf, ns, int(fv(inp, "InpHtfMin")) if saad else 0, int(fv(inp, "InpHtfEma", 90)), int(fv(inp, "InpChopErLook", 16)) if saad else 0)
    tgt, tgt_k = int(L("tgt")), L("tgt_k", 2)
    tr_kind = int(L("tr")); tr_kind = tr_kind if tr_kind in (1, 2, 3) else 0
    cnt = {"setups": 0, "no_break": 0, "risk": 0, "adx": 0, "atr_band": 0, "band_skip": 0, "gap": 0, "spread_reject": 0, "open_at_end": 0, "open_since": 0,
           "loss_filter": 0, "busy": 0}                             # busy: InpMaxPos rounds already open / the cool-down - hungry.py's ceiling
    lf_on = uhv_filters.active(fv, inp)
    mt5 = int(fv(inp, "InpUhvExec", 1)) == 1 and not ttd           # 2026-11-14: MT5's execution (random delay, target held at the broker); the Turtle Trader Desk
    seed = int(fv(inp, "InpUhvDelaySeed", 1))                      # play keeps its own
    if mt5:
        lat = 0.0                                                  # the order is sent on the signal tick; MT5's delay does the rest
    cam_x, cam_nxt = int(fv(inp, "InpUhvCamExit")), {}
    if cam_x:                                                      # per side: the next candle at whose open the hump line is against the trade
        _eff = uhv_filters._camel_eff(D, max(1, int(fv(inp, "InpDetCamPiv", 1) or 1)), max(1, int(fv(inp, "InpDetCamConfirm", 1) or 1)), int(fv(inp, "InpDetCamBoth")))
        for _sd in (1, -1):
            _bad = (_eff == -_sd) if cam_x == 1 else (_eff != _sd)
            _ix = np.where(_bad, np.arange(len(_eff)), len(_eff))
            cam_nxt[_sd] = np.minimum.accumulate(_ix[::-1])[::-1]
    acc = [0, 0.0, 0.0, 0.0, []]                                     # MT5 average over every delay: trades, expected wins, expected pips, variance of the wins
    rows, su, busy, cool_until, day, dnet = [], [], -1.0, -1.0, None, 0.0
    maxpos = int(fv(inp, "InpMaxPos", 1))                         # Zee 2026-11-09: "let's not skip setups that arrive while a trade is already open" -
    open_ends = []                                                 # the EA's InpMaxPos: 1 = one trade at a time (as before), N = up to N open, 0 = every setup
    ttd_cd_until = -1.0
    trend_wins, trend_lost = {}, set()                             # Zee's harvest: wins / losses per trend sub-zone
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
        if fv(inp, "InpUhvFriCutAllNY") > 0:                       # the Friday cut-off for EVERY trade, the angel's secure zone included (the
            _ny = _dt.datetime.fromtimestamp(s["t"], _NY)             # last angel loss, Fri 23 Oct 10:50 NY, was flattened by the weekly close)
            if _ny.weekday() == 4 and _ny.hour * 60 + _ny.minute >= fv(inp, "InpUhvFriCutAllNY") * 60:
                cnt["band_skip"] += 1; continue
        if fv(inp, "InpUhvMaxTrigSpread") > 0 and instant and s.get("sp", 0.0) >= fv(inp, "InpUhvMaxTrigSpread") * PIP - 1e-12:
            cnt["spread_reject"] += 1; continue                     # the spread at the breakout tick (the moment the entry is decided)
        if fv(inp, "InpUhvMaxTrigSpread") > 0 and not instant:      # 2026-11-14: the candle-close entry too - the spread at its entry tick (the first
            _j = int(np.searchsorted(TT, s["t"] + lat))             # tick at or after the breakout candle's close), as ZeeUHV v1.04 does
            if _j < len(TT) and round(float(AA[_j]), 5) - round(float(BB[_j]), 5) >= fv(inp, "InpUhvMaxTrigSpread") * PIP - 1e-12:
                cnt["spread_reject"] += 1; continue
        rm = int(fv(inp, "InpUhvRiskMgr"))
        if rm in (1, 2):                                           # the Risk Manager (Zee 2026-11-06): secure zone vs risky zone
            sec = uhv_filters.secure(fv, inp, D, side, k)
            if rm == 2 and not sec:
                cnt["loss_filter"] += 1; continue
        elif rm in (3, 4):                                         # Zee's zone model: the angel acts only inside his risky zones
            zr = uhv_filters.risky_zone(fv, inp, D, side, k, float(s["level"]), float(s["t"]))
            sec = zr is None                                       # outside every risky zone = untouched
            if rm == 4 and not sec:
                cnt["loss_filter"] += 1; continue
        else:
            sec = False
        if uhv_filters.into_major(fv, inp, D, side, k, float(s["level"])):   # Zee: selling into support (any risk mode)
            cnt["loss_filter"] += 1; continue
        if uhv_filters.into_wall(fv, inp, D, side, k, float(s["level"])):    # Zee: a tested round-figure wall ahead (the 8 April loss)
            cnt["loss_filter"] += 1; continue
        if uhv_filters.in_quiet_box(fv, inp, D, side, k, float(s["level"])):   # Zee: a breakout inside a quiet box range (any risk mode)
            cnt["loss_filter"] += 1; continue
        hv = int(fv(inp, "InpUhvHarvestWins"))
        tid = uhv_filters.trend_id(D, k, side) if hv > 0 else None
        if hv > 0 and (trend_wins.get(tid, 0) >= hv or (fv(inp, "InpUhvHarvestStopLoss", 1) > 0.5 and tid in trend_lost)):
            cnt["loss_filter"] += 1; continue                      # the trend is harvested (or lost): wait for the next one
        if lf_on and not sec and uhv_filters.skip(fv, inp, D, side, k, s["level"] if instant else float(c1[k]), float(atr[k]), float(s["extreme"]),
                                      level=float(s["level"]), ku=int(np.searchsorted(t1, s["uhv_t"])), ts=float(s["t"]),
                                      uhv_v=float(s.get("uv") or 0) or None, brk_ticks=s.get("bv") if instant else None,
                                      brk_px=float(s["bc"]) if instant and "bc" in s else None):
            cnt["loss_filter"] += 1; continue
        if (mode == 1 and not s["ea"]) or (mode == 2 and not s["royal"]) or s["laws"] < minl or (miner > 0 and (s["er"] is None or s["er"] < miner)):
            cnt["band_skip"] += 1; continue
        if any(_sw.values()):
            hr, dow = (s["t"] // 3600) % 24, ((s["t"] // 86400) + 4) % 7       # server time = UTC; 1970-01-01 was a Thursday
            f_, t_ = int(fv(inp, "InpSessFrom")), int(fv(inp, "InpSessTo", 24))
            reason = None
            if _sw["Sides"] and ((side > 0 and fv(inp, "InpBuys", 1) < 0.5) or (side < 0 and fv(inp, "InpSells", 1) < 0.5)):
                reason = "band_skip"
            elif _sw["Session"] and not (f_ <= hr < t_ if f_ < t_ else (hr >= f_ or hr < t_)) and not (f_ == 0 and t_ in (0, 24)):
                reason = "band_skip"
            elif _sw["Session"] and int(fv(inp, "InpSkipDow", -1)) == dow:
                reason = "band_skip"
            elif _sw["Adx"] and fv(inp, "InpAdxMin") > 0 and adx[k] < fv(inp, "InpAdxMin"):
                reason = "adx"
            elif _sw["Atr"] and ((fv(inp, "InpAtrMinUsd") > 0 and atr[k] < fv(inp, "InpAtrMinUsd")) or (fv(inp, "InpAtrMaxUsd") > 0 and atr[k] > fv(inp, "InpAtrMaxUsd"))):
                reason = "atr_band"
            elif _sw["Shape"] and not _shape_ok(o1[k], h1[k], l1[k], c1[k], side, inp, atr[k]):
                reason = "no_break"
            elif _sw["Trend"] and fv(inp, "InpTrendAlign") > 0.5 and (ef[k] - es[k]) * side <= 0:
                reason = "band_skip"
            elif _sw["Trend"] and fv(inp, "InpPriceSide") > 0.5 and (c1[k] - es[k]) * side <= 0:
                reason = "band_skip"
            elif _sw["Trend"] and fv(inp, "InpSlopePips") > 0 and k >= int(fv(inp, "InpSlopeLook", 5)) and (es[k] - es[k - int(fv(inp, "InpSlopeLook", 5))]) * side < fv(inp, "InpSlopePips") * PIP:
                reason = "band_skip"
            elif _sw["Trend"] and fv(inp, "InpEmaGapPips") > 0 and abs(ef[k] - es[k]) < fv(inp, "InpEmaGapPips") * PIP:
                reason = "band_skip"
            elif _sw["Trend"] and fv(inp, "InpHtfMin") > 0 and hup[k] != side:
                reason = "band_skip"
            elif _sw["Chop"] and fv(inp, "InpChopEr") > 0 and er[k] < fv(inp, "InpChopEr"):
                reason = "band_skip"
            elif _sw["Spread"] and fv(inp, "InpMaxSpreadPts") > 0 and sp1[k] / 0.00001 > fv(inp, "InpMaxSpreadPts"):
                reason = "spread_reject"
            if reason:
                cnt[reason] += 1; continue
        if maxpos != 1:
            open_ends = [e for e in open_ends if e > s["t"] + lat]  # rounds still open when this setup would fill
        if (s["t"] + lat < busy if maxpos == 1 else maxpos > 0 and len(open_ends) >= maxpos) or s["t"] < cool_until:
            cnt["busy"] += 1; continue
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
        cam_t = None
        if cam_x and k + 2 < len(t1):
            _j = int(cam_nxt[side][k + 2])
            if _j < len(t1):
                _bb = int(np.searchsorted(TT, float(t1[_j])))
                if _bb < b:
                    b, cam_t = _bb, float(t1[_j])                # the round ends there at market unless the stop or the target comes first
        if laws_stop:                                              # LAWS.md: the stop beyond the retracement's extreme -> R; target R:R; breakeven at 1:1
            j0 = a
            while j0 < b and TT[j0] - t0 < lat:
                j0 += 1
            if j0 >= b:
                continue
            f0 = round(float(AA[j0] if side > 0 else BB[j0]), 5)   # whole points (float32 ticks)
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
        X = None
        if mt5 and a < b:                                          # the order's stop price, as the EA sets it: from the price at the signal tick
            _f = round(float(AA[a] if side > 0 else BB[a]), 5)
            X = (int(round((_f - side * sl_t * PIP) * 1e5)), _mt5_delay(int(round(float(TT[a]) * 1000)), side, seed), acc, not aside)
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
          pnl, t_in, fill, t_out, ex, why, best, worst, parts = _exec(X, TT, BB, AA, a, b, t0, side, lat, sl_t, tp, be_t, be_off_t, L("lock_r"), tr_kind, L("tr_k", 2),
                                                      L("tr_act"), L("p1_r"), L("p1_frac", 0.5), L("p1_be") > 0.5, L("p2_r"), L("p2_frac", 0.25),
                                                      L("lcap"), L("lp_r"), L("lp_frac", 0.5), L("dc_bars") * 60.0, L("dc_r", -0.5),
                                                      (max_secs(L("max_bars") * 60.0, fv(inp, "InpUhvMaxSecs")) or -fv(inp, "InpUhvLossSecs")), L("stale_bars") * 60.0, L("stale_r", 0.5), atr[k] / PIP,
                                                      fv(inp, "InpBeUsd") if saad else 0.0, lock_at, lock_px)
        if why < 0:
            continue
        if cam_t is not None and why == 8 and t0 + t_out >= cam_t - 61:
            why = 18                                               # the hump line turned against the trade
        busy = t0 + t_out
        if X is not None and why != 1:                             # MT5: every exit but the order's own stop is a market close, and that order is delayed too -
            busy += _mt5_delay(int(round(float(TT[a]) * 1000)), side, seed + 7919)   # the round holds its place (InpMaxPos) until it executes
        open_ends.append(busy)
        usd = pnl * usd_pip
        if aside:                                                  # stood aside: a ghost (shown grey, "would have made"); it blocks, its result is not money
            cnt["band_skip"] += 1
        else:
            dnet += usd
            if tid is not None:                                    # the harvest tally of this trend
                if usd > 0:
                    trend_wins[tid] = trend_wins.get(tid, 0) + 1
                elif usd < 0:
                    trend_lost.add(tid)
            if saad and usd < 0 and fv(inp, "InpCoolBars") > 0:
                cool_until = busy + fv(inp, "InpCoolBars") * 60
        rows.append([side, t0 + t_in, fill, X[0] / 1e5 if X is not None else fill - side * sl_t * PIP, t0 + t_out, ex, round(usd, 4), 0, box + (0 if side > 0 else 21), 0, 1 if aside else 0, 0, 0, why, pnl,
                     best / sl_t, min(worst, 0.0) / sl_t, sl_t * usd_pip, 0, parts])      # 15 best move (R) · 16 deepest dip (R) · 17 risk $ · 19 partial closes
    tr = np.array(rows, dtype=np.float64) if rows else np.zeros((0, 20))
    global LAST_EXP
    LAST_EXP = np.array(acc[4], dtype=np.float64).reshape(-1, 2) if mt5 else None   # diagnostics: per row (P(win), expected pips) of the last MT5-mode run
    if mt5 and acc[0]:                                             # the average MT5 run of this setting (every delay weighted as MT5 draws it)
        cnt.update(mt5_n=acc[0], mt5_exp_wins=round(acc[1], 2), mt5_exp_net=round(acc[2] * usd_pip, 2), mt5_sd_wins=round(acc[3] ** 0.5, 2))
    return tr, su, cnt


def _origin_bar(o, h, l, c, k, side, back, ret_start):
    """uhv_diamond.Diamond.origin on the arrays: the candle where the retracement began, seen when candle k has just closed (-1 = none)"""
    H = lambda q: h[k - q + 1]; Lo = lambda q: l[k - q + 1]; col = lambda q: int(c[k - q + 1] > o[k - q + 1]) - int(c[k - q + 1] < o[k - q + 1])   # noqa: E731
    blo = lambda q: min(o[k - q + 1], c[k - q + 1]); bhi = lambda q: max(o[k - q + 1], c[k - q + 1])   # noqa: E731
    n = min(k + 1, 400)
    want_red = side > 0
    ext, best = -1, 0.0
    for q in range(2, back + 1):
        if q > n:
            break
        x = H(q) if want_red else Lo(q)
        if ext < 0 or (x > best if want_red else x < best):
            best, ext = x, q
    if ext < 2:
        return -1
    g = -1
    for q in range(ext, min(ext + 8, back + 8) + 1):
        if q > n:
            break
        if (col(q) > 0) if want_red else (col(q) < 0):
            g = q
            break
    if g < 2:
        return -1
    lvl = Lo(g) if want_red else H(g)
    for q in range(g - 1, 0, -1):
        if (col(q) < 0) if want_red else (col(q) > 0):
            if (blo(q) < lvl) if want_red else (bhi(q) > lvl):
                if ret_start:
                    for j in range(g - 1, q, -1):
                        if (col(j) < 0) if want_red else (col(j) > 0):
                            return k - j + 1
                return k - q + 1
    return -1


def trade_setups(inputs, tr):
    """for the chart (Zee 2026-11-14: "verify if we're taking the correct setups ... by visually inspecting each trade's setup"): per trade row,
    (the UHV candle's time, the level whose break is the entry, the time of the candle where the retracement began) - or None when the row's
    setup cannot be told (the Turtle Trader Desk play, or InpUhvExec 0 with a latency)"""
    inp = inputs or {}
    out = [None] * len(tr)
    if not len(tr) or uhv_ttd.fv(inp, "InpTtdOn") > 0.5:
        return out
    dfile = det_file(inp)
    S, TK = _setups(dfile)
    D = sim.data("year1")
    t1 = np.asarray(D["t1"], dtype=np.int64)
    o1, h1, l1, c1 = (np.asarray(D[q]) for q in ("o1", "h1", "l1", "c1"))
    back, rs = int(fv(inp, "InpDetRetraceBack", 20)), int(fv(inp, "InpDetRetStart"))
    instant = int(fv(inp, "InpUhvEntry", 1)) == 1
    if instant:
        IS = _instant_setups(TK, fv(inp, "InpUhvPreBreak"), dfile, fv(inp, "InpUhvPreBreakFrac"), int(fv(inp, "InpUhvRetEnd")))
        key = {(int(round(q["t"] * 1000)), int(q["side"])): q for q in IS}
    else:
        TT = TK["t"]
        key = {}
        for q in S:
            j = int(np.searchsorted(TT, float(q["t"])))
            if j < len(TT):
                key[(int(round(float(TT[j]) * 1000)), int(q["side"]))] = q   # a later setup on the same tick wins, as the engine's last row would
    for i, r in enumerate(tr):
        q = key.get((int(round(r[1] * 1000)), int(r[0])))
        if q is None:
            continue
        kt = (int(q["bar"]) if instant else int(q["t"])) - 60       # the last closed candle when the setup was read
        k = int(np.searchsorted(t1, kt))
        if k >= len(t1) or t1[k] != kt:
            continue
        ob = _origin_bar(o1, h1, l1, c1, k, int(r[0]), back, rs)
        out[i] = (float(q["uhv_t"]), float(q["level"]), float(t1[ob]) if ob >= 0 else None)
    return out
