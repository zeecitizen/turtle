"""report_microstructure_test.py — backtest microstructure findings from the report.

Layers on top of current LIVE config (Setup 1 HARD GATE + BIG STACK descending ladder).

NEW filters tested:
  A) POC LOWER-33% rule (approx via tick density in UHV bar)
  B) Internal structure (body ≥50%, wicks ≤40%)
  C) UHV range ≥ 1.5× ATR(14)
  D) Pseudo-delta positive at breakout
  E) Micro-stall exit (10s/3pip)
  F) Session-overlap-only (15-19 broker)
  G) Combined report-stack
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

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


def sim_one_main(entry, dir_sign, ticks, fear_ideal, lots,
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP,
                 micro_stall_sec=0, micro_stall_pips=0):
    """Sim a main with optional micro-stall exit."""
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    entry_time = ticks[0][0]
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
            adv_pts = bid - entry
        else:
            profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
            adv_pts = entry - ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        # Micro-stall check
        if micro_stall_sec > 0 and micro_stall_pips > 0:
            elapsed = (dt - entry_time).total_seconds()
            if elapsed >= micro_stall_sec and adv_pts < micro_stall_pips:
                return round(profit, 2), dt, cur
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
              micro_stall_sec=0, micro_stall_pips=0):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots,
                                                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP,
                                                 micro_stall_sec=micro_stall_sec, micro_stall_pips=micro_stall_pips)
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


# ────────── REPORT FILTERS ──────────

def find_setup1_uhv_bar(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars=3, pattern_lookback=10):
    """Find the UHV red bar that is the catalyst of the most-recent Setup 1 match."""
    bm = probe_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None: return None
    start = max(pattern_lookback, idx - lookback_bars)
    for trig in range(idx, start - 1, -1):
        if not setup1_at_m1(bars_1m, trig, dir_sign, pattern_lookback): continue
        # Found a match — return the UHV anchor bar
        uhv_idx = find_uhv_red_idx_m1(bars_1m, trig, pattern_lookback, dir_sign)
        if uhv_idx is None: continue
        return bars_1m[uhv_idx]
    return None


def approx_poc_in_bottom33(uhv_bar):
    """Approximate POC: walk ticks in the UHV bar's minute, compute price-bucket histogram,
    find the price with the most ticks. Check if it's in lower 33% of the bar's range."""
    bar_dt = uhv_bar[0]
    bar_high = uhv_bar[2]; bar_low = uhv_bar[3]
    rng = bar_high - bar_low
    if rng <= 0: return False
    ticks = ticks_in_range(bar_dt, bar_dt + timedelta(seconds=60))
    if not ticks: return False
    # Histogram with 20 buckets
    buckets = [0] * 20
    for _, bid, ask in ticks:
        mid = (bid + ask) / 2
        if mid < bar_low or mid > bar_high: continue
        b = min(19, int((mid - bar_low) / rng * 20))
        buckets[b] += 1
    if max(buckets) == 0: return False
    poc_bucket = buckets.index(max(buckets))
    poc_pct = poc_bucket / 20.0  # fraction of range from low
    return poc_pct < 0.33  # in bottom third


def has_internal_structure(uhv_bar, body_min=0.50, wick_max=0.40):
    """Body ≥ X% of range, no individual wick > Y% of range."""
    o, h, l, c = uhv_bar[1], uhv_bar[2], uhv_bar[3], uhv_bar[4]
    rng = h - l
    if rng <= 0: return False
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    if body / rng < body_min: return False
    if upper_wick / rng > wick_max: return False
    if lower_wick / rng > wick_max: return False
    return True


def has_wide_uhv(uhv_bar, atr_val, mult=1.5):
    """UHV range ≥ mult × ATR(14)."""
    if atr_val is None or atr_val <= 0: return False
    rng = uhv_bar[2] - uhv_bar[3]
    return rng >= mult * atr_val


def pseudo_delta_positive(probe_time, dir_sign, lookback_sec=20):
    """Approx delta: count up-ticks vs down-ticks in trigger bar's first N seconds.
    For buys: more up-ticks = positive delta = good."""
    end = probe_time
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


def in_session_overlap(when):
    """Broker time 15:00-19:00 = London/NY overlap (GMT 12-16)."""
    h = when.hour
    return 15 <= h <= 18


def run(label, *, require_setup1=True, lb_bars=3, pattern_lb=10,
         require_poc33=False, require_structure=False, require_wide_uhv=False,
         require_pseudo_delta=False, require_session_overlap=False,
         micro_stall_sec=0, micro_stall_pips=0):
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

        # Setup 1 HARD GATE (current LIVE)
        if require_setup1:
            if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, lb_bars, pattern_lb): continue

        # Get the Setup 1 UHV catalyst bar for POC/structure/wide checks
        s1_uhv = find_setup1_uhv_bar(entry_time, dir_sign, bars_1m, bar_idx_1m, lb_bars, pattern_lb) if require_setup1 else uhv

        # ── REPORT FILTERS ──
        if require_poc33 and s1_uhv:
            if not approx_poc_in_bottom33(s1_uhv): continue
        if require_structure and s1_uhv:
            if not has_internal_structure(s1_uhv): continue
        if require_wide_uhv and s1_uhv:
            uhv_dt = s1_uhv[0]
            uhv_idx = bar_idx_1m.get(uhv_dt)
            atr_val = atr_1m[uhv_idx] if uhv_idx and uhv_idx < len(atr_1m) else None
            if not has_wide_uhv(s1_uhv, atr_val, 1.5): continue
        if require_pseudo_delta:
            if not pseudo_delta_positive(entry_time, dir_sign, 20): continue
        if require_session_overlap:
            if not in_session_overlap(confirm_dt): continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m,
                          micro_stall_sec=micro_stall_sec, micro_stall_pips=micro_stall_pips)
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
print("REPORT MICROSTRUCTURE — testing on top of Setup 1 HARD GATE (current LIVE)")
print("=" * 200)
print()
print("--- BASELINE (current LIVE) ---")
run("Setup 1 HARD GATE lb=3 (current LIVE)", lb_bars=3)

print()
print("--- A) POC LOWER-33% rule (approx via tick density in UHV bar) ---")
run("+ POC bottom-33%", lb_bars=3, require_poc33=True)

print()
print("--- B) Internal structure (body >=50%, wicks <=40%) ---")
run("+ structure: body>=50% wicks<=40%", lb_bars=3, require_structure=True)

print()
print("--- C) UHV range >= 1.5x ATR(14) ---")
run("+ wide UHV (>=1.5x ATR)", lb_bars=3, require_wide_uhv=True)

print()
print("--- D) Pseudo-delta positive at breakout ---")
run("+ pseudo-delta positive (last 20s ticks)", lb_bars=3, require_pseudo_delta=True)

print()
print("--- E) MICRO-STALL exit (10s / 3pip) ---")
run("+ micro-stall 10s/3pip", lb_bars=3, micro_stall_sec=10, micro_stall_pips=3)
run("+ micro-stall 10s/2pip (looser)", lb_bars=3, micro_stall_sec=10, micro_stall_pips=2)
run("+ micro-stall 15s/3pip", lb_bars=3, micro_stall_sec=15, micro_stall_pips=3)
run("+ micro-stall 5s/2pip (very tight)", lb_bars=3, micro_stall_sec=5, micro_stall_pips=2)

print()
print("--- F) SESSION OVERLAP only (broker 15-18) ---")
run("+ session overlap", lb_bars=3, require_session_overlap=True)

print()
print("--- G) COMBOS ---")
run("+ structure + wide UHV", lb_bars=3, require_structure=True, require_wide_uhv=True)
run("+ structure + POC33 + wide UHV", lb_bars=3, require_structure=True, require_poc33=True, require_wide_uhv=True)
run("+ structure + micro-stall 10s/3pip", lb_bars=3, require_structure=True, micro_stall_sec=10, micro_stall_pips=3)
run("REPORT FULL: structure + POC33 + wide + delta + micro-stall",
    lb_bars=3, require_structure=True, require_poc33=True, require_wide_uhv=True,
    require_pseudo_delta=True, micro_stall_sec=10, micro_stall_pips=3)
