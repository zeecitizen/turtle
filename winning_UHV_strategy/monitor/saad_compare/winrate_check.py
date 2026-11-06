"""winrate_check.py - Zee 2026-10-19: "can you check if the indicator ... is showing the correct winrate. its not counting trades twice
or something?"  Reads the Saad indicator three independent ways in one go and checks they agree:
  1. the month panel (bottom right: nT / nW / nL counters, updated at each exit)
  2. the trade export table (every remembered trade with its exit time and P/L; switched on for a few seconds, then off again)
  3. the EXIT #n labels on the chart
and that no trade number, and no entry (time + side + price), appears twice. Writes why_out/winrate_check.json.
    py winrate_check.py
"""
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
import server  # noqa: E402

NODE = r"C:\Program Files\nodejs\node.exe"
CLI = r"C:/Users/zeesh/Documents/GitHub/tradingview-mcp/src/cli/index.js"


def cli(*a):
    r = subprocess.run([NODE, CLI, *a], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180)
    return json.loads(r.stdout)


def tables():
    return {t["rows"][0]: t["rows"] for t in cli("data", "tables", "-f", "Saad")["studies"][0]["tables"] if t.get("rows")}


def month_panel(T):
    rows = next((v for k, v in T.items() if "Win rate" in k and "Net" in k), [])
    out = {}
    for r in rows[1:]:
        m = re.match(r"(\w+ \d{4})\*? \| (\d+)% \| ([+-]\$[\d,.]+) \| (\d+) tr · (\d+)W/(\d+)L", r)
        if m:
            out[m.group(1)] = {"wr": int(m.group(2)), "net": float(m.group(3).replace("$", "").replace(",", "")), "n": int(m.group(4)),
                               "w": int(m.group(5)), "l": int(m.group(6))}
    return out


def money(s):
    return float(s.replace("$", "").replace(",", "").replace("+", "").replace("−", "-"))


# every table comes from ONE read (one CDP call = one calculation of the indicator), so the panel and the export always agree on the
# settings even while Zee edits the chart; the labels are a second read, kept only if the tables read after them are unchanged
st = server.tv_eval(server.JS_STUDY)
names = server.pine_inputs()
k = names.index("exOn")
server.set_input(st["id"], k, True)
time.sleep(8)
for attempt in range(5):
    B = tables()
    labels = cli("data", "labels", "-f", "Saad", "-n", "500")["studies"][0]["labels"]
    B2 = tables()
    stable = B == B2
    if stable:
        break
    time.sleep(10)
server.set_input(st["id"], k, False)
changed = []

exp = next((v for kk, v in B.items() if kk.startswith("# | side")), [])
trades = []
for r in exp[1:]:
    c = [x.strip() for x in r.split("|")]
    if len(c) >= 8 and c[0].isdigit():
        trades.append({"num": int(c[0]), "side": c[1], "en_t": c[2], "en": c[3], "ex_t": c[5], "pnl": money(c[7])})
dup_num = [n for n, c in Counter(t["num"] for t in trades).items() if c > 1]
dup_entry = [e for e, c in Counter((t["en_t"], t["side"], t["en"]) for t in trades).items() if c > 1]
by_m = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "z": 0, "net": 0.0})
for t in trades:
    m = time.strftime("%b %Y", time.strptime(t["ex_t"][:7], "%Y-%m"))
    d = by_m[m]
    d["n"] += 1; d["net"] += t["pnl"]
    d["w" if t["pnl"] > 0 else "l" if t["pnl"] < 0 else "z"] += 1

lab = {}
for L in labels:
    m = re.match(r"EXIT #(\d+)\n([+-]\$[\d,.]+)", L["text"] or "")
    if m:
        lab.setdefault(int(m.group(1)), []).append(money(m.group(2)))
dup_lab = [n for n, v in lab.items() if len(v) > 1]
pnl_of = {t["num"]: t["pnl"] for t in trades}
lab_mismatch = [(n, v[0], pnl_of.get(n)) for n, v in lab.items() if n in pnl_of and abs(v[0] - pnl_of[n]) > 0.051]

P = month_panel(B)
D = next((v for kk, v in B.items() if kk.startswith("Last 30 days") or kk.startswith("Days in the range")), [])
d30 = {"n": 0, "w": 0.0, "net": 0.0}
for r in D[1:-1]:
    c = [x.strip() for x in r.split("|")]
    d30["n"] += int(c[1]); d30["w"] += int(c[1]) * int(c[2].rstrip("%")) / 100; d30["net"] += money(c[3])
print(f"chart {st['symbol']} {st['res']} min | labels read while the chart stood still: {stable}")
print(f"30-day box: rows add up to {d30['n']} trades, ~{d30['w']:.0f} wins, {d30['net']:+,.2f} | its own total line: {D[-1] if D else '-'}")
print(f"export table: {len(trades)} trades (#{trades[0]['num'] if trades else '-'} - #{trades[-1]['num'] if trades else '-'}) | "
      f"duplicate trade numbers: {dup_num} | duplicate entries (same time, side, price): {dup_entry}")
print(f"EXIT labels: {len(lab)} trades | a trade number with two EXIT labels: {dup_lab} | label P/L different from the export: {lab_mismatch[:5]}")
print("month | panel: trades W/L WR net | export (by exit time, UTC): trades W/L/zero WR net")
for m, p in P.items():
    e = by_m.get(m, {})
    ewr = 100 * e.get("w", 0) / e["n"] if e.get("n") else 0
    print(f"{m} | {p['n']} {p['w']}W/{p['l']}L {p['wr']}% {p['net']:+,.2f} | {e.get('n')} {e.get('w')}W/{e.get('l')}L/{e.get('z')} {ewr:.1f}% {e.get('net', 0):+,.2f}")
json.dump({"stable": stable, "changed": changed, "panel": P, "export_by_month": by_m, "trades": trades, "dup_num": dup_num, "dup_entry": dup_entry,
           "dup_labels": dup_lab, "label_mismatch": lab_mismatch}, open(Path(__file__).parent / "why_out" / "winrate_check.json", "w"), indent=1)
