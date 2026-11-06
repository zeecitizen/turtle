"""Chop filters on Saad 08-17 (Zee, 2026-10-11: "we want to avoid choppy markets"). Axi rig,
XAUUSD.pro M5, real ticks, random delay, $25k, 0.10 lots. Appends to saad_court.jsonl."""
import json, sys
from pathlib import Path
import axi_rig
OUT = Path(__file__).with_name("saad_court.jsonl")
BASE = {"InpSessFrom": "8", "InpSessTo": "17"}
ARMS = {"chop_base": {}}
for n in (1, 2, 4):     ARMS[f"chop_cross{n}"] = {"InpChopCross": str(n)}
for e in (0.2, 0.3, 0.4): ARMS[f"chop_er{int(e*100)}"] = {"InpChopEr": str(e)}
for p in (1, 2, 4):     ARMS[f"chop_slope{p}"] = {"InpChopSlope": str(p)}
for a in (15, 20, 25):  ARMS[f"chop_adx{a}"] = {"InpChopAdx": str(a)}
names = sys.argv[1:] or list(ARMS)
axi_rig.use("axi")
axi_rig.compile_ea("Saad_strategy")
for n in names:
    r = axi_rig.run("Saad_strategy", "XAUUSD.pro", "M5", dict(BASE, **ARMS[n]), tag=f"saad_{n}")
    r["arm"] = n
    with OUT.open("a") as f: f.write(json.dumps(r) + "\n")
    print(n, r.get("net"), r.get("trades"), r.get("wr"), r.get("pf"), r.get("dd"), r.get("error", ""), flush=True)
