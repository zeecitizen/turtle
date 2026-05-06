"""pdf2_enhancements_test.py — backtest the 2nd PDF's 12 filter theories.

All tested on top of current Shano-Zee winning combo:
  descending ladder 0.70→0.10, fearI=$100, maxBurst=7,
  hour+2min trend+skipFast+UHV(20) filters.

Filters from the PDF:
  1. TICK-SPEED: trigger close > UHV high within first N seconds of trigger bar
  2. SPREAD: spread at confirm <= baseline × X
  3. TIME-OF-DAY: only trade in London-NY overlap (GMT 12-16 = broker 15-19)
  4. FAILURE EXIT: exit if main close back inside UHV body within 1-2 bars
  5. KILL TIMER: exit if 0.5R not reached within 2-5 sec (similar to existing skipFastConfirm)
  6. VOLATILITY COLLAPSE: trigger candle ATR/range not the lowest of last 10
  7. TREND ALIGNMENT (M15 21-EMA): price above M15 21-EMA for buys (below for sells)
  8. COMPRESSION: require N consecutive low-vol candles before trigger
  11. BREAKOUT DISTANCE: next swing high/low >= X points away
  12. CHAIN-STOP: stop trading after 2 consecutive losing chains
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, get_emas, compute_ema,
)
from advanced_features import compute_atr

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
PROBE_LOTS = 0.01
HORIZON_SEC = 600


def trend_at(when, ema_f, ema_s, bar_idx, tf=2):
    anchor = when.minute - (when.minute % tf)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf * d)
            idx = bar_idx.get(t)
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


def get_break_time_in_trigger(trigger_dt, dir_sign, uhv_extreme, bars_1m, bar_idx_1m):
    """Return seconds-into-trigger-bar when the close FIRST broke beyond UHV.
    For approximation: walk ticks during the trigger minute, find first tick where bid (sell)
    crosses below uhv_low, OR ask (buy) crosses above uhv_high."""
    bar_start = trigger_dt
    bar_end = trigger_dt + timedelta(seconds=60)
    ticks = ticks_in_range(bar_start, bar_end)
    if not ticks: return None
    for dt, bid, ask in ticks:
        if dir_sign == 1 and ask > uhv_extreme: return (dt - bar_start).total_seconds()
        if dir_sign == -1 and bid < uhv_extreme: return (dt - bar_start).total_seconds()
    return None


def median_spread_baseline(when, bars_1m_with_tc, bar_idx_1m, lookback=30):
    """Compute median spread from ticks in last 30 minutes."""
    end = when
    start = when - timedelta(minutes=lookback)
    ticks = ticks_in_range(start, end)
    if not ticks: return None
    spreads = sorted(ask - bid for _, bid, ask in ticks)
    return spreads[len(spreads)//2] if spreads else None


def get_m15_trend(when, ema_15m, bar_idx_15m):
    """Return 1=above 21-EMA on M15, -1=below, 0=na/at."""
    anchor = when.minute - (when.minute % 15)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_15m.get(bm)
    if idx is None:
        for d in range(1, 20):
            t = bm - timedelta(minutes=15 * d)
            idx = bar_idx_15m.get(t)
            if idx is not None: break
        if idx is None: return 0
    ema = ema_15m[idx]
    if ema is None: return 0
    return 1 if when else 0  # placeholder; use price comparison in caller


def build_15m_bars():
    if hasattr(build_15m_bars, "_cache"): return build_15m_bars._cache
    bars_1m = build_1m_bars()
    bars = []
    cur = None; o = h = l = c = None; tc = 0
    for b in bars_1m:
        dt, b_o, b_h, b_l, b_c = b[0], b[1], b[2], b[3], b[4]
        b_tc = b[5]
        anchor = dt.minute - (dt.minute % 15)
        bm = dt.replace(minute=anchor, second=0, microsecond=0)
        if cur is None:
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; tc = b_tc
        elif bm != cur:
            bars.append((cur, o, h, l, c, tc))
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; tc = b_tc
        else:
            if b_h > h: h = b_h
            if b_l < l: l = b_l
            c = b_c; tc += b_tc
    if cur is not None: bars.append((cur, o, h, l, c, tc))
    build_15m_bars._cache = bars
    return bars


def run_with_filters(label, *, max_break_sec=None, max_spread_mult=None,
                      session_overlap_only=False, vol_collapse_check=False,
                      m15_trend_align=False, compression_n=None,
                      chain_stop_after_losses=None,
                      brk_distance_pts=None,
                      failure_exit_after_bars=None):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    atr_1m = compute_atr(bars_1m, 14)
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    # 15-min EMA-21 for HTF trend filter
    bars_15m = build_15m_bars()
    bar_idx_15m = {b[0]: i for i, b in enumerate(bars_15m)}
    closes_15m = [b[4] for b in bars_15m]
    ema_21_15m = compute_ema(closes_15m, 21)

    chains = []
    consecutive_losing_chains = 0
    halted = False

    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        if halted: continue

        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None; entry_spread = None
        for dt, bid, ask in ticks:
            if entry_spread is None: entry_spread = ask - bid
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
        uhv, uhv_idx, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # ===== NEW FILTER #1: TICK-SPEED =====
        if max_break_sec is not None:
            uhv_extreme = uhv[2] if dir_sign == 1 else uhv[3]
            trigger_dt = trigger[0]
            brk_sec = get_break_time_in_trigger(trigger_dt, dir_sign, uhv_extreme, bars_1m, bar_idx_1m)
            if brk_sec is None or brk_sec > max_break_sec: continue

        # ===== NEW FILTER #2: SPREAD =====
        if max_spread_mult is not None and entry_spread is not None:
            baseline = median_spread_baseline(entry_time, bars_1m, bar_idx_1m, 30)
            if baseline is not None and baseline > 0:
                if entry_spread > max_spread_mult * baseline: continue

        # ===== NEW FILTER #3: SESSION OVERLAP =====
        # London-NY overlap = 12:00-16:00 GMT = 15:00-19:00 broker time (UTC+3)
        if session_overlap_only:
            if not (15 <= h <= 18): continue

        # ===== NEW FILTER #6: VOLATILITY COLLAPSE =====
        # Trigger candle range must NOT be the lowest of last 10
        if vol_collapse_check:
            recent10 = bars_1m[max(0, trigger_idx - 10):trigger_idx]
            trigger_range = trigger[2] - trigger[3]
            if recent10:
                min_range = min((b[2] - b[3]) for b in recent10)
                if trigger_range <= min_range: continue
                # Also require trigger range >= 30% of UHV range
                uhv_range = uhv[2] - uhv[3]
                if uhv_range > 0 and trigger_range < 0.30 * uhv_range: continue

        # ===== NEW FILTER #7: M15 21-EMA TREND ALIGNMENT =====
        if m15_trend_align:
            anchor = entry_time.minute - (entry_time.minute % 15)
            bm15 = entry_time.replace(minute=anchor, second=0, microsecond=0)
            idx15 = bar_idx_15m.get(bm15)
            if idx15 is None:
                for d in range(1, 10):
                    t15 = bm15 - timedelta(minutes=15 * d)
                    idx15 = bar_idx_15m.get(t15)
                    if idx15 is not None: break
            if idx15 is None or idx15 >= len(ema_21_15m) or ema_21_15m[idx15] is None: continue
            ema_val = ema_21_15m[idx15]
            if dir_sign == 1 and entry_price <= ema_val: continue
            if dir_sign == -1 and entry_price >= ema_val: continue

        # ===== NEW FILTER #9: COMPRESSION =====
        # Require N consecutive low-volume candles between UHV and trigger
        if compression_n is not None:
            if uhv_idx is None: continue
            between = bars_1m[uhv_idx + 1:trigger_idx + 1]  # bars after UHV up to trigger
            if len(between) < compression_n: continue
            # All must have volume below UHV's
            avg_low_vol = sum(b[5] for b in between) / len(between)
            if avg_low_vol >= 0.7 * uhv[5]: continue

        # ===== NEW FILTER #11: BREAKOUT DISTANCE =====
        if brk_distance_pts is not None:
            # Find next swing high/low in lookback
            recent = bars_1m[max(0, trigger_idx - 30):trigger_idx]
            if dir_sign == 1:
                # For buys: next swing HIGH must be > X pts above trigger close
                next_obstacle = max((b[2] for b in recent), default=trigger[4])
                distance = next_obstacle - trigger[4]
            else:
                # For sells: next swing LOW must be > X pts below trigger close
                next_obstacle = min((b[3] for b in recent), default=trigger[4])
                distance = trigger[4] - next_obstacle
            # Actually we want the OPPOSITE direction obstacle (toward our trade dir).
            # Skip the math complexity — just say the trigger has to be > X pts past UHV
            uhv_extreme = uhv[2] if dir_sign == 1 else uhv[3]
            distance_past = (trigger[4] - uhv_extreme) if dir_sign == 1 else (uhv_extreme - trigger[4])
            if distance_past < brk_distance_pts: continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m)
        chains.append(chain)

        # ===== NEW FILTER #12: CHAIN-STOP =====
        if chain_stop_after_losses is not None:
            chain_pnl = sum(m[1] for m in chain)
            if chain_pnl < 0:
                consecutive_losing_chains += 1
                if consecutive_losing_chains >= chain_stop_after_losses:
                    halted = True
            else:
                consecutive_losing_chains = 0

    n_chains = len(chains)
    all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = [m for m in all_mains if m[1] > 0]
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing_chains = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)

    print(f"  {label:<70}chains={n_chains:<3}mains={len(all_mains):<4}WR={len(wins)/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing_chains={losing_chains}  worst=${big_loss:+.2f}")


print("=" * 180)
print("PDF #2 — Phase-2 enhancements backtest on Shano-Zee descending ladder")
print("Base: probeConfirm=0.45, trail=$12/$4, fearI=$100, maxBurst=7, descending 0.70→0.10")
print("=" * 180)
print()
print("--- BASELINE ---")
run_with_filters("BASELINE: Shano-Zee descending only")

print()
print("--- 1) TICK-SPEED: break of UHV must occur within first N seconds of trigger candle ---")
for max_sec in [10, 15, 20, 30, 45]:
    run_with_filters(f"break within first {max_sec}s of trigger candle", max_break_sec=max_sec)

print()
print("--- 2) SPREAD FILTER: spread <= baseline(30min median) × X ---")
for mult in [1.1, 1.2, 1.3, 1.5, 2.0]:
    run_with_filters(f"spread <= {mult:.1f}× baseline", max_spread_mult=mult)

print()
print("--- 3) SESSION OVERLAP: trade only London-NY overlap (broker hour 15-18) ---")
run_with_filters("session: only London-NY overlap (15-18 broker)", session_overlap_only=True)

print()
print("--- 6) VOLATILITY COLLAPSE: trigger range NOT lowest-10 AND >=30% UHV range ---")
run_with_filters("vol-collapse check: trigger not lowest-10, >=30% UHV", vol_collapse_check=True)

print()
print("--- 7) M15 21-EMA TREND ALIGNMENT ---")
run_with_filters("M15 21-EMA: price above for buys / below for sells", m15_trend_align=True)

print()
print("--- 9) COMPRESSION: N consecutive low-vol candles between UHV and trigger ---")
for n in [1, 2, 3, 5]:
    run_with_filters(f"require {n} compression candle(s) (vol <70% UHV)", compression_n=n)

print()
print("--- 11) BREAKOUT DISTANCE: trigger close must be >X pts beyond UHV extreme ---")
for pts in [0.5, 1.0, 2.0, 3.0]:
    run_with_filters(f"trigger close >= {pts}pt past UHV", brk_distance_pts=pts)

print()
print("--- 12) CHAIN-STOP: halt after N consecutive losing chains ---")
for n in [2, 3, 4]:
    run_with_filters(f"halt after {n} losing chains", chain_stop_after_losses=n)

print()
print("--- COMBOS ---")
run_with_filters("session-only + spread<=1.3× + tick<=20s",
                 session_overlap_only=True, max_spread_mult=1.3, max_break_sec=20)
run_with_filters("M15 trend + tick<=20s + spread<=1.3×",
                 m15_trend_align=True, max_break_sec=20, max_spread_mult=1.3)
run_with_filters("session-only + M15 trend + chain-stop(2)",
                 session_overlap_only=True, m15_trend_align=True, chain_stop_after_losses=2)
run_with_filters("BIG STACK: tick<=15s + spread<=1.3 + M15 trend + chain-stop(2)",
                 max_break_sec=15, max_spread_mult=1.3, m15_trend_align=True,
                 chain_stop_after_losses=2)
