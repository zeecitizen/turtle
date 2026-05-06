"""pdf4_loo_realistic.py — leave-one-out under CURRENT live config.

Same approach as filter_loo_correct.py, but using:
  - 0.3 lots
  - trail 25/8
  - burst-delta 5s
  - Direct Raw execution scenario (0.5pip slip + 300ms latency)

For each filter, turn it OFF and measure: how many MORE chains fire, what happens to WR/total/losing.
Goal: find filters cutting trades without contributing to WR.
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


def run(label, *, skip_bad_hours=True, skip_fast_confirm=True, trend_filter=True,
        uhv_filter=True, trigger_past_pts=0.3, tick_speed_max=15, spread_mult=1.2,
        m15_trend=True, setup1_filter=True, burst_delta_filter=True, burst_delta_lb=5,
        trail_t=25, trail_d=8, fear_ideal=100, lot_start=0.30):
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

    chains = []
    blocked_by = {}
    def block(name): blocked_by[name] = blocked_by.get(name, 0) + 1

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
            if (4 <= h <= 6) or (21 <= h <= 23): block('bad_hours'); continue
        if skip_fast_confirm:
            if 3 <= confirm_speed <= 8: block('fast_confirm'); continue
        if trend_filter:
            t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t is None or t == 0 or t != dir_sign: block('trend_2m'); continue

        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: block('no_uhv_data'); continue
        trigger = bars_1m[trigger_idx]
        if uhv_filter:
            margin = trigger_past_pts
            if dir_sign == 1 and trigger[4] < uhv[2] + margin: block('uhv_filter'); continue
            if dir_sign == -1 and trigger[4] > uhv[3] - margin: block('uhv_filter'); continue
        if tick_speed_max > 0:
            ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
            if ts is None or ts > tick_speed_max: block('tick_speed'); continue
        if spread_mult > 0:
            if not actual_spread_check(confirm_dt, spread_mult): block('spread'); continue
        if m15_trend:
            ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
            if ema_v is not None:
                price = (confirm_bid + confirm_ask) / 2
                if dir_sign == 1 and price <= ema_v: block('m15_trend'); continue
                if dir_sign == -1 and price >= ema_v: block('m15_trend'); continue
        if setup1_filter:
            if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10):
                block('setup1'); continue

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
    print(f"  {label:<55}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chainWR={chain_wr:>5.1f}%")
    return n, total, losing, main_wr, blocked_by


print("=" * 100)
print("PDF #4 LOO under CURRENT LIVE realistic config")
print("(0.3 lots, trail 25/8, bd_lb=5s, Direct Raw execution)")
print("=" * 100)
print()
print("--- BASELINE (current LIVE) ---")
n_base, t_base, l_base, wr_base, blocks = run("LIVE: full stack")
print()
print("Per-filter block count:")
for k, v in sorted(blocks.items(), key=lambda x: -x[1]):
    print(f"  {k:<20} blocked {v:>3} probes")

print()
print("=" * 100)
print("LEAVE-ONE-OUT (turn off ONE filter at a time)")
print("=" * 100)

variants = [
    ("WITHOUT bad_hours", dict(skip_bad_hours=False)),
    ("WITHOUT fast_confirm", dict(skip_fast_confirm=False)),
    ("WITHOUT trend_2m", dict(trend_filter=False)),
    ("WITHOUT uhv_filter+margin", dict(uhv_filter=False)),
    ("WITHOUT trigger margin (keep uhv basic)", dict(trigger_past_pts=0.0)),
    ("WITHOUT tick_speed", dict(tick_speed_max=0)),
    ("WITHOUT spread filter", dict(spread_mult=0)),
    ("WITHOUT m15_trend", dict(m15_trend=False)),
    ("WITHOUT setup1", dict(setup1_filter=False)),
    ("WITHOUT burst_delta", dict(burst_delta_filter=False)),
]
for label, kwargs in variants:
    n, t, l, wr, _ = run(label, **kwargs)
    dn = n - n_base; dt = t - t_base; dl = l - l_base; dwr = wr - wr_base
    print(f"      Δ chains={dn:+d}  Δ total=${dt:+.2f}  Δ losing={dl:+d}  Δ WR={dwr:+.1f}%")
