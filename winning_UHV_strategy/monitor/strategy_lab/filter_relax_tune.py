"""filter_relax_tune.py — find optimal threshold for tick_speed_max + spread_max.

LOO showed:
  - tick_speed_max=15s blocks 15 probes; removing entirely → +$607 / +1 losing
  - spread_max=1.3 blocks 1 probe; removing → +$131 / 0 losing

Test relaxed thresholds for both individually and combined.
"""
from __future__ import annotations
import sys
from pathlib import Path
LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from filter_loo_test import run

print("=" * 200)
print("RELAX TUNE — find sweet spot for tick_speed and spread thresholds")
print("=" * 200)

print()
print("--- BASELINE (current LIVE: tick<=15s, spread<=1.3x) ---")
run("LIVE", tick_speed_max=True, tick_speed_sec=15, spread_max=True, spread_mult=1.3)

print()
print("--- TICK-SPEED SWEEP (keep spread=1.3) ---")
for sec in [20, 25, 30, 45, 60, 90, 120]:
    run(f"tick_speed<={sec}s", tick_speed_max=True, tick_speed_sec=sec)
run("tick_speed OFF", tick_speed_max=False)

print()
print("--- SPREAD SWEEP (keep tick=15s) ---")
for m in [1.5, 1.8, 2.0, 2.5, 3.0]:
    run(f"spread<={m}x", spread_max=True, spread_mult=m)
run("spread OFF", spread_max=False)

print()
print("--- BAD-HOURS RELAX OPTIONS ---")
run("bad_hours OFF", skip_bad_hours=False)

print()
print("--- COMBINED RELAX CANDIDATES ---")
run("tick<=30s + spread=1.3", tick_speed_sec=30)
run("tick<=45s + spread=1.3", tick_speed_sec=45)
run("tick<=60s + spread=1.3", tick_speed_sec=60)
run("tick<=30s + spread<=1.5x", tick_speed_sec=30, spread_mult=1.5)
run("tick<=45s + spread<=1.5x", tick_speed_sec=45, spread_mult=1.5)
run("tick<=60s + spread<=1.5x", tick_speed_sec=60, spread_mult=1.5)
run("tick OFF + spread<=1.5x", tick_speed_max=False, spread_mult=1.5)
run("tick OFF + spread OFF", tick_speed_max=False, spread_max=False)
run("tick OFF + spread OFF + bad_hours OFF", tick_speed_max=False, spread_max=False, skip_bad_hours=False)
