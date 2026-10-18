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
TESTS = [  # (what, {pine setting: value})
    ("trading hours off (all day)", {"fSessFrom": 0, "fSessTo": 24}),
    ("hours: start at midnight (keep the 6 PM PKT end)", {"fSessFrom": 0}),
    ("hours: no end (keep the 4 AM PKT start)", {"fSessTo": 24}),
    ("ADX filter off", {"fAdxMin": 0}),
    ("ATR minimum off ($4)", {"fAtrMin": 0}),
    ("ATR maximum off ($18)", {"fAtrMax": 0}),
    ("ATR band off (both)", {"fAtrMin": 0, "fAtrMax": 0}),
    ("chop filter off (0.24 -> 0)", {"iEr": 0}),
    ("chop filter back to the EA's 0.11", {"iEr": 0.11}),
    ("EMAs back to 9/50", {"iFast": 9, "iSlow": 50}),
    ("fast EMA back to 9", {"iFast": 9}),
    ("slow EMA back to 50", {"iSlow": 50}),
    ("break back to 2 pips (from 5)", {"iBreakP": 2}),
    ("ATR stop off -> 30 pips beyond the candle", {"iSlMode": PIPS}),
    ("ATR stop off -> the EA's 35 pips", {"iSlMode": PIPS, "iSlPips": 35}),
    ("ATR stop x2 -> x2.5", {"iSlAtrM": 2.5}),
    ("max risk back to $15 (from $20)", {"iMaxRisk": 15}),
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
print("NOW (optimizer pass):", fmt(base), flush=True)
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
    print(f"{'ALL GREEN ' if green else ''}{what}: {fmt(p)} | total {res[-1]['total']:+,.0f}", flush=True)
    back = settled(p)
    if back != base:
        print("   (!) the chart did not come back to the same numbers:", fmt(back), flush=True)
        base = back
json.dump({"base": base, "tests": res}, open(Path(__file__).parent / "why_out" / "tv_one_by_one.json", "w"), indent=1)
now = dict(zip(names, server.tv_eval(server.JS_STUDY)["values"]))
print("chart settings back as they were:", [k for k in names if now[k] != cur[k]] == [])
