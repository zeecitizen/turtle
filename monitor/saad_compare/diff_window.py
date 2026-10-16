"""diff_window.py - the chart's own setups / skips next to the EA's log, for one time window (UTC).

    py diff_window.py "2026-10-12 02:30" "2026-10-12 02:50"

Reads the indicator's debug event table (switched on for the window, then off again) and the last Strategy Tester run's
agent log in Zee's Blueberry terminal (run why_compare.py first). Server time = UTC+3 (Blueberry, summer).
"""
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

frm, to = sys.argv[1], sys.argv[2]
OFF = 3
ms = lambda s: int(datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp() * 1000)
st = server.tv_eval(server.JS_STUDY); names = server.pine_inputs()
def setv(d):
    vals = ",".join("{id: 'in_%d', value: %s}" % (names.index(k), __import__("json").dumps(v)) for k, v in d.items())
    server.tv_eval("(() => { window.TradingViewApi.activeChart().getStudyById('%s').setInputValues([%s]); return JSON.stringify(1); })()" % (st["id"], vals))
setv({"skEx": True, "skFrom": ms(frm), "skTo": ms(to)})
rows = None
for _ in range(10):
    time.sleep(4)
    d = server.tv("data", "tables", "--filter", "Saad")
    rows = next((t["rows"] for s in d.get("studies", []) for t in s.get("tables", []) if t["rows"] and t["rows"][0].startswith("event UTC")), None)
    if rows:
        break
setv({"skEx": False})
chart = []
for r in (rows or [])[1:]:
    tm, _, ev = r.partition("|")
    chart.append((tm.strip()[:16], "CHART " + ev.strip()))
logs = sorted(Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Tester\27280402C90F04230EE7E17540AE21E1").glob("Agent-*/logs/*.log"), key=lambda p: p.stat().st_mtime)
txt = logs[-1].read_text(encoding="utf-16", errors="ignore")
txt = txt[txt.rfind("testing of Experts\\Saad_strategy_1min"):]
a = datetime.strptime(frm, "%Y-%m-%d %H:%M"); b = datetime.strptime(to, "%Y-%m-%d %H:%M")
ea = []
for m in re.finditer(r"(\d{4}\.\d\d\.\d\d \d\d:\d\d):\d\d\s+\[SAAD-1min\] (.*)", txt):
    t = datetime.strptime(m.group(1), "%Y.%m.%d %H:%M") - timedelta(hours=OFF)
    if a <= t <= b:
        ea.append((t.strftime("%Y-%m-%d %H:%M"), "  EA  " + m.group(2)[:170]))
for tm, line in sorted(chart + ea, key=lambda x: (x[0], x[1].startswith("  EA"))):
    print(tm[5:], line)
