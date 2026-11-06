"""pdf3_combo_test.py — combine the two winners from pdf3_deep_mine.

Top 2 winners on top of LIVE (Setup 1 + burst-delta-15s):
  - CDD-div exit (10s check, 60s window) — $1320 / 90.3% / 1 losing
  - Trigger >= 0.3pt past UHV — $1275 / 90.7% / 0 losing

Goal: stack them and see if they multiply.
"""
from __future__ import annotations
import sys
from pathlib import Path
LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))

# Reuse pdf3_deep_mine_test infrastructure
from pdf3_deep_mine_test import run

print("=" * 200)
print("PDF #3 COMBO — stacking CDD-div exit + trigger>=Npt past UHV")
print("All on top of LIVE (Setup 1 lb=3 + burst-delta-15s)")
print("=" * 200)

print()
print("--- Singles (re-confirm) ---")
run("LIVE baseline", require_burst_delta=True)
run("LIVE + CDD-div(10s/60s)", cdd_div_exit=True, cdd_check_sec=10, cdd_window_sec=60)
run("LIVE + trigger>=0.3pt", require_trigger_past=True, trigger_past_pts=0.3)
run("LIVE + trigger>=0.5pt", require_trigger_past=True, trigger_past_pts=0.5)
run("LIVE + trigger>=1.0pt", require_trigger_past=True, trigger_past_pts=1.0)

print()
print("--- Pair: CDD-div + trigger-past-UHV ---")
for cs, cw in [(10, 60), (10, 30), (5, 15)]:
    for pts in [0.3, 0.5, 1.0, 1.5]:
        run(f"+ CDD({cs}/{cw}) + trigger>={pts}pt",
            cdd_div_exit=True, cdd_check_sec=cs, cdd_window_sec=cw,
            require_trigger_past=True, trigger_past_pts=pts)

print()
print("--- CDD-div with finer tuning ---")
for cs, cw in [(7, 45), (10, 90), (15, 60), (15, 90), (20, 60)]:
    run(f"+ CDD({cs}/{cw})",
        cdd_div_exit=True, cdd_check_sec=cs, cdd_window_sec=cw)
