"""s5_robustness_test.py — split-sample robustness validation for S5 best config.
Best config from grid sweep: sweep_window=5, sweep_min=$1.0, sl_buffer=$0.3, TP=$12, ER>=0.15.

Validates by splitting the 21 days into:
  - 3rds (chronological)
  - 5ths (more granular)
  - Buy-only vs Sell-only (direction balance)

Asks: does the +EV hold across regimes, or did 1 period save the whole result?
"""
import csv, sys, glob, bisect
from datetime import datetime, timedelta
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).parent))
from backtest_s3_teacher_spec import aggregate_to_tf
from backtest_v349_multiday import load_ticks, COMMON
PPP=1.0; COST=0.20; TP=12.0
MOM=0.55; RETRO=12; TRENDLB=30; TRENDMIN=7.0; ERMIN=0.15; ERLB=30
# Best config from grid sweep
SWEEP_WINDOW=5; SWEEP_MIN=1.0; SL_BUFFER=0.3

# Build oracle
ALLBARS=[]; DAYTICKS={}
for path in sorted(glob.glob(str(COMMON/"shano_ticks_2026-*.csv"))):
    tk = load_ticks(path)
    if len(tk) < 5000: continue
    DAYTICKS[Path(path).stem.split("_")[-1]] = tk
    cur=None
    for x in tk:
        m = x["t"].replace(second=0, microsecond=0); mid = (x["bid"]+x["ask"])/2
        if cur is None or m != cur["time"]:
            if cur: ALLBARS.append(cur)
            cur = {"time":m, "open":mid, "high":mid, "low":mid, "close":mid, "vol":1}
        else:
            cur["high"]=max(cur["high"],mid); cur["low"]=min(cur["low"],mid); cur["close"]=mid; cur["vol"]+=1
    if cur: ALLBARS.append(cur)
ALLBARS.sort(key=lambda b:b["time"])
M5 = aggregate_to_tf(ALLBARS, 5)
M5_close = [b["close"] for b in M5]

def trend_dir(i):
    half = TRENDLB // 2
    if i - 2*half < 0: return 0
    rHi = max(b["high"] for b in M5[i-half+1:i+1])
    rLo = min(b["low"]  for b in M5[i-half+1:i+1])
    oHi = max(b["high"] for b in M5[i-2*half+1:i-half+1])
    oLo = min(b["low"]  for b in M5[i-2*half+1:i-half+1])
    if rHi > oHi and rLo > oLo: return 1
    if rHi < oHi and rLo < oLo: return -1
    return 0
def er_at_m5(i):
    if i < ERLB: return 0.0
    net = abs(M5_close[i] - M5_close[i-ERLB])
    path = sum(abs(M5_close[j] - M5_close[j-1]) for j in range(i-ERLB+1, i+1))
    return net/path if path > 1e-9 else 0.0

def detect_breakout(i, buy):
    if i < max(TRENDLB, RETRO+1, 25): return None
    bo = M5[i]
    rng = bo["high"] - bo["low"]
    if rng <= 0: return None
    body = abs(bo["close"] - bo["open"])
    if body/rng < MOM: return None
    avgbody = sum(abs(M5[s]["close"]-M5[s]["open"]) for s in range(i-RETRO, i+1)) / (RETRO+1)
    if body < avgbody: return None
    if er_at_m5(i) < ERMIN: return None
    td24 = bo["close"] - M5[i-24]["close"]
    td = trend_dir(i)
    if buy:
        if not (bo["close"] > bo["open"] and td == 1 and td24 >= TRENDMIN): return None
        uhv_v = -1; uhv_h = 0
        for s in range(i-RETRO, i):
            b = M5[s]
            if b["close"] < b["open"] and b["vol"] > uhv_v:
                uhv_v = b["vol"]; uhv_h = b["high"]
        if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] > uhv_h and bo["open"] <= uhv_h:
            return ("buy", uhv_h, bo, i)
    else:
        if not (bo["close"] < bo["open"] and td == -1 and td24 <= -TRENDMIN): return None
        uhv_v = -1; uhv_l = 0
        for s in range(i-RETRO, i):
            b = M5[s]
            if b["close"] > b["open"] and b["vol"] > uhv_v:
                uhv_v = b["vol"]; uhv_l = b["low"]
        if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
            return ("sell", uhv_l, bo, i)
    return None

def find_failed_test(side, bo, bo_idx):
    bo_open = bo["open"]; level = bo_open
    for j in range(bo_idx+1, min(bo_idx+1+SWEEP_WINDOW, len(M5))):
        b = M5[j]
        if side == "buy":
            if b["low"] <= (level - SWEEP_MIN) and b["close"] > level:
                return (b["close"], b["low"], b["time"]+timedelta(minutes=5))
        else:
            if b["high"] >= (level + SWEEP_MIN) and b["close"] < level:
                return (b["close"], b["high"], b["time"]+timedelta(minutes=5))
    return None

def ticks_for(t): return DAYTICKS.get(t.strftime("%Y-%m-%d"))
def walk(tk, k, side, sl, tp):
    e = tk[k]["ask"] if side == "buy" else tk[k]["bid"]
    for j in range(k, min(len(tk), k+20000)):
        bid, ask = tk[j]["bid"], tk[j]["ask"]
        if side == "buy":
            if bid <= sl: return (sl-e)-COST
            if bid >= tp: return (tp-e)-COST
        else:
            if ask >= sl: return (e-sl)-COST
            if ask <= tp: return (e-tp)-COST
    last = tk[-1]; px = last["bid"] if side=="buy" else last["ask"]
    return (((px-e) if side=="buy" else (e-px))*PPP) - COST

# Generate ALL trades
trades = []   # (time, side, pnl)
for i in range(len(M5)):
    for buy in (True, False):
        sig = detect_breakout(i, buy)
        if sig is None: continue
        side, _, bo, bo_idx = sig
        confirm = find_failed_test(side, bo, bo_idx)
        if confirm is None: continue
        entry_intent, swept_extreme, entry_time = confirm
        if side == "buy":
            sl = swept_extreme - SL_BUFFER; tp = entry_intent + TP
        else:
            sl = swept_extreme + SL_BUFFER; tp = entry_intent - TP
        tk = ticks_for(entry_time)
        if not tk: continue
        T = [x["t"] for x in tk]
        k = bisect.bisect_left(T, entry_time)
        if k >= len(tk): continue
        pnl = walk(tk, k, side, sl, tp)
        trades.append((entry_time, side, pnl))
trades.sort()
n = len(trades)
print(f"S5 best config (sw=5, min=$1.0, buf=$0.3, TP=$12, ER>=0.15)")
print(f"Total: {n} trades over 21 days\n")

def report(label, subset):
    if not subset:
        print(f"  {label:<22} (empty)"); return
    s = sorted(subset)
    nn = len(s); tot = sum(p for _,_,p in s); w = sum(1 for _,_,p in s if p>0)
    print(f"  {label:<22}{nn:>4}{100*w/nn:>5.0f}%{tot:>+8.0f}{tot/nn:>+7.2f}")

print(f"  {'segment':<22}{'n':>4}{'WR%':>5}{'TOTAL$':>8}{'EV':>7}")

# Chronological thirds
if n>0:
    first_t = trades[0][0]; last_t = trades[-1][0]
    span = (last_t - first_t).total_seconds()
    t1_cut = first_t + timedelta(seconds=span/3)
    t2_cut = first_t + timedelta(seconds=2*span/3)
    seg1 = [t for t in trades if t[0] <  t1_cut]
    seg2 = [t for t in trades if t1_cut <= t[0] < t2_cut]
    seg3 = [t for t in trades if t[0] >= t2_cut]
    report("Third 1 (early)", seg1)
    report("Third 2 (mid)",   seg2)
    report("Third 3 (late)",  seg3)
print()

# Quintiles
print(f"  {'5-way split':<22}")
if n>0:
    for i in range(5):
        a = first_t + timedelta(seconds=i*span/5)
        b = first_t + timedelta(seconds=(i+1)*span/5)
        seg = [t for t in trades if a <= t[0] < b] if i<4 else [t for t in trades if t[0] >= a]
        report(f"  Fifth {i+1}", seg)
print()

# Direction split
buys = [t for t in trades if t[1]=="buy"]
sells = [t for t in trades if t[1]=="sell"]
report("BUY-only",  buys)
report("SELL-only", sells)
print()
report("ALL TRADES",  trades)
