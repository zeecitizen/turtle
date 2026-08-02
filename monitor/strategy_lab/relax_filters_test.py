"""relax_filters_test.py — which filter cuts frequency the most, and do we stay
profitable if we relax it? Per EA: baseline (current deployed) vs each filter
relaxed -> trades, trades/day, WR, total, EV, + walk-forward (train/test).

All at 0.02 lots for clean comparison. 12 trading days.
"""
import sys, glob
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import (aggregate_to_tf, group_bars_by_day, stats,
                                       find_h1_fvgs as f3)
from backtest_setups import find_h1_fvgs as find_sided
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both
from backtest_teacher_faithful import s3_filter_upper_wick
from s1_video2_backtest import detect_buy as s1b, detect_sell as s1s

CONTRACT=100.0; LOTS=0.02


def rpt(label, trades, ndays):
    r=stats(trades)
    if not r: print(f"  {label:<40} no trades"); return None
    ev=r["pwin"]*r["w_avg"]-(1-r["pwin"])*r["l_avg"]
    pos="OK " if r["total"]>0 else "BAD"
    print(f"  {label:<40} n={r['n']:>3} ({r['n']/ndays:>4.1f}/day) WR={r['pwin']*100:>4.1f}% "
          f"TOT=${r['total']:>+7.1f} EV=${ev:+5.2f} {pos}")
    return r


def main():
    print("Loading 12d...")
    bars=load_m1_merged(); days_bars=group_bars_by_day(bars)
    m5_bull=f3(aggregate_to_tf(bars,5)); h1=aggregate_to_tf(bars,60)
    allf=find_sided(aggregate_to_tf(bars,60))
    h1_bull=[f for f in allf if f["side"]=="bullish"]; h1_bear=[f for f in allf if f["side"]=="bearish"]
    m15=aggregate_to_tf(bars,15)
    cache={}
    for tf in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
        day=Path(tf).stem.split("_")[-1]
        if day not in days_bars: continue
        db=days_bars[day]
        if len(db)<30: continue
        ticks=load_ticks(tf)
        if len(ticks)<100: continue
        cache[day]={"m5":aggregate_to_tf(db,5),"m1":db,"ticks":ticks}
    days=sorted(cache.keys()); nd=len(days); mid=nd//2; train,test=days[:mid],days[mid:]
    print(f"  {nd} days\n")

    def s3_run(dys, require_fvg, wick):
        tr=[]
        for d in dys:
            c=cache[d]
            sigs=s3_ea_mirror(c["m5"], sl_buf=2.0, h1_fvgs=m5_bull, require_fvg=require_fvg)
            for s in sigs: s["side"]=+1
            if wick: sigs=s3_filter_upper_wick(c["m5"], sigs, 0.35)
            if sigs: tr+=replay_ticks_both(c["ticks"],sigs,LOTS,CONTRACT)
        return tr
    def s1_run(dys, big_spread):
        tr=[]
        for d in dys:
            c=cache[d]; sigs=[]; fired=set()
            for idx in range(30,len(c["m5"])):
                for det,fv in [(s1b,h1_bull),(s1s,h1_bear)]:
                    sg=det(c["m5"],idx,fv,sl_buf=2.0,tp_points=7.5,big_spread=big_spread,spread_mult=1.3)
                    if sg and sg["ref"] not in fired: sigs.append(sg); fired.add(sg["ref"])
            if sigs: tr+=replay_ticks_both(c["ticks"],sigs,LOTS,CONTRACT)
        return tr
    def ns_run(dys, use_h1):
        tr=[]
        for d in dys:
            c=cache[d]
            # nsnd_ea_mirror uses M15-or-H1 internally; to relax we'd need a flag.
            # The mirror always checks M15 (+H1). Current deployed = M15-only handled in EA;
            # here mirror approximates current (M15+H1 in mirror). Report as-is.
            sigs=nsnd_ea_mirror(c["m1"], m15, h1, vol_min=3, trend_th=2.0, use_hhhl=False)
            if sigs: tr+=replay_ticks_both(c["ticks"],sigs,LOTS,CONTRACT)
        return tr

    print("="*86); print("  S3 — biggest trade-cutter is the M5-FVG filter. Relax it?"); print("="*86)
    rpt("CURRENT (M5-FVG on + wick<=0.35)", s3_run(days,True,True), nd)
    rpt("relax wick only (M5-FVG on)",      s3_run(days,True,False), nd)
    rpt("relax M5-FVG only (wick on)",      s3_run(days,False,True), nd)
    rpt("relax BOTH (no FVG, no wick)",     s3_run(days,False,False), nd)
    print("  -- walk-forward: relax M5-FVG (keep wick) --")
    rpt("    TRAIN", s3_run(train,False,True), len(train))
    rpt("    TEST(OOS)", s3_run(test,False,True), len(test))
    print("  -- walk-forward: relax BOTH --")
    rpt("    TRAIN", s3_run(train,False,False), len(train))
    rpt("    TEST(OOS)", s3_run(test,False,False), len(test))

    print("\n"+"="*86); print("  S1 — biggest cutter is the big-spread filter. Relax it?"); print("="*86)
    rpt("CURRENT (big-spread 1.3x)", s1_run(days,True), nd)
    rpt("relax big-spread (off)",    s1_run(days,False), nd)
    print("  -- walk-forward: big-spread OFF --")
    rpt("    TRAIN", s1_run(train,False), len(train))
    rpt("    TEST(OOS)", s1_run(test,False), len(test))

    print("\n"+"="*86); print("  NSND — current config (M15 FVG)"); print("="*86)
    rpt("CURRENT (M15 fvg, vol_min=3)", ns_run(days,False), nd)


if __name__ == "__main__":
    main()
