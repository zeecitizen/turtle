"""probe_trail_test.py — what if we DON'T fire mains, just trail the 0.01 probes?

The accidental orphan probes today netted ~+$150 by riding the trend with no main.
This tests: would replacing the 0.40-main fire with a 0.01-trail-forever strategy
beat the current $417 (90.9%) winning combo?

For each confirmed probe, we simulate two strategies:
  A) MAIN: open 0.40 lot at confirm, exit at trail/fearIdeal (current)
  B) PROBE-TRAIL: keep the 0.01 probe open, trail with several configs
     - probeTrail $X drop: once probe MFE >= $X, close on $Y drop
     - tested at multiple trail params

Compare: total $$, WR, max drawdown, time held.
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
TRAIL_TRIGGER_MAIN = 12.0
TRAIL_DROP_MAIN = 4.0
FEAR_IDEAL_MAIN = 50.0
PROBE_LOTS = 0.01
MAIN_LOTS = 0.40
HORIZON_MAIN_SEC = 600           # 10 min for main
HORIZON_PROBE_SEC = 4 * 3600     # let probe run for up to 4 hours


def trend_at(when, ema_f, ema_s, bar_idx, tf=1):
    if tf == 1:
        bm = when.replace(second=0, microsecond=0)
    else:
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


def sim_main(entry_price, dir_sign, ticks, trail_trig, trail_drop, fear_ideal, lots):
    if not ticks: return 0.0
    peak = 0.0; last = 0.0
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry_price) * lots * CONTRACT_SIZE
        else:
            profit = (entry_price - ask) * lots * CONTRACT_SIZE
        last = profit
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return profit
        if peak >= trail_trig and (peak - profit) >= trail_drop: return profit
    return last


def sim_probe_trail(entry_price, dir_sign, ticks, trail_trig, trail_drop, fail_loss, lots):
    """Open at entry_price, trail same logic but with probe lots and probeFail stop."""
    if not ticks: return 0.0, 0
    peak = 0.0; last = 0.0
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry_price) * lots * CONTRACT_SIZE
        else:
            profit = (entry_price - ask) * lots * CONTRACT_SIZE
        last = profit
        if profit > peak: peak = profit
        if profit <= -fail_loss: return profit, (dt - ticks[0][0]).total_seconds()
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return profit, (dt - ticks[0][0]).total_seconds()
    return last, (ticks[-1][0] - ticks[0][0]).total_seconds()


def run_comparison(probe_trail_trig, probe_trail_drop, probe_fail, label,
                   horizon_sec=HORIZON_PROBE_SEC,
                   apply_winning_filters=False, trend_tf=2):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    ema_f, ema_s, bar_idx, _ = get_emas(tf_minutes=trend_tf)

    main_results = []
    probe_results = []
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue

        # Walk to confirm
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

        # Apply winning filters if requested
        if apply_winning_filters:
            h = confirm_dt.hour
            if (4 <= h <= 6) or (21 <= h <= 23): continue
            t = trend_at(confirm_dt, ema_f, ema_s, bar_idx, trend_tf)
            if t is not None and t != dir_sign: continue
            if 3 <= confirm_speed <= 8: continue

        # Strategy A: 0.40 MAIN
        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        horizon_end_main = confirm_dt + timedelta(seconds=HORIZON_MAIN_SEC)
        main_ticks = ticks_in_range(confirm_dt, horizon_end_main)
        main_pnl = sim_main(main_entry, dir_sign, main_ticks,
                            TRAIL_TRIGGER_MAIN, TRAIL_DROP_MAIN, FEAR_IDEAL_MAIN, MAIN_LOTS)
        main_results.append(main_pnl)

        # Strategy B: 0.01 PROBE-TRAIL — keep probe running, trail with probe params
        # Entry stays at original probe entry_price (probe was opened at entry_time)
        # We track the EXISTING 0.01 lot position from entry_time onward
        horizon_end_probe = entry_time + timedelta(seconds=horizon_sec)
        probe_ticks = ticks_in_range(entry_time, horizon_end_probe)
        probe_pnl, hold_sec = sim_probe_trail(
            entry_price, dir_sign, probe_ticks,
            probe_trail_trig, probe_trail_drop, probe_fail, PROBE_LOTS)
        probe_results.append((probe_pnl, hold_sec))

    n = len(main_results)
    main_total = sum(main_results)
    main_wins = sum(1 for p in main_results if p > 0)
    probe_total = sum(p for p, _ in probe_results)
    probe_wins = sum(1 for p, _ in probe_results if p > 0)
    probe_avg_hold = sum(s for _, s in probe_results) / max(n, 1)

    print(f"  {label}")
    print(f"    fired={n}")
    print(f"    MAIN(0.40):    total=${main_total:+8.2f}  WR={main_wins/max(n,1)*100:.1f}%  "
          f"avg=${main_total/max(n,1):+.2f}")
    print(f"    PROBE(0.01):   total=${probe_total:+8.2f}  WR={probe_wins/max(n,1)*100:.1f}%  "
          f"avg=${probe_total/max(n,1):+.2f}  hold_avg={probe_avg_hold/60:.1f}min")
    print()
    return main_total, probe_total


print("=" * 100)
print("STRATEGY A (0.40 MAIN, current)  vs  STRATEGY B (0.01 PROBE-TRAIL, hypothesis)")
print("Same probe set, same confirm trigger, two simulated outcomes per probe.")
print("=" * 100)
print()

print("ON ALL CONFIRMED PROBES (no filters):")
run_comparison(probe_trail_trig=4.0, probe_trail_drop=1.0, probe_fail=3.0,
               label="probe trail trig=$4 drop=$1 fail=$3 (4hr horizon)")
run_comparison(probe_trail_trig=8.0, probe_trail_drop=2.0, probe_fail=3.0,
               label="probe trail trig=$8 drop=$2 fail=$3 (4hr horizon)")
run_comparison(probe_trail_trig=15.0, probe_trail_drop=4.0, probe_fail=3.0,
               label="probe trail trig=$15 drop=$4 fail=$3 (4hr horizon)")
run_comparison(probe_trail_trig=30.0, probe_trail_drop=8.0, probe_fail=3.0,
               label="probe trail trig=$30 drop=$8 fail=$3 (4hr horizon, big runner)")
run_comparison(probe_trail_trig=50.0, probe_trail_drop=15.0, probe_fail=3.0,
               label="probe trail trig=$50 drop=$15 fail=$3 (let it FLY)")

print()
print("ON WINNING-COMBO PROBES (hour + 2-min trend + skipFastConfirm):")
run_comparison(probe_trail_trig=4.0, probe_trail_drop=1.0, probe_fail=3.0,
               label="probe trail trig=$4 drop=$1 fail=$3", apply_winning_filters=True)
run_comparison(probe_trail_trig=8.0, probe_trail_drop=2.0, probe_fail=3.0,
               label="probe trail trig=$8 drop=$2 fail=$3", apply_winning_filters=True)
run_comparison(probe_trail_trig=15.0, probe_trail_drop=4.0, probe_fail=3.0,
               label="probe trail trig=$15 drop=$4 fail=$3", apply_winning_filters=True)
run_comparison(probe_trail_trig=30.0, probe_trail_drop=8.0, probe_fail=3.0,
               label="probe trail trig=$30 drop=$8 fail=$3", apply_winning_filters=True)
run_comparison(probe_trail_trig=50.0, probe_trail_drop=15.0, probe_fail=3.0,
               label="probe trail trig=$50 drop=$15 fail=$3 (let it FLY)", apply_winning_filters=True)
