"""hidden_div_rsi_test.py — backtest hidden divergence + RSI retest as trend-continuation filters.

THEORY:
  - Hidden divergence = trend CONTINUATION (opposite of regular divergence)
    * Bullish: price higher-low + RSI lower-low → uptrend's strength still hidden, continues UP
    * Bearish: price lower-high + RSI higher-high → downtrend continues DOWN
  - RSI Retest of 50-line:
    * Bullish: RSI was >50, pulled back to 45-55, bouncing up → uptrend continues
    * Bearish: RSI was <50, pulled up to 45-55, dropping → downtrend continues

For Shano-Zee: these confirm "this UHV breakout is part of a continuing trend, not a one-off"
Probes in the direction of confirmed continuation should have higher win rate.

Tested:
  A) RSI(14) hidden divergence on 1-min bars
  B) RSI retest of 50 on 1-min bars
  C) Same on 5-min bars (HTF perspective)
  D) Combined with current BIG STACK
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
    """Standard Wilder's RSI."""
    n = len(closes)
    rsi = [None] * n
    if n < period + 1: return rsi
    gains, losses = [], []
    for i in range(1, n):
        ch = closes[i] - closes[i-1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    # Initial averages (SMA seed)
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    rs = avg_g / avg_l if avg_l > 0 else 999
    rsi[period] = 100 - (100 / (1 + rs))
    # Wilder smoothing
    for i in range(period + 1, n):
        avg_g = (avg_g * (period - 1) + gains[i-1]) / period
        avg_l = (avg_l * (period - 1) + losses[i-1]) / period
        rs = avg_g / avg_l if avg_l > 0 else 999
        rsi[i] = 100 - (100 / (1 + rs))
    return rsi


def find_swing_lows(values, idx, lookback=15, min_distance=3):
    """Return indices of recent swing lows in values[max(0,idx-lookback):idx+1]."""
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
    """Detect bullish hidden div: price higher-low + RSI lower-low (in that swing)."""
    p_lows = find_swing_lows(closes, idx, lookback)
    r_lows = find_swing_lows(rsi, idx, lookback)
    if len(p_lows) < 2 or len(r_lows) < 2: return False
    # Take last two of each
    p1, p2 = p_lows[-2], p_lows[-1]  # p1 earlier, p2 later
    r1, r2 = r_lows[-2], r_lows[-1]
    # Must be roughly same swings (within 3 bars)
    if abs(p2 - r2) > 3 or abs(p1 - r1) > 3: return False
    # Bullish hidden: latest price low HIGHER, latest RSI low LOWER
    if closes[p2] > closes[p1] and rsi[r2] < rsi[r1]:
        return True
    return False


def has_bearish_hidden_div(closes, rsi, idx, lookback=15):
    p_hi = find_swing_highs(closes, idx, lookback)
    r_hi = find_swing_highs(rsi, idx, lookback)
    if len(p_hi) < 2 or len(r_hi) < 2: return False
    p1, p2 = p_hi[-2], p_hi[-1]
    r1, r2 = r_hi[-2], r_hi[-1]
    if abs(p2 - r2) > 3 or abs(p1 - r1) > 3: return False
    # Bearish hidden: latest price high LOWER, latest RSI high HIGHER
    if closes[p2] < closes[p1] and rsi[r2] > rsi[r1]:
        return True
    return False


def has_bullish_rsi_retest(rsi, idx, retest_lookback=10):
    """RSI was >55 in recent bars, pulled back to 45-55, now > 50 (rising back)."""
    if idx < retest_lookback or rsi[idx] is None: return False
    if rsi[idx] < 50 or rsi[idx] > 60: return False  # currently near 50 from above
    # Was it >55 in lookback?
    recent = [rsi[i] for i in range(idx - retest_lookback, idx) if rsi[i] is not None]
    if not recent: return False
    return max(recent) > 55  # pulled back from above


def has_bearish_rsi_retest(rsi, idx, retest_lookback=10):
    if idx < retest_lookback or rsi[idx] is None: return False
    if rsi[idx] > 50 or rsi[idx] < 40: return False
    recent = [rsi[i] for i in range(idx - retest_lookback, idx) if rsi[i] is not None]
    if not recent: return False
    return min(recent) < 45  # pulled up from below


# ── Sim infra (same as descending_ladder_test) ──
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


def run(label, *, hidden_div=False, rsi_retest=False, rsi_period=14, lookback=15):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    closes_1m = [b[4] for b in bars_1m]
    rsi_1m = compute_rsi(closes_1m, rsi_period)
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
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # NEW filters
        if hidden_div:
            if dir_sign == 1:
                if not has_bullish_hidden_div(closes_1m, rsi_1m, trigger_idx, lookback): continue
            else:
                if not has_bearish_hidden_div(closes_1m, rsi_1m, trigger_idx, lookback): continue
        if rsi_retest:
            if dir_sign == 1:
                if not has_bullish_rsi_retest(rsi_1m, trigger_idx): continue
            else:
                if not has_bearish_rsi_retest(rsi_1m, trigger_idx): continue

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

    print(f"  {label:<60}chains={n:<3}mains={len(all_mains):<4}WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing}  worst=${big_loss:+.2f}")


print("=" * 140)
print("HIDDEN DIVERGENCE + RSI RETEST backtest")
print("Base: descending ladder 0.70→0.10, fearI=$100, max 7 bursts, hour+2min trend+skipFast+UHV(20)")
print("=" * 140)
print()

print("--- BASELINE (no hidden div, no RSI retest) ---")
run("BASELINE Shano-Zee descending")

print()
print("--- HIDDEN DIVERGENCE FILTER (dir-aware) ---")
print("Bullish hidden div for buys (price higher-low + RSI lower-low) — trend continues up")
print("Bearish hidden div for sells (price lower-high + RSI higher-high) — trend continues down")
for lb in [10, 15, 20, 25]:
    run(f"hidden div (lookback={lb} bars, RSI(14))", hidden_div=True, lookback=lb)

print()
print("--- RSI RETEST OF 50-LINE ---")
print("Bullish: RSI was >55 recently, now 50-60, rising = uptrend continues")
print("Bearish: RSI was <45 recently, now 40-50, dropping = downtrend continues")
run("RSI(14) retest of 50", rsi_retest=True)

print()
print("--- COMBINED ---")
run("RSI hidden div (lb=15) + RSI retest", hidden_div=True, rsi_retest=True, lookback=15)
run("RSI hidden div (lb=20) + RSI retest", hidden_div=True, rsi_retest=True, lookback=20)

print()
print("--- DIFFERENT RSI PERIODS ---")
for p in [9, 14, 21]:
    run(f"hidden div (lb=15, RSI({p}))", hidden_div=True, lookback=15, rsi_period=p)
