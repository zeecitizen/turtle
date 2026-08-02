"""regime_gate_test.py — do S1/S3 only bleed in CHOP? Test a Kaufman Efficiency Ratio
(ER) gate on the trustworthy oracle (M1 bars from ticks: aligned + live tick-volume).
ER over N bars = |close[i]-close[i-N]| / sum|close step| ; ~1 = clean trend, ~0 = chop.
Only take a signal if ER >= threshold at the signal bar. Baseline exit (structural SL/TP).
If a threshold clearly lifts total AND holds both halves, that's a real, deployable fix.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs
from backtest_v349_multiday import load_ticks, COMMON
import s3_full_m1 as S3
import bisect
PPP=1.0; COST=0.20; ERN=30

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
BT=[b["time"] for b in ALLBARS]; C=[b["close"] for b in ALLBARS]
days=group_bars_by_day(ALLBARS)
h1=aggregate_to_tf(ALLBARS,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]

# precompute ER over ERN M1 bars
ER=[0.0]*len(ALLBARS)
for i in range(ERN,len(ALLBARS)):
    direction=abs(C[i]-C[i-ERN])
    vol=sum(abs(C[j]-C[j-1]) for j in range(i-ERN+1,i+1))
    ER[i]=direction/vol if vol>1e-9 else 0.0
def er_at(t):
    i=bisect.bisect_left(BT,t)-1
    return ER[i] if 0<=i<len(ER) else 0.0

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

# gather signals with ER + outcome
def collect(siggen):
    out=[]
    for s in siggen:
        tk=ticks_for(s["fire_time"])
        if not tk: continue
        T=[x["t"] for x in tk]; k=bisect.bisect_left(T,s["fire_time"])
        if k>=len(tk): continue
        out.append((s["fire_time"], er_at(s["fire_time"]), walk(tk,k,s["side"],s["sl"],s["tp"])))
    return out

s1sig=[]
for day in sorted(days):
    db=days[day]
    if len(db)<35: continue
    for s in s1_mirror(db,hb,he,sl_buf=2.0,tp_points=2.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True):
        s1sig.append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
s3sig=[]
for day in sorted(days):
    db=days[day]
    if len(db)<35: continue
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
    fired=set()
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired:
                fired.add(r["ref_t"]); s3sig.append({"side":r["side"],"sl":r["sl"],"tp":r["tp"],"fire_time":r["bo_t"]+timedelta(minutes=1)})

for name,sigs in [("S1",collect(s1sig)),("S3",collect(s3sig))]:
    print(f"\n{name} — ER gate (baseline exit), aligned oracle")
    print(f"  {'gate':<12}{'n':>5}{'WR%':>6}{'TOTAL':>9}{'EV':>8}{'1stH':>8}{'2ndH':>8}")
    for thr in [0.0,0.2,0.3,0.4,0.5]:
        kept=[(t,p) for t,er,p in sigs if er>=thr]
        if not kept: print(f"  ER>={thr:<8}(none)"); continue
        kept.sort(); n=len(kept); tot=sum(p for _,p in kept); w=sum(1 for _,p in kept if p>0)
        half=kept[n//2][0]; t1=sum(p for d,p in kept if d<half); t2=sum(p for d,p in kept if d>=half)
        print(f"  ER>={thr:<8}{n:>5}{100*w/n:>6.0f}%{tot:>+9.0f}{tot/n:>+8.2f}{t1:>+8.0f}{t2:>+8.0f}")
