"""bar_revalidate.py — the trustworthy rebuild. Re-run the LIVE engines (S1, S3, NSND)
on a single consistent bar file (27thmayexport.csv) with BAR-based fills, so signals
and execution share one timeline — the tick/bar alignment bug that corrupted the old
backtests is impossible here.

Each engine's own detector produces side/SL/TP. Fill: enter at the open of the bar
after the signal; walk M1 bars; SL checked before TP within a bar (conservative).
This measures the raw ENTRY + structural SL/TP edge (the trail is a separate on-top
improver that needs ticks to model and can only help green trades).

Reports per engine: trades, WR, net total ($ = price pts @0.01 lot), EV/trade, and a
train/test split. Compare against the old (corrupted) tick numbers.
"""
import csv, sys
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, COMMON
from nsnd_fvg_tf_test import nsnd_signals
import s3_full_m1 as S3
PPP=1.0

def load(fn="27thmayexport.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),
                       "close":float(r["close"]),"vol":int(r["tick_volume"]),
                       "sp":float(r["spread"])*0.001})
        except: pass
    b.sort(key=lambda x:x["time"]); return b
BARS=load(); n=len(BARS)
TIDX={b["time"]:i for i,b in enumerate(BARS)}
times=[b["time"] for b in BARS]
import bisect
def bar_at_or_after(t):
    i=bisect.bisect_left(times,t)
    return i if i<n else None
print(f"loaded {n} M1 bars  {BARS[0]['time']} .. {BARS[-1]['time']}\n")

days=group_bars_by_day(BARS)
h1=aggregate_to_tf(BARS,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]
m15=aggregate_to_tf(BARS,15)

def s1_sigs():
    out=[]
    for day in sorted(days):
        db=days[day]
        if len(db)<35: continue
        for s in s1_mirror(db,hb,he,sl_buf=2.0,tp_points=2.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True):
            out.append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)})
    return out
def s3_sigs():
    out=[]
    for day in sorted(days):
        db=days[day]
        if len(db)<35: continue
        bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
        fired=set()
        for i in range(len(bb)):
            for buy in (True,False):
                r=S3.detect(bb,i,buy)
                if r and r["ref_t"] not in fired:
                    fired.add(r["ref_t"]); out.append({"side":r["side"],"sl":r["sl"],"tp":r["tp"],"fire_time":r["bo_t"]+timedelta(minutes=1)})
    return out
def nsnd_sigs():
    return [{"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["fire_time"]} for s in nsnd_signals(BARS,[(m15,15)])]

ORDER="sl"   # which to assume hits first when a bar spans BOTH: 'sl' (worst) or 'tp' (best)
def sim(sig):
    k=bar_at_or_after(sig["fire_time"])
    if k is None or k+1>=n: return None
    e=BARS[k+1]["open"]; side=sig["side"]; sl=sig["sl"]; tp=sig["tp"]
    cost=BARS[k]["sp"]+0.04
    for j in range(k+1, min(n, k+1+600)):
        hi,lo=BARS[j]["high"],BARS[j]["low"]
        hit_sl = (lo<=sl) if side==+1 else (hi>=sl)
        hit_tp = (hi>=tp) if side==+1 else (lo<=tp)
        if hit_sl and hit_tp:
            first = ORDER
        elif hit_sl: first="sl"
        elif hit_tp: first="tp"
        else: continue
        if first=="sl": return ((sl-e) if side==+1 else (e-sl))-cost
        else:           return ((tp-e) if side==+1 else (e-tp))-cost
    px=BARS[min(n-1,k+600)]["close"]
    return ((px-e) if side==+1 else (e-px))-cost

def report(name, sigs):
    res=[]
    for s in sigs:
        r=sim(s)
        if r is not None: res.append((s["fire_time"],r))
    if not res: print(f"  {name:<8} (no trades)"); return
    res.sort(key=lambda x:x[0])
    tot=sum(p for _,p in res); w=[p for _,p in res if p>0]; wr=100*len(w)/len(res)
    half=res[len(res)//2][0]
    t1=sum(p for t,p in res if t<half); t2=sum(p for t,p in res if t>=half)
    aw=sum(w)/len(w) if w else 0; lo=[p for _,p in res if p<=0]; al=sum(lo)/len(lo) if lo else 0
    print(f"  {name:<8}{tot:>+8.0f}{wr:>6.0f}{len(res):>6}{tot/len(res):>+8.2f}{aw:>+8.2f}{al:>+8.2f}{t1:>+8.0f}{t2:>+8.0f}")

S1S=s1_sigs(); S3S=s3_sigs(); NS=nsnd_sigs()
for order in ["sl","tp"]:
    globals()["ORDER"]=order
    lbl = "SL-first (worst case / conservative)" if order=="sl" else "TP-first (best case / optimistic)"
    print(f"\n=== Bar fills assuming {lbl} ===")
    print(f"  {'engine':<8}{'TOTAL':>8}{'WR%':>6}{'n':>6}{'EV':>8}{'avgW':>8}{'avgL':>8}{'1stH':>8}{'2ndH':>8}")
    report("S1", S1S); report("S3", S3S); report("NSND", NS)
