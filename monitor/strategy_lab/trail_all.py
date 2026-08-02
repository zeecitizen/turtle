"""trail_all.py — validate Zee's peak-trail profit-lock on ALL THREE engines
(S1, S3, NSND) before deploying it live. For each engine, compare on real ticks:
baseline (SL/TP) vs fixed BE@$1 (current live) vs trail(act +$0.3, giveback $0.3).
Decide per-engine; only deploy where the trail clearly wins (total + maxDD).
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
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, load_ticks, COMMON
from nsnd_fvg_tf_test import nsnd_signals
import s3_full_m1 as S3
PPP=0.01*100.0; COST=0.40

def load_native(fn="latest_for_claude.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),
                       "close":float(r["close"]),"vol":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["time"]); return b

bars=load_native(); days=group_bars_by_day(bars)
h1=aggregate_to_tf(bars,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]
m15=aggregate_to_tf(bars,15)
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}

nsnd_by={}
for s in nsnd_signals(bars,[(m15,15)]):
    nsnd_by.setdefault(s["fire_time"].strftime("%Y-%m-%d"),[]).append(
        {"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]})

def s1_for(db):
    out=[]
    for s in s1_mirror(db,hb,he,sl_buf=2.0,tp_points=2.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True):
        out.append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
    return out

def s3_for(db):
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
    out=[]; fired=set()
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired:
                fired.add(r["ref_t"]); out.append({"side":r["side"],"sl":r["sl"],"tp":r["tp"],"fire_time":r["bo_t"]+timedelta(minutes=1)})
    return out

def sim(sig, ticks, mode, p1=0.0, p2=0.0):
    side,sl,tp=sig["side"],sig["sl"],sig["tp"]; e=None; peak=0.0; cur_sl=sl
    for tk in ticks:
        if tk["t"]<sig["fire_time"]: continue
        bid,ask=tk["bid"],tk["ask"]
        if e is None: e=ask if side==+1 else bid; cur_sl=sl; continue
        px=bid if side==+1 else ask
        pnl=((px-e) if side==+1 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if mode=="be" and peak>=p1:
            be=e+(0.05 if side==+1 else -0.05)
            cur_sl=max(cur_sl,be) if side==+1 else min(cur_sl,be)
        elif mode=="trail" and peak>=p1:
            floor=max(0.0, peak-p2)
            if pnl<=floor: return floor-COST
        if side==+1:
            if bid<=cur_sl: return (cur_sl-e)*PPP-COST
            if bid>=tp: return (tp-e)*PPP-COST
        else:
            if ask>=cur_sl: return (e-cur_sl)*PPP-COST
            if ask<=tp: return (e-tp)*PPP-COST
    if e is None: return None
    last=ticks[-1]; px=last["bid"] if side==+1 else last["ask"]
    return (((px-e) if side==+1 else (e-px))*PPP)-COST

_TICKS={}
def ticks_for(day):
    if day not in _TICKS: _TICKS[day]=load_ticks(td[day])
    return _TICKS[day]

def build(siggen, per_day_map=None):
    work=[]
    for day in sorted(days):
        if day not in td: continue
        db=days[day]
        if len(db)<35: continue
        sg = per_day_map.get(day,[]) if per_day_map is not None else siggen(db)
        if sg: work.append((day,sg,ticks_for(day)))
    return work

def run(work,mode,p1=0.0,p2=0.0):
    allc=[]; perday={}
    for day,sg,ticks in work:
        for s in sg:
            r=sim(s,ticks,mode,p1,p2)
            if r is not None: allc.append((s["fire_time"],r)); perday[day]=perday.get(day,0)+r
    allc.sort(key=lambda x:x[0]); eq=0;pk=0;mdd=0
    for _,p in allc: eq+=p;pk=max(pk,eq);mdd=max(mdd,pk-eq)
    n=len(allc); wins=sum(1 for _,p in allc if p>0); wr=100*wins/n if n else 0
    dl=sorted(perday); ok=sum(1 for f in [0.4,0.5,0.6,0.7,0.8] if dl and sum(v for d,v in perday.items() if d>=dl[int(len(dl)*f)])>0)
    wd=min(perday.values()) if perday else 0
    return sum(p for _,p in allc),wr,mdd,wd,n,ok

ENGINES=[("S1",build(s1_for)),("S3",build(s3_for)),("NSND",build(None,nsnd_by))]
print("Peak-trail (act +$0.3, giveback $0.3) vs fixed BE@$1 vs baseline — per engine, real ticks, net cost\n")
print(f"  {'engine / policy':<30} {'TOTAL':>7} {'WR%':>5} {'maxDD':>6} {'worst':>6} {'n':>4} {'split':>6}")
def line(lbl,res): print(f"  {lbl:<30} {res[0]:>+7.0f} {res[1]:>5.0f} {res[2]:>6.0f} {res[3]:>+6.0f} {res[4]:>4} {res[5]:>4}/5")
for name,work in ENGINES:
    line(f"{name}  baseline (SL/TP)", run(work,"base"))
    line(f"{name}  fixed BE @ +$1.0", run(work,"be",1.0))
    line(f"{name}  TRAIL act$0.3 give$0.3", run(work,"trail",0.3,0.3))
    print()
