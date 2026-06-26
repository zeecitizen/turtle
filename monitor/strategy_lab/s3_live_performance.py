"""s3_live_performance.py — S3 actual live trade history from fills."""
import csv, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

# S3 decisions: col[1]=EA, col[15]=position_ticket, col[16]=magic(88003)
s3_tickets = set()
with open(COMMON / "s3_decisions.csv", "r") as f:
    for row in f:
        p = row.strip().split(",")
        if len(p) < 17: continue
        ticket = p[14].strip()  # col[14] = position_ticket for S3
        if ticket and ticket not in ("0", "0.00", "", "88003"):
            s3_tickets.add(ticket)

print(f"S3 position tickets found: {len(s3_tickets)}")

# Match turtle fills
trades = []
with open(COMMON / "turtle_fills.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["position_ticket"].strip() in s3_tickets:
            trades.append({
                "date":    row["broker_time"][:10],
                "time":    row["broker_time"][11:19],
                "lots":    float(row["volume"]),
                "net":     float(row["net_pnl"]),
                "comment": row["comment"],
            })

trades.sort(key=lambda x: x["date"] + x["time"])

print(f"\n{'Date':<12} {'Time':<9} {'Lots':<6} {'Net P&L':>9}  Result   Comment")
print("-" * 72)

by_day = {}
total  = 0.0
wins   = 0

for t in trades:
    m = "WIN" if t["net"] > 0 else "SL "
    print(f"{t['date']}  {t['time']}  {t['lots']:<6} ${t['net']:>+8.2f}  {m}   {t['comment']}")
    total += t["net"]
    if t["net"] > 0: wins += 1
    by_day[t["date"]] = by_day.get(t["date"], 0.0) + t["net"]

n = len(trades)
if n == 0:
    print("No S3 trades matched. Check s3_decisions.csv column layout.")
    sys.exit()

print()
print("-" * 72)
wr    = wins / n * 100
avg_w = sum(t["net"] for t in trades if t["net"] > 0) / wins if wins else 0
avg_l = sum(t["net"] for t in trades if t["net"] <= 0) / (n - wins) if (n - wins) else 0
ev    = (wr / 100) * avg_w + (1 - wr / 100) * avg_l
print(f"TOTAL : {n} trades | {wins}W / {n-wins}L | WR={wr:.1f}%")
print(f"Avg W : ${avg_w:+.2f}   Avg L: ${avg_l:+.2f}   EV/trade: ${ev:+.2f}")
print(f"Net   : ${total:+.2f}")

print("\nDaily P&L:")
for d in sorted(by_day):
    pnl  = by_day[d]
    mark = "GREEN" if pnl > 0 else "RED"
    print(f"  {d}  ${pnl:>+8.2f}  {mark}")

green = sum(1 for p in by_day.values() if p > 0)
red   = len(by_day) - green
print(f"\n  {green} green / {red} red days out of {len(by_day)} trading days")
