"""pdf4_monte_carlo.py — Directive Epsilon: Monte Carlo Risk of Ruin.

Per PDF: extract Pw, Pl, avg W, avg L from realistic backtest, run 10,000
permutations of 1,000-trade sequences, find probability of hitting drawdown.
"""
from __future__ import annotations
import random, statistics
random.seed(42)

# Empirical metrics from pdf4_full_resize.py results
# Best realistic candidate: trail 12/4 + lot 0.2
P_WIN = 0.667           # 67% per-main WR
AVG_WIN = 15.80         # average winning trade $
AVG_LOSS = -10.40       # average losing trade $ (negative)

# Account
STARTING_EQUITY = 2296.25  # current account
RUIN_THRESHOLD_PCT = 30.0  # 30% drawdown = ruin
RUIN_DOLLAR = STARTING_EQUITY * (RUIN_THRESHOLD_PCT / 100.0)

# Simulation
N_PERMUTATIONS = 10_000
TRADES_PER_PERM = 1_000


def simulate_one():
    """Run 1000 trades, track max drawdown."""
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    for _ in range(TRADES_PER_PERM):
        if random.random() < P_WIN:
            eq += AVG_WIN
        else:
            eq += AVG_LOSS
        if eq > peak: peak = eq
        dd = peak - eq
        if dd > max_dd: max_dd = dd
    return eq, max_dd


def run_mc(label, p_win, avg_w, avg_l):
    global P_WIN, AVG_WIN, AVG_LOSS
    P_WIN = p_win; AVG_WIN = avg_w; AVG_LOSS = avg_l
    finals = []; max_dds = []
    ruin_count = 0
    for _ in range(N_PERMUTATIONS):
        f, md = simulate_one()
        finals.append(f); max_dds.append(md)
        if md >= RUIN_DOLLAR: ruin_count += 1
    finals.sort(); max_dds.sort()
    n = len(finals)
    print(f"  {label}")
    print(f"    Pw={p_win:.2%} avgW=${avg_w:+.2f} avgL=${avg_l:+.2f} expectancy=${p_win*avg_w + (1-p_win)*avg_l:+.2f}/trade")
    print(f"    Final equity over 1000 trades:")
    print(f"      median: ${finals[n//2]:+.0f}    Q1: ${finals[n//4]:+.0f}    Q3: ${finals[3*n//4]:+.0f}")
    print(f"      worst:  ${finals[0]:+.0f}      best: ${finals[-1]:+.0f}")
    print(f"      P(loss): {sum(1 for f in finals if f < 0)/n*100:.1f}%")
    print(f"    Max drawdown:")
    print(f"      median: ${max_dds[n//2]:.0f}   Q3: ${max_dds[3*n//4]:.0f}   Q95: ${max_dds[int(0.95*n)]:.0f}   worst: ${max_dds[-1]:.0f}")
    print(f"    Risk of Ruin (30% = ${RUIN_DOLLAR:.0f}): {ruin_count/N_PERMUTATIONS*100:.2f}% ({ruin_count}/{N_PERMUTATIONS})")
    print()


print("=" * 100)
print(f"PDF #4 DIRECTIVE EPSILON — Monte Carlo Risk of Ruin")
print(f"Account: ${STARTING_EQUITY:.0f} | Ruin = {RUIN_THRESHOLD_PCT}% drawdown = ${RUIN_DOLLAR:.0f}")
print(f"Simulations: {N_PERMUTATIONS} permutations × {TRADES_PER_PERM} trades each")
print("=" * 100)
print()

print("--- A) CURRENT LIVE (0.7 lots) under REALISTIC execution ---")
run_mc("LIVE 0.7 lots realistic", p_win=0.40, avg_w=26.6, avg_l=-62.1)

print("--- B) RECOMMENDED (0.2 lots) under REALISTIC execution ---")
run_mc("0.2 lots, trail 12/4 (PDF-validated)", p_win=0.667, avg_w=15.80, avg_l=-10.40)

print("--- C) ALTERNATE (0.2 lots, trail 18/6) ---")
run_mc("0.2 lots, trail 18/6", p_win=0.688, avg_w=16.80, avg_l=-9.80)

print("--- D) Conservative 0.1 lots ---")
run_mc("0.1 lots, trail 12/4", p_win=0.571, avg_w=11.0, avg_l=-4.30)

print("--- E) BACKTEST FANTASY (0.7 lots zero-latency, what we used to claim) ---")
run_mc("BACKTEST 0.7 lots, no latency (FANTASY)", p_win=0.962, avg_w=27.0, avg_l=-19.80)

print("=" * 100)
print("VERDICT")
print("=" * 100)
print("""
Per PDF: 'Risk of Ruin > 2-5% means system over-leveraged or relies on asymmetric negative risk profile.'

Required action: Drop lots from 0.7 → 0.2 immediately. Backtest fantasy showed 0% RoR but realistic
modeling reveals current 0.7-lot config has high RoR risk vs. resilient 0.2-lot config near 0% RoR.
""")
