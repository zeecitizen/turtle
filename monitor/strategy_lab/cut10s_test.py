"""cut10s_test.py — Zee's time-stop idea: if a trade is in LOSS N seconds after
entry, cut it immediately. Backtest on real ticks (S3), clean entries only
(skip signals before tick coverage). Compare to the current trail-only policy.

The honest-reliable part: "is it red N seconds in?" is measured purely from the
tick stream (entry tick vs the tick N seconds later) — unaffected by the bar/tick
alignment issue. The eventual outcome of trades we DON'T cut still uses the
bar-derived SL/TP, so treat absolute totals with the usual caveat; the key signal
is the RECOVERY RATE: of trades red at N s, how many go on to win anyway.
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

def sim(sig, ticks, cut_secs):
    """trail act0.3/give0.3 + SL/TP. If cut_secs>0: at the first tick >= entry+cut_secs,
    if floating<0 close immediately. Returns (pnl, red_at_cut, recovered_flag_placeholder)."""
    side,sl,tp=sig["side"],sig["sl"],sig["tp"]; e=None;peak=0.0;entry_t=None;cut_armed=(cut_secs>0)
    red_at_cut=None
    for tk in ticks:
        if tk["t"]<sig["fire_time"]: continue
        bid,ask=tk["bid"],tk["ask"]
        if e is None: e=ask if side==+1 else bid; entry_t=tk["t"]; continue
        px=bid if side==+1 else ask
        pnl=((px-e) if side==+1 else (e-px))*PPP
        if cut_armed and (tk["t"]-entry_t).total_seconds()>=cut_secs:
            red_at_cut=(pnl<0)
            cut_armed=False
            if pnl<0: return pnl-COST, red_at_cut
        if pnl>peak: peak=pnl
        if peak>=0.3:
            floor=max(0.0,peak-0.3)
            if pnl<=floor: return floor-COST, red_at_cut
        if side==+1:
            if bid<=sl: return (sl-e)*PPP-COST, red_at_cut
            if bid>=tp: return (tp-e)*PPP-COST, red_at_cut
        else:
            if ask>=sl: return (e-sl)*PPP-COST, red_at_cut
            if ask<=tp: return (e-tp)*PPP-COST, red_at_cut
    if e is None: return None, None
    last=ticks[-1];px=last["bid"] if side==+1 else last["ask"]
    return (((px-e) if side==+1 else (e-px))*PPP)-COST, red_at_cut

work=[]
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    ticks=load_ticks(td[day])
    if not ticks: continue
    ft0=ticks[0]["t"]
    s=[x for x in sigs_for(db) if x["fire_time"]>=ft0]
    if s: work.append((s,ticks))

def run(cut):
    pnls=[]
    for sg,ticks in work:
        for s in sg:
            r,_=sim(s,ticks,cut)
            if r is not None: pnls.append(r)
    w=[p for p in pnls if p>0]
    return sum(pnls),100*len(w)/len(pnls) if pnls else 0,len(pnls),(sum(w)/len(w) if w else 0),(sum(p for p in pnls if p<=0)/max(1,len(pnls)-len(w)))

print("S3 — Zee's 'cut if red after N seconds' vs trail-only (clean entries, real ticks)\n")
print(f"  {'policy':<22}{'TOTAL':>7}{'WR%':>5}{'avgWin':>8}{'avgLoss':>9}{'n':>5}")
t=run(0); print(f"  {'trail only (live)':<22}{t[0]:>+7.0f}{t[1]:>5.0f}{t[3]:>+8.2f}{t[4]:>+9.2f}{t[2]:>5}")
for cs in [10,20,30,60]:
    t=run(cs); print(f"  {'cut red @'+str(cs)+'s':<22}{t[0]:>+7.0f}{t[1]:>5.0f}{t[3]:>+8.2f}{t[4]:>+9.2f}{t[2]:>5}")

# Diagnostic: of trades RED at 10s, how many recover to a WIN under trail-only?
red=0;red_recover=0;green=0;green_win=0
for sg,ticks in work:
    for s in sg:
        full,rc=sim(s,ticks,0)   # trail-only outcome
        _,rc10=sim(s,ticks,10)   # was it red at 10s
        if full is None or rc10 is None: continue
        if rc10:  # red at 10s
            red+=1
            if full>0: red_recover+=1
        else:
            green+=1
            if full>0: green_win+=1
print(f"\nDiagnostic (trail-only outcomes):")
print(f"  red at 10s:   {red:>4} trades — recovered to a WIN: {red_recover} ({100*red_recover/max(1,red):.0f}%)")
print(f"  green at 10s: {green:>4} trades — ended a WIN:       {green_win} ({100*green_win/max(1,green):.0f}%)")
