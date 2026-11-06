"""reduce_avg_loss.py — try every method to cut the -$51.60 avg loss.

Current: 24 fires, 96% WR, +$444 total, +$22 avg win, -$51.60 avg loss (1 loss).
The 1 loss trips fearIdeal at -$50.

Methods tested:
  A) Tighter fearIdeal: $40 → $10
  B) MAE stop: bail if drawdown reaches $X before any peak
  C) Time bail: exit if no profit after T seconds
  D) Breakeven move: once peak hits $X, move stop to breakeven
  E) Quick adverse bail: exit if price moves against entry by Y pts in first 60s
  F) Combined: best B + best D etc.
"""
from __future__ import annotations
import csv
import sys
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
FEAR_IDEAL_BASE = 50.0
PROBE_LOTS = 0.01
MAIN_LOTS = 0.40
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


def sim_main_extended(entry, dir_sign, ticks, *,
                      trail_trig=12, trail_drop=4, fear_ideal=50,
                      mae_bail=None,           # exit if drawdown before peak >= X
                      time_bail_sec=None,      # exit if profit <=0 after N sec
                      time_bail_threshold=0,   # only bail if profit <= this after time
                      breakeven_trigger=None,  # once peak >= X, move stop to BE+
                      breakeven_offset=0,      # offset above BE (lock in this much)
                      quick_adverse_pts=None,  # exit if dropped X pts in first 60s
                      quick_adverse_sec=60,
                      lots=0.40):
    if not ticks: return 0.0, "no_data"
    peak = 0.0; last = 0.0
    t0 = ticks[0][0]
    be_active = False
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry) * lots * CONTRACT_SIZE
            adverse_pts = entry - bid
        else:
            profit = (entry - ask) * lots * CONTRACT_SIZE
            adverse_pts = ask - entry
        last = profit
        if profit > peak: peak = profit
        elapsed = (dt - t0).total_seconds()

        # Quick-adverse bail
        if quick_adverse_pts is not None and elapsed <= quick_adverse_sec:
            if adverse_pts >= quick_adverse_pts and peak < trail_trig:
                return round(profit, 2), f"quick_adverse({adverse_pts:.2f}pt)"

        # MAE bail (drawdown before any meaningful peak)
        if mae_bail is not None and peak < trail_trig:
            if profit <= -mae_bail:
                return round(profit, 2), f"mae_bail(${profit:.2f})"

        # Breakeven move: once peak hits trigger, exit if drops back to BE+offset
        if breakeven_trigger is not None and peak >= breakeven_trigger:
            be_active = True
            if profit <= breakeven_offset:
                return round(profit, 2), f"BE_stop(${profit:.2f})"

        # Time bail: exit if not in profit after T seconds
        if time_bail_sec is not None and elapsed >= time_bail_sec and peak < trail_trig:
            if profit <= time_bail_threshold:
                return round(profit, 2), f"time_bail({elapsed:.0f}s)"

        # Standard fearIdeal
        if profit <= -fear_ideal:
            return round(profit, 2), f"fearIdeal(${profit:.2f})"

        # Standard trail
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), f"trail(peak=${peak:.2f})"

    return round(last, 2), "horizon_end"


def run_filter(label, **sim_kwargs):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    ema_f, ema_s, bar_idx, _ = get_emas(tf_minutes=2)
    fired = 0; wins = 0; total = 0.0
    losses_list = []
    wins_list = []
    exits = defaultdict(int)

    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue

        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        confirm_dt = confirm_bid = confirm_ask = None
        confirm_speed = None
        for dt, bid, ask in ticks:
            if dir_sign == 1:
                fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else:
                fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds()
                break
        if confirm_dt is None: continue

        # Apply winning combo filters
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx, tf=2)
        if t is not None and t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue

        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        horizon_end = confirm_dt + timedelta(seconds=HORIZON_SEC)
        main_ticks = ticks_in_range(confirm_dt, horizon_end)
        pnl, reason = sim_main_extended(main_entry, dir_sign, main_ticks, **sim_kwargs)
        fired += 1
        total += pnl
        exits[reason.split('(')[0]] += 1
        if pnl > 0:
            wins += 1
            wins_list.append(pnl)
        else:
            losses_list.append(pnl)

    wr = wins / max(fired, 1) * 100
    avg_w = sum(wins_list) / max(len(wins_list), 1)
    avg_l = sum(losses_list) / max(len(losses_list), 1)
    max_l = min(losses_list) if losses_list else 0
    print(f"  {label:<55}fired={fired:<3} W={wins:<2} L={fired-wins:<2} WR={wr:>5.1f}%  "
          f"total=${total:+8.2f}  avgW=${avg_w:+6.2f}  avgL=${avg_l:+7.2f}  maxL=${max_l:+7.2f}")


print("=" * 130)
print("BASELINE (current winning combo, 0.40 lots)")
print("=" * 130)
run_filter("baseline (fearI=$50)", fear_ideal=50)

print()
print("=" * 130)
print("METHOD A: TIGHTER fearIdeal")
print("=" * 130)
for fi in [45, 40, 35, 30, 25, 20, 15, 10]:
    run_filter(f"fearIdeal=${fi}", fear_ideal=fi)

print()
print("=" * 130)
print("METHOD B: MAE BAIL (exit on drawdown before any meaningful peak)")
print("=" * 130)
for mae in [40, 30, 25, 20, 15, 12, 10, 8]:
    run_filter(f"MAE bail @ ${mae}", fear_ideal=50, mae_bail=mae)

print()
print("=" * 130)
print("METHOD C: TIME BAIL (exit if not in profit after T sec, any negative position)")
print("=" * 130)
for t_sec in [30, 60, 90, 120, 180, 240, 300]:
    run_filter(f"time bail @ {t_sec}s if profit<=0", fear_ideal=50, time_bail_sec=t_sec, time_bail_threshold=0)

print()
print("=" * 130)
print("METHOD C2: TIME BAIL (exit if profit < -$10 after T sec — softer)")
print("=" * 130)
for t_sec in [30, 60, 90, 120, 180]:
    run_filter(f"time bail @ {t_sec}s if profit<=-$10", fear_ideal=50, time_bail_sec=t_sec, time_bail_threshold=-10)

print()
print("=" * 130)
print("METHOD D: BREAKEVEN MOVE (once peak >= X, exit at BE)")
print("=" * 130)
for be_trig in [4, 6, 8, 10]:
    run_filter(f"BE move once peak >= ${be_trig}", fear_ideal=50, breakeven_trigger=be_trig, breakeven_offset=0)

print()
print("=" * 130)
print("METHOD D2: LOCK-IN MOVE (once peak >= X, exit at BE+$2)")
print("=" * 130)
for be_trig in [6, 8, 10, 12]:
    run_filter(f"Lock $2 once peak >= ${be_trig}", fear_ideal=50, breakeven_trigger=be_trig, breakeven_offset=2)

print()
print("=" * 130)
print("METHOD E: QUICK ADVERSE (exit if price drops X pts in first 60s)")
print("=" * 130)
for pts in [1, 2, 3, 4, 5, 6, 8]:
    run_filter(f"quick adverse @ {pts}pt in 60s", fear_ideal=50, quick_adverse_pts=pts, quick_adverse_sec=60)

print()
print("=" * 130)
print("METHOD F: COMBINED — best of each method layered")
print("=" * 130)
run_filter("MAE $20 + time bail 90s", fear_ideal=50, mae_bail=20, time_bail_sec=90, time_bail_threshold=0)
run_filter("MAE $15 + BE @ $8", fear_ideal=50, mae_bail=15, breakeven_trigger=8)
run_filter("MAE $20 + BE @ $8", fear_ideal=50, mae_bail=20, breakeven_trigger=8)
run_filter("MAE $20 + BE @ $10", fear_ideal=50, mae_bail=20, breakeven_trigger=10)
run_filter("fearI=$30 + BE @ $8", fear_ideal=30, breakeven_trigger=8)
run_filter("fearI=$25 + BE @ $10", fear_ideal=25, breakeven_trigger=10)
run_filter("quick 3pt + BE @ $8", fear_ideal=50, quick_adverse_pts=3, breakeven_trigger=8)
run_filter("quick 4pt + BE @ $10", fear_ideal=50, quick_adverse_pts=4, breakeven_trigger=10)
