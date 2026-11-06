"""fvg_engulfing_test.py — test SMC-style filter chain layered on Shano-Zee.

Theory:
  1. HTF uptrend (price above M15 EMA-21)
  2. Valid retracement (recent pullback)
  3. Price touched higher-TF Fair Value Gap (FVG)
  4. Reversal signal: trigger candle is engulfing in trend direction
  → high-probability buy setup (mirror for sell)

FVG (Fair Value Gap) on M15:
  Bullish FVG: 3-candle pattern where bar[i-2].low > bar[i].high
    → zone = [bar[i].high, bar[i-2].low] is "imbalance"
  Bearish FVG: bar[i-2].high < bar[i].low
    → zone = [bar[i-2].high, bar[i].low]

"Touched FVG" = recent price (last K minutes) entered the FVG zone.

Engulfing on 1-min:
  Bullish: trigger close > prev open AND trigger open < prev close
  Bearish: trigger close < prev open AND trigger open > prev close
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, get_emas, compute_ema,
)

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
PROBE_LOTS = 0.01
HORIZON_SEC = 600


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


def detect_fvgs(tf_bars, lookback=20):
    """Return list of (idx, kind, zone_low, zone_high) for FVGs in last `lookback` bars.
    kind = 1 (bullish) or -1 (bearish)."""
    fvgs = []
    n = len(tf_bars)
    start = max(2, n - lookback)
    for i in range(start, n):
        prev = tf_bars[i-2]; cur = tf_bars[i]
        # Bullish FVG: prev.low > cur.high → gap up zone
        if prev[3] > cur[2]:
            fvgs.append((i, 1, cur[2], prev[3]))
        # Bearish FVG: prev.high < cur.low → gap down zone
        if prev[2] < cur[3]:
            fvgs.append((i, -1, prev[2], cur[3]))
    return fvgs


def has_touched_fvg(when, dir_sign, tf_bars, tf_idx_map, fvg_lookback=20, touch_lookback_min=30, tf_min=15):
    """True if the trade direction's FVG was recently touched."""
    anchor = when.minute - (when.minute % tf_min)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    cur_idx = tf_idx_map.get(bm)
    if cur_idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf_min * d)
            cur_idx = tf_idx_map.get(t)
            if cur_idx is not None: break
    if cur_idx is None: return False
    fvgs = detect_fvgs(tf_bars[:cur_idx + 1], fvg_lookback)
    if not fvgs: return False
    # Filter FVGs by direction (bullish FVG for buy, bearish FVG for sell)
    relevant = [f for f in fvgs if f[1] == dir_sign]
    if not relevant: return False
    # Check if recent price (last touch_lookback_min minutes) entered any FVG zone
    touch_window_start = when - timedelta(minutes=touch_lookback_min)
    # Use 1-min bars for tighter price tracking — would need bars_1m... let's use TF bars
    for f in relevant:
        f_idx, kind, zlo, zhi = f
        # Check bars between f_idx (after FVG formed) and cur_idx
        for k in range(f_idx + 1, cur_idx + 1):
            bar = tf_bars[k]
            if bar[0] < touch_window_start: continue  # too old
            # Did this bar's range overlap the FVG zone?
            if bar[3] <= zhi and bar[2] >= zlo:
                return True
    return False


def is_engulfing(bars_1m, trigger_idx, dir_sign):
    """Trigger bar engulfs previous bar's body in direction."""
    if trigger_idx < 1: return False
    cur = bars_1m[trigger_idx]
    prev = bars_1m[trigger_idx - 1]
    cur_o = cur[1]; cur_c = cur[4]
    prev_o = prev[1]; prev_c = prev[4]
    if dir_sign == 1:  # bullish engulfing: prev was bear, cur is bull and engulfs
        if prev_c >= prev_o: return False  # prev must be bear
        if cur_c <= cur_o: return False    # cur must be bull
        return cur_c > prev_o and cur_o < prev_c
    else:  # bearish engulfing
        if prev_c <= prev_o: return False
        if cur_c >= cur_o: return False
        return cur_c < prev_o and cur_o > prev_c


def htf_trend_aligned(when, dir_sign, ema_15m, bar_idx_15m, tf_min=15):
    """Price above M15 EMA-21 for buys / below for sells."""
    anchor = when.minute - (when.minute % tf_min)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_15m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf_min * d)
            idx = bar_idx_15m.get(t)
            if idx is not None: break
    if idx is None or idx >= len(ema_15m) or ema_15m[idx] is None: return False
    return True  # placeholder; price comparison done in caller


def has_recent_pullback(bars_1m, trigger_idx, dir_sign, lookback=10):
    """Recent pullback: in last N 1-min bars, at least 2 opposite-color candles."""
    start = max(0, trigger_idx - lookback)
    opposite = 0
    for k in range(start, trigger_idx):
        bar = bars_1m[k]
        is_bull = bar[4] > bar[1]
        if dir_sign == 1 and not is_bull: opposite += 1
        if dir_sign == -1 and is_bull: opposite += 1
    return opposite >= 2


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


def run(label, *, require_htf_trend=False, require_pullback=False,
         require_fvg_touch=False, require_engulfing=False,
         fvg_tf=15, fvg_lookback=20, pullback_lookback=10,
         touch_lookback_min=30):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    bars_15m = aggregate_to_tf(bars_1m, 15)
    bar_idx_15m = {b[0]: i for i, b in enumerate(bars_15m)}
    closes_15m = [b[4] for b in bars_15m]
    ema_21_15m = compute_ema(closes_15m, 21)

    bars_5m = aggregate_to_tf(bars_1m, 5)
    bar_idx_5m = {b[0]: i for i, b in enumerate(bars_5m)}

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

        # ── NEW SMC FILTERS ──
        if require_htf_trend:
            anchor = entry_time.minute - (entry_time.minute % 15)
            bm15 = entry_time.replace(minute=anchor, second=0, microsecond=0)
            idx15 = bar_idx_15m.get(bm15)
            if idx15 is None:
                for d in range(1, 10):
                    t15 = bm15 - timedelta(minutes=15 * d)
                    idx15 = bar_idx_15m.get(t15)
                    if idx15 is not None: break
            if idx15 is None or idx15 >= len(ema_21_15m) or ema_21_15m[idx15] is None: continue
            if dir_sign == 1 and entry_price <= ema_21_15m[idx15]: continue
            if dir_sign == -1 and entry_price >= ema_21_15m[idx15]: continue

        if require_pullback:
            if not has_recent_pullback(bars_1m, trigger_idx, dir_sign, pullback_lookback): continue

        if require_fvg_touch:
            if fvg_tf == 15:
                tf_bars = bars_15m; tf_map = bar_idx_15m
            else:
                tf_bars = bars_5m; tf_map = bar_idx_5m
            if not has_touched_fvg(entry_time, dir_sign, tf_bars, tf_map,
                                    fvg_lookback, touch_lookback_min, fvg_tf): continue

        if require_engulfing:
            if not is_engulfing(bars_1m, trigger_idx, dir_sign): continue

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
print("SMC THEORY: HTF trend + retracement + FVG touch + engulfing entry")
print("Base: descending ladder 0.70->0.10, fearI=$100, max 7 bursts, hour+2min trend+skipFast+UHV(20)")
print("=" * 180)
print()
print("--- BASELINE ---")
run("BASELINE Shano-Zee descending")

print()
print("--- INDIVIDUAL FILTERS ---")
run("HTF trend (M15 21-EMA aligned)", require_htf_trend=True)
run("Recent pullback (>=2 opposite color in last 10 bars)", require_pullback=True)
run("FVG touch (M15, lookback=20, touched in last 30min)", require_fvg_touch=True, fvg_tf=15)
run("FVG touch (M5, lookback=20, touched in last 30min)", require_fvg_touch=True, fvg_tf=5)
run("Engulfing trigger candle", require_engulfing=True)

print()
print("--- COMBOS (theory chain) ---")
run("HTF trend + pullback", require_htf_trend=True, require_pullback=True)
run("HTF trend + pullback + engulfing", require_htf_trend=True, require_pullback=True, require_engulfing=True)
run("HTF trend + pullback + M15 FVG touch", require_htf_trend=True, require_pullback=True, require_fvg_touch=True, fvg_tf=15)
run("HTF trend + pullback + M5 FVG touch", require_htf_trend=True, require_pullback=True, require_fvg_touch=True, fvg_tf=5)
run("FULL THEORY: HTF + pullback + FVG + engulfing (M15 FVG)",
    require_htf_trend=True, require_pullback=True, require_fvg_touch=True, require_engulfing=True, fvg_tf=15)
run("FULL THEORY: HTF + pullback + FVG + engulfing (M5 FVG)",
    require_htf_trend=True, require_pullback=True, require_fvg_touch=True, require_engulfing=True, fvg_tf=5)
print()
print("--- TUNED ---")
for tlb in [15, 30, 60, 120]:
    run(f"HTF + pullback + M5 FVG (touch_lookback={tlb}min)",
        require_htf_trend=True, require_pullback=True, require_fvg_touch=True, fvg_tf=5, touch_lookback_min=tlb)
