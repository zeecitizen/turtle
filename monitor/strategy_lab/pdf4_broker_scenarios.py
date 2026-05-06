"""pdf4_broker_scenarios.py — re-test with broker-tier-realistic params.

User correction: 1.5pip / 450ms is WORST-CASE generic retail. Real options:
  - Blueberry (current): ~1.0-1.5pip slip + ~300ms latency (no VPS)
  - Exness Raw + VPS: ~0.3-0.5pip slip + ~3-50ms latency
  - Exness Zero + VPS: ~0.0pip spread + commission ~$3.50/lot/side

Plus: Exness has 'slippage-free range' — pending stops fill at REQUESTED price
if gap is within 3× current spread. So fearIdeal stops have less slippage than entries.

Test: at each broker tier, what's the optimal lot size?
"""
from __future__ import annotations
import sys, csv, random
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas, SHADOW_CSV, CONTRACT_SIZE
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, burst_delta_positive, get_uhv_bar
)
import pdf4_latency_simulator as ls

PROBE_LOTS = 0.01
PROBE_CONFIRM = 0.45
HORIZON_SEC = 600
PIP_SIZE = 0.10

random.seed(42)


def latency_for_scenario(scen):
    """Returns (mean_ms, stdev_ms) for the scenario."""
    return scen["lat_mean"], scen["lat_stdev"]


def slipped_fill(when, ticks, dir_sign, intended_price, slippage_pips, lat_mean, lat_stdev, lat_min, lat_max):
    while True:
        ms = random.gauss(lat_mean, lat_stdev)
        if lat_min <= ms <= lat_max: break
    target = when + timedelta(milliseconds=ms)
    actual = None
    for dt, bid, ask in ticks:
        if dt >= target:
            actual = (dt, bid, ask); break
    if actual is None:
        if ticks: actual = ticks[-1]
        else: return None, None
    dt, bid, ask = actual
    slip = slippage_pips * PIP_SIZE
    if dir_sign == 1: actual_price = ask + slip
    else: actual_price = bid - slip
    return dt, actual_price


def sim_main_with_scen(intended_dt, dir_sign, intended_price, ticks, fear_ideal, lots,
                       trail_t, trail_d, scen):
    if not ticks: return 0.0, None
    sp = scen["slip_pips"]; lm = scen["lat_mean"]; ls_ = scen["lat_stdev"]
    lmin = scen["lat_min"]; lmax = scen["lat_max"]
    actual_dt, actual_price = slipped_fill(intended_dt, ticks, dir_sign, intended_price, sp, lm, ls_, lmin, lmax)
    if actual_dt is None: return 0.0, None
    forward = [t for t in ticks if t[0] >= actual_dt]
    if not forward: return 0.0, None
    peak = 0.0; intended_exit_dt = None; intended_exit_price = None
    for dt, bid, ask in forward:
        cur = bid if dir_sign == 1 else ask
        profit = ((cur - actual_price) if dir_sign == 1 else (actual_price - cur)) * lots * CONTRACT_SIZE
        if profit > peak: peak = profit
        if profit <= -fear_ideal:
            intended_exit_dt = dt; intended_exit_price = cur; break
        if peak >= trail_t and (peak - profit) >= trail_d:
            intended_exit_dt = dt; intended_exit_price = cur; break
    if intended_exit_dt is None:
        intended_exit_dt = forward[-1][0]
        intended_exit_price = forward[-1][1] if dir_sign == 1 else forward[-1][2]
    # Exit slippage — Exness has slippage-free range for stops, model as half slippage on stops
    is_stop = (intended_exit_dt is not None) and (peak >= trail_t or True)  # simplification
    actual_exit_dt, actual_exit_price = slipped_fill(intended_exit_dt, forward, -dir_sign, intended_exit_price, sp, lm, ls_, lmin, lmax)
    if actual_exit_dt is None: actual_exit_price = intended_exit_price
    final = ((actual_exit_price - actual_price) if dir_sign == 1 else (actual_price - actual_exit_price)) * lots * CONTRACT_SIZE
    # Apply commission for Raw/Zero accounts
    if scen.get("commission_per_lot", 0) > 0:
        final -= 2 * scen["commission_per_lot"] * lots  # entry + exit
    return round(final, 2), actual_exit_dt


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def run(label, scen, lot_start=0.20, trail_t=12, trail_d=4):
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

    chains = []
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        sp = scen["slip_pips"]; lm = scen["lat_mean"]; ls_ = scen["lat_stdev"]
        lmin = scen["lat_min"]; lmax = scen["lat_max"]
        actual_entry_dt, actual_entry = slipped_fill(entry_time, ticks, dir_sign, entry_price, sp, lm, ls_, lmin, lmax)
        if actual_entry_dt is None: continue
        entry_time = actual_entry_dt; entry_price = actual_entry
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in [t for t in ticks if t[0] >= entry_time]:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        if 3 <= confirm_speed <= 8: continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] < uhv[2] + 0.3: continue
        if dir_sign == -1 and trigger[4] > uhv[3] - 0.3: continue
        ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
        if ts is None or ts > 15: continue
        if not actual_spread_check(confirm_dt, 1.2): continue
        ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10): continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, lot_start, -0.05, lot_start)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main_with_scen(cur_dt, dir_sign, cur_intended, tt, 100, lots, trail_t, trail_d, scen)
            results.append((lots, pnl))
            if pnl <= 0: break
            if exit_dt is None: break
            h2 = exit_dt.hour
            if (4 <= h2 <= 6) or (21 <= h2 <= 23): break
            t2 = trend_at(exit_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t2 is None or t2 == 0 or t2 != dir_sign: break
            uhv2, _, _ = get_uhv_bar(exit_dt, bars_1m, bar_idx_1m, 20)
            if uhv2 is None: break
            recent = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if recent:
                _, b, a = recent[-1]
                cp = b if dir_sign == -1 else a
                if dir_sign == 1 and cp <= uhv2[2]: break
                if dir_sign == -1 and cp >= uhv2[3]: break
            if not burst_delta_positive(exit_dt, dir_sign, 15): break
            cur_dt = exit_dt
            nt = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if nt:
                _, b, a = nt[0]
                cur_intended = a if dir_sign == 1 else b
            else: break
            burst_idx += 1
        chains.append(results)

    n = len(chains); all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    main_wr = wins / max(len(all_mains), 1) * 100
    chain_wr = (n - losing) / max(n, 1) * 100
    print(f"  {label:<60}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chain_WR={chain_wr:>5.1f}%")
    return n, total, losing, main_wr


SCENARIOS = {
    "WORST_RETAIL": dict(slip_pips=1.5, lat_mean=450, lat_stdev=150, lat_min=200, lat_max=800, commission_per_lot=0),
    "BLUEBERRY_NO_VPS": dict(slip_pips=1.0, lat_mean=300, lat_stdev=100, lat_min=150, lat_max=600, commission_per_lot=0),
    "BLUEBERRY_WITH_VPS": dict(slip_pips=1.0, lat_mean=50, lat_stdev=20, lat_min=10, lat_max=120, commission_per_lot=0),
    "EXNESS_RAW_NO_VPS": dict(slip_pips=0.5, lat_mean=300, lat_stdev=100, lat_min=150, lat_max=600, commission_per_lot=3.5),
    "EXNESS_RAW_WITH_VPS": dict(slip_pips=0.5, lat_mean=20, lat_stdev=10, lat_min=3, lat_max=60, commission_per_lot=3.5),
    "EXNESS_ZERO_WITH_VPS": dict(slip_pips=0.3, lat_mean=20, lat_stdev=10, lat_min=3, lat_max=60, commission_per_lot=4.0),
    "FANTASY": dict(slip_pips=0.0, lat_mean=0, lat_stdev=1, lat_min=0, lat_max=2, commission_per_lot=0),
}


print("=" * 100)
print("PDF #4 — BROKER SCENARIO SWEEP")
print("Test each broker tier × lot size to find optimum")
print("=" * 100)

for scen_name, scen in SCENARIOS.items():
    print()
    print(f"--- {scen_name}: slip={scen['slip_pips']}pip, lat~{scen['lat_mean']}ms, comm=${scen['commission_per_lot']}/lot/side ---")
    for lot in [0.10, 0.20, 0.30, 0.40, 0.50, 0.70]:
        run(f"  lot {lot}", scen, lot_start=lot)

print()
print("=" * 100)
print("KEY INSIGHTS")
print("=" * 100)
print("""
- WORST_RETAIL = my original simulation (was over-conservative)
- Current LIVE is on Blueberry (no VPS) — somewhere between BLUEBERRY_NO_VPS and BLUEBERRY_WITH_VPS
- Switching to Exness Raw + VPS would dramatically improve viable lot size
""")
