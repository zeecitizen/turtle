"""RULES_EMA_SAAD.md as written, on the Overview's engine (server.sim_result path), m15 2023->now, 1 lot."""
import sys, numpy as np
sys.path.insert(0, r"C:\Users\zeesh\turtle\monitor\saad_view")
import server, sim
from concurrent.futures import ThreadPoolExecutor
DOC = dict(InpEmaFast=9, InpEmaSlow=50, InpUsePin=1, InpMarubozu=1, InpHammer=0, InpStar=0, InpPinDir=0, InpMinRangeAtr=0,
    InpLongRule=0, InpShortLine=0, InpTouchMode=0, InpTouchPips=0, InpLongExitAbove=0, InpSkipBothEma=0,
    InpBreakBars=2, InpBreakPips=0, InpSlMode=0, InpSlPips=20, InpMaxRiskUsd=0,
    InpLongExit=0, InpLongTouch=1, InpLongTrailUsd=3, InpLongResTp=1, InpLongResTp1=1, InpResTp1Ride=0,
    InpShortTouch=0, InpShortTpPips=0, InpLongTpPips=0, InpMinTpPips=0, InpMaxTpPips=0,
    InpTrail=1, InpTrailSide=0, InpRide=1, InpBeUsd=0, InpBeTpPct=0, InpPartialPct=0, InpTp1Be=0, InpCloseLossMins=0, InpNoNewMins=0,
    InpChopEr=0, InpAdxMin=0, InpHtfMin=0, InpTrendAlign=0, InpExitMode=0, InpEntryMode=0,
    InpBandsB="1"*21, InpBandsS="1"*21, InpMaxPos=1, InpLots=1, InpRiskPct=0, InpDexRiskSizing=0, InpProbeMode=0)
def run(kv):
    inp = server.full_inputs({k: str(v) for k, v in {**DOC, **kv}.items()})
    tr, _, _ = sim.simulate(inp, ds="m15")
    p = np.array([x[6] for x in tr if x[10] == 0]); eq = np.cumsum(p); dd = (np.maximum.accumulate(eq) - eq).max()
    w, l = p[p > 0], p[p <= 0]
    return f"{len(p):5d}  WR {100*len(w)/len(p):5.1f}%  net {p.sum():+10,.0f}  PF {w.sum()/-l.sum():4.2f}  avg +{w.mean():5,.0f}/{l.mean():6,.0f}  worst {p.min():+7,.0f}  DD {dd:7,.0f}"
G = [("As written", {}), ("+ breakeven at $3", {"InpBeUsd": 3}),
     ("+ no chop (ER16 >= 0.11)", {"InpChopEr": 0.11}), ("+ no chop (ADX >= 25)", {"InpAdxMin": 25}),
     ("+ BE $3 + ER 0.11", {"InpBeUsd": 3, "InpChopEr": 0.11})]
with ThreadPoolExecutor(5) as ex:
    for (n, _), r in zip(G, ex.map(lambda g: run(g[1]), G)): print(f"{n:28s} {r}")
