"""s4_trail_test.py — should the trailing profit-lock go on S4 (Feb-11 UHV, magic 88007)?
S4's geometry is lopsided: SL ~$7.5, TP ~$2 — one full stop erases ~4 wins, so a
give-back killer should help a lot. RISK: TP is only $2, so the trail (arm +$0.3,
give-back $0.3) could SCRATCH winners that wobble before reaching the $2 TP. Measure net.

PART A — replay today's ACTUAL 7 S4 trades (from s4_decisions.csv) on real ticks:
   baseline (hold to SL/TP) vs trail. Most faithful — checks both the loser AND the 6 winners.
PART B — breadth: generic trend-breakouts on tick-derived bars (aligned, all 19 days)
   with S4 geometry (SL $7.5 / TP $2), baseline vs trail. $ = price pts @0.01 lot.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_v349_multiday import load_ticks, COMMON
import bisect
PPP=1.0; COST=0.20; TACT=0.3; TGIVE=0.3

def walk(ticks, k, side, sl, tp, mode="base", arm=0.5):
    """mode: 'base' (SL/TP) · 'trail' (arm/give exit) · 'be' (once +$arm, move SL to
    entry and KEEP TP — saves give-back losers without scratching winners)."""
    e = ticks[k]["ask"] if side>0 else ticks[k]["bid"]
    peak=0.0; cur_sl=sl
    for j in range(k, min(len(ticks), k+20000)):
        bid,ask = ticks[j]["bid"], ticks[j]["ask"]
        px = bid if side>0 else ask
        pnl = ((px-e) if side>0 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if mode=="trail" and peak>=TACT and pnl <= max(0.0, peak-TGIVE):
            return pnl-COST
        if mode=="be" and peak>=arm:
            cur_sl = e if side>0 else e        # SL to entry (breakeven), keep TP
        if side>0:
            if bid<=cur_sl: return (cur_sl-e)-COST
            if bid>=tp: return (tp-e)-COST
        else:
            if ask>=cur_sl: return (e-cur_sl)-COST
            if ask<=tp: return (e-tp)-COST
    last=ticks[-1]; px=last["bid"] if side>0 else last["ask"]
    return (((px-e) if side>0 else (e-px))*PPP)-COST

# ---------- PART A: today's real S4 trades ----------
print("PART A — today's ACTUAL S4 trades replayed on real ticks (baseline vs trail)\n")
dec=[]
for r in csv.reader(open(COMMON/"s4_decisions.csv")):
    if len(r)<7 or not r[0].startswith("2026.05.27"): continue
    # time, ea, side, bar_time, entry, sl, tp, ticket, magic, lots
    dec.append({"t":datetime.strptime(r[0],"%Y.%m.%d %H:%M:%S"),"side":1 if r[2]=="buy" else -1,
                "entry":float(r[4]),"sl":float(r[5]),"tp":float(r[6])})
ticks=load_ticks(str(COMMON/"shano_ticks_2026-05-27.csv"))
T=[tk["t"] for tk in ticks]
base_tot=trail_tot=be_tot=0.0
print(f"  {'time':<9}{'side':<5}{'baseline':>10}{'trail':>9}{'BE@0.5':>9}")
for d in dec:
    k=bisect.bisect_left(T,d["t"])
    if k>=len(ticks): continue
    b=walk(ticks,k,d["side"],d["sl"],d["tp"],"base")
    t=walk(ticks,k,d["side"],d["sl"],d["tp"],"trail")
    be=walk(ticks,k,d["side"],d["sl"],d["tp"],"be",0.5)
    base_tot+=b; trail_tot+=t; be_tot+=be
    print(f"  {d['t'].strftime('%H:%M'):<9}{'BUY' if d['side']>0 else 'SELL':<5}{b:>+10.2f}{t:>+9.2f}{be:>+9.2f}")
print(f"  {'TOTAL':<14}{base_tot:>+10.2f}{trail_tot:>+9.2f}{be_tot:>+9.2f}")
print(f"  → trail {trail_tot-base_tot:+.2f} vs base · BE@0.5 {be_tot-base_tot:+.2f} vs base")

# ---------- PART B: breadth on generic breakouts w/ S4 geometry ----------
def m1_from_ticks(tk):
    bars=[]; cur=None
    for x in tk:
        m=x["t"].replace(second=0,microsecond=0); mid=(x["bid"]+x["ask"])/2
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
SL_D, TP_D = 7.5, 2.0
pol={"baseline":("base",0),"trail 0.3/0.3":("trail",0),"BE@0.3":("be",0.3),"BE@0.5":("be",0.5),"BE@0.75":("be",0.75),"BE@1.0":("be",1.0)}
agg={k:{"n":0,"w":0,"pnl":0.0} for k in pol}
for path in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
    tk=load_ticks(path)
    if len(tk)<5000: continue
    bars=m1_from_ticks(tk); sigs=breakouts(bars); T=[x["t"] for x in tk]
    for (ft,side) in sigs:
        k=bisect.bisect_left(T,ft)
        if k>=len(tk): continue
        e=tk[k]["ask"] if side>0 else tk[k]["bid"]
        sl=e-SL_D if side>0 else e+SL_D; tp=e+TP_D if side>0 else e-TP_D
        for name,(m,a) in pol.items():
            r=walk(tk,k,side,sl,tp,m,a)
            agg[name]["n"]+=1; agg[name]["w"]+= (r>0); agg[name]["pnl"]+=r
print("\nPART B — generic breakouts, S4 geometry (SL $7.5 / TP $2), 19 days, net cost")
print(f"  {'policy':<14}{'n':>5}{'WR%':>6}{'TOTAL$':>9}{'avg$':>8}")
for name in pol:
    d=agg[name]; print(f"  {name:<14}{d['n']:>5}{100*d['w']/d['n']:>5.0f}%{d['pnl']:>+9.0f}{d['pnl']/d['n']:>+8.2f}")
