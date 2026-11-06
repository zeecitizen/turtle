"""
signal_filter_combos.py — apply stacked quality filters to the 17.8K
signal dataset and see how powerful the combined filter is.

Test various stacks of:
  - vol_mult >= X
  - uhv_rng_pts >= Y
  - bars_back >= Z
  - bo_vol_ratio <= W

Output: signals retained, SL-hit %, median MFE, signal density per day.
"""
from __future__ import annotations
import csv
import statistics
from pathlib import Path

CSV_IN = Path(__file__).parent / "signal_quality_dataset.csv"


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
            rows.append(r)
    return rows


def test_filter(rows, vol_min=0, rng_min=0, bars_min=0, bo_vol_max=1.0,
                bo_body_min=0, days=64, label=""):
    sub = [r for r in rows if
           r["vol_mult"] >= vol_min and
           r["uhv_rng_pts"] >= rng_min and
           r["bars_back"] >= bars_min and
           r["bo_vol_ratio"] <= bo_vol_max and
           r["bo_body_pct"] >= bo_body_min]
    if not sub: return
    n = len(sub)
    sl = sum(1 for r in sub if r["sl_hit"]) / n * 100
    bank = sum(1 for r in sub if r["mfe_usd"] >= 1.5) / n * 100
    med_mfe = statistics.median(r["mfe_usd"] for r in sub)
    med_mae = statistics.median(r["mae_usd"] for r in sub)
    # Mean PF (excluding inf)
    pfs = [r["profit_factor"] for r in sub if r["profit_factor"] < 999]
    med_pf = statistics.median(pfs) if pfs else 0
    per_day = n / days
    # Use peak-trail $1/$0.5 estimate: each bankable trade banks roughly peak - $0.5
    # SL-hit trades lose UHV.low which we approximate from MAE
    avg_loss = sum(r["mae_usd"] for r in sub if r["sl_hit"]) / max(1, sum(1 for r in sub if r["sl_hit"]))
    print(f"  {label:<45} n={n:<5} day={per_day:<5.1f} bank%={bank:<5.1f} sl%={sl:<5.1f} medMFE=${med_mfe:<6.1f} medMAE=${med_mae:<6.1f} pf={med_pf:<5.2f} avgL=${avg_loss:.1f}")


def main():
    rows = load()
    print(f"Loaded {len(rows)} signals from 64 days.\n")
    print(f"{'filter':<47} {'count':<10} {'/day':<6} {'bank%':<8} {'sl%':<7} {'mfe':<10} {'mae':<10} {'pf':<7} {'avgLoss':<8}")
    print("-" * 130)

    # Baseline
    test_filter(rows, label="baseline (no filter)")
    print()

    print("Single-feature filters:")
    test_filter(rows, vol_min=1.5, label="vol_mult >= 1.5")
    test_filter(rows, vol_min=2.0, label="vol_mult >= 2.0")
    test_filter(rows, vol_min=3.0, label="vol_mult >= 3.0")
    test_filter(rows, rng_min=3, label="rng >= 3pt")
    test_filter(rows, rng_min=5, label="rng >= 5pt")
    test_filter(rows, rng_min=10, label="rng >= 10pt")
    test_filter(rows, bars_min=12, label="bars_back >= 12")
    test_filter(rows, bars_min=25, label="bars_back >= 25")
    test_filter(rows, bo_vol_max=0.6, label="bo_vol_ratio <= 0.6")
    test_filter(rows, bo_vol_max=0.4, label="bo_vol_ratio <= 0.4")

    print()
    print("Stacked filters:")
    test_filter(rows, vol_min=1.5, rng_min=3, label="vol>=1.5 + rng>=3")
    test_filter(rows, vol_min=2.0, rng_min=3, label="vol>=2.0 + rng>=3")
    test_filter(rows, vol_min=1.5, bars_min=12, label="vol>=1.5 + bars>=12")
    test_filter(rows, vol_min=1.5, rng_min=3, bars_min=12, label="vol>=1.5 + rng>=3 + bars>=12")
    test_filter(rows, vol_min=2.0, rng_min=5, bars_min=12, label="vol>=2.0 + rng>=5 + bars>=12")
    test_filter(rows, vol_min=1.5, rng_min=3, bars_min=12, bo_vol_max=0.6,
                label="vol>=1.5 + rng>=3 + bars>=12 + bovol<=0.6")
    test_filter(rows, vol_min=2.0, rng_min=5, bars_min=25, bo_vol_max=0.6,
                label="vol>=2.0 + rng>=5 + bars>=25 + bovol<=0.6")
    test_filter(rows, vol_min=3.0, rng_min=5, bars_min=12, bo_vol_max=0.5,
                label="vol>=3.0 + rng>=5 + bars>=12 + bovol<=0.5")


if __name__ == "__main__":
    main()
