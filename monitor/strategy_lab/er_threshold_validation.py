"""er_threshold_validation.py — find validated ER (Kaufman Efficiency Ratio) thresholds
for S1/S3/NSND on the trustworthy aligned oracle, using the REVERTED (v2.44/v1.34)
configs.

Sweep ER ∈ {0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40} per engine. Report total / WR /
1st-half / 2nd-half per threshold. Pick the threshold that:
  (a) maximizes net total, and
  (b) keeps BOTH halves positive (robustness across regime), and
  (c) does not collapse trade count to a tiny sample.

Output: a per-engine recommendation. Threshold to be set as the new InpERMin default.
"""
import csv, sys, glob, bisect
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf, group_bars_by_day
from backtest_s1_uhv_breakout import s1_mirror, find_h1_fvgs
from backtest_v349_multiday import load_ticks, COMMON
from nsnd_fvg_tf_test import nsnd_signals
import s3_full_m1 as S3
# Patch S3's SL buffer to the REVERTED value (was 5.0 in the module, broken May-27 default)
S3.SLBUF = 2.0
PPP=1.0; COST=0.20; ERLB=30

print("Building tick-derived M1 oracle (aligned + live-matching volume)...")
ALLBARS=[]; DAYTICKS={}
for path in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
    tk=load_ticks(path)
    if len(tk)<5000: continue
    DAYTICKS[Path(path).stem.split("_")[-1]]=tk
    cur=None
    for x in tk:
        m=x["t"].replace(second=0,microsecond=0); mid=(x["bid"]+x["ask"])/2
        if cur is None or m!=cur["time"]:
            if cur: ALLBARS.append(cur)
            cur={"time":m,"open":mid,"high":mid,"low":mid,"close":mid,"vol":1}
        else: cur["high"]=max(cur["high"],mid); cur["low"]=min(cur["low"],mid); cur["close"]=mid; cur["vol"]+=1
    if cur: ALLBARS.append(cur)
ALLBARS.sort(key=lambda b:b["time"])
M5 = aggregate_to_tf(ALLBARS, 5)
M15 = aggregate_to_tf(ALLBARS, 15)
H1  = aggregate_to_tf(ALLBARS, 60)
hb=[f for f in find_h1_fvgs(H1) if f["side"]=="bullish"]
he=[f for f in find_h1_fvgs(H1) if f["side"]=="bearish"]
print(f"  {len(ALLBARS)} M1 bars  →  {len(M5)} M5 bars  /  {len(M15)} M15  /  {len(H1)} H1  over {len(DAYTICKS)} days\n")

# Precompute ER arrays for each TF (close-based, ERLB=30 bars)
def precompute_er(bars):
    closes=[b["close"] for b in bars]; ts=[b["time"] for b in bars]; ER=[0.0]*len(bars)
    for i in range(ERLB, len(bars)):
        net=abs(closes[i]-closes[i-ERLB])
        path=sum(abs(closes[j]-closes[j-1]) for j in range(i-ERLB+1, i+1))
        ER[i]=net/path if path>1e-9 else 0.0
    return ts, ER
M5_t, M5_ER = precompute_er(M5)
M1_t, M1_ER = precompute_er(ALLBARS)
def er_at(ts, ER, t):
    i=bisect.bisect_left(ts,t)-1
    return ER[i] if 0<=i<len(ER) else 0.0

def ticks_for(t): return DAYTICKS.get(t.strftime("%Y-%m-%d"))
def walk(tk, k, side, sl, tp):
    e=tk[k]["ask"] if side>0 else tk[k]["bid"]
    for j in range(k, min(len(tk),k+20000)):
        bid,ask=tk[j]["bid"],tk[j]["ask"]
        if side>0:
            if bid<=sl: return (sl-e)-COST
            if bid>=tp: return (tp-e)-COST
        else:
            if ask>=sl: return (e-sl)-COST
            if ask<=tp: return (e-tp)-COST
    last=tk[-1]; px=last["bid"] if side>0 else last["ask"]
    return (((px-e) if side>0 else (e-px))*PPP)-COST

# ── Generate per-engine signals with the REVERTED params ──
print("Generating signals on reverted configs...")
days = group_bars_by_day(ALLBARS)
S1_sigs=[]
for day in sorted(days):
    db=days[day]
    if len(db)<35: continue
    db_m5 = aggregate_to_tf(db, 5)
    # S1 v2.44 reverted: TF=M5, TP=7.5, sl_buf=2.0
    for s in s1_mirror(db_m5, hb, he, sl_buf=2.0, tp_points=7.5, do_buy=True, do_sell=True, require_fvg=False, require_sweep=True):
        S1_sigs.append({"side":s["side"], "sl":s["sl"], "tp":s["tp"],
                        "fire_time": s["fire_time"] - timedelta(minutes=5) + timedelta(minutes=1),
                        "tf":"M5"})
S3_sigs=[]
# S3.detect expects short-key bars (t/o/h/l/c/v). Convert.
M5_s3 = [{"t":b["time"],"o":b["open"],"h":b["high"],"l":b["low"],"c":b["close"],"v":b["vol"]} for b in M5]
for i in range(len(M5_s3)):
    for buy in (True, False):
        r = S3.detect(M5_s3, i, buy)
        if r is None: continue
        # S3 v2.44 reverted: TF=M5 (already), SLBUF=2.0 (patched), M5-FVG=true
        S3_sigs.append({"side":r["side"], "sl":r["sl"], "tp":r["tp"],
                        "fire_time": r["bo_t"] + timedelta(minutes=5),
                        "tf":"M5"})
NSND_sigs=[]
for s in nsnd_signals(ALLBARS, [(M15,15)]):
    NSND_sigs.append({"side":s["side"], "sl":s["sl"], "tp":s["tp"],
                      "fire_time": s["fire_time"], "tf":"M1"})
print(f"  S1: {len(S1_sigs)} sigs  |  S3: {len(S3_sigs)} sigs  |  NSND: {len(NSND_sigs)} sigs\n")

# ── ER sweep per engine ──
THRESHOLDS = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
def sweep(name, sigs):
    print(f"=== {name} ===")
    print(f"  {'ER≥':<6}{'n':>5}{'WR%':>5}{'TOTAL$':>8}{'EV':>7}{'1stH$':>8}{'2ndH$':>8}")
    for thr in THRESHOLDS:
        kept=[]
        for s in sigs:
            ts, ER = (M5_t, M5_ER) if s["tf"]=="M5" else (M1_t, M1_ER)
            er = er_at(ts, ER, s["fire_time"])
            if er < thr: continue
            tk = ticks_for(s["fire_time"])
            if not tk: continue
            T=[x["t"] for x in tk]; k=bisect.bisect_left(T, s["fire_time"])
            if k>=len(tk): continue
            kept.append((s["fire_time"], walk(tk, k, s["side"], s["sl"], s["tp"])))
        if not kept: print(f"  {thr:<6.2f} (no trades)"); continue
        kept.sort()
        n=len(kept); tot=sum(p for _,p in kept); w=sum(1 for _,p in kept if p>0)
        half=kept[n//2][0]
        t1=sum(p for d,p in kept if d<half); t2=sum(p for d,p in kept if d>=half)
        print(f"  {thr:<6.2f}{n:>5}{100*w/n:>4.0f}%{tot:>+8.0f}{tot/n:>+7.2f}{t1:>+8.0f}{t2:>+8.0f}")
    print()

sweep("S1 (reverted: M5, TP=7.5, SL_buf=2.0)", S1_sigs)
sweep("S3 (reverted: M5, peak-TP, SL_buf=2.0, M5-FVG on)", S3_sigs)
sweep("NSND (reverted: M1, TP=$12, SL=0.10)", NSND_sigs)
