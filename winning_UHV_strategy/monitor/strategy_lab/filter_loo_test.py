"""filter_loo_test.py — leave-one-out analysis of LIVE filter stack.

For each LIVE filter, turn it OFF and measure:
  - chain count (how many MORE trades qualify without it)
  - WR (does turning off hurt accuracy)
  - total profit
  - losing chains

Goal: find filters that cut a lot of trades but don't add much edge.

LIVE filter stack (in evaluation order):
  1. skipBadHours (04-06 + 21-23)
  2. skipFastConfirm (3-8s confirm)
  3. trendFilter (2-min EMA-34/89)
  4. uhvFilter (trigger close past UHV extreme)
  5. triggerPastUhvPts (>=0.3pt margin) ⭐
  6. tickSpeedMaxSec (<=15s into trigger bar)
  7. spreadMaxMult (<=1.3x baseline)
  8. m15TrendFilter (M15 21-EMA alignment)
  9. setup1Filter (M1 UHV breakout pattern)
  10. chainStopAfterLoss (halt after 2 losing chains) — pre-chain
  11. burstDeltaFilter (positive delta at each burst)
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, get_emas,
)
from advanced_features import compute_atr

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
PROBE_LOTS = 0.01
HORIZON_SEC = 600


def trend_at(when, ema_f, ema_s, bar_idx_2m, tf=2):
    anchor = when.minute - (when.minute % tf)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_2m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf * d)
            idx = bar_idx_2m.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < 89: return None
    f = ema_f[idx]; s = ema_s[idx]; fp = ema_f[idx-1]
    if f is None or s is None or fp is None: return None
    if f > s and f > fp: return 1
    if f < s and f < fp: return -1
    return 0


def m15_trend_at(when, ema_m15, bar_idx_15m):
    anchor = when.minute - (when.minute % 15)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_15m.get(bm)
    if idx is None:
        for d in range(1, 10):
            t = bm - timedelta(minutes=15 * d)
            idx = bar_idx_15m.get(t)
            if idx is not None: break
        if idx is None: return None, None
    if idx < 21: return None, None
    return ema_m15[idx], idx


def get_uhv_bar(when, bars_1m, bar_idx_1m, lookback=20):
    bm = when.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < lookback + 1: return None, None, None
    trigger_idx = idx - 1
    lookback_bars = bars_1m[max(0, trigger_idx - lookback):trigger_idx]
    if not lookback_bars: return None, None, None
    uhv = max(lookback_bars, key=lambda b: b[5])
    uhv_global_idx = bars_1m.index(uhv)
    return uhv, uhv_global_idx, trigger_idx


def find_uhv_red_idx_m1(bars_1m, idx, lookback, dir_sign):
    start = max(0, idx - lookback)
    cands = []
    for i in range(start, idx):
        bar = bars_1m[i]
        is_red = bar[4] < bar[1]; is_green = bar[4] > bar[1]
        if dir_sign == 1 and is_red: cands.append(i)
        elif dir_sign == -1 and is_green: cands.append(i)
    if not cands: return None
    return max(cands, key=lambda i: bars_1m[i][5])


def setup1_at_m1(bars_1m, idx, dir_sign, lookback=10):
    if idx < 3: return False
    uhv_idx = find_uhv_red_idx_m1(bars_1m, idx, lookback, dir_sign)
    if uhv_idx is None: return False
    uhv = bars_1m[uhv_idx]
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


def setup1_active(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars=3, pattern_lookback=10):
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
        if setup1_at_m1(bars_1m, i, dir_sign, pattern_lookback):
            return True
    return False


def find_setup1_uhv_with_trigger(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars=3, pattern_lookback=10):
    bm = probe_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None: return None, None
    start = max(pattern_lookback, idx - lookback_bars)
    for trig in range(idx, start - 1, -1):
        if not setup1_at_m1(bars_1m, trig, dir_sign, pattern_lookback): continue
        uhv_idx = find_uhv_red_idx_m1(bars_1m, trig, pattern_lookback, dir_sign)
        if uhv_idx is None: continue
        return bars_1m[uhv_idx], bars_1m[trig]
    return None, None


def burst_delta_positive(when, dir_sign, lookback_sec=15):
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


def sim_one_main_with_cdd(entry, dir_sign, ticks, fear_ideal, lots,
                           cdd_div_exit=True, cdd_check_sec=10, cdd_window_sec=60, min_profit=5.0):
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    entry_time = ticks[0][0]
    price_hwm = entry; cumdelta_hwm = 0
    last_check = entry_time
    window = []; prev_mid = None
    for dt, bid, ask in ticks:
        mid = (bid + ask) / 2
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else: profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        sgn = 0
        if prev_mid is not None:
            if mid > prev_mid: sgn = 1
            elif mid < prev_mid: sgn = -1
        prev_mid = mid
        window.append((dt, mid, sgn))
        cutoff = dt - timedelta(seconds=cdd_window_sec)
        while window and window[0][0] < cutoff: window.pop(0)
        if cdd_div_exit and profit >= min_profit and (dt - last_check).total_seconds() >= cdd_check_sec:
            last_check = dt
            cumdelta = sum(w[2] for w in window)
            cumdelta_dir = cumdelta if dir_sign == 1 else -cumdelta
            new_price_hwm = (dir_sign == 1 and cur > price_hwm) or (dir_sign == -1 and cur < price_hwm)
            if new_price_hwm:
                if cumdelta_dir < cumdelta_hwm:
                    return round(profit, 2), dt, cur
                price_hwm = cur; cumdelta_hwm = cumdelta_dir
            elif cumdelta_dir > cumdelta_hwm:
                cumdelta_hwm = cumdelta_dir
        if profit <= -fear_ideal: return round(profit, 2), dt, cur
        if peak >= TRAIL_TRIGGER and (peak - profit) >= TRAIL_DROP:
            return round(profit, 2), dt, cur
    return round(last, 2), last_dt, last_price


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
                         skip_bad_hours=True, trend_filter=True, uhv_filter=True, burst_delta=True):
    if skip_bad_hours:
        h = when.hour
        if (4 <= h <= 6) or (21 <= h <= 23): return False
    if trend_filter:
        t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: return False
    if uhv_filter:
        uhv, _, _ = get_uhv_bar(when, bars_1m, bar_idx_1m, 20)
        if uhv is None: return False
        if dir_sign == 1 and price <= uhv[2]: return False
        if dir_sign == -1 and price >= uhv[3]: return False
    if burst_delta:
        if not burst_delta_positive(when, dir_sign, 15): return False
    return True


def sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
               fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
               ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
               horizon_sec=HORIZON_SEC,
               cdd_div_exit=True,
               burst_skip_bad_hours=True, burst_trend=True, burst_uhv=True, burst_delta=True):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price = sim_one_main_with_cdd(
            main_entry, dir_sign, ticks, fear_ideal, lots, cdd_div_exit=cdd_div_exit)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price, ema_f, ema_s, bar_idx_2m,
                                    bars_1m, bar_idx_1m,
                                    skip_bad_hours=burst_skip_bad_hours, trend_filter=burst_trend,
                                    uhv_filter=burst_uhv, burst_delta=burst_delta): break
        cur_dt = exit_dt; main_entry = exit_price; burst_idx += 1
    return main_results


def run(label, *,
        # All filters default to LIVE config (ON), set False to disable individual ones
        skip_bad_hours=True,
        skip_fast_confirm=True,
        trend_filter=True,
        uhv_filter=True,
        trigger_past_uhv=True, trigger_past_pts=0.3,
        tick_speed_max=True, tick_speed_sec=15,
        spread_max=True, spread_mult=1.3,
        m15_trend=True,
        setup1_filter=True, lb_bars=3, pattern_lb=10,
        chain_stop=True, chain_stop_n=2,
        burst_delta=True,
        cdd_div_exit=True):

    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, ema_m15_s, bar_idx_15m, _ = get_emas(21, 21, 15)  # use fast as 21-EMA proxy

    # Spread baseline tracking — rolling 60s median
    def spread_at(when):
        ticks = ticks_in_range(when - timedelta(seconds=60), when)
        if len(ticks) < 5: return None, None
        spreads = sorted([ask - bid for _, bid, ask in ticks])
        med = spreads[len(spreads)//2]
        # current spread = last tick
        cur = ticks[-1][2] - ticks[-1][1]
        return cur, med

    chains = []
    consec_losing = 0
    blocked_by = {}  # filter -> count

    def block(filter_name):
        blocked_by[filter_name] = blocked_by.get(filter_name, 0) + 1

    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue

        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in ticks:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        # Filter cascade
        if skip_bad_hours:
            h = confirm_dt.hour
            if (4 <= h <= 6) or (21 <= h <= 23): block('bad_hours'); continue
        if skip_fast_confirm:
            if 3 <= confirm_speed <= 8: block('fast_confirm'); continue
        if trend_filter:
            t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t is None or t == 0 or t != dir_sign: block('trend_2m'); continue
        if chain_stop:
            if consec_losing >= chain_stop_n: block('chain_stop'); continue

        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: block('no_uhv_data'); continue
        trigger = bars_1m[trigger_idx]
        if uhv_filter:
            margin = trigger_past_pts if trigger_past_uhv else 0.0
            if dir_sign == 1 and trigger[4] < uhv[2] + margin: block('uhv_filter'); continue
            if dir_sign == -1 and trigger[4] > uhv[3] - margin: block('uhv_filter'); continue
        elif trigger_past_uhv:
            # Margin requires UHV filter — if UHV off, margin is moot
            pass

        if tick_speed_max:
            # tick-speed: confirm_speed should be <= tick_speed_sec
            if confirm_speed > tick_speed_sec: block('tick_speed'); continue

        if spread_max:
            cur, med = spread_at(confirm_dt)
            if cur is not None and med is not None and med > 0 and cur > spread_mult * med:
                block('spread'); continue

        if m15_trend:
            ema_v, idx15 = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
            if ema_v is not None:
                price = (confirm_bid + confirm_ask) / 2
                if dir_sign == 1 and price <= ema_v: block('m15_trend'); continue
                if dir_sign == -1 and price >= ema_v: block('m15_trend'); continue

        if setup1_filter:
            if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, lb_bars, pattern_lb):
                block('setup1'); continue

        # All filters passed — sim the chain
        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m,
                          cdd_div_exit=cdd_div_exit,
                          burst_skip_bad_hours=skip_bad_hours,
                          burst_trend=trend_filter,
                          burst_uhv=uhv_filter,
                          burst_delta=burst_delta)
        chains.append(chain)
        chain_pnl = sum(m[1] for m in chain)
        if chain_pnl < 0: consec_losing += 1
        else: consec_losing = 0

    n = len(chains); all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    chain_wr = (n - losing) / max(n, 1) * 100
    main_wr = wins/max(len(all_mains),1)*100
    print(f"  {label:<60}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chain_WR={chain_wr:>5.1f}%")
    return n, total, losing, chain_wr, blocked_by


print("=" * 200)
print("LEAVE-ONE-OUT FILTER ANALYSIS")
print("Goal: find filters cutting trades without adding edge")
print("=" * 200)
print()
print("--- FULL LIVE STACK (baseline) ---")
n_base, t_base, l_base, wr_base, blocks = run("LIVE: full ULTIMATE stack")
print()
print("Per-filter block count (probes blocked at each gate):")
for k, v in sorted(blocks.items(), key=lambda x: -x[1]):
    print(f"  {k:<20} blocked {v:>4} probes")

print()
print("=" * 200)
print("LEAVE-ONE-OUT (turn off ONE filter, keep all others)")
print("=" * 200)

variants = [
    ("WITHOUT skip_bad_hours",       dict(skip_bad_hours=False)),
    ("WITHOUT skip_fast_confirm",    dict(skip_fast_confirm=False)),
    ("WITHOUT trend_filter (2m)",    dict(trend_filter=False)),
    ("WITHOUT uhv_filter",           dict(uhv_filter=False, trigger_past_uhv=False)),
    ("WITHOUT trigger_past_uhv",     dict(trigger_past_uhv=False)),
    ("WITHOUT tick_speed_max",       dict(tick_speed_max=False)),
    ("WITHOUT spread_max",           dict(spread_max=False)),
    ("WITHOUT m15_trend",            dict(m15_trend=False)),
    ("WITHOUT setup1_filter",        dict(setup1_filter=False)),
    ("WITHOUT chain_stop",           dict(chain_stop=False)),
    ("WITHOUT burst_delta",          dict(burst_delta=False)),
    ("WITHOUT cdd_div_exit",         dict(cdd_div_exit=False)),
]

for label, kwargs in variants:
    n, t, l, wr, _ = run(label, **kwargs)
    delta_n = n - n_base
    delta_t = t - t_base
    print(f"      Δ chains={delta_n:+d}  Δ total=${delta_t:+.2f}  Δ losing={l-l_base:+d}")

print()
print("=" * 200)
print("HIGHEST-IMPACT relaxations (+chains with minimal losing-chain hit)")
print("=" * 200)
print("Look for: large +chains, small +losing, decent +total")
