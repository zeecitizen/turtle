"""_common.py - shared helpers for the look-ahead audit canaries (read-only use of the engine / filter code)."""
import os, sys, json, itertools
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT); os.chdir(ROOT)
import numpy as np

BASE_FILE = os.path.join(ROOT, "settings", "saved", "2026-11-05 05-45-38.json")


def base_inputs():
    return json.load(open(BASE_FILE, encoding="utf-8"))["inputs"]


def grids():
    """the scanner's own value grids (scan.py G['loss filters'] + the G['cause: ...'] groups + G['risk manager'])"""
    import scan
    out = {}
    for g, d in scan.G.items():
        if g == "loss filters" or g.startswith("cause:") or g == "risk manager":
            for k, spec in d.items():
                if spec == "bool":
                    out[k] = [0, 1]
                else:
                    out[k] = list(spec[1])
    return out


# each loss setting with its companion knobs (the companions only act with the main one on)
COMP = {"InpUhvStruct": [], "InpUhvSRPips": ["InpUhvSRLook"], "InpUhvRangeAtr": ["InpUhvRangeBars"],
        "InpUhvFreshBreak": ["InpUhvFreshSwings"], "InpUhvBrokeHighs": ["InpUhvBrokeLook"], "InpUhvMaxHumps": [], "InpUhvDeepRet": [],
        "InpUhvHtf5": ["InpUhvHtf5N"], "InpUhvSRAhead": ["InpUhvSRAheadLook"], "InpUhvBigFig": ["InpUhvFigStep"], "InpUhvMinHumps": [],
        "InpUhvCounterAtr": ["InpUhvCounterBars"], "InpUhvFriCutNY": [], "InpUhvRunPips": ["InpUhvRunBars"], "InpUhvLoudBrk": [],
        "InpUhvMinTicks": [], "InpUhvSunOpenMins": [], "InpUhvNewsNY": ["InpUhvNewsMins"], "InpUhvSpikeAtr": ["InpUhvSpikeBars"],
        "InpUhvHoliday": [], "InpUhvMinAtrPips": [], "InpUhvMaxGapPips": []}


def skip_configs():
    """[(main setting, {inputs})] - every non-zero grid value of each loss setting x every grid value of its companions"""
    G = grids()
    out = []
    for main, comps in COMP.items():
        vals = [v for v in G[main] if float(v) != 0]
        for combo in itertools.product(vals, *[G[c] for c in comps]):
            d = {main: str(combo[0])}
            d.update({c: str(v) for c, v in zip(comps, combo[1:])})
            out.append((main, d))
    return out


def secure_configs():
    """the Risk Manager's secure() zone: every grid value of each knob with the others at their defaults, plus a few corners"""
    G = grids()
    dflt = {"InpUhvSafeHumpsMin": "2", "InpUhvSafeHumpsMax": "5", "InpUhvSafeErMin": "0.15", "InpUhvSafeErMax": "0.45",
            "InpUhvSafeErBars": "16", "InpUhvSafeRangeAtr": "0", "InpUhvSafeRangeBars": "20"}
    out = [dict(dflt)]
    for k in dflt:
        for v in G[k]:
            d = dict(dflt); d[k] = str(v); out.append(d)
    for ra in (2, 3, 5):
        for rb in (10, 60):
            for eb in (8, 30):
                d = dict(dflt); d.update(InpUhvSafeRangeAtr=str(ra), InpUhvSafeRangeBars=str(rb), InpUhvSafeErBars=str(eb)); out.append(d)
    return out


def record_calls(inp_extra=None):
    """run the real engine once; return (skip-call args list of dicts, secure-call list, counts). The recorder never skips."""
    import uhv_engine, uhv_filters
    rec_skip, rec_sec = [], []
    real_skip, real_sec = uhv_filters.skip, uhv_filters.secure

    def rec(fv, inp, D, side, k, px, atr_k, extreme, level=None, ku=None, ts=None, uhv_v=None, brk_ticks=None, brk_px=None):
        rec_skip.append(dict(side=side, k=k, px=px, atr_k=atr_k, extreme=extreme, level=level, ku=ku, ts=ts, uhv_v=uhv_v,
                             brk_ticks=brk_ticks, brk_px=brk_px))
        return None

    def rec2(fv, inp, D, side, k):
        rec_sec.append((side, k)); return False
    uhv_filters.skip, uhv_filters.secure = rec, rec2
    try:
        inp = dict(base_inputs())
        inp["InpUhvMinAtrPips"] = "1e-12"
        inp["InpUhvRiskMgr"] = "1"
        inp.update(inp_extra or {})
        rows, su, cnt = uhv_engine.simulate(inp)
    finally:
        uhv_filters.skip, uhv_filters.secure = real_skip, real_sec
    return rec_skip, rec_sec, cnt


def fv(inp, k, d=0.0):
    import uhv_engine
    return uhv_engine.fv(inp, k, d)


def clear_caches():
    """the filter cache is keyed on id(D) and the engine's caches on the setups FILE (not the data): clear all before every variant"""
    import uhv_filters, uhv_engine
    uhv_filters._C.clear()
    uhv_engine._INST.clear()
