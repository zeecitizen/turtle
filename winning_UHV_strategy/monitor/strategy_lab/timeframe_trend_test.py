"""timeframe_trend_test.py — does a higher-timeframe trend filter give better WR?

Hypothesis: 5-min EMA trend is more stable than 1-min. Test by replacing
the trend check with EMAs computed on 2-min, 3-min, 5-min bars.

Probe trigger logic stays on tick level (Shano's pattern is 1-min). Only the
TREND FILTER timeframe changes.
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
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, compute_ema,
)

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
FEAR_IDEAL = 50.0
PROBE_LOTS = 0.01
MAIN_LOTS = 0.40
HORIZON_SEC = 600


def aggregate_to_tf(bars_1m, minutes):
    """Aggregate 1-min bars into N-min bars."""
    out = []
    cur_start = None; o = h = l = c = None
    for dt, b_o, b_h, b_l, b_c in bars_1m:
        anchor_min = (dt.minute // minutes) * minutes
        bm = dt.replace(minute=anchor_min, second=0, microsecond=0)
        if cur_start is None:
            cur_start = bm; o = b_o; h = b_h; l = b_l; c = b_c
        elif bm != cur_start:
            out.append((cur_start, o, h, l, c))
            cur_start = bm; o = b_o; h = b_h; l = b_l; c = b_c
        else:
            if b_h > h: h = b_h
            if b_l < l: l = b_l
            c = b_c
    if cur_start is not None: out.append((cur_start, o, h, l, c))
    return out


def trend_at_tf(when, ema_fast, ema_slow, bar_idx, tf_minutes):
    """Trend at given time on timeframe with tf_minutes bars. Returns +1/-1/0/None."""
    anchor = when.minute - (when.minute % tf_minutes)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf_minutes * d)
            idx = bar_idx.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < 89: return None
    f = ema_fast[idx]; s = ema_slow[idx]; fp = ema_fast[idx-1]
    if f is None or s is None or fp is None: return None
    if f > s and f > fp: return 1
    if f < s and f < fp: return -1
    return 0


def run_with_tf_trend(tf_minutes, name, skipBadHours=True, skipFastConfirm=True):
    bars_1m = build_1m_bars()
    if tf_minutes == 1:
        bars = bars_1m
    else:
        bars = aggregate_to_tf(bars_1m, tf_minutes)
    closes = [b[4] for b in bars]
    ema_f = compute_ema(closes, 34)
    ema_s = compute_ema(closes, 89)
    bar_idx = {b[0]: i for i, b in enumerate(bars)}

    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    fired = 0; wins = 0; total = 0.0
    skipped_no_conf = 0; skipped_filt = 0
    big_losses = 0; max_loss = 0
    daily = defaultdict(float)

    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue

        # Confirm walk
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
                confirm_speed = (dt - entry_time).total_seconds()
                break
        if confirm_dt is None:
            skipped_no_conf += 1; continue

        # Filters
        skip = False
        if skipBadHours:
            h = confirm_dt.hour
            if (4 <= h <= 6) or (21 <= h <= 23): skip = True
        if not skip:
            t = trend_at_tf(confirm_dt, ema_f, ema_s, bar_idx, tf_minutes)
            if t is None: pass  # be lenient if no data
            elif t != dir_sign: skip = True
        if not skip and skipFastConfirm:
            if 3 <= confirm_speed <= 8: skip = True

        if skip:
            skipped_filt += 1; continue

        # Sim main
        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        horizon_end = confirm_dt + timedelta(seconds=HORIZON_SEC)
        main_ticks = ticks_in_range(confirm_dt, horizon_end)
        peak = 0.0; last_profit = 0.0
        for dt, bid, ask in main_ticks:
            if dir_sign == 1:
                profit = (bid - main_entry) * MAIN_LOTS * CONTRACT_SIZE
            else:
                profit = (main_entry - ask) * MAIN_LOTS * CONTRACT_SIZE
            last_profit = profit
            if profit > peak: peak = profit
            if profit <= -FEAR_IDEAL: break
            if peak >= TRAIL_TRIGGER and (peak - profit) >= TRAIL_DROP: break
        pnl = round(last_profit, 2)
        fired += 1
        if pnl > 0: wins += 1
        if pnl <= -30: big_losses += 1
        if pnl < max_loss: max_loss = pnl
        total += pnl
        daily[entry_time.strftime("%Y-%m-%d")] += pnl

    wr = wins / max(fired, 1) * 100
    daily_str = " | ".join(f"{d[-5:]}:${p:+.0f}" for d, p in sorted(daily.items()))
    print(f"  {name:<55}fired={fired:<3}filt_out={skipped_filt:<3}WR={wr:>5.1f}%  total=${total:+8.2f}  big_L={big_losses:<2}  max_L=${max_loss:>7.2f}  daily=[{daily_str}]")
    return {"tf": tf_minutes, "fired": fired, "wins": wins, "wr": wr, "total": total, "big_L": big_losses}


print("=" * 180)
print("TIMEFRAME TREND FILTER COMPARISON")
print("All other filters fixed: skipBadHours=True, skipFastConfirm=True, EMA-34/89")
print("Only the TIMEFRAME of the EMA trend check changes")
print("=" * 180)
results = []
for tf in [1, 2, 3, 5, 10, 15]:
    r = run_with_tf_trend(tf, f"trend on {tf}-min EMA-34/89")
    results.append(r)

print()
print("=" * 180)
print("WITHOUT skipFastConfirm (just hour + N-min trend)")
print("=" * 180)
for tf in [1, 2, 3, 5, 10, 15]:
    run_with_tf_trend(tf, f"trend on {tf}-min EMA-34/89 (no fast skip)", skipFastConfirm=False)

print()
print("=" * 180)
print("ONLY trend filter (no hour, no fast — pure trend test)")
print("=" * 180)
for tf in [1, 2, 3, 5, 10, 15]:
    run_with_tf_trend(tf, f"trend on {tf}-min EMA-34/89 (trend ONLY)",
                      skipBadHours=False, skipFastConfirm=False)
