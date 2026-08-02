"""feb11_hot_hours.py — find the high-volatility hours on Feb 11 where Zee made $835."""
from __future__ import annotations
import csv, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

CSV = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/shano_ticks_2026-02-11.csv")

# Bucket by hour: count ticks + measure price range per hour
buckets = defaultdict(lambda: dict(n=0, hi=-1e9, lo=1e9, first=None, last=None))
with CSV.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        ts = row.get("ts_broker") or row.get("ts") or row.get("t")
        if not ts: continue
        if "." in ts.split(" ", 1)[-1]: ts = ts.rsplit(".", 1)[0]
        try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
        except ValueError: continue
        try: bid = float(row["bid"]); ask = float(row["ask"])
        except: continue
        h = dt.hour
        b = buckets[h]
        b["n"] += 1
        mid = (bid + ask) / 2
        if mid > b["hi"]: b["hi"] = mid
        if mid < b["lo"]: b["lo"] = mid
        if b["first"] is None: b["first"] = mid
        b["last"] = mid

print(f"FEB 11 BROKER-HOUR VOLATILITY ANALYSIS")
print(f"{'hr (broker)':12s} {'ticks':>6s} {'range pts':>10s} {'net move':>10s} {'1st→last':>12s}")
total_n = sum(b["n"] for b in buckets.values())
hot = []
for h in sorted(buckets.keys()):
    b = buckets[h]
    rng = b["hi"] - b["lo"]
    net = b["last"] - b["first"]
    pct_ticks = 100 * b["n"] / total_n
    marker = " 🔥" if (rng >= 5.0 or b["n"] > total_n / 24 * 1.5) else ""
    print(f"  {h:02d}:00-{h:02d}:59 {b['n']:>5d}  {rng:>8.2f}  {net:>+9.2f}  {b['first']:>4.2f}→{b['last']:>4.2f}{marker}")
    if rng >= 5.0:
        hot.append(h)

print(f"\nTOTAL: {total_n} ticks across {len(buckets)} hours")
print(f"HOT HOURS (range >= 5pt): {sorted(hot)}")
print(f"  → these are the windows Zee most likely traded heavily")
