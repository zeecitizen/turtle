"""s3_m5fvg_walk_forward.py — out-of-sample validation of requiring an M5
FVG tap for S3. Train on first 6 days, test on last 6 days. Compare
no-FVG (current live) vs M5-FVG-required on BOTH halves.

If M5-FVG holds its edge on the TEST half, deploy. If it collapses OOS,
it was curve-fit and we keep no-FVG.
"""
import csv, sys, glob
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day, stats,
                                       find_h1_fvgs)
from ea_mirror_validate import s3_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both

CONTRACT = 100.0


def run_days(cache, days, require_fvg, fvgs):
    trades = []
    for day in days:
        if day not in cache: continue
        c = cache[day]
        sigs = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=fvgs, require_fvg=require_fvg)
        for s in sigs: s["side"] = +1
        if not sigs: continue
        trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
    return trades


def line(label, trades):
    r = stats(trades)
    if not r:
        print(f"    {label:<30} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"    {label:<30} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    print("Loading 12d real-tick dataset...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    m5_fvgs = find_h1_fvgs(aggregate_to_tf(bars, 5))   # bullish M5 FVGs
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
    train, test = days_sorted[:mid], days_sorted[mid:]
    print(f"  {len(cache)} days. TRAIN {train[0]}..{train[-1]} | TEST {test[0]}..{test[-1]}\n")

    print("="*78)
    print("  TRAIN (first 6 days)")
    print("="*78)
    line("no FVG (current live)", run_days(cache, train, False, None))
    tr_m5 = line("require M5 FVG", run_days(cache, train, True, m5_fvgs))

    print()
    print("="*78)
    print("  TEST (last 6 days, OUT-OF-SAMPLE)")
    print("="*78)
    te_base = line("no FVG (current live)", run_days(cache, test, False, None))
    te_m5   = line("require M5 FVG", run_days(cache, test, True, m5_fvgs))

    print()
    print("="*78)
    print("  VERDICT")
    print("="*78)
    if te_m5 and te_base:
        ev_base = te_base["pwin"]*te_base["w_avg"] - (1-te_base["pwin"])*te_base["l_avg"]
        ev_m5   = te_m5["pwin"]*te_m5["w_avg"]   - (1-te_m5["pwin"])*te_m5["l_avg"]
        print(f"  OOS no-FVG:  n={te_base['n']} TOT=${te_base['total']:+.1f} EV=${ev_base:+.2f}")
        print(f"  OOS M5-FVG:  n={te_m5['n']} TOT=${te_m5['total']:+.1f} EV=${ev_m5:+.2f}")
        if te_m5["total"] > 0 and ev_m5 > ev_base:
            print(f"\n  M5-FVG HOLDS out-of-sample (positive + better EV than no-FVG). DEPLOY.")
        elif te_m5["total"] > 0:
            print(f"\n  M5-FVG positive OOS but EV not better than no-FVG. Marginal — your call.")
        else:
            print(f"\n  M5-FVG BREAKS out-of-sample (negative). DO NOT deploy — was curve-fit.")


if __name__ == "__main__":
    main()
