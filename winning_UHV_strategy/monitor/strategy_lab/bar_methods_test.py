"""bar_methods_test.py — CLEAN bar-based backtest (no alignment bug possible: signals
AND fills come from the same single bar file) of two of Zee's earlier-entry methods
from the Loom/YouTube teaching (yt_BEkjgePTwjw):

  TWO-BAR REVERSAL (sell): in a downtrend, after an up candle (the retracement push),
    the next candle breaks that up candle's LOW and closes below it -> short.
  ENGULFING (sell): in a downtrend, a down candle engulfs the prior candle's body AND
    breaks its low, on SMALLER volume (no-demand) -> short.   (buys = mirror)

Both fire EARLIER than the UHV sweep entry. We trade WITH the trend (teacher's rule).
Exit sweep: SL beyond the pattern extreme (+buffer), TP at an R multiple. Bar fills:
enter next-bar open; each later bar, SL checked before TP (conservative). Reports per
method/exit: trades, WR, net total, EV/trade, and a train/test split for robustness.
Data: 27thmayexport.csv (100k M1 bars). $ = price points at 0.01 lot (PPP=1).
"""
import csv, sys
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
from backtest_s1_uhv_breakout import COMMON
PPP=1.0

def load(fn="27thmayexport.csv"):
    b=[]
    for r in csv.DictReader(open(COMMON/fn)):
        try: b.append({"t":datetime.strptime(r["time_iso"],"%Y.%m.%d %H:%M:%S"),
                       "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
                       "c":float(r["close"]),"v":int(r["tick_volume"]),
                       "sp":float(r["spread"])*0.001})
        except: pass
    b.sort(key=lambda x:x["t"]); return b
B=load(); n=len(B)
print(f"loaded {n} M1 bars  {B[0]['t']} .. {B[-1]['t']}\n")

def trend(i, look=30):
    if i-look<0: return 0
    d=B[i]["c"]-B[i-look]["c"]
    th=0.8   # ~$0.8 over 30 M1 bars to call a trend (filters chop)
    return 1 if d>th else (-1 if d<-th else 0)

def avgvol(i, k=20):
    s=0;c=0
    for j in range(max(0,i-k),i):
        s+=B[j]["v"]; c+=1
    return s/c if c else 0

def signals(method):
    """yield (i_signal, side, sl, pattern_extreme) — entry is next bar open."""
    out=[]
    for i in range(31,n-1):
        tr=trend(i)
        a,b=B[i-1],B[i]   # a=prior, b=trigger
        if method=="twobar":
            # SELL: downtrend, prior up candle, trigger breaks its low & closes below
            if tr<0 and a["c"]>a["o"] and b["c"]<a["l"]:
                out.append((i,-1,max(a["h"],b["h"])))
            # BUY: uptrend, prior down candle, trigger breaks its high & closes above
            if tr>0 and a["c"]<a["o"] and b["c"]>a["h"]:
                out.append((i,+1,min(a["l"],b["l"])))
        elif method=="engulf":
            small = b["v"] < a["v"]              # no-demand / no-supply: smaller volume
            # bearish engulf + break low, downtrend
            if tr<0 and b["c"]<b["o"] and b["o"]>=a["c"] and b["c"]<a["o"] and b["c"]<a["l"] and small:
                out.append((i,-1,max(a["h"],b["h"])))
            # bullish engulf + break high, uptrend
            if tr>0 and b["c"]>b["o"] and b["o"]<=a["c"] and b["c"]>a["o"] and b["c"]>a["h"] and small:
                out.append((i,+1,min(a["l"],b["l"])))
    return out

def sim(sigs, rr, slbuf=0.10):
    """enter next-bar open; SL=extreme±buf; TP=entry±rr*risk. SL checked before TP."""
    res=[]
    for (i,side,ext) in sigs:
        e=B[i+1]["o"]
        sl = ext + slbuf if side<0 else ext - slbuf
        risk = abs(e-sl)
        if risk<0.05: continue
        tp = e - rr*risk if side<0 else e + rr*risk
        cost = B[i]["sp"] + 0.04
        outc=None
        for j in range(i+1, min(n, i+1+600)):   # cap hold ~10h
            hi,lo=B[j]["h"],B[j]["l"]
            if side<0:
                if hi>=sl: outc=-(risk)-cost; break
                if lo<=tp: outc=+(rr*risk)-cost; break
            else:
                if lo<=sl: outc=-(risk)-cost; break
                if hi>=tp: outc=+(rr*risk)-cost; break
        if outc is None:
            px=B[min(n-1,i+600)]["c"]; outc=((e-px) if side<0 else (px-e))-cost
        res.append((B[i]["t"],outc))
    return res

def report(name, res):
    if not res: print(f"  {name:<26} (no trades)"); return
    tot=sum(p for _,p in res); w=[p for _,p in res if p>0]; wr=100*len(w)/len(res)
    half=res[len(res)//2][0]
    tr1=sum(p for t,p in res if t< half); tr2=sum(p for t,p in res if t>=half)
    ev=tot/len(res)
    print(f"  {name:<26}{tot:>+8.0f}{wr:>6.0f}{len(res):>6}{ev:>+8.2f}{tr1:>+8.0f}{tr2:>+8.0f}")

for method in ["twobar","engulf"]:
    sg=signals(method)
    print(f"=== {method.upper()}  ({len(sg)} raw signals) ===")
    print(f"  {'exit':<26}{'TOTAL':>8}{'WR%':>6}{'n':>6}{'EV':>8}{'1stHalf':>8}{'2ndHalf':>8}")
    for rr in [1.0,1.5,2.0,3.0]:
        report(f"with-trend, {rr}:1 R", sim(sg, rr))
    print()
