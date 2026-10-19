"""oct_chart_vs_mt5.py - Zee 2026-10-19: "it shows 86% winrate for October. why is the MT5 showing differently. compare each trade".
The indicator's October trades (its export table, UTC) next to MT5 v1.27 run 1 (server time = UTC+3 in October), matched by side + entry time."""
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

NODE, CLI = r"C:\Program Files\nodejs\node.exe", r"C:/Users/zeesh/Documents/GitHub/tradingview-mcp/src/cli/index.js"


def tables():
    r = subprocess.run([NODE, CLI, "data", "tables", "-f", "Saad"], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180)
    return {t["rows"][0]: t["rows"] for t in json.loads(r.stdout)["studies"][0]["tables"] if t.get("rows")}


st = server.tv_eval(server.JS_STUDY); names = server.pine_inputs(); k = names.index("exOn")
server.set_input(st["id"], k, True); time.sleep(8)
T = tables()
server.set_input(st["id"], k, False)
exp = next(v for kk, v in T.items() if kk.startswith("# | side"))
chart = []
for r in exp[1:]:
    c = [x.strip() for x in r.split("|")]
    if len(c) >= 9 and c[0].isdigit() and c[5].startswith("2026-10"):
        chart.append({"num": int(c[0]), "side": c[1], "in": datetime.strptime(c[2], "%Y-%m-%d %H:%M"), "en": float(c[3]), "sl": float(c[4]),
                      "out": datetime.strptime(c[5], "%Y-%m-%d %H:%M"), "ex": float(c[6]), "pnl": float(c[7].replace("$", "").replace(",", "").replace("+", "")),
                      "why": c[8]})
mt = []
for p in json.load(open(Path(__file__).parents[1] / "strategy_lab" / "v127_october.json"))["run 1"]["pos"]:
    mt.append({"side": p["side"], "in": datetime.strptime(p["in"], "%Y-%m-%d %H:%M") - timedelta(hours=3), "out": datetime.strptime(p["out"], "%Y-%m-%d %H:%M") - timedelta(hours=3),
               "en": p["en"], "ex": p["ex"], "pnl": p["pnl"]})
used = set()
rows = []
for c in chart:
    best = None
    for i, m in enumerate(mt):
        if i in used or m["side"] != c["side"]:
            continue
        d = abs((m["in"] - c["in"]).total_seconds()) / 60
        if d <= 45 and (best is None or d < best[0]):
            best = (d, i)
    if best:
        used.add(best[1]); rows.append((c, mt[best[1]]))
    else:
        rows.append((c, None))
rows += [(None, m) for i, m in enumerate(mt) if i not in used]
rows.sort(key=lambda x: (x[0] or x[1])["in"])
pkt = lambda t: (t + timedelta(hours=5)).strftime("%b %d %I:%M %p")
print(f"chart: {len(chart)} October trades, {sum(c['pnl'] > 0 for c in chart)} wins, net {sum(c['pnl'] for c in chart):+,.2f}")
print(f"MT5  : {len(mt)} October trades, {sum(m['pnl'] > 0 for m in mt)} wins, net {sum(m['pnl'] for m in mt):+,.2f}\n")
out = []
for c, m in rows:
    t = (c or m)["in"]
    line = f"{pkt(t)} PKT {(c or m)['side']:4} | chart: " + (f"#{c['num']} {c['en']:.2f} -> {c['ex']:.2f} {c['pnl']:+,.0f} ({c['why'][:40]})" if c else "-- no trade --") + \
           " | MT5: " + (f"{m['en']:.2f} -> {m['ex']:.2f} {m['pnl']:+,.0f} (out {pkt(m['out'])})" if m else "-- no trade --")
    print(line)
    out.append({"chart": {k: (str(v) if isinstance(v, datetime) else v) for k, v in c.items()} if c else None,
                "mt5": {k: (str(v) if isinstance(v, datetime) else v) for k, v in m.items()} if m else None})
json.dump(out, open(Path(__file__).parent / "why_out" / "oct_chart_vs_mt5.json", "w"), indent=1)
