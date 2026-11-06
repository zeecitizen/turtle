"""halt_test.py — does the daily-loss halt help or HURT? On a +EV system, stopping
after a bad run forfeits the recovery. Replay the portfolio (S1+S3+NSND @ M1) with
different daily-halt levels: once a day's REALIZED P&L <= -X, stop NEW entries for
that day (open trades run on). Compare total / worst-day / maxDD / days-halted.
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
    nsnd_by.setdefault(s["fire_time"].strftime("%Y-%m-%d"),[]).append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]})

def day_signals(db):
    sg=[]
    for s in s1_mirror(db,hb,he,sl_buf=2.0,tp_points=3.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True):
        sg.append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
    fired=set()
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired:
                fired.add(r["ref_t"]); sg.append({"side":r["side"],"sl":r["sl"],"tp":r["tp"],"fire_time":r["bo_t"]+timedelta(minutes=1)})
    return sg

work=[]
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    sg=day_signals(db)+nsnd_by.get(day,[])
    if sg: work.append((day,sorted(sg,key=lambda x:x["fire_time"]),load_ticks(td[day])))

def replay_day(sigs, ticks, haltX):
    units=[]; closed=[]; si=0; day_real=0.0
    for tk in ticks:
        t,bid,ask=tk["t"],tk["bid"],tk["ask"]
        for u in units[:]:
            hit=None
            if u["side"]==+1:
                if bid<=u["sl"]: hit=(u["sl"]-u["e"])*PPP
                elif bid>=u["tp"]: hit=(u["tp"]-u["e"])*PPP
            else:
                if ask>=u["sl"]: hit=(u["e"]-u["sl"])*PPP
                elif ask<=u["tp"]: hit=(u["e"]-u["tp"])*PPP
            if hit is not None: day_real+=hit-COST; closed.append((t,hit-COST)); units.remove(u)
        halted = haltX>0 and day_real <= -haltX
        while si<len(sigs) and sigs[si]["fire_time"]<=t:
            s=sigs[si]; si+=1
            if not halted:
                e=ask if s["side"]==+1 else bid
                units.append({"side":s["side"],"e":e,"sl":s["sl"],"tp":s["tp"]})
    if ticks:
        last=ticks[-1]
        for u in units:
            px=last["bid"] if u["side"]==+1 else last["ask"]
            closed.append((last["t"],(((px-u["e"]) if u["side"]==+1 else (u["e"]-px))*PPP)-COST))
    return closed

print("Daily-loss halt — portfolio (S1+S3+NSND @ M1), 0.01 lots, net of cost\n")
print(f"  {'halt':<14} {'TOTAL':>9} {'maxDD':>8} {'worstDay':>9} {'days halted':>12}")
for X in [0,60,40,25,15]:
    allc=[]; perday={}; halted_days=0
    for day,sg,ticks in work:
        c=replay_day(sg,ticks,X)
        allc+=c; dp=sum(p for _,p in c); perday[day]=dp
        if X>0 and dp<=-X: halted_days+=1
    allc.sort(key=lambda x:x[0]); eq=0;peak=0;mdd=0
    for _,p in allc: eq+=p;peak=max(peak,eq);mdd=max(mdd,peak-eq)
    lbl="OFF (no halt)" if X==0 else f"-${X}"
    print(f"  {lbl:<14} {sum(p for _,p in allc):>+9.0f} {mdd:>8.0f} {min(perday.values()):>+9.0f} {halted_days:>12}")
