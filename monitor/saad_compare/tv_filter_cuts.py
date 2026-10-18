"""tv_one_by_one.py - Zee 2026-10-19: "deactivate the applied settings from optimizer on tradingview 1 by 1 to see which one turns all 3
months green". From the chart as it is (the optimizer pass on it), change ONE setting (switch a filter off, or put it back to the EA's
default), read the indicator's month panel, put it back, next. Writes why_out/tv_one_by_one.json.
    py tv_one_by_one.py
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

NODE = r"C:\Program Files\nodejs\node.exe"
CLI = r"C:/Users/zeesh/Documents/GitHub/tradingview-mcp/src/cli/index.js"
PIPS = "Pips beyond the setup candle"
TESTS = [  # Zee 2026-10-19: "check which setting is cutting out trades ... 1 per day"
    ("trading session -> All hours", {"fSess": "All hours"}),
    ("ADX >= 30 -> off", {"fAdxMin": 0}),
    ("ATR band $1-$18 -> off", {"fAtrMin": 0, "fAtrMax": 0}),
    ("range boxes: tick all 42", {**{f"rpB{i:02d}": True for i in range(21)}, **{f"rpS{i:02d}": True for i in range(21)}}),
    ("unticked range: Stand aside -> Skip it and take the next setup", {"rpOff": "Skip it and take the next setup"}),
    ("max risk $19 -> never skip", {"iMaxRisk": 0}),
    ("min TP1 distance 5 pips -> 1", {"iMinTp": 1}),
    ("setup candle >= 0.55 ATR -> off", {"iMinAtr": 0}),
    ("SELL setups on the 9 EMA only -> Either EMA", {"iSLine": "Either"}),
    ("cancel a waiting setup across the close -> off", {"iGap": False}),
    ("no trades while the broker is closed -> off", {"bcOn": False}),
    ("TP1 Next EMA -> Normal (shorter trades?)", {"tpMode": "Normal: BUY = touch of the other EMA · SELL = last swing low"}),
    ("ALL FIVE FILTERS OFF (session, ADX, ATR band, boxes, max risk)", {"fSess": "All hours", "fAdxMin": 0, "fAtrMin": 0, "fAtrMax": 0, "iMaxRisk": 0,
        **{f"rpB{i:02d}": True for i in range(21)}, **{f"rpS{i:02d}": True for i in range(21)}}),
]


def panel():
    r = subprocess.run([NODE, CLI, "data", "tables", "-f", "Saad"], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180)
    rows = next((t["rows"] for t in json.loads(r.stdout)["studies"][0]["tables"] if t.get("rows") and "Win rate" in t["rows"][0]), [])
    out = {}
    for row in rows[1:]:
        m = re.match(r"(\w+ \d{4})\*? \| (\d+)% \| ([+-]\$[\d,.]+) \| (\d+) tr · (\d+)W/(\d+)L · PF ([\d.-]+)", row)
        if m:
            out[m.group(1)] = {"wr": int(m.group(2)), "net": float(m.group(3).replace("$", "").replace(",", "")), "n": int(m.group(4)), "pf": m.group(7)}
    return out


def settled(prev=None):
    """read until two reads in a row agree (TradingView needs a moment to recalculate)"""
    time.sleep(4)
    a = panel()
    for _ in range(8):
        time.sleep(2)
        b = panel()
        if a == b and a and a != prev:
            return a
        a = b
    return a


def fmt(p):
    return " | ".join(f"{m[:3]} {v['net']:+,.0f} ({v['n']} tr, {v['wr']}%, PF {v['pf']})" for m, v in p.items())


st = server.tv_eval(server.JS_STUDY)
names = server.pine_inputs()
assert len(names) == len(st["values"]), (len(names), len(st["values"]))
cur = dict(zip(names, st["values"]))
base = panel()
n0 = sum(v["n"] for v in base.values())
print(f"NOW: {n0} trades | total {sum(v['net'] for v in base.values()):+,.0f} | {fmt(base)}", flush=True)
res = []
for what, ch in TESTS:
    if all(cur[k] == v for k, v in ch.items()):
        continue
    for k, v in ch.items():
        server.set_input(st["id"], names.index(k), v)
    p = settled(base)
    for k in ch:
        server.set_input(st["id"], names.index(k), cur[k])
    green = bool(p) and all(v["net"] > 0 for v in p.values())
    res.append({"what": what, "change": ch, "months": p, "all_green": green, "total": round(sum(v["net"] for v in p.values()), 2)})
    n = sum(v["n"] for v in p.values())
    print(f"{what}: {n} trades ({n - n0:+d}) | total {res[-1]['total']:+,.0f} | {fmt(p)}", flush=True)
    back = settled(p)
    if back != base:
        print("   (!) the chart did not come back to the same numbers:", fmt(back), flush=True)
        base = back
json.dump({"base": base, "tests": res}, open(Path(__file__).parent / "why_out" / "tv_filter_cuts.json", "w"), indent=1)
now = dict(zip(names, server.tv_eval(server.JS_STUDY)["values"]))
print("chart settings back as they were:", [k for k in names if now[k] != cur[k]] == [])
