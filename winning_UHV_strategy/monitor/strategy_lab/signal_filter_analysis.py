"""
signal_filter_analysis.py — bucket the 17.8K signal dataset by each
pre-entry feature and compute outcome stats per bucket. Goal: find
features where high values cleanly predict good outcomes (high MFE,
low SL-hit), enabling pre-entry filters that improve signal:noise.

Outcomes of interest (with v3.30's peak-trail $1/$0.50 exit):
  - "bankable" = MFE >= $1.50 (trade reaches $1 peak and trail fires at $0.50+)
  - "sl_first" = sl_hit and MFE < $1.50 (loss without protective profit)

For each feature, compare bucketed signals to overall:
  - lift in bankable rate
  - lift in sl_first rate (lower is better)
"""
from __future__ import annotations
import csv
import statistics
from pathlib import Path
from collections import defaultdict

CSV_IN = Path(__file__).parent / "signal_quality_dataset.csv"

BANKABLE_MFE = 1.5    # min MFE for v3.30 peak-trail to bank meaningful profit
DISASTER_MAE = -3.0   # MAE below this = catastrophic loser regardless of SL


def load():
    rows = []
    with open(CSV_IN) as f:
        for r in csv.DictReader(f):
            for k in ("hour", "bars_back", "sl_hit_bar"):
                r[k] = int(r[k])
            for k in ("vol_mult", "body_pct", "uhv_rng_pts",
                      "bo_body_pct", "bo_vol_ratio",
                      "mfe_usd", "mae_usd", "profit_factor"):
                r[k] = float(r[k])
            r["sl_hit"] = r["sl_hit"].lower() == "true"
            r["bankable"] = r["mfe_usd"] >= BANKABLE_MFE
            r["disaster"] = r["mae_usd"] <= DISASTER_MAE
            rows.append(r)
    return rows


def bucket_stats(rows, key, buckets, label):
    """Print stats per bucket. `buckets` is a list of (lo, hi) for numeric
    features, or a list of values for categorical features (str)."""
    print(f"\n=== Feature: {label} ===")
    print(f"  {'bucket':<24} {'n':<6} {'bank%':<8} {'sl_hit%':<8} {'disastr%':<9} {'med MFE':<10} {'med MAE':<10} {'med PF':<8}")
    if isinstance(buckets[0], tuple):
        for lo, hi in buckets:
            sub = [r for r in rows if lo <= r[key] < hi]
            describe(f"[{lo}, {hi})", sub)
    else:
        for v in buckets:
            sub = [r for r in rows if r[key] == v]
            describe(str(v), sub)


def describe(label, sub):
    if not sub:
        print(f"  {label:<24} 0")
        return
    n = len(sub)
    bank = sum(1 for r in sub if r["bankable"]) / n * 100
    sl = sum(1 for r in sub if r["sl_hit"]) / n * 100
    dis = sum(1 for r in sub if r["disaster"]) / n * 100
    med_mfe = statistics.median(r["mfe_usd"] for r in sub)
    med_mae = statistics.median(r["mae_usd"] for r in sub)
    pfs = [r["profit_factor"] for r in sub if r["profit_factor"] < 999]
    med_pf = statistics.median(pfs) if pfs else 0
    print(f"  {label:<24} {n:<6} {bank:<7.1f}% {sl:<7.1f}% {dis:<8.1f}% ${med_mfe:<9.2f} ${med_mae:<9.2f} {med_pf:<8.2f}")


def main():
    rows = load()
    print(f"Loaded {len(rows)} signals.")
    overall_bank = sum(1 for r in rows if r["bankable"]) / len(rows) * 100
    overall_sl = sum(1 for r in rows if r["sl_hit"]) / len(rows) * 100
    overall_dis = sum(1 for r in rows if r["disaster"]) / len(rows) * 100
    print(f"OVERALL: bankable={overall_bank:.1f}%  sl_hit={overall_sl:.1f}%  disaster={overall_dis:.1f}%")

    bucket_stats(rows, "vol_mult",
                 [(0, 0.8), (0.8, 1.0), (1.0, 1.2), (1.2, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 100)],
                 "UHV vol_mult vs prior-20")

    bucket_stats(rows, "body_pct",
                 [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)],
                 "UHV body % of range")

    bucket_stats(rows, "uhv_rng_pts",
                 [(0, 1), (1, 3), (3, 5), (5, 10), (10, 50)],
                 "UHV range (points)")

    bucket_stats(rows, "bars_back",
                 [(1, 3), (3, 6), (6, 12), (12, 25), (25, 100)],
                 "bars from UHV to breakout")

    bucket_stats(rows, "bo_body_pct",
                 [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)],
                 "breakout body % of range")

    bucket_stats(rows, "bo_vol_ratio",
                 [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)],
                 "breakout vol / UHV vol")

    bucket_stats(rows, "h1_trend",
                 ["up", "down", "flat", "?"],
                 "H1 trend at breakout")

    bucket_stats(rows, "side", ["buy", "sell"], "side")

    bucket_stats(rows, "hour",
                 list(range(0, 24)),
                 "broker hour")


if __name__ == "__main__":
    main()
