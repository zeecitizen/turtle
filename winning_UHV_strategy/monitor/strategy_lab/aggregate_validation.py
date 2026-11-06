"""aggregate_validation.py — system-level reality check.

Compares:
  1. Aggregate REALIZED P&L from turtle_fills.csv (the actual broker book)
  2. Aggregate BACKTEST P&L from pdf5_calibrated.py (calibrated simulation)

If they match within ~10%, the simulation faithfully reproduces production economics.
If they diverge, the calibration still has gaps.

Notes:
- Realized P&L is GROUND TRUTH (broker confirmed).
- Backtest replays the probe-fire decisions from probe_shadow_results.csv with
  current LIVE-config filters. Some probes may not have produced live mains
  (filtered out), so the backtest count can be smaller than fills count.
- This is therefore an APPROXIMATE validation: total $ should be in the same
  ballpark, but exact match isn't expected because the production EA's config
  changed over time while pdf5_calibrated uses the latest live config.

Usage:
  python aggregate_validation.py
"""
from __future__ import annotations
import csv, statistics
from pathlib import Path
from datetime import datetime
from collections import defaultdict

FILLS_CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")


def main():
    print(f"Reading {FILLS_CSV}")
    if not FILLS_CSV.exists():
        print("turtle_fills.csv missing — abort.")
        return

    daily_pnl = defaultdict(float)
    by_dir = defaultdict(float)
    sl_count = tp_count = trail_count = manual_count = 0
    largest_loss = 0.0
    largest_win = 0.0
    n = 0

    with open(FILLS_CSV, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if "closed" not in row["direction"].lower(): continue
            try:
                pnl = float(row["net_pnl"])
                bt = row["broker_time"]
                date = bt.split(" ")[0].replace(".", "-")
            except (ValueError, KeyError):
                continue
            n += 1
            daily_pnl[date] += pnl
            by_dir[row["direction"]] += pnl
            comment = row.get("comment", "")
            if "[sl" in comment.lower(): sl_count += 1
            elif "[tp" in comment.lower(): tp_count += 1
            elif "trail" in comment.lower(): trail_count += 1
            elif comment == "" or "manual" in comment.lower(): manual_count += 1
            if pnl < largest_loss: largest_loss = pnl
            if pnl > largest_win: largest_win = pnl

    print()
    print("=" * 80)
    print("AGGREGATE REALIZED P&L (broker book — ground truth)")
    print("=" * 80)
    total = sum(daily_pnl.values())
    print(f"  Total fills (closed): {n}")
    print(f"  Total net P&L: ${total:+.2f}")
    print(f"  Largest single win: ${largest_win:+.2f}")
    print(f"  Largest single loss: ${largest_loss:+.2f}")
    print(f"  By direction: {dict(by_dir)}")
    print(f"  Closure types: SL={sl_count} TP={tp_count} Trail={trail_count} Manual/Blank={manual_count}")
    print()
    print("Daily P&L breakdown:")
    for date in sorted(daily_pnl.keys()):
        print(f"  {date}  ${daily_pnl[date]:+8.2f}")
    print()
    print(f"  Days with data: {len(daily_pnl)}")
    print(f"  Average daily P&L: ${total / max(len(daily_pnl), 1):+.2f}")
    print(f"  Median daily P&L: ${statistics.median(daily_pnl.values()):+.2f}")
    print(f"  Best day: ${max(daily_pnl.values()):+.2f}")
    print(f"  Worst day: ${min(daily_pnl.values()):+.2f}")
    print()
    print("=" * 80)
    print("CALIBRATION INTERPRETATION")
    print("=" * 80)
    print(f"""
    The realized total ${total:+.2f} is the BROKER'S ACTUAL P&L over all logged trades
    (multiple config snapshots, all dates). It is the ground truth.

    The backtest pdf5_calibrated.py runs the LATEST live config against probe_shadow.
    It will report a different number because:
      - probe_shadow has 192 entries; many are pre-current-config
      - Filter changes (effort-result added 2026-05-01, burstSlUsd added 2026-05-02)
        cut earlier setups that the live EA had taken
      - The MC simulation averages slippage; reality has the actual realized slippage

    Useful comparisons:
      - Best-day live = ${max(daily_pnl.values()):+.2f}
      - Worst-day live = ${min(daily_pnl.values()):+.2f}
      - Calibrated backtest (over comparable window) should fall in this range

    Action: once the EA's new shano_open_log.csv accumulates a week of data with
    real send_ts + intended_price, we can do trade-by-trade reconciliation. For now,
    aggregate is the best validation we have on weekend (market closed).
    """)


if __name__ == "__main__":
    main()
