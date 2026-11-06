"""s3_hour_filter_sweep.py — full sweep of hour-skip filter combined with
SL=$2.00 (new production default).

Methodology:
  1. Run S3 mirror with SL=$2 on full 12 days, get per-hour P&L
  2. Identify "bad hours" using FIRST 6 days only (training)
  3. Apply skip filter on LAST 6 days (out-of-sample validation)
  4. Also report full-12d in-sample for comparison
  5. Test several skip configs: skip-N-worst, threshold-based, fixed set

This walk-forward design surfaces curve-fitting:
  if a config works on train but fails on test, it's overfit.
"""
import csv, sys, glob
sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, replay_ticks, stats, group_bars_by_day, find_h1_fvgs
from ea_mirror_validate import s3_ea_mirror

CONTRACT = 100.0


def per_hour_pnl(trades):
    by_h = defaultdict(list)
    for t in trades:
        by_h[t["fire_hour"]].append(t)
    return {h: sum(t["pnl"] for t in ts) for h, ts in by_h.items()}


def filter_by_skip_hours(trades, skip_hours):
    return [t for t in trades if t["fire_hour"] not in skip_hours]


def report(label, trades):
    if not trades:
        print(f"  {label:<40}  no trades")
        return None
    r = stats(trades)
    pos = "✅" if r["total"] > 0 else "❌"
    print(f"  {label:<40}  n={r['n']:>3} pw={r['pwin']:.2f} "
          f"W=${r['w_avg']:>5.1f} L=${r['l_avg']:>5.1f}  TOT=${r['total']:>+8.1f}  {pos}")
    return r


def main():
    print("Loading...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    # Run mirror with SL=$2 per day, tag each trade with fire_hour
    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        m5 = aggregate_to_tf(db, 5)
        sigs = s3_ea_mirror(m5, sl_buf=2.0, h1_fvgs=h1_fvgs, require_fvg=False)
        done = replay_ticks(ticks, sigs, 0.10, CONTRACT)
        for i, t in enumerate(done):
            t["fire_hour"] = sigs[i]["fire_time"].hour if i < len(sigs) else 0
            t["fire_day"]  = day
        cache[day] = done

    all_trades = [t for ts in cache.values() for t in ts]
    days_sorted = sorted(cache.keys())
    mid = len(days_sorted) // 2
    train_days = days_sorted[:mid]
    test_days  = days_sorted[mid:]
    train_trades = [t for d in train_days for t in cache[d]]
    test_trades  = [t for d in test_days  for t in cache[d]]

    print(f"  {len(all_trades)} trades total ({len(train_trades)} train / {len(test_trades)} test)")
    print(f"  Train days: {train_days[0]} → {train_days[-1]}")
    print(f"  Test days:  {test_days[0]} → {test_days[-1]}\n")

    # ===== TRAIN: identify bad hours using FIRST half =====
    print("="*78)
    print("  TRAIN (first 6 days): per-hour P&L with SL=$2")
    print("="*78)
    train_h = per_hour_pnl(train_trades)
    sorted_h = sorted(train_h.items(), key=lambda x: x[1])
    print(f"  {'hour':>5} {'pnl':>10}")
    for h, p in sorted_h:
        bar = "▮"*max(0,int(p/30)) if p>0 else "▯"*max(0,int(-p/30))
        print(f"  {h:>5} ${p:>+8.1f}  {bar}")

    # ===== TEST several skip filters on TEST half =====
    print()
    print("="*78)
    print("  TEST (last 6 days, OUT-OF-SAMPLE) with various skip filters from train")
    print("="*78)
    print(f"  Baseline TEST (no filter): ", end="")
    baseline_test = report("baseline test", test_trades)

    # Build skip sets from train
    bad_hours_train = [h for h, p in train_h.items() if p < 0]
    print(f"\n  Bad hours in TRAIN (P&L < 0): {sorted(bad_hours_train)}")
    very_bad_train = [h for h, p in train_h.items() if p < -50]
    print(f"  Very bad hours in TRAIN (P&L < -$50): {sorted(very_bad_train)}")

    configs = [
        ("skip ALL bad-train (<$0)",  set(bad_hours_train)),
        ("skip very-bad-train (<-$50)", set(very_bad_train)),
        ("skip hours 13,15,16 (NY open)", {13, 15, 16}),
        ("skip hours 13,15,16,18 (NY open + morning)", {13, 15, 16, 18}),
        ("skip hours 13,15,16,18,19,20 (NY full day)", {13, 15, 16, 18, 19, 20}),
        ("skip 15,16 only (London+NY open)", {15, 16}),
        ("skip 16 only (NY open only)", {16}),
    ]
    print()
    for label, skip in configs:
        sub = filter_by_skip_hours(test_trades, skip)
        report(label[:38], sub)

    # ===== Also report full-12d in-sample for each config (for comparison) =====
    print()
    print("="*78)
    print("  IN-SAMPLE (full 12 days) with each skip config")
    print("="*78)
    report("baseline FULL", all_trades)
    print()
    for label, skip in configs:
        sub = filter_by_skip_hours(all_trades, skip)
        report(label[:38], sub)

    # ===== Robustness check: any single day skewing results? =====
    print()
    print("="*78)
    print("  Per-day P&L: baseline (no filter) vs skip-13/15/16 (NY open block)")
    print("="*78)
    skip316 = {13, 15, 16}
    print(f"  {'day':<12} {'baseline':>10} {'filtered':>10} {'Δ':>10}")
    for d in days_sorted:
        ts = cache[d]
        base = sum(t["pnl"] for t in ts)
        filt = sum(t["pnl"] for t in ts if t["fire_hour"] not in skip316)
        delta = filt - base
        mark = "🟢" if filt > 0 else "🔴" if filt < 0 else "  "
        print(f"  {d:<12} ${base:>+8.1f} ${filt:>+8.1f} ${delta:>+8.1f}  {mark}")

    # ===== Final recommendation summary =====
    print()
    print("="*78)
    print("  Final summary")
    print("="*78)
    base_all_r = stats(all_trades)
    print(f"  Current production (SL=$2, no filter): n={base_all_r['n']} ${base_all_r['total']:+.1f}")
    for label, skip in configs:
        sub = filter_by_skip_hours(all_trades, skip)
        r = stats(sub)
        if r is None: continue
        delta_in = r["total"] - base_all_r["total"]
        # also test on the test-only subset
        sub_test = filter_by_skip_hours(test_trades, skip)
        r_test = stats(sub_test)
        if r_test is None: continue
        baseline_test_total = baseline_test["total"] if baseline_test else 0
        delta_test = r_test["total"] - baseline_test_total
        print(f"  {label:<40}  IN-SAMP Δ=${delta_in:+.1f}  OUT-SAMP Δ=${delta_test:+.1f}")


if __name__ == "__main__":
    main()
