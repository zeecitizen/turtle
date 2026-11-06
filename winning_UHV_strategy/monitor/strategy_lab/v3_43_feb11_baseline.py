"""v3.43 baseline validation against Zee's 20 Feb 11 textbook entries.

Goal: make sure dropping the volume check + non-fatal lookback doesn't tank
Zee's reference day. Compares v3.42 strict vs v3.43 relax on Feb 11 02:00-21:00.
"""
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

from v3_43_relax_sim import load_bars, simulate, M1_CSV

ZEE_TRADES = [
    ("01:59:04", "buy",  6.65),
    ("02:09:38", "sell", 11.69),
    ("02:29:02", "buy",  20.01),
    ("16:49:07", "buy",  17.12),
    ("16:52:21", "buy",  8.85),
    ("16:54:10", "buy",  8.26),
    ("16:58:03", "buy",  5.73),
    ("17:02:45", "buy",  54.93),
    ("17:36:11", "buy",  3.29),
    ("17:36:13", "buy",  14.50),
    ("17:37:26", "buy",  7.08),
    ("17:49:59", "buy",  52.78),
    ("18:24:18", "buy",  8.51),
    ("18:41:50", "buy",  -1.43),
    ("19:20:34", "sell", 14.21),
    ("19:26:06", "sell", 14.55),
    ("19:29:31", "buy",  0.84),
    ("19:36:19", "buy",  10.60),
    ("19:38:39", "buy",  11.02),
    ("19:38:59", "buy",  0.92),
]


def evaluate(trades, name):
    matched = set()
    captured = 0
    for st, side, _pnl in ZEE_TRADES:
        zt = datetime(2026, 2, 11, int(st[:2]), int(st[3:5]), int(st[6:8]))
        best = None; best_gap = timedelta(minutes=99); best_idx = None
        for i, t in enumerate(trades):
            if i in matched: continue
            if t["side"] != side: continue
            gap = abs(t["entry_time"] - zt)
            if gap < timedelta(minutes=5) and gap < best_gap:
                best, best_gap, best_idx = t, gap, i
        if best:
            matched.add(best_idx); captured += 1
    total = sum(t["close_pnl"] for t in trades)
    wins = sum(1 for t in trades if t["close_pnl"] > 0)
    losses = sum(1 for t in trades if t["close_pnl"] < 0)
    wr = 100 * wins / (wins + losses) if (wins + losses) else 0
    print(f"{name:<40}: fires={len(trades):<5}  captured Zee={captured:>2}/{len(ZEE_TRADES)}  WR={wr:.0f}%  P&L=${total:+.2f}")


def main():
    bars = load_bars(M1_CSV)
    start = datetime(2026, 2, 11, 1, 0)
    end = datetime(2026, 2, 11, 21, 0)
    has_feb11 = any(b["time"].date() == start.date() for b in bars)
    if not has_feb11:
        print("ERROR: no Feb 11 bars in CSV")
        return

    modes = [
        ("v3.42 (strict vol + break)", {"mode_strict_vol": True,  "mode_break": True,  "mode_color": True}),
        ("v3.43 (drop vol + relax break)", {"mode_strict_vol": False, "mode_break": False, "mode_color": True}),
    ]
    print(f"Zee: {len(ZEE_TRADES)} textbook entries on Feb 11 (01:00-21:00)\n")
    for name, mode in modes:
        trades = simulate(bars, start, end, mode)
        evaluate(trades, name)


if __name__ == "__main__":
    main()
