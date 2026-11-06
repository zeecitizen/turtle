"""trail_test.py — Zee's peak-trailing profit-lock idea vs fixed BE@$1 vs baseline.

Idea: once a trade is green, ratchet a floor under the floating profit. The instant
profit reverses to (peak - giveback), exit immediately (still in profit / at scratch).
This catches trades that peak BELOW the +$1 breakeven trigger (e.g. +$0.70 then reverse).

The whole question is the GIVE-BACK distance vs gold's spread (~$0.2-0.4): too tight
and noise shakes you out of winners before they reach TP; too loose and you give back
too much. We sweep (activation, giveback) and judge on TOTAL + WR + maxDD + worst-day
+ multi-split, on native signals replayed over real ticks, net of $0.40/trade cost.

Floor is clamped at 0 (breakeven) so the trail never exits at a loss — the original
SL still handles losers. The fixed TP is kept (a runner can still reach it).
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
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

def sim(sig, ticks, mode, p1=0.0, p2=0.0):
    """mode: 'base' (SL/TP only), 'be' (fixed breakeven, p1=arm),
             'trail' (p1=activation, p2=giveback, floor clamped >=0)."""
    side,sl,tp=sig["side"],sig["sl"],sig["tp"]; e=None; peak=0.0; cur_sl=sl
    for tk in ticks:
        if tk["t"]<sig["fire_time"]: continue
        bid,ask=tk["bid"],tk["ask"]
        if e is None: e=ask if side==+1 else bid; cur_sl=sl; continue
        px=bid if side==+1 else ask
        pnl=((px-e) if side==+1 else (e-px))*PPP
        if pnl>peak: peak=pnl
        # ---- profit-lock exits (return at the LOCK level, realistic) ----
        if mode=="be" and peak>=p1:
            be=e+(0.05 if side==+1 else -0.05)
            cur_sl=max(cur_sl,be) if side==+1 else min(cur_sl,be)
        elif mode=="trail" and peak>=p1:
            floor=max(0.0, peak-p2)               # $ floor under peak, never a loss
            if pnl<=floor: return floor-COST       # reversed to the floor -> bail in profit
        # ---- hard SL / TP ----
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

def run(mode,p1=0.0,p2=0.0):
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

print("S3@M1 — Zee's peak-trail profit-lock vs fixed BE vs baseline (real ticks, net cost)\n")
print(f"  {'policy':<28} {'TOTAL':>7} {'WR%':>5} {'maxDD':>6} {'worst':>6} {'n':>4} {'split':>6}")
def line(lbl,res): print(f"  {lbl:<28} {res[0]:>+7.0f} {res[1]:>5.0f} {res[2]:>6.0f} {res[3]:>+6.0f} {res[4]:>4} {res[5]:>4}/5")
line("baseline (SL/TP)", run("base"))
line("fixed BE @ +$1.0 (current)", run("be",1.0))
print()
for act in [0.3,0.5,0.7,1.0]:
    for gb in [0.2,0.3,0.5]:
        line(f"trail act+${act} giveback ${gb}", run("trail",act,gb))
