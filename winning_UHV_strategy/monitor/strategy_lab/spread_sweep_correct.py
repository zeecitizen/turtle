"""spread_sweep_correct.py — sweep spread filter using EA-faithful measurement."""
from __future__ import annotations
import sys
from pathlib import Path
LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from filter_loo_correct import run

print("=" * 200)
print("SPREAD FILTER SWEEP (with correct tick-speed=15s)")
print("=" * 200)

print()
print("--- BASELINE: LIVE (tick_speed=15s, spread=1.3x) ---")
run("LIVE corrected (tick=15, spread=1.3)")

print()
print("--- SPREAD SWEEP (keep tick_speed=15s) ---")
for mult in [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 2.0, 2.5, 3.0]:
    run(f"spread<={mult}x", spread_mult=mult)
run("spread OFF", spread_mult=0)

print()
print("--- SPREAD SWEEP at LOOSER tick_speed=30s ---")
for mult in [1.0, 1.3, 1.5, 1.8, 2.0]:
    run(f"tick=30 + spread<={mult}x", tick_speed_sec=30, spread_mult=mult)
run("tick=30 + spread OFF", tick_speed_sec=30, spread_mult=0)

print()
print("--- DISTRIBUTION CHECK: spread of qualifying probes ---")
import csv
from datetime import datetime, timedelta
from unified_backtester import SHADOW_CSV, ticks_in_range, CONTRACT_SIZE

PROBE_LOTS = 0.01
PROBE_CONFIRM = 0.45
rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
rows.sort(key=lambda r: r.get("entry_time", ""))

ratios_at_confirm = []
for r in rows:
    try:
        entry_time = datetime.fromisoformat(r["entry_time"])
        close_time = datetime.fromisoformat(r["close_time"])
        entry_price = float(r["entry_price"])
        dir_sign = 1 if r["dir"] == "buy" else -1
    except (ValueError, KeyError): continue
    ticks = ticks_in_range(entry_time, close_time)
    if not ticks: continue
    confirm_dt = None
    for dt, bid, ask in ticks:
        if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
        else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
        if fav >= PROBE_CONFIRM:
            confirm_dt = dt; cur_bid = bid; cur_ask = ask; break
    if confirm_dt is None: continue

    # Sample spread baseline: 1 sample per second over last 60s
    samples = []
    for sec_ago in range(60, 0, -1):
        t = confirm_dt - timedelta(seconds=sec_ago)
        st = ticks_in_range(t, t + timedelta(seconds=1))
        if st:
            _, b, a = st[0]
            samples.append(a - b)
    if len(samples) < 30: continue
    med = sorted(samples)[len(samples)//2]
    if med <= 0: continue
    cur_spread = cur_ask - cur_bid
    ratio = cur_spread / med
    ratios_at_confirm.append((ratio, cur_spread, med))

ratios_at_confirm.sort()
n = len(ratios_at_confirm)
print(f"\nDistribution of spread-ratio (cur/median) at probe confirm time, {n} probes:")
if n:
    print(f"  min={ratios_at_confirm[0][0]:.2f}  Q1={ratios_at_confirm[n//4][0]:.2f}  median={ratios_at_confirm[n//2][0]:.2f}  Q3={ratios_at_confirm[3*n//4][0]:.2f}  max={ratios_at_confirm[-1][0]:.2f}")
    above_13 = sum(1 for r, _, _ in ratios_at_confirm if r > 1.3)
    above_15 = sum(1 for r, _, _ in ratios_at_confirm if r > 1.5)
    above_20 = sum(1 for r, _, _ in ratios_at_confirm if r > 2.0)
    print(f"  Probes with ratio > 1.3x: {above_13}/{n}")
    print(f"  Probes with ratio > 1.5x: {above_15}/{n}")
    print(f"  Probes with ratio > 2.0x: {above_20}/{n}")
