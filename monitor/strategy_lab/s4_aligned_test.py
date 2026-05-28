"""s4_aligned_test.py — validate S4 (Feb-11 UHV, M5) on the trustworthy oracle
(M1 bars built from ticks → M5 aggregate; both aligned with execution AND with live
tick-volume = sum of M1 tick counts). Live S4 config:
  InpMomBodyFrac=0.55, InpRetraceLookback=12, InpTrendLookback=30, InpRequireTrend=true,
  InpTrend24Min=7.0, InpTPPts=2.0, InpSLPts=7.5. ER disabled.
Baseline replay (its real fixed SL/TP). If S4 holds up here, morning recommendation
can be constructive ("keep/focus S4") rather than just "pause everything".
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf
from backtest_v349_multiday import load_ticks, COMMON
import bisect
PPP=1.0; COST=0.20
MOM=0.55; RETRO=12; TRENDLB=30; TRENDMIN=7.0; TP=2.0; SL=7.5

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
M5=aggregate_to_tf(ALLBARS,5)
# normalise key names: aggregate_to_tf returns {time,open,high,low,close,vol} or similar — verify
# (we assume it preserves the same keys)
print(f"{len(ALLBARS)} M1 bars → {len(M5)} M5 bars over {len(DAYTICKS)} days\n")

def trend_dir(i):
    """recent half (i-half+1..i) vs prior half (i-2*half+1..i-half). HH+HL=1, LH+LL=-1."""
    half=TRENDLB//2
    if i-2*half<0: return 0
    rHi=max(b["high"] for b in M5[i-half+1:i+1])
    rLo=min(b["low"]  for b in M5[i-half+1:i+1])
    oHi=max(b["high"] for b in M5[i-2*half+1:i-half+1])
    oLo=min(b["low"]  for b in M5[i-2*half+1:i-half+1])
    if rHi>oHi and rLo>oLo: return 1
    if rHi<oHi and rLo<oLo: return -1
    return 0

def signals():
    out=[]
    for i in range(max(TRENDLB,RETRO+1, 25), len(M5)):
        bo=M5[i]
        rng=bo["high"]-bo["low"]
        if rng<=0: continue
        body=abs(bo["close"]-bo["open"])
        if body/rng<MOM: continue
        avgbody=sum(abs(M5[s]["close"]-M5[s]["open"]) for s in range(i-RETRO,i+1))/(RETRO+1)
        if body<avgbody: continue
        td24 = bo["close"] - M5[i-24]["close"]
        td=trend_dir(i)
        # BUY
        if bo["close"]>bo["open"] and td==1 and td24>=TRENDMIN:
            uhv_v=-1; uhv_h=0
            for s in range(i-RETRO,i):                   # shifts 2..13 = i-RETRO .. i-1
                b=M5[s]
                if b["close"]<b["open"] and b["vol"]>uhv_v:
                    uhv_v=b["vol"]; uhv_h=b["high"]
            if uhv_v>0 and bo["vol"]<uhv_v and bo["close"]>uhv_h and bo["open"]<=uhv_h:
                out.append({"side":+1,"fire_time":bo["time"]+timedelta(minutes=5)})
                continue
        # SELL
        if bo["close"]<bo["open"] and td==-1 and td24<=-TRENDMIN:
            uhv_v=-1; uhv_l=0
            for s in range(i-RETRO,i):
                b=M5[s]
                if b["close"]>b["open"] and b["vol"]>uhv_v:
                    uhv_v=b["vol"]; uhv_l=b["low"]
            if uhv_v>0 and bo["vol"]<uhv_v and bo["close"]<uhv_l and bo["open"]>=uhv_l:
                out.append({"side":-1,"fire_time":bo["time"]+timedelta(minutes=5)})
    return out

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

sigs=signals()
res=[]
for s in sigs:
    tk=ticks_for(s["fire_time"])
    if not tk: continue
    T=[x["t"] for x in tk]; k=bisect.bisect_left(T,s["fire_time"])
    if k>=len(tk): continue
    e_intent = tk[k]["ask"] if s["side"]>0 else tk[k]["bid"]
    sl = e_intent-SL if s["side"]>0 else e_intent+SL
    tp = e_intent+TP if s["side"]>0 else e_intent-TP
    res.append((s["fire_time"], walk(tk,k,s["side"],sl,tp)))

print(f"S4 (Feb-11 UHV, M5) on aligned oracle, baseline exit (SL $7.5 / TP $2)")
if not res: print("  no signals"); sys.exit()
res.sort(); n=len(res); tot=sum(p for _,p in res); w=sum(1 for _,p in res if p>0)
half=res[n//2][0]; t1=sum(p for d,p in res if d<half); t2=sum(p for d,p in res if d>=half)
eq=0;pk=0;mdd=0
for _,p in res: eq+=p;pk=max(pk,eq);mdd=max(mdd,pk-eq)
print(f"  {'n':>5}{'WR%':>6}{'TOTAL':>9}{'EV':>8}{'maxDD':>8}{'1stH':>8}{'2ndH':>8}")
print(f"  {n:>5}{100*w/n:>5.0f}%{tot:>+9.0f}{tot/n:>+8.2f}{mdd:>8.0f}{t1:>+8.0f}{t2:>+8.0f}")
