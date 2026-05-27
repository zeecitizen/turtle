"""s1_m1_exits.py — should S1@M1 book quick profits? These M1 breakouts peak fast
then reverse. Test exit policies on the ACTUAL S1@M1 signals (native bars, ticks):
baseline (fixed TP/SL) vs quick-TP caps vs breakeven-after-peak vs trail.
Adopt only what BEATS baseline net-of-cost AND holds OOS (don't just cap winners).
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day, stats
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, load_ticks, COMMON
CONTRACT = 100.0; LOTS = 0.01; PPP = LOTS*CONTRACT; COST = 0.40

def load_native(fn="latest_for_claude.csv"):
    b = []
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time": datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),
                       "close":float(r["close"]),"vol":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["time"]); return b

def sim(sig, ticks, policy):
    """Walk ticks from fire; return net pnl($) for one trade under `policy`."""
    side, sl, tp = sig["side"], sig["sl"], sig["tp"]
    e = None; peak = 0.0
    for tk in ticks:
        if tk["t"] < sig["fire_time"]: continue
        bid, ask = tk["bid"], tk["ask"]
        if e is None:
            e = ask if side==+1 else bid          # enter at next tick
            cur_sl = sl
            continue
        px = bid if side==+1 else ask              # mark price for this side
        pnl = ((px-e) if side==+1 else (e-px))*PPP
        peak = max(peak, pnl)
        # policy-driven dynamic stop / cap
        if policy["type"]=="tpcap" and pnl >= policy["usd"]:
            return pnl-COST
        if policy["type"]=="breakeven" and peak >= policy["arm"]:
            cur_sl = e + (0.01 if side==+1 else -0.01)   # ~breakeven
            if (side==+1 and px<=cur_sl) or (side==-1 and px>=cur_sl):
                return ((cur_sl-e) if side==+1 else (e-cur_sl))*PPP - COST
        if policy["type"]=="trail" and peak >= policy["arm"]:
            lock = peak - policy["drop"]*PPP             # trail $drop below peak
            if pnl <= lock: return lock-COST
        # base SL / TP
        if side==+1:
            if bid<=cur_sl: return (cur_sl-e)*PPP-COST
            if bid>=tp:     return (tp-e)*PPP-COST
        else:
            if ask>=cur_sl: return (e-cur_sl)*PPP-COST
            if ask<=tp:     return (e-tp)*PPP-COST
    if e is None: return None
    last = ticks[-1]; px = last["bid"] if side==+1 else last["ask"]
    return (((px-e) if side==+1 else (e-px))*PPP)-COST

KW = dict(sl_buf=2.0, tp_points=7.5, do_buy=True, do_sell=True, require_fvg=False, require_sweep=True)
bars = load_native()
h1 = aggregate_to_tf(bars,60); fv = find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}
days=group_bars_by_day(bars)
# pre-collect (day, signals, ticks)
work=[]
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    sigs=s1_mirror(db,hb,he,**KW)
    for s in sigs: s["fire_time"]=s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)
    if sigs: work.append((day, sigs, load_ticks(td[day])))

POLICIES={
  "baseline (TP7.5/SL)":      {"type":"none"},
  "book +$3 (tp cap)":        {"type":"tpcap","usd":3.0},
  "book +$5 (tp cap)":        {"type":"tpcap","usd":5.0},
  "breakeven after +$3":      {"type":"breakeven","arm":3.0},
  "trail $2 after +$3 peak":  {"type":"trail","arm":3.0,"drop":2.0},
}
print(f"S1@M1 exit-policy test — {sum(len(s) for _,s,_ in work)} signals, net of ${COST}/tr cost\n")
for name,pol in POLICIES.items():
    perday={}
    for day,sigs,ticks in work:
        tot=0
        for s in sigs:
            r=sim(s,ticks,pol)
            if r is not None: tot+=r
        perday[day]=tot
    allp=[v for v in perday.values()]; total=sum(allp)
    dl=sorted(perday); cut=dl[len(dl)//2]
    oos=sum(v for d,v in perday.items() if d>=cut)
    print(f"  {name:<26} TOTAL ${total:>+7.0f}   OOS ${oos:>+6.0f}   {'OK' if oos>0 else 'BAD'}")
