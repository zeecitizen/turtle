"""scan.py - "Scan every setting" (Zee 2026-10-21: "can you include every single setting that we have in the Scan the levers. so i keep pressing trade this
for that until we're done gaining everything we can from all the settings on earth we have").

From the research bench (the settings on screen + the bench's changes + the bench's Exit Lab exit), every setting the EA has - the lines, the candle,
the location, the trigger, the filters, each range box, the stop, the exit and the 27 Exit Lab settings (EA v1.30 InpX*) - is moved a few steps either
way, one at a time, and each move runs on the data AS EA SETTINGS (the bench's Exit Lab exit too: InpX*, exactly what MT5 runs). Only settings that can
act are tried (e.g. the sweep settings only with the sweep entry, the fallback only in exit mode 1 without a target). Sizing (lots, risk %) is left to
Mission Control. The runs go to a few worker processes (kept while in use, shut after 10 idle minutes).
Python tester numbers: hypotheses until MT5 confirms them ("Check in MT5" after applying)."""
import concurrent.futures as cf
import multiprocessing as mp
import os
import threading
import time

os.environ.setdefault("NUMBA_CPU_NAME", "generic")

# (kind, lo, hi, step) | ("enum", [values]) | ("list", [values]) | "bool"
G_SAAD = {   # the original Turtle TV's list (kept for reference; TurtleTVUHV scans G below)
    "the lines": {"InpEmaFast": ("int", 3, 60, 1), "InpEmaSlow": ("int", 10, 200, 2)},
    "the candle": {"InpWickMin": ("num", 0.1, 0.9, 0.05), "InpBodyMax": ("num", 0.1, 0.9, 0.05), "InpNoseMax": ("num", 0.0, 0.6, 0.05),
                   "InpMaruBody": ("num", 0.3, 0.95, 0.05), "InpHamRatio": ("num", 1.0, 5.0, 0.25), "InpHamNose": ("num", 0.1, 0.9, 0.05),
                   "InpMinRangeAtr": ("num", 0.0, 1.5, 0.05), "InpUsePin": "bool", "InpMarubozu": "bool", "InpHammer": "bool", "InpStar": "bool",
                   "InpPinDir": "bool", "InpPinColor": "bool"},
    "where": {"InpTouchPips": ("num", 0, 10, 0.5), "InpTouchMode": ("enum", [0, 1]), "InpLongRule": ("enum", [0, 1, 2]), "InpShortLine": ("enum", [0, 1, 2]),
              "InpLongExitAbove": "bool", "InpSkipBothEma": "bool"},
    "the trigger": {"InpBreakBars": ("int", 1, 6, 1), "InpBreakPips": ("num", 0, 20, 1), "InpTrigBid": "bool", "InpEntryMode": ("enum", [0, 1, 2]),
                    "InpRetestFrac": ("num", 0.1, 0.9, 0.1), "InpRetestBars": ("int", 1, 8, 1), "InpSweepPips": ("num", 0, 30, 2), "InpSweepBars": ("int", 1, 8, 1),
                    "InpSweepEntry": ("enum", [0, 1]), "InpSweepSlPips": ("num", 0, 40, 5)},
    "filters": {"InpAdxMin": ("num", 0, 50, 1), "InpAdxPeriod": ("int", 7, 28, 1), "InpAtrMinUsd": ("num", 0, 10, 0.5), "InpAtrMaxUsd": ("num", 0, 40, 2),
                "InpSessFrom": ("int", 0, 23, 1), "InpSessTo": ("int", 1, 24, 1), "InpSkipDow": ("enum", [-1, 1, 2, 3, 4, 5]), "InpNoNewMins": ("int", 0, 240, 15),
                "InpChopEr": ("num", 0, 0.5, 0.05), "InpChopErLook": ("int", 4, 40, 2), "InpHtfMin": ("enum", [0, 15, 30, 60, 240]), "InpHtfEma": ("int", 10, 100, 5),
                "InpTrendAlign": "bool", "InpPriceSide": "bool", "InpSlopePips": ("num", 0, 40, 2.5), "InpSlopeLook": ("int", 2, 20, 1),
                "InpEmaGapPips": ("num", 0, 40, 2.5), "InpMaxSpreadPts": ("int", 0, 100, 10), "InpGapCancel": "bool", "InpCoolBars": ("int", 0, 16, 1),
                "InpBuys": "bool", "InpSells": "bool", "InpMaxPos": ("int", 1, 4, 1), "InpReplace": "bool", "InpExtraDir": ("enum", [0, 1, 2]),
                "InpDayLossUsd": ("num", 0, 10000, 250), "InpDayTargetUsd": ("num", 0, 20000, 500), "InpDayLossPct": ("num", 0, 10, 0.5)},
    "range boxes": {"InpRangeLook": ("int", 3, 30, 1), "InpRangeLookS": ("int", 3, 30, 1), "InpBandOff": ("enum", [0, 1])},
    "the stop": {"InpSlMode": ("enum", [0, 1, 2]), "InpSlAtrMult": ("num", 0.5, 5, 0.1), "InpSlPips": ("num", 0, 100, 5), "InpSlUsd": ("num", 1, 30, 1),
                 "InpMaxRiskUsd": ("num", 0, 60, 1)},
    "the exit": {"InpExitMode": ("enum", [0, 1, 2]), "InpCloseLossMins": ("list", [0, 1, 3, 5, 10, 15, 30, 60]), "InpFixTpPips": ("list", [0, 20, 40, 60, 80, 100, 150, 200])},
    "v1.23 exits": {"InpLongExit": ("enum", [0, 1]), "InpLongTpPips": ("int", 0, 50, 5), "InpShortTpPips": ("int", 0, 50, 5), "InpMinTpPips": ("int", 0, 60, 5),
                    "InpMaxTpPips": ("int", 0, 300, 25), "InpSwingPivot": ("int", 1, 6, 1), "InpSwingLook": ("int", 20, 200, 10), "InpBeUsd": ("num", 0, 20, 1),
                    "InpLongTouch": ("enum", [0, 1]), "InpLongTrailUsd": ("num", 0.5, 10, 0.5), "InpLongResTp": "bool", "InpLongResTp1": "bool", "InpResTp1Ride": "bool",
                    "InpShortTouch": ("enum", [0, 1]), "InpTrailStepUsd": ("num", 0, 5, 0.5), "InpShortTrailUsd": ("num", 0.5, 10, 0.5), "InpBeTpPct": ("num", 0, 1, 0.05),
                    "InpTrail": "bool", "InpTrailSide": ("enum", [0, 1, 2]), "InpRide": "bool", "InpTrailMode": ("enum", [0, 1, 2]), "InpTrailN": ("int", 1, 10, 1),
                    "InpTrailPips": ("int", 5, 100, 5), "InpTrailAtr": ("num", 0.5, 5, 0.25), "InpTrailStart": ("int", 0, 100, 5), "InpRideLock": ("enum", [0, 1, 2]),
                    "InpLockPips": ("int", 0, 50, 5), "InpLockAtUsd": ("num", 0, 20, 1), "InpLockUsd": ("num", 0, 10, 0.5), "InpMaxBars": ("int", 0, 96, 4),
                    "InpPartialPct": ("num", 0, 0.9, 0.1), "InpTp1Be": "bool"},
}

# TurtleTVUHV (Zee 2026-11-05: "every single setting related to our 95% winning EA -> put it into the scanner"): every setting the UHV engine
# (uhv_engine.py) reads - the UHV Diamond group, and Saad's entry settings it applies to the UHV breakout candle when InpUhvSaad is on
G = {
    "UHV Diamond": {"InpUhvMode": ("enum", [0, 1, 2]), "InpUhvMinLaws": ("int", 0, 3, 1), "InpUhvMinEr": ("num", 0, 0.6, 0.05), "InpUhvEntry": ("enum", [0, 1]),
                    "InpUhvStopMode": ("enum", [0, 1, 2]), "InpUhvSlBeyond": ("num", 0, 40, 0.5), "InpUhvRR": ("num", 0.25, 6, 0.25), "InpUhvBeR": ("num", 0, 4, 0.25),
                    "InpUhvFixTp": ("list", [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1, 1.5, 2, 3, 5, 8, 12, 20]), "InpUhvTpPips": ("num", 0.1, 20, 0.5),
                    "InpUhvSlPips": ("num", 0.5, 40, 0.5), "InpUhvMaxSecs": ("list", [0, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 14400]),
                    "InpUhvPreBreak": ("list", [0, 0.1, 0.2, 0.3, 0.5, 1]), "InpUhvLossSecs": ("list", [0, 300, 600, 900, 1200, 1800, 2340, 2700, 3600, 5400, 7200]), "InpUhvLatency": ("num", 0, 2, 0.1), "InpUhvSaad": "bool", "InpTtdOn": "bool"},
    "the candle": {"InpWickMin": ("num", 0.1, 0.9, 0.05), "InpBodyMax": ("num", 0.1, 0.9, 0.05), "InpNoseMax": ("num", 0.0, 0.6, 0.05),
                   "InpMaruBody": ("num", 0.3, 0.95, 0.05), "InpHamRatio": ("num", 1.0, 5.0, 0.25), "InpHamNose": ("num", 0.1, 0.9, 0.05),
                   "InpMinRangeAtr": ("num", 0.0, 1.5, 0.05), "InpUsePin": "bool", "InpMarubozu": "bool", "InpHammer": "bool", "InpStar": "bool", "InpPinColor": "bool"},
    "the lines": {"InpEmaFast": ("int", 3, 60, 1), "InpEmaSlow": ("int", 10, 200, 2)},
    "filters": {"InpAdxMin": ("num", 0, 50, 1), "InpAtrMinUsd": ("num", 0, 0.001, 0.00005), "InpAtrMaxUsd": ("num", 0, 0.002, 0.0001),
                "InpSessFrom": ("int", 0, 23, 1), "InpSessTo": ("int", 1, 24, 1), "InpSkipDow": ("enum", [-1, 1, 2, 3, 4, 5]),
                "InpChopEr": ("num", 0, 0.5, 0.05), "InpChopErLook": ("int", 4, 60, 2), "InpHtfMin": ("enum", [0, 15, 30, 60, 240]), "InpHtfEma": ("int", 10, 100, 5),
                "InpTrendAlign": "bool", "InpPriceSide": "bool", "InpSlopePips": ("num", 0, 10, 0.5), "InpSlopeLook": ("int", 2, 20, 1),
                "InpEmaGapPips": ("num", 0, 10, 0.5), "InpMaxSpreadPts": ("int", 0, 10, 1), "InpCoolBars": ("int", 0, 30, 1),
                "InpBuys": "bool", "InpSells": "bool", "InpDayLossUsd": ("num", 0, 5000, 250), "InpDayTargetUsd": ("num", 0, 5000, 250),
                "InpBeUsd": ("num", 0, 10, 0.5), "InpLockAtUsd": ("num", 0, 10, 0.5), "InpLockUsd": ("num", 0, 5, 0.25)},
    "range boxes": {"InpRangeLook": ("int", 3, 30, 1), "InpRangeLookS": ("int", 3, 30, 1), "InpBandOff": ("enum", [0, 1])},
}
import uhv_ttd  # noqa: E402
_TTD_RANGE = {"enum": None, "bool": None}
_TTD_LISTS = {"InpTtd_uDir": [0, 1, 2], "InpTtd_uTM": [0, 1, 2], "InpTtd_uST": [0, 1, 2, 3, 4, 5, 6], "InpTtd_iExMode": [0, 1, 2]}


def _ttd_spec(k, d):
    if d[1] == "bool":
        return "bool"
    if k in _TTD_LISTS:
        return ("enum", _TTD_LISTS[k])
    v = float(d[0]) if d[0] not in ("", None) else 0.0
    hi = max(v * 3, 5.0) if v else 10.0
    return ("num", 0, round(hi, 2), round(max(hi / 20, 0.1), 2))


G["loss filters"] = {"InpUhvNoClose": "bool", "InpUhvMaxTrigSpread": ("list", [0, 0.7, 0.8, 1.0, 1.5, 2.0]), "InpUhvStruct": ("enum", [0, 1, 2]), "InpUhvSRPips": ("list", [0, 0.5, 1, 1.5, 2, 3, 4, 5]),
                     "InpUhvSRLook": ("list", [20, 30, 60, 120, 240]), "InpUhvRangeAtr": ("list", [0, 1, 1.5, 2, 2.5, 3]),
                     "InpUhvRangeBars": ("list", [5, 10, 15, 20, 30]), "InpUhvFreshBreak": ("list", [0, 1, 2, 3, 5, 8]),
                     "InpUhvFreshSwings": ("list", [1, 2, 3, 4]), "InpUhvBrokeHighs": ("list", [0, 2, 3, 4, 5, 6, 8]),
                     "InpUhvBrokeLook": ("list", [2, 4, 8, 12, 20]), "InpUhvMaxHumps": ("list", [0, 2, 3, 4, 5, 6, 8]),
                     "InpUhvDeepRet": ("list", [0, 0.5, 0.6, 0.7, 0.8, 0.9]), "InpUhvHtf5": ("enum", [0, 1, 2]),
                     "InpUhvHtf5N": ("list", [3, 6, 12, 20, 50])}   # Zee 2026-11-06: the loss filters from his loss comments (uhv_filters.py)
G["cause: support / resistance"] = {"InpUhvSRAhead": ("list", [0, 0.3, 0.5, 1.0, 1.5, 2.0]), "InpUhvSRAheadLook": ("list", [15, 30, 60, 120]),
                                    "InpUhvBigFig": ("list", [0, 0.5, 0.8, 1.0, 1.5, 2.0]), "InpUhvFigStep": ("enum", [100, 50])}
G["cause: against the structure"] = {"InpUhvMinHumps": ("list", [0, 2, 3, 4]), "InpUhvCounterAtr": ("list", [0, 3, 4, 6, 8]),
                                     "InpUhvCounterBars": ("list", [30, 60, 90, 120])}
G["cause: market close"] = {"InpUhvFriCutNY": ("list", [0, 10, 12, 13, 14, 15, 16]),
                             "InpUhvFriCutAllNY": ("list", [0, 8, 9, 10, 11, 12, 13])}   # Zee 2026-11-06: the Friday cut for the angel's zone too
G["cause: exhausted / climax"] = {"InpUhvRunPips": ("list", [0, 4, 6, 8, 10, 15]), "InpUhvRunBars": ("list", [10, 20, 30, 60]),
                                  "InpUhvLoudBrk": ("list", [0, 0.7, 0.8, 0.9, 0.95])}
G["cause: rollover / dead market"] = {"InpUhvMinTicks": ("list", [0, 10, 15, 20, 30, 40]), "InpUhvSunOpenMins": ("list", [0, 30, 60, 120])}
G["cause: news / spike"] = {"InpUhvNewsNY": "bool", "InpUhvNewsMins": ("list", [1, 2, 5, 10]), "InpUhvSpikeAtr": ("list", [0, 2, 3, 4, 5]),
                            "InpUhvSpikeBars": ("list", [5, 15, 30, 60]), "InpUhvHoliday": "bool"}
G["cause: chop"] = {"InpUhvMinAtrPips": ("list", [0, 0.5, 0.8, 1.0, 1.5, 2.0])}
G["cause: bad fill"] = {"InpUhvMaxGapPips": ("list", [0, 0.3, 0.5, 0.6, 0.8, 1.0])}
G["into support"] = {"InpUhvSellSup": ("list", [0, 0.5, 1, 1.5, 2, 3]), "InpUhvSellSupPiv": ("list", [5, 10, 20]), "InpUhvSellSupLast": ("list", [1, 2, 3]),
                      "InpUhvBuyRes": ("list", [0, 0.5, 1, 2]), "InpUhvWall": ("list", [0, 0.5, 1, 1.5, 2]),
                      "InpUhvWallTouches": ("list", [1, 2, 3, 4]), "InpUhvWallBars": ("list", [30, 60, 120]),
                      "InpUhvWallFig": ("enum", [100, 50])}   # Zee 2026-11-06: selling into a major support; a tested round-figure wall
G["zone model"] = {"InpUhvZStart": "bool", "InpUhvZStartHumps": ("list", [2, 3]), "InpUhvZEnd": "bool", "InpUhvZEndHumps": ("list", [3, 4, 5, 6]),
                    "InpUhvZRange": "bool", "InpUhvZRangeBars": ("list", [10, 20, 30, 60]), "InpUhvZRangeAtr": ("list", [2, 3, 4, 5]),
                    "InpUhvZSR": ("list", [0, 0.5, 1, 1.5, 2, 3]), "InpUhvZSRLook": ("list", [30, 60, 120, 240]), "InpUhvZNews": "bool",
                    "InpUhvZClose": "bool", "InpUhvZOpen": "bool", "InpUhvHarvestWins": ("list", [0, 1, 2, 3, 4, 5]),
                    "InpUhvHarvestStopLoss": "bool"}   # Zee 2026-11-06: his zone model + the trend harvest
G["risk manager"] = {"InpUhvRiskMgr": ("enum", [0, 1, 2, 3, 4]), "InpUhvSafeHumpsMin": ("list", [1, 2, 3]), "InpUhvSafeHumpsMax": ("list", [3, 4, 5, 6, 8]),
                      "InpUhvSafeErMin": ("list", [0, 0.1, 0.15, 0.2, 0.3]), "InpUhvSafeErMax": ("list", [0.35, 0.45, 0.6, 1.01]),
                      "InpUhvSafeErBars": ("list", [8, 16, 30]), "InpUhvSafeRangeAtr": ("list", [0, 2, 3, 4, 5]),
                      "InpUhvSafeRangeBars": ("list", [10, 20, 30, 60])}   # Zee 2026-11-06: the loss filters only where risk is expected
G["UHV detection"] = {"InpDetCamPiv": ("list", [1, 2, 3, 4, 5]), "InpDetCamConfirm": ("list", [1, 2, 3]), "InpDetCamStrong": ("list", [0, 2, 3, 4]),
                      "InpDetMaxHumps": ("list", [1, 2, 3, 4, 5, 99]), "InpDetPivot": ("list", [2, 3, 4, 5]), "InpDetTrendLook": ("list", [10, 15, 20, 30, 40]),
                      "InpDetRetraceBack": ("list", [10, 15, 20, 30]), "InpDetUhvBody": ("list", [0, 0.3, 0.4, 0.5, 0.6, 0.7]),
                      "InpDetMomBody": ("list", [0, 0.5, 0.6, 0.7, 0.8, 0.9]), "InpDetCooldown": ("list", [0, 1, 3, 5, 10])}   # Zee 2026-11-05: camel humps, UHV detection, UHV + breakout shape
G["Turtle Trader Desk"] = {k: _ttd_spec(k, d) for k, d in uhv_ttd.TTD.items() if k != "InpTtdOn"}   # Zee 2026-11-05: the indicator's settings
SAAD_ON = {"the candle", "the lines", "filters"}                     # these act only with InpUhvSaad on (uhv_engine.py)
UHV_LAB_OFF = {"cx", "cx_buf", "cx_n", "cx_when", "cx_after", "fb", "fb_buf", "fb_n", "adx_exit", "fri_hour", "tr_buf", "pess"}   # not in the UHV engine yet
GROUP = {k: g for g, d in G.items() for k in d}
SPEC = {k: v for d in G.values() for k, v in d.items()}
# Exit Lab settings that are off (0): where switching them on starts
STARTERS = {"p1_r": [0.5, 1, 1.5, 2], "p2_r": [1.5, 2, 3], "be_r": [0.5, 1, 1.5, 2], "lock_r": [0.5, 1, 2], "max_bars": [4, 8, 16, 32], "stale_bars": [4, 8, 16],
            "adx_exit": [15, 20, 25], "fri_hour": [18, 20, 21], "fb_buf": [0.1, 0.25, 0.5], "cx_buf": [0.1, 0.25, 0.5], "tr_act": [0.5, 1, 2], "tr_buf": [0.5, 1, 2],
            "cx_after": [1, 2, 4], "be_off": [0.05, 0.1, 0.25], "lcap": [10, 15, 20, 30], "lp_r": [0.25, 0.5, 0.75], "dc_bars": [4, 8, 16]}


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _relevant(k, cur):
    """only settings that can act with the others as they are (the same conditions as the EA's code)"""
    g = lambda n: str(cur.get(n, "")).strip()  # noqa: E731
    if GROUP.get(k) in SAAD_ON and g("InpUhvSaad").lower() != "true":
        return False                                                # TurtleTVUHV: Saad's settings act only with InpUhvSaad on
    knob = {"InpUhvSRLook": "InpUhvSRPips", "InpUhvRangeBars": "InpUhvRangeAtr", "InpUhvFreshSwings": "InpUhvFreshBreak",
            "InpUhvBrokeLook": "InpUhvBrokeHighs", "InpUhvHtf5N": "InpUhvHtf5", "InpUhvSRAheadLook": "InpUhvSRAhead",
            "InpUhvFigStep": "InpUhvBigFig", "InpUhvCounterBars": "InpUhvCounterAtr", "InpUhvRunBars": "InpUhvRunPips",
            "InpUhvNewsMins": "InpUhvNewsNY", "InpUhvSpikeBars": "InpUhvSpikeAtr", "InpUhvSafeHumpsMin": "InpUhvRiskMgr",
            "InpUhvSafeHumpsMax": "InpUhvRiskMgr", "InpUhvSafeErMin": "InpUhvRiskMgr", "InpUhvSafeErMax": "InpUhvRiskMgr",
            "InpUhvSafeErBars": "InpUhvRiskMgr", "InpUhvSafeRangeAtr": "InpUhvRiskMgr", "InpUhvSafeRangeBars": "InpUhvSafeRangeAtr",
            "InpUhvZStartHumps": "InpUhvZStart", "InpUhvZEndHumps": "InpUhvZEnd", "InpUhvZRangeBars": "InpUhvZRange",
            "InpUhvZRangeAtr": "InpUhvZRange", "InpUhvZSRLook": "InpUhvZSR", "InpUhvHarvestStopLoss": "InpUhvHarvestWins",
            "InpUhvSellSupPiv": "InpUhvSellSup", "InpUhvSellSupLast": "InpUhvSellSup", "InpUhvWallTouches": "InpUhvWall",
            "InpUhvWallBars": "InpUhvWall", "InpUhvWallFig": "InpUhvWall"}.get(k)
    if knob and not (str(cur.get(knob, "")).strip().lower() == "true" or _f(cur.get(knob)) > 0):
        return False                                                # a loss filter's tuning knob acts only with the filter on
    if GROUP.get(k) == "Turtle Trader Desk" and g("InpTtdOn").lower() != "true":
        return False                                                # the indicator's settings act only with InpTtdOn on
    if k in ("InpUhvTpPips", "InpUhvSlPips"):
        return g("InpUhvStopMode") == "0"
    if k in ("InpUhvSlBeyond", "InpUhvFixTp", "InpUhvBeR"):
        return g("InpUhvStopMode") in ("1", "2")
    if k == "InpUhvRR":
        return g("InpUhvStopMode") in ("1", "2") and _f(cur.get("InpUhvFixTp")) == 0
    if k in ("InpUhvMode", "InpUhvMinLaws"):
        return g("InpUhvEntry") == "0"                              # the instant entry has no EA / royal / laws tags
    if k in ("InpRetestFrac", "InpRetestBars"):
        return g("InpEntryMode") == "1"
    if k in ("InpSweepPips", "InpSweepBars", "InpSweepEntry", "InpSweepSlPips"):
        return g("InpEntryMode") == "2"
    if k == "InpSlAtrMult":
        return g("InpSlMode") == "1"
    if k == "InpSlPips":
        return g("InpSlMode") == "0"
    if k == "InpSlUsd":
        return g("InpSlMode") == "2"
    if k == "InpChopErLook":
        return _f(cur.get("InpChopEr")) > 0
    if k == "InpHtfEma":
        return _f(cur.get("InpHtfMin")) > 0
    if k == "InpSlopeLook":
        return _f(cur.get("InpSlopePips")) > 0
    if k in ("InpReplace", "InpExtraDir"):
        return _f(cur.get("InpMaxPos")) > 1
    if GROUP.get(k) == "v1.23 exits":
        return g("InpExitMode") == "0"
    return True


def _valid(cur):
    """combinations that cannot trade: the slow EMA not above the fast one, a session that ends before it starts"""
    return _f(cur.get("InpEmaSlow"), 32) > _f(cur.get("InpEmaFast"), 16) and _f(cur.get("InpSessTo"), 24) > _f(cur.get("InpSessFrom"), 0)


def _fmt(kind, v):
    if kind == "int":
        return str(int(round(v)))
    return f"{round(v, 6):g}"


def _values(spec, cur):
    """a few steps either side of the value on screen, plus 'off' (0) for the settings where 0 switches them off"""
    if spec == "bool":
        return ["false" if str(cur).strip().lower() == "true" else "true"]
    kind = spec[0]
    if kind in ("enum", "list"):
        return [str(v) for v in spec[1] if abs(_f(v, 1e9) - _f(cur, -1e9)) > 1e-9]
    lo, hi, st = spec[1], spec[2], spec[3]
    try:
        c = float(cur)
    except (TypeError, ValueError):
        return []
    out = []
    for d in (-4, -2, -1, 1, 2, 4):
        v = round((c + d * st) / st) * st
        if lo - 1e-9 <= v <= hi + 1e-9:
            out.append(_fmt(kind, v))
    if lo <= 0 < c:
        out.append(_fmt(kind, 0))
    if c == 0 and kind == "num" and lo <= 0:                            # TurtleTVUHV: an "off" setting is also tried switched on
        out += [_fmt(kind, v) for v in (st, 2 * st, 4 * st) if v <= hi]
    return [v for v in dict.fromkeys(out) if abs(float(v) - c) > 1e-9]


def lab_sets(labfull):
    """the bench's Exit Lab exit as the EA's own settings (InpX*) - what MT5 runs"""
    import sim_full
    out = {}
    for f, k in sim_full.XFIELDS.items():
        if f in labfull:
            v = _f(labfull[f])
            out[k] = ("true" if v else "false") if f == "p1_be" else _fmt("num", v)
    return out


# the broker's real gold spread (Blueberry ticks, 2026): 10th percentile 14 points, median 19. A spread limit below this never lets an EA trade
# live (the tester's clamped export spread did, which is how a limit of 10 looked great and took no trades in MT5)
SPREAD_FLOOR = 15


def _gate(k):
    g = GROUP.get(k)
    return "InpTtdOn" if g == "Turtle Trader Desk" else "InpUhvSaad" if g in SAAD_ON else None


def moves(base_in, labfull, trust=None, include=()):
    """every move from the bench: {group, key, label, from, to, sets (EA settings for the page), lab (the bench form for the page), xs (InpX for the run), trust}
    include: switches ticked in the Exit Lab (InpTtdOn / InpUhvSaad) - their groups are scanned as if switched on, each move carrying the switch"""
    import exitlab
    trust = trust or {}
    out = []
    for k, spec in SPEC.items():
        gate, b, extra = _gate(k), base_in, {}
        if gate and gate in include and str(base_in.get(gate, "")).lower() != "true":
            b, extra = dict(base_in, **{gate: "true"}), {gate: "true"}
        if k not in b or not _relevant(k, b):
            continue
        for v in _values(spec, b[k]):
            if k == "InpMaxSpreadPts" and 0 < _f(v) < SPREAD_FLOOR:
                continue                                                # the broker never meets it: no trades live
            if not _valid(dict(b, **{k: v})):
                continue
            out.append({"group": GROUP[k], "key": k, "label": k[3:] + (" (+ switch on)" if extra else ""), "from": str(b[k]), "to": v,
                        "sets": dict(extra, **{k: v}), "lab": {}, "xs": {}, "trust": trust.get(k, "")})
    if str(base_in.get("InpUhvStopMode", "")).strip() in ("1", "2"):       # Zee 2026-11-05: a bigger target / ride it - moves that need 2+ settings at once
        fix = _f(base_in.get("InpUhvFixTp"))
        for rr in (0.25, 0.5, 0.75, 1, 1.5, 2, 3):                     # the R target needs the fixed TP off
            if fix != 0 or abs(_f(base_in.get("InpUhvRR")) - rr) > 1e-9:
                out.append({"group": "UHV Diamond", "key": "InpUhvRR", "label": f"target {rr}R (fixed TP off)", "from": f"TP {fix:g} pips" if fix else f"{_f(base_in.get('InpUhvRR')):g}R",
                            "to": f"{rr}R", "sets": {"InpUhvFixTp": "0", "InpUhvRR": f"{rr:g}"}, "lab": {}, "xs": {}, "trust": ""})
        for act in (0.05, 0.1, 0.25, 0.5, 1):                          # ride it: no target, a trailing stop k pips behind once +act R
            for k in (0.5, 1, 2, 3, 5):
                sets = {"InpUhvFixTp": "0", "InpUhvRR": "100", "InpXTr": "1", "InpXTrK": f"{k:g}", "InpXTrAct": f"{act:g}"}
                if all(str(base_in.get(x, "")).strip() == v for x, v in sets.items()):
                    continue
                out.append({"group": "UHV Diamond", "key": "InpXTr", "label": f"ride it: no target, trail {k:g} pips behind once +{act:g}R", "from": "current exit",
                            "to": f"trail {k:g}p @ {act:g}R", "sets": sets, "lab": {}, "xs": {}, "trust": ""})
    for side, key in (("BUY", "InpBandsB"), ("SELL", "InpBandsS")):         # every range box, ticked / unticked
        s = str(base_in.get(key, "1" * 21)).ljust(21, "1")[:21]
        for b in range(21):
            t = s[:b] + ("0" if s[b] == "1" else "1") + s[b + 1:]
            nm = f"{side} box {'>100%' if b == 20 else f'{b * 5}-{b * 5 + 5}%'}"
            out.append({"group": "range boxes", "key": key, "label": nm, "from": "on" if s[b] == "1" else "off", "to": "off" if s[b] == "1" else "on",
                        "sets": {key: t}, "lab": {}, "xs": {}, "trust": ""})
    mode = str(base_in.get("InpExitMode", "")).strip()
    if mode in ("1", "2"):                                                  # the Exit Lab settings (EA v1.30 InpX*) act in exit modes 1-2
        L = dict(exitlab.DEFAULT, **(labfull or {}))
        g = lambda f: _f(L.get(f, 0))  # noqa: E731
        for f, x in exitlab.FIELDS.items():
            if f in UHV_LAB_OFF or (x.get("show") and not _show(x["show"], L)):   # TurtleTVUHV: only the exits the UHV engine plays
                continue
            if f in ("fb", "fb_buf", "fb_n") and (mode != "1" or g("tgt") != 0):
                continue                                                    # the fallback exists only in exit mode 1 without a lab target
            cur = g(f)
            names = {}
            if x["t"] == "sel":
                vals = [float(o) for o, _ in x["opts"] if o != int(cur) and not (f == "tr" and o > 3) and not (f == "tgt" and o == 0 and False)]
                names = {float(o): nm for o, nm in x["opts"]}
            elif x["t"] == "bool":
                vals = [0.0 if cur else 1.0]
                names = {0.0: "off", 1.0: "on"}
            elif cur == 0 and f in STARTERS:
                vals = [float(v) for v in STARTERS[f]]
            else:
                grid = exitlab.GRID.get(f)
                if isinstance(grid, dict):
                    grid = grid.get(int(g("tgt" if f == "tgt_k" else "tr")))
                if not grid:
                    continue
                vals = [float(v) for v in _values(("num",) + tuple(grid), cur)]
            for v in vals:
                d = {f: v}
                xs = lab_sets(dict(L, **d))
                out.append({"group": "Exit Lab", "key": f, "label": "X: " + x["label"], "from": names.get(cur, f"{cur:g}"), "to": names.get(v, f"{v:g}"),
                            "sets": {}, "lab": d, "xs": xs, "trust": ""})
    return out


def _show(cond, L):
    v = lambda f: _f(L.get(f, 0))  # noqa: E731
    for o in cond.split("||"):
        ok = True
        for a in o.split("&&"):
            for op in (">=", "<=", "==", ">", "<"):
                if op in a:
                    f, c = a.split(op)
                    x, c = v(f.strip()), float(c)
                    ok = ok and {">=": x >= c, "<=": x <= c, "==": x == c, ">": x > c, "<": x < c}[op]
                    break
        if ok:
            return True
    return False


# ---------------------------------------------------------------- the runs, on a few worker processes
WORKERS = max(2, min(4, (os.cpu_count() or 4) - 2))
_POOL, _LOCK, _USED = None, threading.Lock(), [0.0]


def _winit():
    os.environ.setdefault("NUMBA_CPU_NAME", "generic")
    import sim, uhv_engine                                            # TurtleTVUHV: the workers run the UHV engine, as the server does
    sim.simulate = uhv_engine.simulate
    threading.Thread(target=_watch_parent, args=(os.getppid(),), daemon=True).start()


def _watch_parent(ppid):
    """a worker leaves when its server is gone (a killed server would otherwise leave ~340 MB orphans behind on Windows)"""
    if os.name != "nt":
        while True:
            time.sleep(3)
            if os.getppid() != ppid:
                os._exit(0)
    import ctypes
    k32 = ctypes.windll.kernel32
    while True:
        time.sleep(3)
        h = k32.OpenProcess(0x00100000, False, ppid)               # SYNCHRONIZE
        if not h:
            os._exit(0)
        gone = k32.WaitForSingleObject(h, 0) == 0                 # WAIT_OBJECT_0: the server has exited
        k32.CloseHandle(h)
        if gone:
            os._exit(0)


def _pool():
    global _POOL
    with _LOCK:
        if _POOL is None:
            _POOL = cf.ProcessPoolExecutor(max_workers=WORKERS, mp_context=mp.get_context("spawn"), initializer=_winit)
            threading.Thread(target=_reaper, daemon=True).start()
        _USED[0] = time.time()
        return _POOL


def _drop_pool():
    global _POOL
    with _LOCK:
        if _POOL is not None:
            try:
                _POOL.shutdown(wait=False, cancel_futures=True)
            except Exception:                                    # noqa: BLE001
                pass
            _POOL = None


def kill_pool():
    """Zee 2026-11-05 "stop scan": end the workers now - a run already going (a detection rebuild takes ~70 s) would otherwise finish"""
    global _POOL
    with _LOCK:
        pool, _POOL = _POOL, None
    if pool is None:
        return 0
    procs = list((getattr(pool, "_processes", None) or {}).values())
    try:
        pool.shutdown(wait=False, cancel_futures=True)
    except Exception:                                            # noqa: BLE001
        pass
    for pr in procs:
        try:
            pr.terminate()
        except Exception:                                        # noqa: BLE001
            pass
    return len(procs)


def _reaper():
    """the workers hold the data in memory (~340 MB each): let them go after 10 idle minutes"""
    while True:
        time.sleep(60)
        with _LOCK:
            if _POOL is None:
                return
            idle = time.time() - _USED[0] > 600
        if idle:
            _drop_pool()
            return


def evaluate(task):
    """one run (in a worker): EA settings over the data -> the numbers (L = the loss side for the loss cutter, Lh = the same per half, days = day by day)"""
    import exitlab
    import losslab
    inputs, ds, sets, window = task
    _, real, oe = exitlab.run(dict(inputs, **sets), ds)               # the Exit Lab exit comes in as InpX* settings, exactly as the EA reads it
    s = exitlab.stats(real, window, open_end=oe)
    a0, a1, b0, b1 = window
    p, t = real[:, 6], real[:, 1]
    return {"train": s["train"]["net"], "test": s["test"]["net"], "net": s["total"], "wr": s["all"]["wr"], "pf": s["all"]["pf"], "dd": s["all"]["dd"],
            "n": s["all"]["n"], "stuck": s["stuck"], "L": losslab.loss_stats(p),
            "Lh": [losslab.loss_stats(p[(t >= a0) & (t < a1)]), losslab.loss_stats(p[(t >= b0) & (t < b1)])], "days": losslab.day_stats(real)}


def _sig(sets, lab):
    """what a move changes, comparable between moves: short numbers as numbers ("15" = "15.0"), everything else as text - the range-box
    strings ("111110010100001010111") are 21-digit words, not numbers (as floats, different boxes would look the same)"""
    def v(x):
        s = str(x).strip().lower()
        if len(s) <= 12:
            try:
                return round(float(s), 6)
            except ValueError:
                pass
        return s
    return (tuple(sorted((k, v(x)) for k, x in sets.items())), tuple(sorted((k, v(x)) for k, x in lab.items())))


def data_moves(props, base_in, labfull, trust, have):
    """the loss autopsy's proposals -> moves. One that the scan already makes gets the autopsy's reason instead of a twin;
    one that changes nothing, cannot trade or cannot act is dropped."""
    import exitlab
    L = dict(exitlab.DEFAULT, **(labfull or {}))
    index = {_sig(m["sets"], m["lab"]): m for m in have}
    out = []
    for pr in props:
        sets = {k: (v if isinstance(v, str) else _fmt("int" if SPEC.get(k, ("num",))[0] == "int" else "num", float(v))) for k, v in (pr.get("sets") or {}).items()}
        lab = {k: float(v) for k, v in (pr.get("lab") or {}).items()}
        if sets and all(_sig({k: base_in.get(k)}, {}) == _sig({k: v}, {}) for k, v in sets.items()):
            continue                                             # already the bench's values
        if lab and all(abs(_f(L.get(k)) - v) < 1e-9 for k, v in lab.items()):
            continue
        if sets and not _valid(dict(base_in, **sets)):
            continue
        if any(k not in base_in for k in sets):
            continue
        if any(not _relevant(k, dict(base_in, **sets)) for k in sets):
            continue
        sig = _sig(sets, lab)
        if sig in index:                                         # the scan's own move: give it the reason
            index[sig]["why"] = pr.get("why", "")
            index[sig]["data"] = True
            continue
        m = {"group": pr.get("group", "the stop"), "key": next(iter(sets or lab)), "label": pr.get("label", ""), "from": str(pr.get("from", "")),
             "to": str(pr.get("to", "")), "sets": sets, "lab": lab, "xs": lab_sets(dict(L, **lab)) if lab else {},
             "trust": trust.get(next(iter(sets)), "") if sets else "", "why": pr.get("why", ""), "data": True}
        index[sig] = m
        out.append(m)
    return out


def run_all(job, inputs, ds, lab, sets, window, focus=None):
    import exitlab
    import sim_full
    if not lab:                                                  # no bench form sent: the exit in the settings themselves (InpX*)
        lab = {k: v for k, v in (sim_full.lab_from_inputs(dict(inputs, **(sets or {}))) or {}).items() if k != "pess"}
    labfull = {k: v for k, v in dict(exitlab.DEFAULT, **lab).items() if k != "pess"}
    base_sets = dict(sets or {}, **lab_sets(labfull))            # the bench as EA settings: the same numbers MT5 would run
    base_in = dict(inputs, **base_sets)
    trust = exitlab.ea_trust()
    mv = moves(base_in, labfull, trust, tuple(job.kw.get("include") or ()))
    aut = None
    if focus == "loss":                                          # the loss cutter: read the bench's own trades, add the moves they point to
        import losslab
        import sim
        job.phase = "the loss autopsy: reading every trade on the bench"
        tr, setups, _ = sim.simulate(base_in, ds=ds)
        aut = losslab.autopsy(tr[tr[:, 10] == 0], setups, sim.data(ds), base_in, labfull)
        mv += data_moves(aut.pop("proposals"), base_in, labfull, trust, mv)
    requested = job.kw.get("priority") or []
    by_sig = {_sig(m["sets"], m["lab"]): m for m in mv}
    priority = []
    for item in requested[:9]:
        if not isinstance(item, dict):
            continue
        m = by_sig.get(_sig(item.get("sets") or {}, item.get("lab") or {}))
        if m is not None and m not in priority:
            priority.append(m)
    if not priority:
        seen = set()
        for m in mv:
            if m["key"] not in seen:
                seen.add(m["key"])
                priority.append(m)
                if len(priority) == 10:
                    break
    priority_ids = {id(m) for m in priority}
    mv = priority + [m for m in mv if id(m) not in priority_ids]
    priority_count = len(priority)
    job.total = len(mv) + 1
    job.phase = f"rechecking {priority_count} previous suggestions first"
    tasks = [(inputs, ds, base_sets, window)] + [(inputs, ds, dict(base_sets, **m["sets"], **m["xs"]), window) for m in mv]
    results = [None] * len(tasks)
    completed_order = []
    t0 = time.time()

    def publish_partial():
        if results[0] is None:
            return
        completed = [i for i in completed_order if i > 0 and results[i] is not None]
        moves_done = [dict({k: v for k, v in mv[i - 1].items() if k != "xs"}, r=results[i]) for i in completed]
        job.partial_result = {"now": results[0], "moves": moves_done, "seconds": round(time.time() - t0, 1), "n": len(mv),
                              "completed": len(completed), "priority_count": priority_count, "partial": True,
                              "stopped": False, "focus": focus or "", "autopsy": aut}

    try:
        pool = _pool()
        initial = list(range(priority_count + 1))
        remaining = list(range(priority_count + 1, len(tasks)))
        for batch, is_initial in ((initial, True), (remaining, False)):
            if not batch:
                continue
            futs = {pool.submit(evaluate, tasks[i]): i for i in batch}
            since_publish = 0
            for f in cf.as_completed(futs):
                if job._stop:
                    for g in futs:
                        g.cancel()
                    break
                i = futs[f]
                results[i] = f.result()
                completed_order.append(i)
                job.progress += 1
                since_publish += 1
                job.phase = f"{mv[i - 1]['group']}: {mv[i - 1]['label']} → {mv[i - 1]['to']}" if i else "the exit on the bench"
                if is_initial and all(results[n] is not None for n in initial):
                    publish_partial()
                elif not is_initial and since_publish >= 5:
                    publish_partial()
                    since_publish = 0
            if job._stop:
                break
        _USED[0] = time.time()
    except Exception as e:                                       # noqa: BLE001  (a broken pool: drop it, finish on this core, a fresh pool next time)
        _drop_pool()
        job.phase = f"finishing on one core ({type(e).__name__})"
        for i, t in enumerate(tasks):
            if job._stop:
                break
            if results[i] is None:
                results[i] = evaluate(t)
                completed_order.append(i)
                job.progress += 1
                if results[0] is not None and job.progress % 5 == 0:
                    publish_partial()
    now = results[0]
    out = [dict({k: v for k, v in m.items() if k != "xs"}, r=r) for m, r in zip(mv, results[1:]) if r]
    return {"now": now, "moves": out, "seconds": round(time.time() - t0, 1), "n": len(mv), "stopped": now is None or len(out) < len(mv),
            "focus": focus or "", "autopsy": aut}
