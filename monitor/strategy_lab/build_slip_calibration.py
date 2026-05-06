"""build_slip_calibration.py — extract empirical slippage distribution from turtle_fills.csv.

Output: slip_calibration.json with the full sorted distribution + key percentiles.
Backtester will sample from this distribution instead of using a constant SLIP_PIPS.

Empirical source: 340 SL exit fills from production (2026-04-20 to 2026-05-01).
Each row has the intended SL price (in comment `[sl X.XX]`) and actual fill price.
Slippage = price worse than intended (always non-negative for a stop hit).

Assumption: entry slippage follows the same distribution as exit slippage. This is
defensible for market orders on liquid pairs but should be re-validated when the EA
starts logging send_ts + intended_price for entries (Monday onwards).
"""
from __future__ import annotations
import csv, json, re, statistics
from pathlib import Path

FILLS_CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\turtle_fills.csv")
OUT_JSON  = Path(__file__).parent / "slip_calibration.json"
PIP_SIZE  = 0.10


def main():
    print(f"Reading {FILLS_CSV}")
    slips_pips = []  # combined buy + sell

    with open(FILLS_CSV, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if "closed" not in row["direction"].lower(): continue
            m = re.search(r"\[sl (\d+\.\d+)\]", row.get("comment", ""))
            if not m: continue
            try:
                sl_price = float(m.group(1))
                close_price = float(row["close_price"])
            except (ValueError, KeyError):
                continue
            # Slippage: price WORSE than SL. For a long, exit at bid: slip = sl - bid (positive = slipped through SL).
            # For a short, exit at ask: slip = ask - sl. We take absolute value since slippage direction is "worse".
            if "BUY" in row["direction"]:
                slip_price = sl_price - close_price
            else:
                slip_price = close_price - sl_price
            if slip_price < 0:  # filled BETTER than SL (rare price-improvement case); count as 0
                slip_price = 0.0
            slips_pips.append(slip_price / PIP_SIZE)

    n = len(slips_pips)
    if n == 0:
        print("No slip data found — aborting.")
        return

    s = sorted(slips_pips)
    pcts = {p: round(s[min(int(n * p / 100), n - 1)], 3) for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]}

    cal = {
        "n": n,
        "mean_pips": round(statistics.mean(s), 3),
        "stdev_pips": round(statistics.stdev(s) if n > 1 else 0, 3),
        "min_pips": round(min(s), 3),
        "max_pips": round(max(s), 3),
        "percentiles_pips": pcts,
        # Sorted distribution for inverse-CDF sampling. Compact: store as sorted list.
        "sorted_distribution_pips": [round(v, 3) for v in s],
        "source": "turtle_fills.csv SL exits (2026-04-20 to 2026-05-01)",
        "note": "Sample uniform u in [0,1]; pick s[floor(u * n)] for empirical-CDF slippage in pips.",
    }

    OUT_JSON.write_text(json.dumps(cal, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_JSON}  (n={n})")
    print()
    print("Empirical SL slippage (in pips):")
    print(f"  mean={cal['mean_pips']}  stdev={cal['stdev_pips']}")
    print(f"  Percentiles: " + "  ".join(f"p{k}={v}" for k, v in pcts.items()))
    print()
    print("BACKTEST WAS USING: SLIP_PIPS=0.5 (constant)")
    print(f"EMPIRICAL MEAN:    {cal['mean_pips']} pips ({cal['mean_pips']/0.5:.2f}x the constant)")
    print(f"EMPIRICAL P95:     {pcts[95]} pips ({pcts[95]/0.5:.0f}x the constant)")
    print(f"EMPIRICAL MAX:     {cal['max_pips']} pips ({cal['max_pips']/0.5:.0f}x the constant)")


if __name__ == "__main__":
    main()
