"""hungry.py - the HUNGRY scanner: more trades per day at the same win rate.

Zee 2026-11-08: "can u add a button to the scanner near Scan all four detectors -> the name of new button can be : Scan for maximizing trades ->
this button does this: It tries to increase the number of trades we take per day without loosing the winrate -> so it is like a greedy, hungry
for trade scanner which tries to include more and more trades with minimal loss of winrate ... i want you to put all the intelligence you have
into building this one scanner which trades more per day at same winrate".

HOW IT THINKS
  A setting takes 976 of 25,694 setups: every other setup is blocked by SOME input - a session rule, the spread gate, the setup selection, the
  risk manager, one of ~60 loss filters, the Saad switches, a stood-aside range box, the one-trade-at-a-time rule. Every one of those inputs has
  a LOOSENING direction: the direction that lets MORE trades through (a later Friday cut, a wider spread, a higher MaxAtrPips, a lower MinErN,
  a switch to off ...). LEVERS below lists them all, with that direction; the trade geometry and the fill model (stops, targets, latency, lots,
  the TTD indicator, the Exit Lab exits) are FROZEN - Zee's standing rule: never buy trades or win rate with wider stops.
  The scan is a greedy path: from the setting, try EVERY loosening move one at a time through the FULL engine (scan.py's worker pool), keep the
  move that adds the most trades while the win rate stays within `tol` points of the START (default 0 = the same win rate), apply it, and go
  again from there - the next round tries the survivors of the last round (the top_k by trades added), every further step of the input just
  moved, and any lever the move unlocked (the Safe* zone inputs after the risk manager changed ...). It stops when no move adds `min_gain`
  trades within the tolerance, after `max_rounds`, or when Zee presses Stop. Every evaluated point goes on a trades-vs-win-rate frontier, so a
  point the greedy path did not take (more trades at a small win-rate cost) is still visible and savable.
  WHICH of the acceptable moves a round takes is `greedy` (GREEDY below; review 2026-11-08): 'most' = the most trades (the original rule; with a
  start below 100% it may take +100 trades with one new loss over +10 trades with none, because the win rate RISES - Zee's order is win rate,
  then fewest losses, then trades); 'free' = no new losses first, then the most trades; 'cheapest' = the most trades per win-rate point spent
  (with a tolerance > 0 'most' spends the whole budget on one big move where two cheaper moves would both have fit); 'auto' (default) = 'most'
  at tolerance 0, 'cheapest' above it. "Added trades' WR" is the TRUE marginal win rate: the two runs' trade lists are diffed by entry time,
  so a move that swaps trades (PreBreak, Htf5 1<->2, RiskMgr to 0, a detection rebuild) reports the win rate of the trades it ADDED and how
  many it dropped (`d_removed`), never a -50% or 140%.
  'Detection' levers (the InpDet* inputs) change WHICH setups exist: each value builds a setups file (~1-2 min, cached in simdata/det_cache) -
  they run last and only with include_det.
  Range-box strings (InpBandsB / InpBandsS, 21 chars of 0/1) are compared as TEXT (_eq): as floats the last four boxes (85-100%, beyond) vanish
  in the 21-digit float's ULP, so their moves were never offered and their change was dropped from a row's params (review 2026-11-08).

EVERY NUMBER HERE IS A TESTER ESTIMATE (Python): a hypothesis until MT5 / live fills confirm it. Say so in the UI."""
import concurrent.futures as cf
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("NUMBA_CPU_NAME", "generic")
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import detlab as DL  # noqa: E402
import uhv_engine as U  # noqa: E402
import uhv_filters as F  # noqa: E402
import scan as SCAN  # noqa: E402  (the grids G[...] / SPEC and the worker pool; importing it starts nothing)

SPLIT = 1782864000                                  # 1 Jul 2026 00:00 UTC: the Mar-Jun / Jul-Nov halves
GREEDY = ("auto", "most", "free", "cheapest")                    # how a round's pick is ranked - see the module doc
OPTS = {"tol": 0.0, "include_det": True, "max_rounds": 8, "min_gain": 5, "top_k": 30, "greedy": "auto"}
_fmt, _same = DL._fmt, DL._same
BANDS_DEFAULT = "1" * 21
BAND_KEYS = ("InpBandsB", "InpBandsS")


def _eq(key, a, b):
    """the same value? the range-box strings as text, everything else as detlab._same (numbers within 1e-9, 'true'/'false' as words)"""
    if key in BAND_KEYS:
        return str(a).strip().ljust(21, "1")[:21] == str(b).strip().ljust(21, "1")[:21]
    return _same(a, b)


# ====================================================================================================== reading the merged inputs
def _default(key):
    if key in U.UHV_DEFAULTS:
        return str(U.UHV_DEFAULTS[key][0])
    if key in U.DET_DEFAULT:
        return _fmt(U.DET_DEFAULT[key])
    if key in ("InpBandsB", "InpBandsS"):
        return BANDS_DEFAULT
    if key == "InpBandOff":
        return "1"
    return ""


def _cur(M, key):
    """the input's current value as a string ('' never: the engine's default fills a missing / blank one)"""
    v = str(M.get(key, "")).strip()
    return v if v != "" else _default(key)


def _num(M, key):
    return U.fv({key: _cur(M, key)}, key, 0.0)


def _grid(key):
    """the scanner's values for an input: detlab.P's grid where the Detector Lab has one, else scan.py's list"""
    spec = DL.P.get(key)
    if spec and spec.get("grid"):
        return [float(v) for v in spec["grid"]]
    s = SCAN.SPEC.get(key)
    if isinstance(s, tuple) and s[0] in ("list", "enum"):
        try:
            return [float(v) for v in s[1]]
        except (TypeError, ValueError):
            return []
    return []


def _up(M, key, grid=None):
    """grid values ABOVE the current one (0 excluded - 0 is 'off', a separate move)"""
    c = _num(M, key)
    return [v for v in (grid or _grid(key)) if v > c + 1e-9 and v > 0]


def _down(M, key, grid=None):
    """grid values BELOW the current one but above 0"""
    c = _num(M, key)
    return [v for v in (grid or _grid(key)) if 1e-9 < v < c - 1e-9]


def _words(key):
    """plain English for an input: its comment up to the first bracket, without the 'loss filter:' style prefix"""
    c = (U.UHV_DEFAULTS.get(key) or U.DET.get(key) or ("", ""))[1]
    c = c.split(" (")[0].split(". ")[0]
    if ":" in c and len(c.split(":")[0]) <= 24:
        c = c.split(":", 1)[1].strip()
    return (c[:110] + "…") if len(c) > 110 else c


NAMES = {                                           # shorter words for the inputs Zee meets most
    "InpUhvNoClose": "no entries in the New York rollover 16:45-17:45", "InpUhvFriCutAllNY": "Friday cut-off for every trade (NY hour)",
    "InpUhvFriCutNY": "Friday cut-off (NY hour)", "InpUhvLateUtcFrom": "late session: no entries from this UTC hour",
    "InpUhvHourFrom": "trade only from this UTC hour", "InpUhvHourTo": "trade only before this UTC hour", "InpUhvNewsNY": "no entries around US data",
    "InpUhvNewsMins": "minutes before US data", "InpUhvHoliday": "no entries on bank holidays", "InpUhvSunOpenMins": "quiet minutes after the Sunday open",
    "InpMaxPos": "positions open at the same time (0 = every setup)", "InpUhvMaxTrigSpread": "max spread at the breakout tick (pips)", "InpUhvMaxGapPips": "max gap through the level (pips)",
    "InpUhvMode": "which setups (0 every · 1 EA's own · 2 royal)", "InpUhvMinLaws": "laws needed", "InpUhvMinEr": "15-minute efficiency ratio at least",
    "InpUhvRiskMgr": "risk manager mode", "InpUhvPreBreak": "enter this many pips before the level", "InpUhvHarvestWins": "harvest: wins per trend",
    "InpUhvHarvestStopLoss": "harvest: a loss ends the trend", "InpUhvSaad": "all of Saad's entry filters", "InpBandOff": "a stood-aside range box still blocks the next trade",
    "InpDetCamPiv": "detection: camel hump size", "InpDetCamConfirm": "detection: humps that confirm a trend flip", "InpDetCamStrong": "detection: strong-trend louder breakout",
    "InpDetMaxHumps": "detection: EA hump budget", "InpDetPivot": "detection: retracement swing size", "InpDetTrendLook": "detection: trend look-back",
    "InpDetRetraceBack": "detection: retracement look-back", "InpDetUhvBody": "detection: UHV body share", "InpDetMomBody": "detection: breakout body share",
    "InpDetCooldown": "detection: EA cooldown candles",
}
for _k in ("Shape", "Trend", "Adx", "Atr", "Session", "Sides", "Chop", "Spread"):
    NAMES["InpUhvSaad" + _k] = f"Saad filter: {_k.lower()}"


def label(key):
    """NAMES, else the Detector Lab's slider label (it names the rule: 'Wick fake-break: candles back'), else the engine comment's words"""
    spec = DL.P.get(key)
    return NAMES.get(key) or (spec and spec.get("label")) or _words(key) or key


# ====================================================================================================== the levers
# {key, group, kind, gen(M) -> [value | (value, text) | (value, text, extra_params)]} - gen returns the LOOSER values from the current merged
# inputs M (values that let MORE trades through); extra_params ride along in the same move (the Saad master switch keeps its eight filters on).
# kind 'skip' = inside uhv_filters.skip (never runs under risk manager 2 or 4 - both trade only the secure zone / outside the risky zones, where
# the engine passes sec=True and skip() is never asked; runs only outside the secure zone under 1 / inside the risky zones under 3);
# 'engine' = always applied; 'det' = rebuilds the setups file.
LEVERS = []


def _lever(key, group, gen, kind="engine", gate=None):
    LEVERS.append({"key": key, "group": group, "kind": kind, "gen": gen, "gate": gate})


def _rm(M):
    return int(_num(M, "InpUhvRiskMgr"))


def _instant(M):
    return int(_num(M, "InpUhvEntry")) == 1 and not (_num(M, "InpTtdOn") > 0.5)


def _lf_on(M):
    return F.active(U.fv, M)


def _skip_runs(M):
    """do the skip() loss filters run at all? rm 2 takes only the secure zone and rm 4 skips the risky zones: in both every survivor is 'sec',
    so `if lf_on and not sec and skip(...)` never runs (review 2026-11-08: under rm 4, 28 skip-only levers ran the full engine for nothing)"""
    return _rm(M) not in (2, 4)


def _entry1(M):
    """instant entry (InpUhvEntry 1) - the engine applies MaxTrigSpread and MaxGapPips whenever it is, TTD on or off (review 2026-11-08:
    gating them on _instant hid both spread levers while the Turtle Trader Desk indicator was on)"""
    return int(_num(M, "InpUhvEntry")) == 1


def _on(key):
    return lambda M: _num(M, key) > 0


def _switch_off(M, key):
    return [0] if _num(M, key) > 0 else []


def _hours_later(M, key, hi):
    c = int(_num(M, key))
    return ([h for h in range(c + 1, hi + 1)] + [0]) if c > 0 else []


# ---- session
_lever("InpUhvNoClose", "session", lambda M: _switch_off(M, "InpUhvNoClose"))
_lever("InpUhvFriCutAllNY", "session", lambda M: _hours_later(M, "InpUhvFriCutAllNY", 16))
_lever("InpUhvFriCutNY", "session", lambda M: _hours_later(M, "InpUhvFriCutNY", 16), "skip")
_lever("InpUhvLateUtcFrom", "session", lambda M: _hours_later(M, "InpUhvLateUtcFrom", 23), "skip")
_lever("InpUhvHourFrom", "session", lambda M: list(range(int(_num(M, "InpUhvHourFrom")) - 1, -1, -1)) if _num(M, "InpUhvHourFrom") > 0 else [], "skip")
_lever("InpUhvHourTo", "session", lambda M: list(range(int(_num(M, "InpUhvHourTo")) + 1, 25)) if _num(M, "InpUhvHourTo") < 24 else [], "skip")
_lever("InpUhvNewsNY", "session", lambda M: _switch_off(M, "InpUhvNewsNY"), "skip")
_lever("InpUhvNewsMins", "session", lambda M: _down(M, "InpUhvNewsMins", [1, 2, 5, 10]), "skip", gate=_on("InpUhvNewsNY"))
_lever("InpUhvHoliday", "session", lambda M: _switch_off(M, "InpUhvHoliday"), "skip")
_lever("InpUhvSunOpenMins", "session", lambda M: _down(M, "InpUhvSunOpenMins") + _switch_off(M, "InpUhvSunOpenMins"), "skip")
def _wider(M, key, grid=None):
    """a 'skip when above X' gate that is ON: the grid values above X, then off. OFF (0) stays off - switching it on only removes trades"""
    return (_up(M, key, grid) + [0]) if _num(M, key) > 0 else []


# ---- positions (Zee 2026-11-09: the one-trade-at-a-time rule blocked 14,933 of 25,694 setups on the starter)
def _maxpos(M):
    """1 -> 2, 3, every setup; N -> N+1, every setup; 0 (every setup) has nothing looser"""
    cur = int(_num(M, "InpMaxPos")) if str(M.get("InpMaxPos", "1")).strip() not in ("", "None") else 1
    return [] if cur == 0 else ([2, 3, 0] if cur == 1 else [cur + 1, 0])
_lever("InpMaxPos", "positions", _maxpos)
# ---- spread (the breakout tick: instant entry only - the engine applies both gates only then, with or without the TTD indicator)
_lever("InpUhvMaxTrigSpread", "spread", lambda M: _wider(M, "InpUhvMaxTrigSpread", [0.7, 0.8, 1.0, 1.5, 2.0]), gate=_entry1)
_lever("InpUhvMaxGapPips", "spread", lambda M: _wider(M, "InpUhvMaxGapPips"), "skip", gate=_entry1)
# ---- setups (which setups are taken)
_lever("InpUhvMode", "setups", lambda M: list(range(int(_num(M, "InpUhvMode")) - 1, -1, -1)))
_lever("InpUhvMinLaws", "setups", lambda M: list(range(int(_num(M, "InpUhvMinLaws")) - 1, -1, -1)))
_lever("InpUhvMinEr", "setups", lambda M: _down(M, "InpUhvMinEr", [0.2, 0.3]) + _switch_off(M, "InpUhvMinEr"))


# ---- risk manager. 0 = loss filters EVERYWHERE; 1 = only outside the secure zone (looser than 0); 2 = only the secure zone is traded;
#      3 = loss filters only inside Zee's risky zones (looser than 0); 4 = the risky zones are skipped. Loosening: 2->1, 2->0, 4->3, 4->0 and,
#      with loss filters on, 0->1 / 0->3 (the filters act in fewer places). 1->0 and 3->0 are TIGHTER, so they are not levers here.
def _rm_moves(M):
    rm = _rm(M)
    if rm == 2:
        return [1, 0]
    if rm == 4:
        return [3, 0]
    if rm == 0 and _lf_on(M):
        return [1, 3]
    return []


_lever("InpUhvRiskMgr", "risk manager", _rm_moves)
_sec = lambda M: _rm(M) in (1, 2)                                  # the secure zone matters: wider zone = looser under both 1 and 2
_lever("InpUhvSafeHumpsMin", "risk manager", lambda M: _down(M, "InpUhvSafeHumpsMin"), gate=_sec)
_lever("InpUhvSafeHumpsMax", "risk manager", lambda M: _up(M, "InpUhvSafeHumpsMax"), gate=_sec)
_lever("InpUhvSafeErMin", "risk manager", lambda M: _down(M, "InpUhvSafeErMin") + _switch_off(M, "InpUhvSafeErMin"), gate=_sec)
_lever("InpUhvSafeErMax", "risk manager", lambda M: _up(M, "InpUhvSafeErMax"), gate=_sec)
_lever("InpUhvSafeRangeAtr", "risk manager", lambda M: _down(M, "InpUhvSafeRangeAtr") + _switch_off(M, "InpUhvSafeRangeAtr"), gate=_sec)
_zone = lambda M: _rm(M) in (3, 4)                                 # the risky zones matter: smaller zones = looser under both 3 and 4
for _k in ("InpUhvZStart", "InpUhvZEnd", "InpUhvZRange", "InpUhvZNews", "InpUhvZClose", "InpUhvZOpen"):
    _lever(_k, "risk manager", (lambda k: lambda M: _switch_off(M, k))(_k), gate=_zone)
_lever("InpUhvZSR", "risk manager", lambda M: _down(M, "InpUhvZSR") + _switch_off(M, "InpUhvZSR"), gate=_zone)
_lever("InpUhvZEndHumps", "risk manager", lambda M: _up(M, "InpUhvZEndHumps"), gate=lambda M: _zone(M) and _num(M, "InpUhvZEnd") > 0)
_lever("InpUhvZStartHumps", "risk manager", lambda M: _down(M, "InpUhvZStartHumps"), gate=lambda M: _zone(M) and _num(M, "InpUhvZStart") > 0)
_lever("InpUhvZRangeAtr", "risk manager", lambda M: _down(M, "InpUhvZRangeAtr"), gate=lambda M: _zone(M) and _num(M, "InpUhvZRange") > 0)


# ---- loss filters (the detectors' inputs): the REVERSE of detlab.TIGHTER's direction along the grid, plus 0 (= off) for the 'off' kind.
#      'nocheck' (BoxAtr / BoxVol): 0 DROPS the condition and fires MORE, so 0 is tighter - the looser values are the lower non-zero ones,
#      and from 0 any non-zero value adds a condition (looser).
_WIDER_GRID = {"InpUhvWallTouches": [1, 2, 3, 4, 5, 6]}            # the scanner grid stops at 4; detlab.P allows 6 (a wall needs more touches = fewer walls)


def _loosen_tighter(key):
    d, z = DL.TIGHTER[key]
    g = _WIDER_GRID.get(key) or _grid(key)

    def gen(M):
        c = _num(M, key)
        if z == "off":
            if c <= 0:
                return []                                            # off: switching it on only removes trades
            return (_down(M, key, g) if d == "up" else _up(M, key, g)) + [0]
        if z == "nocheck":
            if c <= 0:
                return [v for v in g if v > 0]
            return _down(M, key, g) if d == "up" else _up(M, key, g)
        return _down(M, key, g) if d == "up" else _up(M, key, g)    # structural threshold (no off value)
    return gen


_LF_GATE = {                                                       # a structural threshold matters only while its rule is on
    "InpUhvBoxAtr": _on("InpUhvBoxInside"), "InpUhvBoxVol": _on("InpUhvBoxInside"), "InpUhvZRangeAtr": None,
    "InpUhvSellSupLast": lambda M: _num(M, "InpUhvSellSup") > 0 or _num(M, "InpUhvBuyRes") > 0, "InpUhvWallTouches": _on("InpUhvWall"),
    "InpUhvFreshSwings": _on("InpUhvFreshBreak"), "InpUhvBrokeLook": _on("InpUhvBrokeHighs"), "InpUhvWickBars": _on("InpUhvWickFake"),
}
_NOT_SKIP = {"InpUhvBoxAtr", "InpUhvBoxVol", "InpUhvSellSup", "InpUhvBuyRes", "InpUhvSellSupLast", "InpUhvWall", "InpUhvWallTouches"}   # into_major / into_wall / in_quiet_box run at every risk mode
for _k in DL.TIGHTER:
    if _k == "InpUhvZRangeAtr":
        continue                                                     # a zone input: in the risk manager group above
    _lever(_k, "loss filters", _loosen_tighter(_k), "engine" if _k in _NOT_SKIP else "skip", gate=_LF_GATE.get(_k))
# enum switches -> off (and the looser mode where the modes are ordered)
for _k in ("InpUhvWickFake", "InpUhvNoLowerHigh", "InpUhvShiftEma", "InpUhvShiftStoch", "InpUhvShiftAvwap"):
    _lever(_k, "loss filters", (lambda k: lambda M: _switch_off(M, k))(_k), "skip")
_lever("InpUhvBoxInside", "loss filters", lambda M: _switch_off(M, "InpUhvBoxInside"))
_lever("InpUhvStruct", "loss filters", lambda M: {1: [2, 0], 2: [0]}.get(int(_num(M, "InpUhvStruct")), []), "skip")        # 1 = HH and HL, 2 = only the HH: 2 is looser
_lever("InpUhvV2Against", "loss filters", lambda M: {2: [1, 0], 1: [0]}.get(int(_num(M, "InpUhvV2Against")), []), "skip")  # 2 = only WITH the trend, 1 = not against: 1 is looser
_lever("InpUhvHtf5", "loss filters", lambda M: {1: [0, 2], 2: [0, 1]}.get(int(_num(M, "InpUhvHtf5")), []), "skip")        # the two modes are not ordered: off, and the other
# thresholds outside detlab.P: (key, looser direction, grid)
for _k, _d, _g in (("InpUhvMaxHumps", "up", [2, 3, 4, 5, 6, 8]), ("InpUhvMinHumps", "down", [2, 3, 4]), ("InpUhvDeepRet", "up", [0.5, 0.6, 0.7, 0.8, 0.9]),
                   ("InpUhvRunPips", "up", [4, 6, 8, 10, 15]), ("InpUhvLoudBrk", "up", [0.7, 0.8, 0.9, 0.95]), ("InpUhvSpikeAtr", "up", [2, 3, 4, 5]),
                   ("InpUhvMaxStopPips", "up", [1, 2, 3, 5]), ("InpUhvMinBrkRatio", "down", [0.05, 0.1, 0.2]), ("InpUhvMinMoveAtr", "up", [0.5, 1, 2]),
                   ("InpUhvMaxRunAtr", "up", [3, 4, 5, 6])):
    _lever(_k, "loss filters", (lambda k, d, g: lambda M: ((_up(M, k, g) if d == "up" else _down(M, k, g)) + [0]) if _num(M, k) > 0 else [])(_k, _d, _g), "skip")
_lever("InpUhvHarvestWins", "loss filters", lambda M: ([int(_num(M, "InpUhvHarvestWins")) + 1, int(_num(M, "InpUhvHarvestWins")) + 2, 0]) if _num(M, "InpUhvHarvestWins") > 0 else [])
_lever("InpUhvHarvestStopLoss", "loss filters", lambda M: _switch_off(M, "InpUhvHarvestStopLoss"), gate=_on("InpUhvHarvestWins"))
# ---- Saad's switches: 'true' -> 'false' (with InpUhvSaad on, every single switch is already on - only the master switch is a move).
#      The master ALSO switches Saad's exits (uhv_engine: InpBeUsd / InpLockAtUsd / InpCoolBars / InpDayLossUsd / InpDayTargetUsd all read
#      '... if saad else 0'). Geometry is frozen here, so: with those five at 0 the master off is a pure gate move; otherwise the move keeps
#      the eight filters ON and says out loud that the exits change (review 2026-11-08) - the eight single switches then loosen one by one.
_SAAD_SW = ("Shape", "Trend", "Adx", "Atr", "Session", "Sides", "Chop", "Spread")
_SAAD_EXITS = ("InpBeUsd", "InpLockAtUsd", "InpCoolBars", "InpDayLossUsd", "InpDayTargetUsd")


def _saad_master(M):
    if _num(M, "InpUhvSaad") <= 0.5:
        return []
    if all(_num(M, k) <= 0 for k in _SAAD_EXITS):
        return ["false"]
    return [("false", "all of Saad's entry filters: master off, the eight filters kept on (ALSO drops Saad's break-even / lock / cool-down / day limits - the exits change)",
             {"InpUhvSaad" + k: "true" for k in _SAAD_SW})]


_lever("InpUhvSaad", "saad", _saad_master)
for _k in _SAAD_SW:
    _lever("InpUhvSaad" + _k, "saad", (lambda k: lambda M: ["false"] if _num(M, k) > 0.5 else [])("InpUhvSaad" + _k), gate=lambda M: _num(M, "InpUhvSaad") < 0.5)


# ---- range boxes: every '0' box -> '1' (traded), one move per box; InpBandOff 1 -> 0 while any box stands aside (the ghost stops blocking)
def _box_moves(side_key, word):
    def gen(M):
        b = _cur(M, side_key).ljust(21, "1")[:21]
        out = []
        for i, ch in enumerate(b):
            if ch == "0":
                to = b[:i] + "1" + b[i + 1:]
                rng = f"{i * 5}-{(i + 1) * 5}%" if i < 20 else "beyond 100%"
                out.append((to, f"{word} box {rng}: stand aside → trade"))
        return out
    return gen


_lever("InpBandsB", "range boxes", _box_moves("InpBandsB", "BUY"))
_lever("InpBandsS", "range boxes", _box_moves("InpBandsS", "SELL"))
_lever("InpBandOff", "range boxes", lambda M: [0] if _num(M, "InpBandOff") > 0.5 else [],
       gate=lambda M: "0" in _cur(M, "InpBandsB").ljust(21, "1")[:21] + _cur(M, "InpBandsS").ljust(21, "1")[:21])
# ---- entry: the pre-break offset is not monotone (earlier entry = more breaks reached, but more fakes): the engine judges every other value
_lever("InpUhvPreBreak", "entry", lambda M: [v for v in (0, 0.5, 1, 1.5, 2) if not _same(v, _num(M, "InpUhvPreBreak"))], gate=_instant)


# ---- detection (SLOW: a setups file per value). With instant entry only the inputs that shape the ROUGHS (the waiting UHV levels) matter:
#      CamStrong / MaxHumps / Cooldown / MomBody only tag the candle-close fires ('ea'), so they are levers for InpUhvEntry 0 only.
def _candle_close(M):
    return not _instant(M)


def _ea_tag(M):
    return _candle_close(M) and int(_num(M, "InpUhvMode")) in (1, 2)


_lever("InpDetCamPiv", "detection", lambda M: _down(M, "InpDetCamPiv", [1, 2, 3, 4, 5]), "det")
_lever("InpDetCamConfirm", "detection", lambda M: _down(M, "InpDetCamConfirm", [1, 2, 3]), "det")
_lever("InpDetCamStrong", "detection", lambda M: ([2] if _num(M, "InpDetCamStrong") <= 0 else _down(M, "InpDetCamStrong", [2, 3, 4])), "det", gate=_candle_close)   # 0 = never louder: the strict value
_lever("InpDetMaxHumps", "detection", lambda M: _up(M, "InpDetMaxHumps", [4, 5, 99]), "det", gate=_ea_tag)
_lever("InpDetPivot", "detection", lambda M: _down(M, "InpDetPivot", [2, 3, 4, 5]), "det")
_lever("InpDetTrendLook", "detection", lambda M: [v for v in (10, 15, 30) if not _same(v, _num(M, "InpDetTrendLook"))], "det")
_lever("InpDetRetraceBack", "detection", lambda M: [v for v in (15, 30) if not _same(v, _num(M, "InpDetRetraceBack"))], "det")
_lever("InpDetUhvBody", "detection", lambda M: _down(M, "InpDetUhvBody", [0.3, 0.4, 0.5, 0.6, 0.7]) + _switch_off(M, "InpDetUhvBody"), "det")
_lever("InpDetMomBody", "detection", lambda M: _down(M, "InpDetMomBody", [0.5, 0.6, 0.7, 0.8, 0.9]) + _switch_off(M, "InpDetMomBody"), "det", gate=_candle_close)
_lever("InpDetCooldown", "detection", lambda M: _down(M, "InpDetCooldown", [1, 3, 5, 10]) + _switch_off(M, "InpDetCooldown"), "det", gate=_ea_tag)

GROUPS = ["session", "positions", "spread", "setups", "risk manager", "loss filters", "saad", "range boxes", "entry", "detection"]
FROZEN = ("InpUhvStopMode", "InpUhvSlBeyond", "InpUhvRR", "InpUhvFixTp", "InpUhvBeR", "InpUhvTpPips", "InpUhvSlPips", "InpUhvLatency", "InpUhvLossSecs",
          "InpUhvMaxSecs", "InpUhvLots", "InpUhvEntry")           # never moved (+ every InpTtd* / InpX* and the structural look-backs)


def moves(M, include_det=True):
    """the loosening moves from the merged inputs M: [{key, group, kind, label, from, to, change, params: {key: to}}], detection last, deduped"""
    M = {k: str(v) for k, v in (M or {}).items()}
    out, seen = [], set()
    for L in LEVERS:
        if L["group"] == "detection" and not include_det:
            continue
        if L["gate"] and not L["gate"](M):
            continue
        if L["kind"] == "skip" and not _skip_runs(M):
            continue
        key = L["key"]
        cur = _cur(M, key)
        try:
            vals = L["gen"](M)
        except Exception:  # noqa: BLE001 - a bad input value must not kill the scan
            vals = []
        for v in vals:
            text, extra = None, {}
            if isinstance(v, tuple):
                tup = v
                v, text = tup[0], tup[1]
                extra = dict(tup[2]) if len(tup) > 2 and tup[2] else {}    # (value, text, extra_params): the move sets more than one input
            to = str(v) if isinstance(v, str) else _fmt(v)
            if _eq(key, to, cur) or (key, to) in seen:
                continue
            seen.add((key, to))
            frm = cur if key in BAND_KEYS else _fmt(cur) if cur not in ("true", "false") else cur
            if text is None:
                tv = "off" if (to == "0" and key not in ("InpUhvMode", "InpUhvHourFrom", "InpUhvRiskMgr", "InpBandOff", "InpUhvMinLaws", "InpDetCamStrong", "InpDetCooldown")) else to
                text = f"{label(key)}: {frm} → {tv}"
            out.append({"key": key, "group": L["group"], "kind": L["kind"], "label": label(key), "from": frm, "to": to, "change": text, "params": dict(extra, **{key: to})})
    out.sort(key=lambda m: GROUPS.index(m["group"]) if m["group"] in GROUPS else 99)   # fast levers first, detection builds last
    return out


def levers_report(M, include_det=True):
    """{group: [{key, from, to: [..]}]} with counts - for the console and the page's 'what will it try' line"""
    mv = moves(M, include_det)
    by = {}
    for m in mv:
        g = by.setdefault(m["group"], {})
        e = g.setdefault(m["key"], {"key": m["key"], "label": m["label"], "from": m["from"], "to": []})
        e["to"].append(m["to"])
    return {"groups": {g: list(v.values()) for g, v in by.items()}, "counts": {g: sum(len(e["to"]) for e in v.values()) for g, v in by.items()}, "total": len(mv)}


# ====================================================================================================== one full engine run
def _part(X):
    n = int(len(X))
    w = int((X[:, 6] > 0).sum()) if n else 0
    return {"trades": n, "wins": w, "losses": n - w, "wr": round(100.0 * w / max(n, 1), 2), "net": round(float(X[:, 6].sum()), 2) if n else 0.0}


def run(inputs):
    """one FULL engine run (in a scan worker or inline) -> the numbers, the halves, the skip counts. Module-level so the pool can pickle it."""
    os.environ.setdefault("NUMBA_CPU_NAME", "generic")
    t0 = time.time()
    tr, _, cnt = U.simulate(inputs)
    R = tr[tr[:, 10] == 0] if len(tr) else tr
    D = DL._D(); t1 = np.asarray(D["t1"], dtype=np.int64)
    days = len(np.unique(t1 // 86400))                            # as detlab._summ: every day with data
    out = _part(R)
    out.update(per_day=round(out["trades"] / max(days, 1), 2), days=days,
               h1=_part(R[R[:, 1] < SPLIT]) if len(R) else _part(R), h2=_part(R[R[:, 1] >= SPLIT]) if len(R) else _part(R),
               skips={k: int(v) for k, v in cnt.items()}, ghosts=int((tr[:, 10] == 1).sum()) if len(tr) else 0, secs=round(time.time() - t0, 1),
               # the trades by entry time (one trade at a time, so the entry tick identifies a trade): on_row diffs two runs with them for the
               # TRUE marginal win rate of the trades a move added (kept out of the result's JSON by _summary / _public)
               t_in=[float(x) for x in R[:, 1]] if len(R) else [], win_t=[float(x) for x in R[R[:, 6] > 0, 1]] if len(R) else [])
    return out


def _public(s):
    """a run's result without the trade lists (the JSON the page gets)"""
    return {k: v for k, v in s.items() if k not in ("t_in", "win_t")}


BLOCK_NAMES = {"band_skip": "sessions, setup rules, Saad hours & range boxes", "spread_reject": "spread at the breakout tick", "loss_filter": "loss filters (detectors, risk manager, harvest)",
               "busy": "busy (one trade at a time)", "adx": "Saad ADX", "atr_band": "Saad ATR band", "no_break": "Saad candle shape", "gap": "gap", "risk": "risk"}


def ceiling(base):
    """where the setups go: setups = taken + stood-aside ghosts + blocked (by group) + busy + unexplained (no tick / no fill within 24 h)"""
    sk = dict(base.get("skips") or {})
    setups, taken, ghosts = int(sk.get("setups", 0)), int(base["trades"]), int(base.get("ghosts", 0))
    blocked = {}
    for k, v in sk.items():
        if k in ("setups", "open_at_end", "open_since") or k.startswith("mt5_") or not v:
            continue
        blocked[k] = int(v) - (ghosts if k == "band_skip" else 0)   # the engine counts a stood-aside ghost under band_skip
    other = setups - taken - ghosts - sum(blocked.values())
    return {"setups": setups, "taken": taken, "per_day": base["per_day"], "days": base.get("days"), "ghosts": ghosts, "blocked": blocked, "names": BLOCK_NAMES,
            "unexplained": other, "note": "a setup is counted once, at the first rule that stops it; 'unexplained' = no tick / no fill within 24 h"}


# ====================================================================================================== the hungry path
def _summary(s):
    return {k: s[k] for k in ("trades", "wins", "losses", "wr", "net", "per_day", "h1", "h2") if k in s}


def _pool():
    try:
        return SCAN._pool()
    except Exception:  # noqa: BLE001 - no spawn / frozen numba: run inline
        return None


def _diff(M, saved):
    """the FULL diff of the merged inputs vs the saved setting's file (what Apply / Save need); range boxes compared as text (_eq)"""
    return {k: v for k, v in M.items() if not _eq(k, v, saved[k] if k in saved else _default(k))}


def _evaluate(cands, Mc, pool, job, on_row, memo):
    """every candidate through the engine (pool or inline); on_row(move, result) as each lands; stops between candidates when job['stop']"""
    todo = []
    for m in cands:
        Mi = DL.final_inputs(m["params"], Mc)
        sig = tuple(sorted(Mi.items()))
        if sig in memo:
            on_row(m, memo[sig])
            continue
        todo.append((m, Mi, sig))
    if not todo:
        return
    if pool is None:
        for m, Mi, sig in todo:
            if job.get("stop"):
                return
            try:
                s = run(Mi); memo[sig] = s; on_row(m, s)
            except Exception as e:  # noqa: BLE001
                on_row(m, {"error": f"{type(e).__name__}: {str(e)[:120]}"})
        return
    futs = {}
    for m, Mi, sig in todo:
        try:
            futs[pool.submit(run, Mi)] = (m, sig)
        except Exception:  # noqa: BLE001 - the pool died: the rest inline
            try:
                s = run(Mi); memo[sig] = s; on_row(m, s)
            except Exception as e:  # noqa: BLE001
                on_row(m, {"error": f"{type(e).__name__}: {str(e)[:120]}"})
    pending, broken = set(futs), []
    while pending:
        if job.get("stop"):
            for f in pending:
                f.cancel()                                           # the queued ones; a running engine call finishes on its own
            return
        done, pending = cf.wait(pending, timeout=0.5, return_when=cf.FIRST_COMPLETED)
        for f in done:
            m, sig = futs[f]
            try:
                s = f.result(); memo[sig] = s; on_row(m, s)
            except cf.process.BrokenProcessPool:                     # a worker died (a killed pool, a crash): drop the pool, finish these inline
                broken.append((m, sig))
            except Exception as e:  # noqa: BLE001 - one bad value must not kill the scan
                on_row(m, {"error": f"{type(e).__name__}: {str(e)[:120]}"})
    if broken:
        try:
            SCAN._drop_pool()
        except Exception:  # noqa: BLE001
            pass
        Mi_by = {id(m): Mi for m, Mi, _ in todo}
        for m, sig in broken:
            if job.get("stop"):
                return
            try:
                s = run(Mi_by[id(m)]); memo[sig] = s; on_row(m, s)
            except Exception as e:  # noqa: BLE001
                on_row(m, {"error": f"{type(e).__name__}: {str(e)[:120]}"})


def hungry(setting_file, inputs=None, params=None, opts=None, job=None):
    """the greedy path (see the module doc). job: detlab.new_job(); job['stop'] = True stops it between candidates.
    job['result'] = {base, start, path, rounds, frontier, ceiling, opts, evaluations, secs, stopped, why_stopped, note}"""
    job = job if job is not None else DL.new_job("hungry")
    o = dict(OPTS, **{k: v for k, v in (opts or {}).items() if v is not None})
    tol, inc_det = max(0.0, float(o["tol"])), bool(o["include_det"])
    max_rounds, min_gain, top_k = max(1, int(o["max_rounds"])), max(1, int(o["min_gain"])), max(5, int(o["top_k"]))
    t0 = time.time()
    try:
        p, rec = DL._setting(setting_file)
        inputs = inputs if inputs is not None else rec["inputs"]
        saved = {k: str(v) for k, v in (rec.get("inputs") or {}).items()}
        start = {k: str(v) for k, v in (params or {}).items()}
        M0 = DL.final_inputs(start, inputs)
        job.update(phase="the starting point (full engine run)", progress=0, total=1, done=False, error=None, stop=False)
        base = run(M0)
        point0 = dict(_summary(base), step=0, round=0, change="the setting" + (" + your sliders" if start else ""), key=None, params=_diff(M0, saved), m_wr=None,
                      d_trades=0, d_losses=0, d_wr=0.0, d_per_day=0.0)
        greedy = str(o.get("greedy") or "auto")
        if greedy not in GREEDY:
            greedy = "auto"
        rank = ("most" if tol <= 0 else "cheapest") if greedy == "auto" else greedy
        o["greedy"], o["rank"] = greedy, rank
        res = {"base": _public(base), "start": start, "setting": p.stem, "path": [point0], "rounds": [], "frontier": [], "ceiling": ceiling(base), "opts": o,
               "levers": levers_report(M0, inc_det), "evaluations": 0, "secs": 0, "stopped": False, "why_stopped": None,
               "note": "every row is a FULL engine run - a TESTER ESTIMATE (Python), a hypothesis until MT5 / live fills confirm it; "
                       "the trade geometry (stops, targets, latency, lots) is frozen - only the gates that decide WHICH setups are taken move"}
        job.update(result=res)
        pool = _pool()
        memo = {}
        allpts = [dict(point0, on_path=True)]
        pt_of = {}                                                   # id(row) -> its allpts entry: the pick's entry is MARKED on_path, not appended twice (review 2026-11-08)
        cur, Mc, cur_diff = base, dict(M0), _diff(M0, saved)
        prev_rows, prev_keys, stepped = None, None, None
        for r in range(1, max_rounds + 1):
            if job.get("stop"):
                break
            every = moves(Mc, inc_det)
            keys_now = {m["key"] for m in every}
            if r == 1 or prev_rows is None:
                cands = every
            else:                                                    # the survivors of the last round, the input just stepped, the newly unlocked levers
                good = [x for x in prev_rows if "error" not in x and x["wr"] >= base["wr"] - tol - 0.25]
                good.sort(key=lambda x: (-x["d_trades"], x["losses"]))
                keep = {(x["key"], x["to"]) for x in good[:top_k]}
                cands = [m for m in every if (m["key"], m["to"]) in keep or m["key"] == stepped or m["key"] not in prev_keys]
            prev_keys = keys_now
            for i_c, m in enumerate(cands):
                m["order"] = i_c                                     # the lever order lists the mildest loosening first: the tie-break (runs 2026-11-08 picked MaxTrigSpread 1.5 once, 2 the next)
            rd = {"round": r, "from": _summary(cur), "candidates": len(cands), "rows": [], "pick": None, "secs": 0,
                  "slow": sum(1 for m in cands if m["kind"] == "det")}
            res["rounds"].append(rd)
            best = {"trades": cur["trades"], "per_day": cur["per_day"], "wr": cur["wr"], "losses": cur["losses"]}   # the phase line's "best so far"
            n_done = [0]
            tr0 = time.time()
            cur_set, cur_win = set(cur.get("t_in") or []), set(cur.get("win_t") or [])

            def phase():
                job.update(progress=n_done[0], total=len(cands),
                           phase=f"round {r} · {n_done[0]} of {len(cands)} candidates · best so far {best['trades']:,} trades ({best['per_day']:.1f}/day) at {best['wr']:.2f}%"
                                 + (f" · {rd['slow']} detection builds (slow)" if rd["slow"] else ""))

            def on_row(m, s, _rd=rd, _cur=cur, _diff0=cur_diff, _cs=cur_set, _cw=cur_win):
                n_done[0] += 1
                row = dict(m)
                row["params"] = dict(_diff0, **m["params"])          # the FULL diff vs the saved setting: Apply / Save in one click
                row["params"] = {k: v for k, v in row["params"].items() if not _eq(k, v, saved[k] if k in saved else _default(k))}
                if "error" in s:
                    row.update(error=s["error"], ok=False)
                    _rd["rows"].append(row)
                else:
                    row.update(_summary(s), secs=s.get("secs"))
                    dt = s["trades"] - _cur["trades"]
                    # the TRUE marginal win rate: the trades this run has that the current point has not (by entry time) and how many it won;
                    # d_removed = the current point's trades it dropped (PreBreak, Htf5 1<->2, RiskMgr to 0, a detection rebuild swap trades:
                    # Δwins/Δtrades gave -50% or 140% there - review 2026-11-08)
                    new_t = [t for t in (s.get("t_in") or []) if t not in _cs]
                    new_w = sum(1 for t in (s.get("win_t") or []) if t not in _cs)
                    removed = len(_cs) - (len(s.get("t_in") or []) - len(new_t)) if _cs or s.get("t_in") else max(0, -dt)
                    row.update(d_trades=dt, d_per_day=round(s["per_day"] - _cur["per_day"], 2), d_losses=s["losses"] - _cur["losses"], d_wr=round(s["wr"] - _cur["wr"], 2),
                               m_wr=(round(100.0 * new_w / len(new_t), 1) if new_t else None), d_added=len(new_t), d_removed=int(removed),
                               # ok = enough new trades within the tolerance, OR "free" trades: more trades and not one more loss (integration 2026-11-08:
                               # NewsNY 1->off added +2 at 0 losses and min_gain 5 refused it - a hungry scanner takes every free trade)
                               ok=bool((dt >= min_gain and s["wr"] >= base["wr"] - tol - 1e-9) or (dt > 0 and s["losses"] <= _cur["losses"] and s["wr"] >= base["wr"] - tol - 1e-9)))
                    _rd["rows"].append(row)
                    apt = {"trades": s["trades"], "wr": s["wr"], "losses": s["losses"], "per_day": s["per_day"], "net": s["net"], "params": row["params"],
                           "change": row["change"], "key": row["key"], "to": row["to"], "round": r, "h1": s["h1"], "h2": s["h2"], "m_wr": row["m_wr"],
                           "d_trades": dt, "d_losses": row["d_losses"], "d_removed": row["d_removed"]}
                    allpts.append(apt); pt_of[id(row)] = apt
                    if row["ok"] and (s["trades"], -s["losses"]) > (best["trades"], -best["losses"]):
                        best.update(trades=s["trades"], per_day=s["per_day"], wr=s["wr"], losses=s["losses"])
                _rd["rows"].sort(key=lambda x: (x.get("error") is not None, not x.get("ok"), -x.get("trades", -1), x.get("losses", 1e9), -(x.get("m_wr") or 0), x.get("order", 0)))
                res["evaluations"] += 1; res["secs"] = round(time.time() - t0, 1); _rd["secs"] = round(time.time() - tr0, 1)
                phase()

            phase()
            _evaluate(cands, Mc, pool, job, on_row, memo)
            if job.get("stop"):
                break
            ok = [x for x in rd["rows"] if x.get("ok")]
            if not ok:
                res["why_stopped"] = "no lever adds trades within the tolerance" if cands else "no lever left to loosen"
                break
            # the pick (module doc, GREEDY): 'most' = most trades; 'free' = no new losses first, then most trades; 'cheapest' = most trades per
            # win-rate point spent vs the START (a move at or above the start's win rate costs 0.01 -> ranks first)
            if rank == "free":
                ok.sort(key=lambda x: (max(0, x["d_losses"]), -x["trades"], -(x["m_wr"] or 0), x.get("order", 0)))
            elif rank == "cheapest":
                ok.sort(key=lambda x: (-(x["d_trades"] / max(base["wr"] - x["wr"], 0.01)), -x["trades"], x["losses"], x.get("order", 0)))
            else:
                ok.sort(key=lambda x: (-x["trades"], x["losses"], -(x["m_wr"] or 0), x.get("order", 0)))
            pick = ok[0]
            rd["pick"] = {"key": pick["key"], "to": pick["to"], "change": pick["change"], "rank": rank}
            Mc = DL.final_inputs(pick["params"], inputs)             # the saved inputs + the full diff = the new current point
            cur = memo.get(tuple(sorted(Mc.items()))) or run(Mc)
            cur_diff = _diff(Mc, saved)
            stepped = pick["key"]
            pt = dict(_summary(cur), step=len(res["path"]), round=r, change=pick["change"], key=pick["key"], to=pick["to"], params=cur_diff,
                      m_wr=pick["m_wr"], d_trades=pick["d_trades"], d_losses=pick["d_losses"], d_wr=pick["d_wr"], d_per_day=pick["d_per_day"],
                      d_added=pick.get("d_added"), d_removed=pick.get("d_removed"))
            res["path"].append(pt)
            apt = pt_of.get(id(pick))
            if apt is not None:
                apt.update(on_path=True, step=pt["step"])            # the frontier / the chart see ONE dot for the step, and it knows it is a path step
            else:
                allpts.append(dict(pt, on_path=True))
            prev_rows = rd["rows"]
            if r == max_rounds:
                res["why_stopped"] = f"{max_rounds} rounds done (🍖 Keep hunting from the last step, or pick more rounds)"
        if job.get("stop"):
            res["stopped"], res["why_stopped"] = True, "stopped by you"
        # the frontier: the Pareto set over (trades up, win rate up) of every evaluated point, the start included
        pts = sorted(allpts, key=lambda x: (-x["trades"], -x["wr"]))
        front, best_wr = [], -1.0
        for x in pts:
            if x["wr"] > best_wr + 1e-9:
                front.append(x); best_wr = x["wr"]
        res["frontier"] = sorted(front, key=lambda x: x["trades"])
        res["points"] = [{k: x.get(k) for k in ("trades", "wr", "losses", "per_day", "change", "round", "step", "on_path", "m_wr", "d_trades", "d_removed")} for x in allpts]
        res["secs"] = round(time.time() - t0, 1)
        last = res["path"][-1]
        res["gain"] = {"trades": last["trades"] - base["trades"], "per_day": round(last["per_day"] - base["per_day"], 2), "losses": last["losses"] - base["losses"],
                       "wr": round(last["wr"] - base["wr"], 2), "steps": len(res["path"]) - 1}
        job.update(result=res, done=True, phase="stopped" if res["stopped"] else "done", progress=job.get("total") or 1)
        return res
    except Exception as e:  # noqa: BLE001 - the job dict carries the error
        job.update(error=f"{type(e).__name__}: {e}", done=True, phase="error")
        raise


def hungry_async(setting_file, inputs=None, params=None, opts=None, job=None):
    job = job if job is not None else DL.new_job("hungry")
    threading.Thread(target=lambda: DL._quiet(hungry, setting_file, inputs, params, opts, job), daemon=True).start()
    return job


if __name__ == "__main__":                                    # python hungry.py "<saved setting>" [tol] [rounds] [det 0/1]
    import json as _json
    f = sys.argv[1] if len(sys.argv) > 1 else "2026-11-07 12-09-37 + New Detector 100 percent at 976"
    p, rec = DL._setting(f)
    rep = levers_report(rec["inputs"], include_det=True)
    for g, rows in rep["groups"].items():
        print(f"\n[{g}] {rep['counts'][g]} moves")
        for e in rows:
            print(f"  {e['key']:26s} {e['from']!s:>8} -> {', '.join(e['to'])}")
    print("\ntotal", rep["total"])
    if len(sys.argv) > 2:
        job = DL.new_job("hungry")
        res = hungry(f, None, None, {"tol": float(sys.argv[2]), "max_rounds": int(sys.argv[3]) if len(sys.argv) > 3 else 2,
                                     "include_det": bool(int(sys.argv[4])) if len(sys.argv) > 4 else False}, job)
        print(_json.dumps({"base": _summary(res["base"]), "path": [(x["step"], x["change"], x["trades"], x["losses"], x["wr"]) for x in res["path"]],
                           "why": res["why_stopped"], "secs": res["secs"]}, indent=1))
