"""mfe_distribution_v279.py — Answer Zee's question: how far do trades travel into positive?

For each canonical UHV M1 fire detected with v2.79 gates, walk the tick data forward
and measure the Max Favorable Excursion (MFE) — i.e., the peak unrealized profit
before the trade either reverses or hits SL.

This tells us where the OPTIMAL exit/lock distance is.
"""
from __future__ import annotations
import sys, csv
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab")
import screener_canonical_uhv_m1 as m1

# Match v2.79 EA gate values
m1.HARD_TREND = False                  # bloom mandate (no trend gate)
m1.UHV_BODY_MIN = 0.50                 # v2.79 restored
m1.BREAKOUT_VOL_MAX_RATIO = 0.75       # v2.79 restored
m1.MOM_THRESH = 0.65
m1.MIN_BREAKOUT_PENETRATION = 0.30

CSV_DIR = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files")
# Use the most recent tick days we have (June 2026 data)
csvs = sorted(CSV_DIR.glob("shano_ticks_2026-06-*.csv"))
print(f"Loading {len(csvs)} tick CSVs: {[p.name for p in csvs]}")

bars = m1.build_m1(csvs)
print(f"Built {len(bars)} M1 bars")
fires = m1.detect(bars)
print(f"Detected {len(fires)} M1 fires with v2.79 gate values")

# Load raw ticks (bid/ask per timestamp) for the window
ticks = []
for p in csvs:
    with p.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = row.get("ts_broker") or row.get("ts") or row.get("t")
            if not ts: continue
            if "." in ts.split(" ", 1)[-1]: ts = ts.rsplit(".", 1)[0]
            try: dt = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
            except ValueError: continue
            try:
                bid = float(row["bid"]); ask = float(row["ask"])
            except (KeyError, ValueError): continue
            ticks.append((dt, bid, ask))
ticks.sort()
print(f"Loaded {len(ticks)} ticks")

# For each fire, measure MFE (peak favorable excursion)
results = []
for f in fires:
    open_dt = datetime.strptime(f.open_t, "%Y-%m-%d %H:%M")
    entry_idx = None
    for j, (t, b, a) in enumerate(ticks):
        if t > open_dt:
            entry_idx = j; break
    if entry_idx is None: continue
    entry_price = ticks[entry_idx][2] if f.side == "BUY" else ticks[entry_idx][1]
    # Walk forward 5 minutes max (M1 scalp horizon)
    mfe = 0.0
    mae = 0.0
    cap_until = ticks[entry_idx][0] + timedelta(seconds=300)
    for k in range(entry_idx, min(entry_idx + 2000, len(ticks))):
        t, b, a = ticks[k]
        if t > cap_until: break
        cur_price = b if f.side == "BUY" else a
        delta = (cur_price - entry_price) if f.side == "BUY" else (entry_price - cur_price)
        if delta > mfe: mfe = delta
        if delta < -mae: mae = -delta
        # Stop if hit -2pt SL (canonical SL distance)
        if mae >= 2.0: break
    results.append(dict(side=f.side, open_t=f.open_t, entry=entry_price, mfe=mfe, mae=mae))

if not results:
    print("\nNo fires/results — exiting"); sys.exit(0)

# Tally MFE distribution
print(f"\n=== MFE DISTRIBUTION (n={len(results)} fires, v2.79 gates) ===")
print(f"\n%% reaching given MFE threshold:")
for thresh_pt in [0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 5.00]:
    cnt = sum(1 for r in results if r["mfe"] >= thresh_pt)
    pct = 100 * cnt / len(results)
    bar = "#" * int(pct / 2)
    print(f"  >= +{thresh_pt:.2f}pt  ({thresh_pt*0.30*100:5.1f}usd@0.30lots)  {cnt:3d}  ({pct:5.1f}%)  {bar}")

print(f"\nFine-grained MFE histogram (buckets):")
buckets = [(0.00,0.05),(0.05,0.10),(0.10,0.20),(0.20,0.30),(0.30,0.50),
            (0.50,0.75),(0.75,1.00),(1.00,1.50),(1.50,2.00),(2.00,3.00),(3.00,10.00)]
for lo, hi in buckets:
    cnt = sum(1 for r in results if lo <= r["mfe"] < hi)
    pct = 100 * cnt / len(results)
    bar = "#" * int(pct / 2)
    print(f"  +{lo:.2f} to +{hi:.2f}pt:  {cnt:3d}  ({pct:5.1f}%)  {bar}")

# Stats
mfes = sorted([r["mfe"] for r in results])
print(f"\n  Min MFE:    +{mfes[0]:.3f}pt")
print(f"  Max MFE:    +{mfes[-1]:.3f}pt")
print(f"  Mean MFE:   +{sum(mfes)/len(mfes):.3f}pt")
print(f"  Median MFE: +{mfes[len(mfes)//2]:.3f}pt")
print(f"  25th pct:   +{mfes[len(mfes)//4]:.3f}pt")
print(f"  75th pct:   +{mfes[3*len(mfes)//4]:.3f}pt")

# Simulate optimal lock distance: if we lock at +X, how much profit per 0.30 lots?
print(f"\n=== SIMULATED EV (per trade) AT VARIOUS LOCK DISTANCES (0.30 lots) ===")
sl_loss = 2.0 * 0.30 * 100  # canonical SL = 2pt at 0.30 lots = $60
sl_loss = 60
print(f"  SL hit cost: ${sl_loss:.2f}  (2pt × 0.30 lots × 100)")
print()
for lock_pt in [0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00, 1.50, 2.00]:
    wins = sum(1 for r in results if r["mfe"] >= lock_pt)
    losses = len(results) - wins
    win_amount = lock_pt * 0.30 * 100  # USD
    total = wins * win_amount - losses * sl_loss
    per_trade = total / len(results)
    wr = 100 * wins / len(results)
    print(f"  Lock @ +{lock_pt:.2f}pt (${win_amount:5.2f}):  WR={wr:5.1f}%  Total=${total:+8.2f}  EV/trade=${per_trade:+5.2f}")

# Save results
out_path = Path(r"C:/Users/zeesh/Documents/GitHub/turtle/monitor/strategy_lab/_canonical/mfe_v279_results.csv")
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["side","open_t","entry","mfe","mae"])
    w.writeheader()
    for r in results: w.writerow(r)
print(f"\nResults saved: {out_path}")
