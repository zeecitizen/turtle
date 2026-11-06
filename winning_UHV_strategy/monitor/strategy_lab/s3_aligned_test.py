"""s3_aligned_test.py — PROPER S3 oracle: build M1 bars FROM the tick files, where
bar volume = tick-count per minute (which IS native MT5 tick_volume). So this is BOTH
time-aligned with execution AND has live-matching volume — dissolving both the
alignment bug AND the rev-eng-volume mismatch. Run S3.detect on these bars, replay on
the same ticks with the live exit (trail 0.3/0.3 + SL/TP), and compare BUY-only vs
SELL-only vs BOTH. Honest: multi-day, WR, total, drawdown, train/test split.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_ticks, COMMON
import s3_full_m1 as S3
import bisect
PPP=1.0; COST=0.20; TACT=0.3; TGIVE=0.3

def m1_from_ticks(tk):
    """M1 OHLC from mid, volume = tick count (== native tick_volume)."""
    bars=[]; cur=None
    for x in tk:
        m=x["t"].replace(second=0,microsecond=0); mid=(x["bid"]+x["ask"])/2
        if cur is None or m!=cur["t"]:
            if cur: bars.append(cur)
            cur={"t":m,"o":mid,"h":mid,"l":mid,"c":mid,"v":1}
        else:
            cur["h"]=max(cur["h"],mid); cur["l"]=min(cur["l"],mid); cur["c"]=mid; cur["v"]+=1
    if cur: bars.append(cur)
    return bars

def walk(tk, k, side, sl, tp, trail):
    e=tk[k]["ask"] if side>0 else tk[k]["bid"]; peak=0.0; cur_sl=sl
    for j in range(k,min(len(tk),k+20000)):
        bid,ask=tk[j]["bid"],tk[j]["ask"]; px=bid if side>0 else ask
        pnl=((px-e) if side>0 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if trail and peak>=TACT and pnl<=max(0.0,peak-TGIVE): return pnl-COST
        if side>0:
            if bid<=cur_sl: return (cur_sl-e)-COST
            if bid>=tp: return (tp-e)-COST
        else:
            if ask>=cur_sl: return (e-cur_sl)-COST
            if ask<=tp: return (e-tp)-COST
    last=tk[-1]; px=last["bid"] if side>0 else last["ask"]
    return (((px-e) if side>0 else (e-px))*PPP)-COST

res={"base":[], "trail":[]}   # (date, pnl)
for path in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
    tk=load_ticks(path)
    if len(tk)<5000: continue
    day=Path(path).stem.split("_")[-1]
    bars=m1_from_ticks(tk); T=[x["t"] for x in tk]
    fired=set()
    for i in range(len(bars)):
        for buy in (True,False):
            r=S3.detect(bars,i,buy)
            if r and r["ref_t"] not in fired:
                fired.add(r["ref_t"])
                ft=r["bo_t"]+timedelta(minutes=1); k=bisect.bisect_left(T,ft)
                if k>=len(tk): continue
                res["base"].append((day,walk(tk,k,r["side"],r["sl"],r["tp"],False)))
                res["trail"].append((day,walk(tk,k,r["side"],r["sl"],r["tp"],True)))

def rep(label, rows):
    if not rows: print(f"  {label:<12} (none)"); return
    rows=sorted(rows); n=len(rows); tot=sum(p for _,p in rows); w=sum(1 for _,p in rows if p>0)
    half=rows[n//2][0]
    t1=sum(p for d,p in rows if d<half); t2=sum(p for d,p in rows if d>=half)
    eq=0;pk=0;mdd=0
    for _,p in rows: eq+=p;pk=max(pk,eq);mdd=max(mdd,pk-eq)
    print(f"  {label:<12}{n:>5}{100*w/n:>6.0f}%{tot:>+9.0f}{tot/n:>+8.2f}{mdd:>8.0f}{t1:>+8.0f}{t2:>+8.0f}")

print("S3 on tick-derived bars (aligned + real tick-volume), 19 days — does the TRAIL help?\n")
print(f"  {'exit':<12}{'n':>5}{'WR%':>6}{'TOTAL':>9}{'EV':>8}{'maxDD':>8}{'1stH':>8}{'2ndH':>8}")
rep("baseline", res["base"]); rep("trail 0.3", res["trail"])
