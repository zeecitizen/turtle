"""soft_be_test.py — once trade goes positive, cap loss at -$X.

Two interpretations of user's question:
  A) "soft BE": once profit > 0 (or > trigger), exit if profit <= -$X
  B) "tight trail from positive": once profit > 0, trail with $X drop from peak

Tests A and B at multiple thresholds against baseline.
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
FEAR_IDEAL = 80.0
PROBE_LOTS = 0.01
MAIN_LOTS = 0.70
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


def sim_main(entry, dir_sign, ticks, *,
             trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP, fear_ideal=FEAR_IDEAL,
             soft_be_arm=None,        # arm soft-BE once profit reaches this (None = on first tick > 0)
             soft_be_floor=None,      # exit if profit <= this (after armed)
             tight_trail_arm=None,    # arm tight trail once profit reaches this
             tight_trail_drop=None,   # drop $ to exit (from peak)
             lots=MAIN_LOTS):
    if not ticks: return 0.0, "no_data"
    peak = 0.0; last = 0.0
    soft_be_armed = False
    tight_trail_armed = False
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry) * lots * CONTRACT_SIZE
        else:
            profit = (entry - ask) * lots * CONTRACT_SIZE
        last = profit
        if profit > peak: peak = profit

        # Arm soft-BE
        if soft_be_floor is not None and not soft_be_armed:
            arm_threshold = soft_be_arm if soft_be_arm is not None else 0.01
            if profit >= arm_threshold:
                soft_be_armed = True

        # Soft-BE exit
        if soft_be_armed and soft_be_floor is not None:
            if profit <= soft_be_floor:
                return round(profit, 2), f"soft_BE(${profit:.2f})"

        # Arm tight trail
        if tight_trail_drop is not None and not tight_trail_armed:
            arm_threshold = tight_trail_arm if tight_trail_arm is not None else 0.01
            if profit >= arm_threshold:
                tight_trail_armed = True

        # Tight trail exit
        if tight_trail_armed and tight_trail_drop is not None:
            if peak >= 0 and (peak - profit) >= tight_trail_drop:
                return round(profit, 2), f"tight_trail(${profit:.2f})"

        # Standard fearIdeal
        if profit <= -fear_ideal:
            return round(profit, 2), f"fearIdeal(${profit:.2f})"
        # Standard trail
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), f"trail(${profit:.2f})"
    return round(last, 2), "horizon_end"


def run_test(label, **kw):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))
    ema_f, ema_s, bar_idx, _ = get_emas(tf_minutes=2)
    fired = 0; wins = 0; total = 0.0
    Ws = []; Ls = []
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
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in ticks:
            if dir_sign == 1:
                fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else:
                fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx, 2)
        if t is not None and t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        horizon_end = confirm_dt + timedelta(seconds=HORIZON_SEC)
        main_ticks = ticks_in_range(confirm_dt, horizon_end)
        pnl, reason = sim_main(main_entry, dir_sign, main_ticks, **kw)
        fired += 1; total += pnl
        exits[reason.split('(')[0]] += 1
        if pnl > 0: wins += 1; Ws.append(pnl)
        else: Ls.append(pnl)
    wr = wins / max(fired, 1) * 100
    avgW = sum(Ws) / max(len(Ws), 1)
    avgL = sum(Ls) / max(len(Ls), 1)
    maxL = min(Ls) if Ls else 0
    print(f"  {label:<60}fired={fired}  W={wins} L={fired-wins}  WR={wr:>5.1f}%  total=${total:+8.2f}  avgW=${avgW:+6.2f}  avgL=${avgL:+7.2f}  maxL=${maxL:+7.2f}")


print(f"All tests use 0.70 LOTS, fearIdeal=$80 (current winning combo)")
print()
print("=" * 140)
print("BASELINE")
print("=" * 140)
run_test("baseline (no BE/soft-BE)")
print()
print("=" * 140)
print("METHOD A: SOFT-BE (once profit > $0, exit if profit drops to floor)")
print("=" * 140)
for floor in [-1, -2, -3, -5, -8, -12, -20]:
    run_test(f"soft-BE: arm @ first positive, floor=${floor}", soft_be_floor=floor)

print()
print("=" * 140)
print("METHOD A2: SOFT-BE with arm threshold (require profit >= X first)")
print("=" * 140)
for arm in [2, 5, 8]:
    for floor in [-3, -5]:
        run_test(f"soft-BE: arm @ +${arm}, floor=${floor}", soft_be_arm=arm, soft_be_floor=floor)

print()
print("=" * 140)
print("METHOD B: TIGHT TRAIL FROM POSITIVE (once positive, trail with $X drop from peak)")
print("=" * 140)
for drop in [2, 3, 4, 5, 6, 8]:
    run_test(f"tight trail: arm @ first positive, ${drop} drop", tight_trail_drop=drop)

print()
print("=" * 140)
print("METHOD B2: TIGHT TRAIL with arm threshold")
print("=" * 140)
for arm in [3, 5, 8]:
    for drop in [3, 4, 5]:
        run_test(f"tight trail: arm @ +${arm}, ${drop} drop", tight_trail_arm=arm, tight_trail_drop=drop)
