"""v127_three_brokers.py - Zee 2026-10-20: "maybe the MT5 we're testing is Axi. can u check if v1.27 on Blueberry MT5, Axi MT5, prime XBT MT5 differ?"
Saad_strategy_15min v1.27 (pure defaults, 2 lots, $100k, NO delay so only the broker's data differs) on each broker's REAL ticks:
  Blueberry  XAUUSD_BB  (rig axi3, Blueberry ticks cloned from Zee's terminal, Jan 1 - Oct 17)
  Axi        XAUUSD_TK  (rig axi4, Axi real ticks cloned from the Axi terminal, Jan 6 - ~Oct 8; +$4/lot commission like Axi)
  PrimeXBT   XAUUSDp    (rig pxbt, PrimeXBT's own terminal data, real ticks from Sep 18)
Times to UTC (Blueberry / Axi = New York close: UTC+3 Mar 8 - Nov 1, else UTC+2; PrimeXBT = UTC), per-month WR / net on each broker and on the
common windows, and trade-by-trade matches (side + entry within 30 min). Writes v127_three_brokers.json.   py v127_three_brokers.py [--rerun]"""
import json
import sys
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "saad_compare"))
import axi_rig  # noqa: E402
import server  # noqa: E402

EA = "Saad_strategy_15min"
B = {"Blueberry": ("XAUUSD_BB", "axi3", "2026.01.01", 0.0), "Axi": ("XAUUSD_TK", "axi4", "2026.01.06", 4.0), "PrimeXBT": ("XAUUSDp", "pxbt", "2026.09.18", 0.0)}
OUT = HERE / "v127_three_brokers.json"
runs = {}


def go(name):
    sym, rig, frm, _ = B[name]
    rep = Path(axi_rig._R(rig)) / "reports" / f"v127_3b_{name}.htm"
    if "--rerun" in sys.argv or not rep.exists():
        axi_rig.kill_rig(rig)
        axi_rig.compile_ea(EA, rig=rig)
        r = axi_rig.run(EA, sym, "M15", {"InpLogCsv": "false"}, frm=frm, to="2026.10.17", deposit=100000, rig=rig, tag=f"v127_3b_{name}", exec_mode=0)
        runs[name] = {k: r.get(k) for k in ("net", "pf", "trades", "dd", "quality", "error")}
        print(name, runs[name], flush=True)
    runs.setdefault(name, {})["rep"] = str(rep)


ths = [threading.Thread(target=go, args=(n,)) for n in B]
for th in ths:
    th.start()
for th in ths:
    th.join()


def utc(s, name):
    t = datetime.strptime(s, "%Y-%m-%d %H:%M")
    if name == "PrimeXBT":
        return t
    return t - timedelta(hours=3 if datetime(2026, 3, 8) <= t < datetime(2026, 11, 1) else 2)


T = {}
for name in B:
    comm = B[name][3] * 2                                         # $/lot round trip x 2 lots
    T[name] = [{"side": p["side"], "in": utc(p["in"], name), "out": utc(p["out"], name), "en": p["en"], "ex": p["ex"], "pnl": p["pnl"] - comm}
               for p in server.parse_positions(runs[name]["rep"], 0)]
    print(f"{name}: {len(T[name])} trades, first {T[name][0]['in']:%b %d %H:%M} last {T[name][-1]['out']:%b %d %H:%M} UTC")


def stats(ts):
    n, w = len(ts), sum(t["pnl"] > 0 for t in ts)
    return {"n": n, "w": w, "wr": round(100 * w / n, 1) if n else 0, "net": round(sum(t["pnl"] for t in ts))}


def window(a, b):
    return {k: [t for t in v if a <= t["in"] < b] for k, v in T.items()}


def match(x, y):
    used, pairs = set(), []
    for t in x:
        best = None
        for i, u in enumerate(y):
            if i not in used and u["side"] == t["side"]:
                d = abs((u["in"] - t["in"]).total_seconds()) / 60
                if d <= 30 and (best is None or d < best[0]):
                    best = (d, i)
        if best:
            used.add(best[1]); pairs.append((t, y[best[1]]))
    same = sum((a["pnl"] > 0) == (b["pnl"] > 0) for a, b in pairs)
    return {"x": len(x), "y": len(y), "shared": len(pairs), "same_result": same, "x_only": len(x) - len(pairs), "y_only": len(y) - len(pairs)}


ends = {k: max(t["in"] for t in v) for k, v in T.items()}
res = {"runs": runs, "windows": {}}
pkt = lambda t: f"{t + timedelta(hours=5):%b %d}"
for label, a, names in (("Jan 6 - Axi's data end: Blueberry vs Axi", datetime(2026, 1, 6), ("Blueberry", "Axi")),
                        ("Sep 18 - Oct 16: Blueberry vs PrimeXBT", datetime(2026, 9, 18), ("Blueberry", "PrimeXBT")),
                        ("Sep 18 - Axi's data end: all three", datetime(2026, 9, 18), ("Blueberry", "Axi", "PrimeXBT"))):
    b = min(ends[n] for n in names) + timedelta(minutes=1)
    W = window(a, b)
    print(f"\n=== {label} ({a:%b %d} - {b:%b %d %H:%M} UTC)")
    mon = defaultdict(dict)
    for n in names:
        for t in W[n]:
            mon[t["in"].strftime("%Y-%m")].setdefault(n, []).append(t)
    print("month    | " + " | ".join(f"{n:>9}: trades WR net" for n in names))
    for m in sorted(mon):
        print(f"{m}  | " + " | ".join(f"{stats(mon[m].get(n, []))['n']:>9} {stats(mon[m].get(n, []))['wr']:5.1f}% {stats(mon[m].get(n, []))['net']:+9,}" for n in names))
    tot = {n: stats(W[n]) for n in names}
    print("TOTAL    | " + " | ".join(f"{tot[n]['n']:>9} {tot[n]['wr']:5.1f}% {tot[n]['net']:+9,}" for n in names))
    pm = {}
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            m = match(W[names[i]], W[names[j]])
            pm[f"{names[i]} vs {names[j]}"] = m
            print(f"  {names[i]} vs {names[j]}: {m['shared']} shared trades, {m['same_result']} same win/loss | only {names[i]} {m['x_only']}, only {names[j]} {m['y_only']}")
    res["windows"][label] = {"from": str(a), "to": str(b), "total": tot,
                             "months": {m: {n: stats(v.get(n, [])) for n in names} for m, v in mon.items()}, "match": pm}
res["trades"] = {k: [dict(t, **{"in": str(t["in"]), "out": str(t["out"])}) for t in v] for k, v in T.items()}
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
