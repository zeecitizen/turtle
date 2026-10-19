"""aug_oct_chart_vs_mt5.py - Zee 2026-10-19: "i want the winrates that are shown on chart for oct, sept, and august ... its 30 points of winrate!"
Every chart trade (the indicator's export table, Aug 2 - Oct 16, UTC) next to MT5 v1.27 (rig axi, XAUUSD_BB = Blueberry ticks, NO delay - the chart
has none - same period), matched by side + entry time; per-month win rates of both, and every unmatched / different trade.
Writes why_out/aug_oct_cmp.json.   py aug_oct_chart_vs_mt5.py [--rerun]"""
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402
import axi_rig  # noqa: E402

NODE, CLI = r"C:\Program Files\nodejs\node.exe", r"C:/Users/zeesh/Documents/GitHub/tradingview-mcp/src/cli/index.js"
OUT = Path(__file__).parent / "why_out" / "aug_oct_cmp.json"
REP = Path(axi_rig._R("axi")) / "reports" / "aug_oct_cmp.htm"

# 1. MT5
if "--rerun" in sys.argv or not REP.exists():
    axi_rig.kill_rig("axi")
    axi_rig.compile_ea("Saad_strategy_15min", rig="axi")
    r = axi_rig.run("Saad_strategy_15min", "XAUUSD_BB", "M15", {"InpLogCsv": "false"}, frm="2026.07.20", to="2026.10.17", deposit=100000, rig="axi",
                    tag="aug_oct_cmp", exec_mode=0)
    print("MT5 run:", {k: r.get(k) for k in ("net", "pf", "trades", "dd", "error")})
mt = []
for p in server.parse_positions(str(REP), 0):
    t_in = datetime.strptime(p["in"], "%Y-%m-%d %H:%M")
    off = 3 if t_in < datetime(2026, 11, 1) else 2                     # Blueberry server = UTC+3 (NY summer time)
    mt.append({"side": p["side"], "in": t_in - timedelta(hours=off), "out": datetime.strptime(p["out"], "%Y-%m-%d %H:%M") - timedelta(hours=off),
               "en": p["en"], "ex": p["ex"], "pnl": p["pnl"]})

# 2. the chart
st = server.tv_eval(server.JS_STUDY); names = server.pine_inputs(); k = names.index("exOn")
server.set_input(st["id"], k, True); time.sleep(8)
r = subprocess.run([NODE, CLI, "data", "tables", "-f", "Saad"], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180)
server.set_input(st["id"], k, False)
exp = next(t["rows"] for t in json.loads(r.stdout)["studies"][0]["tables"] if t.get("rows") and t["rows"][0].startswith("# | side"))
chart = []
for row in exp[1:]:
    c = [x.strip() for x in row.split("|")]
    if len(c) >= 9 and c[0].isdigit():
        chart.append({"num": int(c[0]), "side": c[1], "in": datetime.strptime(c[2], "%Y-%m-%d %H:%M"), "en": float(c[3]), "sl": float(c[4]),
                      "out": datetime.strptime(c[5], "%Y-%m-%d %H:%M"), "ex": float(c[6]),
                      "pnl": float(c[7].replace("$", "").replace(",", "").replace("+", "")), "why": c[8]})
first, last = min(c["in"] for c in chart), datetime(2026, 10, 17)
chart = [c for c in chart if c["out"] < last]
mt = [m for m in mt if first <= m["in"] < last]

# 3. match
used, pairs = set(), []
for c in chart:
    best = None
    for i, m in enumerate(mt):
        if i in used or m["side"] != c["side"]:
            continue
        d = abs((m["in"] - c["in"]).total_seconds()) / 60
        if d <= 30 and (best is None or d < best[0]):
            best = (d, i)
    if best:
        used.add(best[1])
    pairs.append((c, mt[best[1]] if best else None))
pairs += [(None, m) for i, m in enumerate(mt) if i not in used]
pairs.sort(key=lambda x: (x[0] or x[1])["in"])

mon = defaultdict(lambda: {"c_n": 0, "c_w": 0, "c_net": 0.0, "m_n": 0, "m_w": 0, "m_net": 0.0})
for c, m in pairs:
    if c:
        d = mon[c["out"].strftime("%Y-%m")]; d["c_n"] += 1; d["c_w"] += c["pnl"] > 0; d["c_net"] += c["pnl"]
    if m:
        d = mon[m["out"].strftime("%Y-%m")]; d["m_n"] += 1; d["m_w"] += m["pnl"] > 0; d["m_net"] += m["pnl"]
print(f"\nchart trades {len(chart)} from {first:%b %d} | MT5 (no delay) trades {len(mt)}")
print("month   | chart: trades wins WR net        | MT5: trades wins WR net")
for k in sorted(mon):
    d = mon[k]
    print(f"{k} | {d['c_n']:3} {d['c_w']:3} {100 * d['c_w'] / max(1, d['c_n']):3.0f}% {d['c_net']:+10,.0f} | {d['m_n']:3} {d['m_w']:3} "
          f"{100 * d['m_w'] / max(1, d['m_n']):3.0f}% {d['m_net']:+10,.0f}")
both = [(c, m) for c, m in pairs if c and m]
flip = [(c, m) for c, m in both if (c["pnl"] > 0) != (m["pnl"] > 0)]
print(f"\nshared trades {len(both)} | same win/loss on both: {len(both) - len(flip)} | win on one, loss on the other: {len(flip)}")
print(f"chart-only trades {sum(1 for c, m in pairs if c and not m)} | MT5-only trades {sum(1 for c, m in pairs if m and not c)}")
pkt = lambda t: (t + timedelta(hours=5)).strftime("%b %d %I:%M %p")
print("\nDIFFERENT OUTCOME on a shared trade:")
for c, m in flip:
    print(f"  {pkt(c['in'])} {c['side']:4} chart #{c['num']} {c['en']:.2f}->{c['ex']:.2f} {c['pnl']:+,.0f} ({c['why'][:38]}) | MT5 {m['en']:.2f}->{m['ex']:.2f} {m['pnl']:+,.0f} out {pkt(m['out'])}")
print("\nCHART ONLY:")
for c, m in pairs:
    if c and not m:
        print(f"  {pkt(c['in'])} {c['side']:4} #{c['num']} {c['en']:.2f}->{c['ex']:.2f} {c['pnl']:+,.0f} ({c['why'][:40]})")
print("\nMT5 ONLY:")
for c, m in pairs:
    if m and not c:
        print(f"  {pkt(m['in'])} {m['side']:4} {m['en']:.2f}->{m['ex']:.2f} {m['pnl']:+,.0f} out {pkt(m['out'])}")
ser = lambda d: {k: (str(v) if isinstance(v, datetime) else v) for k, v in d.items()} if d else None
OUT.write_text(json.dumps([{"chart": ser(c), "mt5": ser(m)} for c, m in pairs], indent=1), encoding="utf-8")
