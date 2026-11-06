"""Bottom-up study: every place price turned UP on one M5 session, judged by VSISA.

Zee, 2026-09-17: "find out all places where price rises -> let's call these places
bottoms -> now on the bottoms apply the VSISA concepts you've learnt -> compare your
prediction from VSISA concepts to the actual candles after the reaction candle's appear
-> see if you can manage more than 1 VSISA setups on the 5 minute timeframe."

This is the opposite direction from every search so far. The EA starts from its filters
and asks what passes; this starts from what the MARKET did and asks which turns VSISA
could have called. That is the only way to see setups the EA is BLIND to, rather than
setups it merely rates differently.

*** HYPOTHESIS ONLY - CLAUDE.md ***
No P&L is computed or reported here. This measures, per bottom, how far price actually
travelled in each direction after the reaction candle, in POINTS, from MT5's own exported
bars. A rule that looks good here has earned one thing: a run in the Strategy Tester.
Python's measured haircut on win rate is ~16 points.
"""
from __future__ import annotations
import csv, sys, statistics as st
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

CSV = Path(r"C:/Users/zeesh/AppData/Roaming/MetaQuotes/Terminal/Common/Files/vsisa_bars_now.csv")
DAY = "2026.09.16"
PT  = 0.01          # gold: 1 point
PIV = 2             # bars each side that define a bottom
FWD = 24            # bars of future to measure (2 hours of M5)
SL_BUF = 120        # points below the reaction low - the EA's own buffer

rows=[r for r in csv.DictReader(open(CSV))]
B=[{"t":r["time_iso"],"o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
    "c":float(r["close"]),"v":int(r["tick_volume"])} for r in rows]
day=[i for i,b in enumerate(B) if b["t"].startswith(DAY)]
lo,hi=day[0],day[-1]
print("bars loaded %d | %s has %d M5 bars (%s .. %s)"%(len(B),DAY,len(day),B[lo]["t"][11:],B[hi]["t"][11:]))

def avg(xs): return sum(xs)/len(xs) if xs else 0.0

# ---------- step 1: every bottom, i.e. every place price rises from ----------
bottoms=[]
for i in range(lo,hi+1):
    if i-PIV<0 or i+PIV>len(B)-1: continue
    if all(B[i]["l"]<B[i-q]["l"] and B[i]["l"]<=B[i+q]["l"] for q in (1,PIV)):
        bottoms.append(i)
print("bottoms (pivot lows, %d bars each side): %d"%(PIV,len(bottoms)))

# ---------- step 2: at each bottom, read the VSISA story ----------
out=[]
for i in bottoms:
    # the reaction candle: first bar closing UP at the low or just after it
    r=None
    for k in (i,i+1,i+2):
        if k<=len(B)-2 and B[k]["c"]>B[k]["o"]: r=k; break
    if r is None: continue
    # the background campaign: the run of DOWN bars before the low
    camp=[]; k=i-1 if B[i]["c"]<=B[i]["o"] else i
    j=i
    while j>0 and B[j]["c"]<=B[j]["o"] and len(camp)<10:
        camp.append(j); j-=1
    if not camp: continue
    look=[b["v"] for b in B[max(0,r-200):r]]
    if not look: continue
    vmax,vavg=max(look),avg(look)
    cmax=max(B[c]["v"] for c in camp)
    rb=B[r]
    rng=rb["h"]-rb["l"]
    f={"t":rb["t"][11:16],"camp":len(camp),
       "big_max":cmax/vmax if vmax else 0,          # LAW: campaign must be LOUD
       "big_avg":cmax/vavg if vavg else 0,
       "quiet":rb["v"]/cmax if cmax else 9,         # LAW: reaction must be QUIET
       "body":(rb["c"]-rb["o"])/rng if rng else 0,
       "spread":rng/avg([B[q]["h"]-B[q]["l"] for q in range(max(0,r-20),r)] or [1]),
       "swept":1 if rb["l"]<=min(B[q]["l"] for q in range(max(0,r-30),r)) else 0}
    # ---------- step 3: what the candles AFTER the reaction actually did ----------
    entry=rb["c"]; stop=rb["l"]-SL_BUF*PT; risk=entry-stop
    if risk<=0: continue
    mfe=mae=0.0; hitR=0.0; stopped=None
    for q in range(r+1,min(r+1+FWD,len(B))):
        mae=max(mae,(entry-B[q]["l"])/PT); mfe=max(mfe,(B[q]["h"]-entry)/PT)
        if stopped is None and B[q]["l"]<=stop: stopped=q-r
        if stopped is None: hitR=max(hitR,(B[q]["h"]-entry)/risk)
    f.update(risk_pts=risk/PT,mfe=mfe,mae=mae,R=hitR,stopped=stopped or 0)
    out.append(f)

print("\nbottoms with a readable reaction candle + campaign: %d\n"%len(out))
print("%-6s %4s %6s %6s %6s %5s %6s %5s | %7s %6s %6s %5s"%(
      "time","camp","bigMax","bigAvg","quiet","body","spread","swept","riskPts","MFE","MAE","R"))
print("-"*104)
for f in out:
    print("%-6s %4d %6.2f %6.2f %6.2f %5.2f %6.2f %5d | %7.0f %6.0f %6.0f %5.2f"%(
        f["t"],f["camp"],f["big_max"],f["big_avg"],f["quiet"],f["body"],f["spread"],
        f["swept"],f["risk_pts"],f["mfe"],f["mae"],f["R"]))

# ---------- step 4: which of the laws actually separated the good bottoms ----------
def split(name,key,thr):
    a=[f for f in out if f[key]>=thr]; b=[f for f in out if f[key]<thr]
    def s(g): return "n=%2d  reach2R %2d%%  medR %4.2f"%(
        len(g),100*sum(1 for f in g if f["R"]>=2)//max(1,len(g)),
        st.median([f["R"] for f in g]) if g else 0)
    print("%-22s >=%-5s %s   |  <  %s"%(name,thr,s(a),s(b)))

print("\nWhich law separated a good bottom from a bad one (reach 2R before the stop):")
print("ALL BOTTOMS            %s"%("n=%2d  reach2R %2d%%  medR %4.2f"%(
    len(out),100*sum(1 for f in out if f["R"]>=2)//max(1,len(out)),
    st.median([f["R"] for f in out]) if out else 0)))
for n,k,t in (("campaign loud vs max","big_max",0.70),("campaign loud vs avg","big_avg",1.10),
              ("reaction body","body",0.35),("reaction spread","spread",1.00),
              ("swept a 30-bar low","swept",1)):
    split(n,k,t)
print("\nreaction QUIET (lower is quieter) - split the other way:")
for t in (0.40,0.60,0.80,1.00):
    a=[f for f in out if f["quiet"]<=t]
    print("  quiet <= %.2f   n=%2d  reach2R %2d%%  medR %4.2f"%(
        t,len(a),100*sum(1 for f in a if f["R"]>=2)//max(1,len(a)),
        st.median([f["R"] for f in a]) if a else 0))
