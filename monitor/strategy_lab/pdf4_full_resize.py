"""pdf4_full_resize.py — comprehensive lot/trail/fearIdeal sweep with realistic execution."""
from __future__ import annotations
import sys, random
from pathlib import Path
LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from pdf4_trail_resize import run

random.seed(42)

print("=" * 100)
print("PDF #4 — FULL LOT SIZE SWEEP under realistic execution")
print("=" * 100)

print()
print("--- Lot sweep at trail 12/4 ---")
for lot in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.70]:
    run(f"trail 12/4, lot {lot}", trail_trigger=12, trail_drop=4, lot_start=lot)

print()
print("--- Lot sweep at trail 20/8 (PDF prefers wider trail) ---")
for lot in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.70]:
    run(f"trail 20/8, lot {lot}", trail_trigger=20, trail_drop=8, lot_start=lot)

print()
print("--- Lot sweep at trail 25/8 ---")
for lot in [0.10, 0.20, 0.30, 0.40]:
    run(f"trail 25/8, lot {lot}", trail_trigger=25, trail_drop=8, lot_start=lot)

print()
print("--- BEST CANDIDATE FINE-TUNE ---")
# The winners from earlier: 0.2 lot + 12/4 = $126/67%, 0.1 lot + 30/10 = $91/50%
for lot, tt, td in [(0.20, 12, 4), (0.20, 15, 5), (0.20, 18, 6), (0.20, 20, 8), (0.25, 12, 4), (0.15, 12, 4), (0.30, 12, 4)]:
    run(f"trail {tt}/{td}, lot {lot} ⭐", trail_trigger=tt, trail_drop=td, lot_start=lot)
