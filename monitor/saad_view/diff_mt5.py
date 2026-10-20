"""diff_mt5.py - one setting change: MT5 (the viewer EA's export, no delay) vs the Turtle TV Tester, trade by trade; prints the first differences.
   py diff_mt5.py InpShortLine=2 [InpExitMode=0 ...]"""
import sys, json
from pathlib import Path
from datetime import datetime
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
sys.stdout.reconfigure(encoding="utf-8")
import sim, axi_rig
sets = dict(a.split("=", 1) for a in sys.argv[1:])
dfl = axi_rig.ea_defaults("Saad_strategy_15min_view")
EA, RIG, TAG = "Saad_strategy_15min_view", "axi7", "diff"
axi_rig.kill_rig(RIG); axi_rig.compile_ea(EA, rig=RIG)
r = axi_rig.run(EA, "XAUUSD_BB", "M15", dict(sets, InpLogCsv="false", InpExportTag=TAG), frm="2026.01.01", to="2026.10.17", deposit=100000, rig=RIG, tag=TAG, exec_mode=0)
ev = [l.split("\t") for l in (sim.COMMON / f"saadview_{TAG}_events.csv").read_text().splitlines()[1:]]
ep = lambda s: int((datetime.strptime(s, "%Y.%m.%d %H:%M:%S") - datetime(1970, 1, 1)).total_seconds())
ent = {e[8]: e for e in ev if e[0] == "entry"}
M = [(int(ent[e[8]][2]), ep(ent[e[8]][1]), float(ent[e[8]][3]), ep(e[1]), float(e[3]), float(e[5]), e[9]) for e in ev if e[0] == "exit" and e[8] in ent]
tr = sim.simulate(dict(dfl, **sets))[0]
S = [(int(x[0]), int(x[1]), x[2], int(x[4]), x[5], x[6], int(x[13])) for x in tr if x[10] == 0]
print(f"MT5 {len(M)} trades {sum(m[5] for m in M):+,.0f} | sim {len(S)} trades {sum(s[5] for s in S):+,.0f}")
f = lambda t: datetime.utcfromtimestamp(t).strftime("%m-%d %H:%M")
used = set(); shown = 0
for m in M:
    best = None
    for i, s in enumerate(S):
        if i not in used and s[0] == m[0] and abs(s[1] - m[1]) <= 180:
            best = i; break
    if best is None:
        if shown < 12: print(f"MT5 only  {'B' if m[0]>0 else 'S'} {f(m[1])} {m[2]:.2f} -> {f(m[3])} {m[4]:.2f} {m[5]:+.0f} ({m[6]})"); shown += 1
        continue
    used.add(best); s = S[best]
    if abs(s[5] - m[5]) > 300 and shown < 12:
        print(f"DIFF      {'B' if m[0]>0 else 'S'} {f(m[1])} MT5 -> {f(m[3])} {m[4]:.2f} {m[5]:+.0f} ({m[6]}) | sim -> {f(s[3])} {s[4]:.2f} {s[5]:+.0f} (why {s[6]})"); shown += 1
for i, s in enumerate(S):
    if i not in used and shown < 24:
        print(f"sim only  {'B' if s[0]>0 else 'S'} {f(s[1])} {s[2]:.2f} -> {f(s[3])} {s[4]:.2f} {s[5]:+.0f} (why {s[6]})"); shown += 1
