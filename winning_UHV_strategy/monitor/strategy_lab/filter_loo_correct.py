"""filter_loo_correct.py — corrected LOO with proper tick-speed measurement.

BUG IN PREVIOUS LOO: was using confirm_speed (probe→main confirm time) instead of
the EA's actual tick-speed metric (seconds-into-trigger-bar of UHV cross).

CORRECT tick-speed:
  trigger_bar_open = probe_entry_minute - 1 minute
  walk trigger bar's ticks, find first tick where bid > uhv_high (buy) or ask < uhv_low (sell)
  tick_speed = (cross_time - bar_open).total_seconds()
  block if tick_speed > maxSec (default 15)

CORRECT spread:
  60-sample-per-second rolling buffer. Median of last 60 seconds.
  block if current_spread > spread_mult * median.
  (My old impl used last 60s of TICKS, not 1Hz samples — should be close enough.)
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
        if idx is None: return None
    if idx < 21: return None
    return ema_m15[idx]


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


# ─── CORRECTED tick-speed measurement ──────────────────────────────
def actual_tick_speed(probe_entry_time, dir_sign, uhv_high, uhv_low):
    """Measure seconds-into-trigger-bar where price first crossed UHV extreme.
    Trigger bar = the M1 bar that JUST CLOSED before the probe entry.
    """
    # Probe entry happens AFTER the trigger bar closes.
    # If probe entry is at 14:30:00+ (anywhere in 14:30 minute), trigger bar = 14:29:00-14:29:59.
    probe_min = probe_entry_time.replace(second=0, microsecond=0)
    bar_open = probe_min - timedelta(minutes=1)
    bar_close = probe_min  # exclusive
    ticks = ticks_in_range(bar_open, bar_close)
    if not ticks: return None
    extreme = uhv_high if dir_sign == 1 else uhv_low
    for dt, bid, ask in ticks:
        if dir_sign == 1 and bid > extreme:
            return (dt - bar_open).total_seconds()
        if dir_sign == -1 and ask < extreme:
            return (dt - bar_open).total_seconds()
    return None  # never crossed in trigger bar (rare — UHV filter would block this anyway)


# ─── CORRECTED spread measurement ──────────────────────────────────
def actual_spread_check(when, mult):
    """Match EA logic: rolling 60-sample 1Hz median, block if cur > mult * median."""
    # Approximate by sampling 1 spread per second over last 60s
    samples = []
    for sec_ago in range(60, 0, -1):
        t = when - timedelta(seconds=sec_ago)
        # Find the closest tick at or after this second
        ticks = ticks_in_range(t, t + timedelta(seconds=1))
        if ticks:
            _, bid, ask = ticks[0]
            samples.append(ask - bid)
    if len(samples) < 30: return True  # warm-up: allow
    samples_sorted = sorted(samples)
    med = samples_sorted[len(samples_sorted)//2]
    if med <= 0: return True
    # Current spread (just before `when`)
    cur_ticks = ticks_in_range(when - timedelta(seconds=2), when)
    if not cur_ticks: return True
    _, cur_bid, cur_ask = cur_ticks[-1]
    cur_spread = cur_ask - cur_bid
    return cur_spread <= mult * med


# ─── Setup 1 + helpers ──────────────────────────────
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


def sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
               fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
               ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
               horizon_sec=HORIZON_SEC, cdd_div_exit=True, burst_delta=True):
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
        h = exit_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): break
        t = trend_at(exit_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: break
        uhv, _, _ = get_uhv_bar(exit_dt, bars_1m, bar_idx_1m, 20)
        if uhv is None: break
        if dir_sign == 1 and exit_price <= uhv[2]: break
        if dir_sign == -1 and exit_price >= uhv[3]: break
        if burst_delta and not burst_delta_positive(exit_dt, dir_sign, 15): break
        cur_dt = exit_dt; main_entry = exit_price; burst_idx += 1
    return main_results


def run(label, *,
        skip_bad_hours=True,
        skip_fast_confirm=True,
        trend_filter=True,
        uhv_filter=True,
        trigger_past_pts=0.3,
        tick_speed_sec=15,    # 0 = OFF
        spread_mult=1.3,      # 0 = OFF
        m15_trend=True,
        setup1_filter=True,
        chain_stop_n=2,
        burst_delta=True,
        cdd_div_exit=True,
        verbose=False):

    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

    chains = []
    consec_losing = 0
    blocked_by = {}
    tick_speeds_passed = []  # for analysis

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

        if skip_bad_hours:
            h = confirm_dt.hour
            if (4 <= h <= 6) or (21 <= h <= 23): block('bad_hours'); continue
        if skip_fast_confirm:
            if 3 <= confirm_speed <= 8: block('fast_confirm'); continue
        if trend_filter:
            t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t is None or t == 0 or t != dir_sign: block('trend_2m'); continue
        if chain_stop_n > 0 and consec_losing >= chain_stop_n: block('chain_stop'); continue

        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: block('no_uhv_data'); continue
        trigger = bars_1m[trigger_idx]
        margin = trigger_past_pts
        if uhv_filter:
            if dir_sign == 1 and trigger[4] < uhv[2] + margin: block('uhv_filter'); continue
            if dir_sign == -1 and trigger[4] > uhv[3] - margin: block('uhv_filter'); continue

        # CORRECTED tick-speed
        if tick_speed_sec > 0:
            ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
            if ts is None or ts > tick_speed_sec:
                block('tick_speed'); continue
            tick_speeds_passed.append(ts)
        else:
            # Still record for analysis
            ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
            if ts is not None: tick_speeds_passed.append(ts)

        # CORRECTED spread (still rough but better than my old impl)
        if spread_mult > 0:
            if not actual_spread_check(confirm_dt, spread_mult):
                block('spread'); continue

        if m15_trend:
            ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
            if ema_v is not None:
                price = (confirm_bid + confirm_ask) / 2
                if dir_sign == 1 and price <= ema_v: block('m15_trend'); continue
                if dir_sign == -1 and price >= ema_v: block('m15_trend'); continue

        if setup1_filter:
            if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10):
                block('setup1'); continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m,
                          cdd_div_exit=cdd_div_exit, burst_delta=burst_delta)
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
    if verbose and tick_speeds_passed:
        ts_sorted = sorted(tick_speeds_passed)
        print(f"      tick-speed of passing trades: min={min(ts_sorted):.1f}s  median={ts_sorted[len(ts_sorted)//2]:.1f}s  max={max(ts_sorted):.1f}s  count={len(ts_sorted)}")
    return n, total, losing, blocked_by, tick_speeds_passed


print("=" * 200)
print("CORRECTED LOO — using EA's actual tick-speed + spread measurement")
print("=" * 200)

print()
print("--- BASELINE: full LIVE stack with CORRECTED measurement ---")
n_base, t_base, l_base, blocks, ts_passed = run("LIVE corrected", verbose=True)
print()
print("Block counts (corrected):")
for k, v in sorted(blocks.items(), key=lambda x: -x[1]):
    print(f"  {k:<20} blocked {v:>4}")

print()
print("--- TICK-SPEED SWEEP with CORRECT measurement ---")
print("Now answer: does tightening tick-speed actually IMPROVE WR or just cut trades?")
for sec in [5, 10, 15, 20, 25, 30, 45, 60]:
    run(f"tick_speed<={sec}s (correct)", tick_speed_sec=sec, verbose=True)
run("tick_speed OFF", tick_speed_sec=0, verbose=True)

print()
print("--- DISTRIBUTION OF tick-speed of QUALIFYING trades ---")
n, t, l, b, ts = run("collect-all (no tick filter)", tick_speed_sec=0, verbose=False)
ts.sort()
if ts:
    print(f"Quartiles of tick-speeds (sec) of {len(ts)} qualifying probes:")
    q1 = ts[len(ts)//4]; q2 = ts[len(ts)//2]; q3 = ts[3*len(ts)//4]
    print(f"  Q1={q1:.1f}s  Q2(median)={q2:.1f}s  Q3={q3:.1f}s  min={min(ts):.1f}  max={max(ts):.1f}")
