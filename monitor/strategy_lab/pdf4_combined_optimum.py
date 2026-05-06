"""pdf4_combined_optimum.py — stack the per-parameter winners from realistic re-tune.

Single best changes vs LIVE baseline:
  - trail 30/10 (was 12/4) → +$128 improvement
  - burst-delta lb 5s (was 15s) → +$46 improvement, 87.5% WR vs 79%
  - spread 1.05x (was 1.2x) → +2% WR, slight $ cost
  - fearIdeal $80 (was $100) → +$30 improvement

Goal: stack them and see if combined beats baseline by even more.
"""
from __future__ import annotations
import sys
from pathlib import Path
LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from pdf4_realistic_retune import run

print("=" * 100)
print("REALISTIC ULTIMATE STACK — combine winners from re-tune")
print("All under Direct Raw + 0.3 lots execution")
print("=" * 100)

print()
print("--- SINGLES (re-confirm) ---")
run("LIVE baseline (12/4 trail, bd=15, spr=1.2, fi=100)")
run("+ trail 30/10", trail_t=30, trail_d=10)
run("+ burst_delta=5s", burst_delta_lb=5)
run("+ burst_delta=60s", burst_delta_lb=60)
run("+ spread 1.05x", spread_mult=1.05)
run("+ fearIdeal=80", fear_ideal=80)
run("+ trigger_past 0pt", trigger_past_pts=0.0)

print()
print("--- TWO-WAY COMBOS ---")
run("trail 30/10 + bd=5s", trail_t=30, trail_d=10, burst_delta_lb=5)
run("trail 30/10 + bd=60s", trail_t=30, trail_d=10, burst_delta_lb=60)
run("trail 30/10 + spr 1.05x", trail_t=30, trail_d=10, spread_mult=1.05)
run("trail 30/10 + fi=80", trail_t=30, trail_d=10, fear_ideal=80)
run("bd=5s + spr 1.05x", burst_delta_lb=5, spread_mult=1.05)
run("bd=60s + spr 1.05x", burst_delta_lb=60, spread_mult=1.05)

print()
print("--- THREE-WAY COMBOS ---")
run("trail 30/10 + bd=5s + spr 1.05x", trail_t=30, trail_d=10, burst_delta_lb=5, spread_mult=1.05)
run("trail 30/10 + bd=5s + fi=80", trail_t=30, trail_d=10, burst_delta_lb=5, fear_ideal=80)
run("trail 30/10 + bd=60s + spr 1.05x", trail_t=30, trail_d=10, burst_delta_lb=60, spread_mult=1.05)
run("trail 30/10 + bd=60s + fi=80", trail_t=30, trail_d=10, burst_delta_lb=60, fear_ideal=80)
run("trail 25/8 + bd=5s + spr 1.05x", trail_t=25, trail_d=8, burst_delta_lb=5, spread_mult=1.05)

print()
print("--- ULTIMATE: ALL FOUR WINNERS STACKED ---")
run("ULTIMATE: trail 30/10 + bd=5s + spr 1.05x + fi=80",
    trail_t=30, trail_d=10, burst_delta_lb=5, spread_mult=1.05, fear_ideal=80)
run("ULTIMATE-B: trail 30/10 + bd=60s + spr 1.05x + fi=80",
    trail_t=30, trail_d=10, burst_delta_lb=60, spread_mult=1.05, fear_ideal=80)
run("ULTIMATE-C: trail 25/8 + bd=5s + spr 1.05x + fi=80",
    trail_t=25, trail_d=8, burst_delta_lb=5, spread_mult=1.05, fear_ideal=80)
