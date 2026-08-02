"""s3_be_test.py — validate a $-based breakeven for S3@M1 ("secure then run":
once a trade reaches +$X, move SL to entry so a green trade can't flip to a full
loss; keep the peak-TP so winners still run). Tests vs baseline on native ticks,
total + maxDD + multi-split. This is the give-back killer for S3 (3 of today's 5).
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
from backtest_s1_uhv_breakout import load_ticks, COMMON
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
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}

def sigs_for(db):
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
    out=[]; fired=set()
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired:
                fired.add(r["ref_t"]); out.append({"side":r["side"],"sl":r["sl"],"tp":r["tp"],"fire_time":r["bo_t"]+timedelta(minutes=1)})
    return out

def sim(sig, ticks, be_arm):
    side,sl,tp=sig["side"],sig["sl"],sig["tp"]; e=None; peak=0; cur_sl=sl
    for tk in ticks:
        if tk["t"]<sig["fire_time"]: continue
        bid,ask=tk["bid"],tk["ask"]
        if e is None: e=ask if side==+1 else bid; cur_sl=sl; continue
        px=bid if side==+1 else ask
        pnl=((px-e) if side==+1 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if be_arm>0 and peak>=be_arm:   # arm breakeven: SL -> entry + tiny buffer
            be = e + (0.05 if side==+1 else -0.05)
            cur_sl = max(cur_sl,be) if side==+1 else min(cur_sl,be)
        if side==+1:
            if bid<=cur_sl: return (cur_sl-e)*PPP-COST
            if bid>=tp: return (tp-e)*PPP-COST
        else:
            if ask>=cur_sl: return (e-cur_sl)*PPP-COST
            if ask<=tp: return (e-tp)*PPP-COST
    if e is None: return None
    last=ticks[-1]; px=last["bid"] if side==+1 else last["ask"]
    return (((px-e) if side==+1 else (e-px))*PPP)-COST

work=[]
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    s=sigs_for(db)
    if s: work.append((day,s,load_ticks(td[day])))

print("S3@M1 — $-based breakeven (secure-then-run) vs baseline, net of cost\n")
print(f"  {'policy':<22} {'TOTAL':>8} {'maxDD':>7} {'worstDay':>9} {'splits':>7}")
for arm in [0,1.0,1.5,2.0,3.0]:
    allc=[]; perday={}
    for day,sg,ticks in work:
        for s in sg:
            r=sim(s,ticks,arm)
            if r is not None: allc.append((s["fire_time"],r)); perday[day]=perday.get(day,0)+r
    allc.sort(key=lambda x:x[0]); eq=0;peak=0;mdd=0
    for _,p in allc: eq+=p;peak=max(peak,eq);mdd=max(mdd,peak-eq)
    dl=sorted(perday); ok=sum(1 for f in [0.4,0.5,0.6,0.7,0.8] if dl and sum(v for d,v in perday.items() if d>=dl[int(len(dl)*f)])>0)
    lbl="baseline (no BE)" if arm==0 else f"BE after +${arm}"
    print(f"  {lbl:<22} {sum(p for _,p in allc):>+8.0f} {mdd:>7.0f} {min(perday.values()):>+9.0f} {ok:>5}/5")
