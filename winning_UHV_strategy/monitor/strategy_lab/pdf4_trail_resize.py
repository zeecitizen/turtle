"""pdf4_trail_resize.py — find trail params that SURVIVE realistic execution.

If 12/4 trail + 0.7 lots collapses to -$266 under latency+slippage, we need wider
trails so each win is comfortably larger than the $21 round-trip slippage cost.

Test: trail trigger 20/30/40, drop 8/12/16, with latency+slippage ON.
"""
from __future__ import annotations
import sys, csv, random, statistics
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

random.seed(42)


def sim_one_main_with_latency_custom(
        intended_entry_dt, dir_sign, intended_entry_price, ticks, fear_ideal, lots,
        trail_trigger, trail_drop):
    if not ticks: return 0.0, "no_ticks", None
    actual_entry_dt, actual_entry_price, _ = ls.latency_slipped_fill(
        intended_entry_dt, ticks, dir_sign, intended_entry_price)
    if actual_entry_dt is None: return 0.0, "entry_failed", None
    forward_ticks = [t for t in ticks if t[0] >= actual_entry_dt]
    if not forward_ticks: return 0.0, "no_forward", None

    peak = 0.0; last_profit = 0.0
    intended_exit_dt = None; intended_exit_price = None; exit_reason = "horizon_end"
    for dt, bid, ask in forward_ticks:
        if dir_sign == 1:
            cur = bid
            profit = (cur - actual_entry_price) * lots * CONTRACT_SIZE
        else:
            cur = ask
            profit = (actual_entry_price - cur) * lots * CONTRACT_SIZE
        last_profit = profit
        if profit > peak: peak = profit
        if profit <= -fear_ideal:
            intended_exit_dt = dt; intended_exit_price = cur; exit_reason = "fearIdeal"; break
        if peak >= trail_trigger and (peak - profit) >= trail_drop:
            intended_exit_dt = dt; intended_exit_price = cur; exit_reason = "trail"; break
    if intended_exit_dt is None:
        intended_exit_dt = forward_ticks[-1][0]
        intended_exit_price = forward_ticks[-1][1] if dir_sign == 1 else forward_ticks[-1][2]

    exit_dir = -dir_sign
    actual_exit_dt, actual_exit_price, _ = ls.latency_slipped_fill(
        intended_exit_dt, forward_ticks, exit_dir, intended_exit_price)
    if actual_exit_dt is None:
        actual_exit_price = intended_exit_price
    if dir_sign == 1:
        final_pnl = (actual_exit_price - actual_entry_price) * lots * CONTRACT_SIZE
    else:
        final_pnl = (actual_entry_price - actual_exit_price) * lots * CONTRACT_SIZE
    return round(final_pnl, 2), exit_reason, actual_exit_dt


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def sim_chain(confirm_dt, intended_entry, dir_sign, fear_ideal, max_burst,
              ladder_start, ladder_step, ladder_max,
              ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
              trail_trigger, trail_drop, burst_delta=True):
    main_results = []
    cur_dt = confirm_dt
    cur_intended = intended_entry
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_reason, exit_dt = sim_one_main_with_latency_custom(
            cur_dt, dir_sign, cur_intended, ticks, fear_ideal, lots, trail_trigger, trail_drop)
        main_results.append((lots, pnl, exit_reason))
        if pnl <= 0: break
        if exit_dt is None: break
        h = exit_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): break
        t = trend_at(exit_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: break
        uhv, _, _ = get_uhv_bar(exit_dt, bars_1m, bar_idx_1m, 20)
        if uhv is None: break
        recent = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
        if recent:
            _, b, a = recent[-1]
            cur_price = b if dir_sign == -1 else a
            if dir_sign == 1 and cur_price <= uhv[2]: break
            if dir_sign == -1 and cur_price >= uhv[3]: break
        if burst_delta and not burst_delta_positive(exit_dt, dir_sign, 15): break
        cur_dt = exit_dt
        next_ticks = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
        if next_ticks:
            _, b, a = next_ticks[0]
            cur_intended = a if dir_sign == 1 else b
        else:
            break
        burst_idx += 1
    return main_results


def run(label, *, trail_trigger, trail_drop, fear_ideal=100, lot_start=0.70):
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
        # latency on probe entry
        actual_entry_dt, actual_entry, _ = ls.latency_slipped_fill(entry_time, ticks, dir_sign, entry_price)
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
        chain = sim_chain(confirm_dt, intended_entry, dir_sign,
                          fear_ideal=fear_ideal, max_burst=7,
                          ladder_start=lot_start, ladder_step=-0.10, ladder_max=lot_start,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m,
                          trail_trigger=trail_trigger, trail_drop=trail_drop)
        chains.append(chain)

    n = len(chains); all_mains = [(m[0], m[1]) for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    chain_wr = (n - losing) / max(n, 1) * 100
    main_wr = wins / max(len(all_mains), 1) * 100
    avg_win = sum(m[1] for m in all_mains if m[1] > 0) / max(wins, 1)
    avg_loss = sum(m[1] for m in all_mains if m[1] <= 0) / max(len(all_mains) - wins, 1)
    print(f"  {label:<55}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  avgW=${avg_win:+.1f}  avgL=${avg_loss:+.1f}  worst=${big_loss:+.1f}")


print("=" * 100)
print("PDF #4 — Find trail params that SURVIVE realistic execution costs")
print("(Latency 200-800ms + 1.5pip slippage ALWAYS ON for all tests)")
print("=" * 100)

print()
print("--- CURRENT LIVE: trail 12/4 + 0.7 lots ---")
run("LIVE: trail 12/4, lot 0.7", trail_trigger=12, trail_drop=4)

print()
print("--- WIDER TRAIL: trigger 20-40, drop 8-16 (with 0.7 lots) ---")
for tt, td in [(15, 5), (20, 6), (20, 8), (25, 8), (25, 10), (30, 10), (30, 12), (40, 14), (40, 16)]:
    run(f"trail {tt}/{td}, lot 0.7", trail_trigger=tt, trail_drop=td)

print()
print("--- DROP TO SMALLER LOTS (slippage scales linearly with lot) ---")
for lot in [0.20, 0.10]:
    for tt, td in [(12, 4), (20, 8), (30, 10)]:
        run(f"trail {tt}/{td}, lot {lot}", trail_trigger=tt, trail_drop=td, lot_start=lot)

print()
print("--- TIGHTER FEAR-IDEAL (cap loss faster) ---")
for fi in [50, 70, 100]:
    run(f"fearIdeal=${fi}, trail 25/10, lot 0.7", trail_trigger=25, trail_drop=10, fear_ideal=fi)
