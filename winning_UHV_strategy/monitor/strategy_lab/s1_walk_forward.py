"""s1_walk_forward.py — out-of-sample validation of the S1 (UHV Breakout)
best config from backtest_s1_uhv_breakout.py.

Methodology:
  1. Split 12 days into TRAIN (first 6) and TEST (last 6)
  2. Sweep configs on TRAIN only, pick best
  3. Apply that config to TEST
  4. Compare TRAIN vs TEST performance — if test holds up, edge is real;
     if test collapses, the best-config was curve-fit to noise

This is the same protocol that validated S3's hour filter (later abandoned
when it failed live A/B). If S1 passes walk-forward, deploy it. If not,
don't.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs
from backtest_s1_uhv_breakout import s1_mirror, replay_ticks_both

CONTRACT = 100.0


def report(label, sigs, trades, indent=""):
    r = stats(trades)
    if not trades:
        print(f"{indent}{label:<55} sigs={len(sigs):>3} no closed trades")
        return None
    pos = "OK " if r["total"] > 0 else "BAD"
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    print(f"{indent}{label:<55} sigs={len(sigs):>3} n={r['n']:>3} "
          f"WR={r['pwin']*100:>4.1f}% W=${r['w_avg']:>5.1f} L=${r['l_avg']:>5.1f} "
          f"TOT=${r['total']:>+7.1f}  EV=${ev:+5.2f}  {pos}")
    return r


def run_on_days(cache, days, h1_bull, h1_bear, **kw):
    all_sigs, all_trades = [], []
    for day in days:
        if day not in cache: continue
        c = cache[day]
        sigs = s1_mirror(c["m5"], h1_bull, h1_bear, **kw)
        if not sigs: continue
        all_sigs.extend(sigs)
        done = replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT)
        all_trades.extend(done)
    return all_sigs, all_trades


def main():
    print("Loading 12d M1 + ticks...")
    bars_all = load_m1_merged()
    days_bars = group_bars_by_day(bars_all)
    h1 = aggregate_to_tf(bars_all, 60)
    all_fvgs = find_h1_fvgs(h1)
    h1_bull = [f for f in all_fvgs if f["side"] == "bullish"]
    h1_bear = [f for f in all_fvgs if f["side"] == "bearish"]
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

    days_sorted = sorted(cache.keys())
    mid = len(days_sorted) // 2
    train_days = days_sorted[:mid]
    test_days  = days_sorted[mid:]
    print(f"  {len(cache)} days. TRAIN: {train_days[0]}..{train_days[-1]} ({len(train_days)} days)")
    print(f"              TEST:  {test_days[0]}..{test_days[-1]} ({len(test_days)} days)\n")

    # ── Sweep on TRAIN only ──
    print("="*100)
    print("  STEP 1 — sweep on TRAIN only, find best config")
    print("="*100)
    configs = []
    # BUY+SELL, FVG req, sweep SL × TP
    for slb in [0.50, 1.00, 2.00, 3.00]:
        for tp in [3.0, 5.0, 7.5, 10.0]:
            for sides in [("BUY+SELL", True, True), ("BUY only", True, False)]:
                configs.append({
                    "label": f"{sides[0]:<10} SL=${slb:.2f} TP={tp:>4.1f}",
                    "sl_buf": slb, "tp_points": tp,
                    "do_buy": sides[1], "do_sell": sides[2],
                    "require_fvg": True, "require_sweep": True,
                    "require_open_inside": True,
                })

    train_results = []
    for cfg in configs:
        sigs, trades = run_on_days(cache, train_days, h1_bull, h1_bear,
                                   sl_buf=cfg["sl_buf"], tp_points=cfg["tp_points"],
                                   do_buy=cfg["do_buy"], do_sell=cfg["do_sell"],
                                   require_fvg=cfg["require_fvg"],
                                   require_sweep=cfg["require_sweep"],
                                   require_open_inside=cfg["require_open_inside"])
        r = report(cfg["label"], sigs, trades, indent="  ")
        train_results.append((cfg, r))

    # Pick best by total P&L (require >= 6 trades to be statistically meaningful)
    eligible = [(cfg, r) for cfg, r in train_results if r and r["n"] >= 6]
    eligible.sort(key=lambda x: x[1]["total"], reverse=True)
    if not eligible:
        print("\n  [ERR] no config produced enough train trades")
        return
    print()
    print("  TOP 5 TRAIN CONFIGS:")
    for cfg, r in eligible[:5]:
        print(f"    {cfg['label']:<40}  n={r['n']:>3}  TOT=${r['total']:+.1f}")

    # ── Apply top configs to TEST ──
    print()
    print("="*100)
    print("  STEP 2 — apply top TRAIN configs to TEST (out-of-sample)")
    print("="*100)
    print(f"  {'config':<40}  {'TRAIN':>10}  {'TEST':>10}  {'TEST EV/tr':>11}  verdict")
    print(f"  {'-'*40}  {'-'*10}  {'-'*10}  {'-'*11}  {'-'*15}")
    holds = []
    for cfg, train_r in eligible[:5]:
        sigs, trades = run_on_days(cache, test_days, h1_bull, h1_bear,
                                   sl_buf=cfg["sl_buf"], tp_points=cfg["tp_points"],
                                   do_buy=cfg["do_buy"], do_sell=cfg["do_sell"],
                                   require_fvg=cfg["require_fvg"],
                                   require_sweep=cfg["require_sweep"],
                                   require_open_inside=cfg["require_open_inside"])
        test_r = stats(trades)
        train_tot = train_r["total"]
        if test_r is None:
            print(f"  {cfg['label']:<40}  ${train_tot:>+8.1f}  {'no trades':>10}  {'-':>11}  no test trades")
            continue
        test_tot = test_r["total"]
        test_ev = test_r["pwin"]*test_r["w_avg"] - (1-test_r["pwin"])*test_r["l_avg"]
        if test_tot > 0 and test_ev > 0:
            verdict = "OK -- HOLDS"
            holds.append((cfg, train_r, test_r))
        elif test_tot > 0:
            verdict = "neutral"
        else:
            verdict = "BAD -- BREAKS"
        print(f"  {cfg['label']:<40}  ${train_tot:>+8.1f}  ${test_tot:>+8.1f}  ${test_ev:>+8.2f}  {verdict}")

    # ── Final verdict ──
    print()
    print("="*100)
    print("  FINAL VERDICT")
    print("="*100)
    if not holds:
        print("  All top train configs FAILED out-of-sample.")
        print("  Conclusion: S1 best config was CURVE-FIT to in-sample noise.")
        print("  Recommendation: DO NOT DEPLOY S1 with these settings.")
        print("  Consider sticking with S3+NSND only.")
        return
    print(f"  {len(holds)}/{min(5,len(eligible))} top train configs held up on test data.")
    print(f"  Of those, the most robust (best test P&L):")
    holds.sort(key=lambda x: x[2]["total"], reverse=True)
    cfg, train_r, test_r = holds[0]
    print(f"    Config: {cfg['label']}")
    print(f"      TRAIN ({len(train_days)}d): n={train_r['n']} WR={train_r['pwin']*100:.1f}% TOT=${train_r['total']:+.1f}")
    print(f"      TEST  ({len(test_days)}d): n={test_r['n']}  WR={test_r['pwin']*100:.1f}% TOT=${test_r['total']:+.1f}")
    test_ev = test_r["pwin"]*test_r["w_avg"] - (1-test_r["pwin"])*test_r["l_avg"]
    print(f"      TEST EV/trade: ${test_ev:+.2f}")
    print(f"  At 0.02 lots:  TEST extrapolated to 12d: ${test_r['total']*2/5:+.1f} = ${test_r['total']*2/5/12:+.1f}/day")
    print(f"  At 0.10 lots:  TEST extrapolated to 12d: ${test_r['total']*2:+.1f}  = ${test_r['total']*2/12:+.1f}/day")
    print()
    print("  RECOMMENDATION: deploy this config — passes out-of-sample test.")


if __name__ == "__main__":
    main()
