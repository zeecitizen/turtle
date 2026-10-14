"""MT5 tests of the two fixes suggested by the PXBT post-mortem (XAUUSD_TK real ticks, M15, 1 lot, $25k, 200 ms).
    py run_saad_fix.py <rig> <variant@per> ...     results -> testing/saad_fix_runs.jsonl"""
import json, sys
from pathlib import Path
import axi_rig

V = {"base": ("Saad_strategy_15min", {}),
     "no50long": ("Saad_strategy_15min", {"InpLongRule": 0}),
     "gapfix": ("Saad_gapfix", {}),
     "both": ("Saad_gapfix", {"InpLongRule": 0}),
     "nochop": ("Saad_strategy_15min", {"InpChopEr": 0}),
     "chop05": ("Saad_strategy_15min", {"InpChopEr": 0.05}),
     "short9and50": ("Saad_strategy_15min", {"InpShortLine": 2}),
     "short50only": ("Saad_strategy_15min", {"InpShortLine": 0})}
for _n in (0, 13, 20, 21, 26, 34, 100, 200): V[f"sema{_n}"] = ("Saad_shortema", {"InpShortEma2": _n})
for _m in (1, 2, 3): V[f"mom{_m}"] = ("Saad_mom", {"InpMomMode": _m})
P = {"full": ("2026.01.06", "2026.10.08"), "tune": ("2026.01.06", "2026.07.01"), "julo": ("2026.07.01", "2026.10.08")}
axi_rig.use(sys.argv[1])
for name in sys.argv[2:]:
    var, per = name.split("@")
    ea, sets = V[var]
    sets = {"InpLots": 1.0, "InpLog": "false", "InpDraw": "false", **sets}
    r = axi_rig.run(ea, "XAUUSD_TK", "M15", sets, frm=P[per][0], to=P[per][1], exec_mode=200, tag=f"saadfix_{var}_{per}", deposit=25000, timeout=3600)
    rec = {"variant": var, "per": per, **{k: r.get(k) for k in ("net", "trades", "wr", "pf", "dd", "net_per_dd", "day_stats", "trade_stats")}}
    with open(Path(r"C:\Users\zeesh\turtle\testing\saad_fix_runs.jsonl"), "a") as f: f.write(json.dumps(rec) + "\n")
    print(f"{name}: net {r.get('net'):,.0f} | deals {r.get('trades')} | PF {r.get('pf')} | DD {r.get('dd')} | net/DD {r.get('net_per_dd')} | worst day {r.get('day_stats', {}).get('worst')}", flush=True)
