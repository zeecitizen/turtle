"""s3_full_m1.py — FULL live S3 logic (buy+sell, Trend60 filter, upper-wick filter,
peak-TP, SL=5) mirrored from S3Trader.mq5, tested M1 vs M5 on native bars,
tick-replay, multi-split + cost. This is the faithful validation (vs the earlier
buy-only stand-in) before deciding S3's timeframe.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import replay_ticks_both, load_ticks, COMMON
CONTRACT=100.0; COST=0.40
TREND_LB=24; TREND_TH=1.0; T60=5.0; RETRACE_LB=30; PEAK_LB=10; SLBUF=5.0; WICKMAX=0.35; MINTP=0.2

def load_native(fn="latest_for_claude.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"t":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
                       "c":float(r["close"]),"v":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["t"]); return b

grn=lambda x:x["c"]>x["o"]; red=lambda x:x["c"]<x["o"]

def detect(m, idx, buy):
    if idx < max(TREND_LB,60,RETRACE_LB,PEAK_LB)+2: return None
    bo=m[idx]
    if buy and not grn(bo): return None
    if (not buy) and not red(bo): return None
    # base trend + 60-bar trend
    if buy:
        if not (m[idx]["c"]-m[idx-TREND_LB]["c"] > TREND_TH): return None
        if not (m[idx]["c"]-m[idx-60]["c"] >= T60): return None
    else:
        if not (m[idx-TREND_LB]["c"]-m[idx]["c"] > TREND_TH): return None
        if not (m[idx-60]["c"]-m[idx]["c"] >= T60): return None
    # retracement: nearest candidate (green for buy / red for sell) whose extreme was
    # broken by subsequent opposite-color bars; collect those bars
    opp = red if buy else grn          # retracement bars are opposite color to candidate
    cand_ok = grn if buy else red
    refs=[]
    for g in range(idx-1, idx-2-RETRACE_LB, -1):
        if g<1: break
        if not cand_ok(m[g]): continue
        ext = m[g]["l"] if buy else m[g]["h"]
        broke=False; got=[]
        for j in range(g+1, idx):
            if opp(m[j]):
                if (buy and (m[j]["c"]<ext or m[j]["l"]<ext)) or ((not buy) and (m[j]["c"]>ext or m[j]["h"]>ext)): broke=True
                got.append(j)
        if broke and got: refs=got; break
    if not refs: return None
    # matching ref bar: bo wicks beyond ref extreme, closes back inside, higher vol
    mref=None
    for j in refs:
        r=m[j]
        if buy:
            if bo["l"]>=r["l"] or bo["c"]<=r["l"] or bo["v"]<=r["v"]: continue
        else:
            if bo["h"]<=r["h"] or bo["c"]>=r["h"] or bo["v"]<=r["v"]: continue
        mref=r; break
    if mref is None: return None
    # upper/lower-wick rejection filter (<=0.35)
    rng=bo["h"]-bo["l"]
    if rng>0:
        wick=(bo["h"]-max(bo["o"],bo["c"])) if buy else (min(bo["o"],bo["c"])-bo["l"])
        if wick/rng > WICKMAX: return None
    entry=bo["c"]
    if buy:
        sl=bo["l"]-SLBUF; tp=max(m[j]["h"] for j in range(idx-PEAK_LB,idx))
        if tp<=entry+MINTP: return None
    else:
        sl=bo["h"]+SLBUF; tp=min(m[j]["l"] for j in range(idx-PEAK_LB,idx))
        if tp>=entry-MINTP: return None
    return {"side":+1 if buy else -1,"sl":sl,"tp":tp,"ref_t":mref["t"],"bo_t":bo["t"]}

def run(tf_min):
    bars=load_native(); days=group_bars_by_day([{**{"time":x["t"]},**x} for x in bars]) if False else None
    # group by day on raw native, aggregate per day
    perday={}; ntr=0
    by={}
    for x in bars: by.setdefault(x["t"].strftime("%Y-%m-%d"),[]).append(x)
    td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}
    for day in sorted(by):
        if day not in td: continue
        db=by[day]
        if tf_min>1:
            agg=aggregate_to_tf([{"time":x["t"],"open":x["o"],"high":x["h"],"low":x["l"],"close":x["c"],"vol":x["v"]} for x in db], tf_min)
            bb=[{"t":a["time"],"o":a["open"],"h":a["high"],"l":a["low"],"c":a["close"],"v":a["vol"]} for a in agg]
        else: bb=db
        fired=set(); sigs=[]
        for i in range(len(bb)):
            for buy in (True,False):
                s=detect(bb,i,buy)
                if s and s["ref_t"] not in fired:
                    sigs.append({"side":s["side"],"sl":s["sl"],"tp":s["tp"],"fire_time":s["bo_t"]+timedelta(minutes=tf_min)}); fired.add(s["ref_t"])
        if not sigs: continue
        for t in replay_ticks_both(load_ticks(td[day]),sigs,0.01,CONTRACT):
            perday[day]=perday.get(day,0)+t["pnl"]-COST; ntr+=1
    return perday,ntr

def report(label,perday,ntr):
    if not ntr: print(f"  {label:<10} no trades"); return
    dl=sorted(perday)
    def oos(f): cut=dl[int(len(dl)*f)]; return sum(v for d,v in perday.items() if d>=cut)
    tot=sum(perday.values()); ok=sum(1 for f in [0.4,0.5,0.6,0.7,0.8] if oos(f)>0)
    print(f"  {label:<10} n={ntr:>3}  NET=${tot:>+7.0f}  OOS@50%=${oos(0.5):>+6.0f}  splits {ok}/5 OOS+  {'OK' if ok>=4 and tot>0 else 'weak'}")

if __name__ == "__main__":   # guard so `import s3_full_m1` only exposes detect(), no backtest run
    print("FULL S3 (buy+sell, Trend60, upper-wick) — native, 0.01 lots, net of cost\n")
    report("S3 @ M5", *run(5)); report("S3 @ M1", *run(1))
