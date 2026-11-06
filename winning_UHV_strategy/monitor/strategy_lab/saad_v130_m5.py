"""saad_v130_m5.py - Zee 2026-10-18 5-min focus: the EA's own defaults (= v1.30: Zee's 15-min settings + ATR stop 2.5 + TP1 10 pips early,
every v1.31-v1.39 addition off) on a timeframe, full year XAUUSD_BB real ticks, random delay, $100k, rig "axi".   py saad_v130_m5.py [M5]"""
import json
import random
import sys
import time
from pathlib import Path

import axi_rig

HERE = Path(__file__).resolve().parent
PER = sys.argv[1] if len(sys.argv) > 1 else "M5"
s = dict(axi_rig.ea_defaults("Saad_strategy_1min"), InpBarSource="0", InpLogCsv="false", InpOptScore="4", InpOptMinTrades="1")
axi_rig.compile_ea("Saad_strategy_1min", rig="axi")
for a in range(3):
    r = axi_rig.run("Saad_strategy_1min", "XAUUSD_BB", PER, s, frm="2026.01.01", to="2026.10.17", deposit=100000, rig="axi", tag=f"v130{PER}", exec_mode=-1)
    if r.get("error") not in ("authorization failed", "no report"):
        break
    axi_rig.kill_rig("axi"); time.sleep(3 + random.random() * 5)
mo = r.get("months") or {}
h1 = sum(v for k, v in mo.items() if k <= "2026.06"); h2 = sum(v for k, v in mo.items() if k >= "2026.07")
out = dict(net=r.get("net"), pf=r.get("pf"), wr=r.get("wr"), trades=r.get("trades"), dd=r.get("dd"), h1=h1, h2=h2, months=mo, days=r.get("day_stats"), err=r.get("error"))
json.dump(out, open(HERE / f"saad_v130_{PER.lower()}.json", "w"), indent=1)
print(PER, json.dumps({k: v for k, v in out.items() if k != "months"}), "\nmonths", mo)
