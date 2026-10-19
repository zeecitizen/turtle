"""compare_tv.py - Zee 2026-10-20: "the bottom right panel on tradingview shows on october a winrate of 86% .. find out why turtle Tv shows different
result 62.5% on october and fix it". The chart's own trades (the indicator's export, read from TradingView) next to the Turtle TV Tester on
TradingView's candles (a) the TradingView way (chart rules, $0.17 spread, no swap, blind inside the entry candle before Oct 12), (b) the chart's rules
with 1-minute data everywhere, (c) v1.27's rules with the real spread and swap, and (d) on Blueberry's MT5 candles - per month and trade by trade.
Writes simdata/compare_tv.json.   py compare_tv.py"""
import importlib.util
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")
import sim  # noqa: E402

spec = importlib.util.spec_from_file_location("cmp", HERE.parents[0] / "saad_compare" / "server.py")
CMP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CMP)

tv = json.loads(urllib.request.urlopen("http://127.0.0.1:8773/api/tv", timeout=120).read())          # the chart's settings -> EA inputs
inputs = json.loads(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8773/api/sim", data=json.dumps({"inputs": tv["sets"], "ema": False, "setups": False}).encode(),
                                                                  headers={"Content-Type": "application/json"}), timeout=120).read())["inputs"]
chart = CMP.read_tv()["trades"]                                                                           # the indicator's own trade list (UTC)
C = [{"side": 1 if c["side"] == "BUY" else -1, "in": datetime.strptime(c["in"], "%Y-%m-%d %H:%M"), "out": datetime.strptime(c["out"], "%Y-%m-%d %H:%M"),
      "en": c["en"], "pnl": c["pnl"], "why": c["why"]} for c in chart]
utc = lambda e: datetime(1970, 1, 1) + timedelta(seconds=int(e)) - timedelta(hours=3 if int(e) < 1793480400 else 2)   # server -> UTC (DST ends Nov 1)


def trades(tr):
    return [{"side": int(x[0]), "in": utc(x[1]), "out": utc(x[4]), "en": x[2], "pnl": x[6], "why": int(x[13])} for x in tr if x[10] == 0]


RUNS = {
    "a TradingView's way (TV candles, chart rules, blind before Oct 12)": sim.simulate(inputs, ds="tv", chart=True, blind_until=sim.TV_M1_FROM)[0],
    "b TV candles, chart rules, 1-minute data everywhere": sim.simulate(inputs, ds="tv", chart=True)[0],
    "c TV candles, v1.27 rules, real spread + swap": sim.simulate(inputs, ds="tv")[0],
    "d Blueberry MT5 candles (Turtle TV until now)": sim.simulate(inputs, ds="year")[0],
}
first = min(c["in"] for c in C)
mon = lambda t: t.strftime("%Y-%m")
res = {"settings_changed": {k: v for k, v in tv["sets"].items()}, "chart": {}, "runs": {}}


def by_month(T):
    m = defaultdict(lambda: [0, 0, 0.0])
    for t in T:
        if t["in"] >= first:
            d = m[mon(t["out"])]; d[0] += 1; d[1] += t["pnl"] > 0; d[2] += t["pnl"]
    return m


cm = by_month(C)
print(f"chart (TradingView panel): {len(C)} trades from {first:%b %d}")
months = sorted(cm)
print("month   | " + " | ".join(f"{m}" for m in months))
print("chart   | " + " | ".join(f"{cm[m][1]}/{cm[m][0]} {100 * cm[m][1] / max(1, cm[m][0]):.0f}%" for m in months))
res["chart"] = {m: cm[m] for m in months}
for name, tr in RUNS.items():
    T = trades(tr)
    bm = by_month(T)
    print(f"{name[:2]}      | " + " | ".join(f"{bm[m][1]}/{bm[m][0]} {100 * bm[m][1] / max(1, bm[m][0]):.0f}%" for m in months) + f"   <- {name}")
    used, pairs = set(), []
    for c in C:
        best = None
        for i, t in enumerate(T):
            if i in used or t["side"] != c["side"]:
                continue
            d = abs((t["in"] - c["in"]).total_seconds())
            if d <= 1800 and (best is None or d < best[0]):
                best = (d, i)
        if best:
            used.add(best[1]); pairs.append((c, T[best[1]]))
    same = sum((a["pnl"] > 0) == (b["pnl"] > 0) for a, b in pairs)
    Tn = [t for t in T if t["in"] >= first]
    print(f"        shared {len(pairs)}/{len(C)} chart trades, same win/loss {same} | chart only {len(C) - len(pairs)}, Turtle TV only {len(Tn) - len(pairs)}")
    diff = [(a, b) for a, b in pairs if (a["pnl"] > 0) != (b["pnl"] > 0)]
    for a, b in diff:
        print(f"          {a['in'] + timedelta(hours=5):%b %d %I:%M %p} PKT {'BUY' if a['side'] > 0 else 'SELL'}: chart {a['pnl']:+,.0f} ({a['why'][:40]}) | Turtle TV {b['pnl']:+,.0f} "
              f"({['', 'stop', 'EMA target', 'close-back', 'day close'][b['why']]})")
    res["runs"][name] = {"months": {m: bm[m] for m in months}, "shared": len(pairs), "same": same, "turtle_only": len(Tn) - len(pairs),
                         "diff": [{"in": str(a["in"]), "side": a["side"], "chart": a["pnl"], "turtle": b["pnl"]} for a, b in diff]}
(HERE / "simdata" / "compare_tv.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
