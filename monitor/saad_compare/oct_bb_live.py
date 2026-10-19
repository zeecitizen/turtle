"""oct_bb_live.py - Zee 2026-10-19: "can you test in MT5 blueberry". v1.27 (pure defaults) in Zee's OWN Blueberry terminal's Strategy Tester,
XAUUSD (Blueberry's real ticks), M15, Oct 1 - Oct 19, random delay, $100k; then trade by trade against the chart's October (why_out/oct_chart_vs_mt5.json)."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

server.EA = "Saad_strategy_15min"
r, rep = server.bb_live_run({"InpLogCsv": "false"}, "M15", "2026.10.01", "2026.10.20", -1, "v127_oct_bb")
pos = server.parse_positions(rep, 3)          # Blueberry server = UTC+3 in October -> UTC
print(f"Blueberry MT5, v1.27, Oct 1-19: net {r.get('net'):+,.2f} PF {r.get('pf')} trades {len(pos)} wins {sum(p['pnl'] > 0 for p in pos)} DD {r.get('dd')} quality {r.get('quality')}")
chart = [x["chart"] for x in json.load(open(Path(__file__).parent / "why_out" / "oct_chart_vs_mt5.json")) if x["chart"]]
for c in chart:
    c["in"] = datetime.fromisoformat(c["in"])
mt = [{**p, "in": datetime.strptime(p["in"], "%Y-%m-%d %H:%M")} for p in pos]
used, rows = set(), []
for c in chart:
    best = None
    for i, m in enumerate(mt):
        if i in used or m["side"] != c["side"]:
            continue
        d = abs((m["in"] - c["in"]).total_seconds()) / 60
        if d <= 45 and (best is None or d < best[0]):
            best = (d, i)
    if best:
        used.add(best[1])
    rows.append((c, mt[best[1]] if best else None))
rows += [(None, m) for i, m in enumerate(mt) if i not in used]
rows.sort(key=lambda x: (x[0] or x[1])["in"])
pkt = lambda t: (t + timedelta(hours=5)).strftime("%b %d %I:%M %p")
for c, m in rows:
    print(f"{pkt((c or m)['in'])} PKT {(c or m)['side']:4} | chart: " + (f"#{c['num']} {c['en']:.2f} -> {c['ex']:.2f} {c['pnl']:+,.0f}" if c else "-- no trade --")
          + " | Blueberry MT5: " + (f"{m['en']:.2f} -> {m['ex']:.2f} {m['pnl']:+,.0f}" if m else "-- no trade --"))
json.dump({"result": {k: r.get(k) for k in ("net", "pf", "trades", "dd", "quality", "daily")}, "positions": pos}, open(Path(__file__).parent / "why_out" / "oct_bb_live.json", "w"), indent=1)
