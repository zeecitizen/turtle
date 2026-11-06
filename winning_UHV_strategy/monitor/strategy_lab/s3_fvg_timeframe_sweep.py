"""s3_fvg_timeframe_sweep.py — test Zee's idea: instead of requiring an
HOURLY FVG tap (too restrictive, 7 trades/12d), use an FVG from the
IMMEDIATE higher timeframe. S3 runs on M5, so test M5 / M15 / M30 / H1
FVG taps and compare trade count + P&L.

Goal: keep S3's "point of interest" (FVG) edge without killing frequency.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day, stats,
                                       find_h1_fvgs)
from ea_mirror_validate import s3_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both

CONTRACT = 100.0


def rpt(label, trades):
    r = stats(trades)
    if not r:
        print(f"  {label:<34} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"  {label:<34} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"W=${r['w_avg']:>5.1f} L=${r['l_avg']:>5.1f} "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def main():
    print("Loading 12d real-tick dataset...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))

    # Build bullish FVGs at each timeframe (find_h1_fvgs is generic — builds
    # bullish 3-bar gaps from any bar list, format {t0, gap_low, gap_high, filled_at})
    fvg_by_tf = {}
    for tf_name, k in [("M5", 5), ("M15", 15), ("M30", 30), ("H1", 60)]:
        tf_bars = aggregate_to_tf(bars, k)
        fvg_by_tf[tf_name] = find_h1_fvgs(tf_bars)
        print(f"  {tf_name}: {len(tf_bars)} bars, {len(fvg_by_tf[tf_name])} bullish FVGs")

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

    def run(require_fvg, fvgs):
        trades = []
        for day, c in cache.items():
            sigs = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=fvgs,
                                require_fvg=require_fvg)
            for s in sigs: s["side"] = +1
            if not sigs: continue
            trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
        return trades

    print("="*92)
    print("  S3 FVG-tap requirement by timeframe (SL=$2, all else current live)")
    print("="*92)
    rpt("no FVG (current live)", run(False, None))
    for tf_name in ["M5", "M15", "M30", "H1"]:
        rpt(f"require {tf_name} FVG tap", run(True, fvg_by_tf[tf_name]))

    # Also test combined: M5 OR M15 (any lower-TF FVG)
    print()
    print("="*92)
    print("  Combined: require M5-OR-M15 FVG tap (union)")
    print("="*92)
    union_5_15 = fvg_by_tf["M5"] + fvg_by_tf["M15"]
    rpt("require (M5 or M15) FVG tap", run(True, union_5_15))
    union_15_30 = fvg_by_tf["M15"] + fvg_by_tf["M30"]
    rpt("require (M15 or M30) FVG tap", run(True, union_15_30))


if __name__ == "__main__":
    main()
