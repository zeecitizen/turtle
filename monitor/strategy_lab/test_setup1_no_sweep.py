"""test_setup1_no_sweep.py — test Setup 1 with sweep step removed.

Original turtle tests claimed sweep step 2 cuts too many trades.
Here we test: keep step 1 (UHV catalyst) + step 3 (trigger close past UHV extreme),
skip step 2 (sweep requirement).
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
    find_uhv_red_idx_m1, get_uhv_bar
)

random.seed(42)
PROBE_LOTS = 0.01; PROBE_CONFIRM = 0.45; HORIZON_SEC = 600; PIP_SIZE = 0.10
SLIP_PIPS = 0.5; LAT_MEAN = 300; LAT_STDEV = 100; LAT_MIN = 150; LAT_MAX = 600
COMMISSION_PER_LOT = 3.5


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


def setup1_at_m1_custom(bars_1m, idx, dir_sign, lookback=10, require_sweep=True):
    """Setup 1 detector with optional sweep step."""
    if idx < 3: return False
    uhv_idx = find_uhv_red_idx_m1(bars_1m, idx, lookback, dir_sign)
    if uhv_idx is None: return False
    uhv = bars_1m[uhv_idx]
    if require_sweep:
        swept = False
        for i in range(uhv_idx + 1, idx):
            if dir_sign == 1 and bars_1m[i][3] < uhv[3]: swept = True; break
            if dir_sign == -1 and bars_1m[i][2] > uhv[2]: swept = True; break
        if not swept: return False
    cur = bars_1m[idx]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False
        if cur[4] <= uhv[2]: return False
    else:
        if cur[4] >= cur[1]: return False
        if cur[4] >= uhv[3]: return False
    return True


def setup1_active(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars=3, pattern_lookback=10, require_sweep=True):
    bm = probe_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None: return False
    start = max(pattern_lookback, idx - lookback_bars)
    for i in range(start, idx + 1):
        if setup1_at_m1_custom(bars_1m, i, dir_sign, pattern_lookback, require_sweep):
            return True
    return False


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


def run(label, *, require_sweep=True, lot_start=0.30, trail_t=25, trail_d=8):
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
        # Skip bad_hours and skip_fast_confirm — already disabled in LIVE
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
        # Setup 1 (with or without sweep step)
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10, require_sweep): continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, lot_start, -0.07, lot_start)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, 100, lots, trail_t, trail_d)
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
    avg_w = sum(m[1] for m in all_mains if m[1] > 0) / max(wins, 1)
    avg_l = sum(m[1] for m in all_mains if m[1] <= 0) / max(len(all_mains) - wins, 1) if (len(all_mains) - wins) else 0
    print(f"  {label:<55}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chainWR={chain_wr:>5.1f}%  avgW=${avg_w:+.1f}  avgL=${avg_l:+.1f}")


print("=" * 100)
print("SETUP 1 — sweep step on/off comparison (Direct Raw realistic execution)")
print("=" * 100)
print()
run("Setup 1 WITH sweep (current LIVE)", require_sweep=True)
run("Setup 1 WITHOUT sweep (turtle proposal)", require_sweep=False)
