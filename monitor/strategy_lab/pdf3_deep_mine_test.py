"""pdf3_deep_mine_test.py — mine PDF #3 microstructure phrases for untested filters.

Already tested elsewhere:
  - POC bottom-33% (report_microstructure_test.py)
  - Internal structure body/wicks (same)
  - Wide UHV >= 1.5x ATR (same)
  - Pseudo-delta at probe-confirm 20s (same — 87.3% WR / +$957)
  - Pseudo-delta at burst (delta_application_test.py — 90.0% WR / +$1270 / 1 losing)
  - Micro-stall (hurt performance, skip)
  - Session overlap broker 15-18 (very small sample)

Tests NEW from PDF text:
  1) CDD TRUE DIVERGENCE as exit — track cumulative delta during open trade.
     Exit when price makes new HH but cumDelta makes lower HH.
  2) LOWER-VOLUME TRIGGER requirement — trigger candle tickVolume < UHV tickVolume.
  3) HEAVY POSITIVE DELTA at confirm — delta/total > threshold (sweep 0.10, 0.20, 0.30).
  4) TRIGGER >= Npt PAST UHV (sweep 0.5, 1.0, 1.5, 2.0).
  5) ATR MULTIPLIER SWEEP (1.2, 1.5, 1.8, 2.0).
  6) ULTIMATE STACK — LIVE config + best confirmed adders.
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


# ─── shared helpers ───────────────────────────────────────────
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


def find_setup1_uhv_bar_with_trigger(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars=3, pattern_lookback=10):
    """Find both UHV catalyst and trigger bar from most-recent Setup 1 match."""
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


# ─── PDF NEW filters ──────────────────────────────────────────
def lower_vol_trigger(uhv_bar, trigger_bar, ratio_max=1.0):
    """Trigger candle tick volume must be < ratio_max * UHV tick volume."""
    if trigger_bar is None or uhv_bar is None: return False
    return trigger_bar[5] < uhv_bar[5] * ratio_max


def heavy_positive_delta(probe_time, dir_sign, lookback_sec=20, min_ratio=0.20):
    """delta / total > min_ratio. Disproportionate aggressive flow."""
    end = probe_time
    start = end - timedelta(seconds=lookback_sec)
    ticks = ticks_in_range(start, end)
    if len(ticks) < 5: return False
    up = down = 0; prev_mid = None
    for _, bid, ask in ticks:
        mid = (bid + ask) / 2
        if prev_mid is not None:
            if mid > prev_mid: up += 1
            elif mid < prev_mid: down += 1
        prev_mid = mid
    total = up + down
    if total < 5: return False
    if dir_sign == 1:
        return (up - down) / total >= min_ratio
    else:
        return (down - up) / total >= min_ratio


def trigger_past_uhv(uhv_bar, trigger_close, dir_sign, min_pts=1.0):
    """Trigger close must be >= min_pts past UHV extreme."""
    if uhv_bar is None: return False
    if dir_sign == 1: return trigger_close - uhv_bar[2] >= min_pts
    else: return uhv_bar[3] - trigger_close >= min_pts


def has_wide_uhv(uhv_bar, atr_val, mult=1.5):
    if atr_val is None or atr_val <= 0: return False
    rng = uhv_bar[2] - uhv_bar[3]
    return rng >= mult * atr_val


def pseudo_delta_positive(probe_time, dir_sign, lookback_sec=20):
    end = probe_time
    start = end - timedelta(seconds=lookback_sec)
    ticks = ticks_in_range(start, end)
    if len(ticks) < 5: return False
    up = down = 0; prev_mid = None
    for _, bid, ask in ticks:
        mid = (bid + ask) / 2
        if prev_mid is not None:
            if mid > prev_mid: up += 1
            elif mid < prev_mid: down += 1
        prev_mid = mid
    delta = up - down
    return (dir_sign == 1 and delta > 0) or (dir_sign == -1 and delta < 0)


# ─── CDD true divergence ────────────────────────────────────
def sim_one_main_cdd_div(entry, dir_sign, ticks, fear_ideal, lots,
                          trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP,
                          cdd_check_sec=5, cdd_window_sec=15, min_profit=5.0):
    """Sim main with CDD divergence exit:
    Track price-HWM and a sliding-window cumulative delta. When in profit > min_profit,
    every cdd_check_sec, look at last cdd_window_sec of ticks: if price > previous HWM
    but cumDelta in window < previous max cumDelta in window → divergence → exit."""
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    entry_time = ticks[0][0]
    price_hwm = entry
    cumdelta_hwm = 0
    last_check = entry_time
    # Walk ticks, keep rolling delta in sliding window
    window = []  # (dt, mid, delta_sign)
    prev_mid = None
    for dt, bid, ask in ticks:
        mid = (bid + ask) / 2
        if dir_sign == 1:
            profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else:
            profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        # Tick direction
        sgn = 0
        if prev_mid is not None:
            if mid > prev_mid: sgn = 1
            elif mid < prev_mid: sgn = -1
        prev_mid = mid
        window.append((dt, mid, sgn))
        # Trim window
        cutoff = dt - timedelta(seconds=cdd_window_sec)
        while window and window[0][0] < cutoff: window.pop(0)
        # CDD divergence check
        if profit >= min_profit and (dt - last_check).total_seconds() >= cdd_check_sec:
            last_check = dt
            cur_cumdelta = sum(w[2] for w in window)
            if dir_sign == 1: cur_cumdelta_dir = cur_cumdelta
            else: cur_cumdelta_dir = -cur_cumdelta
            # Compare to HWMs
            new_price_hwm = (dir_sign == 1 and cur > price_hwm) or (dir_sign == -1 and cur < price_hwm)
            if new_price_hwm:
                if cur_cumdelta_dir < cumdelta_hwm:
                    return round(profit, 2), dt, cur
                price_hwm = cur
                cumdelta_hwm = cur_cumdelta_dir
            elif cur_cumdelta_dir > cumdelta_hwm:
                cumdelta_hwm = cur_cumdelta_dir
        if profit <= -fear_ideal: return round(profit, 2), dt, cur
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur
    return round(last, 2), last_dt, last_price


def sim_one_main(entry, dir_sign, ticks, fear_ideal, lots,
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP):
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else: profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return round(profit, 2), dt, cur
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur
    return round(last, 2), last_dt, last_price


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def burst_delta_positive(when, dir_sign, lookback_sec=15):
    end = when
    start = end - timedelta(seconds=lookback_sec)
    ticks = ticks_in_range(start, end)
    if len(ticks) < 5: return True  # fail-open if too sparse
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


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
                         uhv_lookback=20, require_burst_delta=True, burst_delta_lb=15):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
    if t is None or t == 0 or t != dir_sign: return False
    uhv, _, _ = get_uhv_bar(when, bars_1m, bar_idx_1m, uhv_lookback)
    if uhv is None: return False
    if dir_sign == 1 and price <= uhv[2]: return False
    if dir_sign == -1 and price >= uhv[3]: return False
    if require_burst_delta:
        if not burst_delta_positive(when, dir_sign, burst_delta_lb): return False
    return True


def sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
               fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
               ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
               uhv_lookback=20, horizon_sec=HORIZON_SEC,
               require_burst_delta=True, burst_delta_lb=15,
               cdd_div_exit=False, cdd_check_sec=5, cdd_window_sec=15):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        if cdd_div_exit:
            pnl, exit_dt, exit_price = sim_one_main_cdd_div(
                main_entry, dir_sign, ticks, fear_ideal, lots,
                trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP,
                cdd_check_sec=cdd_check_sec, cdd_window_sec=cdd_window_sec)
        else:
            pnl, exit_dt, exit_price = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price, ema_f, ema_s, bar_idx_2m,
                                    bars_1m, bar_idx_1m, uhv_lookback,
                                    require_burst_delta=require_burst_delta,
                                    burst_delta_lb=burst_delta_lb): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run(label, *,
        require_setup1=True, lb_bars=3, pattern_lb=10,
        require_lower_vol_trigger=False, lower_vol_ratio=1.0,
        require_heavy_delta=False, heavy_delta_ratio=0.20, heavy_delta_lb=20,
        require_trigger_past=False, trigger_past_pts=1.0,
        require_wide_uhv=False, wide_uhv_mult=1.5,
        require_pseudo_delta_confirm=False, pseudo_delta_lb=20,
        require_burst_delta=True, burst_delta_lb=15,
        cdd_div_exit=False, cdd_check_sec=5, cdd_window_sec=15):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    atr_1m = compute_atr(bars_1m, 14)
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

        # BIG STACK base
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

        # Setup 1 HARD GATE (LIVE)
        if require_setup1:
            if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, lb_bars, pattern_lb): continue

        # Get S1 UHV + trigger for filters
        s1_uhv, s1_trig = find_setup1_uhv_bar_with_trigger(
            entry_time, dir_sign, bars_1m, bar_idx_1m, lb_bars, pattern_lb)
        if not s1_uhv: s1_uhv = uhv
        if not s1_trig: s1_trig = trigger

        # NEW filters
        if require_lower_vol_trigger:
            if not lower_vol_trigger(s1_uhv, s1_trig, lower_vol_ratio): continue
        if require_heavy_delta:
            if not heavy_positive_delta(entry_time, dir_sign, heavy_delta_lb, heavy_delta_ratio): continue
        if require_trigger_past:
            if not trigger_past_uhv(s1_uhv, s1_trig[4], dir_sign, trigger_past_pts): continue
        if require_wide_uhv:
            uhv_dt = s1_uhv[0]
            uhv_idx = bar_idx_1m.get(uhv_dt)
            atr_val = atr_1m[uhv_idx] if uhv_idx and uhv_idx < len(atr_1m) else None
            if not has_wide_uhv(s1_uhv, atr_val, wide_uhv_mult): continue
        if require_pseudo_delta_confirm:
            if not pseudo_delta_positive(entry_time, dir_sign, pseudo_delta_lb): continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m,
                          require_burst_delta=require_burst_delta,
                          burst_delta_lb=burst_delta_lb,
                          cdd_div_exit=cdd_div_exit,
                          cdd_check_sec=cdd_check_sec,
                          cdd_window_sec=cdd_window_sec)
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
print("PDF #3 DEEP MINE — testing UNTESTED phrases on top of LIVE (Setup 1 + burst-delta-15s)")
print("=" * 200)
print()
print("--- BASELINE: LIVE config (Setup 1 lb=3 + burst-delta-15s) ---")
run("LIVE: Setup 1 + burst-delta-15s", require_burst_delta=True, burst_delta_lb=15)

print()
print("--- 1) CDD TRUE DIVERGENCE as exit (price-HH but cumDelta lower-HH) ---")
for cs, cw in [(5, 15), (5, 30), (10, 30), (10, 60), (3, 10)]:
    run(f"+ CDD-div exit (check {cs}s, window {cw}s)",
        cdd_div_exit=True, cdd_check_sec=cs, cdd_window_sec=cw)

print()
print("--- 2) LOWER-VOLUME TRIGGER (trigger < ratio * UHV) ---")
for r in [0.5, 0.7, 0.9, 1.0]:
    run(f"+ trigger vol < {r} * UHV vol", require_lower_vol_trigger=True, lower_vol_ratio=r)

print()
print("--- 3) HEAVY POSITIVE DELTA at confirm (delta/total > X) ---")
for ratio in [0.10, 0.15, 0.20, 0.25, 0.30]:
    for lb in [15, 20, 30]:
        run(f"+ heavy delta {ratio:.2f} (lb={lb}s)",
            require_heavy_delta=True, heavy_delta_ratio=ratio, heavy_delta_lb=lb)

print()
print("--- 4) TRIGGER >= Npt PAST UHV (cleaner breakout requirement) ---")
for pts in [0.3, 0.5, 1.0, 1.5, 2.0]:
    run(f"+ trigger >= {pts}pt past UHV",
        require_trigger_past=True, trigger_past_pts=pts)

print()
print("--- 5) ATR MULTIPLIER SWEEP (UHV range >= X * ATR) ---")
for mult in [1.0, 1.2, 1.5, 1.8, 2.0]:
    run(f"+ wide UHV >= {mult}x ATR",
        require_wide_uhv=True, wide_uhv_mult=mult)

print()
print("--- 6) STACKED CONFIRMED WINNERS ---")
run("+ pseudo-delta confirm 30s",
    require_pseudo_delta_confirm=True, pseudo_delta_lb=30)
run("+ pseudo-delta confirm 30s + lower-vol trigger 0.9x",
    require_pseudo_delta_confirm=True, pseudo_delta_lb=30,
    require_lower_vol_trigger=True, lower_vol_ratio=0.9)
run("+ pseudo-delta confirm 30s + trigger>=1pt past",
    require_pseudo_delta_confirm=True, pseudo_delta_lb=30,
    require_trigger_past=True, trigger_past_pts=1.0)
run("+ heavy delta 0.20 lb=20 + lower-vol 1.0",
    require_heavy_delta=True, heavy_delta_ratio=0.20, heavy_delta_lb=20,
    require_lower_vol_trigger=True, lower_vol_ratio=1.0)

print()
print("--- 7) ULTIMATE CANDIDATES — best-of-best ---")
run("ULTIMATE A: confirm-delta30s + burst-delta15s",
    require_pseudo_delta_confirm=True, pseudo_delta_lb=30,
    require_burst_delta=True, burst_delta_lb=15)
run("ULTIMATE B: heavy-delta0.20 + burst-delta15s",
    require_heavy_delta=True, heavy_delta_ratio=0.20, heavy_delta_lb=20,
    require_burst_delta=True, burst_delta_lb=15)
run("ULTIMATE C: confirm-delta30 + heavy0.20 + burst15",
    require_pseudo_delta_confirm=True, pseudo_delta_lb=30,
    require_heavy_delta=True, heavy_delta_ratio=0.20, heavy_delta_lb=20,
    require_burst_delta=True, burst_delta_lb=15)
