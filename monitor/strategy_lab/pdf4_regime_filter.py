"""pdf4_regime_filter.py — Directive Delta: M15 regime classifier.

Per PDF: classify market state on 15-min using ADX + Bollinger Bands:
  - Trending: ADX > 25, price holds above/below 50-EMA
  - Volatile: BB width > 1.5x trailing avg, ATR > 1.2x historical
  - Quiet/Choppy: ADX < 20, BB width < 0.8x trailing avg → DISABLE TRADING

Test: does adding regime filter improve realistic backtest results?
"""
from __future__ import annotations
import sys, csv, random, statistics
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas, SHADOW_CSV, CONTRACT_SIZE
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, burst_delta_positive, get_uhv_bar
)
import pdf4_latency_simulator as ls

PROBE_LOTS = 0.01
PROBE_CONFIRM = 0.45
HORIZON_SEC = 600

random.seed(42)


def build_m15_bars():
    """Build M15 bars from M1 bars."""
    if hasattr(build_m15_bars, "_cache"): return build_m15_bars._cache
    bars_1m = build_1m_bars()
    bars_15m = []
    cur_start = None; o = h = l = c = None
    for b in bars_1m:
        dt, b_o, b_h, b_l, b_c, _ = b
        anchor = dt.minute - (dt.minute % 15)
        bm = dt.replace(minute=anchor, second=0, microsecond=0)
        if cur_start is None:
            cur_start = bm; o = b_o; h = b_h; l = b_l; c = b_c
        elif bm != cur_start:
            bars_15m.append((cur_start, o, h, l, c))
            cur_start = bm; o = b_o; h = b_h; l = b_l; c = b_c
        else:
            if b_h > h: h = b_h
            if b_l < l: l = b_l
            c = b_c
    if cur_start: bars_15m.append((cur_start, o, h, l, c))
    build_m15_bars._cache = bars_15m
    return bars_15m


def compute_adx(bars, period=14):
    """Compute ADX. Returns list aligned with bars."""
    n = len(bars)
    if n < period + 1: return [None] * n
    tr = [0.0]; pdm = [0.0]; ndm = [0.0]
    for i in range(1, n):
        h, l, c = bars[i][2], bars[i][3], bars[i][4]
        ph, pl, pc = bars[i-1][2], bars[i-1][3], bars[i-1][4]
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
        up = h - ph; dn = pl - l
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
    # smoothed
    atr = [None] * n
    spdm = [None] * n
    sndm = [None] * n
    atr[period] = sum(tr[1:period+1]) / period
    spdm[period] = sum(pdm[1:period+1]) / period
    sndm[period] = sum(ndm[1:period+1]) / period
    for i in range(period+1, n):
        atr[i] = (atr[i-1] * (period-1) + tr[i]) / period
        spdm[i] = (spdm[i-1] * (period-1) + pdm[i]) / period
        sndm[i] = (sndm[i-1] * (period-1) + ndm[i]) / period
    pdi = [None] * n; ndi = [None] * n; dx = [None] * n
    for i in range(period, n):
        if atr[i] and atr[i] > 0:
            pdi[i] = 100 * spdm[i] / atr[i]
            ndi[i] = 100 * sndm[i] / atr[i]
            den = pdi[i] + ndi[i]
            if den > 0:
                dx[i] = 100 * abs(pdi[i] - ndi[i]) / den
    adx = [None] * n
    if n >= 2*period:
        adx[2*period-1] = sum(d for d in dx[period:2*period] if d is not None) / period
        for i in range(2*period, n):
            adx[i] = (adx[i-1] * (period-1) + (dx[i] or 0)) / period
    return adx


def compute_bb_width(bars, period=20, mult=2.0):
    """Bollinger Bands width = (upper-lower)/middle. Returns list aligned with bars."""
    n = len(bars)
    width = [None] * n
    closes = [b[4] for b in bars]
    for i in range(period - 1, n):
        window = closes[i - period + 1:i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        std = var ** 0.5
        if mean > 0:
            width[i] = 2 * mult * std / mean  # relative width
    return width


def classify_regime(when, bars_15m, bar_idx_15m, adx_arr, bb_arr):
    """Return 'trending', 'volatile', 'quiet', or None."""
    anchor = when.minute - (when.minute % 15)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_15m.get(bm)
    if idx is None:
        for d in range(1, 10):
            t = bm - timedelta(minutes=15*d)
            idx = bar_idx_15m.get(t)
            if idx is not None: break
    if idx is None or idx < 30: return None
    adx = adx_arr[idx] if idx < len(adx_arr) else None
    bbw = bb_arr[idx] if idx < len(bb_arr) else None
    if adx is None or bbw is None: return None
    # Trailing 20-bar avg BB width
    recent_bbs = [b for b in bb_arr[max(0, idx-20):idx] if b is not None]
    avg_bbw = sum(recent_bbs) / max(len(recent_bbs), 1) if recent_bbs else bbw

    if adx > 25: return "trending"
    if bbw > 1.5 * avg_bbw: return "volatile"
    if adx < 20 and bbw < 0.8 * avg_bbw: return "quiet"
    return "neutral"


def sim_one_main_lat(intended_dt, dir_sign, intended_price, ticks, fear_ideal, lots, trail_t, trail_d):
    if not ticks: return 0.0, "no_ticks", None
    actual_dt, actual_price, _ = ls.latency_slipped_fill(intended_dt, ticks, dir_sign, intended_price)
    if actual_dt is None: return 0.0, "entry_failed", None
    forward = [t for t in ticks if t[0] >= actual_dt]
    if not forward: return 0.0, "no_forward", None
    peak = 0.0
    intended_exit_dt = None; intended_exit_price = None; reason = "horizon_end"
    for dt, bid, ask in forward:
        cur = bid if dir_sign == 1 else ask
        profit = ((cur - actual_price) if dir_sign == 1 else (actual_price - cur)) * lots * CONTRACT_SIZE
        if profit > peak: peak = profit
        if profit <= -fear_ideal:
            intended_exit_dt = dt; intended_exit_price = cur; reason = "fearIdeal"; break
        if peak >= trail_t and (peak - profit) >= trail_d:
            intended_exit_dt = dt; intended_exit_price = cur; reason = "trail"; break
    if intended_exit_dt is None:
        intended_exit_dt = forward[-1][0]
        intended_exit_price = forward[-1][1] if dir_sign == 1 else forward[-1][2]
    actual_exit_dt, actual_exit_price, _ = ls.latency_slipped_fill(
        intended_exit_dt, forward, -dir_sign, intended_exit_price)
    if actual_exit_dt is None: actual_exit_price = intended_exit_price
    final = ((actual_exit_price - actual_price) if dir_sign == 1 else (actual_price - actual_exit_price)) * lots * CONTRACT_SIZE
    return round(final, 2), reason, actual_exit_dt


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def run(label, *, regime_filter=False, allow_quiet=False, lot_start=0.2, trail_t=12, trail_d=4):
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    bars_15m = build_m15_bars()
    bar_idx_15m = {b[0]: i for i, b in enumerate(bars_15m)}
    adx_arr = compute_adx(bars_15m, 14)
    bb_arr = compute_bb_width(bars_15m, 20)
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, _, _ = get_emas(21, 21, 15)

    chains = []
    blocked_quiet = 0; blocked_neutral = 0
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        actual_entry_dt, actual_entry, _ = ls.latency_slipped_fill(entry_time, ticks, dir_sign, entry_price)
        if actual_entry_dt is None: continue
        entry_time = actual_entry_dt; entry_price = actual_entry
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in [t for t in ticks if t[0] >= entry_time]:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        if 3 <= confirm_speed <= 8: continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] < uhv[2] + 0.3: continue
        if dir_sign == -1 and trigger[4] > uhv[3] - 0.3: continue
        ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
        if ts is None or ts > 15: continue
        if not actual_spread_check(confirm_dt, 1.2): continue
        ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10): continue

        # REGIME FILTER
        if regime_filter:
            regime = classify_regime(confirm_dt, bars_15m, bar_idx_15m, adx_arr, bb_arr)
            if regime == "quiet":
                blocked_quiet += 1; continue
            if regime == "neutral" and not allow_quiet:
                blocked_neutral += 1; continue
            # trending or volatile = allowed

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt
        cur_intended = intended_entry
        burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, lot_start, -0.05, lot_start)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, _, exit_dt = sim_one_main_lat(cur_dt, dir_sign, cur_intended, tt, 100, lots, trail_t, trail_d)
            results.append((lots, pnl))
            if pnl <= 0: break
            if exit_dt is None: break
            h2 = exit_dt.hour
            if (4 <= h2 <= 6) or (21 <= h2 <= 23): break
            t2 = trend_at(exit_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t2 is None or t2 == 0 or t2 != dir_sign: break
            uhv2, _, _ = get_uhv_bar(exit_dt, bars_1m, bar_idx_1m, 20)
            if uhv2 is None: break
            recent = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if recent:
                _, b, a = recent[-1]
                cp = b if dir_sign == -1 else a
                if dir_sign == 1 and cp <= uhv2[2]: break
                if dir_sign == -1 and cp >= uhv2[3]: break
            if not burst_delta_positive(exit_dt, dir_sign, 15): break
            cur_dt = exit_dt
            nt = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if nt:
                _, b, a = nt[0]
                cur_intended = a if dir_sign == 1 else b
            else:
                break
            burst_idx += 1
        chains.append(results)

    n = len(chains); all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    chain_wr = (n - losing) / max(n, 1) * 100
    main_wr = wins / max(len(all_mains), 1) * 100
    extra = ""
    if regime_filter:
        extra = f"  q-block={blocked_quiet}, n-block={blocked_neutral}"
    print(f"  {label:<55}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chain_WR={chain_wr:>5.1f}%{extra}")


print("=" * 100)
print("PDF #4 DIRECTIVE DELTA — M15 regime filter (ADX + Bollinger Bands)")
print("Quiet regime (ADX<20 + BB<0.8×avg) → DISABLE trading")
print("=" * 100)

print()
print("--- BASELINE: 0.2 lots realistic, no regime filter ---")
run("0.2 lots, no regime filter (current applied LIVE)")

print()
print("--- WITH REGIME FILTER (block quiet only) ---")
run("0.2 lots + regime filter (allow neutral)", regime_filter=True, allow_quiet=True)

print()
print("--- STRICT REGIME FILTER (only trending or volatile) ---")
run("0.2 lots + regime filter (strict)", regime_filter=True, allow_quiet=False)
