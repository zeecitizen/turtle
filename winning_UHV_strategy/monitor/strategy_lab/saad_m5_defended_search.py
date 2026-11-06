"""saad_m5_defended_search.py - Zee 2026-10-18: "ok let's shift our focus to 5 min time frame". The M1 defended search, on M5:
V1 (the M1 search's best drivers) made +$498 / 41 trades on M5 and v1.30 (the 15-min setup) -$57.9k, so 5 min needs its own settings.
ONE MT5 genetic optimization of Saad_strategy_1min v1.39 on M5 with every defense on the table (Task 8 / 10 / 4):
cost gate, hard TP, ADX, volatility band, bar-open entries, session window, ATR stop, Fibonacci / fixed close-all targets, slower EMAs,
small break pips, trend alignment, chop filter, max risk, breakeven. Learn Jan 1 - Jun 30, MT5 forward-tests every result on Jul 1 - Oct 16.
Score = profit factor (InpOptScore 5), 0 below 120 trades (M5 has a fifth of M1's candles). Base = Zee's 1-min chart (saad_tasks_base_m1.json) with every range box ON.

    py saad_m5_defended_search.py           # run  -> C:/mt5_rig_axi/reports/opt_m5def.xml + .forward.xml
    py saad_m5_defended_search.py --read    # top results by FORWARD profit factor
"""
import json
import sys
from pathlib import Path

import axi_rig
import saad_optimize as so

HERE = Path(__file__).resolve().parent
base = json.load(open(HERE / "saad_opt_base_sets_m1def.json"))      # the same base as the M1 search
base = dict(base, InpBarSource="0", InpBandsB="1" * 21, InpBandsS="1" * 21, InpBandPauseBars="0", InpRangeMin="0", InpRangeMax="0",
            InpRangeMinS="0", InpRangeMaxS="0", InpCoolN="0", InpReEntry="false", InpLogCsv="false", InpOptScore="5", InpOptMinTrades="120")
(HERE / "saad_opt_base_sets_m5def.json").write_text(json.dumps(base, indent=1), encoding="utf-8")
OPT = {"InpEmaFast": (4, 2, 12), "InpEmaSlow": (8, 4, 24), "InpBreakPips": (0, 1, 4), "InpEntryMode": (0, 1, 3),
       "InpSlMode": (0, 1, 1), "InpSlAtrMult": (1, 0.5, 4), "InpSlPips": (4, 4, 36), "InpMaxRiskUsd": (0, 4, 20),
       "InpTpMode": (1, 1, 2), "InpTpFixUsd": (1, 1, 8), "InpTpFibPct": (150, 50, 400), "InpPartialPct": (0.5, 0.25, 1.0),
       "InpHardTp": None, "InpBeTpPct": (0, 0.25, 1.0), "InpCostGateX": (0, 1, 6), "InpAdxMin": (0, 5, 35),
       "InpAtrMinUsd": (0, 1, 4), "InpAtrMaxUsd": (0, 2, 12), "InpSessFrom": (0, 2, 16), "InpSessTo": (16, 2, 24),
       "InpChopEr": (0, 0.05, 0.3), "InpHtfIdx": (0, 1, 5), "InpHtfEma": (10, 20, 90)}
so.FROM, so.TO, so.FORWARD = "2026.01.01", "2026.10.17", "2026.07.01"
so.JOBS["m5def"] = {"sets": "saad_opt_base_sets_m5def.json", "period": "M5", "algo": 2, "forward": True, "delay": 0, "fixed": {}, "opt": OPT}

if __name__ == "__main__":
    if "--read" not in sys.argv:
        so.start("m5def")
    R = Path(axi_rig._R(so.RIG)) / "reports"
    back = {r["Pass"]: r for r in so._rows(R / "opt_m5def.xml")}
    fwd = so._rows(R / "opt_m5def.forward.xml") if (R / "opt_m5def.forward.xml").exists() else []
    print(len(back), "passes,", len(fwd), "forward")
    top = sorted(fwd, key=lambda r: -float(r.get("Forward Result") or 0))[:15]
    for r in top:
        b = back.get(r["Pass"], {})
        print(f"pass {r['Pass']}: PF Jan-Jun {float(b.get('Result') or 0):.3f} | PF Jul-Oct {float(r.get('Forward Result') or 0):.3f} | "
              f"net Jan-Jun {float(b.get('Profit') or 0):+,.0f} | net Jul-Oct {float(r.get('Profit') or 0):+,.0f} | " + ", ".join(f"{k}={r.get(k)}" for k in OPT))
    json.dump({"top": top, "back": [back.get(r["Pass"]) for r in top]}, open(HERE / "saad_m5_defended_top.json", "w"), indent=1)
