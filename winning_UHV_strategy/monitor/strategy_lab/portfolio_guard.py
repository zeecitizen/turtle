"""portfolio_guard.py — anti-cluster guard test. Today's -$44 was 3 engines
buying the same spot at once (-$37 cluster). Merge ALL engines' signals (S1/S3/
NSND @ M1) chronologically, replay per day on real ticks, and test guards that
limit correlated/concurrent entries. Key metric = MAX DRAWDOWN (the cluster pain),
plus total + worst-day. Adopt a guard only if it cuts DD without gutting the edge.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, load_ticks, COMMON
from nsnd_fvg_tf_test import nsnd_signals
import s3_full_m1 as S3
CONTRACT=100.0; PPP=0.01*CONTRACT; COST=0.40

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
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}
m15=aggregate_to_tf(bars,15)
nsnd_by={}
for s in nsnd_signals(bars,[(m15,15)]):
    nsnd_by.setdefault(s["fire_time"].strftime("%Y-%m-%d"),[]).append({"ea":"NSND","side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]})

def day_signals(db):
    sg=[]
    for s in s1_mirror(db,hb,he,sl_buf=2.0,tp_points=3.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True):
        sg.append({"ea":"S1","side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
    fired=set()
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired:
                fired.add(r["ref_t"]); sg.append({"ea":"S3","side":r["side"],"sl":r["sl"],"tp":r["tp"],"fire_time":r["bo_t"]+timedelta(minutes=1)})
    return sg

def allow(guard, units, s, recents, t):
    if guard["type"]=="none": return True
    if guard["type"]=="maxconc": return len(units) < guard["k"]
    if guard["type"]=="onedir": return not any(u["side"]==s["side"] for u in units)
    if guard["type"]=="cooldown":
        return not any((t-rt).total_seconds() < guard["sec"] for rt in recents)
    return True

def replay_day(sigs, ticks, guard):
    sigs=sorted(sigs,key=lambda x:x["fire_time"]); units=[]; closed=[]; recents=[]; si=0
    for tk in ticks:
        t,bid,ask=tk["t"],tk["bid"],tk["ask"]
        for u in units[:]:
            px=bid if u["side"]==+1 else ask
            hit=None
            if u["side"]==+1:
                if bid<=u["sl"]: hit=(u["sl"]-u["e"])*PPP
                elif bid>=u["tp"]: hit=(u["tp"]-u["e"])*PPP
            else:
                if ask>=u["sl"]: hit=(u["e"]-u["sl"])*PPP
                elif ask<=u["tp"]: hit=(u["e"]-u["tp"])*PPP
            if hit is not None: closed.append((t,hit-COST)); units.remove(u)
        while si<len(sigs) and sigs[si]["fire_time"]<=t:
            s=sigs[si]; si+=1
            if allow(guard,units,s,recents,t):
                e=ask if s["side"]==+1 else bid
                units.append({"side":s["side"],"e":e,"sl":s["sl"],"tp":s["tp"]}); recents.append(t)
    if ticks:
        last=ticks[-1]
        for u in units:
            px=last["bid"] if u["side"]==+1 else last["ask"]
            closed.append((last["t"],(((px-u["e"]) if u["side"]==+1 else (u["e"]-px))*PPP)-COST))
    return closed

GUARDS={
 "baseline (no guard)":     {"type":"none"},
 "max 1 concurrent":        {"type":"maxconc","k":1},
 "max 2 concurrent":        {"type":"maxconc","k":2},
 "one per direction":       {"type":"onedir"},
 "cooldown 3 min":          {"type":"cooldown","sec":180},
 "cooldown 5 min":          {"type":"cooldown","sec":300},
}
# precompute per-day signals + ticks once
work=[]
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    sg=day_signals(db)+nsnd_by.get(day,[])
    if sg: work.append((day,sg,load_ticks(td[day])))

print("Anti-cluster guard — portfolio (S1+S3+NSND @ M1), 0.01 lots, net of cost\n")
print(f"  {'guard':<22} {'trades':>6} {'TOTAL':>9} {'maxDD':>8} {'worstDay':>9}")
for name,g in GUARDS.items():
    allc=[]  # (time,pnl)
    perday={}
    for day,sg,ticks in work:
        c=replay_day(sg,ticks,g)
        allc+=c; perday[day]=sum(p for _,p in c)
    allc.sort(key=lambda x:x[0])
    eq=0; peak=0; mdd=0
    for _,p in allc:
        eq+=p; peak=max(peak,eq); mdd=max(mdd,peak-eq)
    total=sum(p for _,p in allc); worst=min(perday.values()) if perday else 0
    print(f"  {name:<22} {len(allc):>6} {total:>+9.0f} {mdd:>8.0f} {worst:>+9.0f}")
