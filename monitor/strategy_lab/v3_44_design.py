"""Classify the remaining 9 Shano misses under v3.43 relaxed detector.

For each missed Shano fire:
  - What bar did she fire on (M1 OHLC)
  - What color is that bar (green/red)
  - What does v3.43 detector say if we ASK for the opposite side too
  - What does v3.43 detector say if we let it use bar.high/low instead of close
  - Could a "tick-driven" version (intra-bar) catch it
"""
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

from v3_43_relax_sim import load_bars, simulate, M1_CSV, SHANO_SETUPS, detect_relaxed


def main():
    bars = load_bars(M1_CSV)
    start = datetime(2026, 5, 13, 2, 0)
    end = datetime(2026, 5, 13, 3, 0)
    trades = simulate(bars, start, end, {"mode_strict_vol": False, "mode_break": False, "mode_color": True})
    matched_times = set()
    for st, side, _, _ in SHANO_SETUPS:
        zt = datetime(2026, 5, 13, int(st[:2]), int(st[3:5]), int(st[6:8]))
        for t in trades:
            if t["side"] == side and abs((t["entry_time"] - zt).total_seconds()) < 180:
                matched_times.add((st, side))
                break

    print(f"v3.43 captured: {len(matched_times)}/18\n")
    print("REMAINING MISSES — diagnosed:")
    print(f"{'Shano':<10} {'side':<5} {'bar OHLC':<35} {'sign':<5} {'why no fire (color check on)':<40} {'no-color fires?'}")
    print("-" * 130)
    for st, side, lot, pnl in SHANO_SETUPS:
        if (st, side) in matched_times: continue
        # Find the bar Shano fired in
        h, m, s = int(st[:2]), int(st[3:5]), int(st[6:8])
        bar_minute = datetime(2026, 5, 13, h, m)
        bar_idx = next((i for i, b in enumerate(bars) if b["time"] == bar_minute), None)
        if bar_idx is None:
            print(f"{st:<10} {side:<5} (bar not in CSV)")
            continue
        b = bars[bar_idx]
        sign = "G" if b["close"] > b["open"] else ("R" if b["close"] < b["open"] else "_")

        # With color check: what does detector say?
        sigs_with_color = detect_relaxed(bars, bar_idx, mode_strict_vol=False, mode_break=False, mode_color=True)
        sigs_no_color = detect_relaxed(bars, bar_idx, mode_strict_vol=False, mode_break=False, mode_color=False)

        with_color_sides = set(s["side"] for s in sigs_with_color)
        no_color_sides = set(s["side"] for s in sigs_no_color)

        # Why didn't v3.43 fire Shano's side?
        if side in with_color_sides:
            why = "FIRED but didn't match (gap > 3 min or matched to other)"
        elif sign == "G" and side == "sell":
            why = "bar is GREEN, color check blocks sell"
        elif sign == "R" and side == "buy":
            why = "bar is RED, color check blocks buy"
        elif sign == "_":
            why = "doji"
        else:
            why = "detector rejected (need deeper look)"

        no_color_msg = f"yes: {sorted(no_color_sides)}" if side in no_color_sides else f"NO: {sorted(no_color_sides) or '[]'}"
        ohlc = f"O{b['open']:.2f} H{b['high']:.2f} L{b['low']:.2f} C{b['close']:.2f}"
        print(f"{st:<10} {side:<5} {ohlc:<35} {sign:<5} {why:<40} {no_color_msg}")


if __name__ == "__main__":
    main()
