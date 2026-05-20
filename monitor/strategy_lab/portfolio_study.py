"""portfolio_study.py — honest combined picture of the 3 deployed EAs at their
CURRENT best configs, across 12d real ticks. Per-day P&L, total, avg/day,
worst day, max drawdown, per-EA contribution. Reported at 0.02 lots (live size).

Configs (as deployed):
  S3  : buy-only, M5-FVG required, SL=$2  (s3_ea_mirror)
  S1  : BUY+SELL, big-spread climax 1.3x, H1 FVG, SL=$2, TP=$7.5
  NSND: M15-only FVG, vol_min=3, trend=2.0
"""
import sys, glob
from datetime import timedelta
from collections import defaultdict
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats, find_h1_fvgs
from backtest_setups import find_h1_fvgs as find_fvgs_sided
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both
from s1_video2_backtest import detect_buy as s1_buy, detect_sell as s1_sell

CONTRACT = 100.0
LOTS = 0.02   # live size


def day_pnl(ticks, sigs):
    if not sigs: return 0.0, 0, 0
    done = replay_ticks_both(ticks, sigs, LOTS, CONTRACT)
    tot = sum(t["pnl"] for t in done)
    w = sum(1 for t in done if t["pnl"] > 0); l = sum(1 for t in done if t["pnl"] < 0)
    return tot, w, l


def main():
    print(f"Loading 12d... (reported at {LOTS} lots)")
    bars = load_m1_merged()
    days_bars = group_bars_by_day(bars)
    h1 = aggregate_to_tf(bars, 60)
    m5_bull = find_h1_fvgs(aggregate_to_tf(bars, 5))
    allf = find_fvgs_sided(aggregate_to_tf(bars, 60))
    h1_bull = [f for f in allf if f["side"] == "bullish"]
    h1_bear = [f for f in allf if f["side"] == "bearish"]
    m15 = aggregate_to_tf(bars, 15)

    cache = {}
    for tf in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
        day = Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db = days_bars[day]
        if len(db) < 30: continue
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        cache[day] = {"m5": aggregate_to_tf(db, 5), "m1": db, "ticks": ticks}

    days = sorted(cache.keys())
    rows = []
    tot_by_ea = defaultdict(float)
    for day in days:
        c = cache[day]
        # S3 buy-only M5-FVG
        s3 = s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=m5_bull, require_fvg=True)
        for s in s3: s["side"] = +1
        s3p, s3w, s3l = day_pnl(c["ticks"], s3)
        # S1 bidir big-spread
        s1 = []; fired = set()
        for idx in range(30, len(c["m5"])):
            for det, fv in [(s1_buy, h1_bull), (s1_sell, h1_bear)]:
                sig = det(c["m5"], idx, fv, sl_buf=2.0, tp_points=7.5, big_spread=True, spread_mult=1.3)
                if sig and sig["ref"] not in fired:
                    s1.append(sig); fired.add(sig["ref"])
        s1p, s1w, s1l = day_pnl(c["ticks"], s1)
        # NSND M15-only
        ns = nsnd_ea_mirror(c["m1"], m15, h1, vol_min=3, trend_th=2.0, use_hhhl=False)
        nsp, nsw, nsl = day_pnl(c["ticks"], ns)
        combined = s3p + s1p + nsp
        rows.append((day, s3p, s1p, nsp, combined,
                     (s3w+s1w+nsw), (s3l+s1l+nsl)))
        tot_by_ea["S3"] += s3p; tot_by_ea["S1"] += s1p; tot_by_ea["NSND"] += nsp

    print("\n" + "="*86)
    print(f"  PORTFOLIO — 3 EAs combined, per-day P&L @ {LOTS} lots")
    print("="*86)
    print(f"  {'day':<12} {'S3':>9} {'S1':>9} {'NSND':>9} {'COMBINED':>10} {'W':>3} {'L':>3}")
    cum = 0; peak = 0; max_dd = 0; worst = 0; pos_days = 0
    for (day, s3p, s1p, nsp, comb, w, l) in rows:
        cum += comb; peak = max(peak, cum); max_dd = max(max_dd, peak - cum)
        worst = min(worst, comb); pos_days += (comb > 0)
        mark = "+" if comb > 0 else ("-" if comb < 0 else " ")
        print(f"  {day:<12} {s3p:>+9.1f} {s1p:>+9.1f} {nsp:>+9.1f} {comb:>+10.1f} {w:>3} {l:>3} {mark}")
    total = sum(r[4] for r in rows)
    print("  " + "-"*84)
    print(f"  {'TOTAL':<12} {tot_by_ea['S3']:>+9.1f} {tot_by_ea['S1']:>+9.1f} "
          f"{tot_by_ea['NSND']:>+9.1f} {total:>+10.1f}")
    print(f"\n  Combined total 12d @ {LOTS} lots: ${total:+.1f}")
    print(f"  Avg/day: ${total/len(rows):+.1f}   Positive days: {pos_days}/{len(rows)}")
    print(f"  Worst day: ${worst:+.1f}   Max equity drawdown: ${max_dd:.1f}")
    cap = 500
    print(f"  Worst day as % of $500 capital: {abs(worst)/cap*100:.1f}%")
    print(f"  Max DD as % of $500: {max_dd/cap*100:.1f}%")
    # at 0.10 for reference
    print(f"\n  (Reference @0.10 lots = x5: total ${total*5:+.0f}, avg/day ${total/len(rows)*5:+.0f})")


if __name__ == "__main__":
    main()
