"""pdf_filters_test.py — backtest the PDF theories + user's selling-background theory.

Tests on 172-probe dataset, descending ladder 0.70→0.10, fearI=$100, maxBurst=7.

Filters tested (one at a time, layered on Shano-Zee winning combo):
  A) SELLING BACKGROUND (user's theory): UHV's prior 3-5 candles also high volume
  B) STRONG BODY: UHV body ≥ X% of range (40, 50, 60, 70)
  C) BODY > WICK: UHV body > total wicks
  D) BREAKOUT VOLUME UPTICK: trigger vol > avg(last 3-5)
  E) HOLD 50% UHV BODY: price holds 50% UHV body — test would need post-entry sim
  F) CLUSTER COMPRESSION: 3+ low-vol candles between UHV and trigger
  G) UHV WIDE BODY (PDF #2): UHV range > X × ATR(14)
  H) NO LONG WICK (PDF #6): UHV upper wick (for sell) or lower wick (for buy) < X% of range
  I) COMBOS of the best individuals
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

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
    """Return (uhv_bar, uhv_idx_in_bars_1m, trigger_idx) or (None, None, None)."""
    bm = when.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < lookback + 1: return None, None, None
    trigger_idx = idx - 1  # bar before entry
    lookback_bars = bars_1m[max(0, trigger_idx - lookback):trigger_idx]
    if not lookback_bars: return None, None, None
    uhv = max(lookback_bars, key=lambda b: b[5])
    # Find uhv_idx in full bars_1m list
    uhv_global_idx = bars_1m.index(uhv)  # find returns first match
    return uhv, uhv_global_idx, trigger_idx


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m,
                         bars_1m, bar_idx_1m, uhv_lookback=20):
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
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP):
    if not ticks: return 0.0, None, entry, "no_data"
    peak = 0.0; last_profit = 0.0; last_dt = ticks[-1][0]; last_price = entry
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else: profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last_profit = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return round(profit, 2), dt, cur, "fearIdeal"
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur, "trail"
    return round(last_profit, 2), last_dt, last_price, "horizon"


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
              fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
              ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
              uhv_lookback=20, horizon_sec=HORIZON_SEC):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price, reason = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl, reason))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price,
                                    ema_f, ema_s, bar_idx_2m,
                                    bars_1m, bar_idx_1m, uhv_lookback): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run_with_extra_filter(label, extra_predicate=None):
    """extra_predicate(uhv_bar, trigger_bar, lookback_bars, atr_val) -> bool (True = keep)."""
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    atr = compute_atr(bars_1m, 14)
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

        # Standard Shano-Zee filters
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        # UHV breakout
        uhv, uhv_idx, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None or trigger_idx is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # EXTRA FILTER from PDF/teacher theories
        if extra_predicate:
            atr_val = atr[trigger_idx] if trigger_idx < len(atr) else None
            lookback_bars = bars_1m[max(0, trigger_idx - 20):trigger_idx]
            if not extra_predicate(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
                continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m)
        chains.append(chain)

    n_chains = len(chains)
    all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = [m for m in all_mains if m[1] > 0]
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing_chains = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)

    print(f"  {label:<70}chains={n_chains:<3}mains={len(all_mains):<4}WR={len(wins)/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing_chains={losing_chains}  worst=${big_loss:+.2f}")
    return total, n_chains


print("=" * 180)
print("PDF & Teacher's Theories — backtest each filter on top of Shano-Zee descending ladder")
print("Base: probeConfirm=0.45, trail=$12/$4, fearI=$100, maxBurst=7, descending 0.70→0.10")
print("=" * 180)
print()

# Baseline (no extra filter)
print("--- BASELINE (descending ladder, no extra PDF filter) ---")
run_with_extra_filter("BASELINE: Shano-Zee descending only")

print()
print("--- A) SELLING BACKGROUND (your teacher's theory) ---")
print("UHV's prior N candles also high volume (avg vol >= X * uhv vol)")
def selling_bg(N, ratio):
    def f(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
        # Look at N bars BEFORE the UHV bar
        if uhv_idx < N: return False
        prior_bars = bars_1m[uhv_idx - N:uhv_idx]
        if not prior_bars: return False
        avg_prior_vol = sum(b[5] for b in prior_bars) / len(prior_bars)
        return avg_prior_vol >= ratio * uhv[5]
    return f

for N in [3, 5, 7]:
    for ratio in [0.40, 0.50, 0.60, 0.70]:
        run_with_extra_filter(f"selling bg: prior {N} bars avg vol >= {ratio:.0%} UHV vol",
                              selling_bg(N, ratio))
    print()

print("--- B) STRONG UHV BODY (PDF #2 + #6) ---")
print("UHV body must be ≥ X% of range")
def body_strength(min_pct):
    def f(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
        body = abs(uhv[4] - uhv[1])
        rng = uhv[2] - uhv[3]
        return body >= min_pct * rng
    return f

for pct in [0.40, 0.50, 0.60, 0.70]:
    run_with_extra_filter(f"UHV body >= {pct:.0%} of range", body_strength(pct))

print()
print("--- C) BODY > WICK (your additional rule) ---")
print("UHV body > combined wicks")
def body_gt_wick(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
    body = abs(uhv[4] - uhv[1])
    upper_wick = uhv[2] - max(uhv[1], uhv[4])
    lower_wick = min(uhv[1], uhv[4]) - uhv[3]
    return body > (upper_wick + lower_wick)

run_with_extra_filter("UHV body > total wicks", body_gt_wick)

print()
print("--- D) BREAKOUT VOLUME UPTICK (PDF #1) ---")
print("Trigger candle volume > avg(last N candles before trigger)")
def brk_vol_uptick(N, mult):
    def f(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
        # bars_1m[trigger_idx - N:trigger_idx] would give N bars before trigger
        # We have lookback_bars = 20 bars before trigger
        if len(lookback_bars) < N: return False
        recent = lookback_bars[-N:]
        avg = sum(b[5] for b in recent) / N
        return trigger[5] >= mult * avg
    return f

for N in [3, 5]:
    for mult in [1.0, 1.2, 1.5, 2.0]:
        run_with_extra_filter(f"trigger vol >= {mult:.1f}× avg(prev {N})", brk_vol_uptick(N, mult))
    print()

print("--- G) UHV WIDE BODY (PDF #2): UHV range > X × ATR(14) ---")
def uhv_wide(mult):
    def f(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
        if atr_val is None or atr_val == 0: return False
        rng = uhv[2] - uhv[3]
        return rng >= mult * atr_val
    return f

for mult in [1.0, 1.5, 2.0, 2.5]:
    run_with_extra_filter(f"UHV range >= {mult:.1f}× ATR(14)", uhv_wide(mult))

print()
print("--- H) NO LONG WICK (PDF #6) ---")
print("Direction-aware: for SELL probes, UHV upper wick must be small (no absorption above);")
print("for BUY probes, UHV lower wick must be small")
def no_long_wick(max_pct):
    def f(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
        rng = uhv[2] - uhv[3]
        if rng <= 0: return False
        upper_wick = uhv[2] - max(uhv[1], uhv[4])
        lower_wick = min(uhv[1], uhv[4]) - uhv[3]
        # Check both wicks regardless of direction
        return upper_wick <= max_pct * rng and lower_wick <= max_pct * rng
    return f

for pct in [0.20, 0.30, 0.40, 0.50]:
    run_with_extra_filter(f"both UHV wicks <= {pct:.0%} of range", no_long_wick(pct))

print()
print("--- I) COMBO: Best filter + ladder ---")
# Test combined best filters
def combo1(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
    body = abs(uhv[4] - uhv[1])
    rng = uhv[2] - uhv[3]
    if rng <= 0: return False
    if body < 0.5 * rng: return False  # body >= 50% of range
    upper_wick = uhv[2] - max(uhv[1], uhv[4])
    lower_wick = min(uhv[1], uhv[4]) - uhv[3]
    if body <= upper_wick + lower_wick: return False  # body > wicks
    return True

run_with_extra_filter("COMBO: body>=50% AND body>wicks", combo1)

def combo2(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
    if not combo1(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m): return False
    # Plus selling background
    N = 5
    if uhv_idx < N: return False
    prior = bars_1m[uhv_idx - N:uhv_idx]
    avg_prior = sum(b[5] for b in prior) / max(len(prior), 1)
    return avg_prior >= 0.50 * uhv[5]

run_with_extra_filter("COMBO: body>=50% + body>wicks + selling bg(5/50%)", combo2)

def combo3(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m):
    if not combo1(uhv, trigger, lookback_bars, atr_val, uhv_idx, bars_1m): return False
    # Plus trigger volume uptick vs prior 5
    if len(lookback_bars) < 5: return False
    recent = lookback_bars[-5:]
    avg = sum(b[5] for b in recent) / 5
    return trigger[5] >= 1.0 * avg  # trigger at least matches recent avg

run_with_extra_filter("COMBO: body>=50% + body>wicks + brk vol >= avg(5)", combo3)
