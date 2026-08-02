"""mfe_curves.py — per-EA "how far do trades run" probability curves for the
dashboard gauge. For each engine, replay its signals on real ticks recording each
trade's PEAK profit ($, MFE), then for target percentages report the $ level that
that % of trades reached. Writes monitor/mfe_curves.json.

  e.g. {"S1":[{"pct":90,"usd":0.2},{"pct":50,"usd":1.4},{"pct":10,"usd":7.1}], ...}
  pct = % of trades that reached at least usd profit (so 90% = easy/near, 10% = far).
"""
import csv, sys, glob, json
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
CONTRACT=100.0; LOTS=0.01; PPP=LOTS*CONTRACT
OUT=Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\mfe_curves.json")
PCTS=[90,80,70,60,50,40,30,20,10,5]

def load_native(fn="latest_for_claude.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),
                       "close":float(r["close"]),"vol":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["time"]); return b

def peak(sig, ticks):
    side, sl = sig["side"], sig["sl"]; e=None; pk=0.0
    for tk in ticks:
        if tk["t"] < sig["fire_time"]: continue
        bid, ask = tk["bid"], tk["ask"]
        if e is None: e=ask if side==+1 else bid; continue
        px=bid if side==+1 else ask
        pnl=((px-e) if side==+1 else (e-px))*PPP
        if pnl>pk: pk=pnl
        if (side==+1 and bid<=sl) or (side==-1 and ask>=sl): break
    return None if e is None else pk

bars=load_native(); days=group_bars_by_day(bars)
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}
h1=aggregate_to_tf(bars,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]

def s1_sigs(db):
    s=s1_mirror(db,hb,he,sl_buf=2.0,tp_points=7.5,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True)
    for x in s: x["fire_time"]=x["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)
    return s
def s3_sigs(db):
    out=[]; fired=set()
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired:
                out.append({"side":r["side"],"sl":r["sl"],"fire_time":r["bo_t"]+timedelta(minutes=1)}); fired.add(r["ref_t"])
    return out
ENG={"S1":s1_sigs,"S3":s3_sigs}
peaks={k:[] for k in ENG}; peaks["NSND"]=[]
# NSND: compute signals ONCE on full history, then group by fire day (was O(days^2))
m15=aggregate_to_tf(bars,15)
nsnd_all={}
for s in nsnd_signals(bars,[(m15,15)]):
    nsnd_all.setdefault(s["fire_time"].strftime("%Y-%m-%d"),[]).append({"side":s["side"],"sl":s["sl"],"fire_time":s["fire_time"]})
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    ticks=load_ticks(td[day])
    for k,fn in ENG.items():
        for s in fn(db):
            p=peak(s,ticks)
            if p is not None: peaks[k].append(p)
    for s in nsnd_all.get(day,[]):
        p=peak(s,ticks)
        if p is not None: peaks["NSND"].append(p)

curves={}
for k,ps in peaks.items():
    if len(ps)<20: print(f"{k}: only {len(ps)} trades — skip"); continue
    ps_sorted=sorted(ps)
    lv=[]
    for pc in PCTS:
        # $ level reached by pc% of trades = (100-pc) percentile of the peak distribution
        idx=int((100-pc)/100*len(ps_sorted)); idx=min(max(idx,0),len(ps_sorted)-1)
        usd=round(ps_sorted[idx],2)
        lv.append({"pct":pc,"usd":max(0.0,usd)})
    curves[k]=lv
    print(f"{k}: n={len(ps)}  " + " ".join(f"{x['pct']}%=${x['usd']}" for x in lv))
OUT.write_text(json.dumps(curves,indent=1))
print("\nwrote",OUT)
