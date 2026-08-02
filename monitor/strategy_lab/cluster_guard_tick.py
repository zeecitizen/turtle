"""cluster_guard_tick.py — validate the anti-cluster guard + overnight-session filter
on real ticks, the clean way: bars are built FROM each day's ticks, the real engines
(S1/S3/NSND) generate signals on those bars, and the whole portfolio is replayed
tick-by-tick (trail 0.3/0.3 + SL/TP) — one timeline, no alignment bug.

Today's live pain was CLUSTERING: 2 S3 buys 39s apart (-$18.7) and a 14:33 triple
pile-up S1+S1+S3 all long, all stopped (-$37). Test guards that cap correlated
concurrency. Adopt one only if it cuts drawdown without gutting total.

Caveat: tick-derived volume = tick-count/min (differs from broker tick_volume), so the
SET of S3/NSND signals isn't identical to live — but the guard's RELATIVE effect (same
signals, guard on vs off) is the trustworthy comparison, which is what we're measuring.
$ = price points @0.01 lot.
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
PPP=1.0; COST=0.20; TACT=0.3; TGIVE=0.3

def m1_from_ticks(ticks):
    bars=[]; cur=None; cnt=0
    for tk in ticks:
        m=tk["t"].replace(second=0, microsecond=0)
        mid=(tk["bid"]+tk["ask"])/2
        if cur is None or m!=cur["time"]:
            if cur: cur["vol"]=cnt; bars.append(cur)
            cur={"time":m,"open":mid,"high":mid,"low":mid,"close":mid,"vol":0}; cnt=1
        else:
            cur["high"]=max(cur["high"],mid); cur["low"]=min(cur["low"],mid); cur["close"]=mid; cnt+=1
    if cur: cur["vol"]=cnt; bars.append(cur)
    return bars

def day_signals(bars):
    sg=[]
    if len(bars)<70: return sg
    h1=aggregate_to_tf(bars,60); fv=find_h1_fvgs(h1)
    hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]
    m15=aggregate_to_tf(bars,15)
    for s in s1_mirror(bars,hb,he,sl_buf=2.0,tp_points=2.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True):
        sg.append({"ea":"S1","side":s["side"],"sl":s["sl"],"tp":s["tp"],"ft":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in bars]
    fired=set()
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired:
                fired.add(r["ref_t"]); sg.append({"ea":"S3","side":r["side"],"sl":r["sl"],"tp":r["tp"],"ft":r["bo_t"]+timedelta(minutes=1)})
    for s in nsnd_signals(bars,[(m15,15)]):
        sg.append({"ea":"NSND","side":s["side"],"sl":s["sl"],"tp":s["tp"],"ft":s["fire_time"]})
    sg.sort(key=lambda x:x["ft"]); return sg

GUARDS={
 "baseline (no guard)":      lambda u,s,last: True,
 "max 1 same-direction":     lambda u,s,last: not any(x["side"]==s["side"] for x in u),
 "max 2 concurrent":         lambda u,s,last: len(u)<2,
 "cooldown 5m same-dir":     lambda u,s,last: (s["side"] not in last) or (s["ft"]-last[s["side"]]).total_seconds()>=300,
 "skip 00:00-06:00":         lambda u,s,last: not (0<=s["ft"].hour<6),
 "max1dir + skip 00-06":     lambda u,s,last: (not any(x["side"]==s["side"] for x in u)) and not (0<=s["ft"].hour<6),
}

def replay(sigs, ticks, guard):
    units=[]; closed=[]; si=0; last={}
    for tk in ticks:
        t,bid,ask=tk["t"],tk["bid"],tk["ask"]
        for u in units[:]:
            px=bid if u["side"]==1 else ask
            pnl=((px-u["e"]) if u["side"]==1 else (u["e"]-px))*PPP
            if pnl>u["pk"]: u["pk"]=pnl
            done=None
            if u["pk"]>=TACT and pnl<=max(0.0,u["pk"]-TGIVE): done=pnl-COST
            elif u["side"]==1:
                if bid<=u["sl"]: done=(u["sl"]-u["e"])-COST
                elif bid>=u["tp"]: done=(u["tp"]-u["e"])-COST
            else:
                if ask>=u["sl"]: done=(u["e"]-u["sl"])-COST
                elif ask<=u["tp"]: done=(u["e"]-u["tp"])-COST
            if done is not None: closed.append((t,done)); units.remove(u)
        while si<len(sigs) and sigs[si]["ft"]<=t:
            s=sigs[si]; si+=1
            if guard(units,s,last):
                e=ask if s["side"]==1 else bid
                units.append({"side":s["side"],"e":e,"sl":s["sl"],"tp":s["tp"],"pk":0.0})
                last[s["side"]]=s["ft"]
    if ticks:
        last_tk=ticks[-1]
        for u in units:
            px=last_tk["bid"] if u["side"]==1 else last_tk["ask"]
            closed.append((last_tk["t"],(((px-u["e"]) if u["side"]==1 else (u["e"]-px))*PPP)-COST))
    return closed

td=sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv")))
work=[]
for path in td:
    ticks=load_ticks(Path(path))
    if len(ticks)<5000: continue
    bars=m1_from_ticks(ticks)
    sg=day_signals(bars)
    if sg: work.append((Path(path).stem.split("_")[-1],sg,ticks))
print(f"days={len(work)}  total signals={sum(len(s) for _,s,_ in work)}\n")
print(f"  {'guard':<24}{'trades':>7}{'TOTAL':>8}{'maxDD':>7}{'worstDay':>9}")
for name,g in GUARDS.items():
    allc=[]; perday={}
    for day,sg,ticks in work:
        c=replay(sg,ticks,g); allc+=c; perday[day]=sum(p for _,p in c)
    allc.sort(key=lambda x:x[0]); eq=0;pk=0;mdd=0
    for _,p in allc: eq+=p;pk=max(pk,eq);mdd=max(mdd,pk-eq)
    wd=min(perday.values()) if perday else 0
    print(f"  {name:<24}{len(allc):>7}{sum(p for _,p in allc):>+8.0f}{mdd:>7.0f}{wd:>+9.0f}")
