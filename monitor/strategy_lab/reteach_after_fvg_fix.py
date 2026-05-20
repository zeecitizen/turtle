"""reteach_after_fvg_fix.py — re-test the teacher theories we REJECTED, now
combined with the FVG-timeframe insight (use same/immediate-higher TF FVG,
not coarse H1). Hypothesis: the teacher's momentum/low-vol breakout filter
and tighter FVG may work better together than alone.

S1: swap H1 FVG -> M5/M15 FVG, then layer momentum + low-vol breakout.
NSND: swap its FVG TF + re-test 1-Day trend on top.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_setups import find_h1_fvgs as find_fvgs_sided
from backtest_s1_uhv_breakout import replay_ticks_both
from backtest_teacher_faithful import (detect_s1_buy_tf, detect_s1_sell_tf)

CONTRACT = 100.0


def rpt(label, trades):
    r = stats(trades)
    if not r:
        print(f"  {label:<46} no trades"); return None
    ev = r["pwin"]*r["w_avg"] - (1-r["pwin"])*r["l_avg"]
    pos = "OK " if r["total"] > 0 else "BAD"
    print(f"  {label:<46} n={r['n']:>3} WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+8.1f} EV=${ev:+6.2f} {pos}")
    return r


def s1_run(cache, bull, bear, mom, lv):
    trades = []
    for day, c in cache.items():
        m5 = c["m5"]; fired = set(); sigs = []
        for idx in range(30, len(m5)):
            for det, fv in [(detect_s1_buy_tf, bull), (detect_s1_sell_tf, bear)]:
                s = det(m5, idx, fv, 2.0, 7.5, require_momentum=mom, require_low_vol=lv)
                if s and s["ref_uhv_t"] not in fired:
                    sigs.append(s); fired.add(s["ref_uhv_t"])
        if sigs:
            trades.extend(replay_ticks_both(c["ticks"], sigs, 0.10, CONTRACT))
    return trades


def main():
    print("Loading 12d real-tick dataset...")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    # Sided FVGs at each TF
    fvg = {}
    for name, k in [("M5",5),("M15",15),("H1",60)]:
        all_f = find_fvgs_sided(aggregate_to_tf(bars, k))
        fvg[name] = ([f for f in all_f if f["side"]=="bullish"],
                     [f for f in all_f if f["side"]=="bearish"])
        print(f"  {name}: bull={len(fvg[name][0])} bear={len(fvg[name][1])}")

    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "ticks": ticks}
    print(f"  {len(cache)} days\n")

    print("="*94)
    print("  S1 — FVG timeframe swap x teacher momentum/low-vol filters (SL=$2 TP=$7.5 BUY+SELL)")
    print("="*94)
    for tfn in ["H1","M15","M5"]:
        bull, bear = fvg[tfn]
        print(f"  -- FVG TF = {tfn} --")
        rpt(f"  {tfn} FVG, no teacher filters (baseline)", s1_run(cache,bull,bear,False,False))
        rpt(f"  {tfn} FVG + momentum candle",              s1_run(cache,bull,bear,True, False))
        rpt(f"  {tfn} FVG + low-vol breakout",             s1_run(cache,bull,bear,False,True))
        rpt(f"  {tfn} FVG + momentum + low-vol (full TF)",  s1_run(cache,bull,bear,True, True))
        print()


if __name__ == "__main__":
    main()
