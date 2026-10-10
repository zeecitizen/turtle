"""Saad v3.20 court: each test against the v3.10 baseline (defaults = 08-17 + ER 0.20).
Axi rig, XAUUSD.pro M5, real ticks, random delay, $25k, 0.10 lots, Jan 1 -> Oct 8."""
import json, sys
from pathlib import Path
import axi_rig
OUT = Path(__file__).with_name("saad_court.jsonl")
ARMS = {
    "v310_base":       {},
    "t1_mirror":       {"InpLongMode": "1"},
    "t2a_tp30":        {"InpTpPips": "30"},
    "t2b_tp40":        {"InpTpPips": "40"},
    "t3a_sl15":        {"InpSlPips": "15"},
    "t3b_sl25":        {"InpSlPips": "25"},
    "t4_shorts":       {"InpBuys": "false"},
    "mirror_tp30":     {"InpLongMode": "1", "InpTpPips": "30"},
    "mirror_tp40":     {"InpLongMode": "1", "InpTpPips": "40"},
    "mirror_longs":    {"InpLongMode": "1", "InpSells": "false"},
    "rules_longs":     {"InpSells": "false"},
    "sl30":            {"InpSlPips": "30"},
    "sl35":            {"InpSlPips": "35"},
    "sl25_shorts":     {"InpSlPips": "25", "InpBuys": "false"},
}
names = sys.argv[1:] or list(ARMS)
axi_rig.use("axi")
axi_rig.compile_ea("Saad_strategy")
for n in names:
    r = axi_rig.run("Saad_strategy", "XAUUSD.pro", "M5", ARMS[n], tag=f"saad_{n}")
    r["arm"] = n
    with OUT.open("a") as f: f.write(json.dumps(r) + "\n")
    m = r.get("months", {})
    h1 = sum(v for k, v in m.items() if k < "2026.05"); h2 = sum(v for k, v in m.items() if k >= "2026.05")
    print(n, r.get("net"), r.get("trades"), r.get("wr"), r.get("pf"), r.get("dd"),
          f"JanApr {h1:.0f} MayOct {h2:.0f} losingMonths {sum(v < 0 for v in m.values())}", r.get("error", ""), flush=True)
