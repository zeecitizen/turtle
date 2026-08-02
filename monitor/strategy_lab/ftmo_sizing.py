"""ftmo_sizing.py — find the FTMO-safe lot multiplier.

FTMO Challenge ($10k): target +$500, daily loss limit -$300 (HARD FAIL),
trailing max loss -$1000. Binding constraint = the -$300 daily limit.

Method: build each EA's per-day P&L at 0.02 lots (12d real ticks), combine at the
DEPLOYED EV weights (S3 0.03 / S1 0.02 / NSND 0.01 -> multipliers 1.5/1.0/0.5),
then sweep an overall multiplier M. For each M report avg/day, WORST day,
max drawdown, est. days-to-$500, and whether it stays FTMO-safe.

Safety rule: keep the worst BACKTEST day <= 50% of the -$300 limit (i.e. >= -$150),
because live worst days run bigger than in-sample (e.g. live -$32 already > backtest -$12).
"""
import sys, glob
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_m1_merged, load_ticks, COMMON
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, find_h1_fvgs as f3
from backtest_setups import find_h1_fvgs as find_sided
from ea_mirror_validate import s3_ea_mirror, nsnd_ea_mirror
from backtest_s1_uhv_breakout import replay_ticks_both
from s1_video2_backtest import detect_buy as s1b, detect_sell as s1s

CONTRACT=100.0; BASE=0.02
DAILY_LIMIT=-300; TRAIL_MAX=-1000; TARGET=500
DEPLOY={"S3":0.03,"S1":0.02,"NSND":0.01}  # mult vs 0.02 = 1.5/1.0/0.5


def day_pnl(ticks, sigs):
    if not sigs: return 0.0
    return sum(t["pnl"] for t in replay_ticks_both(ticks, sigs, BASE, CONTRACT))


def main():
    print("Loading 12d...")
    bars=load_m1_merged(); db=group_bars_by_day(bars)
    m5_bull=f3(aggregate_to_tf(bars,5)); h1=aggregate_to_tf(bars,60)
    allf=find_sided(aggregate_to_tf(bars,60))
    h1_bull=[f for f in allf if f["side"]=="bullish"]; h1_bear=[f for f in allf if f["side"]=="bearish"]
    m15=aggregate_to_tf(bars,15)
    cache={}
    for tf in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
        d=Path(tf).stem.split("_")[-1]
        if d not in db: continue
        bb=db[d]
        if len(bb)<30: continue
        tk=load_ticks(tf)
        if len(tk)<100: continue
        cache[d]={"m5":aggregate_to_tf(bb,5),"m1":bb,"ticks":tk}
    days=sorted(cache)
    # per-day combined P&L at DEPLOYED weights (S3 1.5x, S1 1.0x, NSND 0.5x of 0.02-series)
    daily=[]
    for d in days:
        c=cache[d]
        s3=s3_ea_mirror(c["m5"],sl_buf=2.0,h1_fvgs=m5_bull,require_fvg=True)
        for s in s3: s["side"]=+1
        s3p=day_pnl(c["ticks"],s3)*(DEPLOY["S3"]/BASE)
        s1=[]; fired=set()
        for idx in range(30,len(c["m5"])):
            for det,fv in [(s1b,h1_bull),(s1s,h1_bear)]:
                sg=det(c["m5"],idx,fv,sl_buf=2.0,tp_points=7.5,big_spread=True,spread_mult=1.3)
                if sg and sg["ref"] not in fired: s1.append(sg); fired.add(sg["ref"])
        s1p=day_pnl(c["ticks"],s1)*(DEPLOY["S1"]/BASE)
        ns=nsnd_ea_mirror(c["m1"],m15,h1,vol_min=3,trend_th=2.0,use_hhhl=False)
        nsp=day_pnl(c["ticks"],ns)*(DEPLOY["NSND"]/BASE)
        daily.append(s3p+s1p+nsp)

    def maxdd(series, M):
        cum=peak=dd=0
        for v in series:
            cum+=v*M; peak=max(peak,cum); dd=min(dd,cum-peak)
        return dd
    avg=sum(daily)/len(daily); worst=min(daily); total=sum(daily)
    print(f"\n  DEPLOYED lots (S3 .03/S1 .02/NSND .01), 12d: avg/day=${avg:+.1f} worst=${worst:+.1f} "
          f"total=${total:+.1f} maxDD=${maxdd(daily,1):.1f}  (M=1 baseline)")
    print(f"\n  FTMO: target +${TARGET}, daily limit ${DAILY_LIMIT}, trailing ${TRAIL_MAX}")
    print("  Safety rule: keep worst backtest day >= -$150 (50% buffer on the daily limit)\n")
    print(f"  {'mult M':>6} {'lots S3/S1/NSND':<18} {'avg/day':>8} {'worst day':>10} {'maxDD':>8} "
          f"{'days→$500':>10} {'FTMO-safe?':>11}")
    for M in [1,2,3,4,5,6,8]:
        lots=f"{DEPLOY['S3']*M:.2f}/{DEPLOY['S1']*M:.2f}/{DEPLOY['NSND']*M:.2f}"
        a=avg*M; w=worst*M; dd=maxdd(daily,M)
        days=TARGET/a if a>0 else 999
        safe = (w >= -150) and (dd >= TRAIL_MAX)   # worst day within 50% buffer + DD ok
        flag = "OK" if safe else ("worst>limit" if w<DAILY_LIMIT else "thin buffer")
        print(f"  {M:>5}x {lots:<18} ${a:>+6.1f} ${w:>+9.1f} ${dd:>+7.1f} {days:>9.1f} {flag:>11}")


if __name__=="__main__":
    main()
