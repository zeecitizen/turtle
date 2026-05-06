"""delta_application_test.py — find where pseudo-delta filter has most impact.

Test points:
  A) AT PROBE-CONFIRM (entry to first main) — current test
  B) AT EACH BURST-FIRE — require positive delta before opening burst N
  C) BOTH — required at confirm AND at each burst
  D) AS EXIT SIGNAL — if delta turns negative during open position, exit early

Plus lookback window tuning: 5s, 10s, 15s, 20s, 30s, 60s.
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


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback=20):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
    if t is None or t == 0 or t != dir_sign: return False
    uhv, _, _ = get_uhv_bar(when, bars_1m, bar_idx_1m, uhv_lookback)
    if uhv is None: return False
    if dir_sign == 1 and price <= uhv[2]: return False
    if dir_sign == -1 and price >= uhv[3]: return False
    return True


def pseudo_delta_positive(when, dir_sign, lookback_sec=20):
    end = when
    start = end - timedelta(seconds=lookback_sec)
    ticks = ticks_in_range(start, end)
    if len(ticks) < 5: return False
    up = 0; down = 0; prev_mid = None
    for _, bid, ask in ticks:
        mid = (bid + ask) / 2
        if prev_mid is not None:
            if mid > prev_mid: up += 1
            elif mid < prev_mid: down += 1
        prev_mid = mid
    delta = up - down
    return (dir_sign == 1 and delta > 0) or (dir_sign == -1 and delta < 0)


def sim_one_main_with_delta_exit(entry, dir_sign, ticks, fear_ideal, lots,
                                  trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP,
                                  delta_exit=False, delta_check_interval=10, delta_lookback=20):
    """If delta_exit=True: every N seconds while in profit, check delta. If turns negative, exit."""
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    last_delta_check = ticks[0][0]
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else: profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        # Delta-divergence exit: when in profit but delta turning bearish for buys
        if delta_exit and profit > 5 and (dt - last_delta_check).total_seconds() >= delta_check_interval:
            if not pseudo_delta_positive(dt, dir_sign, delta_lookback):
                return round(profit, 2), dt, cur
            last_delta_check = dt
        if profit <= -fear_ideal: return round(profit, 2), dt, cur
        if peak >= trail_trig and (peak - profit) >= trail_drop:
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
              uhv_lookback=20, horizon_sec=HORIZON_SEC,
              delta_at_burst=False, delta_lookback=20,
              delta_exit=False, delta_exit_interval=10):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        # Burst-time delta filter (skip burst > 0 if delta turns negative)
        if delta_at_burst and burst_idx > 0:
            if not pseudo_delta_positive(cur_dt, dir_sign, delta_lookback):
                break
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price = sim_one_main_with_delta_exit(
            main_entry, dir_sign, ticks, fear_ideal, lots,
            delta_exit=delta_exit, delta_check_interval=delta_exit_interval, delta_lookback=delta_lookback)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


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


def setup1_active(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars, pattern_lookback):
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


def run(label, *, delta_at_confirm=False, delta_at_burst=False, delta_exit=False,
        delta_lookback=20, delta_exit_interval=10):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

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
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in ticks:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        # Standard BIG STACK base filters
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # Setup 1 HARD GATE (current LIVE: lb_bars=3, pattern_lb=10)
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10): continue

        # Delta at confirm
        if delta_at_confirm:
            if not pseudo_delta_positive(confirm_dt, dir_sign, delta_lookback): continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m,
                          delta_at_burst=delta_at_burst, delta_lookback=delta_lookback,
                          delta_exit=delta_exit, delta_exit_interval=delta_exit_interval)
        chains.append(chain)

    n = len(chains); all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    chain_wr = (n - losing) / max(n, 1) * 100
    print(f"  {label:<70}chains={n:<3}  WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chain_WR={chain_wr:>5.1f}%  worst=${big_loss:+.2f}")


print("=" * 200)
print("PSEUDO-DELTA APPLICATION POINTS — find where it has most impact")
print("All on top of Setup 1 HARD GATE lb=3 (current LIVE)")
print("=" * 200)
print()
print("--- BASELINE (current LIVE: no delta) ---")
run("baseline (no delta filter)")

print()
print("--- A) DELTA AT PROBE-CONFIRM (current single test) ---")
run("delta at confirm (lookback=20s)", delta_at_confirm=True, delta_lookback=20)

print()
print("--- B) DELTA AT EACH BURST-FIRE only (no confirm filter) ---")
run("delta at each burst (lookback=20s)", delta_at_burst=True, delta_lookback=20)

print()
print("--- C) DELTA AT BOTH (confirm + each burst) ---")
run("delta at confirm + bursts", delta_at_confirm=True, delta_at_burst=True, delta_lookback=20)

print()
print("--- D) DELTA AS EXIT SIGNAL (during open position) ---")
for interval in [5, 10, 15, 30]:
    run(f"delta exit (check every {interval}s, profit>5)",
        delta_exit=True, delta_exit_interval=interval, delta_lookback=20)

print()
print("--- E) DELTA AT CONFIRM + AS EXIT SIGNAL ---")
run("delta at confirm + exit-on-divergence (10s interval)",
    delta_at_confirm=True, delta_exit=True, delta_exit_interval=10, delta_lookback=20)

print()
print("--- LOOKBACK WINDOW TUNING (delta at confirm only) ---")
for lb in [5, 10, 15, 20, 30, 60]:
    run(f"delta at confirm, lookback={lb}s", delta_at_confirm=True, delta_lookback=lb)

print()
print("--- LOOKBACK WINDOW TUNING (delta at burst only) ---")
for lb in [5, 10, 15, 20, 30]:
    run(f"delta at burst, lookback={lb}s", delta_at_burst=True, delta_lookback=lb)

print()
print("--- COMBINED TUNED ---")
run("BEST guess: confirm 20s + burst 10s",
    delta_at_confirm=True, delta_at_burst=True, delta_lookback=15)
run("AGGRESSIVE: confirm 30s + burst 30s + exit 5s",
    delta_at_confirm=True, delta_at_burst=True, delta_exit=True,
    delta_exit_interval=5, delta_lookback=30)
