"""backtest_btc_friday.py — Simulate S4b v2.00 on BTCUSD M1 for Friday May 22nd.
Uses exported btc_m1_recent.csv from MT5.
"""
import sys, csv
from datetime import datetime, timedelta
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\btc_m1_recent.csv")

# Parameters matching BtcS4bTrader
TREND_LB = 30
RETRACE_LB = 12
BODY_FRAC = 0.55
ER_MIN = 0.15
UHV_RANGE_MIN = 100.0  # BTC scale
ATR_PERIOD = 7
ATR_SL_MULT = 2.0
ATR_TRAIL_MULT = 2.0
ATR_BE_MULT = 1.0
LOTS = 0.01
CONTRACT = 1.0  # 1 lot = 1 BTC typically

# Load bars
bars = []
with open(CSV, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        bars.append({
            "time": datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "vol": int(row["tick_volume"]),
            "spread": float(row["spread"]),
        })

print(f"Loaded {len(bars)} M1 bars: {bars[0]['time']} → {bars[-1]['time']}")

# Helper functions
def trend_dir(seg):
    if len(seg) < TREND_LB: return 0
    s = seg[-TREND_LB:]
    h = TREND_LB // 2
    recent, older = s[h:], s[:h]
    if max(b["high"] for b in recent) > max(b["high"] for b in older) and \
       min(b["low"] for b in recent) > min(b["low"] for b in older): return 1
    if max(b["high"] for b in recent) < max(b["high"] for b in older) and \
       min(b["low"] for b in recent) < min(b["low"] for b in older): return -1
    return 0

def efficiency_ratio(seg):
    s = seg[-TREND_LB:]
    if len(s) < 2: return 0.0
    net = abs(s[-1]["close"] - s[0]["close"])
    path = sum(abs(s[k]["close"] - s[k-1]["close"]) for k in range(1, len(s)))
    return (net / path) if path > 0 else 0.0

def calc_atr(seg):
    if len(seg) < ATR_PERIOD + 1: return 0.0
    trs = []
    for i in range(-ATR_PERIOD, 0):
        h, l, pc = seg[i]["high"], seg[i]["low"], seg[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)

# Run for multiple days to see the pattern
print(f"\n{'='*100}")
print(f"BTCUSD S4b v2.00 — Bar-by-bar simulation")
print(f"UHV range min = ${UHV_RANGE_MIN:.0f}, ATR({ATR_PERIOD}): SL={ATR_SL_MULT}x, Trail={ATR_TRAIL_MULT}x, BE@{ATR_BE_MULT}x")
print(f"{'='*100}")

# Group by day
from collections import defaultdict
days = defaultdict(list)
for b in bars:
    days[b["time"].strftime("%Y-%m-%d")].append(b)

start_idx = TREND_LB + RETRACE_LB + 2
all_trades = []

# Focus on recent week including Friday 22nd
target_days = sorted(days.keys())[-10:]  # last 10 days

for day_str in target_days:
    day_bars = days[day_str]
    day_start = datetime.strptime(day_str, "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    
    # Find signals on this day
    day_signals = []
    for i in range(start_idx, len(bars)):
        bo = bars[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < BODY_FRAC: continue
        
        win = bars[i - RETRACE_LB:i]
        avgbody = sum(abs(b["close"] - b["open"]) for b in win) / len(win)
        if body < avgbody: continue
        
        tw = bars[i - TREND_LB:i]
        if efficiency_ratio(tw) < ER_MIN: continue
        td = trend_dir(tw)
        if td == 0: continue
        
        cur_atr = calc_atr(bars[:i+1])
        if cur_atr <= 0: continue
        
        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"] and (b["high"]-b["low"]) >= UHV_RANGE_MIN]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                day_signals.append({"side": 1, "time": bo["time"], "entry": bo["close"],
                                    "atr": cur_atr, "bar_idx": i})
                continue
        
        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"] and (b["high"]-b["low"]) >= UHV_RANGE_MIN]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                day_signals.append({"side": -1, "time": bo["time"], "entry": bo["close"],
                                    "atr": cur_atr, "bar_idx": i})
    
    # Simulate trades
    day_trades = []
    for sig in day_signals:
        entry = sig["entry"]
        atr_v = sig["atr"]
        is_buy = sig["side"] == 1
        sl_price = entry - ATR_SL_MULT * atr_v if is_buy else entry + ATR_SL_MULT * atr_v
        peak = 0
        be_hit = False
        exit_price = entry
        outcome = "EOD"
        
        for j in range(sig["bar_idx"] + 1, len(bars)):
            b = bars[j]
            if b["time"] >= day_end + timedelta(hours=4):
                exit_price = b["open"]
                outcome = "EOD"
                break
            
            if is_buy:
                if b["high"] - entry > peak:
                    peak = b["high"] - entry
                if not be_hit and peak >= ATR_BE_MULT * atr_v:
                    be_hit = True
                    sl_price = max(sl_price, entry)
                trail_sl = (entry + peak) - ATR_TRAIL_MULT * atr_v
                if trail_sl > sl_price:
                    sl_price = trail_sl
                if b["low"] <= sl_price:
                    exit_price = sl_price
                    outcome = "SL"
                    break
            else:
                if entry - b["low"] > peak:
                    peak = entry - b["low"]
                if not be_hit and peak >= ATR_BE_MULT * atr_v:
                    be_hit = True
                    sl_price = min(sl_price, entry)
                trail_sl = (entry - peak) + ATR_TRAIL_MULT * atr_v
                if trail_sl < sl_price:
                    sl_price = trail_sl
                if b["high"] >= sl_price:
                    exit_price = sl_price
                    outcome = "SL"
                    break
        
        pnl_pts = (exit_price - entry) if is_buy else (entry - exit_price)
        pnl_usd = pnl_pts * LOTS * CONTRACT
        day_trades.append({
            "time": sig["time"], "side": "BUY" if is_buy else "SELL",
            "entry": entry, "exit": exit_price, "pnl": pnl_usd, "outcome": outcome,
            "atr": atr_v,
        })
    
    all_trades.extend(day_trades)
    
    n = len(day_trades)
    if n == 0:
        print(f"  {day_str}  n=  0  (no signals)")
        continue
    w = sum(1 for t in day_trades if t["pnl"] > 0)
    tot = sum(t["pnl"] for t in day_trades)
    wr = w / n if n else 0
    flag = " ← FRIDAY" if "2026-05-22" in day_str else ""
    print(f"  {day_str}  n={n:>3}  WR={wr:>5.1%}  P&L=${tot:>+8.2f}{flag}")
    
    # Print individual trades for Friday
    if "2026-05-22" in day_str or "2026-05-23" in day_str or "2026-05-24" in day_str:
        for t in day_trades:
            wl = "W" if t["pnl"] > 0 else "L"
            print(f"    {t['time'].strftime('%H:%M')} {t['side']:<4} entry=${t['entry']:>10.2f} exit=${t['exit']:>10.2f} [{t['outcome']}] ATR=${t['atr']:.2f} pnl=${t['pnl']:>+8.2f} {wl}")

# Summary
print(f"\n{'='*100}")
n = len(all_trades)
if n:
    w = sum(1 for t in all_trades if t["pnl"] > 0)
    tot = sum(t["pnl"] for t in all_trades)
    avg_w = sum(t["pnl"] for t in all_trades if t["pnl"] > 0) / w if w else 0
    avg_l = sum(t["pnl"] for t in all_trades if t["pnl"] <= 0) / (n - w) if (n - w) else 0
    print(f"TOTAL ({len(target_days)} days): n={n}  WR={w/n:.1%}  avg_W=${avg_w:.2f}  avg_L=${avg_l:+.2f}  TOTAL=${tot:+.2f}")
else:
    print("No trades found. Diagnosing...")
    # Check what UHV range would work
    recent = [b for b in bars if b["time"] >= datetime(2026, 5, 20)]
    ranges = [b["high"] - b["low"] for b in recent]
    if ranges:
        print(f"  Recent M1 range stats: avg=${sum(ranges)/len(ranges):.2f}, max=${max(ranges):.2f}, p90=${sorted(ranges)[int(len(ranges)*0.9)]:.2f}")
        print(f"  Current UHV_RANGE_MIN = ${UHV_RANGE_MIN:.0f}")
        # Count bars with range >= threshold at various levels
        for threshold in [10, 25, 50, 75, 100, 150, 200]:
            count = sum(1 for r in ranges if r >= threshold)
            print(f"    Bars with range >= ${threshold}: {count} ({count/len(ranges)*100:.1f}%)")
