"""validate_s3_v2_thorough.py — RIGOROUS pre-deployment validation of
S3Trader v2 on XAU.

Tests:
  A. Per-day P&L (is the edge consistent or driven by 1-2 huge days?)
  B. Walk-forward: tune on first 6 days, validate on held-out last 6 days
  C. Drawdown: max consecutive losing trades, peak-to-trough equity drawdown,
     time spent underwater
  D. Parameter sensitivity: vary SL/TP-peak-LB/trend-threshold ±20%, see
     how much P&L moves
  E. Best-day / worst-day extremes

Before live deployment, all of these should be reasonable, not just the
aggregate total.
"""
import csv, sys, glob
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, find_h1_fvgs,
    detect_signals, replay_ticks, stats, group_bars_by_day)

CONTRACT = 100.0  # XAU


def run_with_params(cache, h1_fvgs, sl_buf, trend, peak_lb, require_fvg,
                    lots=0.10):
    """Return per-day trade lists. Days as date-string keys."""
    out = {}
    for day, c in cache.items():
        sigs = detect_signals(c["m5"], h1_fvgs, sl_buf, trend, 24,
                              require_fvg, peak_lb, 5)
        if not sigs:
            out[day] = []
            continue
        done = replay_ticks(c["ticks"], sigs, lots, CONTRACT)
        out[day] = done
    return out


def total_pnl(trades_by_day):
    return sum(sum(t["pnl"] for t in v) for v in trades_by_day.values())


def pwin(trades_by_day):
    all_t = [t for v in trades_by_day.values() for t in v]
    wins = [t for t in all_t if t["pnl"] > 0]
    losses = [t for t in all_t if t["pnl"] < 0]
    if not (wins or losses): return 0
    return len(wins) / (len(wins) + len(losses))


def main():
    print("="*78)
    print("  S3Trader v2 — THOROUGH PRE-DEPLOYMENT VALIDATION (XAU)")
    print("="*78)
    print("Loading...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    h1_fvgs = find_h1_fvgs(h1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    # Pre-cache ticks + M5
    cache = {}
    for tf in tick_files:
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        day_bars = days_bars[day]
        if len(day_bars) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(day_bars, 5), "ticks": ticks}
    days_sorted = sorted(cache.keys())
    print(f"  {len(cache)} days cached: {days_sorted[0]} → {days_sorted[-1]}\n")

    # Deployed v2 config
    LOTS = 0.10
    SL_BUF, TREND, PEAK_LB, REQUIRE_FVG = 0.10, 1.0, 10, False

    # ───────────────────────────────────────────────────────────
    # A. PER-DAY P&L
    # ───────────────────────────────────────────────────────────
    print("=== A. PER-DAY P&L (deployed config: SL=$0.10, trend=$1, peak=10, no FVG) ===")
    by_day = run_with_params(cache, h1_fvgs, SL_BUF, TREND, PEAK_LB, REQUIRE_FVG, LOTS)
    total = 0
    print(f"  {'Day':<12} {'n':>4} {'wins':>5} {'losses':>7} {'pnl':>10}")
    for d in days_sorted:
        ts = by_day[d]
        wins = sum(1 for t in ts if t["pnl"] > 0)
        losses = sum(1 for t in ts if t["pnl"] < 0)
        pnl = sum(t["pnl"] for t in ts)
        total += pnl
        marker = " 🟢" if pnl > 0 else (" 🔴" if pnl < 0 else "")
        print(f"  {d:<12} {len(ts):>4} {wins:>5} {losses:>7}  ${pnl:>+8.1f}{marker}")
    print(f"  {'='*40}")
    print(f"  {'TOTAL':<12}                ${total:>+8.1f}")
    pos_days = sum(1 for d in days_sorted if sum(t["pnl"] for t in by_day[d]) > 0)
    neg_days = sum(1 for d in days_sorted if sum(t["pnl"] for t in by_day[d]) < 0)
    print(f"  Positive days: {pos_days}/{len(days_sorted)}  Negative: {neg_days}/{len(days_sorted)}")

    # ───────────────────────────────────────────────────────────
    # B. WALK-FORWARD (no peeking)
    # ───────────────────────────────────────────────────────────
    print()
    print("=== B. WALK-FORWARD: tune on first 6 days, validate on last 6 days ===")
    n = len(days_sorted)
    train_days = days_sorted[:n//2]
    test_days  = days_sorted[n//2:]
    print(f"  Train: {train_days[0]} → {train_days[-1]} ({len(train_days)} days)")
    print(f"  Test:  {test_days[0]} → {test_days[-1]} ({len(test_days)} days)")

    # Tune on train: try several configs, pick best on train, report performance on test
    print(f"  Searching train for best config...")
    best_train = None
    for sl_buf in [0.05, 0.10, 0.20, 0.50, 1.0]:
        for trend in [0.5, 1.0, 2.0, 5.0]:
            for peak_lb in [5, 10, 20, 30]:
                train_cache = {d: cache[d] for d in train_days}
                by_d = run_with_params(train_cache, h1_fvgs, sl_buf, trend, peak_lb, False, LOTS)
                tot = total_pnl(by_d)
                if best_train is None or tot > best_train[0]:
                    best_train = (tot, sl_buf, trend, peak_lb)
    tot_tr, sl_b, trd, pkl = best_train
    print(f"  Best train config: SL=${sl_b}, trend=${trd}, peak={pkl}  → train total ${tot_tr:+.1f}")
    # Apply same config to test (UNSEEN)
    test_cache = {d: cache[d] for d in test_days}
    by_d_test = run_with_params(test_cache, h1_fvgs, sl_b, trd, pkl, False, LOTS)
    tot_test = total_pnl(by_d_test)
    p_test = pwin(by_d_test)
    n_test = sum(len(v) for v in by_d_test.values())
    print(f"  Test (unseen): n={n_test}, pwin={p_test:.2f}, TOTAL ${tot_test:+.1f}")
    print(f"  Verdict: {'✅ edge survives' if tot_test > 0 else '🔴 edge does NOT survive'} on held-out data")
    print(f"  Projection if real edge ≈ test result: ${tot_test*4:+.1f} / 6 days @ 0.40 lots")

    # Also: how does the DEPLOYED config perform on test alone?
    by_d_test_deployed = run_with_params(test_cache, h1_fvgs, SL_BUF, TREND, PEAK_LB, REQUIRE_FVG, LOTS)
    tot_test_dep = total_pnl(by_d_test_deployed)
    p_test_dep = pwin(by_d_test_deployed)
    n_test_dep = sum(len(v) for v in by_d_test_deployed.values())
    print(f"  Deployed config (SL=$0.10, trend=$1, peak=10) on test: n={n_test_dep}, "
          f"pwin={p_test_dep:.2f}, TOTAL ${tot_test_dep:+.1f}")

    # ───────────────────────────────────────────────────────────
    # C. DRAWDOWN
    # ───────────────────────────────────────────────────────────
    print()
    print("=== C. DRAWDOWN ANALYSIS (deployed config) ===")
    all_trades = []
    for d in days_sorted:
        for t in sorted(by_day[d], key=lambda x: x["fire_time"]):
            all_trades.append((d, t))
    equity = [0.0]
    peak = 0.0
    max_dd = 0.0
    max_consec_losses = 0
    cur_consec = 0
    for d, t in all_trades:
        equity.append(equity[-1] + t["pnl"])
        if equity[-1] > peak: peak = equity[-1]
        dd = peak - equity[-1]
        if dd > max_dd: max_dd = dd
        if t["pnl"] < 0:
            cur_consec += 1
            if cur_consec > max_consec_losses: max_consec_losses = cur_consec
        else:
            cur_consec = 0
    print(f"  Trades total: {len(all_trades)}")
    print(f"  Peak equity: ${peak:+.1f}")
    print(f"  Max drawdown: ${max_dd:.1f}  ({max_dd/max(1, peak)*100:.0f}% of peak)")
    print(f"  Max consecutive losses: {max_consec_losses}")
    print(f"  @ 0.40 lots: max DD ≈ ${max_dd*4:.0f},  worst streak loss ≈ ${max_consec_losses * 46 * 4:.0f}")
    print(f"  → On $500 real account, max DD = {max_dd*4/500*100:.0f}% (NOT 0.40 lots safe if > 30%)")

    # ───────────────────────────────────────────────────────────
    # D. PARAMETER SENSITIVITY
    # ───────────────────────────────────────────────────────────
    print()
    print("=== D. PARAMETER SENSITIVITY (deployed ± perturbations) ===")
    print(f"  {'perturbation':<35} {'n':>5} {'pwin':>6} {'TOTAL':>12}")
    base = (0.10, 1.0, 10)
    perturbations = [
        ("BASELINE",                    0.10, 1.0,  10),
        ("SL ↑ 20% (0.12)",             0.12, 1.0,  10),
        ("SL ↓ 20% (0.08)",             0.08, 1.0,  10),
        ("Trend ↑ 100% ($2)",           0.10, 2.0,  10),
        ("Trend ↓ 50% ($0.5)",          0.10, 0.5,  10),
        ("Peak ↑ 100% (20 bars)",       0.10, 1.0,  20),
        ("Peak ↓ 50% (5 bars)",         0.10, 1.0,  5),
        ("SL ↑20% + Peak↑100%",         0.12, 1.0,  20),
        ("SL ↓20% + Trend↓50%",         0.08, 0.5,  10),
    ]
    for label, sl, tr, pk in perturbations:
        by_d = run_with_params(cache, h1_fvgs, sl, tr, pk, False, LOTS)
        tot = total_pnl(by_d)
        n_ = sum(len(v) for v in by_d.values())
        pw = pwin(by_d)
        delta = ""
        if label != "BASELINE":
            base_tot = -1
            for lab2, sl2, tr2, pk2 in perturbations:
                if lab2 == "BASELINE":
                    by_d_b = run_with_params(cache, h1_fvgs, sl2, tr2, pk2, False, LOTS)
                    base_tot = total_pnl(by_d_b)
                    break
            delta = f"  Δ vs baseline: {(tot-base_tot)/max(1,abs(base_tot))*100:+.0f}%"
        marker = " ✅" if tot > 0 else " 🔴"
        print(f"  {label:<35} {n_:>5} {pw:>5.2f}  ${tot:>+8.1f}{marker}{delta}")

    # ───────────────────────────────────────────────────────────
    # E. EXTREMES
    # ───────────────────────────────────────────────────────────
    print()
    print("=== E. EXTREMES (deployed config, individual trades) ===")
    flat = [t for v in by_day.values() for t in v]
    flat.sort(key=lambda x: x["pnl"])
    worst = [f"{t['pnl']:+.1f}" for t in flat[:3]]
    best  = [f"{t['pnl']:+.1f}" for t in flat[-3:][::-1]]
    print(f"  Worst 3 trades: {worst}")
    print(f"  Best 3 trades:  {best}")
    print(f"  P&L distribution percentiles:")
    import statistics
    pnls = [t["pnl"] for t in flat]
    if pnls:
        print(f"    P10: ${sorted(pnls)[len(pnls)//10]:+.1f}  "
              f"P50: ${statistics.median(pnls):+.1f}  "
              f"P90: ${sorted(pnls)[9*len(pnls)//10]:+.1f}")

    print()
    print("="*78)
    print("  SUMMARY — read this carefully before going live")
    print("="*78)


if __name__ == "__main__":
    main()
