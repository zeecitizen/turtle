"""improve_protected_wr.py — push the 83% WR up while keeping max loss <= $10.

Baseline: arm @ +$3, $4 drop trail = +$481, 83% WR, avgL -$4, maxL -$8.

Approaches:
  A) Widen the trail drop ($5, $6, $7) — more wiggle room before bailing
  B) Higher arm threshold (+$4, +$5, +$6) — only protect committed moves
  C) Layer extra entry filters (consec, ema_dist) to prefilter the bad fires
  D) Combine A+B+C
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
from advanced_features import compute_atr

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


def sim_main(entry, dir_sign, ticks, *, arm_threshold=3.0, trail_drop_after_arm=4.0,
             trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP, fear_ideal=FEAR_IDEAL,
             lots=MAIN_LOTS):
    if not ticks: return 0.0
    peak = 0.0; last = 0.0; armed = False
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE
        else: profit = (entry - ask) * lots * CONTRACT_SIZE
        last = profit
        if profit > peak: peak = profit
        if not armed and profit >= arm_threshold: armed = True
        if armed:
            if (peak - profit) >= trail_drop_after_arm: return round(profit, 2)
        if profit <= -fear_ideal: return round(profit, 2)
        if peak >= trail_trig and (peak - profit) >= trail_drop: return round(profit, 2)
    return round(last, 2)


def run(label, *, arm=3.0, drop=4.0, extra_filter=None):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars = build_1m_bars()
    bar_idx = {b[0]: i for i, b in enumerate(bars)}
    atr = compute_atr(bars, 14)
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_f_1m, _, _, _ = get_emas(34, 89, 1)
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
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is not None and t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue

        # Compute features for extra filter
        if extra_filter:
            bm = entry_time.replace(second=0, microsecond=0)
            idx = bar_idx.get(bm)
            if idx is None:
                for d in range(1, 30):
                    tt = bm - timedelta(minutes=d)
                    idx = bar_idx.get(tt)
                    if idx is not None: break
            if idx is None or idx < 89: continue
            trigger_bar = bars[idx-1] if idx > 0 else bars[idx]
            tb_body = abs(trigger_bar[4] - trigger_bar[1])
            tb_range = trigger_bar[2] - trigger_bar[3]
            tb_ratio = tb_body / max(tb_range, 0.001)
            consec = 0
            tc = 1 if trigger_bar[4] > trigger_bar[1] else -1
            for k in range(idx-1, max(idx-10, 0), -1):
                bc = 1 if bars[k][4] > bars[k][1] else -1
                if bc == tc: consec += 1
                else: break
            atr_v = atr[idx] or 0
            ema34 = ema_f_1m[idx] if idx < len(ema_f_1m) and ema_f_1m[idx] else entry_price
            ema_dist_atr = abs(entry_price - ema34) / max(atr_v, 0.01)
            features = {
                "consec": consec, "ema_dist_atr": ema_dist_atr,
                "trigger_body": tb_body, "trigger_body_ratio": tb_ratio,
                "atr": atr_v,
            }
            if not extra_filter(features): continue

        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        horizon_end = confirm_dt + timedelta(seconds=HORIZON_SEC)
        main_ticks = ticks_in_range(confirm_dt, horizon_end)
        pnl = sim_main(main_entry, dir_sign, main_ticks, arm_threshold=arm, trail_drop_after_arm=drop)
        fired += 1; total += pnl
        if pnl > 0: wins += 1; Ws.append(pnl)
        else: Ls.append(pnl)
    wr = wins / max(fired, 1) * 100
    avgW = sum(Ws) / max(len(Ws), 1)
    avgL = sum(Ls) / max(len(Ls), 1)
    maxL = min(Ls) if Ls else 0
    print(f"  {label:<60}fired={fired:<3}W={wins:<2}L={fired-wins:<2}WR={wr:>5.1f}%  total=${total:+8.2f}  avgL=${avgL:+7.2f}  maxL=${maxL:+7.2f}")


print("BASELINE: arm=$3, drop=$4")
run("baseline (arm $3, drop $4)", arm=3, drop=4)
print()
print("=" * 130)
print("METHOD A: WIDER DROP (more wiggle room before bailing)")
print("=" * 130)
for d in [3, 4, 5, 6, 7, 8, 10]:
    run(f"arm $3, drop ${d}", arm=3, drop=d)

print()
print("=" * 130)
print("METHOD B: HIGHER ARM (only protect committed moves)")
print("=" * 130)
for a in [2, 3, 4, 5, 6, 7, 8]:
    run(f"arm ${a}, drop $4", arm=a, drop=4)

print()
print("=" * 130)
print("METHOD A+B SWEEP")
print("=" * 130)
for a in [3, 4, 5, 6]:
    for d in [4, 5, 6, 7]:
        run(f"arm ${a}, drop ${d}", arm=a, drop=d)
    print()

print("=" * 130)
print("METHOD C: ADD ENTRY FILTERS (skip the trades likely to fail)")
print("Using arm=$3, drop=$4 base")
print("=" * 130)
run("+ skip consec >= 3 (exhaustion)", arm=3, drop=4,
    extra_filter=lambda f: f["consec"] < 3)
run("+ skip consec >= 4", arm=3, drop=4,
    extra_filter=lambda f: f["consec"] < 4)
run("+ skip ema_dist > 3.0", arm=3, drop=4,
    extra_filter=lambda f: f["ema_dist_atr"] <= 3.0)
run("+ skip ema_dist > 4.0", arm=3, drop=4,
    extra_filter=lambda f: f["ema_dist_atr"] <= 4.0)
run("+ skip trigger_body > 4.0", arm=3, drop=4,
    extra_filter=lambda f: f["trigger_body"] <= 4.0)
run("+ skip body_ratio 0.85-0.95 (engulfing)", arm=3, drop=4,
    extra_filter=lambda f: not (0.85 <= f["trigger_body_ratio"] <= 0.95))
run("+ skip ema_dist > 3 AND consec >= 3", arm=3, drop=4,
    extra_filter=lambda f: f["ema_dist_atr"] <= 3.0 and f["consec"] < 3)

print()
print("=" * 130)
print("METHOD D: BEST COMBOS (arm/drop tweaked + filters)")
print("=" * 130)
run("arm $4, drop $5 + ema_dist <= 3", arm=4, drop=5,
    extra_filter=lambda f: f["ema_dist_atr"] <= 3.0)
run("arm $4, drop $6 + ema_dist <= 3", arm=4, drop=6,
    extra_filter=lambda f: f["ema_dist_atr"] <= 3.0)
run("arm $5, drop $5 + ema_dist <= 3", arm=5, drop=5,
    extra_filter=lambda f: f["ema_dist_atr"] <= 3.0)
run("arm $5, drop $6 + ema_dist <= 3", arm=5, drop=6,
    extra_filter=lambda f: f["ema_dist_atr"] <= 3.0)
run("arm $3, drop $5 + consec < 3 + ema_dist <= 3", arm=3, drop=5,
    extra_filter=lambda f: f["consec"] < 3 and f["ema_dist_atr"] <= 3.0)
run("arm $4, drop $5 + consec < 3 + ema_dist <= 3", arm=4, drop=5,
    extra_filter=lambda f: f["consec"] < 3 and f["ema_dist_atr"] <= 3.0)
run("arm $5, drop $5 + consec < 3 + ema_dist <= 3", arm=5, drop=5,
    extra_filter=lambda f: f["consec"] < 3 and f["ema_dist_atr"] <= 3.0)
