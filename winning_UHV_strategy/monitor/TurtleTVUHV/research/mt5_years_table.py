"""print the MT5 year table from mt5_years.json (win rate solved from MT5's trades, net, average win and loss); arg = chart period (default M15)
    py mt5_years_table.py [M15|M5|M1]"""
import json, sys
PER = sys.argv[1] if len(sys.argv) > 1 else "M15"
rows = [r for r in json.load(open("mt5_years.json")) if r.get("period", "M1") == PER]
def wr(r):
    t = r.get("trade_stats") or {}; n = t.get("n") or 0; aw, al = t.get("avg_win") or 0, t.get("avg_loss") or 0
    return None if not n or aw == al else 100 * (r["net"] - n * al) / (aw - al) / n
keys = []
for r in rows:
    if (r["gate"], r["delay"]) not in keys: keys.append((r["gate"], r["delay"]))
print(f"{PER} chart")
print(f"{'gate':44s} {'delay':6s} " + " ".join(f"{y:>22d}" for y in (2023, 2024, 2025, 2026)) + "   TOTAL (net, trades, WR, worst, trading days)")
for g, d in keys:
    line, tot, n, w, worst, days = [], 0, 0, 0, 0, 0
    for y in (2023, 2024, 2025, 2026):
        r = next((x for x in rows if x["gate"] == g and x["delay"] == d and x["year"] == y), None)
        if not r or r.get("error"): line.append(f"{'ERR ' + str(r and r.get('error')):>22s}"); continue
        q = wr(r) or 0; t = r.get("trade_stats") or {}; tn = t.get("n") or 0
        line.append(f"{r['net']:>+10,.0f} {tn:4d} {q:5.1f}%"); tot += r["net"]; n += tn; w += q * tn / 100; worst = min(worst, t.get("largest_loss") or 0); days += r.get("trade_days") or 0
    print(f"{g[5:] if g.startswith('save:') else g:44s} {d:6s} " + " ".join(line) + f"   {tot:+10,.0f} {n:5d} {100 * w / max(1, n):5.2f}% {worst:+7,.0f} {days or '':>5}")
