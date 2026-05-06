"""uhv_filter_test.py — does requiring a UHV breakout context boost WR?

Original turtle.pine UHV strategy: identify highest-volume candle in retracement,
fire when subsequent candle BREAKS OUT of that UHV candle's high (bull) or low (bear).

Volume column in tick CSV is 0 for XAUUSD on Blueberry, so we use TICK-COUNT per
minute as the volume proxy (standard for forex with no published volume).

For each confirmed probe:
  1. Look back N=20 1-min bars before probe entry
  2. Find the bar with highest tick-count (UHV candidate)
  3. Check if the TRIGGER bar (the bar before probe entry) closed above UHV high
     (for bull probe) or below UHV low (for bear probe)
  4. Optional strictness: require UHV in last K bars only, or require K-multiple
     vs avg tick-count

Filter variants tested:
  - UHV in last 20 bars + breakout
  - UHV in last 10 bars + breakout
  - UHV must be K× avg tick-count (1.5×, 2×)
  - Require UHV candle wide-spread (range > 1.5× ATR)
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
    COMMON_DIR,
)

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
FEAR_IDEAL = 80.0
PROBE_LOTS = 0.01
MAIN_LOTS = 0.70
HORIZON_SEC = 600


def build_1m_bars_with_tickcount():
    """Same as build_1m_bars but also returns tick count per minute."""
    if hasattr(build_1m_bars_with_tickcount, "_cache"):
        return build_1m_bars_with_tickcount._cache
    all_ticks = []
    for p in sorted(COMMON_DIR.glob("shano_ticks_*.csv")):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                next(f, None)
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) < 4: continue
                    try:
                        dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                        bid = float(parts[2]); ask = float(parts[3])
                        all_ticks.append((dt, bid, ask))
                    except (ValueError, IndexError): continue
        except OSError: pass

    bars = []  # (dt, o, h, l, c, tickcount)
    cur_min = None; o = h = l = c = None; tc = 0
    for dt, bid, ask in all_ticks:
        mid = (bid + ask) / 2
        bm = dt.replace(second=0, microsecond=0)
        if cur_min is None:
            cur_min = bm; o = h = l = c = mid; tc = 1
        elif bm != cur_min:
            bars.append((cur_min, o, h, l, c, tc))
            cur_min = bm; o = h = l = c = mid; tc = 1
        else:
            if mid > h: h = mid
            if mid < l: l = mid
            c = mid; tc += 1
    if cur_min is not None: bars.append((cur_min, o, h, l, c, tc))
    build_1m_bars_with_tickcount._cache = bars
    return bars


def has_uhv_breakout(probe_entry_time, dir_sign, bars, bar_idx, *,
                    lookback=20, k_multiple=1.0, require_wide_spread=False,
                    require_low_vol_breakout=False, max_breakout_vol_ratio=1.0):
    """Check if this probe is firing as a UHV breakout.
    require_low_vol_breakout: classic VSA — trigger bar tickcount must be
    less than max_breakout_vol_ratio × UHV tickcount (e.g. 0.5 = breakout
    must have at most 50% of UHV's volume)."""
    bm = probe_entry_time.replace(second=0, microsecond=0)
    idx = bar_idx.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx.get(t)
            if idx is not None: break
    if idx is None or idx < lookback + 14:
        return False, None  # not enough history

    # Trigger bar = the bar BEFORE probe entry (the bigness candle)
    trigger = bars[idx - 1] if idx > 0 else bars[idx]

    # Search lookback window (excluding trigger bar) for highest tick-count bar
    lookback_bars = bars[max(0, idx - 1 - lookback):idx - 1]
    if not lookback_bars: return False, None

    # Average tick count in lookback (for k-multiple check)
    avg_tc = sum(b[5] for b in lookback_bars) / len(lookback_bars)

    # Pick highest-volume candle
    uhv = max(lookback_bars, key=lambda b: b[5])
    if uhv[5] < k_multiple * avg_tc:
        return False, None  # UHV not significant enough

    # Optional wide-spread check: UHV range > 1.5× ATR(14)
    if require_wide_spread:
        atr_window = bars[max(0, idx - 14):idx]
        avg_range = sum(b[2] - b[3] for b in atr_window) / max(len(atr_window), 1)
        uhv_range = uhv[2] - uhv[3]
        if uhv_range < 1.5 * avg_range:
            return False, None

    # Breakout check: trigger bar closes BEYOND UHV extreme in probe direction
    breakout_ok = False
    if dir_sign == 1 and trigger[4] > uhv[2]: breakout_ok = True
    elif dir_sign == -1 and trigger[4] < uhv[3]: breakout_ok = True
    if not breakout_ok: return False, None

    # Low-volume breakout requirement: VSA setup needs quiet retest break
    if require_low_vol_breakout:
        if trigger[5] >= max_breakout_vol_ratio * uhv[5]:
            return False, None  # breakout had too much volume

    return True, uhv


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


def sim_main(entry, dir_sign, ticks, *, arm=None, drop=None,
             trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP,
             fear_ideal=FEAR_IDEAL, lots=MAIN_LOTS):
    if not ticks: return 0.0
    peak = 0.0; last = 0.0; armed = False
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE
        else: profit = (entry - ask) * lots * CONTRACT_SIZE
        last = profit
        if profit > peak: peak = profit
        if arm is not None and not armed and profit >= arm: armed = True
        if armed and drop is not None and (peak - profit) >= drop:
            return round(profit, 2)
        if profit <= -fear_ideal: return round(profit, 2)
        if peak >= trail_trig and (peak - profit) >= trail_drop: return round(profit, 2)
    return round(last, 2)


def run(label, *, lookback=20, k_mult=1.0, require_wide=False, require_uhv=True,
        require_low_vol=False, max_brk_ratio=1.0, arm=None, drop=None):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars = build_1m_bars_with_tickcount()
    bar_idx = {b[0]: i for i, b in enumerate(bars)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    fired = 0; wins = 0; total = 0.0
    Ws = []; Ls = []
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

        # Existing winning combo filters
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is not None and t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue

        # NEW: UHV breakout filter
        if require_uhv:
            has_uhv, uhv_bar = has_uhv_breakout(
                entry_time, dir_sign, bars, bar_idx,
                lookback=lookback, k_multiple=k_mult,
                require_wide_spread=require_wide,
                require_low_vol_breakout=require_low_vol,
                max_breakout_vol_ratio=max_brk_ratio)
            if not has_uhv: continue

        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        horizon_end = confirm_dt + timedelta(seconds=HORIZON_SEC)
        main_ticks = ticks_in_range(confirm_dt, horizon_end)
        pnl = sim_main(main_entry, dir_sign, main_ticks, arm=arm, drop=drop)
        fired += 1; total += pnl
        if pnl > 0: wins += 1; Ws.append(pnl)
        else: Ls.append(pnl)

    wr = wins / max(fired, 1) * 100
    avgW = sum(Ws) / max(len(Ws), 1)
    avgL = sum(Ls) / max(len(Ls), 1)
    maxL = min(Ls) if Ls else 0
    print(f"  {label:<60}fired={fired:<3}W={wins:<2}L={fired-wins:<2}WR={wr:>5.1f}%  total=${total:+8.2f}  avgW=${avgW:+6.2f}  avgL=${avgL:+7.2f}  maxL=${maxL:+7.2f}")


print("All tests at 0.70 lots, fearI=$80, winning combo (hour+2min trend+skipFast)")
print()
print("=" * 140)
print("BASELINE (no UHV filter)")
print("=" * 140)
run("baseline (no UHV req)", require_uhv=False)
run("baseline + protected (arm $3, drop $4)", require_uhv=False, arm=3, drop=4)
print()
print("=" * 140)
print("METHOD: UHV BREAKOUT REQUIRED")
print("(trigger bar must close beyond UHV high/low; UHV = highest tick-count bar in lookback)")
print("=" * 140)
for lb in [10, 15, 20, 30]:
    run(f"UHV req: lookback={lb}, any UHV", lookback=lb, k_mult=1.0)

print()
print("=" * 140)
print("METHOD: UHV must be K× avg tick-count (more selective)")
print("=" * 140)
for k in [1.5, 2.0, 2.5, 3.0]:
    for lb in [10, 20]:
        run(f"UHV req: lookback={lb}, k={k}× avg", lookback=lb, k_mult=k)
    print()

print("=" * 140)
print("METHOD: UHV + wide-spread requirement (range > 1.5× ATR)")
print("=" * 140)
for k in [1.0, 1.5, 2.0]:
    run(f"UHV: k={k}× + wide-spread", lookback=20, k_mult=k, require_wide=True)

print()
print("=" * 140)
print("METHOD: UHV + protected exit (arm $3, drop $4)")
print("=" * 140)
for k in [1.0, 1.5, 2.0]:
    run(f"UHV: k={k}× + protected", lookback=20, k_mult=k, arm=3, drop=4)

print()
print("=" * 140)
print("METHOD: CLASSIC VSA — UHV breakout + LOW-VOLUME breakout (the actual rule)")
print("breakout candle volume must be at most X × UHV volume")
print("=" * 140)
for ratio in [1.0, 0.95, 0.90, 0.80, 0.70, 0.60, 0.50, 0.40, 0.30]:
    run(f"UHV req + brk vol <= {ratio:.2f}× UHV vol",
        lookback=20, k_mult=1.0, require_low_vol=True, max_brk_ratio=ratio)

print()
print("=" * 140)
print("METHOD: CLASSIC VSA + UHV must be K× avg (significance)")
print("=" * 140)
for k in [1.5, 2.0]:
    for ratio in [0.80, 0.60, 0.40]:
        run(f"UHV k={k}× + brk vol <= {ratio:.2f}× UHV",
            lookback=20, k_mult=k, require_low_vol=True, max_brk_ratio=ratio)
    print()
