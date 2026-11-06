"""run_fractal.py - MT5 court for FractalBreakout (Williams Fractals 25, M5) vs its no-rules control.

    py run_fractal.py axi  0      # rig, which half of the grid
Results append to _fractal_results.jsonl. Every number is an MT5 Strategy Tester result on XAUUSD_TK real ticks.
"""
import json, sys
from pathlib import Path
import axi_rig

GRID = []
for entry in (0, 1):                                   # 0 = fractal breakout, 1 = control
    for trail in ("2", "3", "5", "8", "12"):
        GRID.append({"InpEntryMode": str(entry), "InpTrailMode": "0", "InpTrailUsd": trail})
    GRID.append({"InpEntryMode": str(entry), "InpTrailMode": "1"})

rig, half = sys.argv[1], int(sys.argv[2])
axi_rig.use(rig)
axi_rig.compile_ea("FractalBreakout")
out = Path(__file__).parent / "_fractal_results.jsonl"
for i, sets in enumerate(GRID):
    if i % 2 != half:
        continue
    tag = "frac_" + "_".join(f"{k[3:]}{v}" for k, v in sets.items())
    r = axi_rig.run("FractalBreakout", "XAUUSD_TK", "M5", sets, frm="2026.01.06", to="2026.10.08", tag=tag)
    r.pop("daily", None)
    with out.open("a") as f:
        f.write(json.dumps(r) + "\n")
    print(tag, r.get("net"), r.get("wr"), r.get("trades"), flush=True)
