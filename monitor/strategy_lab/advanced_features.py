"""
advanced_features.py — mine new probe features for higher-WR predictors.

Tests features beyond what feature_analyzer found:
  1. ATR(14) at probe time — volatility regime
  2. Trigger candle body size (the BIG candle that fired the signal)
  3. Spread at probe entry vs at confirm (slippage indicator)
  4. Consecutive same-color bars before probe (trend strength)
  5. Recent realized volatility (last 5/10 min)
  6. Distance from EMA-34 (momentum stretch)
  7. EMA-34 slope strength (rate of change)
  8. Combined: "perfect probe" features

Goal: find the 95%+ WR slice or new filters to layer onto winning combo.
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
    Config, run, build_1m_bars, get_emas, ticks_in_range,
    SHADOW_CSV, CONTRACT_SIZE,
)

PROBE_CONFIRM = 0.45
PROBE_LOTS = 0.01
MAIN_LOTS = 0.40
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
FEAR_IDEAL = 50.0
HORIZON_SEC = 600


def compute_atr(bars, period=14):
    n = len(bars)
    tr = [0.0] * n
    for i in range(1, n):
        h = bars[i][2]; l = bars[i][3]; pc = bars[i-1][4]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    atr = [None] * n
    if n <= period: return atr
    seed = sum(tr[1:period+1]) / period
    atr[period] = seed
    prev = seed
    for i in range(period+1, n):
        prev = (prev * (period - 1) + tr[i]) / period
        atr[i] = prev
    return atr


def compute_features():
    """Per-confirmed-probe feature dict + sim main outcome."""
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars = build_1m_bars()
    closes = [b[4] for b in bars]
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

        # Walk to confirm
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

        # Find bar index at entry
        bm = entry_time.replace(second=0, microsecond=0)
        idx = bar_idx.get(bm)
        if idx is None:
            for d in range(1, 30):
                t = bm - timedelta(minutes=d)
                idx = bar_idx.get(t)
                if idx is not None: break
        if idx is None or idx < 89: continue

        # Trigger candle: the bar BEFORE entry (the "big bar" trigger)
        trigger_bar = bars[idx - 1] if idx > 0 else bars[idx]
        trigger_body = abs(trigger_bar[4] - trigger_bar[1])
        trigger_range = trigger_bar[2] - trigger_bar[3]
        trigger_body_ratio = trigger_body / max(trigger_range, 0.001)

        # Consecutive same-color bars before entry
        consec = 0
        target_color = 1 if trigger_bar[4] > trigger_bar[1] else -1
        for k in range(idx-1, max(idx-10, 0), -1):
            bc = 1 if bars[k][4] > bars[k][1] else -1
            if bc == target_color: consec += 1
            else: break

        # ATR at entry
        atr_val = atr[idx]
        atr_recent = sum(c for c in atr[max(0,idx-5):idx+1] if c is not None) / max(1, sum(1 for c in atr[max(0,idx-5):idx+1] if c is not None))

        # Distance from EMA-34
        ema34 = ema_f[idx]
        ema_dist_pts = abs(entry_price - ema34) if ema34 else 0
        ema_dist_atr_ratio = ema_dist_pts / max(atr_val or 0.01, 0.01)

        # EMA slope (rate of change over 3 bars)
        ema34_3ago = ema_f[idx-3] if idx >= 3 else None
        ema_slope = (ema34 - ema34_3ago) if (ema34 and ema34_3ago) else 0

        # Spread at entry vs confirm
        confirm_spread = confirm_ask - confirm_bid if confirm_ask else 0
        spread_widen = confirm_spread - (entry_spread or 0)

        # Trigger candle direction matches probe direction?
        trigger_dir_match = (target_color == dir_sign)

        # Recent volatility — sum of |close - open| over last 5 bars
        recent_vol = sum(abs(bars[k][4] - bars[k][1]) for k in range(max(0, idx-5), idx)) / 5

        # Now simulate the main
        main_entry = confirm_ask if dir_sign == 1 else confirm_bid
        horizon_end = confirm_dt + timedelta(seconds=HORIZON_SEC)
        main_ticks = ticks_in_range(confirm_dt, horizon_end)
        peak = 0.0; last_profit = 0.0
        exit_reason = "horizon"
        for dt, bid, ask in main_ticks:
            if dir_sign == 1:
                profit = (bid - main_entry) * MAIN_LOTS * CONTRACT_SIZE
            else:
                profit = (main_entry - ask) * MAIN_LOTS * CONTRACT_SIZE
            last_profit = profit
            if profit > peak: peak = profit
            if profit <= -FEAR_IDEAL: exit_reason = "fearIdeal"; break
            if peak >= TRAIL_TRIGGER and (peak - profit) >= TRAIL_DROP: exit_reason = "trail"; break
        main_pnl = round(last_profit, 2)
        win = main_pnl > 0

        feats.append({
            "entry_time": entry_time, "dir": r["dir"], "dir_sign": dir_sign,
            "main_pnl": main_pnl, "win": win, "exit_reason": exit_reason,
            "hour": entry_time.hour,
            "trigger_body_pts": round(trigger_body, 3),
            "trigger_body_ratio": round(trigger_body_ratio, 3),
            "trigger_dir_match": trigger_dir_match,
            "consec_same_color_before": consec,
            "atr_pts": round(atr_val or 0, 3),
            "atr_recent_pts": round(atr_recent, 3),
            "ema_dist_pts": round(ema_dist_pts, 3),
            "ema_dist_atr_ratio": round(ema_dist_atr_ratio, 2),
            "ema_slope": round(ema_slope, 4),
            "confirm_speed_sec": round(confirm_speed, 1),
            "confirm_fav_cents": round(confirm_fav * 100, 1),
            "entry_spread_pts": round(entry_spread or 0, 3),
            "confirm_spread_pts": round(confirm_spread, 3),
            "spread_widen_pts": round(spread_widen, 3),
            "recent_vol_pts": round(recent_vol, 3),
        })

    return feats


def bin_analyze(feats, name, key, bins, labels=None, baseline_wr=0):
    groups = defaultdict(list)
    for f in feats:
        v = f.get(key)
        if v is None: continue
        for i, edge in enumerate(bins):
            if v <= edge:
                groups[labels[i] if labels else f"<= {edge}"].append(f)
                break
        else:
            groups[labels[-1] if labels else f"> {bins[-1]}"].append(f)
    print(f"\n  === {name} ===")
    print(f"  {'bin':<22}{'n':<5}{'wins':<6}{'WR%':<8}{'avg':<10}")
    order = labels if labels else [f"<= {e}" for e in bins] + [f"> {bins[-1]}"]
    for label in order:
        grp = groups.get(label, [])
        if not grp: continue
        n = len(grp); w = sum(1 for f in grp if f["win"])
        wr = w/n*100; avg = sum(f["main_pnl"] for f in grp) / n
        marker = " <-- HIGH" if wr >= baseline_wr + 12 else " <-- LOW" if wr <= baseline_wr - 12 else ""
        print(f"  {label:<22}{n:<5}{w:<6}{wr:<8.1f}${avg:+8.2f}{marker}")


def cat_analyze(feats, name, key, baseline_wr=0):
    groups = defaultdict(list)
    for f in feats: groups[str(f.get(key))].append(f)
    print(f"\n  === {name} ===")
    print(f"  {'value':<22}{'n':<5}{'wins':<6}{'WR%':<8}{'avg':<10}")
    for k in sorted(groups.keys()):
        grp = groups[k]
        n = len(grp); w = sum(1 for f in grp if f["win"])
        wr = w/n*100; avg = sum(f["main_pnl"] for f in grp) / n
        marker = " <-- HIGH" if wr >= baseline_wr + 12 else " <-- LOW" if wr <= baseline_wr - 12 else ""
        print(f"  {k:<22}{n:<5}{w:<6}{wr:<8.1f}${avg:+8.2f}{marker}")


def main():
    feats = compute_features()
    n = len(feats)
    wins = [f for f in feats if f["win"]]
    base_wr = len(wins) / max(n, 1) * 100
    print(f"Confirmed probes with full features: {n}")
    print(f"Baseline WR: {base_wr:.1f}%")

    print("=" * 80)
    print("NEW FEATURE BUCKETS — looking for predictors")
    print("=" * 80)

    bin_analyze(feats, "trigger_body (points)", "trigger_body_pts",
                [0.5, 1.0, 1.5, 2.5, 4.0],
                ["<=0.5", "0.5-1.0", "1.0-1.5", "1.5-2.5", "2.5-4.0", ">4.0"], base_wr)
    bin_analyze(feats, "trigger_body_ratio (body/range)", "trigger_body_ratio",
                [0.5, 0.7, 0.85, 0.95],
                ["<=0.5", "0.5-0.7", "0.7-0.85", "0.85-0.95", ">0.95"], base_wr)
    cat_analyze(feats, "trigger_dir_match (trigger color = probe dir)",
                "trigger_dir_match", base_wr)
    bin_analyze(feats, "consec_same_color_before",
                "consec_same_color_before", [0, 1, 2, 4],
                ["0", "1", "2", "3-4", ">4"], base_wr)
    bin_analyze(feats, "ATR pts (volatility regime)",
                "atr_pts", [0.5, 1.0, 1.5, 2.5],
                ["<=0.5", "0.5-1.0", "1.0-1.5", "1.5-2.5", ">2.5"], base_wr)
    bin_analyze(feats, "ema_dist_atr_ratio (stretch from EMA34)",
                "ema_dist_atr_ratio", [0.5, 1.0, 2.0, 4.0],
                ["<=0.5", "0.5-1.0", "1.0-2.0", "2.0-4.0", ">4.0"], base_wr)
    bin_analyze(feats, "confirm_fav_cents (probe MFE at confirm)",
                "confirm_fav_cents", [50, 60, 80, 120],
                ["<=50c", "50-60c", "60-80c", "80-120c", ">120c"], base_wr)
    bin_analyze(feats, "entry_spread_pts (XAUUSD spread at probe entry)",
                "entry_spread_pts", [0.15, 0.25, 0.40, 0.60],
                ["<=15", "15-25", "25-40", "40-60", ">60"], base_wr)
    bin_analyze(feats, "spread_widen_pts (delta from entry to confirm)",
                "spread_widen_pts", [-0.05, 0.0, 0.05, 0.20],
                ["narrowed", "no_change", "widen<5pts", "widen5-20", "widen>20"], base_wr)
    bin_analyze(feats, "recent_vol_pts (avg body last 5 bars)",
                "recent_vol_pts", [0.3, 0.5, 0.8, 1.5],
                ["<=0.3", "0.3-0.5", "0.5-0.8", "0.8-1.5", ">1.5"], base_wr)

    # Combined "perfect probe" — find slices with very high WR
    print()
    print("=" * 80)
    print("HIGH-WR SLICES (compound conditions)")
    print("=" * 80)
    slices = [
        ("Trigger body >= 1.5pt + dir_match",
         lambda f: f["trigger_body_pts"] >= 1.5 and f["trigger_dir_match"]),
        ("Trigger body_ratio >= 0.85 + dir_match",
         lambda f: f["trigger_body_ratio"] >= 0.85 and f["trigger_dir_match"]),
        ("Consec same color >= 2 + trigger >= 1.0pt",
         lambda f: f["consec_same_color_before"] >= 2 and f["trigger_body_pts"] >= 1.0),
        ("ATR >= 1.0 (good vol) + trigger >= 1.0",
         lambda f: (f["atr_pts"] or 0) >= 1.0 and f["trigger_body_pts"] >= 1.0),
        ("Spread <= 25pts at entry + trigger >= 1.0",
         lambda f: (f["entry_spread_pts"] or 99) <= 0.25 and f["trigger_body_pts"] >= 1.0),
        ("Confirm MFE >= 60c (not in dead zone)",
         lambda f: f["confirm_fav_cents"] >= 60),
        ("Confirm MFE >= 80c (strong probe)",
         lambda f: f["confirm_fav_cents"] >= 80),
        ("trigger_body_ratio >= 0.85 + ATR >= 0.8",
         lambda f: f["trigger_body_ratio"] >= 0.85 and (f["atr_pts"] or 0) >= 0.8),
        ("ALL: body>=1.5 + dir_match + spread<=25 + ATR>=0.8",
         lambda f: f["trigger_body_pts"] >= 1.5 and f["trigger_dir_match"]
                   and (f["entry_spread_pts"] or 99) <= 0.25
                   and (f["atr_pts"] or 0) >= 0.8),
    ]
    print(f"  {'condition':<60}{'n':<5}{'wins':<6}{'WR%':<8}{'avg':<10}{'total':<10}")
    for name, pred in slices:
        sub = [f for f in feats if pred(f)]
        n_s = len(sub); w = sum(1 for f in sub if f["win"])
        if n_s == 0:
            print(f"  {name:<60}n=0"); continue
        wr = w/n_s*100; avg = sum(f["main_pnl"] for f in sub) / n_s
        total = sum(f["main_pnl"] for f in sub)
        marker = " *** PROMISING ***" if wr >= 90 and n_s >= 10 else ""
        print(f"  {name:<60}{n_s:<5}{w:<6}{wr:<8.1f}${avg:+8.2f}${total:+8.2f}{marker}")


if __name__ == "__main__":
    main()
