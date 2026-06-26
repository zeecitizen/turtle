"""nsnd_live_performance.py — Analyse NSND's actual live trade history from fills."""
import csv, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

# Load NSND decisions to get position tickets
nsnd_tickets = set()
with open(COMMON / "nsnd_decisions.csv", "r") as f:
    for row in f:
        p = row.strip().split(",")
        if len(p) < 17: continue
        ticket = p[15].strip()  # col[15] = position_ticket
        if ticket and ticket not in ("0.00", "0", "", "88006"):
            nsnd_tickets.add(ticket)

print(f"NSND position tickets: {nsnd_tickets}\n")

# Load turtle fills and match
trades = []
with open(COMMON / "turtle_fills.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        pos = row["position_ticket"].strip()
        if pos in nsnd_tickets:
            trades.append({
                "date":    row["broker_time"][:10],
                "time":    row["broker_time"][11:],
                "side":    row["direction"],
                "lots":    float(row["volume"]),
                "net":     float(row["net_pnl"]),
                "gross":   float(row["profit"]),
                "comment": row["comment"],
                "ticket":  pos,
            })

trades.sort(key=lambda x: x["date"] + x["time"])

print(f"{'Date':<12} {'Time':<10} {'Side':<15} {'Lots':<6} {'Net P&L':>9}  {'Result'}  Comment")
print("-" * 80)

by_day = {}
total = 0.0
wins  = 0

for t in trades:
    marker = "WIN" if t["net"] > 0 else "SL "
    sign   = "+" if t["net"] > 0 else ""
    print(f"{t['date']:<12} {t['time']:<10} {t['side']:<15} {t['lots']:<6} "
          f"${sign}{t['net']:>7.2f}  {marker}    {t['comment']}")
    total += t["net"]
    if t["net"] > 0: wins += 1
    by_day[t["date"]] = by_day.get(t["date"], 0.0) + t["net"]

n = len(trades)
print()
print("-" * 80)
wr = wins / n * 100 if n else 0
avg_w = sum(t["net"] for t in trades if t["net"] > 0) / wins if wins else 0
avg_l = sum(t["net"] for t in trades if t["net"] <= 0) / (n - wins) if (n - wins) else 0
ev    = (wr/100) * avg_w + (1 - wr/100) * avg_l
print(f"TOTAL : {n} trades  |  {wins}W / {n-wins}L  |  WR={wr:.1f}%")
print(f"Avg W : ${avg_w:+.2f}    Avg L: ${avg_l:+.2f}    EV/trade: ${ev:+.2f}")
print(f"Net   : ${total:+.2f}")

print("\nDaily P&L:")
print(f"  {'Date':<12} {'P&L':>9}  {'Result'}")
print(f"  {'-'*35}")
for day in sorted(by_day):
    pnl  = by_day[day]
    mark = "GREEN" if pnl > 0 else "RED  "
    print(f"  {day:<12} ${pnl:>+8.2f}  {mark}")

pos_days = sum(1 for p in by_day.values() if p > 0)
neg_days = sum(1 for p in by_day.values() if p <= 0)
print(f"\n  {pos_days} green days / {neg_days} red days out of {len(by_day)} trading days")
print(f"\nConclusion:")
if total > 0 and wr > 50:
    print("  NSND is NET POSITIVE — keeping it is justified.")
elif total > 0 and wr <= 50:
    print("  NSND is net positive but low WR — positive EV, keep but monitor.")
elif total < 0:
    print("  NSND is NET NEGATIVE on real fills — worth investigating or pausing.")
