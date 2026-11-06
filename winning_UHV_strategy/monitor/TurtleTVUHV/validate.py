"""validate.py - does the Turtle TV Tester (sim.py) take the same trades as MT5? (the advisor's ladder: setups, entries, exits, then the RANKING
of different settings). MT5 = the viewer EA's no-delay export of the year (simdata), Blueberry real ticks.
   py monitor/saad_view/validate.py            -> v1.27 defaults, trade by trade
   py monitor/saad_view/validate.py --rank     -> also 10 different settings in both engines (MT5 runs on rig axi7, ~1 min each)"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "monitor" / "strategy_lab"))
sys.stdout.reconfigure(encoding="utf-8")
import sim  # noqa: E402
import axi_rig  # noqa: E402

D = sim.data()
ep = lambda s: int((datetime.strptime(s, "%Y.%m.%d %H:%M:%S") - datetime(1970, 1, 1)).total_seconds())
EA = "Saad_strategy_15min"
dfl = axi_rig.ea_defaults(EA)


def mt5_trades(lines):
    ev = [l.split("\t") for l in lines[1:]]
    ent = {e[8]: e for e in ev if e[0] == "entry"}
    out = []
    for e in ev:
        if e[0] == "exit" and e[8] in ent:
            n = ent[e[8]]
            out.append({"side": int(n[2]), "in": ep(n[1]), "en": float(n[3]), "out": ep(e[1]), "ex": float(e[3]), "pnl": float(e[5])})
    return out


def sim_trades(tr):
    r = tr[tr[:, 10] == 0]
    return [{"side": int(x[0]), "in": int(x[1]), "en": x[2], "out": int(x[4]), "ex": x[5], "pnl": x[6]} for x in r]


def compare(A, B, tol=180):
    """A = sim, B = MT5: pairs by side + entry within tol seconds."""
    used, pairs = set(), []
    for a in A:
        best = None
        for i, b in enumerate(B):
            if i in used or b["side"] != a["side"]:
                continue
            d = abs(b["in"] - a["in"])
            if d <= tol and (best is None or d < best[0]):
                best = (d, i)
        if best:
            used.add(best[1]); pairs.append((a, B[best[1]]))
    same = sum((a["pnl"] > 0) == (b["pnl"] > 0) for a, b in pairs)
    return pairs, same


def wr(T):
    return 100.0 * sum(t["pnl"] > 0 for t in T) / max(1, len(T))


S = sim_trades(sim.simulate(dfl)[0])
M = mt5_trades(list(D["events"]))
pairs, same = compare(S, M)
print(f"v1.27 defaults, year: sim {len(S)} trades WR {wr(S):.1f}% net {sum(t['pnl'] for t in S):+,.0f} | MT5 {len(M)} trades WR {wr(M):.1f}% "
      f"net {sum(t['pnl'] for t in M):+,.0f}")
print(f"  shared trades {len(pairs)} ({100 * len(pairs) / max(1, len(M)):.0f}% of MT5's), same win/loss {same} | sim only {len(S) - len(pairs)}, MT5 only {len(M) - len(pairs)}")
print(f"  shared: entry price diff median ${np.median([abs(a['en'] - b['en']) for a, b in pairs]):.2f}, exit time same candle "
      f"{sum(abs(a['out'] - b['out']) < 900 for a, b in pairs)}/{len(pairs)}, pnl diff median ${np.median([abs(a['pnl'] - b['pnl']) for a, b in pairs]):.0f}")
mon = {}
for T, k in ((S, "s"), (M, "m")):
    for t in T:
        m = datetime.utcfromtimestamp(t["out"]).strftime("%Y-%m")
        d = mon.setdefault(m, {"s": [], "m": []}); d[k].append(t)
print("  month: sim trades WR net | MT5 trades WR net")
for m in sorted(mon):
    a, b = mon[m]["s"], mon[m]["m"]
    print(f"  {m}: {len(a):3} {wr(a):5.1f}% {sum(t['pnl'] for t in a):+9,.0f} | {len(b):3} {wr(b):5.1f}% {sum(t['pnl'] for t in b):+9,.0f}")

if "--rank" in sys.argv:
    VAR = [{}, {"InpAdxMin": "25"}, {"InpAdxMin": "35"}, {"InpEmaFast": "12"}, {"InpEmaSlow": "40"}, {"InpNoseMax": "0.2"}, {"InpSlAtrMult": "1.2"},
           {"InpSlAtrMult": "2.2"}, {"InpMaxRiskUsd": "14"}, {"InpBreakPips": "1"}, {"InpExitMode": "2"}]
    rows = []
    axi_rig.kill_rig("axi7")
    axi_rig.compile_ea(EA, rig="axi7")
    for v in VAR:
        s = sim.score(sim.simulate(dict(dfl, **v))[0])
        r = axi_rig.run(EA, "XAUUSD_BB", "M15", dict(v, InpLogCsv="false"), frm="2026.01.01", to="2026.10.17", deposit=100000, rig="axi7",
                        tag="rank", exec_mode=0)
        rows.append({"set": v, "sim_net": s["net"], "sim_pf": s["pf"], "sim_n": s["n"], "mt5_net": r.get("net"), "mt5_pf": float(r.get("pf") or 0),
                     "mt5_n": r.get("trades")})
        print(f"  {json.dumps(v):32} sim {s['net']:+10,.0f} PF {s['pf']:.2f} n {s['n']:3} | MT5 {r.get('net'):+10,.0f} PF {r.get('pf')} n {r.get('trades')}", flush=True)
    a = np.array([x["sim_net"] for x in rows]); b = np.array([x["mt5_net"] for x in rows], dtype=float)
    ra, rb = a.argsort().argsort(), b.argsort().argsort()
    rho = 1 - 6 * ((ra - rb) ** 2).sum() / (len(a) * (len(a) ** 2 - 1))
    print(f"RANK AGREEMENT (Spearman, net): {rho:.2f}  (1.0 = the same order)")
    (HERE / "simdata" / "rank_check.json").write_text(json.dumps({"rows": rows, "spearman_net": rho}, indent=1))
