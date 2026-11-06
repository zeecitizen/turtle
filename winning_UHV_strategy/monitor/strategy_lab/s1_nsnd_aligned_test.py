"""s1_nsnd_aligned_test.py — does the trail help or hurt S1 and NSND on the TRUSTWORTHY
oracle (M1 bars built FROM ticks: aligned + real tick-volume)? Compare each engine's
plain structural SL/TP (baseline) vs the live trail (0.3/0.3). Decides whether the trail
should be reverted fleet-wide (cycle 3 already showed it hurts S3).
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs
from backtest_v349_multiday import load_ticks, COMMON
from nsnd_fvg_tf_test import nsnd_signals
import bisect
PPP=1.0; COST=0.20; TACT=0.3; TGIVE=0.3

# build global M1 bars FROM ticks (vol = tick count == native tick_volume), keep per-day ticks
ALLBARS=[]; DAYTICKS={}
for path in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
    tk=load_ticks(path)
    if len(tk)<5000: continue
    day=Path(path).stem.split("_")[-1]; DAYTICKS[day]=tk
    cur=None
    for x in tk:
        m=x["t"].replace(second=0,microsecond=0); mid=(x["bid"]+x["ask"])/2
        if cur is None or m!=cur["time"]:
            if cur: ALLBARS.append(cur)
            cur={"time":m,"open":mid,"high":mid,"low":mid,"close":mid,"vol":1}
        else:
            cur["high"]=max(cur["high"],mid); cur["low"]=min(cur["low"],mid); cur["close"]=mid; cur["vol"]+=1
    if cur: ALLBARS.append(cur)
ALLBARS.sort(key=lambda b:b["time"])
days=group_bars_by_day(ALLBARS)
h1=aggregate_to_tf(ALLBARS,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]
m15=aggregate_to_tf(ALLBARS,15)
print(f"built {len(ALLBARS)} tick-derived M1 bars over {len(DAYTICKS)} days\n")

def ticks_for(dt):
    return DAYTICKS.get(dt.strftime("%Y-%m-%d"))

def walk(tk, k, side, sl, tp, trail):
    e=tk[k]["ask"] if side>0 else tk[k]["bid"]; peak=0.0
    for j in range(k,min(len(tk),k+20000)):
        bid,ask=tk[j]["bid"],tk[j]["ask"]; px=bid if side>0 else ask
        pnl=((px-e) if side>0 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if trail and peak>=TACT and pnl<=max(0.0,peak-TGIVE): return pnl-COST
        if side>0:
            if bid<=sl: return (sl-e)-COST
            if bid>=tp: return (tp-e)-COST
        else:
            if ask>=sl: return (e-sl)-COST
            if ask<=tp: return (e-tp)-COST
    last=tk[-1]; px=last["bid"] if side>0 else last["ask"]
    return (((px-e) if side>0 else (e-px))*PPP)-COST

def replay(sigs, label):
    base=[]; trail=[]
    for s in sigs:
        tk=ticks_for(s["fire_time"])
        if not tk: continue
        T=[x["t"] for x in tk]; k=bisect.bisect_left(T,s["fire_time"])
        if k>=len(tk): continue
        base.append((s["fire_time"], walk(tk,k,s["side"],s["sl"],s["tp"],False)))
        trail.append((s["fire_time"], walk(tk,k,s["side"],s["sl"],s["tp"],True)))
    def line(name,rows):
        if not rows: print(f"  {name:<18}(none)"); return
        rows=sorted(rows); n=len(rows); tot=sum(p for _,p in rows); w=sum(1 for _,p in rows if p>0)
        half=rows[n//2][0]; t1=sum(p for d,p in rows if d<half); t2=sum(p for d,p in rows if d>=half)
        print(f"  {name:<18}{n:>5}{100*w/n:>6.0f}%{tot:>+9.0f}{tot/n:>+8.2f}{t1:>+8.0f}{t2:>+8.0f}")
    print(f"{label}:")
    print(f"  {'exit':<18}{'n':>5}{'WR%':>6}{'TOTAL':>9}{'EV':>8}{'1stH':>8}{'2ndH':>8}")
    line("baseline", base); line("trail 0.3/0.3", trail); print()

# S1 signals (live config: M1, FVG off, sweep on, SL buf 2.0, TP 2.0, buy+sell)
s1=[]
for day in sorted(days):
    db=days[day]
    if len(db)<35: continue
    for s in s1_mirror(db,hb,he,sl_buf=2.0,tp_points=2.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True):
        s1.append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
replay(s1, "S1 (UHV breakout)")

# NSND signals (M15 FVG)
ns=[{"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]} for s in nsnd_signals(ALLBARS,[(m15,15)])]
replay(ns, "NSND (No Supply/Demand)")
