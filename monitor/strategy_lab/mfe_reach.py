"""mfe_reach.py — answer Zee's question: "if nearly all trades go positive and we
catch it, shouldn't win-rate be 90%+?"

Two things, on S3 real ticks:
1) PEAK-REACH distribution: what % of trades ever reach +$0.1/0.2/0.3/0.5/1.0 in profit.
   That % is the HARD CEILING on win-rate for a trailing lock armed at that level —
   a trade that never gets green by $X can't be saved; it takes the stop.
2) Trail at progressively LOWER activations (0.1..0.5): WR climbs toward the ceiling,
   but watch TOTAL $ — the high-WR / tiny-bank trap (spread eats the wins; the few
   never-green trades take full stops that outweigh many tiny wins).
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

def trade(sig, ticks, act, give):
    """returns (pnl, peak) — peak is max favorable $ ever seen (before any exit)."""
    side,sl,tp=sig["side"],sig["sl"],sig["tp"]; e=None; peak=0.0
    res=None
    for tk in ticks:
        if tk["t"]<sig["fire_time"]: continue
        bid,ask=tk["bid"],tk["ask"]
        if e is None: e=ask if side==+1 else bid; continue
        px=bid if side==+1 else ask
        pnl=((px-e) if side==+1 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if res is None and act>0 and peak>=act:
            floor=max(0.0,peak-give)
            if pnl<=floor: res=floor-COST
        if res is None:
            if side==+1:
                if bid<=sl: res=(sl-e)*PPP-COST
                elif bid>=tp: res=(tp-e)*PPP-COST
            else:
                if ask>=sl: res=(e-sl)*PPP-COST
                elif ask<=tp: res=(e-tp)*PPP-COST
        if res is not None: break
    if e is None: return None,None
    if res is None:
        last=ticks[-1]; px=last["bid"] if side==+1 else last["ask"]
        res=(((px-e) if side==+1 else (e-px))*PPP)-COST
    return res,peak

work=[]
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    s=sigs_for(db)
    if s: work.append((s,load_ticks(td[day])))

# 1) peak-reach distribution (use a huge activation so we just record peaks, baseline exits)
peaks=[]
for sg,ticks in work:
    for s in sg:
        _,pk=trade(s,ticks,0.0,99)   # act=0 -> no trail, records true peak under SL/TP
        if pk is not None: peaks.append(pk)
n=len(peaks)
print(f"S3 — {n} trades on real ticks\n")
print("PEAK-REACH (the win-rate CEILING for a trail armed at each level):")
for L in [0.1,0.2,0.3,0.5,1.0,2.0]:
    c=sum(1 for p in peaks if p>=L)
    print(f"   reached +${L:<4} : {c:>4}/{n}  = {100*c/n:5.1f}%")
print("\n(a trade that never gets green by +$X cannot be saved — it takes the stop)\n")

print("TRAIL at lower activations — WR rises toward the ceiling, but watch TOTAL $:")
print(f"  {'policy':<26} {'TOTAL':>7} {'WR%':>5} {'avgWin':>7} {'avgLoss':>8} {'n':>4}")
for act in [0.1,0.2,0.3,0.5]:
    give=act  # symmetric give-back at each activation
    pnls=[]
    for sg,ticks in work:
        for s in sg:
            r,_=trade(s,ticks,act,give)
            if r is not None: pnls.append(r)
    wins=[p for p in pnls if p>0]; losses=[p for p in pnls if p<=0]
    aw=sum(wins)/len(wins) if wins else 0; al=sum(losses)/len(losses) if losses else 0
    print(f"  trail act+${act} give${give:<4}  {sum(pnls):>+7.0f} {100*len(wins)/len(pnls):>5.0f} {aw:>+7.2f} {al:>+8.2f} {len(pnls):>4}")
