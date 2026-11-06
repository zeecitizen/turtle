"""slip_drift_monitor.py — detect when broker execution quality is drifting from baseline.

Run weekly (or after any suspected broker change). Compares the most recent N fills'
slippage distribution against the calibrated baseline. Alerts on:
  - Mean drift (>30% change in mean slip)
  - Tail drift (p95 or max changing significantly)
  - Latency drift (mean latency change >50ms or p95 >300ms)
  - Distribution-shape divergence (Kolmogorov-Smirnov-style two-sample test)

If drift detected → recommend re-running build_slip_calibration.py + fit_lognormal_slip.py
with fresh data, and re-validating the backtest with walk-forward methodology.

Sources:
  - shano_open_log.csv — written by EA's LogOpenWithLatency() (entry slippage + latency)
  - turtle_fills.csv — broker SL exit slippage (existing)
  - slip_calibration.json — current baseline

Usage:
  python slip_drift_monitor.py [--recent-n 50]
"""
from __future__ import annotations
import csv, json, math, statistics, sys, re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

COMMON_DIR = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
OPEN_LOG   = COMMON_DIR / "shano_open_log.csv"
FILLS_CSV  = COMMON_DIR / "turtle_fills.csv"
CAL_PATH   = Path(__file__).parent / "slip_calibration.json"

PIP_SIZE = 0.10
DRIFT_MEAN_PCT     = 0.30   # alert if mean shifts >30%
DRIFT_P95_PCT      = 0.40   # alert if p95 shifts >40%
DRIFT_LATENCY_MEAN_MS = 50  # alert if mean latency drifts >50ms
DRIFT_LATENCY_P95_MS  = 300 # alert if p95 latency >300ms above baseline


def read_recent_open_log_slips(n=50):
    """Return last N entry slippages from shano_open_log.csv (in pips)."""
    if not OPEN_LOG.exists():
        return [], []
    slips = []; latencies_ms = []
    with open(OPEN_LOG, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for row in rows[-n:]:
        try:
            slip_pts = float(row["slip_pts"])
            latency_us = int(row["latency_us"])
            slips.append(slip_pts / PIP_SIZE)
            latencies_ms.append(latency_us / 1000.0)
        except (ValueError, KeyError):
            continue
    return slips, latencies_ms


def read_recent_fills_slips(n=50):
    """Return last N SL slippages from turtle_fills.csv (in pips)."""
    if not FILLS_CSV.exists(): return []
    slips = []
    with open(FILLS_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for row in rows[-n:]:
        if "closed" not in row.get("direction", "").lower(): continue
        m = re.search(r"\[sl (\d+\.\d+)\]", row.get("comment", ""))
        if not m: continue
        try:
            sl_price = float(m.group(1))
            close_price = float(row["close_price"])
        except (ValueError, KeyError):
            continue
        if "BUY" in row["direction"]:
            slip_price = sl_price - close_price
        else:
            slip_price = close_price - sl_price
        if slip_price < 0: slip_price = 0.0
        slips.append(slip_price / PIP_SIZE)
    return slips


def ks_two_sample(a, b):
    """Two-sample Kolmogorov-Smirnov test statistic (no scipy dependency).
    Returns the max absolute difference between the two empirical CDFs (D-statistic).
    Larger D = greater distribution divergence. D > 0.2 is a meaningful shift.
    """
    if not a or not b: return 0.0
    sa = sorted(a); sb = sorted(b)
    all_vals = sorted(set(sa + sb))
    na, nb = len(sa), len(sb)
    max_d = 0.0
    for v in all_vals:
        cdf_a = sum(1 for x in sa if x <= v) / na
        cdf_b = sum(1 for x in sb if x <= v) / nb
        d = abs(cdf_a - cdf_b)
        if d > max_d: max_d = d
    return max_d


def main():
    n = 50
    if "--recent-n" in sys.argv:
        idx = sys.argv.index("--recent-n")
        try: n = int(sys.argv[idx + 1])
        except (IndexError, ValueError): pass

    print(f"=" * 80)
    print(f"SLIP DRIFT MONITOR — comparing last {n} fills to calibrated baseline")
    print(f"=" * 80)
    print()

    if not CAL_PATH.exists():
        print(f"ERR: {CAL_PATH} missing — run build_slip_calibration.py first")
        return

    cal = json.loads(CAL_PATH.read_text(encoding="utf-8"))
    baseline = cal["sorted_distribution_pips"]
    base_mean = cal["mean_pips"]
    base_p95 = cal["percentiles_pips"]["95"]
    base_max = cal["max_pips"]

    print(f"BASELINE (calibrated {cal['n']} fills): mean={base_mean:.2f}pips  p95={base_p95:.2f}pips  max={base_max:.2f}pips")
    print()

    # Recent open-log entry slippages (will be empty until EA logs Monday onwards)
    recent_open_slips, recent_latencies = read_recent_open_log_slips(n)
    if recent_open_slips:
        rmean = statistics.mean(recent_open_slips)
        rp95 = sorted(recent_open_slips)[int(len(recent_open_slips) * 0.95)]
        rmax = max(recent_open_slips)
        ks = ks_two_sample(recent_open_slips, baseline)
        print(f"RECENT (entry slips, {len(recent_open_slips)} fills): mean={rmean:.2f}pips  p95={rp95:.2f}  max={rmax:.2f}  KS={ks:.3f}")
        # Drift checks
        mean_drift = (rmean - base_mean) / max(base_mean, 0.01)
        p95_drift = (rp95 - base_p95) / max(base_p95, 0.01)
        alerts = []
        if abs(mean_drift) > DRIFT_MEAN_PCT:
            alerts.append(f"Mean drift {mean_drift*100:+.0f}% (threshold {DRIFT_MEAN_PCT*100:.0f}%)")
        if abs(p95_drift) > DRIFT_P95_PCT:
            alerts.append(f"p95 drift {p95_drift*100:+.0f}% (threshold {DRIFT_P95_PCT*100:.0f}%)")
        if rmax > base_max * 1.5:
            alerts.append(f"New tail extreme: recent max {rmax:.1f} > 1.5x baseline max {base_max:.1f}")
        if ks > 0.20:
            alerts.append(f"KS divergence {ks:.3f} > 0.20 (significant distribution shift)")
        if alerts:
            print()
            print("  *** DRIFT DETECTED ***")
            for a in alerts: print(f"    - {a}")
            print()
            print("  ACTION: re-run build_slip_calibration.py + fit_lognormal_slip.py with fresh data")
            print("  ACTION: re-validate backtest with walk-forward (train on old, test on recent)")
        else:
            print("  -> No drift detected. Calibration remains valid.")
    else:
        print(f"NO entry-slip data yet (shano_open_log.csv empty or missing).")
        print(f"  This will populate Monday onwards when EA fires its first main with the new logger.")
    print()

    # Latency stats
    if recent_latencies:
        lmean = statistics.mean(recent_latencies)
        lp95 = sorted(recent_latencies)[int(len(recent_latencies) * 0.95)]
        lmax = max(recent_latencies)
        print(f"LATENCY (recent {len(recent_latencies)} fills): mean={lmean:.0f}ms  p95={lp95:.0f}ms  max={lmax:.0f}ms")
        # Compare to backtest assumption (300ms)
        if abs(lmean - 300) > DRIFT_LATENCY_MEAN_MS:
            print(f"  *** LATENCY DRIFT *** mean differs from backtest assumption (300ms) by {lmean-300:+.0f}ms")
            print(f"  ACTION: update LAT_MEAN in pdf5_calibrated.py to {lmean:.0f}")
        if lp95 > 300 + DRIFT_LATENCY_P95_MS:
            print(f"  *** LATENCY TAIL *** p95 of {lp95:.0f}ms exceeds backtest tail allowance")
            print(f"  ACTION: increase LAT_MAX or use lognormal latency model")
    else:
        print("NO latency data yet (shano_open_log.csv empty).")
    print()

    # Recent SL exit slippages (existing data source)
    recent_sl = read_recent_fills_slips(n)
    if recent_sl:
        smean = statistics.mean(recent_sl)
        sks = ks_two_sample(recent_sl, baseline)
        print(f"RECENT SL EXITS (turtle_fills, {len(recent_sl)} fills): mean={smean:.2f}pips  KS-vs-baseline={sks:.3f}")
        if sks > 0.20:
            print(f"  *** SL-exit distribution shifted vs baseline (KS={sks:.3f})")

    print()
    print("Run weekly to monitor broker execution drift.")


if __name__ == "__main__":
    main()
