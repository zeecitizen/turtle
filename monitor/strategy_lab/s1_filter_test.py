"""s1_filter_test.py — does enabling S1's H1-FVG filter restore edge on the trustworthy
aligned oracle? It was disabled based on the misaligned backtest. Now re-test honestly:
require_fvg=False (current live) vs require_fvg=True (filter on). Baseline exit.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs
from backtest_v349_multiday import load_ticks, COMMON
import bisect
PPP=1.0; COST=0.20

ALLBARS=[]; DAYTICKS={}
for path in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
    tk=load_ticks(path)
    if len(tk)<5000: continue
    DAYTICKS[Path(path).stem.split("_")[-1]]=tk
    cur=None
    for x in tk:
        m=x["t"].replace(second=0,microsecond=0); mid=(x["bid"]+x["ask"])/2
        if cur is None or m!=cur["time"]:
            if cur: ALLBARS.append(cur)
            cur={"time":m,"open":mid,"high":mid,"low":mid,"close":mid,"vol":1}
        else: cur["high"]=max(cur["high"],mid); cur["low"]=min(cur["low"],mid); cur["close"]=mid; cur["vol"]+=1
    if cur: ALLBARS.append(cur)
ALLBARS.sort(key=lambda b:b["time"])
days=group_bars_by_day(ALLBARS)
h1=aggregate_to_tf(ALLBARS,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]

def ticks_for(t): return DAYTICKS.get(t.strftime("%Y-%m-%d"))
def walk(tk,k,side,sl,tp):
    e=tk[k]["ask"] if side>0 else tk[k]["bid"]
    for j in range(k,min(len(tk),k+20000)):
        bid,ask=tk[j]["bid"],tk[j]["ask"]
        if side>0:
            if bid<=sl: return (sl-e)-COST
            if bid>=tp: return (tp-e)-COST
        else:
            if ask>=sl: return (e-sl)-COST
            if ask<=tp: return (e-tp)-COST
    last=tk[-1]; px=last["bid"] if side>0 else last["ask"]
    return (((px-e) if side>0 else (e-px))*PPP)-COST

def run(require_fvg):
    sigs=[]
    for day in sorted(days):
        db=days[day]
        if len(db)<35: continue
        for s in s1_mirror(db,hb,he,sl_buf=2.0,tp_points=2.0,do_buy=True,do_sell=True,require_fvg=require_fvg,require_sweep=True):
            sigs.append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],
                         "fire_time":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
    rows=[]
    for s in sigs:
        tk=ticks_for(s["fire_time"])
        if not tk: continue
        T=[x["t"] for x in tk]; k=bisect.bisect_left(T,s["fire_time"])
        if k>=len(tk): continue
        rows.append((s["fire_time"], walk(tk,k,s["side"],s["sl"],s["tp"])))
    return rows

print("S1 filter test on aligned oracle (baseline exit, real tick-volume)\n")
print(f"  {'config':<20}{'n':>5}{'WR%':>6}{'TOTAL':>9}{'EV':>8}{'1stH':>8}{'2ndH':>8}")
for lbl,fvg in [("FVG off (current)",False),("FVG required",True)]:
    rows=run(fvg)
    if not rows: print(f"  {lbl:<20}(none)"); continue
    rows.sort(); n=len(rows); tot=sum(p for _,p in rows); w=sum(1 for _,p in rows if p>0)
    half=rows[n//2][0]; t1=sum(p for d,p in rows if d<half); t2=sum(p for d,p in rows if d>=half)
    print(f"  {lbl:<20}{n:>5}{100*w/n:>5.0f}%{tot:>+9.0f}{tot/n:>+8.2f}{t1:>+8.0f}{t2:>+8.0f}")
