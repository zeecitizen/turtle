"""pdf5_quick_compare.py — fast headline calibrated-vs-old comparison.

Runs the LIVE config in two modes:
  1. OLD slippage:  constant 0.5 pips
  2. CALIBRATED:    sampled from empirical n=340 distribution

Just two scenarios (LIVE baseline + LIVE+burstSL=$15), 5 MC runs each.
Goal: get the headline number quickly so the deep dive doc can cite a real value.
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

PROBE_LOTS = 0.01; PROBE_CONFIRM = 0.45; HORIZON_SEC = 600; PIP_SIZE = 0.10
LAT_MEAN = 300; LAT_STDEV = 100; LAT_MIN = 150; LAT_MAX = 600
COMMISSION_PER_LOT = 3.5
N_RUNS = 5

# Pre-cache the heavy reads ONCE before MC loops
print("Loading SHADOW + tick caches once...")
ROWS = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
ROWS.sort(key=lambda r: r.get("entry_time", ""))
BARS_1M = build_1m_bars()
BAR_IDX_1M = {b[0]: i for i, b in enumerate(BARS_1M)}
EMA_F, EMA_S, BAR_IDX_2M, _ = get_emas(34, 89, 2)
EMA_M15_F, _, BAR_IDX_15M, _ = get_emas(21, 21, 15)
print(f"  {len(ROWS)} probe rows, {len(BARS_1M)} M1 bars cached")
print()


def slipped_fill_old(when, ticks, dir_sign, intended_price):
    """OLD: constant 0.5 pip slip."""
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
    slip = 0.5 * PIP_SIZE
    return (dt, ask + slip) if dir_sign == 1 else (dt, bid - slip)


def slipped_fill_calibrated(when, ticks, dir_sign, intended_price):
    """CALIBRATED: sampled from empirical distribution."""
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
    slip = sample_slip_pips() * PIP_SIZE
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


def sim_main(intended_dt, dir_sign, intended_price, ticks, fear_ideal, lots, trail_t, trail_d, fill_fn):
    if not ticks: return 0.0, None
    actual_dt, actual_price = fill_fn(intended_dt, ticks, dir_sign, intended_price)
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
    actual_exit_dt, actual_exit_price = fill_fn(intended_exit_dt, forward, -dir_sign, intended_exit_price)
    if actual_exit_dt is None: actual_exit_price = intended_exit_price
    final = ((actual_exit_price - actual_price) if dir_sign == 1 else (actual_price - actual_exit_price)) * lots * CONTRACT_SIZE
    final -= 2 * COMMISSION_PER_LOT * lots
    return round(final, 2), actual_exit_dt


def lot_for_burst(b, start, step, max_lot, min_lot=0.01):
    lot = start + b * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def run_once(burst_sl_usd, fill_fn):
    chains = []
    for r in ROWS:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        actual_entry_dt, actual_entry = fill_fn(entry_time, ticks, dir_sign, entry_price)
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

        t = trend_at(confirm_dt, EMA_F, EMA_S, BAR_IDX_2M, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, BARS_1M, BAR_IDX_1M, 20)
        if uhv is None: continue
        trigger = BARS_1M[trigger_idx]
        if dir_sign == 1 and trigger[4] < uhv[2] + 0.3: continue
        if dir_sign == -1 and trigger[4] > uhv[3] - 0.3: continue
        ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
        if ts is None or ts > 15: continue
        if not actual_spread_check(confirm_dt, 1.2): continue
        ema_v = m15_trend_at(confirm_dt, EMA_M15_F, BAR_IDX_15M)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, BARS_1M, BAR_IDX_1M, 3, 10): continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, 0.30, -0.07, 0.30)
            sl_for_this = 100 if burst_idx == 0 else burst_sl_usd
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, sl_for_this, lots, 25, 8, fill_fn)
            results.append((lots, pnl))
            if pnl <= 0: break
            if exit_dt is None: break
            t2 = trend_at(exit_dt, EMA_F, EMA_S, BAR_IDX_2M, 2)
            if t2 is None or t2 == 0 or t2 != dir_sign: break
            uhv2, _, _ = get_uhv_bar(exit_dt, BARS_1M, BAR_IDX_1M, 20)
            if uhv2 is None: break
            recent = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if recent:
                _, b, a = recent[-1]
                cp = b if dir_sign == -1 else a
                if dir_sign == 1 and cp <= uhv2[2]: break
                if dir_sign == -1 and cp >= uhv2[3]: break
            if not burst_delta_pos(exit_dt, dir_sign, 5): break
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
    return n, len(all_mains), main_wr, chain_wr, total, losing, max_dd


def avg_runs(label, fill_fn, burst_sl_usd):
    runs = []
    for i in range(N_RUNS):
        random.seed(42 + i)
        runs.append(run_once(burst_sl_usd, fill_fn))
    n        = sum(r[0] for r in runs) / N_RUNS
    mains    = sum(r[1] for r in runs) / N_RUNS
    main_wr  = sum(r[2] for r in runs) / N_RUNS
    chain_wr = sum(r[3] for r in runs) / N_RUNS
    total_avg = sum(r[4] for r in runs) / N_RUNS
    total_min = min(r[4] for r in runs)
    total_max = max(r[4] for r in runs)
    losing   = sum(r[5] for r in runs) / N_RUNS
    max_dd   = sum(r[6] for r in runs) / N_RUNS
    print(f"  {label:<48s}  chains~{n:.1f}  mains~{mains:.1f}  mainWR={main_wr:.1f}%  chainWR={chain_wr:.1f}%  total=${total_avg:+8.2f}  [${total_min:+.0f}..${total_max:+.0f}]  losing~{losing:.1f}  maxDD=${max_dd:+.2f}")
    return total_avg


print("=" * 110)
print(f"OLD vs CALIBRATED slippage — same LIVE config, same probes, {N_RUNS} MC runs each")
print("=" * 110)
print()

print("--- OLD (constant 0.5 pip slip) ---")
old_a = avg_runs("LIVE baseline (no burst SL)", slipped_fill_old, 100)
old_b = avg_runs("LIVE + burstSL=$15", slipped_fill_old, 15)
print()

print("--- CALIBRATED (sampled empirical distribution, mean 1.14 pips) ---")
cal_a = avg_runs("LIVE baseline (no burst SL)", slipped_fill_calibrated, 100)
cal_b = avg_runs("LIVE + burstSL=$15", slipped_fill_calibrated, 15)
print()

print("=" * 110)
print(f"DELTA: calibrated total - old total")
print(f"  LIVE baseline (no burst SL): old=${old_a:+.2f}  calibrated=${cal_a:+.2f}  delta=${cal_a-old_a:+.2f}")
print(f"  LIVE + burstSL=$15:           old=${old_b:+.2f}  calibrated=${cal_b:+.2f}  delta=${cal_b-old_b:+.2f}")
print()
print("Note: probe_shadow has 192 probes from 2026-04-29 to 2026-05-01 (3-day window).")
print("Calibrated total is the realistic expectation under current LIVE config + burst safety.")
