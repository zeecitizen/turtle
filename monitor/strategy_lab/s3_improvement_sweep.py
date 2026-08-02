"""s3_improvement_sweep.py — test two proposed improvements to S3Trader on
12 days of real ticks, WITHOUT changing the EA code:

  Idea 1: WIDER SL BUFFER — would have saved Trade 3 today (single-wick
          stop-out + recovery). Test buffers 0.10, 0.50, 1.00, 2.00, 5.00.

  Idea 2: TIME-OF-DAY FILTER — today's 4 trades all fired 05:00-08:00
          broker time. Restrict to London/NY hours and see if edge improves.

Both swept independently + as a grid.
"""
import csv, sys, glob
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, replay_ticks, stats,
    group_bars_by_day, find_h1_fvgs)
from ea_mirror_validate import s3_ea_mirror

CONTRACT = 100.0


def filter_by_hour(sigs, hour_min, hour_max):
    """Keep only signals whose fire_time hour ∈ [hour_min, hour_max)."""
    return [s for s in sigs if hour_min <= s["fire_time"].hour < hour_max]


def run_with(cache, h1_fvgs, sl_buf, hour_min=0, hour_max=24, lots=0.10):
    all_trades = []
    for day, c in cache.items():
        sigs = s3_ea_mirror(c["m5"], sl_buf=sl_buf,
                            h1_fvgs=h1_fvgs, require_fvg=False)
        sigs = filter_by_hour(sigs, hour_min, hour_max)
        if not sigs: continue
        done = replay_ticks(c["ticks"], sigs, lots, CONTRACT)
        all_trades.extend(done)
    return all_trades


def fmt_result(r, label):
    if r is None or r["n"] == 0:
        return f"  {label:<40}  no trades"
    pos = "✅" if r["total"] > 0 else "❌"
    return (f"  {label:<40}  n={r['n']:>3} pw={r['pwin']:.2f} "
            f"W=${r['w_avg']:>5.1f} L=${r['l_avg']:>5.1f} "
            f"TOT=${r['total']:>+8.1f}  {pos}")


def main():
    print("Loading data...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "ticks": ticks}
    print(f"  {len(cache)} days cached\n")

    # ===== Idea 1: WIDER SL BUFFER =====
    print("="*78)
    print("  IDEA 1 — SL BUFFER SWEEP (all hours)")
    print("="*78)
    print(f"  Current production: SL = bo.low − $0.10")
    print(f"  Backtest reference: 104 trades, +$1,184\n")
    sl_results = []
    for sl_buf in [0.10, 0.30, 0.50, 1.00, 2.00, 3.00, 5.00]:
        trades = run_with(cache, h1_fvgs, sl_buf=sl_buf)
        r = stats(trades)
        sl_results.append((sl_buf, r))
        print(fmt_result(r, f"SL=$bo.low−${sl_buf:>4.2f}"))

    # ===== Idea 2: TIME-OF-DAY FILTER =====
    print()
    print("="*78)
    print("  IDEA 2 — TIME-OF-DAY FILTER (broker time, default SL=$0.10)")
    print("="*78)
    # Broker is likely GMT+2 or GMT+3. Sessions in broker time:
    #   Asian: 00-07 (low vol XAU)
    #   London open: 07-09
    #   London + NY overlap: 12-16  ← max XAU volume
    #   NY: 12-21
    #   Quiet: 21-24
    print(f"  Broker time used directly (fire_time.hour)\n")
    windows = [
        ("ALL hours (baseline)",          0,  24),
        ("Asian only (00-07)",            0,   7),
        ("London-NY only (08-21)",        8,  21),
        ("London-NY overlap (12-16)",    12,  16),
        ("Avoid Asian quiet (07-21)",     7,  21),
        ("Avoid first 2hrs of day (02-22)", 2,22),
        ("Avoid first/last 1hr (01-23)",  1,  23),
    ]
    tod_results = []
    for label, hmin, hmax in windows:
        trades = run_with(cache, h1_fvgs, sl_buf=0.10,
                          hour_min=hmin, hour_max=hmax)
        r = stats(trades)
        tod_results.append((label, hmin, hmax, r))
        print(fmt_result(r, label))

    # ===== Idea 3: GRID — best SL × best window =====
    print()
    print("="*78)
    print("  IDEA 3 — COMBINED GRID (SL buffer × time window)")
    print("="*78)
    print(f"  {'TimeWindow':<24} {'SL':>5}  {'n':>4} {'pwin':>5} "
          f"{'Wavg':>6} {'Lavg':>6} {'TOTAL':>9}  EV/tr")
    best = None
    for label, hmin, hmax in windows[:5]:
        for sl_buf in [0.10, 0.50, 1.00, 2.00]:
            trades = run_with(cache, h1_fvgs, sl_buf=sl_buf,
                              hour_min=hmin, hour_max=hmax)
            r = stats(trades)
            if r is None: continue
            ev = (r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"])
            mark = "✅" if r["total"] > 0 else " "
            print(f"  {label[:24]:<24} ${sl_buf:>4.2f}  {r['n']:>4} "
                  f"{r['pwin']:>5.2f} ${r['w_avg']:>4.1f} ${r['l_avg']:>4.1f} "
                  f"${r['total']:>+7.1f}  ${ev:>+5.2f}  {mark}")
            if best is None or r["total"] > best[0]:
                best = (r["total"], label, hmin, hmax, sl_buf, r)
        print()

    if best:
        print(f"\nBEST GRID CONFIG: {best[1]}, SL=${best[4]:.2f}")
        print(f"  n={best[5]['n']} pwin={best[5]['pwin']:.2f} TOTAL=${best[0]:+.1f}")
        delta = best[0] - 1184.1
        delta_pct = delta / 1184.1 * 100
        print(f"  Δ vs current production (104 trades, +$1,184): ${delta:+.1f} ({delta_pct:+.1f}%)")


if __name__ == "__main__":
    main()
