"""regime_filter_m1.py — does a chop filter (Kaufman Efficiency Ratio) help the
M1 engines avoid ranging-market losses? Re-test on NATIVE M1 (the old reject was
M5+rev-eng volume). ER = |net move| / |path| over N bars: ~1 trending, ~0 chop.
Only take signals where ER >= threshold. Proper replay, multi-split, net of cost.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, replay_ticks_both, load_ticks, COMMON
import s3_full_m1 as S3
CONTRACT=100.0; COST=0.40; ERN=20

def load_native(fn="latest_for_claude.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),
                       "close":float(r["close"]),"vol":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["time"]); return b

def ER(bars, idx, n=ERN):
    if idx<n: return 0.0
    net=abs(bars[idx]["close"]-bars[idx-n]["close"])
    path=sum(abs(bars[j]["close"]-bars[j-1]["close"]) for j in range(idx-n+1,idx+1))
    return net/path if path>0 else 0.0

bars=load_native(); days=group_bars_by_day(bars)
h1=aggregate_to_tf(bars,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}
THRS=[0.0,0.10,0.15,0.20,0.25,0.30]

def collect(engine):
    """return list of (day, sig, er)"""
    out=[]
    for day in sorted(days):
        if day not in td: continue
        db=days[day]
        if len(db)<35: continue
        idxof={b["time"]:i for i,b in enumerate(db)}
        if engine=="S1":
            sigs=s1_mirror(db,hb,he,sl_buf=2.0,tp_points=3.0,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True)
            for s in sigs:
                bo_t=s["fire_time"]-timedelta(minutes=5); s["fire_time"]=bo_t+timedelta(minutes=1)
                i=idxof.get(bo_t); out.append((day,s,ER(db,i) if i is not None else 0.0))
        else:  # S3 full logic
            bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
            fired=set()
            for i in range(len(bb)):
                for buy in (True,False):
                    r=S3.detect(bb,i,buy)
                    if r and r["ref_t"] not in fired:
                        fired.add(r["ref_t"])
                        out.append((day,{"side":r["side"],"sl":r["sl"],"tp":r.get("tp"),"fire_time":r["bo_t"]+timedelta(minutes=1)}, ER(db,i)))
    return out

def evaluate(engine):
    sigs=collect(engine)
    tickcache={}
    print(f"\n{engine}@M1 — {len(sigs)} signals, ER(20) chop filter:")
    for thr in THRS:
        perday={}
        byday={}
        for day,s,er in sigs:
            if er<thr: continue
            byday.setdefault(day,[]).append(s)
        kept=sum(len(v) for v in byday.values())
        for day,ds in byday.items():
            if day not in tickcache: tickcache[day]=load_ticks(td[day])
            for t in replay_ticks_both(tickcache[day],ds,0.01,CONTRACT):
                perday[day]=perday.get(day,0)+t["pnl"]-COST
        total=sum(perday.values()); dl=sorted(perday)
        ok=sum(1 for f in [0.4,0.5,0.6,0.7,0.8] if dl and sum(v for d,v in perday.items() if d>=dl[int(len(dl)*f)])>0)
        tag="(baseline)" if thr==0 else ""
        print(f"  ER>={thr:.2f}  kept={kept:>3}/{len(sigs)}  TOTAL=${total:>+7.0f}  {ok}/5 OOS+  {tag}")

evaluate("S1")
evaluate("S3")
