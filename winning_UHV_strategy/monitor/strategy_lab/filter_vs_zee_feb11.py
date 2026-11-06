"""
filter_vs_zee_feb11.py — check if proposed quality filters would have
BLOCKED any of Zee's 20 textbook Feb 11 trades.

For each of his 20 trades, find the matching detector signal in the
signal_quality_dataset (Feb 11, ±5min, same side) and check what
features it had. Then evaluate which filters pass / block it.
"""
from __future__ import annotations
import csv
from datetime import datetime, timedelta
from pathlib import Path

CSV_IN = Path(__file__).parent / "signal_quality_dataset.csv"

# Zee's 20 textbook entries
ZEE_FEB11 = [
    ("01:59:04", "buy"),  ("02:09:38", "sell"), ("02:29:02", "buy"),
    ("16:49:07", "buy"),  ("16:52:21", "buy"),  ("16:54:10", "buy"),
    ("16:58:03", "buy"),  ("17:02:45", "buy"),  ("17:36:11", "buy"),
    ("17:36:13", "buy"),  ("17:37:26", "buy"),  ("17:49:59", "buy"),
    ("18:24:18", "buy"),  ("18:41:50", "buy"),  ("19:20:34", "sell"),
    ("19:26:06", "sell"), ("19:29:31", "buy"),  ("19:36:19", "buy"),
    ("19:38:39", "buy"),  ("19:38:59", "buy"),
]


def load():
    rows = []
    with open(CSV_IN) as f:
        for r in csv.DictReader(f):
            if r["date"] != "2026-02-11": continue
            r["dt"] = datetime.strptime(f"{r['date']} {r['time']}", "%Y-%m-%d %H:%M:%S")
            for k in ("vol_mult", "body_pct", "uhv_rng_pts",
                      "bo_body_pct", "bo_vol_ratio", "mfe_usd", "mae_usd"):
                r[k] = float(r[k])
            r["bars_back"] = int(r["bars_back"])
            r["sl_hit"] = r["sl_hit"].lower() == "true"
            rows.append(r)
    return rows


def main():
    feb11 = load()
    print(f"Feb 11 detector signals: {len(feb11)}")
    print()

    # For each Zee trade, find closest detector signal
    print(f"{'Zee':<10} {'side':<5} {'sig time':<10} {'vol_m':<7} {'rng':<6} {'b_back':<7} {'bo_vol':<7} {'MFE':<8} {'outcome':<8}")
    matched = []
    for hms, side in ZEE_FEB11:
        zt = datetime.strptime(f"2026-02-11 {hms}", "%Y-%m-%d %H:%M:%S")
        best = None
        for r in feb11:
            if r["side"] != side: continue
            gap = abs((r["dt"] - zt).total_seconds())
            if gap <= 300:
                if best is None or gap < abs((best["dt"] - zt).total_seconds()):
                    best = r
        if best:
            outcome = "WIN" if best["mfe_usd"] >= 1.5 and not best["sl_hit"] else "loss"
            print(f"{hms:<10} {side:<5} {best['time']:<10} {best['vol_mult']:<7.2f} {best['uhv_rng_pts']:<6.2f} {best['bars_back']:<7} {best['bo_vol_ratio']:<7.2f} ${best['mfe_usd']:<7.2f} {outcome:<8}")
            matched.append(best)
        else:
            print(f"{hms:<10} {side:<5} (no matching detector signal)")

    print()
    print(f"Matched {len(matched)}/20 of Zee's setups to detector signals.")

    # Evaluate filters
    filters = [
        ("vol >= 1.5",                       lambda r: r["vol_mult"] >= 1.5),
        ("vol >= 2.0",                       lambda r: r["vol_mult"] >= 2.0),
        ("vol >= 3.0",                       lambda r: r["vol_mult"] >= 3.0),
        ("rng >= 3",                         lambda r: r["uhv_rng_pts"] >= 3),
        ("rng >= 5",                         lambda r: r["uhv_rng_pts"] >= 5),
        ("rng >= 10",                        lambda r: r["uhv_rng_pts"] >= 10),
        ("bars_back >= 12",                  lambda r: r["bars_back"] >= 12),
        ("bars_back >= 25",                  lambda r: r["bars_back"] >= 25),
        ("bo_vol_ratio <= 0.6",              lambda r: r["bo_vol_ratio"] <= 0.6),
        ("vol>=1.5 + bars>=12",              lambda r: r["vol_mult"] >= 1.5 and r["bars_back"] >= 12),
        ("vol>=1.5 + rng>=3",                lambda r: r["vol_mult"] >= 1.5 and r["uhv_rng_pts"] >= 3),
        ("vol>=1.5 + rng>=3 + bars>=12",     lambda r: r["vol_mult"] >= 1.5 and r["uhv_rng_pts"] >= 3 and r["bars_back"] >= 12),
        ("vol>=2.0 + rng>=5 + bars>=12",     lambda r: r["vol_mult"] >= 2.0 and r["uhv_rng_pts"] >= 5 and r["bars_back"] >= 12),
    ]

    print()
    print(f"{'filter':<40} {'Zee passes':<12} {'Zee blocked':<14}")
    print("-" * 75)
    for name, fn in filters:
        passing = sum(1 for r in matched if fn(r))
        blocked = len(matched) - passing
        print(f"{name:<40} {passing:<12} {blocked:<14}")

    print()
    print("For each filter, list which Zee trades it BLOCKS:")
    for name, fn in filters:
        blocked = [(hms, m) for (hms, _), m in zip(ZEE_FEB11, matched) if not fn(m)]
        if not blocked: continue
        print(f"\n  {name}:")
        for hms, m in blocked[:6]:
            print(f"    {hms}  vol={m['vol_mult']:.2f}  rng={m['uhv_rng_pts']:.2f}  bars={m['bars_back']}  bovol={m['bo_vol_ratio']:.2f}")


if __name__ == "__main__":
    main()
