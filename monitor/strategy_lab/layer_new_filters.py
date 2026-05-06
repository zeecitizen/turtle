"""layer_new_filters.py — apply new feature filters on top of winning combo.

Winning combo so far: skipBadHours + trendFilter + skipFastConfirm
  → 22 fires, 90.9% WR, +$417.20

New filters to test (from advanced_features.py):
  A. skipExhaustion: consec_same_color_before >= 3
  B. skipOverstretched: ema_dist_atr_ratio > 3.0
  C. skipBigBody: trigger_body_pts > 4.0
  D. skipEngulfing: 0.85 <= trigger_body_ratio <= 0.95
  E. skipBadSpread: entry_spread > 25pts
  F. preferConsec2: REQUIRE consec_same_color_before == 2 (very narrow)

Tests every single layer + 2-layer + 3-layer combo on top of winning base.
"""

from __future__ import annotations
import csv
from datetime import datetime, timedelta
from collections import defaultdict
import sys
from pathlib import Path

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    build_1m_bars, get_emas, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE,
)
from advanced_features import compute_atr

# Winning combo params
PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
FEAR_IDEAL = 50.0
PROBE_LOTS = 0.01
MAIN_LOTS = 0.40
HORIZON_SEC = 600


def trend_at(when, ema_fast, ema_slow, bar_idx):
    bm = when.replace(second=0, microsecond=0)
    idx = bar_idx.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < 89: return None
    f = ema_fast[idx]; s = ema_slow[idx]; fp = ema_fast[idx-1]
    if f is None or s is None or fp is None: return None
    if f > s and f > fp: return 1
    if f < s and f < fp: return -1
    return 0


def compute_all_features():
    """Compute features for every probe that confirms (no filters yet)."""
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars = build_1m_bars()
    bar_idx = {b[0]: i for i, b in enumerate(bars)}
    atr = compute_atr(bars, 14)
    ema_f, ema_s, _, _ = get_emas(34, 89)

    feats = []
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
        confirm_fav = 0.0
        entry_spread = None
        for dt, bid, ask in ticks:
            if entry_spread is None:
                entry_spread = (ask - bid)
            if dir_sign == 1:
                fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else:
                fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt, confirm_bid, confirm_ask, confirm_fav = dt, bid, ask, fav
                confirm_speed = (dt - entry_time).total_seconds()
                break
        if confirm_dt is None: continue

        bm = entry_time.replace(second=0, microsecond=0)
        idx = bar_idx.get(bm)
        if idx is None:
            for d in range(1, 30):
                t = bm - timedelta(minutes=d)
                idx = bar_idx.get(t)
                if idx is not None: break
        if idx is None or idx < 89: continue

        trigger_bar = bars[idx - 1] if idx > 0 else bars[idx]
        trigger_body = abs(trigger_bar[4] - trigger_bar[1])
        trigger_range = trigger_bar[2] - trigger_bar[3]
        trigger_body_ratio = trigger_body / max(trigger_range, 0.001)

        consec = 0
        target_color = 1 if trigger_bar[4] > trigger_bar[1] else -1
        for k in range(idx-1, max(idx-10, 0), -1):
            bc = 1 if bars[k][4] > bars[k][1] else -1
            if bc == target_color: consec += 1
            else: break

        atr_val = atr[idx]
        ema34 = ema_f[idx]
        ema_dist_pts = abs(entry_price - ema34) if ema34 else 0
        ema_dist_atr_ratio = ema_dist_pts / max(atr_val or 0.01, 0.01)

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
        main_pnl = round(last_profit, 2)

        # Apply winning combo base filters
        h = confirm_dt.hour
        bad_hour = (4 <= h <= 6) or (21 <= h <= 23)
        trend = trend_at(confirm_dt, ema_f, ema_s, bar_idx)
        against_trend = (trend is not None and trend != 0 and trend != dir_sign)
        fast_confirm = 3 <= confirm_speed <= 8

        in_winning_combo = not (bad_hour or against_trend or fast_confirm)

        feats.append({
            "entry_time": entry_time,
            "dir_sign": dir_sign,
            "main_pnl": main_pnl,
            "win": main_pnl > 0,
            "consec": consec,
            "ema_dist_atr_ratio": ema_dist_atr_ratio,
            "trigger_body_pts": trigger_body,
            "trigger_body_ratio": trigger_body_ratio,
            "entry_spread_pts": (entry_spread or 0),
            "atr_pts": atr_val or 0,
            "confirm_speed": confirm_speed,
            "confirm_fav_dollars": confirm_fav,
            "in_winning_combo": in_winning_combo,
        })
    return feats


def evaluate(feats, name, predicate=None):
    """Apply optional extra predicate on top of winning combo. Predicate returns True to KEEP."""
    sub = [f for f in feats if f["in_winning_combo"]]
    if predicate:
        sub = [f for f in sub if predicate(f)]
    n = len(sub)
    wins = sum(1 for f in sub if f["win"])
    total = sum(f["main_pnl"] for f in sub)
    wr = wins / max(n, 1) * 100
    return {"name": name, "n": n, "wins": wins, "wr": wr, "total": total}


def fmt(r):
    return f"  {r['name']:<60}fired={r['n']:<3} wins={r['wins']:<3}WR={r['wr']:>5.1f}%  total=${r['total']:+8.2f}"


def main():
    feats = compute_all_features()
    print(f"Total confirmed probes: {len(feats)}")
    base = [f for f in feats if f["in_winning_combo"]]
    print(f"In winning combo (hour+trend+fast): {len(base)}")
    print()

    print("=" * 90)
    print("BASELINE (winning combo, no extra filters)")
    print("=" * 90)
    print(fmt(evaluate(feats, "baseline (hour+trend+fast)")))
    print()

    # Predicates: True = KEEP the trade
    candidates = [
        ("+ skip consec >= 3 (exhaustion)",
         lambda f: f["consec"] < 3),
        ("+ skip consec >= 4",
         lambda f: f["consec"] < 4),
        ("+ skip ema_dist_atr > 3.0 (overstretched)",
         lambda f: f["ema_dist_atr_ratio"] <= 3.0),
        ("+ skip ema_dist_atr > 4.0",
         lambda f: f["ema_dist_atr_ratio"] <= 4.0),
        ("+ skip ema_dist_atr > 2.0 (only close to EMA)",
         lambda f: f["ema_dist_atr_ratio"] <= 2.0),
        ("+ skip trigger_body > 4.0pt (climax)",
         lambda f: f["trigger_body_pts"] <= 4.0),
        ("+ skip trigger_body > 3.0pt",
         lambda f: f["trigger_body_pts"] <= 3.0),
        ("+ skip body_ratio 0.85-0.95 (engulfing)",
         lambda f: not (0.85 <= f["trigger_body_ratio"] <= 0.95)),
        ("+ skip entry_spread > 25pts",
         lambda f: f["entry_spread_pts"] <= 0.25),
        ("+ skip entry_spread > 30pts",
         lambda f: f["entry_spread_pts"] <= 0.30),
        ("+ require body_ratio >= 0.5 AND <= 0.85 (clean candle)",
         lambda f: 0.5 <= f["trigger_body_ratio"] <= 0.85),
        ("+ require ATR >= 0.8",
         lambda f: f["atr_pts"] >= 0.8),
    ]

    print("=" * 90)
    print("SINGLE NEW FILTER LAYER")
    print("=" * 90)
    results = []
    for name, pred in candidates:
        r = evaluate(feats, name, pred)
        results.append((name, pred, r))
        print(fmt(r))

    # Best 2-filter combos: pair top single filters
    print()
    print("=" * 90)
    print("2-FILTER COMBOS")
    print("=" * 90)
    combos = [
        ("+ consec<3 + ema_dist<=3.0",
         lambda f: f["consec"] < 3 and f["ema_dist_atr_ratio"] <= 3.0),
        ("+ consec<3 + body<=4.0",
         lambda f: f["consec"] < 3 and f["trigger_body_pts"] <= 4.0),
        ("+ consec<3 + spread<=25",
         lambda f: f["consec"] < 3 and f["entry_spread_pts"] <= 0.25),
        ("+ consec<3 + skip body_ratio 0.85-0.95",
         lambda f: f["consec"] < 3 and not (0.85 <= f["trigger_body_ratio"] <= 0.95)),
        ("+ ema_dist<=3.0 + body<=4.0",
         lambda f: f["ema_dist_atr_ratio"] <= 3.0 and f["trigger_body_pts"] <= 4.0),
        ("+ ema_dist<=3.0 + spread<=25",
         lambda f: f["ema_dist_atr_ratio"] <= 3.0 and f["entry_spread_pts"] <= 0.25),
        ("+ ema_dist<=3.0 + skip engulfing",
         lambda f: f["ema_dist_atr_ratio"] <= 3.0 and not (0.85 <= f["trigger_body_ratio"] <= 0.95)),
        ("+ spread<=25 + skip engulfing",
         lambda f: f["entry_spread_pts"] <= 0.25 and not (0.85 <= f["trigger_body_ratio"] <= 0.95)),
    ]
    for name, pred in combos:
        print(fmt(evaluate(feats, name, pred)))

    # Triple combos: top three signals
    print()
    print("=" * 90)
    print("3-FILTER COMBOS (full belt-and-braces)")
    print("=" * 90)
    triples = [
        ("+ consec<3 + ema_dist<=3.0 + spread<=25",
         lambda f: f["consec"] < 3 and f["ema_dist_atr_ratio"] <= 3.0 and f["entry_spread_pts"] <= 0.25),
        ("+ consec<3 + ema_dist<=3.0 + skip engulfing",
         lambda f: f["consec"] < 3 and f["ema_dist_atr_ratio"] <= 3.0 and not (0.85 <= f["trigger_body_ratio"] <= 0.95)),
        ("+ consec<3 + body<=4.0 + skip engulfing",
         lambda f: f["consec"] < 3 and f["trigger_body_pts"] <= 4.0 and not (0.85 <= f["trigger_body_ratio"] <= 0.95)),
        ("+ ema_dist<=3.0 + body<=4.0 + spread<=25",
         lambda f: f["ema_dist_atr_ratio"] <= 3.0 and f["trigger_body_pts"] <= 4.0 and f["entry_spread_pts"] <= 0.25),
        ("+ ALL 4: consec<3 + ema_dist<=3 + body<=4 + spread<=25",
         lambda f: f["consec"] < 3 and f["ema_dist_atr_ratio"] <= 3.0 and f["trigger_body_pts"] <= 4.0 and f["entry_spread_pts"] <= 0.25),
    ]
    for name, pred in triples:
        print(fmt(evaluate(feats, name, pred)))


if __name__ == "__main__":
    main()
