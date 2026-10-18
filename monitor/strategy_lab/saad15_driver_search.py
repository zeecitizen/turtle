"""saad15_driver_search.py - Zee 2026-10-19: "i want you to run the optimizer for 15 min to saad_strategy_15min on all settings that u think
made the most effect from the previous optimizer we ran on 1 min".

ONE MT5 genetic optimization of Saad_strategy_15min v1.24 on M15 (XAUUSD_BB = Blueberry real ticks) over the 1-min driver analysis'
strongest settings that this EA has: session hours, entry mode (sweep), ATR band, chop filter, break pips, ADX, higher-timeframe trend,
ATR stop, EMAs (Fibonacci TP and the cost gate are not in the 15-min EA). Everything else = the v1.24 defaults (Zee's 15-min settings).
Learn Jan 1 - Jun 30; MT5 forward-tests every result on Jul 1 - Oct 16. Score = profit factor (InpOptScore 5), 0 below 80 whole trades.
Max risk fixed at Zee's $20 ceiling, so ATR stops are not skipped by v1.23's $15 cap.

    py saad15_driver_search.py           # run  -> C:/mt5_rig_axi/reports/opt_s15drv.xml + .forward.xml
    py saad15_driver_search.py --read    # top results by FORWARD profit factor
"""
import json
import sys
from pathlib import Path

import axi_rig
import saad_optimize as so

HERE = Path(__file__).resolve().parent
OPT = {"InpSessFrom": (0, 2, 16), "InpSessTo": (16, 2, 24), "InpEntryMode": (0, 1, 2),
       "InpAtrMinUsd": (0, 1, 6), "InpAtrMaxUsd": (0, 2, 20), "InpChopEr": (0, 0.04, 0.32), "InpBreakPips": (0, 1, 5),
       "InpAdxMin": (0, 5, 35), "InpHtfMin": (0, 30, 60), "InpHtfEma": (10, 20, 90),
       "InpSlMode": (0, 1, 1), "InpSlAtrMult": (1, 0.5, 4), "InpSlPips": (25, 5, 45),
       "InpEmaFast": (5, 2, 15), "InpEmaSlow": (20, 10, 70)}
so.FROM, so.TO, so.FORWARD = "2026.01.01", "2026.10.17", "2026.07.01"
so.JOBS["s15drv"] = {"ea": "Saad_strategy_15min", "sets": "", "period": "M15", "algo": 2, "forward": True, "delay": 0,
                     "fixed": {"InpOptScore": "5", "InpOptMinTrades": "80", "InpMaxRiskUsd": "20", "InpLogCsv": "false"}, "opt": OPT}

if __name__ == "__main__":
    if "--read" not in sys.argv:
        so.start("s15drv")
    R = Path(axi_rig._R(so.RIG)) / "reports"
    back = {r["Pass"]: r for r in so._rows(R / "opt_s15drv.xml")}
    fwd = so._rows(R / "opt_s15drv.forward.xml") if (R / "opt_s15drv.forward.xml").exists() else []
    print(len(back), "passes,", len(fwd), "forward")
    top = sorted(fwd, key=lambda r: -float(r.get("Forward Result") or 0))[:15]
    for r in top:
        b = back.get(r["Pass"], {})
        print(f"pass {r['Pass']}: PF Jan-Jun {float(b.get('Result') or 0):.3f} | PF Jul-Oct {float(r.get('Forward Result') or 0):.3f} | "
              f"net Jan-Jun {float(b.get('Profit') or 0):+,.0f} | net Jul-Oct {float(r.get('Profit') or 0):+,.0f} | " + ", ".join(f"{k}={r.get(k)}" for k in OPT))
    json.dump({"top": top, "back": [back.get(r["Pass"]) for r in top]}, open(HERE / "saad15_driver_top.json", "w"), indent=1)
