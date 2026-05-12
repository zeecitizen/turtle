"""
reverse_engineer_feb11_exits.py — for each of Zee's 20 textbook setups,
walk the M1 bars during the hold to find what mechanical signature
triggered his exit.

For each trade we measure at close:
  - hold time (seconds)
  - peak pnl during hold
  - drawdown from peak at close
  - exit-bar color (vs trade direction: continuation/reversal)
  - exit-bar volume (vs prior 5-bar avg)
  - exit-bar range (vs prior 5-bar avg)
  - number of bars held
  - peak-bar timing (first bar / middle / last)

Goal: find a mechanical signal that matches when Zee chose to close.
"""
from __future__ import annotations
import csv
import os
import statistics
from datetime import datetime
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

# Zee's 20 textbook lesson-2 setups: (entry_time, side, entry_px, close_time, close_px, profit)
ZEE_TRADES = [
    ("01:59:04", "buy",  5042.17, "02:00:43", 5042.96,  6.65),
    ("02:09:38", "sell", 5040.68, "02:10:18", 5039.29, 11.69),
    ("02:29:02", "buy",  5039.03, "02:30:28", 5041.41, 20.01),
    ("16:49:07", "buy",  5047.93, "16:51:03", 5049.96, 17.12),
    ("16:52:21", "buy",  5050.77, "16:52:27", 5051.82,  8.85),
    ("16:54:10", "buy",  5056.74, "16:54:20", 5057.72,  8.26),
    ("16:58:03", "buy",  5064.26, "16:58:27", 5064.94,  5.73),
    ("17:02:45", "buy",  5055.71, "17:03:51", 5062.23, 54.93),
    ("17:36:11", "buy",  5056.53, "17:36:26", 5056.92,  3.29),
    ("17:36:13", "buy",  5057.05, "17:52:56", 5058.77, 14.50),
    ("17:37:26", "buy",  5045.82, "17:40:02", 5046.66,  7.08),
    ("17:49:59", "buy",  5048.32, "17:52:33", 5054.58, 52.78),
    ("18:24:18", "buy",  5059.26, "18:28:33", 5060.27,  8.51),
    ("18:41:50", "buy",  5078.10, "19:06:41", 5077.93, -1.43),
    ("19:20:34", "sell", 5084.21, "19:20:40", 5082.52, 14.21),
    ("19:26:06", "sell", 5089.16, "19:26:50", 5087.43, 14.55),
    ("19:29:31", "buy",  5086.34, "19:39:03", 5086.44,  0.84),
    ("19:36:19", "buy",  5082.91, "19:37:19", 5084.17, 10.60),
    ("19:38:39", "buy",  5083.28, "19:38:50", 5084.59, 11.02),
    ("19:38:59", "buy",  5086.33, "19:39:03", 5086.44,  0.92),
]


def load_bars(p: Path):
    bars = []
    with open(p, "r", encoding="ascii") as f:
        for r in csv.DictReader(f):
            bars.append({
                "time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                "open": float(r["open"]), "high": float(r["high"]),
                "low":  float(r["low"]),  "close": float(r["close"]),
                "vol":  int(r["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars


def pnl_at(price: float, entry: float, side: str) -> float:
    """USD per 0.10 lot. 1 point of XAU @ 0.10 lot = $10."""
    delta = (price - entry) if side == "buy" else (entry - price)
    return delta * 100 * 0.10


def analyze():
    m1 = load_bars(M1_CSV)
    print(f"Loaded {len(m1)} M1 bars")
    print()

    print(f"{'#':<3} {'entry':<9} {'side':<5} {'hold':<6} {'peak_pnl':<9} {'final_pnl':<9} {'drawdown':<10} {'exit_bar_color':<15} {'exit_vol/5avg':<13} {'exit_rng/5avg':<13}")
    print("-" * 110)

    results = []
    for i, (e_hms, side, entry, c_hms, close_px, actual_pnl) in enumerate(ZEE_TRADES, 1):
        et = datetime.strptime(f"2026.02.11 {e_hms}", "%Y.%m.%d %H:%M:%S")
        ct = datetime.strptime(f"2026.02.11 {c_hms}", "%Y.%m.%d %H:%M:%S")
        hold_s = (ct - et).total_seconds()

        # All M1 bars touched during the hold (entry minute through close minute)
        hold_bars = [b for b in m1 if b["time"].replace(second=0) >= et.replace(second=0)
                                  and b["time"].replace(second=0) <= ct.replace(second=0)]
        if not hold_bars:
            continue

        # Peak P&L during hold (using bar HIGH for buy, LOW for sell)
        if side == "buy":
            peak_pnl = pnl_at(max(b["high"] for b in hold_bars), entry, side)
        else:
            peak_pnl = pnl_at(min(b["low"] for b in hold_bars), entry, side)

        drawdown_from_peak = peak_pnl - actual_pnl

        # Exit bar: the M1 bar containing close time
        exit_bar = None
        exit_min = ct.replace(second=0)
        for b in hold_bars:
            if b["time"] == exit_min:
                exit_bar = b; break
        if exit_bar is None:
            exit_bar = hold_bars[-1]

        # Exit-bar color in trade direction: continuation = price moved Zee's way during bar; reversal = against
        ex_close = exit_bar["close"]; ex_open = exit_bar["open"]
        if side == "buy":
            exit_in_favor = ex_close > ex_open
        else:
            exit_in_favor = ex_close < ex_open
        exit_color = "continuation" if exit_in_favor else "reversal"

        # Prior 5-bar avg volume and range (for exit-bar comparison)
        idx_exit = m1.index(exit_bar)
        prior5 = m1[max(0, idx_exit-5):idx_exit]
        if prior5:
            avg5_vol = sum(b["vol"] for b in prior5) / len(prior5)
            avg5_rng = sum(b["high"] - b["low"] for b in prior5) / len(prior5)
            vol_ratio = exit_bar["vol"] / avg5_vol if avg5_vol else 0
            rng_ratio = (exit_bar["high"] - exit_bar["low"]) / avg5_rng if avg5_rng else 0
        else:
            vol_ratio = rng_ratio = 0

        results.append({
            "n": i, "entry_hms": e_hms, "side": side, "hold_s": hold_s,
            "peak_pnl": peak_pnl, "final_pnl": actual_pnl,
            "drawdown": drawdown_from_peak,
            "exit_color": exit_color,
            "exit_vol_ratio": vol_ratio, "exit_rng_ratio": rng_ratio,
            "hold_bars": len(hold_bars),
        })

        print(f"{i:<3} {e_hms:<9} {side:<5} {int(hold_s):<6} ${peak_pnl:<8.2f} ${actual_pnl:<8.2f} ${drawdown_from_peak:<9.2f} {exit_color:<15} {vol_ratio:<13.2f} {rng_ratio:<13.2f}")

    print()
    print("=" * 110)
    print("Aggregate patterns:")
    print("=" * 110)
    # Direction of exit bar
    reversals = [r for r in results if r["exit_color"] == "reversal"]
    continuations = [r for r in results if r["exit_color"] == "continuation"]
    print(f"\nExit-bar direction:")
    print(f"  Reversal candle (against trade): {len(reversals)} / {len(results)}")
    print(f"  Continuation candle (with trade): {len(continuations)} / {len(results)}")

    # Hold time
    hs = [r["hold_s"] for r in results]
    print(f"\nHold time (sec): min={min(hs):.0f} median={statistics.median(hs):.0f} mean={statistics.mean(hs):.0f} max={max(hs):.0f}")

    # Peak banking efficiency
    print(f"\nPeak-vs-final P&L:")
    print(f"  Peak pnl: min=${min(r['peak_pnl'] for r in results):.2f} median=${statistics.median([r['peak_pnl'] for r in results]):.2f} max=${max(r['peak_pnl'] for r in results):.2f}")
    print(f"  Final pnl: min=${min(r['final_pnl'] for r in results):.2f} median=${statistics.median([r['final_pnl'] for r in results]):.2f} max=${max(r['final_pnl'] for r in results):.2f}")
    print(f"  Drawdown from peak (USD given back):")
    dds = [r["drawdown"] for r in results]
    print(f"    min={min(dds):.2f} median={statistics.median(dds):.2f} mean={statistics.mean(dds):.2f} max={max(dds):.2f}")

    # Did Zee bank close to peak?
    bank_ratios = [r["final_pnl"] / r["peak_pnl"] if r["peak_pnl"] > 0 else 0 for r in results]
    print(f"  Bank ratio (final/peak): median={statistics.median(bank_ratios):.2f}  (1.0 = banked at peak)")

    # Exit-bar volume/range patterns
    vols = [r["exit_vol_ratio"] for r in results]
    rngs = [r["exit_rng_ratio"] for r in results]
    print(f"\nExit-bar vol vs prior-5: min={min(vols):.2f} median={statistics.median(vols):.2f} max={max(vols):.2f}")
    print(f"Exit-bar range vs prior-5: min={min(rngs):.2f} median={statistics.median(rngs):.2f} max={max(rngs):.2f}")


if __name__ == "__main__":
    analyze()
