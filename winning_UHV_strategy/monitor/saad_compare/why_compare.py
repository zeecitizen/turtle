"""Trade-by-trade: chart (with exit reason) vs Saad_strategy_1min in Zee's Blueberry MT5 (verbose log). Usage: py why_compare.py [from] [to]
Closes and reopens the Blueberry terminal. Prints one row per trade: TV#n ... | MT ... (empty side = unmatched)."""
import json, re, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import server

OUT = Path(__file__).parent / "why_out"; OUT.mkdir(exist_ok=True)
tv = server.read_tv()
json.dump(tv, open(OUT / "tv_why.json", "w"), indent=1)
sets = dict(tv["ea_sets"]); sets.update({"InpLog": "true", "InpVerbose": "true"})
r, rep = server.bb_live_run(sets, tv["period"], (sys.argv[1] if len(sys.argv) > 1 else "2026.10.11"), (sys.argv[2] if len(sys.argv) > 2 else "2026.10.17"), 0, "why_run")
print("MT5", {k: r.get(k) for k in ["net", "trades", "wr", "pf", "quality"]})
log = sorted(Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Tester\27280402C90F04230EE7E17540AE21E1").glob("Agent-*/logs/*.log"),
             key=lambda p: p.stat().st_mtime)[-1]
txt = log.read_text(encoding="utf-16", errors="ignore")
txt = txt[txt.rfind("testing of Experts\\Saad_strategy_1min"):]
ents, exits = {}, {}
for m in re.finditer(r"(\d{4}\.\d\d\.\d\d \d\d:\d\d:\d\d)\s+\[SAAD-1min\] ENTRY #(\d+) (BUY|SELL) [\d.]+ lots @ ([\d.]+) \| SL ([\d.]+).*?TP1 (.*?) \| setup", txt):
    ents[int(m.group(2))] = dict(t=m.group(1), side=m.group(3), en=float(m.group(4)), sl=float(m.group(5)), tp1=m.group(6))
for m in re.finditer(r"\[SAAD-1min\] EXIT #(\d+) (BUY|SELL) (\d{4}\.\d\d\.\d\d \d\d:\d\d:\d\d) @ ([\d.]+) \| entry [\d.]+ \| (.*?) \| best ([\d.]+) \| SL moves (\d+) \| net ([-+\d.]+)", txt):
    exits[int(m.group(1))] = dict(t=m.group(3), ex=float(m.group(4)), why=m.group(5), best=float(m.group(6)), moves=int(m.group(7)), net=float(m.group(8)))
mt = []
for k, e in sorted(ents.items()):
    x = exits.get(k, {})
    utc = (datetime.strptime(e["t"][:16], "%Y.%m.%d %H:%M") - timedelta(hours=3))
    mt.append(dict(num=k, side=e["side"], inT=utc, en=e["en"], sl=e["sl"], tp1=e["tp1"], why=x.get("why", "?"),
                   out=(datetime.strptime(x["t"][:16], "%Y.%m.%d %H:%M") - timedelta(hours=3)) if x else None,
                   ex=x.get("ex"), net=x.get("net"), best=x.get("best"), moves=x.get("moves")))
json.dump([{**m, "inT": str(m["inT"]), "out": str(m["out"])} for m in mt], open(OUT / "mt_why.json", "w"), indent=1)
P = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M")
used, rows = set(), []
for t in tv["trades"]:
    best = None
    for i, p in enumerate(mt):
        if i in used or p["side"] != t["side"]: continue
        d = abs((p["inT"] - P(t["in"])).total_seconds())
        if d <= 120 and (best is None or d < best[0]): best = (d, i)
    if best: used.add(best[1]); rows.append((P(t["in"]), t, mt[best[1]]))
    else: rows.append((P(t["in"]), t, None))
for i, p in enumerate(mt):
    if i not in used: rows.append((p["inT"], None, p))
rows.sort(key=lambda r: r[0])
for k, t, p in rows:
    a = f"TV#{t['num']:>3} {t['side'][0]} {t['in'][5:]} {t['en']:8.2f}->{t['out'][11:]} {t['pnl']:+8.0f} [{t.get('why','')[:34]}]" if t else " " * 72
    b = f"MT {p['side'][0]} {str(p['inT'])[5:16]} {p['en']:8.2f}->{str(p['out'])[11:16]} {p['net'] or 0:+8.0f} [{p['why'][:30]}] tp1={p['tp1'][:20]}" if p else ""
    print(a, "|", b)
