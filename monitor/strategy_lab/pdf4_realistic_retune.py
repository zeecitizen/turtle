"""pdf4_realistic_retune.py — re-sweep every filter threshold under realistic execution.

Same logic as before, but each parameter is re-optimized against latency+slippage
instead of zero-friction. Goal: recover the 95%+ WR we had in fantasy backtest.

Sweeps:
  1. tick-speed threshold
  2. spread max multiplier
  3. trigger margin past UHV
  4. burst-delta lookback
  5. Setup 1 lookback bars
  6. trail trigger/drop combos
  7. fearIdeal
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
import pdf4_latency_simulator as ls

random.seed(42)

PROBE_LOTS = 0.01
PROBE_CONFIRM = 0.45
HORIZON_SEC = 600
PIP_SIZE = 0.10

# Direct Raw scenario (user's current account)
SLIP_PIPS = 0.5
LAT_MEAN = 300
LAT_STDEV = 100
LAT_MIN = 150
LAT_MAX = 600
COMMISSION_PER_LOT = 3.5  # $7/round-lot, applied as 2× this per fill


def slipped_fill(when, ticks, dir_sign, intended_price):
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
    slip = SLIP_PIPS * PIP_SIZE
    if dir_sign == 1: return dt, ask + slip
    return dt, bid - slip


def burst_delta_positive_custom(when, dir_sign, lookback_sec):
    end = when
    start = end - timedelta(seconds=lookback_sec)
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
        if profit <= -fear_ideal:
            intended_exit_dt = dt; intended_exit_price = cur; break
        if peak >= trail_t and (peak - profit) >= trail_d:
            intended_exit_dt = dt; intended_exit_price = cur; break
    if intended_exit_dt is None:
        intended_exit_dt = forward[-1][0]
        intended_exit_price = forward[-1][1] if dir_sign == 1 else forward[-1][2]
    actual_exit_dt, actual_exit_price = slipped_fill(intended_exit_dt, forward, -dir_sign, intended_exit_price)
    if actual_exit_dt is None: actual_exit_price = intended_exit_price
    final = ((actual_exit_price - actual_price) if dir_sign == 1 else (actual_price - actual_exit_price)) * lots * CONTRACT_SIZE
    final -= 2 * COMMISSION_PER_LOT * lots
    return round(final, 2), actual_exit_dt


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def run(label, *,
        # All defaults match current LIVE
        tick_speed_max=15,
        spread_mult=1.2,
        trigger_past_pts=0.3,
        burst_delta_lb=15,
        setup1_lb=3,
        trail_t=12, trail_d=4,
        fear_ideal=100,
        lot_start=0.30):

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
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        if 3 <= confirm_speed <= 8: continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if trigger_past_pts > 0:
            if dir_sign == 1 and trigger[4] < uhv[2] + trigger_past_pts: continue
            if dir_sign == -1 and trigger[4] > uhv[3] - trigger_past_pts: continue
        if tick_speed_max > 0:
            ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
            if ts is None or ts > tick_speed_max: continue
        if spread_mult > 0:
            if not actual_spread_check(confirm_dt, spread_mult): continue
        ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, setup1_lb, 10): continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, lot_start, -0.07, lot_start)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, fear_ideal, lots, trail_t, trail_d)
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
            if not burst_delta_positive_custom(exit_dt, dir_sign, burst_delta_lb): break
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
    print(f"  {label:<55}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chainWR={chain_wr:>5.1f}%")
    return n, total, losing, main_wr, chain_wr


print("=" * 100)
print("REALISTIC RE-TUNE — re-sweep every filter under Direct Raw + 0.3 lots execution")
print("=" * 100)

print()
print("--- BASELINE (current LIVE) ---")
run("LIVE: tick=15, spr=1.2, trig=0.3, bd=15, s1=3, trail=12/4")

print()
print("=== 1) TICK-SPEED SWEEP ===")
for ts in [5, 8, 10, 12, 15, 18, 20, 25, 30, 0]:
    run(f"tick_speed={ts}s" + (" (OFF)" if ts == 0 else ""), tick_speed_max=ts)

print()
print("=== 2) SPREAD MULTIPLIER SWEEP ===")
for sp in [1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.5, 1.8, 0]:
    run(f"spread<={sp}x" + (" (OFF)" if sp == 0 else ""), spread_mult=sp)

print()
print("=== 3) TRIGGER MARGIN SWEEP ===")
for tp in [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5]:
    run(f"trigger_past={tp}pt", trigger_past_pts=tp)

print()
print("=== 4) BURST-DELTA LOOKBACK SWEEP ===")
for bd in [5, 10, 15, 20, 30, 45, 60]:
    run(f"burst_delta_lb={bd}s", burst_delta_lb=bd)

print()
print("=== 5) SETUP 1 LOOKBACK BARS ===")
for s1 in [1, 2, 3, 5, 7, 10]:
    run(f"setup1_lb={s1} bars", setup1_lb=s1)

print()
print("=== 6) TRAIL TRIGGER/DROP COMBOS ===")
for tt, td in [(8, 3), (10, 4), (12, 4), (15, 5), (15, 6), (18, 6), (20, 7), (20, 8), (25, 8), (25, 10), (30, 10)]:
    run(f"trail {tt}/{td}", trail_t=tt, trail_d=td)

print()
print("=== 7) FEAR-IDEAL SWEEP ===")
for fi in [40, 60, 80, 100, 120, 150, 200]:
    run(f"fearIdeal=${fi}", fear_ideal=fi)
