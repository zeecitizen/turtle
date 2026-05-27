"""tick_breakout_recovery.py — test Zee's theory: a breakout is a bet; if it's a losing
bet, is there a time (in seconds) after which it NEVER recovers to green — past which
holding just feeds the SL?

CLEAN by construction: bars are built FROM the ticks, signals fire at bar close, and the
entry + second-by-second path all come from the SAME tick stream (no alignment possible).
Generic price-only breakout (no volume) so it measures the breakout-bet behaviour itself:
  trend up (close>close[-30]+0.8) & bar closes above prior-10-bar high -> BUY breakout
  trend dn                          & bar closes below prior-10-bar low  -> SELL breakout

For each trade we track floating P&L tick-by-tick (cap 600s). At each elapsed checkpoint T,
among trades RED at T, we report: % that EVER turn green afterward, % that recover to
+$0.30 (where the trail would arm), and the avg eventual P&L if held — i.e. does holding
a still-red breakout just dig deeper?  $ = price points @0.01 lot.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s1_uhv_breakout import load_ticks, COMMON
PPP=1.0; CHECK=[5,10,15,20,30,45,60,90,120,180,300]

def m1_from_ticks(ticks):
    bars=[]; cur=None
    for tk in ticks:
        m=tk["t"].replace(second=0, microsecond=0)
        mid=(tk["bid"]+tk["ask"])/2
        if cur is None or m!=cur["t"]:
            if cur: bars.append(cur)
            cur={"t":m,"o":mid,"h":mid,"l":mid,"c":mid}
        else:
            cur["h"]=max(cur["h"],mid); cur["l"]=min(cur["l"],mid); cur["c"]=mid
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

td=sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv")))
# aggregate stats per checkpoint
red=[0]*len(CHECK); rec=[0]*len(CHECK); rec03=[0]*len(CHECK); held=[0.0]*len(CHECK); deeper=[0.0]*len(CHECK)
ntr=0
for path in td:
    ticks=load_ticks(Path(path))
    if len(ticks)<5000: continue
    bars=m1_from_ticks(ticks)
    sigs=breakouts(bars)
    # index ticks by time for fast forward-walk
    ti=0; T=[tk["t"] for tk in ticks]
    import bisect
    for (ft,side) in sigs:
        k=bisect.bisect_left(T,ft)
        if k>=len(ticks): continue
        e=ticks[k]["ask"] if side>0 else ticks[k]["bid"]
        t0=ticks[k]["t"]
        # build elapsed path
        path_pnl=[]  # (elapsed_sec, pnl)
        j=k; final=None
        while j<len(ticks):
            el=(ticks[j]["t"]-t0).total_seconds()
            if el>600: break
            px=ticks[j]["bid"] if side>0 else ticks[j]["ask"]
            pnl=((px-e) if side>0 else (e-px))*PPP
            path_pnl.append((el,pnl)); final=pnl; j+=1
        if len(path_pnl)<2: continue
        ntr+=1
        for ci,Tc in enumerate(CHECK):
            # pnl at first tick with elapsed>=Tc
            idx=next((x for x,(el,_) in enumerate(path_pnl) if el>=Tc), None)
            if idx is None: continue
            pnl_T=path_pnl[idx][1]
            if pnl_T<0:
                red[ci]+=1
                after=[p for (el,p) in path_pnl[idx:]]
                if any(p>0 for p in after): rec[ci]+=1
                if any(p>=0.30 for p in after): rec03[ci]+=1
                held[ci]+=final          # eventual pnl if held to window end
                deeper[ci]+=min(after)   # worst it digs after T
print(f"ticks days={len(td)}  breakout trades={ntr}\n")
print("Of trades RED at T seconds:  (recovery = ever green again after T)")
print(f"  {'T(s)':>5}{'redN':>7}{'recover%':>10}{'recover>=$0.3%':>15}{'avgHeldPnL':>12}{'avgDeeper':>11}")
for ci,Tc in enumerate(CHECK):
    if red[ci]==0: continue
    print(f"  {Tc:>5}{red[ci]:>7}{100*rec[ci]/red[ci]:>9.0f}%{100*rec03[ci]/red[ci]:>14.0f}%{held[ci]/red[ci]:>+12.2f}{deeper[ci]/red[ci]:>+11.2f}")
