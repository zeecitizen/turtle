"""cut_sweep.py — Zee's hypothesis: "a failed breakout fails — it doesn't come back."
So is there a time T where "still red / still flat at T seconds" reliably means dead?

On clean S3 ticks (entries within tick coverage AND with sane SL/entry/TP ordering,
which removes the bar/tick alignment garbage), sweep cut-times and report:
  - TOTAL / WR for "cut if red at T s"  and  "cut if not yet green (+$0.1) at T s"
  - the RECOVERY RATE of trades red at T s (if this stays high, his hypothesis is
    false for this data; if it drops sharply at some T, that T is exploitable).
All exits otherwise use the live trail (act0.3/give0.3) + SL/TP.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import group_bars_by_day
from backtest_s1_uhv_breakout import load_ticks, COMMON
import s3_full_m1 as S3
PPP=1.0; COST=0.40

def load_native(fn="latest_for_claude.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),"open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),"close":float(r["close"]),"vol":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["time"]); return b
bars=load_native(); days=group_bars_by_day(bars)
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}
def sigs_for(db):
    bb=[{"t":x["time"],"o":x["open"],"h":x["high"],"l":x["low"],"c":x["close"],"v":x["vol"]} for x in db]
    out=[];fired=set()
    for i in range(len(bb)):
        for buy in (True,False):
            r=S3.detect(bb,i,buy)
            if r and r["ref_t"] not in fired: fired.add(r["ref_t"]); out.append({"side":r["side"],"sl":r["sl"],"tp":r["tp"],"fire_time":r["bo_t"]+timedelta(minutes=1)})
    return out

def sim(sig, ticks, cut_secs, mode="red"):
    """mode 'red': cut if floating<0 at cut_secs. 'flat': cut if peak<+0.1 at cut_secs.
    returns (pnl, state_at_cut) where state_at_cut True means the cut condition was met."""
    side,sl,tp=sig["side"],sig["sl"],sig["tp"]; e=None;peak=0.0;entry_t=None;armed=(cut_secs>0);hit=None
    for tk in ticks:
        if tk["t"]<sig["fire_time"]: continue
        bid,ask=tk["bid"],tk["ask"]
        if e is None: e=ask if side==+1 else bid; entry_t=tk["t"]; continue
        px=bid if side==+1 else ask
        pnl=((px-e) if side==+1 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if armed and (tk["t"]-entry_t).total_seconds()>=cut_secs:
            armed=False
            cond = (pnl<0) if mode=="red" else (peak<0.1)
            hit=cond
            if cond: return pnl-COST, hit
        if peak>=0.3:
            floor=max(0.0,peak-0.3)
            if pnl<=floor: return floor-COST, hit
        if side==+1:
            if bid<=sl: return (sl-e)*PPP-COST, hit
            if bid>=tp: return (tp-e)*PPP-COST, hit
        else:
            if ask>=sl: return (e-sl)*PPP-COST, hit
            if ask<=tp: return (e-tp)*PPP-COST, hit
    if e is None: return None, None
    last=ticks[-1];px=last["bid"] if side==+1 else last["ask"]
    return (((px-e) if side==+1 else (e-px))*PPP)-COST, hit

# build clean + sane work set
work=[]; nsane=0; nraw=0
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    ticks=load_ticks(td[day])
    if not ticks: continue
    ft0=ticks[0]["t"]
    sel=[]
    for s in sigs_for(db):
        if s["fire_time"]<ft0: continue
        nraw+=1
        # sane ordering check vs the actual entry tick price
        etk=next((t for t in ticks if t["t"]>=s["fire_time"]), None)
        if not etk: continue
        e=etk["ask"] if s["side"]==1 else etk["bid"]
        sane = (s["sl"]<e<s["tp"]) if s["side"]==1 else (s["sl"]>e>s["tp"])
        if sane: sel.append(s); nsane+=1
    if sel: work.append((sel,ticks))
print(f"S3 clean+sane trades: {nsane} (of {nraw} clean; dropped {nraw-nsane} alignment-garbled)\n")

def run(cut, mode="red"):
    pnls=[]
    for sg,ticks in work:
        for s in sg:
            r,_=sim(s,ticks,cut,mode)
            if r is not None: pnls.append(r)
    w=[p for p in pnls if p>0]
    return sum(pnls), (100*len(w)/len(pnls) if pnls else 0), len(pnls)

print(f"  {'policy':<26}{'TOTAL':>7}{'WR%':>5}{'n':>5}")
b=run(0); print(f"  {'trail only (live)':<26}{b[0]:>+7.0f}{b[1]:>5.0f}{b[2]:>5}")
for cs in [10,20,30,45,60,90,120,180,300]:
    r=run(cs,"red"); print(f"  {'cut RED @'+str(cs)+'s':<26}{r[0]:>+7.0f}{r[1]:>5.0f}{r[2]:>5}")
print()
for cs in [30,60,120,180,300]:
    r=run(cs,"flat"); print(f"  {'cut if not green @'+str(cs)+'s':<26}{r[0]:>+7.0f}{r[1]:>5.0f}{r[2]:>5}")

# recovery-rate-by-time: of trades red at T s, how many still win (trail-only outcome)?
print("\nRECOVERY RATE of trades RED at T seconds (trail-only outcome):")
print(f"  {'T':>5}{'red#':>7}{'recovered':>11}{'rate':>7}")
for cs in [10,20,30,45,60,90,120,180,300]:
    red=0;rec=0
    for sg,ticks in work:
        for s in sg:
            full,_=sim(s,ticks,0)
            _,hit=sim(s,ticks,cs,"red")
            if full is None or hit is None: continue
            if hit:
                red+=1
                if full>0: rec+=1
    print(f"  {cs:>4}s{red:>7}{rec:>11}{(100*rec/max(1,red)):>6.0f}%")
