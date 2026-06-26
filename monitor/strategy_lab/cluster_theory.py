"""cluster_theory.py — test Zee's theory: when several entries fire together (a cluster),
it's strong confluence, so those trades should go into profit FIRST (then maybe reverse).
If true, the TRAIL protects them and we may NOT need to block clusters.

Clean tick build (bars from ticks, generic breakout, entry+path from one tick stream).
A breakout is CLUSTERED if another SAME-DIRECTION breakout fired within 5 min before it
(i.e. it's the 2nd/3rd of a pile-up); else SOLO. For each, on the tick stream:
  - went_green   : floating ever > 0
  - reached_+0.3 : floating ever >= +0.30 (where the trail would arm & protect)
  - outcome under the live exit (trail 0.3/0.3 + a structural SL/TP)
Compare SOLO vs CLUSTERED. Answers: (a) do clusters go green first more? (b) under the
trail, are the clustered (2nd/3rd) trades net positive or negative — i.e. block or keep?
$ = price points @0.01 lot.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s1_uhv_breakout import load_ticks, COMMON
import bisect
PPP=1.0; COST=0.20; TACT=0.3; TGIVE=0.3

def m1_from_ticks(ticks):
    bars=[]; cur=None
    for tk in ticks:
        m=tk["t"].replace(second=0,microsecond=0); mid=(tk["bid"]+tk["ask"])/2
        if cur is None or m!=cur["t"]:
            if cur: bars.append(cur)
            cur={"t":m,"o":mid,"h":mid,"l":mid,"c":mid}
        else: cur["h"]=max(cur["h"],mid); cur["l"]=min(cur["l"],mid); cur["c"]=mid
    if cur: bars.append(cur)
    return bars

def breakouts(bars):
    out=[]
    for i in range(31,len(bars)):
        tr=bars[i]["c"]-bars[i-30]["c"]
        ph=max(b["h"] for b in bars[i-10:i]); pl=min(b["l"] for b in bars[i-10:i])
        if tr>0.8 and bars[i]["c"]>ph:  out.append((bars[i]["t"]+timedelta(minutes=1),+1))
        if tr<-0.8 and bars[i]["c"]<pl: out.append((bars[i]["t"]+timedelta(minutes=1),-1))
    return out

def sim(ticks, k, side):
    """from entry tick k: trail 0.3/0.3 + structural SL/TP (SL=$4 / TP=$3 generic).
    returns (pnl, went_green, reached03)."""
    e=ticks[k]["ask"] if side>0 else ticks[k]["bid"]
    sl = e-4.0 if side>0 else e+4.0
    tp = e+3.0 if side>0 else e-3.0
    peak=0.0; wg=False; r03=False; t0=ticks[k]["t"]
    for j in range(k, min(len(ticks), k+ if_cap(k))):
        px=ticks[j]["bid"] if side>0 else ticks[j]["ask"]
        pnl=((px-e) if side>0 else (e-px))*PPP
        if pnl>0: wg=True
        if pnl>=0.30: r03=True
        if pnl>peak: peak=pnl
        if peak>=TACT and pnl<=max(0.0,peak-TGIVE): return pnl-COST,wg,r03
        if side>0:
            if px<=sl: return (sl-e)-COST,wg,r03
            if px>=tp: return (tp-e)-COST,wg,r03
        else:
            if px>=sl: return (e-sl)-COST,wg,r03
            if px<=tp: return (e-tp)-COST,wg,r03
    last=ticks[min(len(ticks)-1,k+1)]; px=last["bid"] if side>0 else last["ask"]
    return (((px-e) if side>0 else (e-px))*PPP)-COST,wg,r03

def if_cap(k): return 3000   # ~ up to a few hours of ticks

solo={"n":0,"green":0,"r03":0,"pnl":0.0}; clus=dict(solo)
for path in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
    ticks=load_ticks(Path(path))
    if len(ticks)<5000: continue
    bars=m1_from_ticks(ticks); sigs=breakouts(bars)
    T=[tk["t"] for tk in ticks]
    last_dir_time={}
    for (ft,side) in sigs:
        clustered = side in last_dir_time and (ft-last_dir_time[side]).total_seconds()<=300
        last_dir_time[side]=ft
        k=bisect.bisect_left(T,ft)
        if k>=len(ticks): continue
        pnl,wg,r03=sim(ticks,k,side)
        d=clus if clustered else solo
        d["n"]+=1; d["green"]+=wg; d["r03"]+=r03; d["pnl"]+=pnl

print("Zee's cluster theory — SOLO vs CLUSTERED breakouts (clean ticks, trail+SL/TP)\n")
print(f"  {'group':<12}{'n':>5}{'wentGreen%':>12}{'reached+0.3%':>14}{'TOTAL$':>9}{'avg$':>8}")
for name,d in [("solo",solo),("clustered",clus)]:
    if d["n"]==0: continue
    print(f"  {name:<12}{d['n']:>5}{100*d['green']/d['n']:>11.0f}%{100*d['r03']/d['n']:>13.0f}%{d['pnl']:>+9.0f}{d['pnl']/d['n']:>+8.2f}")
