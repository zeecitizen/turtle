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
for _n in (6, 8, 12): V[f"rb{_n}"] = ("Saad_rangebrk", {"InpRangeBars": _n})
V["rb8s"] = ("Saad_rangebrk", {"InpRangeBars": 8, "InpRangeBody": 0.70})
V["maruL"] = ("Saad_maruclose", {"InpMaruClose": 1})
V["maruLS"] = ("Saad_maruclose", {"InpMaruClose": 2})
for _t in (1, 2, 3, 4, 5, 10, 15): V[f"tol{_t}"] = ("Saad_strategy_15min", {"InpTouchPips": _t})
for _m in (2, 3, 5): V[f"multi{_m}"] = ("Saad_strategy_15min", {"InpMaxPos": _m})
V["multi2same"] = ("Saad_strategy_15min", {"InpMaxPos": 2, "InpExtraDir": 1})
V["multi2opp"] = ("Saad_strategy_15min", {"InpMaxPos": 2, "InpExtraDir": 2})
for _h in (45, 55, 60): V[f"hamnose{_h}"] = ("Saad_strategy_15min", {"InpHamNose": _h / 100})
for _s in (10, 20): V[f"sl{_s}"] = ("Saad_strategy_15min", {"InpSlPips": _s})
for _r in (6, 8, 10, 12, 20): V[f"risk{_r}"] = ("Saad_strategy_15min", {"InpMaxRiskUsd": _r})
for _c in (100, 105, 115, 120): V[f"chop{_c}"] = ("Saad_strategy_15min", {"InpChopEr": _c / 1000})
for _t in (10, 15, 20): V[f"tall{_t}"] = ("Saad_tallmaru", {"InpTallMaruAtr": _t / 10})
V["capM"] = ("Saad_capstop", {"InpCapStop": 1})
V["capAll"] = ("Saad_capstop", {"InpCapStop": 2})
for _c in range(10, 21): V[f"capM{_c}"] = ("Saad_capstop", {"InpCapStop": 1, "InpCapUsd": _c})
V["noham"] = ("Saad_strategy_15min", {"InpHammer": "false", "InpStar": "false"})
V["pindir"] = ("Saad_strategy_15min", {"InpPinDir": "true"})
V["pindir_noham"] = ("Saad_strategy_15min", {"InpPinDir": "true", "InpHammer": "false", "InpStar": "false"})
for _w in range(5, 101, 5): V[f"wick{_w}"] = ("Saad_strategy_15min", {"InpWickMin": _w / 100})
for _n in (10, 30): V[f"nose{_n}"] = ("Saad_strategy_15min", {"InpNoseMax": _n / 100})
V["body40"] = ("Saad_strategy_15min", {"InpBodyMax": 0.40})
W = "Saad_wr"
V["wr_ctl"] = (W, {})
V["nopinbuy"] = (W, {"InpNoPinBuy": "true"})
for _x in (2, 3, 4, 6): V[f"ntbe{_x}"] = (W, {"InpNoTpBeUsd": _x})
V["ntbe4l1"] = (W, {"InpNoTpBeUsd": 4, "InpNoTpBeLock": 1})
for _x in (1.0, 1.5, 2.5, 3.0): V[f"atr{int(_x*10)}"] = (W, {"InpTrailAtr": _x})
for _x in (1.0, 1.5, 3.0, 4.0): V[f"tr{int(_x*10)}"] = (W, {"InpLongTrailUsd": _x, "InpShortTrailUsd": _x})
for _x in (0.5, 0.6): V[f"bepct{int(_x*100)}"] = (W, {"InpBeTpPct": _x})
V["raw"] = ("Saad_raw", {})
P = {"full": ("2026.01.06", "2026.10.08"), "tune": ("2026.01.06", "2026.07.01"), "julo": ("2026.07.01", "2026.10.08")}
P["fullrnd"] = P["full"]      # same dates, random delay (exec -1)
axi_rig.use(sys.argv[1])
for name in sys.argv[2:]:
    var, per = name.split("@")
    ea, sets = V[var]
    sets = {"InpLots": 1.0, "InpLog": "false", "InpDraw": "false", **sets}
    r = axi_rig.run(ea, "XAUUSD_TK", "M15", sets, frm=P[per][0], to=P[per][1], exec_mode=-1 if per.endswith("rnd") else 200, tag=f"saadfix_{var}_{per}", deposit=25000, timeout=3600)
    rec = {"variant": var, "per": per, **{k: r.get(k) for k in ("net", "trades", "wr", "pf", "dd", "net_per_dd", "day_stats", "trade_stats")}}
    try:   # the EA's own end-of-run counts: setups, entries, skipped (no break, gap, risk, no support, choppy, busy ...)
        import glob, os
        lg = max(glob.glob(str(axi_rig.RIG / "Tester" / "logs" / "*.log")), key=os.path.getmtime)
        rows = [x for x in open(lg, encoding="utf-16", errors="ignore").read().splitlines() if "[SAAD] setups" in x]
        rec["ea_counts"] = rows[-1].split("[SAAD] ", 1)[1] if rows else None
    except Exception as e:
        rec["ea_counts"] = f"n/a ({e})"
    with open(Path(r"C:\Users\zeesh\turtle\testing\saad_fix_runs.jsonl"), "a") as f: f.write(json.dumps(rec) + "\n")
    print(f"{name}: net {r.get('net'):,.0f} | deals {r.get('trades')} | PF {r.get('pf')} | DD {r.get('dd')} | net/DD {r.get('net_per_dd')} | worst day {r.get('day_stats', {}).get('worst')}", flush=True)
