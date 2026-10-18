"""saad_v1_m5.py - Zee 2026-10-18: "let's shift our focus to 5 min time frame". The V1 'all best drivers' settings (M1 Jan-Jun +$30,096,
PF 2.09, WR 33.6%) on M5 in the MT5 Strategy Tester: full year + Jan-Jun + Jul-Oct, XAUUSD_BB real ticks, random delay, $100k.
Writes saad_v1_m5.json.   py saad_v1_m5.py [period]
"""
import json
import random
import sys
import threading
import time
from pathlib import Path

import axi_rig

HERE = Path(__file__).resolve().parent
V1 = dict(InpSessFrom="16", InpSessTo="18", InpEntryMode="2", InpAtrMaxUsd="0", InpChopEr="0.3", InpAtrMinUsd="2", InpBreakPips="3", InpAdxMin="30",
          InpTpMode="2", InpTpFibPct="200", InpCostGateX="3", InpHtfIdx="4", InpHtfEma="70", InpSlMode="1", InpSlAtrMult="2", InpEmaFast="10", InpEmaSlow="20",
          InpBeTpPct="0.75", InpMaxRiskUsd="10", InpPartialPct="0.75", InpHardTp="true")
PER = sys.argv[1] if len(sys.argv) > 1 else "M5"
# rig "axi" only: axi2-7 belong to the compare page's 10-month view, which re-runs on every chart change (the first try collided with it).
# One full-year pass; Jan-Jun / Jul-Oct are summed from its months.
RUNS = [("year", "2026.01.01", "2026.10.17", "axi")]
base = dict(json.load(open(HERE / "saad_opt_base_sets_m1def.json")), InpOptScore="4", InpOptMinTrades="1", **V1)
res = {}


def one(name, frm, to, rig):
    axi_rig.compile_ea("Saad_strategy_1min", rig=rig)
    for a in range(3):
        r = axi_rig.run("Saad_strategy_1min", "XAUUSD_BB", PER, base, frm=frm, to=to, deposit=100000, rig=rig, tag=f"v1{PER}", exec_mode=-1)
        if r.get("error") not in ("authorization failed", "no report"):
            break
        axi_rig.kill_rig(rig); time.sleep(3 + random.random() * 5)
    ts = r.get("trade_stats") or {}
    n, aw, al, net = ts.get("n") or 0, ts.get("avg_win") or 0, ts.get("avg_loss") or 0, r.get("net") or 0
    wr = 100 * ((net + n * -al) / (aw - al)) / n if n and aw - al else 0
    res[name] = dict(net=net, pf=float(r.get("pf") or 0), wr=wr, n=n, dd=r.get("dd"), months=r.get("months"), days=r.get("day_stats"), err=r.get("error"))
    print(f"{PER} {name}: net {net:+,.0f}  PF {res[name]['pf']:.2f}  WR {wr:.1f}%  trades {n}  err {r.get('error')}", flush=True)


ts = []
for x in RUNS:
    t = threading.Thread(target=one, args=x); t.start(); ts.append(t); time.sleep(4)
[t.join() for t in ts]
mo = (res.get("year") or {}).get("months") or {}
for nm, keys in (("jan-jun", [f"2026.{m:02d}" for m in range(1, 7)]), ("jul-oct", [f"2026.{m:02d}" for m in range(7, 11)])):
    res[nm] = {"net": round(sum(v for k, v in mo.items() if k[:7] in keys), 2)}
    print(f"{PER} {nm}: net {res[nm]['net']:+,.0f}")
print("months", mo)
json.dump(res, open(HERE / f"saad_v1_{PER.lower()}.json", "w"), indent=1)
