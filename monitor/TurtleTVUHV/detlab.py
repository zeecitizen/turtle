"""detlab.py - the Detector Lab (Zee 2026-11-08: "we might want to fine-tune/improve our detectors which are handling these kinds of
fixes/losses/risk.. let's build web pages for each detector that detects this kind of loss ... with diagrams i can fine tune, with labelling
options i can label to improve the accuracy of the detector ... The only way forward is to have the ability to fix broken detectors so they're
not causing a lossy trade!").

Four detectors, each a bundle of the engine's own loss filters (uhv_filters.py), so a tuned detector IS a setting:
  ranging   📦 the quiet box, the N-candle range, the efficiency ratio, the short squeeze box, the wide swing, the range position, the zone box
  sr        🧱 selling into a major support / buying into a major resistance, the tested round-figure wall, S/R pips, S/R just ahead, big figure
  trend     🔀 camel v2 against / not confirmed, EMA slope shift, Stochastic RSI cross, anchored VWAP, lower high, structure, fresh break,
               broke highs, counter-move, 5-minute trend, wick fake-break
  choppy    🌊 direction flips, ATR too low / too high, efficiency ratio, dead ticks, dead volume
Every verdict comes from the SAME functions the tester runs (uhv_filters.skip / in_quiet_box / into_major / into_wall / risky_zone), called with
only that sub-rule's inputs on, so the lab's "FIRES" is exactly what the engine would do. Every function reads candles <= k (the last closed
candle before the entry) only - look-ahead is the cardinal sin; lookahead_check() proves it by mutating the candles after k.
All numbers here are TESTER ESTIMATES (Python): a hypothesis until MT5 / live fills confirm it."""
import datetime as _dt
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import sim  # noqa: E402
import uhv_filters as F  # noqa: E402
import uhv_engine as U  # noqa: E402
from uhv_engine import fv  # noqa: E402

PIP = 1e-4
SAVED = HERE / "settings" / "saved"
SIMDATA = HERE / "simdata"
LABELS_FILE = HERE / "settings" / "detector_labels.json"
LOSSES_1209 = HERE / "research" / "env_analyzer" / "losses_1209.json"
LOSS_COMMENTS = HERE / "settings" / "loss_comments.json"
N_BEFORE, N_AFTER = 120, 20
SAVED_NAME_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]|\.\.')
PKT = _dt.timezone(_dt.timedelta(hours=5))
_LOCK = threading.Lock()

# every filter OFF (the engine's own defaults): a sub-rule is judged with ONLY its own inputs switched on
_OFF = {k: v for k, (v, _) in F.DEFAULTS.items()}


def _utc(ts):
    return _dt.datetime.fromtimestamp(float(ts), _dt.timezone.utc)


def _pkt(ts):
    return _dt.datetime.fromtimestamp(float(ts), PKT).strftime("%d %b %I:%M %p PKT")


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(d)


def _same(a, b):
    # review 2026-11-08: a 21-char range-box string (InpBandsB / InpBandsS) parses as a 21-digit float (~1.1e20, ULP 16384), so flipping any
    # of the last four boxes (85-100%, beyond) did not change the float and the move / the diff was dropped. A string over 15 chars is never a
    # legitimate number here: compare it as text.
    if isinstance(a, str) and isinstance(b, str) and (len(a.strip()) > 15 or len(b.strip()) > 15):
        return a.strip() == b.strip()
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def _merged(inputs, params=None):
    M = {k: str(v) for k, v in (inputs or {}).items()}
    for k, v in (params or {}).items():
        M[k] = str(v)
    return M


def _val(M, key):
    return fv(M, key, _f(F.DEFAULTS.get(key, ("0", ""))[0]))


def _D():
    return sim.data("year1")


# ====================================================================================================== the parameters (= engine inputs)
# label, type, min, max, step, options, grid (the scanner's values, scan.py G[...]), unit note
P = {
    # ranging
    "InpUhvBoxInside": dict(label="Quiet box: skip a level INSIDE the box", type="enum", options=[0, 1], grid=[0, 1]),
    "InpUhvBoxBars": dict(label="Quiet box: candles back", type="num", min=10, max=120, step=5, grid=[20, 30, 45, 60, 90]),
    "InpUhvBoxAtr": dict(label="Quiet box: ATR below this x its average before (0 = no ATR check)", type="num", min=0, max=1.5, step=0.05, grid=[0, 0.8, 0.9, 1.0, 1.2]),
    "InpUhvBoxVol": dict(label="Quiet box: volume below this x the average before (0 = no volume check)", type="num", min=0, max=1.5, step=0.05, grid=[0, 0.8, 0.9, 1.0, 1.2]),
    "InpUhvRangeAtr": dict(label="Range: last N candles span less than this many ATRs (0 = off)", type="num", min=0, max=6, step=0.25, grid=[0, 1, 1.5, 2, 2.5, 3]),
    "InpUhvRangeBars": dict(label="Range: candles (N)", type="num", min=3, max=60, step=1, grid=[5, 10, 15, 20, 30]),
    "InpUhvMinErN": dict(label="Efficiency ratio of the last N closes at least this (0 = off)", type="num", min=0, max=0.6, step=0.01, grid=[0, 0.05, 0.1, 0.15, 0.2, 0.3]),
    "InpUhvErNBars": dict(label="Efficiency ratio: closes (N)", type="num", min=3, max=90, step=1, grid=[5, 10, 15, 20, 30, 45]),
    "InpUhvMinSpanAtr": dict(label="Short squeeze box: last N candles span less than this many ATRs (0 = off)", type="num", min=0, max=4, step=0.1, grid=[0, 1, 1.5, 2]),
    "InpUhvMinSpanBars": dict(label="Short squeeze box: candles (N)", type="num", min=2, max=20, step=1, grid=[5, 8, 10]),
    "InpUhvMaxSpan20Atr": dict(label="Wide swing: last N candles span MORE than this many ATRs (0 = off)", type="num", min=0, max=15, step=0.1, grid=[0, 5, 6, 6.565, 8, 10]),
    "InpUhvSpanBars": dict(label="Wide swing: candles (N)", type="num", min=3, max=60, step=1, grid=[10, 15, 20, 30]),
    "InpUhvMinPos": dict(label="Range position: level in the wrong end of the range, below this share (0 = off)", type="num", min=0, max=0.9, step=0.05, grid=[0, 0.2, 0.3, 0.4, 0.5]),
    "InpUhvPosBars": dict(label="Range position: candles", type="num", min=3, max=90, step=1, grid=[10, 20, 30, 60]),
    "InpUhvZRange": dict(label="Zone box: skip inside a range box (1 = on; acts only with InpUhvRiskMgr 4)", type="enum", options=[0, 1], grid=[0, 1]),
    "InpUhvZRangeBars": dict(label="Zone box: candles", type="num", min=4, max=90, step=1, grid=[10, 20, 30, 60]),
    "InpUhvZRangeAtr": dict(label="Zone box: narrower than this many ATRs", type="num", min=0.5, max=8, step=0.25, grid=[2, 3, 4, 5]),
    # sr
    "InpUhvSellSup": dict(label="Sell into support: level 0..this many pips above a major swing low (0 = off)", type="num", min=0, max=5, step=0.1, grid=[0, 0.5, 1, 1.5, 2, 3]),
    "InpUhvBuyRes": dict(label="Buy into resistance: level 0..this many pips below a major swing high (0 = off)", type="num", min=0, max=5, step=0.1, grid=[0, 0.5, 1, 1.5, 2, 3]),
    "InpUhvSellSupPiv": dict(label="Major swing: candles each side", type="num", min=2, max=40, step=1, grid=[5, 10, 20]),
    "InpUhvSellSupLast": dict(label="Major swings that count (the last N)", type="num", min=1, max=5, step=1, grid=[1, 2, 3]),
    "InpUhvWall": dict(label="Round-figure wall 0..this many pips ahead (0 = off)", type="num", min=0, max=5, step=0.1, grid=[0, 0.5, 1, 1.5, 2]),
    "InpUhvWallTouches": dict(label="Wall: touches that make it tested", type="num", min=1, max=6, step=1, grid=[1, 2, 3, 4]),
    "InpUhvWallBars": dict(label="Wall: candles back", type="num", min=10, max=240, step=5, grid=[30, 60, 120]),
    "InpUhvWallFig": dict(label="Wall: round-figure step (pips)", type="enum", options=[100, 50, 25, 10], grid=[100, 50]),
    "InpUhvSRPips": dict(label="S/R pips: entry this close to the N-candle low (sell) / high (buy) (0 = off)", type="num", min=0, max=8, step=0.1, grid=[0, 0.5, 1, 1.5, 2, 3, 4, 5]),
    "InpUhvSRLook": dict(label="S/R pips: candles back", type="num", min=5, max=300, step=5, grid=[20, 30, 60, 120, 240]),
    "InpUhvSRAhead": dict(label="S/R just ahead: a swing 0..this many pips beyond the level (0 = off)", type="num", min=0, max=4, step=0.1, grid=[0, 0.3, 0.5, 1.0, 1.5, 2.0]),
    "InpUhvSRAheadLook": dict(label="S/R just ahead: candles back", type="num", min=5, max=240, step=5, grid=[15, 30, 60, 120]),
    "InpUhvBigFig": dict(label="Round figure 0..this many pips beyond the level (0 = off)", type="num", min=0, max=4, step=0.1, grid=[0, 0.5, 0.8, 1.0, 1.5, 2.0]),
    "InpUhvFigStep": dict(label="Round figure step (pips)", type="enum", options=[100, 50, 25, 10], grid=[100, 50]),
    # trend
    "InpUhvV2Against": dict(label="Camel v2: 1 = skip AGAINST the trend, 2 = only WITH a confirmed trend", type="enum", options=[0, 1, 2], grid=[0, 1, 2]),
    "InpUhvV2Piv": dict(label="Camel v2: swing size (candles each side)", type="num", min=1, max=8, step=1, grid=[2, 3, 5]),
    "InpUhvV2NoHH": dict(label="Camel v2: ranging until price is this many pips beyond the broken swing", type="num", min=0, max=6, step=0.5, grid=[0, 1, 2, 3]),
    "InpUhvV2Back": dict(label="Camel v2: ranging when back within this many pips of the last swing", type="num", min=0, max=6, step=0.5, grid=[0, 1, 2, 3]),
    "InpUhvShiftEma": dict(label="EMA shift: skip when both EMAs slope against the trade", type="enum", options=[0, 1], grid=[0, 1]),
    "InpUhvShiftEmaFast": dict(label="EMA shift: fast period", type="num", min=3, max=30, step=1, grid=[5, 8, 13]),
    "InpUhvShiftEmaSlow": dict(label="EMA shift: slow period", type="num", min=10, max=100, step=1, grid=[21, 34, 55]),
    "InpUhvShiftStoch": dict(label="Stochastic RSI: skip on a cross out of oversold against a sell (overbought vs a buy)", type="enum", options=[0, 1], grid=[0, 1]),
    "InpUhvShiftStochLvl": dict(label="Stochastic RSI: oversold level (overbought = 100 - this)", type="num", min=10, max=50, step=1, grid=[20, 30, 40]),
    "InpUhvShiftAvwap": dict(label="Anchored VWAP: skip on the wrong side of the VWAP from the extreme of the last N candles (0 = off)", type="num", min=0, max=240, step=5, grid=[0, 30, 60, 90, 120]),
    "InpUhvNoLowerHigh": dict(label="No buys after a lower high / no sells after a higher low", type="enum", options=[0, 1], grid=[0, 1]),
    "InpUhvLhPiv": dict(label="Lower high: swing size", type="num", min=1, max=10, step=1, grid=[2, 3, 5]),
    "InpUhvStruct": dict(label="Structure: 1 = higher high AND higher low needed, 2 = only the higher high", type="enum", options=[0, 1, 2], grid=[0, 1, 2]),
    "InpUhvFreshBreak": dict(label="Fresh break: one of the last N candles broke the last swing highs (sell) - an uptrend began (0 = off)", type="num", min=0, max=12, step=1, grid=[0, 1, 2, 3, 5, 8]),
    "InpUhvFreshSwings": dict(label="Fresh break: swings to clear", type="num", min=1, max=5, step=1, grid=[1, 2, 3, 4]),
    "InpUhvBrokeHighs": dict(label="Broke highs: a recent candle broke the previous N swing highs (sell) (0 = off)", type="num", min=0, max=8, step=1, grid=[0, 2, 3, 4, 5, 6, 8]),
    "InpUhvBrokeLook": dict(label="Broke highs: candles back", type="num", min=1, max=30, step=1, grid=[2, 4, 8, 12, 20]),
    "InpUhvCounterAtr": dict(label="Counter-move: last N candles moved more than this many ATRs against the trade (0 = off)", type="num", min=0, max=15, step=0.5, grid=[0, 3, 4, 6, 8]),
    "InpUhvCounterBars": dict(label="Counter-move: candles (N)", type="num", min=5, max=240, step=5, grid=[30, 60, 90, 120]),
    "InpUhvHtf5": dict(label="5-minute trend: 1 = slope against, 2 = close on the wrong side of its EMA", type="enum", options=[0, 1, 2], grid=[0, 1, 2]),
    "InpUhvHtf5N": dict(label="5-minute trend: candles", type="num", min=3, max=60, step=1, grid=[3, 6, 12, 20, 50]),
    "InpUhvWickFake": dict(label="Wick fake-break: a recent wick poked beyond the last swing and closed back", type="enum", options=[0, 1], grid=[0, 1]),
    "InpUhvWickBars": dict(label="Wick fake-break: candles back", type="num", min=1, max=10, step=1, grid=[1, 2, 3, 5]),
    # choppy
    "InpUhvMaxFlips60": dict(label="Choppy hour: closes changed direction more than this share of the time (0 = off)", type="num", min=0, max=0.9, step=0.01, grid=[0, 0.45, 0.5, 0.56, 0.6, 0.65]),
    "InpUhvFlipsBars": dict(label="Choppy hour: candles", type="num", min=5, max=180, step=5, grid=[30, 45, 60, 90]),
    "InpUhvMinAtrPips": dict(label="Dead tape: ATR below this many pips (0 = off)", type="num", min=0, max=3, step=0.1, grid=[0, 0.5, 0.8, 1.0, 1.5, 2.0]),
    "InpUhvMaxAtrPips": dict(label="Too volatile: ATR above this many pips (0 = off)", type="num", min=0, max=6, step=0.1, grid=[0, 1.5, 2.0, 2.5, 3.0]),
    "InpUhvMinTicks": dict(label="Dead market: last 10 candles averaged fewer ticks than this (0 = off)", type="num", min=0, max=80, step=1, grid=[0, 10, 15, 20, 30, 40]),
    "InpUhvMinVolRel": dict(label="Dead volume: last 10 candles' volume below this x the 300 before (0 = off)", type="num", min=0, max=1.5, step=0.05, grid=[0, 0.4, 0.5, 0.6, 0.8]),
}

# Which way is STRICTER? The whole-setting estimate only sees the trades the setting took, so it can measure a rule firing on MORE of them (a
# tightening) but never a rule firing on fewer (a loosening lets in trades the estimate has never seen: the fit's "best" row on 2026-11-07 12-09-37
# turned the quiet box OFF and the full engine answered 3,621 trades / 35 losses against an estimate of 2 losses cut). dir "up" = a higher value
# fires on a superset, "down" = a lower value does; zero "off" = 0 switches the rule off, "nocheck" = 0 drops a condition (fires MORE); no entry =
# a structural input (candles back, swing size, mode) whose change is neither - locked while its rule is on.
TIGHTER = {
    "InpUhvBoxAtr": ("up", "nocheck"), "InpUhvBoxVol": ("up", "nocheck"), "InpUhvRangeAtr": ("up", "off"), "InpUhvMinErN": ("up", "off"),
    "InpUhvMinSpanAtr": ("up", "off"), "InpUhvMaxSpan20Atr": ("down", "off"), "InpUhvMinPos": ("up", "off"), "InpUhvZRangeAtr": ("up", None),
    "InpUhvSellSup": ("up", "off"), "InpUhvBuyRes": ("up", "off"), "InpUhvSellSupLast": ("up", None), "InpUhvWall": ("up", "off"),
    "InpUhvWallTouches": ("down", None), "InpUhvSRPips": ("up", "off"), "InpUhvSRAhead": ("up", "off"), "InpUhvBigFig": ("up", "off"),
    "InpUhvFreshBreak": ("up", "off"), "InpUhvFreshSwings": ("down", None), "InpUhvBrokeHighs": ("down", "off"), "InpUhvBrokeLook": ("up", None),
    "InpUhvCounterAtr": ("down", "off"), "InpUhvWickBars": ("up", None),
    "InpUhvMaxFlips60": ("down", "off"), "InpUhvMinAtrPips": ("up", "off"), "InpUhvMaxAtrPips": ("down", "off"), "InpUhvMinTicks": ("up", "off"),
    "InpUhvMinVolRel": ("up", "off"),
}
for _k, (_d, _z) in TIGHTER.items():
    P[_k]["dir"], P[_k]["zero"] = _d, _z


def _key_tightens(key, cur, new):
    """True when moving `key` from cur to new can only make its rule fire on MORE trades (or leaves it unchanged)"""
    c, n = float(cur), float(new)
    if abs(c - n) < 1e-9:
        return True
    d, z = P[key].get("dir"), P[key].get("zero")
    if d is None:
        return False                                            # structural: a different rule, not a stricter one
    if z == "off":
        if c == 0:
            return True                                         # this check was off: anything switches it on (fires more)
        if n == 0:
            return False                                        # switching it off lets trades in
    elif z == "nocheck":
        if n == 0:
            return True                                         # dropping the condition fires more
        if c == 0:
            return False                                        # adding a condition fires less
    return n > c if d == "up" else n < c


def loosens(det, inputs, params):
    """the names of the detector's rules that are ON in the setting and that `params` could make fire on FEWER trades (the estimate cannot see those)"""
    M0, M1 = _merged(inputs), _merged(inputs, params)
    out = []
    for r in _rules(det):
        if not _is_on(M0, r):
            continue                                            # an OFF rule can only be switched on = trades removed, which the estimate sees
        for k in r["keys"]:
            if k in params and not _key_tightens(k, _val(M0, k), _val(M1, k)):
                out.append(r["name"])
                break
    return out


# ====================================================================================================== overlay helpers (candles <= k ONLY)
COL = {"ranging": "#f5c542", "sr": "#e06c75", "trend": "#61afef", "choppy": "#56b6c2", "grey": "#8b8f98", "green": "#7ec97e", "red": "#e06c75"}


class LookAhead(AssertionError):
    pass


def _chk(k, *idx):
    """the cardinal sin guard: every bar index an overlay or a feature touches must be <= k"""
    for j in idx:
        if j is not None and int(j) > int(k):
            raise LookAhead(f"bar {j} > k {k}")


def _hline(y, color, label):
    return {"type": "hline", "y": float(y), "color": color, "label": label}


def _box(k0, k1, top, bot, color, label):
    return {"type": "box", "k0": int(k0), "k1": int(k1), "top": float(top), "bot": float(bot), "color": color, "label": label}


def _line(pts, color, label):
    return {"type": "line", "pts": [[int(a), float(b)] for a, b in pts], "color": color, "label": label}


def _marker(k, y, text, color):
    return {"type": "marker", "k": int(k), "y": float(y), "text": text, "color": color}


def _vline(k, color, label):
    return {"type": "vline", "k": int(k), "color": color, "label": label}


def _note(text):
    return {"type": "note", "text": text}


def _er(c, k, N):
    cc = c[k - N:k + 1]
    path = float(np.abs(np.diff(cc)).sum())
    return (abs(float(cc[-1] - cc[0])) / path if path > 0 else 0.0)


def _v2_state(D, k, p):
    """camel v2's swings / flip / broken swing at k (the same loop as uhv_filters.v2_trend, kept for DRAWING - the verdict is v2_trend's)"""
    C = F._prep(D)
    h, l, c = C["h"], C["l"], C["c"]
    sh, sl = [], []
    t, flip, brk = 0, -1, None
    for j in range(max(2 * p, k - 400), k + 1):
        i = j - p
        if h[i] == h[i - p:j + 1].max():
            sh.append((i, float(h[i])))
        if l[i] == l[i - p:j + 1].min():
            sl.append((i, float(l[i])))
        if sh and c[j] > sh[-1][1] and t != 1:
            t, flip, brk = 1, j, sh[-1][1]
        elif sl and c[j] < sl[-1][1] and t != -1:
            t, flip, brk = -1, j, sl[-1][1]
    return t, flip, brk, sh, sl


# ====================================================================================================== the rules
# each: name, kind (skip / box / major / wall / zone), switch (the on/off input), keys (all its inputs), text(M) -> plain English, overlay(M, D, tr)
def _r(name, kind, switch, keys, text, overlay, on=None):
    return {"name": name, "kind": kind, "switch": switch, "keys": keys, "text": text, "overlay": overlay, "on": on}


def _on_default(M, rule):
    return _val(M, rule["switch"]) > 0


def _rule_inputs(M, rule):
    inp = dict(_OFF)
    for key in rule["keys"]:
        inp[key] = M.get(key, _OFF.get(key, "0"))
    return inp


def _rm(M):
    return int(_val(M, "InpUhvRiskMgr")) if M else 0


def _avail(M, rule):
    """does the engine apply this sub-rule AT ALL in this setting? the zone box skips only under Risk Manager mode 4 (uhv_engine.simulate: rm 3
    marks the risky zone for the angel but takes the trade; rm 0/1/2 never call risky_zone)"""
    return _rm(M) == 4 if rule["kind"] == "zone" else True


def _call(rule, inp, D, tr, M=None):
    """the engine's own verdict for ONE sub-rule: the reason string, or None. Gated exactly like uhv_engine.simulate (lines 430-455): skip() runs
    only `if lf_on and not sec` - tr['sec'] is the Risk Manager's verdict for this trade (secure zone under rm 1/2, outside every risky zone under
    rm 3/4; computed in trades() with the setting's own inputs) - and risky_zone() removes a trade only under rm 4. Review 2026-11-08: without
    this the lab counted skip-type rules on trades the engine never filters (an RM 2 save: 'cuts 1 loss + 248 winners', the engine: no change)."""
    side, k, level = tr["side"], tr["k"], tr["level"]
    kind = rule["kind"]
    if kind == "box":
        return F.in_quiet_box(fv, inp, D, side, k, level)
    if kind == "major":
        return F.into_major(fv, inp, D, side, k, level)
    if kind == "wall":
        return F.into_wall(fv, inp, D, side, k, level)
    if kind == "zone":
        if _rm(M) != 4:
            return None
        return F.risky_zone(fv, inp, D, side, k, level, tr.get("ts"))
    if tr.get("sec"):
        return None
    return F.skip(fv, inp, D, side, k, tr["px"], tr["atr"], tr["extreme"], level=level, ku=tr.get("ku"), ts=tr.get("ts"),
                  uhv_v=tr.get("uv") or None, brk_ticks=tr.get("bv"), brk_px=tr.get("bc"))


# ---- ranging overlays
def _ov_box(M, D, tr):
    C = F._prep(D); h, l, v = C["h"], C["l"], C["v"]
    k, side, level = tr["k"], tr["side"], tr["level"]
    N = max(10, int(_val(M, "InpUhvBoxBars"))); a = k - N + 1
    if a < 420:
        return [_note("quiet box: not enough history before this candle")]
    _chk(k, a, k)
    hh, ll = h[a:k + 1], l[a:k + 1]
    top, bot = float(hh.max()), float(ll.min()); ht = top - bot; tol = 0.15 * ht
    out = [_box(a, k, top, bot, COL["ranging"], f"quiet box {N} candles, {ht / PIP:.1f} pips"),
           _hline(top - tol, COL["ranging"], "top zone (15%)"), _hline(bot + tol, COL["ranging"], "bottom zone (15%)")]

    def touches(mask):
        cnt, last, idx = 0, -99, []
        for q in np.flatnonzero(mask):
            if q - last >= 3:
                cnt += 1; last = q; idx.append(int(q))
        return cnt, idx
    nt, it = touches(hh >= top - tol); nb, ib = touches(ll <= bot + tol)
    for q in it:
        out.append(_marker(a + q, h[a + q], "▼", COL["ranging"]))
    for q in ib:
        out.append(_marker(a + q, l[a + q], "▲", COL["ranging"]))
    at = np.asarray(D["atr"], dtype=float)
    ra = float(at[k] / max(at[a - 120:a].mean(), 1e-12)); rv = float(v[a:k + 1].mean() / max(v[a - 300:a].mean(), 1e-9))
    inside = not (level >= top - tol if side > 0 else level <= bot + tol)
    out.append(_note(f"top touched {nt}x, bottom {nb}x (need 2 each) · ATR {ra:.2f}x its average before the box (limit {_val(M, 'InpUhvBoxAtr'):g}) · "
                     f"volume {rv:.2f}x the average before (limit {_val(M, 'InpUhvBoxVol'):g}) · level {'INSIDE' if inside else 'at the edge / outside'} the box"))
    return out


def _span_overlay(M, D, tr, nkey, label, col):
    C = F._prep(D); h, l = C["h"], C["l"]
    k = tr["k"]; N = max(2, int(_val(M, nkey))); a = max(0, k - N + 1)
    _chk(k, a, k)
    top, bot = float(h[a:k + 1].max()), float(l[a:k + 1].min())
    atr = tr["atr"]
    return [_box(a, k, top, bot, col, f"{label}: {N} candles span {(top - bot) / PIP:.1f} pips = {(top - bot) / max(atr, 1e-12):.2f} ATR")], top, bot


def _ov_range(M, D, tr):
    out, top, bot = _span_overlay(M, D, tr, "InpUhvRangeBars", "range", COL["ranging"])
    out.append(_note(f"range rule: skip when the span is below {_val(M, 'InpUhvRangeAtr'):g} ATR (ATR here {tr['atr'] / PIP:.2f} pips)"))
    return out


def _ov_minspan(M, D, tr):
    out, top, bot = _span_overlay(M, D, tr, "InpUhvMinSpanBars", "squeeze box", COL["ranging"])
    out.append(_note(f"short squeeze box: skip when the span is below {_val(M, 'InpUhvMinSpanAtr'):g} ATR"))
    return out


def _ov_span20(M, D, tr):
    out, top, bot = _span_overlay(M, D, tr, "InpUhvSpanBars", "swing", COL["ranging"])
    out.append(_note(f"wide swing: skip when the span is ABOVE {_val(M, 'InpUhvMaxSpan20Atr'):g} ATR"))
    return out


def _ov_pos(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side, level = tr["k"], tr["side"], tr["level"]
    N = max(3, int(_val(M, "InpUhvPosBars"))); a = k - N + 1
    _chk(k, a, k)
    hi, lo = float(h[a:k + 1].max()), float(l[a:k + 1].min())
    pos = (level - lo) / (hi - lo) if hi > lo else 0.5
    p2 = pos if side > 0 else 1 - pos
    return [_box(a, k, hi, lo, COL["ranging"], f"range {N} candles"), _hline(level, COL["ranging"], f"level at {p2 * 100:.0f}% from the trade's end"),
            _note(f"range position: the level sits {p2 * 100:.0f}% of the way from the {'bottom' if side > 0 else 'top'} of the range; skip below {_val(M, 'InpUhvMinPos') * 100:.0f}%")]


def _ov_er(M, D, tr):
    C = F._prep(D); c = C["c"]
    k = tr["k"]; N = max(3, int(_val(M, "InpUhvErNBars")))
    _chk(k, k - N, k)
    er = _er(c, k, N)
    return [_line([(k - N, c[k - N]), (k, c[k])], COL["choppy"], f"net move over {N} closes"),
            _note(f"efficiency ratio {er:.2f} = net move / path of the last {N} closes (skip below {_val(M, 'InpUhvMinErN'):g})")]


def _ov_zrange(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side, level = tr["k"], tr["side"], tr["level"]
    nb = max(4, int(_val(M, "InpUhvZRangeBars"))); a = k - nb + 1
    _chk(k, a, k)
    hi, lo = float(h[a:k + 1].max()), float(l[a:k + 1].min())
    brk = (level > hi) if side > 0 else (level < lo)
    return [_box(a, k, hi, lo, COL["ranging"], f"zone box {nb} candles = {(hi - lo) / max(tr['atr'], 1e-12):.2f} ATR"),
            _note(f"zone box: a box narrower than {_val(M, 'InpUhvZRangeAtr'):g} ATR is risky unless the level breaks OUT of it ({'breaks out' if brk else 'inside'})")]


# ---- sr overlays
def _ov_major(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side, level = tr["k"], tr["side"], tr["level"]
    p = max(2, int(_val(M, "InpUhvSellSupPiv"))); m = max(1, int(_val(M, "InpUhvSellSupLast")))
    lows, highs = F._major_idx(D, p)
    idx = lows if side < 0 else highs
    j = int(np.searchsorted(idx, k - p, side="right"))
    sel = idx[max(0, j - m):j]; sel = sel[sel >= k - 720]
    x = _val(M, "InpUhvSellSup") if side < 0 else _val(M, "InpUhvBuyRes")
    out = []
    for q in sel:
        _chk(k, q)
        y = float(l[q]) if side < 0 else float(h[q])
        d = (level - y) / PIP if side < 0 else (y - level) / PIP
        out.append(_hline(y, COL["sr"], f"major swing {'low' if side < 0 else 'high'} {d:+.1f} pips {'below' if side < 0 else 'above'} the level"))
        out.append(_marker(q, y, "◆", COL["sr"]))
    out.append(_note(f"{'selling into support' if side < 0 else 'buying into resistance'}: the last {m} major swing {'low' if side < 0 else 'high'}{'s' if m > 1 else ''} "
                     f"({p} candles each side); skip when the level is 0..{x:g} pips {'above' if side < 0 else 'below'} one" if x > 0 else
                     f"into a major {'support' if side < 0 else 'resistance'}: off for {'sells' if side < 0 else 'buys'} (0)"))
    return out


def _ov_wall(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side, level = tr["k"], tr["side"], tr["level"]
    T, N = max(1, int(_val(M, "InpUhvWallTouches"))), max(10, int(_val(M, "InpUhvWallBars")))
    g = max(1.0, _val(M, "InpUhvWallFig")) * PIP
    x = _val(M, "InpUhvWall")
    a = k - N + 1; _chk(k, a, k)
    ext = h[a:k + 1] if side > 0 else l[a:k + 1]
    out = []
    # every round figure within 5 pips ahead of the level: its touches (the rule needs >= T touches and 0..x pips ahead)
    f0 = np.ceil(level / g) * g if side > 0 else np.floor(level / g) * g
    for i in range(0, 3):
        cc = f0 + side * i * g
        d = (cc - level) / PIP if side > 0 else (level - cc) / PIP
        if d > max(5.0, x + 1):
            break
        touched = np.flatnonzero(np.abs(ext - cc) <= 0.5e-4)
        out.append(_hline(cc, COL["sr"], f"round figure {cc:.5f}: {len(touched)} touches, {d:.1f} pips ahead"))
        for q in touched[:12]:
            out.append(_marker(a + int(q), ext[int(q)], "•", COL["sr"]))
    out.append(_note(f"wall: a round figure (every {g / PIP:g} pips) touched >= {T} times in {N} candles, lying 0..{x:g} pips ahead of the level"))
    return out


def _ov_srpips(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side, px = tr["k"], tr["side"], tr["px"]
    n = max(2, int(_val(M, "InpUhvSRLook"))); a = k - n + 1; _chk(k, a, k)
    lo, hi = float(l[a:k + 1].min()), float(h[a:k + 1].max())
    y = lo if side < 0 else hi
    d = (px - lo) / PIP if side < 0 else (hi - px) / PIP
    return [_hline(y, COL["sr"], f"{n}-candle {'low' if side < 0 else 'high'}: {d:.1f} pips {'below' if side < 0 else 'above'} the entry"),
            _note(f"S/R pips: skip when the entry is within {_val(M, 'InpUhvSRPips'):g} pips of it")]


def _ov_srahead(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side, level, ku = tr["k"], tr["side"], tr["level"], tr.get("ku")
    look = max(5, int(_val(M, "InpUhvSRAheadLook"))); x = _val(M, "InpUhvSRAhead")
    last = C["lastL"] if side < 0 else C["lastH"]
    out, best = [], None
    for j in F._swings(last, k, 12):
        _chk(k, j)
        if j < k - look or (ku is not None and j >= ku):
            continue
        y = float(l[j]) if side < 0 else float(h[j])
        d = (level - y) / PIP if side < 0 else (y - level) / PIP
        out.append(_marker(j, y, "◇", COL["sr"]))
        if d >= 0 and (best is None or d < best[0]):
            best = (d, y)
    if best:
        out.append(_hline(best[1], COL["sr"], f"nearest swing beyond the level: {best[0]:.1f} pips ahead"))
    out.append(_note(f"S/R just ahead: a swing (before the UHV, last {look} candles) 0..{x:g} pips beyond the level"))
    return out


def _ov_bigfig(M, D, tr):
    side, level = tr["side"], tr["level"]
    g = max(1.0, _val(M, "InpUhvFigStep")) * PIP
    fig = np.ceil(level / g - 1e-9) * g if side > 0 else np.floor(level / g + 1e-9) * g
    d = (fig - level) / PIP if side > 0 else (level - fig) / PIP
    return [_hline(fig, COL["sr"], f"round figure {fig:.5f}: {d:.1f} pips ahead"), _note(f"big figure: skip when a round figure (every {g / PIP:g} pips) is 0..{_val(M, 'InpUhvBigFig'):g} pips beyond the level")]


# ---- trend overlays
def _ov_v2(M, D, tr):
    k, side = tr["k"], tr["side"]
    p = max(1, int(_val(M, "InpUhvV2Piv"))); nohh, back = _val(M, "InpUhvV2NoHH"), _val(M, "InpUhvV2Back")
    t, flip, brk, sh, sl = _v2_state(D, k, p)
    v2 = F.v2_trend(D, k, p, nohh, back)
    out = []
    for i, y in sh[-5:]:
        _chk(k, i); out.append(_marker(i, y, "H", COL["trend"]))
    for i, y in sl[-5:]:
        _chk(k, i); out.append(_marker(i, y, "L", COL["trend"]))
    if flip >= 0:
        _chk(k, flip)
        out.append(_vline(flip, COL["trend"], f"flip to {'up' if t > 0 else 'down'}"))
        out.append(_hline(brk, COL["trend"], "the broken swing"))
    name = {1: "UP", -1: "DOWN", 0: "RANGING"}[v2]
    raw = {1: "up", -1: "down", 0: "none"}[t]
    why = "" if v2 == t else f" (break-of-structure says {raw}, but no new extreme beyond the broken swing / price back at the last swing → ranging)"
    m = int(_val(M, "InpUhvV2Against"))
    out.append(_note(f"camel v2 trend at the entry: {name}{why} · the trade is a {'BUY' if side > 0 else 'SELL'} · "
                     + ("mode 1: skip against the trend" if m == 1 else "mode 2: only WITH a confirmed trend" if m == 2 else "off (0)")))
    return out


def _ov_shift_ema(M, D, tr):
    k, side = tr["k"], tr["side"]
    fast, slow = int(_val(M, "InpUhvShiftEmaFast")), int(_val(M, "InpUhvShiftEmaSlow"))
    ef, es, sk, sd = F._shift_arrays(D, fast, slow)
    a = max(0, k - 80); _chk(k, a, k)
    out = [_line([(j, ef[j]) for j in range(a, k + 1)], COL["trend"], f"EMA {fast}"), _line([(j, es[j]) for j in range(a, k + 1)], COL["grey"], f"EMA {slow}")]
    sf, ss = (ef[k] - ef[k - 3]) / PIP, (es[k] - es[k - 3]) / PIP
    out.append(_note(f"EMA shift: over the last 3 candles EMA {fast} moved {sf:+.2f} pips and EMA {slow} {ss:+.2f} pips; skip when BOTH run against a {'buy' if side > 0 else 'sell'}"))
    return out


def _ov_shift_stoch(M, D, tr):
    k, side = tr["k"], tr["side"]
    fast, slow = int(_val(M, "InpUhvShiftEmaFast")), int(_val(M, "InpUhvShiftEmaSlow"))
    ef, es, sk, sd = F._shift_arrays(D, fast, slow)
    lv = _val(M, "InpUhvShiftStochLvl")
    _chk(k, k - 1, k)
    return [_note(f"Stochastic RSI: K {sk[k]:.0f} / D {sd[k]:.0f} now, K {sk[k - 1]:.0f} / D {sd[k - 1]:.0f} a candle ago; skip a sell when K crosses above D below {lv:g} "
                  f"(a buy: K crosses below D above {100 - lv:g})")]


def _ov_avwap(M, D, tr):
    C = F._prep(D); h, l, c, v = C["h"], C["l"], C["c"], C["v"]
    k, side = tr["k"], tr["side"]
    N = int(_val(M, "InpUhvShiftAvwap"))
    if N <= 0 or k < N + 5:
        return [_note("anchored VWAP: off (0)")]
    seg = slice(k - N + 1, k + 1)
    j = (k - N + 1) + (int(np.argmin(l[seg])) if side < 0 else int(np.argmax(h[seg])))
    _chk(k, j, k)
    vv = np.maximum(v[j:k + 1], 1.0)
    cum = np.cumsum(c[j:k + 1] * vv) / np.cumsum(vv)
    out = [_vline(j, COL["trend"], f"anchor: the {'low' if side < 0 else 'high'} of the last {N}"), _line([(j + i, cum[i]) for i in range(len(cum))], COL["trend"], "anchored VWAP")]
    out.append(_note(f"anchored VWAP {cum[-1]:.5f} vs close {c[k]:.5f}: price is on the {'RIGHT' if (c[k] - cum[-1]) * side >= 0 else 'WRONG'} side for a {'buy' if side > 0 else 'sell'}"
                     + (" (needs 5+ candles since the anchor)" if k - j < 5 else "")))
    return out


def _ov_nolh(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side = tr["k"], tr["side"]
    pp = max(1, int(_val(M, "InpUhvLhPiv"))); arr = h if side > 0 else l
    sw = []
    for i in range(max(pp, k - 300), k - pp + 1):
        win = arr[i - pp:i + pp + 1]
        if (side > 0 and arr[i] == win.max()) or (side < 0 and arr[i] == win.min()):
            sw.append(i)
    out = []
    for i in sw[-2:]:
        _chk(k, i + pp); out.append(_marker(i, arr[i], "H" if side > 0 else "L", COL["trend"]))
    if len(sw) >= 2:
        lower = (arr[sw[-1]] < arr[sw[-2]]) if side > 0 else (arr[sw[-1]] > arr[sw[-2]])
        out.append(_hline(arr[sw[-2]], COL["grey"], "previous swing")); out.append(_hline(arr[sw[-1]], COL["trend"], "last swing"))
        out.append(_note(f"{'lower high' if side > 0 else 'higher low'}: the last swing ({pp} candles each side) is {'LOWER' if lower and side > 0 else 'HIGHER' if lower else 'not'} "
                         f"{'than' if lower else 'against'} the one before → {'skip' if lower else 'fine'}"))
    else:
        out.append(_note("lower high: fewer than two swings in the last 300 candles"))
    return out


def _ov_struct(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side = tr["k"], tr["side"]
    hs, ls = F._swings(C["lastH"], k, 2), F._swings(C["lastL"], k, 2)
    out = []
    for j in hs:
        _chk(k, j + 1); out.append(_marker(j, h[j], "h", COL["trend"]))
    for j in ls:
        _chk(k, j + 1); out.append(_marker(j, l[j], "l", COL["trend"]))
    if len(hs) == 2 and len(ls) == 2:
        hh, hl = h[hs[1]] > h[hs[0]], l[ls[1]] > l[ls[0]]
        out.append(_note(f"structure (1-candle swings): {'higher' if hh else 'lower'} high, {'higher' if hl else 'lower'} low · a buy needs higher/higher, a sell lower/lower "
                         f"(mode {int(_val(M, 'InpUhvStruct'))}: {'both' if int(_val(M, 'InpUhvStruct')) == 1 else 'only the high / low' if int(_val(M, 'InpUhvStruct')) == 2 else 'off'})"))
    return out


def _ov_fresh(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side = tr["k"], tr["side"]
    x = max(1, int(_val(M, "InpUhvFreshBreak"))); nsw = max(1, int(_val(M, "InpUhvFreshSwings")))
    last = C["lastH"] if side < 0 else C["lastL"]
    sw = F._swings(last, k - x, nsw)
    out = [_box(k - x + 1, k, float(h[k - x + 1:k + 1].max()), float(l[k - x + 1:k + 1].min()), COL["trend"], f"last {x} candles")]
    for j in sw:
        _chk(k, j + 1); out.append(_marker(j, h[j] if side < 0 else l[j], "s", COL["trend"]))
    if len(sw) == nsw:
        ref = max(h[j] for j in sw) if side < 0 else min(l[j] for j in sw)
        out.append(_hline(ref, COL["trend"], f"the last {nsw} swing {'highs' if side < 0 else 'lows'}' extreme"))
        broke = (h[k - x + 1:k + 1].max() > ref) if side < 0 else (l[k - x + 1:k + 1].min() < ref)
        out.append(_note(f"fresh break: one of the last {x} candles {'BROKE' if broke else 'did not break'} it → {'an opposite trend has begun, skip' if broke else 'fine'}"))
    return out


def _ov_broke(M, D, tr):
    C = F._prep(D); h, l = C["h"], C["l"]
    k, side = tr["k"], tr["side"]
    x = max(1, int(_val(M, "InpUhvBrokeHighs"))); lk = max(1, int(_val(M, "InpUhvBrokeLook")))
    last = C["lastH"] if side < 0 else C["lastL"]
    sw = F._swings(last, k - lk, x)
    out = [_box(k - lk + 1, k, float(h[k - lk + 1:k + 1].max()), float(l[k - lk + 1:k + 1].min()), COL["trend"], f"last {lk} candles")]
    for j in sw:
        _chk(k, j + 1); out.append(_marker(j, h[j] if side < 0 else l[j], "s", COL["trend"]))
    if len(sw) == x:
        ref = max(h[j] for j in sw) if side < 0 else min(l[j] for j in sw)
        broke = (h[k - lk + 1:k + 1].max() > ref) if side < 0 else (l[k - lk + 1:k + 1].min() < ref)
        out.append(_hline(ref, COL["trend"], f"the previous {x} swing {'highs' if side < 0 else 'lows'}"))
        out.append(_note(f"broke highs: a candle in the last {lk} {'BROKE above' if broke and side < 0 else 'BROKE below' if broke else 'stayed inside'} them → {'skip' if broke else 'fine'}"))
    return out


def _ov_counter(M, D, tr):
    C = F._prep(D); c = C["c"]
    k, side = tr["k"], tr["side"]
    n = max(5, int(_val(M, "InpUhvCounterBars"))); _chk(k, k - n, k)
    mv = (c[k] - c[k - n]) * side / max(tr["atr"], 1e-12)
    return [_line([(k - n, c[k - n]), (k, c[k])], COL["trend"], f"{n}-candle move"),
            _note(f"counter-move: price moved {mv:+.1f} ATR {'with' if mv >= 0 else 'AGAINST'} the trade over {n} candles; skip beyond -{_val(M, 'InpUhvCounterAtr'):g} ATR")]


def _ov_htf5(M, D, tr):
    C = F._prep(D); c = C["c"]
    k, side = tr["k"], tr["side"]
    m = int(_val(M, "InpUhvHtf5")); n = max(3, int(_val(M, "InpUhvHtf5N")))
    end = int(C["end5"][k]); cnt = n if m != 2 else 3 * n
    if end - 5 * (cnt - 1) < 0:
        return [_note("5-minute trend: not enough history")]
    idx = [end - 5 * i for i in range(cnt)][::-1]; _chk(k, *idx)
    out = [_line([(j, c[j]) for j in idx], COL["trend"], "5-minute closes")]
    cl = c[idx]
    slope = np.polyfit(np.arange(cnt), cl, 1)[0] / PIP
    a = 2.0 / (n + 1); e = cl[0]
    for vv in cl[1:]:
        e = a * vv + (1 - a) * e
    out.append(_hline(e, COL["grey"], f"5-min EMA {n}"))
    out.append(_note(f"5-minute trend: slope {slope:+.2f} pips per candle over {n} closes; last 5-min close {'above' if cl[-1] > e else 'below'} its EMA {n} · mode {m} "
                     f"({'slope against = skip' if m == 1 else 'wrong side of the EMA = skip' if m == 2 else 'off'})"))
    return out


def _ov_wick(M, D, tr):
    C = F._prep(D); h, l, c = C["h"], C["l"], C["c"]
    k, side = tr["k"], tr["side"]
    nb = max(1, int(_val(M, "InpUhvWickBars")))
    lastx = C["lastH"] if side > 0 else C["lastL"]
    out, hit = [], None
    for q in range(k - nb + 1, k + 1):
        j = int(lastx[q - 1]) if q >= 1 else -1
        if j < 0:
            continue
        _chk(k, q, j + 1)
        y = h[j] if side > 0 else l[j]
        out.append(_hline(y, COL["grey"], f"last swing {'high' if side > 0 else 'low'} before candle {q - k}"))
        if (side > 0 and h[q] > y and c[q] < y) or (side < 0 and l[q] < y and c[q] > y):
            hit = q; out.append(_marker(q, h[q] if side > 0 else l[q], "wick", COL["trend"]))
    out.append(_note(f"wick fake-break: in the last {nb} candles a wick {'DID poke' if hit is not None else 'did not poke'} beyond the last swing and close back inside → {'skip' if hit is not None else 'fine'}"))
    return out


# ---- choppy overlays
def _ov_flips(M, D, tr):
    C = F._prep(D); c = C["c"]
    k = tr["k"]; nf = max(5, int(_val(M, "InpUhvFlipsBars"))); _chk(k, k - nf, k)
    dd = np.sign(np.diff(c[k - nf:k + 1]))
    fl = np.flatnonzero(dd[1:] * dd[:-1] < 0)
    share = float(len(fl)) / max(len(dd) - 1, 1)
    out = [_marker(k - nf + int(i) + 1, c[k - nf + int(i) + 1], "•", COL["choppy"]) for i in fl[-60:]]
    out.append(_note(f"choppy hour: the closes changed direction {len(fl)} times in {nf} candles = {share * 100:.0f}% of the time; skip above {_val(M, 'InpUhvMaxFlips60') * 100:.0f}%"))
    return out


def _ov_atr(M, D, tr):
    a = tr["atr"] / PIP
    return [_note(f"ATR at the entry {a:.2f} pips · dead tape below {_val(M, 'InpUhvMinAtrPips'):g}, too volatile above {_val(M, 'InpUhvMaxAtrPips'):g} (0 = off)")]


def _ov_ticks(M, D, tr):
    C = F._prep(D); v = C["v"]
    k = tr["k"]; _chk(k, k - 9, k)
    return [_note(f"dead market: the last 10 candles averaged {float(v[k - 9:k + 1].mean()):.0f} ticks; skip below {_val(M, 'InpUhvMinTicks'):g}")]


def _ov_volrel(M, D, tr):
    C = F._prep(D); v = C["v"]
    k = tr["k"]
    if k < 310:
        return [_note("dead volume: not enough history")]
    _chk(k, k - 309, k)
    r = float(v[k - 9:k + 1].mean()) / max(float(v[k - 309:k - 9].mean()), 1e-9)
    return [_note(f"dead volume: the last 10 candles' volume is {r:.2f}x the 300 before; skip below {_val(M, 'InpUhvMinVolRel'):g}")]


# ---- the rule texts (plain English, with the current values)
def _t_box(M):
    return (f"Quiet box: we look back {int(_val(M, 'InpUhvBoxBars'))} candles; if the top and the bottom of that range were each touched at least twice "
            f"(within 15% of the box height, touches 3+ candles apart), the ATR is below {_val(M, 'InpUhvBoxAtr'):g}x its average over the 120 candles before the box "
            f"and the box's volume is below {_val(M, 'InpUhvBoxVol'):g}x the 300 candles before it, and the UHV level sits INSIDE the box, we skip. "
            f"Breaking OUT of the box (the level in the top 15% for a buy, bottom 15% for a sell) is allowed.")


def _t_range(M):
    return f"Range: when the last {int(_val(M, 'InpUhvRangeBars'))} candles (high to low) span less than {_val(M, 'InpUhvRangeAtr'):g} ATR, we skip."


def _t_er(M):
    return (f"Efficiency ratio: the net move of the last {int(_val(M, 'InpUhvErNBars'))} closes divided by the path they walked; below {_val(M, 'InpUhvMinErN'):g} the tape is going "
            f"nowhere and we skip.")


def _t_minspan(M):
    return f"Short squeeze box: when the last {int(_val(M, 'InpUhvMinSpanBars'))} candles span less than {_val(M, 'InpUhvMinSpanAtr'):g} ATR, we skip."


def _t_span20(M):
    return f"Wide swing: when the last {int(_val(M, 'InpUhvSpanBars'))} candles span MORE than {_val(M, 'InpUhvMaxSpan20Atr'):g} ATR (a wild, swinging range), we skip."


def _t_pos(M):
    return (f"Range position: where the level sits in the last {int(_val(M, 'InpUhvPosBars'))} candles' range - a buy from the bottom part (below {_val(M, 'InpUhvMinPos') * 100:.0f}% "
            f"of the way up) or a sell from the top part is 'breaking from the wrong end' and we skip.")


def _t_zrange(M):
    return (f"Zone box (Zee's zone model): the last {int(_val(M, 'InpUhvZRangeBars'))} candles narrower than {_val(M, 'InpUhvZRangeAtr'):g} ATR is a risky pocket; a level breaking OUT of "
            f"the box in its own direction is allowed. Acts only with the Risk Manager in mode 4 (skip risky zones; mode 3 marks the zone but does not skip) - set InpUhvRiskMgr on the main page, "
            f"the lab never changes it.")


def _t_major(M):
    return (f"Major swings: swing lows / highs with {int(_val(M, 'InpUhvSellSupPiv'))} candles each side, the last {int(_val(M, 'InpUhvSellSupLast'))} of them within 720 candles. "
            f"A sell whose level is 0..{_val(M, 'InpUhvSellSup'):g} pips above a major low is selling into support; a buy 0..{_val(M, 'InpUhvBuyRes'):g} pips below a major high is "
            f"buying into resistance (0 = that side off).")


def _t_wall(M):
    return (f"Round-figure wall: a price within 1 pip of a round figure (every {_val(M, 'InpUhvWallFig'):g} pips) that the highs (buy) / lows (sell) touched at least "
            f"{int(_val(M, 'InpUhvWallTouches'))} times in the last {int(_val(M, 'InpUhvWallBars'))} candles, lying 0..{_val(M, 'InpUhvWall'):g} pips ahead of the level - a tested wall, we skip.")


def _t_srpips(M):
    return (f"S/R pips: the lowest low (sell) / highest high (buy) of the last {int(_val(M, 'InpUhvSRLook'))} candles; an entry within {_val(M, 'InpUhvSRPips'):g} pips of it "
            f"is right at the level and we skip.")


def _t_srahead(M):
    return (f"S/R just ahead: a 1-candle swing from before the UHV, in the last {int(_val(M, 'InpUhvSRAheadLook'))} candles, sitting 0..{_val(M, 'InpUhvSRAhead'):g} pips "
            f"beyond the level (above for a buy, below for a sell) - the move would run straight into it, we skip.")


def _t_bigfig(M):
    return f"Big figure: a round figure (every {_val(M, 'InpUhvFigStep'):g} pips) 0..{_val(M, 'InpUhvBigFig'):g} pips beyond the level - we skip."


def _t_v2(M):
    m = int(_val(M, "InpUhvV2Against"))
    return (f"Camel v2 trend (tuned to Zee's 60 blind labels): swings of {int(_val(M, 'InpUhvV2Piv'))} candles each side; the trend flips only when a CLOSE passes the last "
            f"swing high (up) / low (down). It is 'ranging' while price has not gone {_val(M, 'InpUhvV2NoHH'):g} pips beyond the broken swing, or when the close is back within "
            f"{_val(M, 'InpUhvV2Back'):g} pips of the last swing low (uptrend) / high (downtrend). "
            + ("Mode 1: a trade AGAINST the trend is skipped." if m == 1 else "Mode 2: only a trade WITH a confirmed trend is taken (ranging = skip)." if m == 2 else "Off (0)."))


def _t_shift_ema(M):
    return (f"EMA shift: EMA {int(_val(M, 'InpUhvShiftEmaFast'))} and EMA {int(_val(M, 'InpUhvShiftEmaSlow'))} of the closes; when BOTH moved against the trade over the last "
            f"3 candles the trend has shifted and we skip.")


def _t_shift_stoch(M):
    lv = _val(M, "InpUhvShiftStochLvl")
    return (f"Stochastic RSI (RSI 14, stoch 14, K 3, D 3): a sell is skipped when K just crossed above D below {lv:g} (coming out of oversold); a buy when K crossed "
            f"below D above {100 - lv:g}.")


def _t_avwap(M):
    return (f"Anchored VWAP: the volume-weighted average price since the extreme (lowest low for a sell, highest high for a buy) of the last {int(_val(M, 'InpUhvShiftAvwap'))} candles; "
            f"a close on the wrong side of it (above for a sell, below for a buy) means the move has reversed, we skip (needs 5+ candles since the anchor).")


def _t_nolh(M):
    return f"Lower high: swings of {int(_val(M, 'InpUhvLhPiv'))} candles each side in the last 300; a buy after a LOWER high (a sell after a HIGHER low) is skipped."


def _t_struct(M):
    m = int(_val(M, "InpUhvStruct"))
    return ("Structure: the last two 1-candle swing highs and lows; " + ("a buy needs a higher high AND a higher low (a sell: lower low AND lower high)." if m == 1 else
            "a buy needs a higher high (a sell: a lower low)." if m == 2 else "off (0): 1 = higher high AND higher low needed, 2 = only the higher high."))


def _t_fresh(M):
    return (f"Fresh break: when one of the last {int(_val(M, 'InpUhvFreshBreak'))} candles broke above the last {int(_val(M, 'InpUhvFreshSwings'))} swing highs before it, an uptrend "
            f"has just begun and a sell is skipped (buys mirror with swing lows).")


def _t_broke(M):
    return (f"Broke highs: a candle in the last {int(_val(M, 'InpUhvBrokeLook'))} candles made a high above the previous {int(_val(M, 'InpUhvBrokeHighs'))} swing highs - a sell is "
            f"skipped (buys mirror).")


def _t_counter(M):
    return f"Counter-move: when the close moved more than {_val(M, 'InpUhvCounterAtr'):g} ATR AGAINST the trade over the last {int(_val(M, 'InpUhvCounterBars'))} candles, we skip."


def _t_htf5(M):
    m = int(_val(M, "InpUhvHtf5"))
    return (f"5-minute trend: the last {int(_val(M, 'InpUhvHtf5N'))} five-minute closes; " + ("mode 1: skip when their slope runs against the trade." if m == 1 else
            "mode 2: skip when the last 5-minute close is on the wrong side of their EMA." if m == 2 else "off (0): 1 = slope against, 2 = wrong side of the EMA."))


def _t_wick(M):
    return (f"Wick fake-break: one of the last {int(_val(M, 'InpUhvWickBars'))} candles poked beyond the last 1-candle swing high (buy) / low (sell) with its wick and closed "
            f"back inside - the break already failed once, we skip.")


def _t_flips(M):
    return (f"Choppy hour: the share of the last {int(_val(M, 'InpUhvFlipsBars'))} candles whose close changed direction (up after down, down after up); above "
            f"{_val(M, 'InpUhvMaxFlips60') * 100:.0f}% the tape is flipping every other candle and we skip (Zee's 'ranging' losses, x2.4 / x2.8 by half).")


def _t_minatr(M):
    return f"Dead tape: when the ATR at the entry is below {_val(M, 'InpUhvMinAtrPips'):g} pips, we skip."


def _t_maxatr(M):
    return f"Too volatile: when the ATR at the entry is above {_val(M, 'InpUhvMaxAtrPips'):g} pips, we skip (Zee's 'no reason visible' losses)."


def _t_ticks(M):
    return f"Dead market: when the last 10 candles averaged fewer than {_val(M, 'InpUhvMinTicks'):g} ticks, we skip."


def _t_volrel(M):
    return f"Dead volume: when the last 10 candles' volume is below {_val(M, 'InpUhvMinVolRel'):g}x the 300 candles before, we skip."


_SHIFT_KEYS = ["InpUhvShiftEmaFast", "InpUhvShiftEmaSlow"]
R_RANGING = [
    _r("quiet box", "box", "InpUhvBoxInside", ["InpUhvBoxInside", "InpUhvBoxBars", "InpUhvBoxAtr", "InpUhvBoxVol"], _t_box, _ov_box),
    _r("range (N candles < A ATR)", "skip", "InpUhvRangeAtr", ["InpUhvRangeAtr", "InpUhvRangeBars"], _t_range, _ov_range),
    _r("efficiency ratio", "skip", "InpUhvMinErN", ["InpUhvMinErN", "InpUhvErNBars"], _t_er, _ov_er),
    _r("short squeeze box", "skip", "InpUhvMinSpanAtr", ["InpUhvMinSpanAtr", "InpUhvMinSpanBars"], _t_minspan, _ov_minspan),
    _r("wide swing", "skip", "InpUhvMaxSpan20Atr", ["InpUhvMaxSpan20Atr", "InpUhvSpanBars"], _t_span20, _ov_span20),
    _r("range position", "skip", "InpUhvMinPos", ["InpUhvMinPos", "InpUhvPosBars"], _t_pos, _ov_pos),
    _r("zone box", "zone", "InpUhvZRange", ["InpUhvZRange", "InpUhvZRangeBars", "InpUhvZRangeAtr"], _t_zrange, _ov_zrange),
]
R_SR = [
    _r("major support / resistance", "major", "InpUhvSellSup", ["InpUhvSellSup", "InpUhvBuyRes", "InpUhvSellSupPiv", "InpUhvSellSupLast"], _t_major, _ov_major,
       on=lambda M: _val(M, "InpUhvSellSup") > 0 or _val(M, "InpUhvBuyRes") > 0),
    _r("round-figure wall", "wall", "InpUhvWall", ["InpUhvWall", "InpUhvWallTouches", "InpUhvWallBars", "InpUhvWallFig"], _t_wall, _ov_wall),
    _r("S/R pips", "skip", "InpUhvSRPips", ["InpUhvSRPips", "InpUhvSRLook"], _t_srpips, _ov_srpips),
    _r("S/R just ahead", "skip", "InpUhvSRAhead", ["InpUhvSRAhead", "InpUhvSRAheadLook"], _t_srahead, _ov_srahead),
    _r("big figure", "skip", "InpUhvBigFig", ["InpUhvBigFig", "InpUhvFigStep"], _t_bigfig, _ov_bigfig),
]
R_TREND = [
    _r("camel v2 trend", "skip", "InpUhvV2Against", ["InpUhvV2Against", "InpUhvV2Piv", "InpUhvV2NoHH", "InpUhvV2Back"], _t_v2, _ov_v2),
    _r("EMA shift", "skip", "InpUhvShiftEma", ["InpUhvShiftEma"] + _SHIFT_KEYS, _t_shift_ema, _ov_shift_ema),
    _r("Stochastic RSI cross", "skip", "InpUhvShiftStoch", ["InpUhvShiftStoch", "InpUhvShiftStochLvl"] + _SHIFT_KEYS, _t_shift_stoch, _ov_shift_stoch),
    _r("anchored VWAP", "skip", "InpUhvShiftAvwap", ["InpUhvShiftAvwap"], _t_avwap, _ov_avwap),
    _r("lower high / higher low", "skip", "InpUhvNoLowerHigh", ["InpUhvNoLowerHigh", "InpUhvLhPiv"], _t_nolh, _ov_nolh),
    _r("structure", "skip", "InpUhvStruct", ["InpUhvStruct"], _t_struct, _ov_struct),
    _r("fresh break", "skip", "InpUhvFreshBreak", ["InpUhvFreshBreak", "InpUhvFreshSwings"], _t_fresh, _ov_fresh),
    _r("broke highs", "skip", "InpUhvBrokeHighs", ["InpUhvBrokeHighs", "InpUhvBrokeLook"], _t_broke, _ov_broke),
    _r("counter-move", "skip", "InpUhvCounterAtr", ["InpUhvCounterAtr", "InpUhvCounterBars"], _t_counter, _ov_counter),
    _r("5-minute trend", "skip", "InpUhvHtf5", ["InpUhvHtf5", "InpUhvHtf5N"], _t_htf5, _ov_htf5),
    _r("wick fake-break", "skip", "InpUhvWickFake", ["InpUhvWickFake", "InpUhvWickBars"], _t_wick, _ov_wick),
]
R_CHOPPY = [
    _r("direction flips", "skip", "InpUhvMaxFlips60", ["InpUhvMaxFlips60", "InpUhvFlipsBars"], _t_flips, _ov_flips),
    _r("dead tape (ATR too low)", "skip", "InpUhvMinAtrPips", ["InpUhvMinAtrPips"], _t_minatr, _ov_atr),
    _r("too volatile (ATR too high)", "skip", "InpUhvMaxAtrPips", ["InpUhvMaxAtrPips"], _t_maxatr, _ov_atr),
    _r("efficiency ratio", "skip", "InpUhvMinErN", ["InpUhvMinErN", "InpUhvErNBars"], _t_er, _ov_er),
    _r("dead market (ticks)", "skip", "InpUhvMinTicks", ["InpUhvMinTicks"], _t_ticks, _ov_ticks),
    _r("dead volume", "skip", "InpUhvMinVolRel", ["InpUhvMinVolRel"], _t_volrel, _ov_volrel),
]

DETECTORS = {
    "ranging": {"title": "Ranging market", "emoji": "📦", "rules": R_RANGING,
                "yes": r"ranging|sideways|range box|\brange\b|going nowhere|consolidat",
                "no": r"(not|no|isn'?t|wasn'?t|never|hardly)\s+(really\s+|a\s+|in\s+a\s+)?(ranging|range|sideways)",
                "intro": "A ranging market: price going sideways between a top and a bottom, so a breakout inside it has nowhere to go. Zee's words: "
                         "\"from 1257 am till 4:37 price is ranging sideways .. we bought right inside a ranging market.\" Below, how the engine detects it right now."},
    "sr": {"title": "Support / resistance", "emoji": "🧱", "rules": R_SR,
           "yes": r"resistance|support|top here|low here|cannot break|can'?t break|\bwall\b|round (number|figure)|triple top|double top|double bottom",
           "no": r"(not|no|isn'?t|wasn'?t|never)\s+(a\s+|at\s+|near\s+|any\s+)?(resistance|support|level)",
           "intro": "A support or resistance right ahead of the entry: a major swing, a tested round figure, a level price could not break. Zee's words: "
                    "\"price has capped at a bottom and cannot break below 1.15016\". Below, how the engine detects it right now."},
    "trend": {"title": "Trend shift / against the trend", "emoji": "🔀", "rules": R_TREND,
              "yes": r"sold in an? uptrend|bought in an? downtrend|against the trend|trend (no longer holds|shifted|ended)|lower high|higher low|last (low|high) .*broken",
              "no": r"(not|no|isn'?t|wasn'?t|never)\s+(really\s+|an?\s+)?(against|reversal|trend shift|uptrend|downtrend)",
              "intro": "Trading against the trend, or just as the trend shifts: a sell while price is making higher highs, a buy after a lower high, the EMAs rolling over. "
                       "Zee's words: \"price is going up from 1114 till 1241pm .. so we sold in an uptrend.\" Below, how the engine detects it right now."},
    "choppy": {"title": "Choppy tape", "emoji": "🌊", "rules": R_CHOPPY,
               "yes": r"\bchop|choppy|flip|whipsaw|jittery|noisy|dead|no volume",
               "no": r"(not|no|isn'?t|wasn'?t|never)\s+(really\s+|that\s+)?(chop|choppy|flipping)",
               "intro": "A choppy tape: closes flipping direction every other candle, a dead or a wild ATR, no efficiency in the move, no volume. Below, how the engine "
                        "detects it right now (the 'choppy hour' filter is InpUhvMaxFlips60)."},
}


def _rules(det):
    if det not in DETECTORS:
        raise KeyError(f"unknown detector {det!r}; one of {list(DETECTORS)}")
    return DETECTORS[det]["rules"]


def _is_on(M, rule):
    on = bool(rule["on"](M)) if rule["on"] else _on_default(M, rule)
    return on and _avail(M, rule)


def _det_keys(det):
    out = []
    for r in _rules(det):
        for k in r["keys"]:
            if k not in out:
                out.append(k)
    return out


# ====================================================================================================== describe
def describe(det, inputs, gate=None):
    """gate = trades()['gate']: {rm, n, n_skip} - how many of the setting's trades the skip-type rules can act on under its Risk Manager mode"""
    M = _merged(inputs)
    d = DETECTORS[det]
    rules, how = [], [d["intro"]]
    on_txt, off_txt = [], []
    rm = _rm(M)
    for r in _rules(det):
        on = _is_on(M, r)
        txt = r["text"](M)
        if not _avail(M, r):
            txt += f" ⛔ Not available in this setting: needs InpUhvRiskMgr 4 (now {rm}) - set it on the main page; the lab never changes it."
        rules.append({"name": r["name"], "inputs": list(r["keys"]), "text": txt, "on": on, "available": _avail(M, r)})
        (on_txt if on else off_txt).append((r["name"], txt))
    def _bullet(n, t):                                          # the rule text starts with its own name ("Quiet box: ...") - say it once
        head, _, rest = t.partition(":")
        return f"• {n}: {rest.strip()}" if head.strip().lower().replace("-", " ") == n.lower().replace("-", " ") and rest else f"• {n}: {t}"
    if on_txt:
        how.append("ON in this setting:")
        how += [_bullet(n, t) for n, t in on_txt]
    else:
        how.append("No sub-rule of this detector is on in this setting - the engine does not look for it at all right now.")
    if off_txt:
        how.append("Available but OFF (0): " + ", ".join(n for n, _ in off_txt) + ". Turn one on with its slider to see what it would do.")
    if rm in (1, 2, 3, 4):                                       # the engine runs skip() only `if lf_on and not sec` (uhv_engine.simulate)
        where = "OUTSIDE the Risk Manager's secure zone" if rm in (1, 2) else "INSIDE one of Zee's risky zones"
        g = f" - here on {gate['n_skip']} of the setting's {gate['n']} trades" if gate and gate.get("n") else ""
        how.append(f"Risk Manager mode {rm}: the engine applies the skip-type rules (range, efficiency ratio, flips, ATR bands, camel v2, EMA shift, S/R pips, "
                   f"big figure, ...) only to a trade {where}{g}; the other trades cannot be removed by those rules whatever the sliders say, and the lab counts "
                   f"them the same way." + (" Mode 2 takes only secure trades, so NO skip-type rule can act in this setting." if rm == 2 else
                                             " Mode 4 takes only trades outside the risky zones, so NO skip-type rule can act in this setting." if rm == 4 else ""))
    how.append("Every rule reads only the candles closed BEFORE the entry (never the entry candle or anything after it). The lab's verdicts come from the engine's own "
               "functions, so what fires here is exactly what the tester would skip. All counts are tester estimates (Python) - a hypothesis until MT5 confirms it.")
    params = []
    for key in _det_keys(det):
        spec = P[key]
        cur = _val(M, key)
        params.append({"key": key, "label": spec["label"], "type": spec["type"], "min": spec.get("min"), "max": spec.get("max"), "step": spec.get("step"),
                       "options": spec.get("options"), "value": cur, "comment": F.DEFAULTS[key][1], "grid": spec.get("grid")})
    return {"key": det, "title": d["title"], "emoji": d["emoji"], "how": how, "rules": rules, "params": params,
            "current": {k: _val(M, k) for k in _det_keys(det)}}


# ====================================================================================================== the setting's trades (cached)
def _setting(setting_file):
    p = Path(setting_file)
    if not p.is_absolute():
        p = SAVED / p if not str(p).startswith("settings") else HERE / p
    if p.suffix.lower() != ".json":
        # APPEND the extension, never replace: Zee's save "2026-11-07 12-09-37 + 1221at 99.84" has suffix ".84", and
        # with_suffix() turned it into "... 99.json" -> FileNotFoundError -> "server error" on the Detector Lab (2026-11-08 11:37)
        p = p.with_name(p.name + ".json")
    rec = json.loads(p.read_text(encoding="utf-8"))
    return p, rec


def _src_sig(inputs):
    """what the cached trade list depends on besides the inputs: the engine / filter code, the setups file this setting uses and the candles /
    ticks - their mtimes (review 2026-11-08: a cache keyed on the inputs alone kept a stale 'base' when uhv_setups.json or the engine changed)"""
    files = [HERE / n for n in ("uhv_engine.py", "uhv_filters.py", "uhv_ttd.py", "uhv_diamond.py", "uhv_ticks.py", "sim.py")]
    files += [SIMDATA / "year1.npz", SIMDATA / "uhv_ticks_all.npz"]
    try:
        import uhv_ticks
        files.append(Path(uhv_ticks.TICKS))
    except Exception:  # noqa: BLE001
        pass
    try:
        files.append(U.det_file(inputs))
    except Exception:  # noqa: BLE001 - trades() will raise the real error
        pass
    return [(f.name, int(f.stat().st_mtime)) for f in files if f.exists()]


def _hash(p, inputs):
    s = json.dumps({"file": p.name, "inputs": {k: str(v) for k, v in sorted(inputs.items())}, "src": _src_sig(inputs), "v": 4}, sort_keys=True)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


_TR = {}
_BUILD = {}                                                      # {hash: threading.Event} - one engine run per dataset, the other callers wait


def _comments():
    out = []
    try:
        for x in json.loads(LOSSES_1209.read_text(encoding="utf-8")):
            if x.get("comment"):
                out.append((1 if x["side"] == "B" else -1, float(x["te"]), x["comment"]))
    except (OSError, ValueError, KeyError):
        pass
    try:
        for key, x in json.loads(LOSS_COMMENTS.read_text(encoding="utf-8")).items():
            t = x.get("trade") or {}
            if x.get("comment") and t.get("entry_time") is not None:
                out.append((int(t.get("side") or (1 if key.startswith("B") else -1)), float(t["entry_time"]), x["comment"]))
    except (OSError, ValueError, KeyError):
        pass
    return out


def _comment_for(side, t_in, comments):
    best = None
    for s, te, c in comments:
        if s == side and abs(te - t_in) <= 60:
            if best is None or abs(te - t_in) < best[0]:
                best = (abs(te - t_in), c)
    return best[1] if best else ""


def trades(setting_file, inputs=None, progress=None):
    """every trade of the setting with what the detectors need at the entry (k = the last closed candle before it) - the engine run, cached.
    One build per dataset: a second caller (a reload, a second tab) waits for the first instead of running the engine again."""
    p, rec = _setting(setting_file)
    inputs = inputs if inputs is not None else rec["inputs"]
    hsh = _hash(p, inputs)
    with _LOCK:
        if hsh in _TR:
            return _TR[hsh]
        ev = _BUILD.get(hsh)
        mine = ev is None
        if mine:
            ev = _BUILD[hsh] = threading.Event()
    if not mine:
        if progress:
            progress("waiting for the engine run already in progress")
        ev.wait()
        with _LOCK:
            hit = _TR.get(hsh)
        return hit if hit is not None else trades(setting_file, inputs, progress)      # the other build failed: try ourselves
    try:
        return _build_trades(p, rec, inputs, hsh, progress)
    finally:
        with _LOCK:
            _BUILD.pop(hsh, None)
        ev.set()


def _build_trades(p, rec, inputs, hsh, progress):
    cache = SIMDATA / f"detlab_{hsh}.json"
    if cache.exists():
        try:
            out = json.loads(cache.read_text(encoding="utf-8"))
            with _LOCK:
                _TR[hsh] = out
            return out
        except ValueError:
            pass
    t0 = time.time()
    if progress:
        progress("running the engine")
    tr, su, cnt = U.simulate(inputs)
    R = tr[tr[:, 10] == 0] if len(tr) else tr
    dfile = U.det_file(inputs)
    instant = int(fv(inputs, "InpUhvEntry", 1)) == 1
    import uhv_ttd
    ttd = uhv_ttd.fv(inputs, "InpTtdOn") > 0.5
    S, TK = U._setups(dfile)
    if instant:
        S = U._instant_setups(TK, (uhv_ttd.fv(inputs, "InpTtd_uPBD") - uhv_ttd.fv(inputs, "InpTtd_uPBsD")) if ttd else fv(inputs, "InpUhvPreBreak"), dfile)
    st = np.array([s["t"] for s in S], dtype=float)
    D = _D()
    t1 = np.asarray(D["t1"], dtype=np.int64)
    c1, atr = np.asarray(D["c1"], dtype=float), np.asarray(D["atr"], dtype=float)
    N = len(t1)
    comments = _comments()
    rm = int(fv(inputs, "InpUhvRiskMgr"))
    rows = []
    for x in R:
        side, tin = int(x[0]), float(x[1])
        j = int(np.searchsorted(st, tin + 1e-6)) - 1
        s = S[j] if 0 <= j < len(S) and tin - S[j]["t"] < 30 else None
        if s is None:
            continue
        bar_t = s["bar"] - 60 if instant else s["t"] - 60
        k = int(np.searchsorted(t1, bar_t))
        if k >= N or t1[k] != bar_t or k < 450 or k + N_AFTER + 1 >= N:
            continue
        ku = int(np.searchsorted(t1, s["uhv_t"]))
        if rm in (1, 2):                                            # the Risk Manager's verdict, exactly as uhv_engine.simulate computes it:
            sec = bool(F.secure(fv, inputs, D, side, k))             # sec -> the engine never calls skip() on this trade
        elif rm in (3, 4):
            sec = F.risky_zone(fv, inputs, D, side, k, float(s["level"]), float(s["t"])) is None
        else:
            sec = False
        rows.append({"id": f"{_utc(tin):%y%m%d-%H%M%S}-{'B' if side > 0 else 'S'}", "side": side, "k": k, "kb": k + 1, "ku": ku, "level": float(s["level"]),
                     "sec": sec,
                     "extreme": float(s["extreme"]), "px": float(s["level"]) if instant else float(c1[k]), "atr": float(atr[k]), "ts": float(s["t"]),
                     "uv": float(s.get("uv") or 0.0), "bv": (int(s["bv"]) if instant and s.get("bv") is not None else None),
                     "bc": (float(s["bc"]) if instant and "bc" in s else None), "t_in": tin, "fill": float(x[2]), "stop": float(x[3]), "t_out": float(x[4]),
                     "exit": float(x[5]), "pnl": float(x[6]), "win": bool(x[6] > 0), "comment": _comment_for(side, tin, comments)})
    days = len(np.unique(t1 // 86400))
    wins = sum(1 for r in rows if r["win"]); losses = len(rows) - wins
    _migrate_label_ids(rows)
    out = {"file": p.name, "name": rec.get("name") or p.stem, "hash": hsh, "secs": round(time.time() - t0, 1), "n_rows": int(len(R)),
           "gate": {"rm": rm, "n": len(rows), "n_skip": sum(1 for r in rows if not r["sec"])},
           "base": {"trades": len(rows), "losses": losses, "wins": wins, "wr": round(100.0 * wins / max(len(rows), 1), 2), "per_day": round(len(rows) / max(days, 1), 2),
                    "net": round(float(sum(r["pnl"] for r in rows)), 2), "days": int(days)},
           "trades": rows}
    SIMDATA.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, cache)
    with _LOCK:
        _TR[hsh] = out
    return out


def _bars(D, k):
    a, b = k - N_BEFORE + 1, k + N_AFTER + 1
    out = {}
    for key, col in (("t", "t1"), ("o", "o1"), ("h", "h1"), ("l", "l1"), ("c", "c1"), ("v", "v1")):
        arr = np.asarray(D[col][a:b])
        out[key] = [int(x) for x in arr] if key in ("t", "v") else [round(float(x), 5) for x in arr]
    return out


def _zee_says(det, comment):
    """a GUESS from Zee's comment: 'yes' only when it names this cause and no other (review 2026-11-08: the loose patterns tagged 10 of 15
    commented losses as 'trend' when Zee classed 4 - a comment naming two causes is ambiguous and gets no guess). His labels always override."""
    if not comment:
        return None
    d = DETECTORS[det]
    c = comment.lower()
    if re.search(d["no"], c):
        return "no"
    if not re.search(d["yes"], c):
        return None
    hits = [x for x, dd in DETECTORS.items() if re.search(dd["yes"], c) and not re.search(dd["no"], c)]
    return "yes" if hits == [det] else None


def _items(T, D):
    """the dataset's items: every loss, 2 same-side winning twins nearest in time per loss, 24 random winners (fixed seed)"""
    rows = T["trades"]
    losses = [r for r in rows if not r["win"]]
    wins = [r for r in rows if r["win"]]
    used, items = set(), []
    for r in losses:
        items.append((r, "loss"))
    for r in losses:
        cand = sorted((w for w in wins if w["side"] == r["side"] and w["id"] not in used), key=lambda w: abs(w["t_in"] - r["t_in"]))[:2]
        for w in cand:
            used.add(w["id"]); items.append((w, "twin"))
    rng = random.Random(1209)
    pool = [w for w in wins if w["id"] not in used]
    for w in rng.sample(pool, min(24, len(pool))):
        used.add(w["id"]); items.append((w, "random"))
    out = []
    for r, kind in items:
        it = dict(r)
        it["kind"] = kind
        it["bars"] = _bars(D, r["k"])
        it["n_before"] = N_BEFORE
        it["when"] = _pkt(r["t_in"])
        out.append(it)
    return out


_IT = {}


def dataset(det, setting_file, inputs=None):
    T = trades(setting_file, inputs)
    key = T["hash"]
    with _LOCK:
        items = _IT.get(key)
    if items is None:
        items = _items(T, _D())
        with _LOCK:
            _IT.clear(); _IT[key] = items
    out_items = []
    for it in items:
        x = dict(it)
        x["zee_says"] = _zee_says(det, it.get("comment") or "")
        out_items.append(x)
    return {"file": T["file"], "name": T["name"], "hash": key, "base": T["base"], "gate": T.get("gate"), "items": out_items, "engine_secs": T.get("secs"),
            "note": "tester estimate (Python engine on PrimeXBT ticks) - a hypothesis until MT5 confirms it"}


# ====================================================================================================== evaluate / estimate (memoised per rule)
_MEMO = {}


def _rule_sig(M, rule):
    return tuple((k, M.get(k, _OFF.get(k, "0"))) for k in rule["keys"]) + (("InpUhvRiskMgr", M.get("InpUhvRiskMgr", "0")),)


def _rule_on_trades(rule, M, T, D):
    """the sub-rule's verdict on every trade of the setting: {id: reason} for the ones it blocks (memoised per rule + its values)"""
    sig = ("T", T["hash"], rule["name"], _rule_sig(M, rule))
    with _LOCK:
        hit = _MEMO.get(sig)
    if hit is not None:
        return hit
    inp = _rule_inputs(M, rule)
    out = {}
    if _is_on(M, rule):
        if "InpUhvV2Against" in rule["keys"]:
            _v2_prefill(D, T["trades"], max(1, int(_val(M, "InpUhvV2Piv"))), _val(M, "InpUhvV2NoHH"), _val(M, "InpUhvV2Back"))
        for tr in T["trades"]:
            why = _call(rule, inp, D, tr, M)
            if why:
                out[tr["id"]] = why
    with _LOCK:
        if len(_MEMO) > 6000:
            _MEMO.clear()
        _MEMO[sig] = out
    return out


# ---- camel v2 over 3,000 trades: the engine's loop is pure Python (~3 ms a trade). A numba replica fills the engine's OWN cache (uhv_filters._V2)
#      so skip() still answers through v2_trend; before trusting it on a parameter set we compare it with v2_trend on 40 trades - one mismatch and
#      the replica is dropped for that set (the engine stays the judge).
try:
    from numba import njit as _njit
except ImportError:                                               # pragma: no cover
    _njit = None
_V2OK = {}


def _v2_jit_src():
    def _v2_core(h, l, c, k, p, nohh, back):
        n_sh = 0; n_sl = 0; sh_last = 0.0; sl_last = 0.0
        t = 0; flip = -1; brk = 0.0
        start = 2 * p if 2 * p > k - 400 else k - 400
        for j in range(start, k + 1):
            i = j - p
            m = h[i - p]
            for q in range(i - p, j + 1):
                if h[q] > m:
                    m = h[q]
            if h[i] == m:
                sh_last = h[i]; n_sh += 1
            m2 = l[i - p]
            for q in range(i - p, j + 1):
                if l[q] < m2:
                    m2 = l[q]
            if l[i] == m2:
                sl_last = l[i]; n_sl += 1
            if n_sh > 0 and c[j] > sh_last and t != 1:
                t = 1; flip = j; brk = sh_last
            elif n_sl > 0 and c[j] < sl_last and t != -1:
                t = -1; flip = j; brk = sl_last
        out = t
        if t != 0 and flip >= 0:
            if t > 0:
                ext = h[flip]
                for q in range(flip, k + 1):
                    if h[q] > ext:
                        ext = h[q]
                if ext <= brk + nohh * 1e-4:
                    out = 0
            else:
                ext = l[flip]
                for q in range(flip, k + 1):
                    if l[q] < ext:
                        ext = l[q]
                if ext >= brk - nohh * 1e-4:
                    out = 0
        if out != 0:
            has = False; ref = 0.0
            if t > 0 and n_sl > 0:
                ref = sl_last; has = True
            elif t < 0 and n_sh > 0:
                ref = sh_last; has = True
            if has and abs(c[k] - ref) <= back * 1e-4:
                out = 0
        return out
    return _v2_core


_v2_core = _njit(cache=False)(_v2_jit_src()) if _njit else None
_CONTIG = {}


def _contig(D):
    key = id(D)
    if _CONTIG.get("key") != key:
        C = F._prep(D)
        _CONTIG.clear()
        _CONTIG.update(key=key, h=np.ascontiguousarray(C["h"]), l=np.ascontiguousarray(C["l"]), c=np.ascontiguousarray(C["c"]))
    return _CONTIG


def _v2_prefill(D, trs, p, nohh, back):
    if _v2_core is None:
        return False
    key = (id(D), p, nohh, back)
    if key in _V2OK:
        return _V2OK[key]
    X = _contig(D)
    h, l, c = X["h"], X["l"], X["c"]
    ok = True
    for tr in trs[:40]:                                              # the self-check: the engine's own answer first
        k = tr["k"]
        if F.v2_trend(D, k, p, nohh, back) != int(_v2_core(h, l, c, k, p, float(nohh), float(back))):
            ok = False
            break
    if ok:
        for tr in trs:
            k = tr["k"]
            ck = (id(D), k, p, nohh, back)
            if ck not in F._V2:
                F._V2[ck] = int(_v2_core(h, l, c, k, p, float(nohh), float(back)))
    _V2OK[key] = ok
    return ok


def _rule_on_items(rule, M, items, D, hsh):
    sig = ("I", hsh, rule["name"], _rule_sig(M, rule))
    with _LOCK:
        hit = _MEMO.get(sig)
    if hit is not None:
        return hit
    inp = _rule_inputs(M, rule)
    out = {}
    if _is_on(M, rule):
        for tr in items:
            why = _call(rule, inp, D, tr, M)
            if why:
                out[tr["id"]] = why
    with _LOCK:
        if len(_MEMO) > 6000:
            _MEMO.clear()
        _MEMO[sig] = out
    return out


def _items_hash(items):
    return hashlib.sha1(",".join(f"{it['id']}{int(bool(it.get('sec')))}" for it in items).encode()).hexdigest()[:12]


def _counts(fires, labels, items):
    tp = fp = fn = tn = 0
    for it in items:
        lab = (labels.get(it["id"]) or {}).get("label")
        if lab not in ("yes", "no"):
            continue
        f = fires.get(it["id"], False)
        if lab == "yes":
            tp += f; fn += (not f)
        else:
            fp += f; tn += (not f)
    return {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn), "n": int(tp + fp + fn + tn)}


def evaluate(det, params, items, inputs, with_overlay=True):
    """the detector's verdict on each item with `params` laid over `inputs`: fires = the engine WOULD block this entry"""
    M = _merged(inputs, params)
    D = _D()
    hsh = _items_hash(items)
    rules = _rules(det)
    per_rule = {r["name"]: _rule_on_items(r, M, items, D, hsh) for r in rules}
    on = [r for r in rules if _is_on(M, r)]
    verdicts, fires = {}, {}
    for it in items:
        k = it["k"]
        ov, notes = [], {}
        if with_overlay:
            for r in on:
                try:
                    prim = r["overlay"](M, D, it)
                except LookAhead:
                    raise
                except Exception as e:  # noqa: BLE001 - a drawing failure must never hide a verdict
                    prim = [_note(f"{r['name']}: could not draw ({type(e).__name__}: {e})")]
                for pz in prim:
                    for kk in ("k", "k0", "k1"):
                        if kk in pz:
                            _chk(k, pz[kk])
                    for pt in pz.get("pts", ()):
                        _chk(k, pt[0])
                notes[r["name"]] = " · ".join(pz["text"] for pz in prim if pz.get("type") == "note" and pz.get("text"))
                ov += prim
            if not on:
                ov.append(_note("no sub-rule of this detector is on - turn one on to see its drawing"))
        # the badge's reason: the rule's note with its numbers (span, ATR, threshold) when drawn, else the engine's bare code ("range")
        reasons = [f"{r['name']}: {notes.get(r['name']) or per_rule[r['name']][it['id']]}" for r in rules if it["id"] in per_rule[r["name"]]]
        f = bool(reasons)
        fires[it["id"]] = f
        verdicts[it["id"]] = {"fires": f, "why": "; ".join(reasons) if reasons else "silent", "overlay": ov}
    labels = labels_get(det)
    guesses = {it["id"]: {"label": it.get("zee_says") or _zee_says(det, it.get("comment") or "")} for it in items}
    return {"verdicts": verdicts, "labelled": _counts(fires, labels, items), "guessed": _counts(fires, guesses, items),
            "fired": int(sum(fires.values())), "n": len(items)}


def _fires_on_trades(det, M, T, D):
    rules = _rules(det)
    blocked = {}
    for r in rules:
        for tid, why in _rule_on_trades(r, M, T, D).items():
            blocked.setdefault(tid, []).append(f"{r['name']}: {why}")
    return blocked


def estimate(det, params, setting_file, inputs=None):
    """the detector at EVERY trade of the setting (an approximation: harvest / busy interactions ignored) - a tester estimate"""
    T = trades(setting_file, inputs)
    inputs = inputs if inputs is not None else _setting(setting_file)[1]["inputs"]
    M = _merged(inputs, params)
    blocked = _fires_on_trades(det, M, T, _D())
    b = T["base"]
    lc = sum(1 for tr in T["trades"] if tr["id"] in blocked and not tr["win"])
    wc = sum(1 for tr in T["trades"] if tr["id"] in blocked and tr["win"])
    left = b["trades"] - lc - wc
    wr_est = 100.0 * (b["wins"] - wc) / left if left > 0 else 0.0
    loose = loosens(det, inputs, params or {})
    note = "tester estimate"
    if loose:                                                   # the estimate can only count trades REMOVED; a loosened rule lets unseen ones in
        note = f"tester estimate - CAREFUL: these values loosen {', '.join(loose)} (on in this setting), which lets in trades the estimate cannot see; only 🧪 Test knows"
    return {"trades": b["trades"], "base_losses": b["losses"], "losses_cut": lc, "winners_cut": wc, "wr_base": b["wr"], "wr_est": round(wr_est, 2),
            "trades_left": left, "per_day_left": round(left / max(b.get("days", 1), 1), 2), "loosens": loose, "note": note}


# ====================================================================================================== labels
def _labels_all():
    try:
        return json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _labels_write(allx):
    LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LABELS_FILE.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(allx, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, LABELS_FILE)


_OLD_ID = re.compile(r"^\d{4}-\d{6}-[BS]$")


def _migrate_label_ids(rows):
    """one-off: labels keyed by the old '%m%d-%H%M%S-S' id (no year - it collides across years) move to the '%y%m%d-%H%M%S-S' id of the trade
    they match in this dataset; an old key with no match stays as it is"""
    by_tail = {r["id"][2:]: r["id"] for r in rows}
    with _LOCK:
        allx = _labels_all()
        changed = False
        for det, d in allx.items():
            for key in list(d):
                new = by_tail.get(key) if _OLD_ID.match(key) else None
                if new and new not in d:
                    d[new] = d.pop(key); changed = True
        if changed:
            _labels_write(allx)


def labels_get(det):
    return dict(_labels_all().get(det) or {})


def label_set(det, id_, label, note=""):
    if det not in DETECTORS:
        raise KeyError(det)
    label = str(label or "").strip().lower()
    if label not in ("yes", "no", "unsure", ""):
        raise ValueError("label must be yes / no / unsure / ''")
    with _LOCK:
        allx = _labels_all()
        d = allx.setdefault(det, {})
        if not label and not str(note or "").strip():
            d.pop(str(id_), None)
        else:
            d[str(id_)] = {"label": label, "note": str(note or "")[:2000], "saved": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        _labels_write(allx)
    return labels_get(det)


# ====================================================================================================== fit
def _score(objective, bal, est, base, n_lab):
    """losses: losses cut beyond TWICE the random rate (cutting winners at the base loss rate x2 costs a loss each); labels: balanced accuracy;
    both: the sum, labels scaled to losses"""
    L, W = max(base["losses"], 1), max(base["wins"], 1)
    s_loss = est["losses_cut"] - 2.0 * est["winners_cut"] * L / W
    if objective == "losses" or (objective == "labels" and bal is None):
        return s_loss
    if objective == "labels":
        return bal * 100.0 + 0.01 * s_loss
    return s_loss + (bal if bal is not None else 0.0) * L


def _bal_acc(c):
    if c["tp"] + c["fn"] == 0 or c["fp"] + c["tn"] == 0:
        return None
    return 0.5 * (c["tp"] / (c["tp"] + c["fn"]) + c["tn"] / (c["fp"] + c["tn"]))


def _eval_items_fast(det, M, items, D, hsh, labels):
    rules = _rules(det)
    fires = {}
    for r in rules:
        for tid in _rule_on_items(r, M, items, D, hsh):
            fires[tid] = True
    c = _counts(fires, labels, items)
    lc = sum(1 for it in items if fires.get(it["id"]) and not it["win"] and it["kind"] == "loss")
    wc = sum(1 for it in items if fires.get(it["id"]) and it["win"])
    return fires, c, lc, wc


def fit(det, setting_file, inputs=None, objective="both", job=None, budget=1500, seed=7, params=None):
    """random sampling of the parameter grid + coordinate refinement of the best; ranked list of the top 15 distinct parameter sets.
    params = the page's sliders: the search STARTS from them (review 2026-11-08: a second fit used to restart from the saved setting and throw
    Zee's hand tuning away); the estimate stays keyed on the base setting, so 'stricter' is still measured against the setting."""
    job = job if job is not None else {}
    job.update(phase="loading", progress=0, total=budget, done=False, result=None, error=None)
    requested = objective
    try:
        T = trades(setting_file, inputs)
        inputs = inputs if inputs is not None else _setting(setting_file)[1]["inputs"]
        ds = dataset(det, setting_file, inputs)
        items = ds["items"]
        D = _D()
        hsh = _items_hash(items)
        base = T["base"]
        labels = labels_get(det)
        n_lab = sum(1 for it in items if (labels.get(it["id"]) or {}).get("label") in ("yes", "no"))
        if n_lab < 4:                                                # too few of Zee's labels: NEVER fit to comment-keyword guesses (review
            labels = {}                                              # 2026-11-08: they over-tag) - fall back to fewest losses and say so
            if objective in ("labels", "both"):
                objective = "losses"
            lab_src = f"only {n_lab} of your labels (need 4+): fitted for fewest losses instead - comment keywords are shown as hints, never used as labels"
        else:
            lab_src = f"Zee's labels ({n_lab})"
        keys = _det_keys(det)
        rules = _rules(det)
        Mb = _merged(inputs)                                         # the saved setting: 'stricter' and 'changed' are measured against it
        M0 = _merged(inputs, params)                                 # the sliders: where the search starts
        cur = {k: M0.get(k, _OFF.get(k, "0")) for k in keys}
        avail = {r["name"]: _avail(Mb, r) for r in rules}
        rng = random.Random(seed)
        n_w_items = max(sum(1 for it in items if it["win"]), 1)
        W, L = max(base["wins"], 1), max(base["losses"], 1)

        def fmt(k, v):
            v = float(v)
            return str(int(v)) if float(v).is_integer() else f"{v:g}"

        def proxy(params):
            M = _merged(inputs, params)
            fires, c, lc, wc = _eval_items_fast(det, M, items, D, hsh, labels)
            bal = _bal_acc(c)
            est = {"losses_cut": lc, "winners_cut": wc * W / n_w_items}          # the items' winners stand in for all winners
            return _score(objective, bal, est, base, n_lab), c, lc, wc

        seen, cands = set(), []

        n_loose = [0]

        def consider(params):
            sig = tuple(sorted((k, fmt(k, v)) for k, v in params.items()))
            if sig in seen:
                return
            seen.add(sig)
            if loosens(det, inputs, params):                         # never search a LOOSER rule: the estimate cannot see the trades it lets in
                n_loose[0] += 1
                return
            sc, c, lc, wc = proxy(params)
            cands.append((sc, {k: fmt(k, v) for k, v in params.items()}, c, lc, wc))

        # the values worth trying per input: a rule that is ON in the setting may only get STRICTER (its structural inputs stay); an OFF rule: its whole grid
        allowed = {}
        for r in rules:
            on0 = _is_on(Mb, r)
            for k in r["keys"]:
                g = [v for v in P[k]["grid"] if not on0 or _key_tightens(k, _val(Mb, k), v)]
                if not any(_same(v, cur[k]) for v in g):
                    g.append(cur[k])
                allowed[k] = g if avail[r["name"]] else [cur[k]]       # a rule the engine does not apply here (zone box without RM 4) is not searched
        job["phase"] = f"sampling the grid (scored on the {len(items)} charts; labels from {lab_src})"
        consider(dict(cur))
        for r in rules:                                                   # each rule alone at its allowed values
            if not avail[r["name"]]:
                continue
            for k in r["keys"]:
                for v in allowed[k]:
                    pset = dict(cur); pset[k] = v
                    if k != r["switch"] and _val(_merged(inputs, pset), r["switch"]) <= 0:
                        sw = [g for g in P[r["switch"]]["grid"] if float(g) > 0]
                        pset[r["switch"]] = sw[0] if sw else 1
                    consider(pset)
        n1 = int(budget * 0.75)
        while len(seen) < n1:
            pset = dict(cur)
            for r in rules:
                if avail[r["name"]] and rng.random() < 0.45:
                    for k in r["keys"]:
                        pset[k] = rng.choice(allowed[k])
            consider(pset)
            job["progress"] = len(seen)
        cands.sort(key=lambda x: -x[0])
        job["phase"] = "whole-setting estimate of the best (tester estimate)"
        top = cands[:30]
        ranked = []

        def full(params, c, lc_items, wc_items):
            est = estimate(det, params, setting_file, inputs)
            bal = _bal_acc(c)
            sc = _score(objective, bal, est, base, n_lab)
            return {"params": params, "agree": None if bal is None else round(bal, 3), **c, "losses_cut": est["losses_cut"], "winners_cut": est["winners_cut"],
                    "wr_est": est["wr_est"], "wr_base": est["wr_base"], "trades_left": est["trades_left"], "score": round(sc, 3)}
        for sc, params, c, lc, wc in top:
            ranked.append(full(params, c, lc, wc))
            job["progress"] = min(budget, job["progress"] + 5)
        ranked.sort(key=lambda x: -x["score"])
        job["phase"] = "coordinate refinement of the best"
        best = dict(ranked[0]["params"])
        improved, rounds = True, 0
        while improved and rounds < 3 and len(seen) < budget:
            improved = False; rounds += 1
            for k in keys:
                for v in allowed[k]:
                    pset = dict(best); pset[k] = fmt(k, v)
                    sig = tuple(sorted(pset.items()))
                    if sig in seen:
                        continue
                    seen.add(sig)
                    if loosens(det, inputs, pset):
                        n_loose[0] += 1
                        continue
                    sc, c, lc, wc = proxy(pset)
                    rec = full(pset, c, lc, wc)
                    ranked.append(rec)
                    job["progress"] = min(budget, len(seen))
                    if rec["score"] > ranked[0]["score"] + 1e-9:
                        ranked.sort(key=lambda x: -x["score"]); best = dict(rec["params"]); improved = True
            ranked.sort(key=lambda x: -x["score"])
        # distinct top 15: one row per OUTCOME (an inert input changed alongside is the same fix), the fewest changed inputs first
        for r in ranked:                                                  # 'changed' = vs the SAVED setting (what the page's column says)
            r["changed"] = {k: v for k, v in r["params"].items() if not _same(v, Mb.get(k, _OFF.get(k, "0")))}
        ranked.sort(key=lambda x: (-x["score"], len(x["changed"])))
        out, sigs = [], set()
        for r in ranked:
            sig = (r["score"], r["losses_cut"], r["winners_cut"], r["tp"], r["fp"], r["fn"], r["tn"])
            if sig in sigs or tuple(sorted(r["changed"].items())) in sigs:
                continue
            sigs.add(sig); sigs.add(tuple(sorted(r["changed"].items())))
            out.append(dict(r))
            if len(out) >= 15:
                break
        # the honest check: the FULL engine on the top rows (cutting trades moves the busy / cooldown chain, so the full run can differ from the estimate)
        n_full = min(3, len(out))
        for i in range(n_full):
            job["phase"] = f"full engine run of the top {n_full} rows ({i + 1}/{n_full})"
            try:
                fr = test_setting(det, out[i]["params"], setting_file, inputs)
                out[i]["full"] = {k: fr[k] for k in ("trades", "losses", "wr", "net", "per_day", "secs")}
            except Exception as e:  # noqa: BLE001 - the row keeps its estimate, the error is shown instead of the full numbers
                out[i]["full"] = {"error": f"{type(e).__name__}: {e}"[:200]}
        res = {"objective": objective, "requested": requested, "labels_from": lab_src, "evaluations": len(seen) - n_loose[0], "skipped_looser": n_loose[0],
               "base": base, "ranked": out, "full_checked": n_full,
               "start": {k: cur[k] for k in keys if not _same(cur[k], Mb.get(k, _OFF.get(k, "0")))},        # the sliders the search started from
               "note": "tester estimate - a hypothesis until MT5 confirms it; only values that make a rule STRICTER than the setting's were searched"
                       + (f" ({n_loose[0]} looser sets skipped)" if n_loose[0] else "")}
        job.update(result=res, done=True, phase="done", progress=budget)
        return out
    except Exception as e:  # noqa: BLE001
        job.update(error=f"{type(e).__name__}: {e}", done=True, phase="error")
        raise


def new_job(det=None, total=1):
    """an empty job dict: the server registers it (so a poll can find it) BEFORE the worker starts"""
    return {"phase": "queued", "progress": 0, "total": total, "done": False, "result": None, "error": None, "det": det, "started": time.time()}


def fit_async(det, setting_file, inputs=None, objective="both", budget=1500, params=None, job=None):
    job = job if job is not None else new_job(det, budget)
    th = threading.Thread(target=lambda: _quiet(fit, det, setting_file, inputs, objective, job, budget, 7, params), daemon=True)
    th.start()
    return job


def _quiet(fn, *a):
    try:
        fn(*a)
    except Exception:  # noqa: BLE001 - the job dict carries the error
        pass


# ====================================================================================================== features / learned
def _feat_common(D, tr):
    C = F._prep(D); h, l, c, v = C["h"], C["l"], C["c"], C["v"]
    k, side, level, atr = tr["k"], tr["side"], tr["level"], max(tr["atr"], 1e-9)
    return C, h, l, c, v, k, side, level, atr


def features(det, items, inputs=None):
    """per-item numeric features of the detector's sub-signals (candles <= k only): {id: {name: value}}"""
    M = _merged(inputs)
    D = _D()
    out = {}
    for tr in items:
        C, h, l, c, v, k, side, level, atr = _feat_common(D, tr)
        f = {}
        if det == "ranging":
            for N in (10, 20, 45):
                f[f"span{N}_atr"] = float(h[k - N + 1:k + 1].max() - l[k - N + 1:k + 1].min()) / atr
            for N in (10, 30):
                f[f"er{N}"] = _er(c, k, N)
            N = 20; hi, lo = float(h[k - N + 1:k + 1].max()), float(l[k - N + 1:k + 1].min())
            pos = (level - lo) / (hi - lo) if hi > lo else 0.5
            f["pos20_from_trade_end"] = pos if side > 0 else 1 - pos
            N = max(10, int(_val(M, "InpUhvBoxBars"))); a = k - N + 1
            hh, ll = h[a:k + 1], l[a:k + 1]; top, bot = float(hh.max()), float(ll.min()); tol = 0.15 * max(top - bot, 1e-9)

            def touches(mask):
                cnt, last = 0, -99
                for q in np.flatnonzero(mask):
                    if q - last >= 3:
                        cnt += 1; last = q
                return cnt
            f["box_touch_top"] = touches(hh >= top - tol); f["box_touch_bot"] = touches(ll <= bot + tol)
            at = np.asarray(D["atr"], dtype=float)
            f["box_atr_ratio"] = float(at[k] / max(at[a - 120:a].mean(), 1e-12)) if a >= 120 else 1.0
            f["box_vol_ratio"] = float(v[a:k + 1].mean() / max(v[a - 300:a].mean(), 1e-9)) if a >= 300 else 1.0
            f["level_depth_in_box"] = float(((top - level) if side > 0 else (level - bot)) / max(top - bot, 1e-9))
        elif det == "sr":
            for p in (5, 10, 20):
                lows, highs = F._major_idx(D, p)
                idx = lows if side < 0 else highs
                j = int(np.searchsorted(idx, k - p, side="right"))
                sel = idx[max(0, j - 3):j]
                d = ((level - l[sel]) if side < 0 else (h[sel] - level)) / PIP if len(sel) else np.array([99.0])
                ahead = d[d >= 0]
                f[f"major{p}_ahead_pips"] = float(ahead.min()) if len(ahead) else 99.0
            n = 60; lo, hi = float(l[k - n + 1:k + 1].min()), float(h[k - n + 1:k + 1].max())
            f["sr60_pips"] = ((tr["px"] - lo) if side < 0 else (hi - tr["px"])) / PIP
            g = 100 * PIP
            fig = np.ceil(level / g - 1e-9) * g if side > 0 else np.floor(level / g + 1e-9) * g
            f["fig100_ahead_pips"] = ((fig - level) if side > 0 else (level - fig)) / PIP
            g = 50 * PIP
            fig = np.ceil(level / g - 1e-9) * g if side > 0 else np.floor(level / g + 1e-9) * g
            f["fig50_ahead_pips"] = ((fig - level) if side > 0 else (level - fig)) / PIP
            ext = h[k - 59:k + 1] if side > 0 else l[k - 59:k + 1]
            f["touches_at_fig"] = 0.0
            for cc in np.unique(np.round(ext / 1e-5)) * 1e-5:
                d = (cc - level) / PIP if side > 0 else (level - cc) / PIP
                if 0 <= d <= 3 and abs(cc - round(cc / (100 * PIP)) * 100 * PIP) <= 1e-4:
                    f["touches_at_fig"] = max(f["touches_at_fig"], float(np.sum(np.abs(ext - cc) <= 0.5e-4)))
            last = C["lastL"] if side < 0 else C["lastH"]
            best = 99.0
            for j in F._swings(last, k, 12):
                if j < k -30:
                    continue
                d = (level - l[j]) / PIP if side < 0 else (h[j] - level) / PIP
                if 0 <= d < best:
                    best = d
            f["swing30_ahead_pips"] = best
        elif det == "trend":
            f["v2_x_side"] = F.v2_trend(D, k, 2, 2.0, 2.0) * side
            f["v2_p3_x_side"] = F.v2_trend(D, k, 3, 2.0, 2.0) * side
            ef, es, sk, sd = F._shift_arrays(D, 8, 21)
            f["ema8_slope3_x_side"] = (ef[k] - ef[k - 3]) * side / PIP
            f["ema21_slope3_x_side"] = (es[k] - es[k - 3]) * side / PIP
            f["ema_gap_x_side"] = (ef[k] - es[k]) * side / PIP
            f["stochK"] = float(sk[k]); f["stochK_minus_D"] = float(sk[k] - sd[k])
            f["camel_humps_x_side"] = int(C["stk"][k]) * side
            for n in (20, 90):
                f[f"move{n}_atr_x_side"] = (c[k] - c[k - n]) * side / atr
            N = 60; seg = slice(k - N + 1, k + 1)
            j = (k - N + 1) + (int(np.argmin(l[seg])) if side < 0 else int(np.argmax(h[seg])))
            vv = np.maximum(v[j:k + 1], 1.0)
            f["avwap60_dist_x_side"] = (c[k] - float((c[j:k + 1] * vv).sum() / vv.sum())) * side / PIP
            pp = 3; arr = h if side > 0 else l; sw = []
            for i in range(max(pp, k - 300), k - pp + 1):
                win = arr[i - pp:i + pp + 1]
                if (side > 0 and arr[i] == win.max()) or (side < 0 and arr[i] == win.min()):
                    sw.append(i)
            f["lower_high"] = float(len(sw) >= 2 and ((arr[sw[-1]] < arr[sw[-2]]) if side > 0 else (arr[sw[-1]] > arr[sw[-2]])))
            end = int(C["end5"][k]); idx = [end - 5 * i for i in range(12)][::-1]
            f["htf5_slope_x_side"] = float(np.polyfit(np.arange(12), c[idx], 1)[0] * side / PIP) if idx[0] >= 0 else 0.0
        else:
            for nf in (30, 60):
                dd = np.sign(np.diff(c[k - nf:k + 1]))
                f[f"flips{nf}"] = float((dd[1:] * dd[:-1] < 0).mean())
            f["atr_pips"] = atr / PIP
            for N in (10, 30):
                f[f"er{N}"] = _er(c, k, N)
            f["ticks10"] = float(v[k - 9:k + 1].mean())
            f["vol_rel"] = float(v[k - 9:k + 1].mean() / max(float(v[k - 309:k - 9].mean()), 1e-9)) if k >= 310 else 1.0
            f["range10_atr"] = float(h[k - 9:k + 1].max() - l[k - 9:k + 1].min()) / atr
            f["spread_pips"] = float(np.asarray(D["sp1"])[k]) / PIP if "sp1" in D else 0.0
        out[tr["id"]] = {a: (round(float(b), 4) if isinstance(b, (int, float, np.floating, np.integer)) else b) for a, b in f.items()}
    return out


def learned(det, items, inputs=None):
    """a tiny logistic model on the labelled items (Zee's labels; his comment keywords as guesses when there are too few), leave-one-out accuracy"""
    labels = labels_get(det)
    y, X, names, ids, src = [], [], None, [], "labels"
    rows = []
    for it in items:
        lab = (labels.get(it["id"]) or {}).get("label")
        if lab in ("yes", "no"):
            rows.append((it, lab))
    if len(rows) < 8:
        src = "labels + comment keywords"
        got = {it["id"] for it, _ in rows}
        for it in items:
            if it["id"] not in got and it.get("zee_says") in ("yes", "no"):
                rows.append((it, it["zee_says"]))
    if len(rows) < 8 or len({lab for _, lab in rows}) < 2:
        return {"acc_loo": None, "n": len(rows), "coef": {}, "text": f"too few labels ({len(rows)}; need 8+ with both YES and NO) - label more charts and try again", "source": src}
    feats = features(det, [it for it, _ in rows], inputs)
    names = sorted(next(iter(feats.values())).keys())
    X = np.array([[feats[it["id"]][n] for n in names] for it, _ in rows], dtype=float)
    y = np.array([1 if lab == "yes" else 0 for _, lab in rows])
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
    except ImportError:
        return {"acc_loo": None, "n": len(rows), "coef": {}, "text": "scikit-learn is not installed", "source": src}
    ok = 0
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        if len(set(y[m])) < 2:
            continue
        mdl = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, class_weight="balanced", max_iter=500)).fit(X[m], y[m])
        ok += int(mdl.predict(X[i:i + 1])[0] == y[i])
    mdl = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, class_weight="balanced", max_iter=500)).fit(X, y)
    coef = dict(sorted(zip(names, mdl[-1].coef_[0].round(3).tolist()), key=lambda x: -abs(x[1])))
    acc = ok / len(y)
    top = [f"{n} ({'pushes to YES' if w > 0 else 'pushes to NO'}, weight {w:+.2f})" for n, w in list(coef.items())[:4]]
    base_rate = max(y.mean(), 1 - y.mean())
    text = (f"A logistic model on {len(y)} labelled charts ({src}) gets {acc * 100:.0f}% leave-one-out accuracy (always guessing the majority would get "
            f"{base_rate * 100:.0f}%). It leans on: " + "; ".join(top) + ". Tester estimate on a tiny sample - a hint for which rule to tune, not a rule.")
    return {"acc_loo": round(acc, 3), "n": int(len(y)), "coef": coef, "text": text, "source": src, "majority": round(float(base_rate), 3)}


# ====================================================================================================== prompts for Claude
def _bar_table(it, n_before=40, n_after=10, part="before"):
    """part 'before': the candles <= k only (what a rule may read); 'after': the candles after the entry (the outcome, for the diagnosis only)"""
    b = it["bars"]; nb = it["n_before"]
    rows = ["time(UTC)  open    high    low     close   ticks"]
    rng = range(max(0, nb - n_before), nb) if part == "before" else range(nb, min(len(b["t"]), nb + n_after))
    for i in rng:
        tag = "" if i < nb else "   <- AFTER the entry (outcome only; a rule must not read it)"
        if i == nb - 1:
            tag = "   <- k, the last closed candle before the entry"
        rows.append(f"{_utc(b['t'][i]):%H:%M}  {b['o'][i]:.5f} {b['h'][i]:.5f} {b['l'][i]:.5f} {b['c'][i]:.5f} {b['v'][i]:>5d}{tag}")
    return "\n".join(rows)


def ask_prompt(det, item, params, verdict, inputs=None):
    M = _merged(inputs, params)
    d = describe(det, M)
    side = "BUY" if item["side"] > 0 else "SELL"
    f = features(det, [item], M).get(item["id"], {})
    lines = [
        f"You are helping Zee fix the '{d['title']}' loss detector of his UHV breakout tester (EUR/USD 1-minute candles, PrimeXBT ticks). "
        f"The detector is a bundle of the engine's loss filters (uhv_filters.py inputs). Answer in plain English for Zee, no code unless asked, under 250 words.",
        "", f"TRADE {item['id']}: {side} at {item['fill']:.5f} on {item['when']} ({_utc(item['t_in']):%Y-%m-%d %H:%M} UTC); UHV level {item['level']:.5f}, "
        f"retracement extreme {item['extreme']:.5f}, ATR {item['atr'] / PIP:.2f} pips.",
        f"ZEE'S LABEL for this detector: {(labels_get(det).get(item['id']) or {}).get('label') or 'none'}"
        + (f" (his comment's keywords suggest: {item['zee_says']})" if item.get("zee_says") else ""),
        "", "THE RULES AS SET NOW:"]
    lines += [f"- {r['name']} [{'ON' if r['on'] else 'off'}]: {r['text']}" for r in d["rules"]]
    lines += ["", f"THE DETECTOR'S VERDICT: {'FIRES (would skip)' if verdict.get('fires') else 'silent (would trade)'} - {verdict.get('why', '')}",
              "", "SUB-SIGNAL FEATURES at k (candles <= k only): " + ", ".join(f"{a} = {b}" for a, b in f.items()),
              "", "THE CANDLES UP TO k (one-minute; the last 40 closed before the entry - all a rule may read):", _bar_table(item, part="before"), "",
              "QUESTION 1 - answer it BEFORE reading the block below, from these candles alone: is this a case of '" + d["title"] + "'? Say yes / no and why.",
              "", "---- now the outcome and Zee's words, for questions 2 and 3 only (hindsight: never let them colour question 1) ----",
              f"RESULT: {'WIN' if item['win'] else 'LOSS'} ${item['pnl']:.0f} ({item['kind']}).",
              f"ZEE'S COMMENT: {item.get('comment') or '(none)'}",
              "THE 10 CANDLES AFTER THE ENTRY (outcome only; no rule may read them):", _bar_table(item, part="after"), "",
              "QUESTION 2) Why did the detector " + ("fire" if verdict.get("fires") else "stay silent") + " here - which rule / value is the mismatch? "
              "QUESTION 3) Propose ONE concrete change: a parameter value (name the Inp input and the number) or a new rule in terms of candles <= k, and say which "
              "of the other charts it would likely flip. Never use the candles after the entry for the rule. Remember every number here is a Python tester "
              "estimate - a hypothesis, not proof."]
    return "\n".join(lines)


def propose_prompt(det, ds, labels=None, inputs=None, params=None):
    base_in = inputs if inputs is not None else _setting(ds["file"])[1]["inputs"]
    M = _merged(base_in, params)                                     # the params laid over the setting for the TEXT; the base inputs go to the
    d = describe(det, M)                                              # estimate (its engine run + cache are keyed by the setting, never by params)
    labels = labels if labels is not None else labels_get(det)
    items = ds["items"]
    ev = evaluate(det, params or {}, items, base_in, with_overlay=False)
    feats = features(det, items, M)
    est = estimate(det, params or {}, ds["file"], base_in)
    lines = [f"You are helping Zee improve the '{d['title']}' loss detector of his UHV breakout tester (EUR/USD 1-minute, PrimeXBT ticks). Plain English, under 400 words, "
             "then a short list of concrete parameter changes (Inp name = value) or ONE new rule written in terms of candles <= k.",
             "", "THE RULES AS SET NOW:"] + [f"- {r['name']} [{'ON' if r['on'] else 'off'}]: {r['text']}" for r in d["rules"]]
    lines += ["", f"SETTING {ds['name']}: {ds['base']['trades']} trades, {ds['base']['losses']} losses, win rate {ds['base']['wr']}% (tester estimate). "
              f"With the rules as set the detector would cut {est['losses_cut']} losses and {est['winners_cut']} winners (est. win rate {est['wr_est']}%).",
              f"ON THE {len(items)} CHARTS (every loss + its winning twins + random winners): fires on {ev['fired']}; against Zee's labels tp {ev['labelled']['tp']} fp "
              f"{ev['labelled']['fp']} fn {ev['labelled']['fn']} tn {ev['labelled']['tn']}; against his comment keywords tp {ev['guessed']['tp']} fp {ev['guessed']['fp']} "
              f"fn {ev['guessed']['fn']} tn {ev['guessed']['tn']}.", "", "ONE LINE PER CHART (id · kind · result · label · verdict · features · Zee's comment):"]
    for it in items:
        lab = (labels.get(it["id"]) or {}).get("label") or (f"guess:{it['zee_says']}" if it.get("zee_says") else "-")
        v = ev["verdicts"][it["id"]]
        fs = " ".join(f"{a}={b}" for a, b in feats[it["id"]].items())
        cm = (it.get("comment") or "").replace("\n", " ")[:160]
        lines.append(f"{it['id']} · {it['kind']} · {'WIN' if it['win'] else 'LOSS'} · {lab} · {'FIRES' if v['fires'] else 'silent'} ({v['why'][:80]}) · {fs}" + (f" · \"{cm}\"" if cm else ""))
    lines += ["", "TASK: where do the labelled YES charts (and the losses Zee called '" + d["title"] + "') differ from the winners in these features? Which rule should fire on them "
              "and does not, which fires on winners and should not? Propose the smallest parameter change that separates them, and if none can, ONE new rule. "
              "Every rule must read only candles up to k. All numbers are Python tester estimates - hypotheses until MT5 confirms them."]
    return "\n".join(lines)


# ====================================================================================================== save / test
# the params a page may lay over a setting: the detector sliders, every UHV engine input (the loss filters, the risk manager, the sessions ...),
# the detection inputs and the range boxes - the hungry scanner (hungry.py, Zee 2026-11-08: "Scan for maximizing trades") moves all of them.
# Never silently: a key outside this set still raises, so a typo cannot ride into a saved file.
ALLOWED_KEYS = set(P) | set(U.UHV_DEFAULTS) | set(U.DET) | {"InpBandsB", "InpBandsS", "InpBandOff", "InpMaxPos"}


def final_inputs(params, inputs):
    """the inputs the engine runs AND the file keeps: the base setting's inputs with the params laid over - the SAME function for 🧪 Test,
    💾 Save and the hungry scanner, so the file tested is the file saved. The sliders themselves never touch InpUhvRiskMgr: the old save
    flipped it to 4 for the zone box, which switches every skip() loss filter off outside the risky zones (review 2026-11-08: a 'harmless'
    Test, then a saved setting at 8,694 trades / 121 losses / -$16,107 in the tester). The hungry scanner MAY move it - as an explicit, visible
    step of its path, judged by the full engine like every other move."""
    inp = {k: str(v) for k, v in (inputs or {}).items()}
    for k, v in (params or {}).items():
        if k not in ALLOWED_KEYS:
            raise ValueError(f"not an engine input: {k}")
        v = str(v).strip()
        if k in ("InpBandsB", "InpBandsS") and not re.fullmatch(r"[01]{21}", v):      # the engine ljust()s and reads char by char: 'abc' would silently mean 'trade every box'
            raise ValueError(f"{k} must be 21 chars of 0/1 (one per 5% range box), got {v!r}")
        if k == "InpBandOff" and v not in ("0", "1", "0.0", "1.0"):
            raise ValueError(f"InpBandOff must be 0 or 1, got {v!r}")
        inp[k] = v
    return inp


EA_DEFAULTS = {}                                                   # server.py: detlab.EA_DEFAULTS = axi_rig.ea_defaults(EA) (no import cycle)


def full_defaults():
    """every input's default the way the page's own saves diff against them (server.full_inputs): the EA's inputs (InpBandsB / InpBandsS /
    InpBandOff ...), the UHV engine, the TTD indicator, the detection inputs. The EA defaults need the server's EA name: server.py sets
    EA_DEFAULTS once at import; without them the UHV / TTD / detection / range-box defaults still apply."""
    import uhv_ttd
    dfl = {k: str(v) for k, v in (EA_DEFAULTS or {}).items()}
    dfl.update({k: str(v[0]) for k, v in U.UHV_DEFAULTS.items()})
    dfl.update({k: str(v[0]) for k, v in uhv_ttd.TTD.items()})
    dfl.update({k: f"{v:g}" for k, v in U.DET_DEFAULT.items()})
    dfl.update({"InpBandsB": "1" * 21, "InpBandsS": "1" * 21})
    dfl.setdefault("InpBandOff", "1")
    return dfl


def save_setting(det, params, setting_file, name=None):
    """settings/saved/<name>.json in the exact shape of the page's saves: final_inputs() - exactly what 🧪 Test ran"""
    p, rec = _setting(setting_file)
    inp = final_inputs(params, rec["inputs"])
    d = DETECTORS.get(det) or {"emoji": "🍖", "title": "Hungry scanner (more trades, same win rate)"}   # hungry.py saves are not per detector
    name = str(name or "").strip() or f"{_dt.datetime.now():%Y-%m-%d %H-%M-%S} {d['emoji']} {d['title']}"
    if not (name and len(name) <= 150 and not SAVED_NAME_BAD.search(name)):
        raise ValueError("bad setting name")
    # 'changed' = every input that differs from the defaults EXACTLY as /api/save computes it (server.py: dfl = axi_rig.ea_defaults(EA); the
    # TTD / detection inputs are not EA inputs, so they are always listed - that is the convention every saved file and the MT5-run matching
    # already follow). Review 2026-11-08: it was diffed against UHV_DEFAULTS only and otherwise copied from the base, so a hungry save that moved
    # only InpDetCamPiv / a range box / InpBandOff had the SAME 'changed' as its base - and server._attach_candidate_to_saved, which matches an
    # MT5 run to every saved file whose 'changed' is identical, attached the base's MT5 result to it as if verified. Without the server (a
    # script) the merged full_defaults() stand in.
    dfl = {k: str(v) for k, v in EA_DEFAULTS.items()} if EA_DEFAULTS else full_defaults()
    changed = {k: v for k, v in inp.items() if not _same(v, dfl.get(k))}
    out = {"name": name, "inputs": inp, "changed": changed, "ds": rec.get("ds") or "year1", "mode": rec.get("mode") or "ea", "result": None,
           "lab": rec.get("lab") or {}, "lab_describe": rec.get("lab_describe") or "",
           "note": f"Detector Lab: {d['title']} tuned on {p.stem} (tester estimate; run the tester / MT5 for the result)",
           "source": {"kind": "detector_lab", "det": det, "base_setting": p.stem, "params": {k: str(v) for k, v in (params or {}).items()},
                      "saved": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
    SAVED.mkdir(parents=True, exist_ok=True)
    f = SAVED / f"{name}.json"
    while f.exists():
        name = name + " ·"
        f = SAVED / f"{name}.json"
    f.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"file": f.name, "name": name, "inputs": inp}


def test_setting(det, params, setting_file, inputs=None, job=None):
    """the FULL engine with the detector's params laid over the setting (the honest number; still a tester estimate)"""
    job = job if job is not None else {}
    job.update(phase="running the engine", done=False, result=None, error=None)
    try:
        p, rec = _setting(setting_file)
        inputs = inputs if inputs is not None else rec["inputs"]
        M = final_inputs(params, inputs)                             # the same inputs 💾 Save writes
        t0 = time.time()
        tr, su, cnt = U.simulate(M)
        R = tr[tr[:, 10] == 0] if len(tr) else tr
        D = _D(); t1 = np.asarray(D["t1"], dtype=np.int64)
        days = len(np.unique(t1 // 86400))
        wins = int((R[:, 6] > 0).sum()) if len(R) else 0
        res = {"trades": int(len(R)), "wins": wins, "losses": int(len(R) - wins), "wr": round(100.0 * wins / max(len(R), 1), 2), "net": round(float(R[:, 6].sum()), 2) if len(R) else 0.0,
               "per_day": round(len(R) / max(days, 1), 2), "secs": round(time.time() - t0, 1), "skips": {k: int(v) for k, v in cnt.items()}, "note": "tester estimate (full engine run)"}
        job.update(result=res, done=True, phase="done")
        return res
    except Exception as e:  # noqa: BLE001
        job.update(error=f"{type(e).__name__}: {e}", done=True, phase="error")
        raise


def test_async(det, params, setting_file, inputs=None, job=None):
    job = job if job is not None else new_job(det)
    threading.Thread(target=lambda: _quiet(test_setting, det, params, setting_file, inputs, job), daemon=True).start()
    return job


# ====================================================================================================== the auto-tuner scan
# Zee 2026-11-08: "make a button here called Scan for tuned settings -> there it runs a scan similar to (Exit Lab -> Scanner) -> wherein it tries
# different values ... and if a value results in a winrate it can give a suggestion to accept/apply that tuned value. This way i can run an
# auto-tuner -> instead of trying 100s of settings myself." One detector input at a time, every scanner grid value, each through the FULL engine
# (no estimate: the scanner's judge is the real tester run, so looser values are allowed here - the engine sees the trades they let in).
def _summ(tr):
    R = tr[tr[:, 10] == 0] if len(tr) else tr
    D = _D(); t1 = np.asarray(D["t1"], dtype=np.int64)
    days = len(np.unique(t1 // 86400))
    wins = int((R[:, 6] > 0).sum()) if len(R) else 0
    n = int(len(R))
    return {"trades": n, "wins": wins, "losses": n - wins, "wr": round(100.0 * wins / max(n, 1), 2), "net": round(float(R[:, 6].sum()), 2) if n else 0.0,
            "per_day": round(n / max(days, 1), 2)}


def scan_one(inputs):
    """one full engine run (in a scan worker or inline): the setting's inputs -> the numbers"""
    os.environ.setdefault("NUMBA_CPU_NAME", "generic")
    t0 = time.time()
    tr, _, _ = U.simulate(inputs)
    s = _summ(tr)
    s["secs"] = round(time.time() - t0, 1)
    return s


def scan_moves(det, inputs, params=None):
    """the candidates: for every input of the detector (zone box only when the engine applies it), every scanner grid value but the current one.
    Enum switches that are OFF get every ON value; thresholds get the whole grid (stricter AND looser - the full engine judges)."""
    M0 = final_inputs(params, inputs)
    dets = list(DETECTORS) if det == "all" else [det]               # Zee 2026-11-08: "scans all four?" - det "all" = every detector's inputs in one scan
    out, seen = [], set()
    for d in dets:
        for r in _rules(d):
            if not _avail(M0, r):
                continue
            for k in r["keys"]:
                spec = P.get(k)
                if not spec or not spec.get("grid") or k in seen:          # MinErN sits in Ranging AND Choppy: once
                    continue
                seen.add(k)
                cur = _val(M0, k)
                for v in spec["grid"]:
                    if _same(v, cur):
                        continue
                    out.append({"det": d, "emoji": DETECTORS[d]["emoji"], "rule": r["name"], "key": k, "label": spec["label"], "from": _fmt(cur), "to": _fmt(v),
                                "params": dict(params or {}, **{k: _fmt(v)})})
    return M0, out


def _fmt(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(x)) if abs(x - round(x)) < 1e-9 else f"{x:g}"


def _rank_key(row, base):
    """Zee's targets: win rate first, then fewer losses, then more trades (net is information, not the target)"""
    return (-row["wr"], row["losses"], -row["trades"])


def scan(det, setting_file, inputs=None, params=None, job=None):
    job = job if job is not None else new_job(det)
    try:
        p, rec = _setting(setting_file)
        inputs = inputs if inputs is not None else rec["inputs"]
        M0, moves = scan_moves(det, inputs, params)
        job.update(phase="the starting point (full engine run)", total=len(moves) + 1, progress=0)
        t0 = time.time()
        base = scan_one(M0)
        res = {"base": base, "start": {k: str(v) for k, v in (params or {}).items()}, "rows": [], "evaluations": 0, "total": len(moves), "secs": 0,
               "note": "every row is a FULL engine run (tester estimate - a hypothesis until MT5 confirms it)"}
        job.update(result=res, progress=1)
        pool = None
        try:
            import scan as _scan
            pool = _scan._pool()
        except Exception:  # noqa: BLE001 - no pool (frozen numba, no spawn): run inline
            pool = None

        def finish(mv, s):
            row = dict(mv, **s)
            row["d_wr"] = round(s["wr"] - base["wr"], 2); row["d_losses"] = s["losses"] - base["losses"]; row["d_trades"] = s["trades"] - base["trades"]
            row["d_net"] = round(s["net"] - base["net"], 2)
            # a suggestion = a higher win rate, or the same win rate with fewer losses (never: fewer trades alone)
            row["suggest"] = s["wr"] > base["wr"] + 1e-9 or (abs(s["wr"] - base["wr"]) < 1e-9 and s["losses"] < base["losses"])
            res["rows"].append(row)
            res["rows"].sort(key=lambda r: _rank_key(r, base))
            res["evaluations"] += 1; res["secs"] = round(time.time() - t0, 1)
            job.update(progress=1 + res["evaluations"], phase=f"{res['evaluations']} of {len(moves)} values tried · best so far: {res['rows'][0]['wr']:.2f}% / {res['rows'][0]['losses']} losses")

        if pool is not None:
            import concurrent.futures as cf
            futs = {pool.submit(scan_one, final_inputs(mv["params"], inputs)): mv for mv in moves}
            for f in cf.as_completed(futs):
                mv = futs[f]
                try:
                    finish(mv, f.result())
                except Exception as e:  # noqa: BLE001 - one bad value must not kill the scan
                    res.setdefault("errors", []).append({"key": mv["key"], "to": mv["to"], "error": f"{type(e).__name__}: {str(e)[:120]}"})
                    res["evaluations"] += 1
        else:
            for mv in moves:
                try:
                    finish(mv, scan_one(final_inputs(mv["params"], inputs)))
                except Exception as e:  # noqa: BLE001
                    res.setdefault("errors", []).append({"key": mv["key"], "to": mv["to"], "error": f"{type(e).__name__}: {str(e)[:120]}"})
                    res["evaluations"] += 1
        res["suggestions"] = sum(1 for r in res["rows"] if r["suggest"])
        job.update(result=res, done=True, phase="done", progress=job["total"])
        return res
    except Exception as e:  # noqa: BLE001
        job.update(error=f"{type(e).__name__}: {e}", done=True, phase="error")
        raise


def scan_async(det, setting_file, inputs=None, params=None, job=None):
    job = job if job is not None else new_job(det)
    threading.Thread(target=lambda: _quiet(scan, det, setting_file, inputs, params, job), daemon=True).start()
    return job


# ====================================================================================================== the look-ahead proof
def lookahead_check(det, items, inputs=None, params=None, n=3):
    """mutate every candle AFTER k (garbage highs / lows / closes / volumes) and re-run the detector: no verdict may change.
    Expensive (the caches are rebuilt for the mutated data) - a test, not a page call."""
    D = _D()
    pick = items[:n]
    M = _merged(inputs, params)
    rules = _rules(det)
    out = []
    saved = {k: dict(v) for k, v in (("C", F._C),)}
    for it in pick:
        k = it["k"]
        D2 = {key: np.array(D[key], dtype=float, copy=True) for key in ("t1", "o1", "h1", "l1", "c1", "v1", "atr", "adx", "sp1") if key in D}
        rng = np.random.default_rng(k)
        n_after = len(D2["c1"]) - (k + 1)
        for key in ("o1", "h1", "l1", "c1"):
            D2[key][k + 1:] = D2[key][k] + rng.normal(0, 0.01, n_after)      # 100-pip noise after k
        D2["h1"][k + 1:] = np.maximum(D2["h1"][k + 1:], D2["c1"][k + 1:]) + 0.0005
        D2["l1"][k + 1:] = np.minimum(D2["l1"][k + 1:], D2["c1"][k + 1:]) - 0.0005
        D2["v1"][k + 1:] = rng.integers(1, 500, n_after)
        D2["atr"][k + 1:] = rng.uniform(0.0001, 0.01, n_after)
        # the engine's caches are keyed by id(D): a new dict = fresh caches on the mutated candles
        F._MAJ.clear(); F._SHIFT.clear(); F._V2.clear()
        ref = {}
        for r in rules:
            inp = _rule_inputs(M, r)
            ref[r["name"]] = _call(r, inp, D, it, M) if _is_on(M, r) else None
        F._MAJ.clear(); F._SHIFT.clear(); F._V2.clear()
        mut = {}
        for r in rules:
            inp = _rule_inputs(M, r)
            mut[r["name"]] = _call(r, inp, D2, it, M) if _is_on(M, r) else None
        F._MAJ.clear(); F._SHIFT.clear(); F._V2.clear()
        same = all((ref[a] is None) == (mut[a] is None) for a in ref)
        out.append({"id": it["id"], "same": same, "ref": ref, "mutated": mut})
        if not same:
            raise LookAhead(f"{det} verdict changed when the candles after k were mutated on {it['id']}: {ref} vs {mut}")
    F._C.clear(); F._C.update(saved["C"])
    return out
