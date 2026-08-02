"""s3s4_tf.py — which timeframe suits S3 and S4? Same detectors at M1 vs M5 on
native bars, tick-replay, multi-split + $0.40/trade cost. Honest caveats noted.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats, detect_s3_teacher
from backtest_s1_uhv_breakout import replay_ticks_both, load_ticks, COMMON
from s4_backtest import detect_s4, replay as s4replay
CONTRACT=100.0; COST=0.40

def load_native(fn="latest_for_claude.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),
                       "close":float(r["close"]),"vol":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["time"]); return b

bars=load_native(); days=group_bars_by_day(bars)
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}

def report(label, perday, ntr):
    if not ntr: print(f"  {label:<14} no trades"); return
    dl=sorted(perday);
    def oos(f): cut=dl[int(len(dl)*f)]; return sum(v for d,v in perday.items() if d>=cut)
    tot=sum(perday.values()); splits=[0.4,0.5,0.6,0.7,0.8]; ok=sum(1 for f in splits if oos(f)>0)
    print(f"  {label:<14} n={ntr:>3}  NET=${tot:>+7.0f}  OOS@50%=${oos(0.5):>+6.0f}  splits {ok}/5 OOS+  {'OK' if ok>=4 and tot>0 else 'weak'}")

def run_s3(tf_min):
    perday={}; ntr=0
    for day in sorted(days):
        if day not in td: continue
        db=days[day]; bb=aggregate_to_tf(db,tf_min) if tf_min>1 else db
        if len(bb)<35: continue
        sigs=[]; fired=set()
        for i in range(35,len(bb)):
            s=detect_s3_teacher(bb,i,[],5.0,2.0,24,require_h1_fvg=False)
            if s and s["ref_red_t"] not in fired:
                sigs.append({"side":+1,"sl":s["sl"],"tp":s["tp"],"fire_time":s["wicking_t"]+timedelta(minutes=tf_min)}); fired.add(s["ref_red_t"])
        if not sigs: continue
        for t in replay_ticks_both(load_ticks(td[day]),sigs,0.01,CONTRACT):
            perday[day]=perday.get(day,0)+t["pnl"]-COST; ntr+=1
    return perday,ntr

def run_s4(tf_min):
    perday={}; ntr=0
    for day in sorted(days):
        if day not in td: continue
        db=days[day]; bb=aggregate_to_tf(db,tf_min) if tf_min>1 else db
        if len(bb)<35: continue
        # live S4 exit: TP $2 / SL $7.5 (price pts @0.01); ER off
        sigs=detect_s4(bb,day,tp_pts=2.0,sl_pts=7.5,er_min=0.0)
        for s in sigs: s["fire"]=s["fire"]-timedelta(minutes=1)+timedelta(minutes=tf_min)
        if not sigs: continue
        for t in s4replay(load_ticks(td[day]),sigs,0.01):
            perday[day]=perday.get(day,0)+t["pnl"]-COST; ntr+=1
    return perday,ntr

print("Which timeframe suits? native bars, 0.01 lots, net of $0.40/trade\n")
print("S3 (Liquidity Sweep — buy-only detector; omits live sells + 60-bar filter):")
report("S3 @ M5", *run_s3(5)); report("S3 @ M1", *run_s3(1))
print("\nS4 (Feb-11 UHV — live exit TP$2/SL$7.5):")
report("S4 @ M5", *run_s4(5)); report("S4 @ M1", *run_s4(1))
