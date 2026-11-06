"""Win-rate court for Saad_strategy_15min v1.23: exits / trail distances / breakeven, each one MT5 pass on XAUUSD_TK
real ticks (M15, 1 lot, $25k, $4/lot commission added). Scored PER POSITION (partial closes summed) and split by side,
so the win rate is the real trade win rate, not MT5's deal count.
    py run_saad_wr.py <rig> <variant@per> ...       results -> testing/saad_wr_runs.jsonl"""
import json, re, sys
from pathlib import Path
import axi_rig

EA = "Saad_strategy_15min"
V = {"base": {}}
for a in (1.0, 1.5, 2.5, 3.0, 4.0): V[f"atr{a}"] = {"InpTrailAtr": a}                       # Path B trail (ATR x behind best)
for p in (20, 30, 50, 80): V[f"pips{p}"] = {"InpTrailMode": 1, "InpTrailPips": p}           # Path B trail, fixed pips behind best
for n in (3, 6, 10): V[f"bars{n}"] = {"InpTrailMode": 0, "InpTrailN": n}                    # Path B trail, low of last N candles
for u in (1.0, 3.0, 4.0, 6.0): V[f"usd{u}"] = {"InpLongTrailUsd": u, "InpShortTrailUsd": u}  # $ trail after TP1, both sides
for u in (1.0, 3.0, 4.0): V[f"lusd{u}"] = {"InpLongTrailUsd": u}
for u in (1.0, 3.0, 4.0): V[f"susd{u}"] = {"InpShortTrailUsd": u}
V["step1"] = {"InpTrailStepUsd": 1.0}
for b in (2, 3, 5, 8): V[f"be{b}"] = {"InpBeUsd": b}                                         # stop to entry after $b (candle close)
for at, lk in ((2, 0.2), (3, 0.3), (3, 1.0), (5, 0.5), (5, 2.0), (8, 3.0)): V[f"lock{at}_{lk}"] = {"InpLockAtUsd": at, "InpLockUsd": lk}
for c in (0, 0.5, 0.6, 0.9): V[f"ctc{c}"] = {"InpBeTpPct": c}
for pp in (0, 0.3, 0.7): V[f"part{pp}"] = {"InpPartialPct": pp}
for tp in (30, 50, 100): V[f"fixtp{tp}"] = {"InpFixTpPips": tp}
for mb in (8, 16, 32): V[f"maxbars{mb}"] = {"InpMaxBars": mb}
V["restp1"] = {"InpLongResTp1": "true"}
V["nopathB"] = {"InpLongExitAbove": "true"}
P = {"full": ("2026.01.06", "2026.10.08"), "tune": ("2026.01.06", "2026.07.01"), "julo": ("2026.07.01", "2026.10.08")}

ROW = re.compile(r"<tr[^>]*><td>(\d{4}\.\d\d\.\d\d [\d:]+)</td><td>\d+</td><td>[^<]+</td><td>(buy|sell)</td><td>(in|out)</td>"
                 r"<td>([\d.]+)</td><td>[\d.]+</td><td>\d+</td><td>([-\d. ]+)</td><td>([-\d. ]+)</td><td>([-\d. ]+)</td>")


def by_side(rep, comm=4.0):
    t = Path(rep).read_text(encoding="utf-16", errors="ignore").replace("\xa0", " ")
    num = lambda s: float(s.replace(" ", ""))
    tr, cur = [], None
    for ts, typ, io, vol, c, s, p in ROW.findall(t):
        v = num(c) + num(s) + num(p) - (comm * float(vol) if io == "out" else 0)
        if io == "in":
            if cur: tr.append(cur)
            cur = ["BUY" if typ == "buy" else "SELL", v]
        elif cur:
            cur[1] += v
    if cur: tr.append(cur)
    out = {}
    for side in ("ALL", "BUY", "SELL"):
        x = [v for sd, v in tr if side in ("ALL", sd)]
        w = [v for v in x if v > 0]
        out[side] = {"n": len(x), "wr": round(100 * len(w) / len(x), 1) if x else 0, "net": round(sum(x)),
                     "avg_win": round(sum(w) / len(w)) if w else 0, "avg_loss": round(sum(v for v in x if v <= 0) / max(1, len(x) - len(w)))}
    return out


axi_rig.use(sys.argv[1])
for name in sys.argv[2:]:
    var, per = name.split("@")
    rnd = per.endswith("rnd"); per0 = per[:-3] if rnd else per
    sets = {"InpLots": 1.0, "InpLog": "false", "InpDraw": "false", "InpLogCsv": "false", **V[var]}
    tag = f"saadwr_{var}_{per}"
    r = axi_rig.run(EA, "XAUUSD_TK", "M15", sets, frm=P[per0][0], to=P[per0][1], exec_mode=-1 if rnd else 200, tag=tag, deposit=25000, timeout=3600)
    try:
        s = by_side(axi_rig.RIG / "reports" / f"{tag}.htm")
    except Exception as e:
        print(f"{name}: FAILED {r.get('error')} {e}", flush=True); continue
    rec = {"variant": var, "per": per, "sets": V[var], "net": r.get("net"), "pf": r.get("pf"), "dd": r.get("dd"), "net_per_dd": r.get("net_per_dd"), "side": s}
    with open(Path(r"C:\Users\zeesh\turtle\testing\saad_wr_runs.jsonl"), "a") as f: f.write(json.dumps(rec) + "\n")
    a, b, c = s["ALL"], s["BUY"], s["SELL"]
    print(f"{name}: WR {a['wr']}% ({a['n']}) | BUY {b['wr']}% ({b['n']}) SELL {c['wr']}% ({c['n']}) | net {a['net']:,} (B {b['net']:,} S {c['net']:,}) | DD {r.get('dd')}", flush=True)
