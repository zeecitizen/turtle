"""mfe_analyzer.py — how far do trades actually run? Measures each trade's PEAK
profit ($, Maximum Favorable Excursion) on real ticks, builds the distribution,
and finds the EV-optimal fixed TP (and a breakeven-after-peak read). For S1@M1.

Method: generate live S1@M1 signals; replay ticks with NO take-profit (only the
real SL / end-of-day), recording each trade's peak $ and natural final $. Then for
any candidate TP T:  net(T) = (+T if peak>=T else natural_final) - cost.
"""
import csv, sys, glob
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs, load_ticks, COMMON
CONTRACT=100.0; LOTS=0.01; PPP=LOTS*CONTRACT; COST=0.40

def load_native(fn="latest_for_claude.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"time":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "open":float(r["open"]),"high":float(r["high"]),"low":float(r["low"]),
                       "close":float(r["close"]),"vol":int(r["tick_volume"])})
        except: pass
    b.sort(key=lambda x:x["time"]); return b

def sim_mfe(sig, ticks):
    """No-TP replay: return (peak_usd, natural_final_usd) using only the real SL/eod."""
    side, sl = sig["side"], sig["sl"]; e=None; peak=0.0
    for tk in ticks:
        if tk["t"] < sig["fire_time"]: continue
        bid, ask = tk["bid"], tk["ask"]
        if e is None: e = ask if side==+1 else bid; continue
        px = bid if side==+1 else ask
        pnl = ((px-e) if side==+1 else (e-px))*PPP
        if pnl>peak: peak=pnl
        if (side==+1 and bid<=sl) or (side==-1 and ask>=sl):
            return peak, ((sl-e) if side==+1 else (e-sl))*PPP
    if e is None: return None
    last=ticks[-1]; px=last["bid"] if side==+1 else last["ask"]
    return peak, ((px-e) if side==+1 else (e-px))*PPP

KW=dict(sl_buf=2.0,tp_points=7.5,do_buy=True,do_sell=True,require_fvg=False,require_sweep=True)
bars=load_native()
h1=aggregate_to_tf(bars,60); fv=find_h1_fvgs(h1)
hb=[f for f in fv if f["side"]=="bullish"]; he=[f for f in fv if f["side"]=="bearish"]
td={Path(p).stem.split("_")[-1]:p for p in glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))}
days=group_bars_by_day(bars)
trades=[]   # (peak, natural_final)
for day in sorted(days):
    if day not in td: continue
    db=days[day]
    if len(db)<35: continue
    sigs=s1_mirror(db,hb,he,**KW)
    for s in sigs: s["fire_time"]=s["fire_time"]-timedelta(minutes=5)+timedelta(minutes=1)
    if not sigs: continue
    ticks=load_ticks(td[day])
    for s in sigs:
        r=sim_mfe(s,ticks)
        if r: trades.append(r)

n=len(trades)
print(f"S1@M1 — {n} trades, peak-profit (MFE) distribution:\n")
for lvl in [0.5,1,1.5,2,2.5,3,4,5,6,7,8,10]:
    c=sum(1 for p,_ in trades if p>=lvl)
    bar='#'*int(c/n*40)
    print(f"  reach +${lvl:<4}: {c/n*100:>5.1f}%  {bar}")
print(f"\n  EV-optimal fixed TP (net of ${COST}/trade):")
best=None
for T in [1,1.5,2,2.5,3,3.5,4,5,6,7.5]:
    net=sum((T if p>=T else f)-COST for p,f in trades)
    ev=net/n
    if best is None or net>best[1]: best=(T,net)
    print(f"    TP +${T:<4}: total ${net:>+7.0f}  EV/tr ${ev:>+5.2f}")
print(f"\n  => best fixed TP = +${best[0]} (total ${best[1]:+.0f})")
# breakeven-after-peak: if a trade's peak>=X it would survive to BE (~$0) instead of SL
for X in [1,2,3]:
    saved=sum(1 for p,f in trades if p>=X and f<0)
    print(f"  breakeven@+${X}: would flip {saved} losers ({saved/n*100:.0f}% of all) to ~breakeven")
