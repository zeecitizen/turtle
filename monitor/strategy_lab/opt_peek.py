"""opt_peek.py - read a RUNNING MT5 optimization's results from its agents' logs (the .opt cache is only written at the end).
Each agent logs "<pass> OnTester result <score>"; the pass number is the combination's index in the optimized inputs' grid
(mixed radix, inputs in EA declaration order). The decoding is checked against the values the EA prints at OnInit.
    py opt_peek.py            # Saad_strategy_15min driver search (saad15_driver_search.OPT)
"""
import glob
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import axi_rig  # noqa: E402
from saad15_driver_search import OPT  # noqa: E402

EA = "Saad_strategy_15min"
src = (axi_rig.SRC / f"{EA}.mq5").read_text(encoding="utf-8", errors="ignore")
order = [m.group(1) for m in re.finditer(r"^input\s+\w+\s+(\w+)\s*=", src, re.M) if m.group(1) in OPT]
vals = {k: [round(a + i * s, 6) for i in range(int(round((b - a) / s)) + 1)] for k, (a, s, b) in OPT.items()}


def decode(pid, fastest_first):
    out, rest = {}, pid
    seq = order if fastest_first else order[::-1]
    for k in seq:
        n = len(vals[k])
        out[k] = vals[k][rest % n]
        rest //= n
    return out


passes = {}
START = "00:33:50"                       # this run started 2026-10-19 00:33:53 (earlier lines = other runs on the same agents)
for f in glob.glob(r"C:/mt5_rig_axi/Tester/Agent-*/logs/20261019.log"):
    init = None
    for line in open(f, encoding="utf-16", errors="ignore"):
        ts = line.split(chr(9))[2][:8] if line.count(chr(9)) >= 3 else ""
        if ts < START:
            continue
        m = re.search(r"SL (\d+) pips, max risk \$[\d.]+, ER ([\d.]+)/\d+, hours (\d+)-(\d+)", line)
        if m and "v1.24" in line:
            init = (float(m.group(1)), float(m.group(2)), int(m.group(3)), int(m.group(4)))
        m = re.search(r"Tester\s+(\d+) OnTester result ([-\d.e+]+)", line)
        if m:
            passes[int(m.group(1))] = (float(m.group(2)), init)
            init = None

# which digit order matches what the EA printed?
ok = {ff: sum(1 for pid, (s, ini) in passes.items() if ini and (lambda d: (d["InpSlPips"], d["InpChopEr"], d["InpSessFrom"], d["InpSessTo"]) == ini)(decode(pid, ff)))
      for ff in (True, False)}
ff = ok[True] >= ok[False]
checked = sum(1 for p in passes.values() if p[1])
print(f"{len(passes)} passes logged so far | decoding checked on {checked}: {ok[ff]} match ({'first input varies fastest' if ff else 'last input varies fastest'})")
top = sorted(passes.items(), key=lambda x: -x[1][0])[:12]
rows = []
for pid, (s, _) in top:
    d = decode(pid, ff)
    rows.append({"pass": pid, "pf_jan_jun": s, **d})
    print(f"PF Jan-Jun {s:.3f} | " + ", ".join(f"{k.replace('Inp', '')}={v:g}" for k, v in d.items()))
json.dump(rows, open(Path(__file__).with_name("s15drv_peek.json"), "w"), indent=1)
