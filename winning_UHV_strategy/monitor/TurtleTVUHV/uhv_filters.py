"""uhv_filters.py - the loss filters as Turtle TV UHV settings (Zee 2026-11-06: "make each of the following a setting that can be tuned via
the Scanner ... then i can run the scanner and choose how many trades to cut"). Each one comes from his loss comments (Oct + Mar) and was
scored in research/loss_study (api.py, union_test.py). All are OFF at 0; each reads ONLY candles up to k = the last closed candle before
the entry (no look-ahead), so the tester, the scanner and a future EA agree.

  InpUhvStruct      1 = buys need a higher high AND a higher low in the last two swings (sells: lower low AND lower high); 2 = only the
                    higher high (lower low)
  InpUhvSRPips      skip a sell this close (pips) above the lowest low of the last InpUhvSRLook candles (a buy below the highest high)
  InpUhvRangeAtr    skip when the last InpUhvRangeBars candles span less than this many ATRs (a range)
  InpUhvFreshBreak  skip a sell when one of the last N candles broke above the highest of the last InpUhvFreshSwings swing highs before it
                    ("an uptrend has begun"); buys mirror
  InpUhvBrokeHighs  skip a sell when a candle in the last InpUhvBrokeLook candles made a high above the previous N swing highs; buys mirror
  InpUhvMaxHumps    skip when the camel has made this many humps (or more) of the trade's colour in a row (an exhausted trend)
  InpUhvDeepRet     skip a buy when the retracement fell this fraction (0.8 = 80%) of the way back from the last swing high to the low before
                    it in the last 60 candles (sells mirror) - "not enough momentum"
  InpUhvHtf5        1 = skip when the slope of the last InpUhvHtf5N 5-minute closes is against the trade; 2 = when the last 5-minute close
                    is on the wrong side of their InpUhvHtf5N EMA
Swings are 1-candle pivots (a high no lower than the candles either side), confirmed one candle later."""
import datetime as _dtm
from zoneinfo import ZoneInfo

import numpy as np

import uhv_diamond

_NY = ZoneInfo("America/New_York")
_HOLI = {2026: ("04-03", "04-06", "05-01", "05-04", "05-25", "07-03", "08-31", "09-07", "12-25", "12-28"), 2027: ("01-01", "03-26", "03-29", "05-03", "05-31")}

_C = {}

DEFAULTS = {
    "InpUhvStruct": ("0", "loss filter: 1 = buys only after a higher high AND higher low (sells: lower low AND lower high), 2 = only the higher high / lower low (0 = off)"),
    "InpUhvSRPips": ("0", "loss filter: skip a sell this many pips above the lowest low of the last InpUhvSRLook candles (a buy below the highest high) - support / resistance (0 = off)"),
    "InpUhvSRLook": ("60", "loss filter: candles back for the support / resistance level"),
    "InpUhvRangeAtr": ("0", "loss filter: skip when the last InpUhvRangeBars candles span less than this many ATRs - a range (0 = off)"),
    "InpUhvRangeBars": ("10", "loss filter: candles for the range test"),
    "InpUhvFreshBreak": ("0", "loss filter: skip a sell when one of the last N candles broke above the last InpUhvFreshSwings swing highs - an uptrend has begun; buys mirror (0 = off)"),
    "InpUhvFreshSwings": ("2", "loss filter: swing highs (lows) the fresh break must clear"),
    "InpUhvBrokeHighs": ("0", "loss filter: skip a sell when a recent candle broke above the previous N swing highs; buys mirror (0 = off)"),
    "InpUhvBrokeLook": ("8", "loss filter: candles back for 'broke N highs'"),
    "InpUhvMaxHumps": ("0", "loss filter: skip when the camel has made this many humps (or more) of the trade's colour in a row - exhausted trend (0 = off)"),
    "InpUhvDeepRet": ("0", "loss filter: skip when the retracement went this fraction back (0.8 = 80%) towards the last swing low (high) - no momentum (0 = off)"),
    "InpUhvHtf5": ("0", "loss filter: 1 = skip when the 5-minute slope is against the trade, 2 = when the 5-minute close is on the wrong side of its EMA (0 = off)"),
    "InpUhvHtf5N": ("12", "loss filter: 5-minute candles for the slope / EMA"),
    # ---- the loss study's cause categories (research/loss_study, 172 losses read on charts, 2026-11-06) - all off at 0
    "InpUhvSRAhead": ("0", "S/R: skip when a swing high (buy) / low (sell) from before the UHV, in the last InpUhvSRAheadLook candles, sits 0..this many pips beyond the level (0 = off)"),
    "InpUhvSRAheadLook": ("30", "S/R: candles back for the swing just beyond the level"),
    "InpUhvBigFig": ("0", "S/R: skip when a round figure (every InpUhvFigStep pips) sits 0..this many pips beyond the level (0 = off)"),
    "InpUhvFigStep": ("100", "S/R: round-figure step in pips (100 = 1.1200, 50 = 1.1250 too)"),
    "InpUhvMinHumps": ("0", "structure: trade only when the camel has made at least this many humps of the trade's colour in a row - no first-hump flips (0 = off)"),
    "InpUhvCounterAtr": ("0", "structure: skip when the last InpUhvCounterBars candles moved more than this many ATRs AGAINST the trade (0 = off)"),
    "InpUhvCounterBars": ("90", "structure: candles for the counter-move"),
    "InpUhvFriCutNY": ("0", "market close: no Friday entries from this New York hour on (e.g. 13 = 1 pm NY; 0 = off)"),
    "InpUhvFriCutAllNY": ("0", "market close for EVERY trade, the angel's secure zone too: no Friday entries from this New York hour on (0 = off). "
                          "The last angel loss (Fri 23 Oct 10:50 NY) was flattened by the weekly close; base Friday-from-10 pocket x2.6 on both halves"),
    "InpUhvRunPips": ("0", "exhausted: skip when the last InpUhvRunBars candles already ran this many pips IN the trade direction (0 = off)"),
    "InpUhvRunBars": ("30", "exhausted: candles for the run"),
    "InpUhvLoudBrk": ("0", "exhausted: skip when the breakout minute already has this share of the UHV's ticks at the break (0.9 = 90%; 0 = off)"),
    "InpUhvMinTicks": ("0", "dead market: skip when the last 10 candles averaged fewer ticks than this (0 = off)"),
    "InpUhvSunOpenMins": ("0", "dead market: no entries in the first this-many minutes after the Sunday 17:00 New York re-open (0 = off)"),
    "InpUhvNewsNY": ("0", "news: 1 = no entries from InpUhvNewsMins before to 1 minute after 08:30, 09:30, 10:00 New York on weekdays (0 = off)"),
    "InpUhvNewsMins": ("2", "news: minutes before the US data time"),
    "InpUhvSpikeAtr": ("0", "news / spike: skip when one of the last InpUhvSpikeBars candles spanned more than this many ATRs (0 = off)"),
    "InpUhvSpikeBars": ("15", "news / spike: candles back for the spike"),
    "InpUhvHoliday": ("0", "news / holiday: 1 = no entries on Good Friday, Easter Monday, 1 May, UK / US bank holidays, US Independence Day (0 = off)"),
    "InpUhvMinAtrPips": ("0", "chop: skip when the ATR is below this many pips - a dead, choppy tape (0 = off)"),
    "InpUhvMaxGapPips": ("0", "bad fill: skip when the breakout tick itself printed this many pips or more beyond the level - a gap through it (0 = off)"),
    # ---- selling into a MAJOR support (Zee 2026-11-06: "selling at support levels -> it can help us avoid 1-2 losses"): inside the angel's
    #      zones a sell within 2 pips above the last 10-candle swing low loses ~2x as often, on both halves (research/loss_study/pockets)
    "InpUhvSellSup": ("0", "sells: skip when the level sits 0..this many pips ABOVE one of the last InpUhvSellSupLast major swing lows (InpUhvSellSupPiv candles each side) - selling into support (0 = off)"),
    "InpUhvSellSupPiv": ("10", "sells: candles each side that make a swing low 'major'"),
    "InpUhvSellSupLast": ("1", "sells: how many of the last major swing lows count as support"),
    "InpUhvBuyRes": ("0", "buys: the mirror - skip when the level sits 0..this many pips BELOW one of the last major swing highs (0 = off; weaker evidence)"),
    # ---- a TESTED ROUND-FIGURE WALL (Zee 2026-11-06, the 8 April 12:56 loss: bought 1.16999 under a triple top on 1.1700): skip when a level the
    #      highs (buy) / lows (sell) touched >= InpUhvWallTouches times in the last InpUhvWallBars candles, sitting within 1 pip of a round
    #      figure, lies 0..X pips ahead of the entry. Base x2.1 (1.46 / 3.21 by half), 2.5% of trades (research/loss_study/pockets/triple_top.py)
    "InpUhvWall": ("0", "skip when a tested round-figure wall (a triple top / bottom on a 00 figure) lies 0..this many pips ahead (0 = off)"),
    "InpUhvWallTouches": ("3", "wall: touches that make a level 'tested'"),
    "InpUhvWallBars": ("60", "wall: candles back for the touches"),
    "InpUhvWallFig": ("100", "wall: round-figure step in pips (100 = 1.1700; 50 = 1.1750 too)"),
    # ---- Zee's ZONE MODEL (2026-11-06): risky pockets; the angel acts only there (InpUhvRiskMgr 3) or skips them (4)
    "InpUhvZStart": ("0", "zone: 1 = the START of a trend is risky (fewer than InpUhvZStartHumps camel humps in a row)"),
    "InpUhvZStartHumps": ("2", "zone: humps a trend needs before it is past its start"),
    "InpUhvZEnd": ("0", "zone: 1 = the END of a trend is risky (more than InpUhvZEndHumps humps in a row)"),
    "InpUhvZEndHumps": ("4", "zone: humps after which a trend is near its end"),
    "InpUhvZRange": ("0", "zone: 1 = inside a range box is risky (the last InpUhvZRangeBars candles span < InpUhvZRangeAtr ATRs) - a trade breaking OUT of the box in its own direction is allowed"),
    "InpUhvZRangeBars": ("20", "zone: candles for the range box"),
    "InpUhvZRangeAtr": ("3", "zone: the range box is narrower than this many ATRs"),
    "InpUhvZSR": ("0", "zone: near support / resistance is risky - a swing high (buy) / low (sell) within this many pips beyond the level, in the last InpUhvZSRLook candles (0 = off)"),
    "InpUhvZSRLook": ("60", "zone: candles back for support / resistance"),
    "InpUhvZNews": ("0", "zone: 1 = US data minutes (08:30, 09:30, 10:00 NY, 3 min before to 1 after) and a spike candle (> 3 ATR) in the last 15 candles are risky"),
    "InpUhvZClose": ("0", "zone: 1 = near the close is risky (16:00-18:00 New York every day, Friday from 13:00 New York)"),
    "InpUhvZOpen": ("0", "zone: 1 = near an open is risky (the first 30 min after 03:00 NY London, 08:00 NY New York, 09:30 NY stocks, and the Sunday 17:00 NY re-open)"),
    "InpUhvHarvestWins": ("0", "harvest: after this many WINS in the same trend, the trend is harvested - no more entries until the next trend (0 = off)"),
    "InpUhvHarvestStopLoss": ("1", "harvest: 1 = a loss also ends trading in that trend"),
    # ---- the Risk Manager (Zee 2026-11-06): the loss filters only where risk is expected
    "InpUhvRiskMgr": ("0", "risk manager: 0 = off (loss filters everywhere), 1 = loss filters only OUTSIDE the secure zone, 2 = trade only the secure zone, 3 = loss filters only INSIDE Zee's risky zones (the rest untouched), 4 = skip Zee's risky zones"),
    "InpUhvSafeHumpsMin": ("2", "risk manager: secure zone - at least this many camel humps in a row (not the start of a trend)"),
    "InpUhvSafeHumpsMax": ("5", "risk manager: secure zone - at most this many humps in a row (not an exhausted trend)"),
    "InpUhvSafeErMin": ("0.15", "risk manager: secure zone - efficiency ratio of the last InpUhvSafeErBars candles at least this (not chop)"),
    "InpUhvSafeErMax": ("0.45", "risk manager: secure zone - efficiency ratio at most this (not a spike)"),
    "InpUhvSafeErBars": ("16", "risk manager: candles for the efficiency ratio"),
    "InpUhvSafeRangeAtr": ("0", "risk manager: secure zone - NOT in a range: the last InpUhvSafeRangeBars candles must span at least this many ATRs (0 = off)"),
    "InpUhvSafeRangeBars": ("20", "risk manager: candles for the range test"),
}


def _prep(D):
    key = id(D)
    if _C.get("key") == key:
        return _C
    t, h, l, c, v = (np.asarray(D[k], dtype=float) for k in ("t1", "h1", "l1", "c1", "v1"))
    n = len(t)
    ph = np.zeros(n, bool); pl = np.zeros(n, bool)
    ph[1:-1] = (h[1:-1] >= h[:-2]) & (h[1:-1] >= h[2:])
    pl[1:-1] = (l[1:-1] <= l[:-2]) & (l[1:-1] <= l[2:])
    idx = np.arange(n)
    lastH = np.maximum.accumulate(np.where(ph, idx, -1))       # the last pivot high at or before i (a pivot at j is confirmed at j+1)
    lastL = np.maximum.accumulate(np.where(pl, idx, -1))
    # the camel: humps of the same colour in a row after each closed bar (uhv_diamond.camel_step, its CAM_PIV / CAM_CONFIRM)
    p = uhv_diamond.CAM_PIV
    stk = np.zeros(n, dtype=np.int16)
    T, HB, HV, L0B, L0V, LB, LV, S, S0 = 0, None, None, None, None, None, None, 0, 0
    for i in range(2 * p, n):
        cc = i - p
        a = all(not (h[cc] < h[cc + d] or h[cc] < h[cc - d]) for d in range(1, p + 1))
        b = all(not (l[cc] > l[cc + d] or l[cc] > l[cc - d]) for d in range(1, p + 1))
        if a:
            if T == 1:
                if h[cc] >= HV:
                    HB, HV = cc, h[cc]
            else:
                S0 = S; L0B, L0V, HB, HV, T = LB, LV, cc, h[cc], 1
        if b:
            redraw = False
            if T == 1:
                LB, LV, T, redraw = cc, l[cc], -1, True
            elif T == -1 and l[cc] <= LV:
                LB, LV, redraw = cc, l[cc], True
            elif T == 0:
                LB, LV, T = cc, l[cc], -1
            if redraw and HB is not None and L0B is not None:
                tr = 1 if LV > L0V else -1 if LV < L0V else 0
                S = (max(S0, 0) + 1) if tr == 1 else (min(S0, 0) - 1) if tr == -1 else 0
        stk[i] = S
    end5 = np.where(((t.astype(np.int64) + 60) % 300) == 0, idx, -1)
    end5 = np.maximum.accumulate(end5)                          # the last bar that closes a 5-minute candle, at or before i
    _C.clear()
    _C.update(key=key, h=h, l=l, c=c, v=v, t=t, lastH=lastH, lastL=lastL, stk=stk, end5=end5)
    return _C


def _swings(last, k, n):
    """the last n confirmed pivots (indices) up to bar k: a pivot at j is known once bar j+1 has closed (j <= k-1)"""
    out, j = [], (last[k - 1] if k >= 1 else -1)
    while j >= 0 and len(out) < n:
        out.append(j)
        j = last[j - 1] if j >= 1 else -1
    return out[::-1]


def risky_zone(fv, inp, D, side, k, level, ts):
    """Zee's zone model: the first risky pocket this entry sits in, or None (= the untouched zone). k = the last closed candle before the
    breakout minute, level = the UHV level, ts = the decision time (UTC s)."""
    C = _prep(D)
    h, l, c = C["h"], C["l"], C["c"]
    if k < 130:
        return None
    PIPS = 1e-4
    n = int(C["stk"][k]) * side
    if fv(inp, "InpUhvZStart") > 0.5 and n < fv(inp, "InpUhvZStartHumps", 2):
        return "start of trend"
    if fv(inp, "InpUhvZEnd") > 0.5 and n > fv(inp, "InpUhvZEndHumps", 4):
        return "end of trend"
    a = float(D["atr"][k]) if "atr" in D else 0.0
    if fv(inp, "InpUhvZRange") > 0.5 and a > 0:
        nb = max(4, int(fv(inp, "InpUhvZRangeBars", 20)))
        hi, lo = float(h[k - nb + 1:k + 1].max()), float(l[k - nb + 1:k + 1].min())
        if hi - lo < fv(inp, "InpUhvZRangeAtr", 3) * a:
            breakout = (level > hi) if side > 0 else (level < lo)   # breaking OUT of the box in the trade's direction is allowed
            if not breakout:
                return "inside a range"
    x = fv(inp, "InpUhvZSR")
    if x > 0:
        look = max(5, int(fv(inp, "InpUhvZSRLook", 60)))
        last = C["lastH"] if side > 0 else C["lastL"]
        for j in _swings(last, k, 20):
            if j < k - look:
                continue
            d = (h[j] - level) / PIPS if side > 0 else (level - l[j]) / PIPS
            if 0 <= d <= x:
                return "near support / resistance"
    if ts is not None and (fv(inp, "InpUhvZNews") > 0.5 or fv(inp, "InpUhvZClose") > 0.5 or fv(inp, "InpUhvZOpen") > 0.5):
        nyd = _dtm.datetime.fromtimestamp(ts, _NY)
        wd, mins = nyd.weekday(), nyd.hour * 60 + nyd.minute
        if fv(inp, "InpUhvZNews") > 0.5:
            sec = mins * 60 + nyd.second
            if wd < 5 and any(-180 <= sec - cc * 60 <= 60 for cc in (8 * 60 + 30, 9 * 60 + 30, 10 * 60)):
                return "news minute"
            if a > 0 and float((h[k - 14:k + 1] - l[k - 14:k + 1]).max()) > 3 * a:
                return "spike"
        if fv(inp, "InpUhvZClose") > 0.5 and (16 * 60 <= mins < 18 * 60 or (wd == 4 and mins >= 13 * 60)):
            return "near the close"
        if fv(inp, "InpUhvZOpen") > 0.5 and (any(0 <= mins - o < 30 for o in (3 * 60, 8 * 60, 9 * 60 + 30)) or (wd == 6 and 17 * 60 <= mins < 17 * 60 + 30)):
            return "near an open"
    return None


def trend_id(D, k, side):
    """the trend sub-zone: a new id every time the camel's colour (the sign of its humps-in-a-row) changes"""
    C = _prep(D)
    if "tid" not in C:
        sg = np.sign(C["stk"]).astype(np.int8)
        ch = np.zeros(len(sg), dtype=np.int64)
        ch[1:] = (sg[1:] != sg[:-1]) & (sg[1:] != 0)
        C["tid"] = np.cumsum(ch)
    return int(C["tid"][k])


_MAJ = {}


def _major_idx(D, p):
    """indices of p-candle swing lows / highs (a swing at j is known once candle j + p has closed)"""
    key = (id(D), p)
    if key not in _MAJ:
        C = _prep(D)
        h, l = C["h"], C["l"]
        n = len(h)
        lo = np.zeros(n, bool); hi = np.zeros(n, bool)
        for i in range(p, n - p):
            lo[i] = l[i] == l[i - p:i + p + 1].min(); hi[i] = h[i] == h[i - p:i + p + 1].max()
        _MAJ[key] = (np.flatnonzero(lo), np.flatnonzero(hi))
    return _MAJ[key]


def into_major(fv, inp, D, side, k, level):
    """selling into a major support (buying into a major resistance): the reason, or None"""
    x = fv(inp, "InpUhvSellSup") if side < 0 else fv(inp, "InpUhvBuyRes")
    if x <= 0 or level is None:
        return None
    p = max(2, int(fv(inp, "InpUhvSellSupPiv", 10))); m = max(1, int(fv(inp, "InpUhvSellSupLast", 1)))
    lows, highs = _major_idx(D, p)
    idx = lows if side < 0 else highs
    j = int(np.searchsorted(idx, k - p, side="right"))
    sel = idx[max(0, j - m):j]
    sel = sel[sel >= k - 720]
    if not len(sel):
        return None
    C = _prep(D)
    d = (level - C["l"][sel]) / 1e-4 if side < 0 else (C["h"][sel] - level) / 1e-4
    if np.any((d >= 0) & (d <= x)):
        return "selling into support" if side < 0 else "buying into resistance"
    return None


def into_wall(fv, inp, D, side, k, level):
    """a tested round-figure wall ahead: the reason, or None"""
    x = fv(inp, "InpUhvWall")
    if x <= 0 or level is None:
        return None
    C = _prep(D)
    T, N = max(1, int(fv(inp, "InpUhvWallTouches", 3))), max(10, int(fv(inp, "InpUhvWallBars", 60)))
    g = max(1.0, fv(inp, "InpUhvWallFig", 100)) * 1e-4
    ext = C["h"][k - N + 1:k + 1] if side > 0 else C["l"][k - N + 1:k + 1]
    for cc in np.unique(np.round(ext / 1e-5)) * 1e-5:
        d = (cc - level) / 1e-4 if side > 0 else (level - cc) / 1e-4
        if 0 <= d <= x and abs(cc - round(cc / g) * g) <= 1e-4 and int(np.sum(np.abs(ext - cc) <= 0.5e-4)) >= T:
            return "into a tested round-figure wall"
    return None


def secure(fv, inp, D, side, k):
    """the Risk Manager's SECURE zone at the last closed candle k: camel humps of the trade's colour in a row within [min, max] and the
    efficiency ratio of the last N candles within [min, max]"""
    C = _prep(D)
    n = int(C["stk"][k]) * side
    if not (fv(inp, "InpUhvSafeHumpsMin", 2) <= n <= fv(inp, "InpUhvSafeHumpsMax", 5)):
        return False
    m = max(4, int(fv(inp, "InpUhvSafeErBars", 16)))
    if k - m < 0:
        return False
    cc = C["c"][k - m:k + 1]
    path = float(np.abs(np.diff(cc)).sum())
    er = abs(float(cc[-1] - cc[0])) / path if path > 0 else 0.0
    if not (fv(inp, "InpUhvSafeErMin", 0.15) <= er < fv(inp, "InpUhvSafeErMax", 0.45)):
        return False
    x = fv(inp, "InpUhvSafeRangeAtr")
    if x > 0:                                                     # Zee: "ranges / etc whichever areas are loss prone" - a range is never secure
        nb = max(4, int(fv(inp, "InpUhvSafeRangeBars", 20)))
        a = float(D["atr"][k]) if "atr" in D else 0.0
        if a > 0 and float(C["h"][k - nb + 1:k + 1].max() - C["l"][k - nb + 1:k + 1].min()) < x * a:
            return False
    return True


def active(fv, inp):
    return any(fv(inp, k) > 0 for k in ("InpUhvStruct", "InpUhvSRPips", "InpUhvRangeAtr", "InpUhvFreshBreak", "InpUhvBrokeHighs",
                                        "InpUhvMaxHumps", "InpUhvDeepRet", "InpUhvHtf5", "InpUhvSRAhead", "InpUhvBigFig", "InpUhvMinHumps",
                                        "InpUhvCounterAtr", "InpUhvFriCutNY", "InpUhvRunPips", "InpUhvLoudBrk", "InpUhvMinTicks",
                                        "InpUhvSunOpenMins", "InpUhvNewsNY", "InpUhvSpikeAtr", "InpUhvHoliday", "InpUhvMinAtrPips",
                                        "InpUhvMaxGapPips"))


def skip(fv, inp, D, side, k, px, atr_k, extreme, level=None, ku=None, ts=None, uhv_v=None, brk_ticks=None, brk_px=None):
    """None, or the name of the loss filter that skips this entry. k = the last closed candle before the entry, px = the entry price,
    extreme = the setup's retracement extreme (known at the entry)."""
    C = _prep(D)
    h, l, c = C["h"], C["l"], C["c"]
    if k < 130:
        return None
    PIP = 1e-4
    m = fv(inp, "InpUhvStruct")
    if m > 0:
        hs, ls = _swings(C["lastH"], k, 2), _swings(C["lastL"], k, 2)
        if len(hs) == 2 and len(ls) == 2:
            hh, hl = h[hs[1]] > h[hs[0]], l[ls[1]] > l[ls[0]]
            ll, lh = l[ls[1]] < l[ls[0]], h[hs[1]] < h[hs[0]]
            ok = ((hh and hl) if side > 0 else (ll and lh)) if m < 1.5 else (hh if side > 0 else ll)
            if not ok:
                return "structure"
    x = fv(inp, "InpUhvSRPips")
    if x > 0:
        n = max(2, int(fv(inp, "InpUhvSRLook", 60)))
        lo, hi = l[k - n + 1:k + 1].min(), h[k - n + 1:k + 1].max()
        if (side < 0 and px - lo < x * PIP) or (side > 0 and hi - px < x * PIP):
            return "support/resistance"
    x = fv(inp, "InpUhvRangeAtr")
    if x > 0 and atr_k > 0:
        n = max(2, int(fv(inp, "InpUhvRangeBars", 10)))
        if h[k - n + 1:k + 1].max() - l[k - n + 1:k + 1].min() < x * atr_k:
            return "range"
    x = int(fv(inp, "InpUhvFreshBreak"))
    if x > 0:
        nsw = max(1, int(fv(inp, "InpUhvFreshSwings", 2)))
        if side < 0:
            sw = _swings(C["lastH"], k - x, nsw)
            if len(sw) == nsw and h[k - x + 1:k + 1].max() > max(h[j] for j in sw):
                return "fresh break"
        else:
            sw = _swings(C["lastL"], k - x, nsw)
            if len(sw) == nsw and l[k - x + 1:k + 1].min() < min(l[j] for j in sw):
                return "fresh break"
    x = int(fv(inp, "InpUhvBrokeHighs"))
    if x > 0:
        lk = max(1, int(fv(inp, "InpUhvBrokeLook", 8)))
        if side < 0:
            sw = _swings(C["lastH"], k - lk, x)
            if len(sw) == x and h[k - lk + 1:k + 1].max() > max(h[j] for j in sw):
                return "broke highs"
        else:
            sw = _swings(C["lastL"], k - lk, x)
            if len(sw) == x and l[k - lk + 1:k + 1].min() < min(l[j] for j in sw):
                return "broke highs"
    x = int(fv(inp, "InpUhvMaxHumps"))
    if x > 0 and abs(int(C["stk"][k])) >= x:
        return "exhausted"
    x = fv(inp, "InpUhvDeepRet")
    if x > 0:
        hs = [j for j in _swings(C["lastH"], k, 60) if j >= k - 60]
        ls = [j for j in _swings(C["lastL"], k, 60) if j >= k - 60]
        if hs and len(ls) >= 2:
            hi = max(h[j] for j in hs); lo = min(l[j] for j in ls[:-1])
            ext = extreme
            if hi > lo and ((side > 0 and (hi - ext) / (hi - lo) >= x) or (side < 0 and (ext - lo) / (hi - lo) >= x)):
                return "deep retracement"
    m = int(fv(inp, "InpUhvHtf5"))
    if m > 0:
        n = max(3, int(fv(inp, "InpUhvHtf5N", 12)))
        end = int(C["end5"][k])
        cnt = n if m == 1 else 3 * n
        if end - 5 * (cnt - 1) >= 0:
            cl = c[[end - 5 * i for i in range(cnt)][::-1]]
            if m == 1:
                slope = np.polyfit(np.arange(cnt), cl, 1)[0]
                if (side > 0 and slope < 0) or (side < 0 and slope > 0):
                    return "5-min trend"
            else:
                a = 2.0 / (n + 1); e = cl[0]
                for v in cl[1:]:
                    e = a * v + (1 - a) * e
                if (side > 0 and cl[-1] < e) or (side < 0 and cl[-1] > e):
                    return "5-min trend"
    # ---- the loss study's cause categories
    PIPS = 1e-4
    x = fv(inp, "InpUhvSRAhead")
    if x > 0 and level is not None:
        look = max(5, int(fv(inp, "InpUhvSRAheadLook", 30)))
        last = C["lastL"] if side < 0 else C["lastH"]
        for j in _swings(last, k, 12):
            if j < k - look or (ku is not None and j >= ku):
                continue
            d = (level - l[j]) / PIPS if side < 0 else (h[j] - level) / PIPS
            if 0 <= d <= x:
                return "S/R just ahead"
    x = fv(inp, "InpUhvBigFig")
    if x > 0 and level is not None:
        g = max(1.0, fv(inp, "InpUhvFigStep", 100)) * PIPS
        d = (np.ceil(level / g - 1e-9) * g - level) / PIPS if side > 0 else (level - np.floor(level / g + 1e-9) * g) / PIPS
        if 0 < d <= x:
            return "round figure ahead"
    x = int(fv(inp, "InpUhvMinHumps"))
    if x > 0 and int(C["stk"][k]) * side < x:
        return "too few humps"
    x = fv(inp, "InpUhvCounterAtr")
    if x > 0 and atr_k > 0:
        n = max(5, int(fv(inp, "InpUhvCounterBars", 90)))
        if k - n >= 0 and (c[k] - c[k - n]) * side < -x * atr_k:
            return "counter-move"
    if ts is not None:
        nyd = _dtm.datetime.fromtimestamp(ts, _NY)
        wd, mins = nyd.weekday(), nyd.hour * 60 + nyd.minute
        x = fv(inp, "InpUhvFriCutNY")
        if x > 0 and wd == 4 and mins >= x * 60:
            return "Friday close"
        x = fv(inp, "InpUhvSunOpenMins")
        if x > 0 and wd == 6 and 17 * 60 <= mins < 17 * 60 + x:
            return "Sunday open"
        if fv(inp, "InpUhvNewsNY") > 0.5 and wd < 5:
            pre = max(0.5, fv(inp, "InpUhvNewsMins", 2))
            sec = mins * 60 + nyd.second
            if any(-pre * 60 <= sec - cc * 60 <= 60 for cc in (8 * 60 + 30, 9 * 60 + 30, 10 * 60)):
                return "US data"
        if fv(inp, "InpUhvHoliday") > 0.5 and nyd.strftime("%m-%d") in _HOLI.get(nyd.year, ()):
            return "holiday"
    x = fv(inp, "InpUhvRunPips")
    if x > 0:
        n = max(3, int(fv(inp, "InpUhvRunBars", 30)))
        if k - n >= 0 and (c[k] - c[k - n]) * side > x * PIPS:
            return "extended run"
    x = fv(inp, "InpUhvLoudBrk")
    if x > 0 and uhv_v and brk_ticks is not None and brk_ticks >= x * uhv_v:
        return "loud breakout"
    x = fv(inp, "InpUhvMinTicks")
    if x > 0 and float(np.mean(C["v"][k - 9:k + 1])) < x:
        return "dead tape"
    x = fv(inp, "InpUhvSpikeAtr")
    if x > 0 and atr_k > 0:
        n = max(1, int(fv(inp, "InpUhvSpikeBars", 15)))
        if float((h[k - n + 1:k + 1] - l[k - n + 1:k + 1]).max()) > x * atr_k:
            return "spike"
    x = fv(inp, "InpUhvMinAtrPips")
    if x > 0 and atr_k < x * PIPS:
        return "too quiet"
    x = fv(inp, "InpUhvMaxGapPips")
    if x > 0 and brk_px is not None and level is not None and (brk_px - level) * side >= x * PIPS - 1e-12:
        return "gap through the level"
    return None
