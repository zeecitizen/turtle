"""Best versions on other brokers (Zee, 2026-10-11: "run the best versions test on blueberry and
primexbt"). Same window, real ticks, random delay, $25k. Session hours are SERVER time:
Axi/Blueberry UTC+3, PrimeXBT UTC+0, so Axi's 08-17 is PrimeXBT's 05-14 (hour_probe.py).
Appends to cross_broker.jsonl."""
import json, sys
from pathlib import Path
import axi_rig
OUT = Path(__file__).with_name("cross_broker.jsonl")
BROKERS = {"axi": ("XAUUSD.pro", 0), "bb": ("XAUUSD.pi", 0), "pxbt": ("XAUUSDp", -3)}
# Blueberry and PrimeXBT serve real ticks only from 2026-09; every broker uses that window
FROM, TO = "2026.09.01", "2026.10.08"   # symbol, hour shift vs Axi

def arms(shift):
    s = lambda h: str((h + shift) % 24)
    win = {"InpSessFrom": s(8), "InpSessTo": s(17)}
    return {
        "saad_rules":       ("Saad_strategy", {}),
        "saad_8_17":        ("Saad_strategy", dict(win)),
        "saad_8_17_shorts": ("Saad_strategy", dict(win, InpBuys="false")),
        "vsisa_v128":       ("VSISA", {}),
    }

for b in (sys.argv[1:] or list(BROKERS)):
    sym, shift = BROKERS[b]
    axi_rig.use(b)
    compiled = set()
    for name, (ea, sets) in arms(shift).items():
        if ea not in compiled:
            axi_rig.compile_ea(ea); compiled.add(ea)
        r = axi_rig.run(ea, sym, "M5", sets, frm=FROM, to=TO, tag=f"{b}_{name}")
        r.update(arm=name, broker=b, window=f"{FROM}-{TO}")
        with OUT.open("a") as f: f.write(json.dumps(r) + "\n")
        print(b, name, r.get("net"), r.get("trades"), r.get("wr"), r.get("pf"), r.get("dd"),
              r.get("quality"), r.get("error", ""), flush=True)
