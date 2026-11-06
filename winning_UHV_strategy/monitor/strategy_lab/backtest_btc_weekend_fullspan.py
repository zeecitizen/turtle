"""backtest_btc_weekend_fullspan.py — BtcS4b v2.00 over the FULL btc_m1_recent
span (51 days), isolating WEEKEND sessions (Sat+Sun, when XAUUSD is closed) vs
weekday, since BtcS4b is deployed for weekend BTC trading specifically.

Reuses the exact signal + ATR-trail simulation logic from backtest_btc_friday.py.
Reports ALL / WEEKEND / WEEKDAY segments, plus a walk-forward split on weekends.
Validate profitability (full P&L), not capture.
"""
import sys, csv
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

CSV = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\btc_m1_recent.csv")

TREND_LB, RETRACE_LB, BODY_FRAC, ER_MIN = 30, 12, 0.55, 0.15
UHV_RANGE_MIN, ATR_PERIOD = 100.0, 7
ATR_SL_MULT, ATR_TRAIL_MULT, ATR_BE_MULT = 2.0, 2.0, 1.0
LOTS, CONTRACT = 0.01, 1.0

bars = []
with open(CSV) as f:
    for row in csv.DictReader(f):
        bars.append({"time": datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S"),
                     "open": float(row["open"]), "high": float(row["high"]),
                     "low": float(row["low"]), "close": float(row["close"]),
                     "vol": int(row["tick_volume"])})

def trend_dir(seg):
    if len(seg) < TREND_LB: return 0
    s = seg[-TREND_LB:]; h = TREND_LB // 2; recent, older = s[h:], s[:h]
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

start_idx = TREND_LB + RETRACE_LB + 2
signals = []
for i in range(start_idx, len(bars)):
    bo = bars[i]
    rng = bo["high"] - bo["low"]
    if rng <= 0: continue
    body = abs(bo["close"] - bo["open"])
    if body / rng < BODY_FRAC: continue
    win = bars[i - RETRACE_LB:i]
    if body < sum(abs(b["close"] - b["open"]) for b in win) / len(win): continue
    tw = bars[i - TREND_LB:i]
    if efficiency_ratio(tw) < ER_MIN: continue
    td = trend_dir(tw)
    if td == 0: continue
    cur_atr = calc_atr(bars[:i+1])
    if cur_atr <= 0: continue
    if bo["close"] > bo["open"] and td == 1:
        reds = [b for b in win if b["close"] < b["open"] and (b["high"]-b["low"]) >= UHV_RANGE_MIN]
        if reds:
            uhv = max(reds, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                signals.append({"side": 1, "time": bo["time"], "entry": bo["close"], "atr": cur_atr, "bar_idx": i})
    elif bo["close"] < bo["open"] and td == -1:
        greens = [b for b in win if b["close"] > b["open"] and (b["high"]-b["low"]) >= UHV_RANGE_MIN]
        if greens:
            uhv = max(greens, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                signals.append({"side": -1, "time": bo["time"], "entry": bo["close"], "atr": cur_atr, "bar_idx": i})

trades = []
for sig in signals:
    entry, atr_v, is_buy = sig["entry"], sig["atr"], sig["side"] == 1
    day_end = datetime(sig["time"].year, sig["time"].month, sig["time"].day) + timedelta(days=1)
    sl_price = entry - ATR_SL_MULT*atr_v if is_buy else entry + ATR_SL_MULT*atr_v
    peak, be_hit, exit_price = 0, False, entry
    for j in range(sig["bar_idx"]+1, len(bars)):
        b = bars[j]
        if b["time"] >= day_end + timedelta(hours=4): exit_price = b["open"]; break
        if is_buy:
            peak = max(peak, b["high"]-entry)
            if not be_hit and peak >= ATR_BE_MULT*atr_v: be_hit = True; sl_price = max(sl_price, entry)
            sl_price = max(sl_price, (entry+peak) - ATR_TRAIL_MULT*atr_v)
            if b["low"] <= sl_price: exit_price = sl_price; break
        else:
            peak = max(peak, entry-b["low"])
            if not be_hit and peak >= ATR_BE_MULT*atr_v: be_hit = True; sl_price = min(sl_price, entry)
            sl_price = min(sl_price, (entry-peak) + ATR_TRAIL_MULT*atr_v)
            if b["high"] >= sl_price: exit_price = sl_price; break
    pnl = ((exit_price-entry) if is_buy else (entry-exit_price)) * LOTS * CONTRACT
    trades.append({"time": sig["time"], "pnl": pnl, "weekend": sig["time"].weekday() >= 5})  # Sat=5,Sun=6

def report(name, ts):
    n = len(ts)
    if not n: print(f"  {name:<10} n=0"); return
    w = sum(1 for t in ts if t["pnl"] > 0); tot = sum(t["pnl"] for t in ts)
    aw = sum(t["pnl"] for t in ts if t["pnl"] > 0)/w if w else 0
    al = sum(t["pnl"] for t in ts if t["pnl"] <= 0)/(n-w) if (n-w) else 0
    print(f"  {name:<10} n={n:>4}  WR={w/n:>5.1%}  avgW=${aw:>5.2f}  avgL=${al:>+6.2f}  TOTAL=${tot:>+8.2f}")

days_span = sorted({t["time"].strftime("%Y-%m-%d") for t in trades})
print(f"\nBtcS4b full-span: {bars[0]['time'].date()} → {bars[-1]['time'].date()}  ({len(bars)} bars)")
print(f"Trades on {len(days_span)} days. LOTS={LOTS}\n")
report("ALL", trades)
report("WEEKEND", [t for t in trades if t["weekend"]])
report("WEEKDAY", [t for t in trades if not t["weekend"]])

# Walk-forward on WEEKEND subset (the deployed job): split weekend-days in half
we = [t for t in trades if t["weekend"]]
we_days = sorted({t["time"].strftime("%Y-%m-%d") for t in we})
if len(we_days) >= 4:
    cut = we_days[len(we_days)//2]
    print(f"\nWEEKEND walk-forward (split @ {cut}):")
    report("WE-TRAIN", [t for t in we if t["time"].strftime("%Y-%m-%d") < cut])
    report("WE-OOS", [t for t in we if t["time"].strftime("%Y-%m-%d") >= cut])
else:
    print(f"\nWEEKEND walk-forward: only {len(we_days)} weekend-days — too few to split.")
