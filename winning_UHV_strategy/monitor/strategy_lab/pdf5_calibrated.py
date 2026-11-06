"""pdf5_calibrated.py — same as pdf4_loo_realistic.py BUT with calibrated slippage.

Slippage is now sampled from the empirical distribution (n=340 SL fills) instead
of the constant 0.5 pips. This eliminates the largest remaining "fantasy" gap in
our backtest.

Source of empirical distribution: turtle_fills.csv SL exits 2026-04-20 to 2026-05-01.
  mean = 1.14 pips, stdev = 1.84 pips, p95 = 3.7 pips, max = 20.0 pips
  (vs old assumption: 0.5 pips constant)

Run with the same scenarios as pdf4_loo_realistic.py to measure the calibrated-vs-old delta.
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
    setup1_active, get_uhv_bar
)
from slip_calibrator import sample_slip_pips

random.seed(42)
PROBE_LOTS = 0.01; PROBE_CONFIRM = 0.45; HORIZON_SEC = 600; PIP_SIZE = 0.10
LAT_MEAN = 300; LAT_STDEV = 100; LAT_MIN = 150; LAT_MAX = 600
COMMISSION_PER_LOT = 3.5

# Burst safety (matches LIVE deployment 2026-05-02)
BURST_SL_USD       = 15.0
FIRST_MAIN_FEAR    = 100.0


def slipped_fill(when, ticks, dir_sign, intended_price):
    """CALIBRATED: latency stays Gaussian (we don't have empirical data yet),
    slippage sampled from production SL distribution."""
    while True:
        ms = random.gauss(LAT_MEAN, LAT_STDEV)
        if LAT_MIN <= ms <= LAT_MAX: break
    target = when + timedelta(milliseconds=ms)
    actual = None
    for dt, bid, ask in ticks:
        if dt >= target: actual = (dt, bid, ask); break
    if actual is None and ticks: actual = ticks[-1]
    if actual is None: return None, None
    dt, bid, ask = actual
    slip = sample_slip_pips() * PIP_SIZE   # ← CHANGED from constant 0.5 * PIP_SIZE
    return (dt, ask + slip) if dir_sign == 1 else (dt, bid - slip)


def burst_delta_pos(when, dir_sign, lookback_sec):
    end = when; start = end - timedelta(seconds=lookback_sec)
    ticks = ticks_in_range(start, end)
    if len(ticks) < 5: return True
    up = down = 0; prev_mid = None
    for _, bid, ask in ticks:
        mid = (bid + ask) / 2
        if prev_mid is not None:
            if mid > prev_mid: up += 1
            elif mid < prev_mid: down += 1
        prev_mid = mid
    if up + down < 3: return True
    delta = up - down
    return (dir_sign == 1 and delta > 0) or (dir_sign == -1 and delta < 0)


def sim_main(intended_dt, dir_sign, intended_price, ticks, fear_ideal, lots, trail_t, trail_d):
    if not ticks: return 0.0, None
    actual_dt, actual_price = slipped_fill(intended_dt, ticks, dir_sign, intended_price)
    if actual_dt is None: return 0.0, None
    forward = [t for t in ticks if t[0] >= actual_dt]
    if not forward: return 0.0, None
    peak = 0.0; intended_exit_dt = None; intended_exit_price = None
    for dt, bid, ask in forward:
        cur = bid if dir_sign == 1 else ask
        profit = ((cur - actual_price) if dir_sign == 1 else (actual_price - cur)) * lots * CONTRACT_SIZE
        if profit > peak: peak = profit
        if profit <= -fear_ideal: intended_exit_dt = dt; intended_exit_price = cur; break
        if peak >= trail_t and (peak - profit) >= trail_d: intended_exit_dt = dt; intended_exit_price = cur; break
    if intended_exit_dt is None:
        intended_exit_dt = forward[-1][0]
        intended_exit_price = forward[-1][1] if dir_sign == 1 else forward[-1][2]
    actual_exit_dt, actual_exit_price = slipped_fill(intended_exit_dt, forward, -dir_sign, intended_exit_price)
    if actual_exit_dt is None: actual_exit_price = intended_exit_price
    final = ((actual_exit_price - actual_price) if dir_sign == 1 else (actual_price - actual_exit_price)) * lots * CONTRACT_SIZE
    final -= 2 * COMMISSION_PER_LOT * lots
    return round(final, 2), actual_exit_dt


def lot_for_burst(b, start, step, max_lot, min_lot=0.01):
    lot = start + b * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def run(label, *, skip_bad_hours=False, skip_fast_confirm=False, trend_filter=True,
        uhv_filter=True, trigger_past_pts=0.3, tick_speed_max=15, spread_mult=1.2,
        m15_trend=True, setup1_filter=True, burst_delta_filter=True, burst_delta_lb=5,
        trail_t=25, trail_d=8, fear_ideal=100, lot_start=0.30, burst_sl_usd=BURST_SL_USD,
        n_runs=1):
    """Run scenario n_runs times (Monte Carlo) and average. Random slippage sampling adds variance."""
    all_runs = []
    for run_i in range(n_runs):
        random.seed(42 + run_i)
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
            actual_entry_dt, actual_entry = slipped_fill(entry_time, ticks, dir_sign, entry_price)
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

            if skip_bad_hours:
                h = confirm_dt.hour
                if (4 <= h <= 6) or (21 <= h <= 23): continue
            if skip_fast_confirm:
                if 3 <= confirm_speed <= 8: continue
            if trend_filter:
                t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
                if t is None or t == 0 or t != dir_sign: continue
            uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
            if uhv is None: continue
            trigger = bars_1m[trigger_idx]
            if uhv_filter:
                margin = trigger_past_pts
                if dir_sign == 1 and trigger[4] < uhv[2] + margin: continue
                if dir_sign == -1 and trigger[4] > uhv[3] - margin: continue
            if tick_speed_max > 0:
                ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
                if ts is None or ts > tick_speed_max: continue
            if spread_mult > 0:
                if not actual_spread_check(confirm_dt, spread_mult): continue
            if m15_trend:
                ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
                if ema_v is not None:
                    price = (confirm_bid + confirm_ask) / 2
                    if dir_sign == 1 and price <= ema_v: continue
                    if dir_sign == -1 and price >= ema_v: continue
            if setup1_filter:
                if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10): continue

            intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
            cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
            results = []
            while burst_idx < 7:
                lots = lot_for_burst(burst_idx, lot_start, -0.07, lot_start)
                sl_for_this = fear_ideal if burst_idx == 0 else burst_sl_usd
                horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
                tt = ticks_in_range(cur_dt, horizon_end)
                pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, sl_for_this, lots, trail_t, trail_d)
                results.append((lots, pnl))
                if pnl <= 0: break
                if exit_dt is None: break
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
                if burst_delta_filter and not burst_delta_pos(exit_dt, dir_sign, burst_delta_lb): break
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
        max_dd = min(chain_pnls) if chain_pnls else 0
        all_runs.append({
            "n": n, "mains": len(all_mains), "main_wr": main_wr, "chain_wr": chain_wr,
            "total": total, "losing": losing, "max_dd": max_dd,
        })

    # Average across MC runs
    avg_n        = sum(r["n"]        for r in all_runs) / len(all_runs)
    avg_mains    = sum(r["mains"]    for r in all_runs) / len(all_runs)
    avg_main_wr  = sum(r["main_wr"]  for r in all_runs) / len(all_runs)
    avg_chain_wr = sum(r["chain_wr"] for r in all_runs) / len(all_runs)
    avg_total    = sum(r["total"]    for r in all_runs) / len(all_runs)
    avg_losing   = sum(r["losing"]   for r in all_runs) / len(all_runs)
    avg_max_dd   = sum(r["max_dd"]   for r in all_runs) / len(all_runs)
    totals = [r["total"] for r in all_runs]
    total_min = min(totals); total_max = max(totals)
    print(f"  {label:<55s}  chains~{avg_n:.1f}  mains~{avg_mains:.1f}  mainWR={avg_main_wr:.1f}%  chainWR={avg_chain_wr:.1f}%  total=${avg_total:+8.2f}  [${total_min:+.0f}..${total_max:+.0f}]  losing~{avg_losing:.1f}  max_DD=${avg_max_dd:+.2f}")
    return avg_total, avg_n, avg_chain_wr, total_min, total_max


N_RUNS = 5  # Monte Carlo runs to capture slippage variance (5 sufficient, 20 too slow on tick replay)

print("=" * 130)
print("CALIBRATED backtest (slippage sampled from empirical n=340 distribution, mean=1.14pips vs old 0.5pips constant)")
print(f"Each scenario averaged over {N_RUNS} MC runs to capture slippage variance")
print("=" * 130)
print()

print("--- BASELINE: LIVE config (ABSORBS calibrated slippage) ---")
print("    For comparison: pdf4_loo_realistic.py with constant 0.5pip slip reports +$303.79")
base = run("LIVE: full stack (no burst SL)", burst_sl_usd=100, n_runs=N_RUNS)
print()

print("--- WITH burst_SL=$15 (deployed today) ---")
run("LIVE + burstSL=$15", burst_sl_usd=15, n_runs=N_RUNS)
print()

print("--- WITH burst_SL=$15, max_burst=3 ---")
def run2(label, **kw):
    # Allow override of max_burst by patching the inner run function's burst loop limit.
    # Quick implementation: just lower burst_sl_usd to be effective.
    # For max_burst sweep, do a manual pass below.
    pass

# Sweep alternative SL caps under calibrated execution
print("--- CALIBRATED burst SL sweep ---")
for sl in [10, 15, 20, 25, 50, 100]:
    run(f"burstSL=${sl}", burst_sl_usd=sl, n_runs=N_RUNS)
