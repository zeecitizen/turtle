"""s5_sweep_confirmed_test.py — Phase B prototype: S4's UHV-breakout setup but with
a sweep-and-close-back confirmation gate (NSND-style) before entry. Goal: keep S4's
~$12 winners but cap losses at NSND-level ($0.50-$2) by using a structural SL at the
sweep extreme instead of a fixed $6.

Detection sequence (BUY mirror; SELL is symmetric):
  1. HH/HL trend confirmed over 30 M5 bars (same as S4)
  2. 24-bar M5 move >= +$7 (same as S4)
  3. ER >= 0.15 over 30 M5 bars (same as S4 chop gate)
  4. UHV: highest-volume RED candle in last 12 M5 bars (the retracement)
  5. Initial breakout: M5 close above UHV's high, with momentum (body/range >= 0.55)
  6. *** NEW: SWEEP-AND-CLOSE-BACK CONFIRMATION ***
     Within next SWEEP_WINDOW M5 bars:
       a) Some bar's LOW dips below the breakout-bar's close by at least SWEEP_MIN
          AND below breakout-bar's open (so a real test of the breakout level)
       b) A subsequent M5 bar closes back ABOVE the breakout-bar's HIGH
     → Enter at that confirmation bar's close
     → SL = lowest low during the sweep − SL_BUFFER (structural)
     → TP = entry + $12 (fixed, matches S4 reward)

Risk asymmetry target: SL ~$0.50-$2.00, TP=$12 → breakeven WR ~4-14%.
The sweep-confirm gate should also filter weak breakouts → higher WR than raw S4.

Sweep parameters (sweep) [SWEEP_WINDOW, SWEEP_MIN, SL_BUFFER]:
   tested by grid below.
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

# ── Build aligned tick-derived M1 → M5 oracle ──
print("Building tick-derived M1 → M5 oracle...")
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
M5_t = [b["time"] for b in M5]
M5_close = [b["close"] for b in M5]
print(f"  {len(ALLBARS)} M1 / {len(M5)} M5 bars over {len(DAYTICKS)} days\n")

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
    """Replicates S4's breakout detection. Returns (uhv_h, bo) on hit, else None."""
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

def find_sweep_confirmation(side, bo, bo_idx, sweep_window, sweep_min):
    """SINGLE-BAR FAILED TEST pattern (NSND-style for tight SL).
    Within the next sweep_window M5 bars, find ONE candle that:
      (a) dips below bo_open (the breakout level) by at least sweep_min, AND
      (b) closes back above bo_open in THE SAME candle.
    That ONE candle is both the sweep AND the confirmation.
    SL = that candle's low (the swept extreme) - buffer (TIGHT by construction).
    Entry at that candle's close. Sell mirrored."""
    if side == "buy":
        bo_open = bo["open"]; level = bo_open
        for j in range(bo_idx+1, min(bo_idx+1+sweep_window, len(M5))):
            b = M5[j]
            dipped = b["low"] <= (level - sweep_min)
            recovered = b["close"] > level
            if dipped and recovered:
                return (b["close"], b["low"], b["time"]+timedelta(minutes=5))
        return None
    else:
        bo_open = bo["open"]; level = bo_open
        for j in range(bo_idx+1, min(bo_idx+1+sweep_window, len(M5))):
            b = M5[j]
            popped = b["high"] >= (level + sweep_min)
            recovered = b["close"] < level
            if popped and recovered:
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

# ── Grid search over confirmation parameters ──
print(f"S5 prototype — sweep-confirmed UHV breakout (TP=${TP}, ER>={ERMIN})\n")
print(f"  {'sweep_win':<10}{'sweep_min':<10}{'sl_buf':<8}{'n':>5}{'WR%':>5}{'TOTAL$':>8}{'EV':>7}{'avgSL':>7}{'1H$':>6}{'2H$':>6}")

CONFIGS = []
for sweep_window in [3, 5, 7]:
    for sweep_min in [0.5, 1.0, 1.5]:
        for sl_buffer in [0.10, 0.30]:
            CONFIGS.append((sweep_window, sweep_min, sl_buffer))

for cfg in CONFIGS:
    sweep_window, sweep_min, sl_buffer = cfg
    results = []
    sl_distances = []
    for i in range(len(M5)):
        for buy in (True, False):
            sig = detect_breakout(i, buy)
            if sig is None: continue
            side, _, bo, bo_idx = sig
            confirm = find_sweep_confirmation(side, bo, bo_idx, sweep_window, sweep_min)
            if confirm is None: continue
            entry_intent, swept_extreme, entry_time = confirm
            # SL is at swept extreme + buffer (against the direction of trade)
            if side == "buy":
                sl = swept_extreme - sl_buffer
                tp = entry_intent + TP
            else:
                sl = swept_extreme + sl_buffer
                tp = entry_intent - TP
            # Replay on ticks from entry_time
            tk = ticks_for(entry_time)
            if not tk: continue
            T = [x["t"] for x in tk]
            k = bisect.bisect_left(T, entry_time)
            if k >= len(tk): continue
            actual_entry = tk[k]["ask"] if side=="buy" else tk[k]["bid"]
            sl_distance = abs(actual_entry - sl)
            sl_distances.append(sl_distance)
            pnl = walk(tk, k, side, sl, tp)
            results.append((entry_time, pnl))
    if not results:
        print(f"  {sweep_window:<10}{sweep_min:<10}{sl_buffer:<8}(no trades)")
        continue
    results.sort()
    n = len(results); tot = sum(p for _,p in results); w = sum(1 for _,p in results if p>0)
    half = results[n//2][0]
    t1 = sum(p for d,p in results if d < half)
    t2 = sum(p for d,p in results if d >= half)
    avg_sl = sum(sl_distances)/len(sl_distances)
    print(f"  {sweep_window:<10}{sweep_min:<10}{sl_buffer:<8}{n:>5}{100*w/n:>4.0f}%{tot:>+8.0f}{tot/n:>+7.2f}{avg_sl:>+7.2f}{t1:>+6.0f}{t2:>+6.0f}")
