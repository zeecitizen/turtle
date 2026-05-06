"""multi_tf_rsi_test.py — RSI on 5-min/15-min as context filter or hidden div detector.

Tests two approaches:
  A) HIDDEN DIVERGENCE on M5 and M15 RSI (longer-window pattern)
     - Cleaner swings on higher TF; less M1 noise
  B) CONTEXT FILTER: just require RSI in a directional zone at probe time
     - For BUYS: M15 RSI must be above X (default 40) — bullish bias
     - For SELLS: M15 RSI must be below Y (default 60) — bearish bias
     - This is a CONTEXT signal, not a pattern signal

Tested on top of Shano-Zee descending ladder + UHV.
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

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
PROBE_LOTS = 0.01
HORIZON_SEC = 600


def compute_rsi(closes, period=14):
    n = len(closes)
    rsi = [None] * n
    if n < period + 1: return rsi
    gains, losses = [], []
    for i in range(1, n):
        ch = closes[i] - closes[i-1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rs = avg_g / avg_l if avg_l > 0 else 999
    rsi[period] = 100 - (100 / (1 + rs))
    for i in range(period + 1, n):
        avg_g = (avg_g * (period - 1) + gains[i-1]) / period
        avg_l = (avg_l * (period - 1) + losses[i-1]) / period
        rs = avg_g / avg_l if avg_l > 0 else 999
        rsi[i] = 100 - (100 / (1 + rs))
    return rsi


def aggregate_to_tf(bars_1m, minutes):
    out = []
    cur = None; o = h = l = c = None
    for b in bars_1m:
        dt, b_o, b_h, b_l, b_c = b[0], b[1], b[2], b[3], b[4]
        anchor = dt.minute - (dt.minute % minutes)
        bm = dt.replace(minute=anchor, second=0, microsecond=0)
        if cur is None:
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c
        elif bm != cur:
            out.append((cur, o, h, l, c))
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c
        else:
            if b_h > h: h = b_h
            if b_l < l: l = b_l
            c = b_c
    if cur is not None: out.append((cur, o, h, l, c))
    return out


def find_swing_lows(values, idx, lookback=15, min_distance=3):
    swings = []
    start = max(min_distance, idx - lookback)
    end = idx - min_distance
    for i in range(start, end + 1):
        if values[i] is None: continue
        is_low = True
        for k in range(1, min_distance + 1):
            lv = values[i-k]; rv = values[i+k]
            if lv is None or rv is None: is_low = False; break
            if lv <= values[i] or rv <= values[i]: is_low = False; break
        if is_low: swings.append(i)
    return swings


def find_swing_highs(values, idx, lookback=15, min_distance=3):
    swings = []
    start = max(min_distance, idx - lookback)
    end = idx - min_distance
    for i in range(start, end + 1):
        if values[i] is None: continue
        is_high = True
        for k in range(1, min_distance + 1):
            lv = values[i-k]; rv = values[i+k]
            if lv is None or rv is None: is_high = False; break
            if lv >= values[i] or rv >= values[i]: is_high = False; break
        if is_high: swings.append(i)
    return swings


def has_bullish_hidden_div(closes, rsi, idx, lookback=15):
    p_lows = find_swing_lows(closes, idx, lookback)
    r_lows = find_swing_lows(rsi, idx, lookback)
    if len(p_lows) < 2 or len(r_lows) < 2: return False
    p1, p2 = p_lows[-2], p_lows[-1]
    r1, r2 = r_lows[-2], r_lows[-1]
    if abs(p2 - r2) > 3 or abs(p1 - r1) > 3: return False
    return closes[p2] > closes[p1] and rsi[r2] < rsi[r1]


def has_bearish_hidden_div(closes, rsi, idx, lookback=15):
    p_hi = find_swing_highs(closes, idx, lookback)
    r_hi = find_swing_highs(rsi, idx, lookback)
    if len(p_hi) < 2 or len(r_hi) < 2: return False
    p1, p2 = p_hi[-2], p_hi[-1]
    r1, r2 = r_hi[-2], r_hi[-1]
    if abs(p2 - r2) > 3 or abs(p1 - r1) > 3: return False
    return closes[p2] < closes[p1] and rsi[r2] > rsi[r1]


def get_rsi_at(when, bar_idx_tf, rsi_arr, tf_min):
    anchor = when.minute - (when.minute % tf_min)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_tf.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf_min * d)
            idx = bar_idx_tf.get(t)
            if idx is not None: break
    if idx is None or idx >= len(rsi_arr) or rsi_arr[idx] is None: return None, None
    return rsi_arr[idx], idx


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
        pnl, exit_dt, exit_price = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price,
                                    ema_f, ema_s, bar_idx_2m,
                                    bars_1m, bar_idx_1m, uhv_lookback): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run(label, *, hidden_div_tf=None, hidden_div_lookback=15,
         context_min_buy=None, context_max_sell=None, context_tf_min=15,
         rsi_period=14):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    # Build TF bars + RSI as needed
    bars_5m = aggregate_to_tf(bars_1m, 5)
    bars_15m = aggregate_to_tf(bars_1m, 15)
    bar_idx_5m = {b[0]: i for i, b in enumerate(bars_5m)}
    bar_idx_15m = {b[0]: i for i, b in enumerate(bars_15m)}
    rsi_5m = compute_rsi([b[4] for b in bars_5m], rsi_period)
    rsi_15m = compute_rsi([b[4] for b in bars_15m], rsi_period)

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
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # NEW filters
        if hidden_div_tf is not None:
            if hidden_div_tf == 5:
                tf_bars = bars_5m; tf_idx_map = bar_idx_5m; tf_rsi = rsi_5m
            elif hidden_div_tf == 15:
                tf_bars = bars_15m; tf_idx_map = bar_idx_15m; tf_rsi = rsi_15m
            else:
                continue
            tf_closes = [b[4] for b in tf_bars]
            anchor = entry_time.minute - (entry_time.minute % hidden_div_tf)
            bm = entry_time.replace(minute=anchor, second=0, microsecond=0)
            tf_idx = tf_idx_map.get(bm)
            if tf_idx is None:
                for d in range(1, 30):
                    bm2 = bm - timedelta(minutes=hidden_div_tf * d)
                    tf_idx = tf_idx_map.get(bm2)
                    if tf_idx is not None: break
            if tf_idx is None: continue
            if dir_sign == 1:
                if not has_bullish_hidden_div(tf_closes, tf_rsi, tf_idx, hidden_div_lookback): continue
            else:
                if not has_bearish_hidden_div(tf_closes, tf_rsi, tf_idx, hidden_div_lookback): continue

        # Context filter (M15 by default)
        if context_min_buy is not None or context_max_sell is not None:
            if context_tf_min == 15:
                tf_idx_map = bar_idx_15m; tf_rsi = rsi_15m
            elif context_tf_min == 5:
                tf_idx_map = bar_idx_5m; tf_rsi = rsi_5m
            else:
                continue
            rsi_val, _ = get_rsi_at(entry_time, tf_idx_map, tf_rsi, context_tf_min)
            if rsi_val is None: continue
            if dir_sign == 1 and context_min_buy is not None:
                if rsi_val < context_min_buy: continue
            if dir_sign == -1 and context_max_sell is not None:
                if rsi_val > context_max_sell: continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m)
        chains.append(chain)

    n = len(chains); all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)

    print(f"  {label:<70}chains={n:<3}mains={len(all_mains):<4}WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing}  worst=${big_loss:+.2f}")


print("=" * 180)
print("MULTI-TIMEFRAME RSI tests on Shano-Zee descending")
print("Base: probeConfirm=0.45, fearI=$100, descending 0.70->0.10, max 7 bursts, hour+2min trend+skipFast+UHV(20)")
print("=" * 180)
print()
print("--- BASELINE ---")
run("BASELINE Shano-Zee descending")

print()
print("--- A1) HIDDEN DIVERGENCE on M5 RSI ---")
for lb in [10, 15, 20]:
    run(f"M5 hidden div (lookback={lb})", hidden_div_tf=5, hidden_div_lookback=lb)

print()
print("--- A2) HIDDEN DIVERGENCE on M15 RSI ---")
for lb in [10, 15, 20]:
    run(f"M15 hidden div (lookback={lb})", hidden_div_tf=15, hidden_div_lookback=lb)

print()
print("--- B) CONTEXT FILTER: M15 RSI > X for buys, < (100-X) for sells ---")
for thr_buy in [30, 35, 40, 45, 50]:
    thr_sell = 100 - thr_buy
    run(f"M15 RSI buys >= {thr_buy}, sells <= {thr_sell}",
        context_min_buy=thr_buy, context_max_sell=thr_sell, context_tf_min=15)

print()
print("--- B2) CONTEXT FILTER: M5 RSI > X for buys, < (100-X) for sells ---")
for thr_buy in [35, 40, 45, 50]:
    thr_sell = 100 - thr_buy
    run(f"M5 RSI buys >= {thr_buy}, sells <= {thr_sell}",
        context_min_buy=thr_buy, context_max_sell=thr_sell, context_tf_min=5)

print()
print("--- B3) ASYMMETRIC: only require RSI bias for ONE direction ---")
run("M15 RSI buys >= 50 (no sell req)", context_min_buy=50, context_max_sell=None)
run("M15 RSI buys >= 55 (no sell req)", context_min_buy=55, context_max_sell=None)
run("M15 RSI sells <= 50 (no buy req)", context_min_buy=None, context_max_sell=50)
run("M15 RSI sells <= 45 (no buy req)", context_min_buy=None, context_max_sell=45)

print()
print("--- COMBOS (best context + hidden div) ---")
run("M15 RSI buys>=40 sells<=60 + M15 hidden div (lb=15)",
    context_min_buy=40, context_max_sell=60, context_tf_min=15,
    hidden_div_tf=15, hidden_div_lookback=15)
run("M15 RSI buys>=45 sells<=55 (tighter)",
    context_min_buy=45, context_max_sell=55, context_tf_min=15)
