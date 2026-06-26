"""backtest_all_eas_xau.py — Test S4, S4b on XAUUSD M1 for last 10 days.

S1 and S3 are M5-based with FVG requirements that need H1/M5 multi-TF data,
so we build M5 bars from M1 and simulate their core UHV logic (minus FVG filter).

Run: python backtest_all_eas_xau.py
"""
import sys, csv
from datetime import datetime, timedelta
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")

CSV = r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files\export_m1_recent.csv"

# Load M1 bars
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
        })

print(f"Loaded {len(bars)} M1 bars: {bars[0]['time']} → {bars[-1]['time']}")

# Build M5 bars from M1
def build_m5(m1_bars):
    m5 = []
    bucket = []
    for b in m1_bars:
        mins = b["time"].minute
        if mins % 5 == 0 and bucket:
            m5.append({
                "time": bucket[0]["time"],
                "open": bucket[0]["open"],
                "high": max(x["high"] for x in bucket),
                "low": min(x["low"] for x in bucket),
                "close": bucket[-1]["close"],
                "vol": sum(x["vol"] for x in bucket),
            })
            bucket = [b]
        else:
            bucket.append(b)
    if bucket:
        m5.append({
            "time": bucket[0]["time"],
            "open": bucket[0]["open"],
            "high": max(x["high"] for x in bucket),
            "low": min(x["low"] for x in bucket),
            "close": bucket[-1]["close"],
            "vol": sum(x["vol"] for x in bucket),
        })
    return m5

m5_bars = build_m5(bars)
print(f"Built {len(m5_bars)} M5 bars")

LOTS = 0.10
CONTRACT = 100.0
PPP = LOTS * CONTRACT  # profit per point

# ════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════

def trend_dir_hh_hl(seg, lb=30):
    if len(seg) < lb: return 0
    s = seg[-lb:]
    h = lb // 2
    recent, older = s[h:], s[:h]
    if max(b["high"] for b in recent) > max(b["high"] for b in older) and \
       min(b["low"] for b in recent) > min(b["low"] for b in older): return 1
    if max(b["high"] for b in recent) < max(b["high"] for b in older) and \
       min(b["low"] for b in recent) < min(b["low"] for b in older): return -1
    return 0

def efficiency_ratio(seg, lb=30):
    s = seg[-lb:]
    if len(s) < 2: return 0.0
    net = abs(s[-1]["close"] - s[0]["close"])
    path = sum(abs(s[k]["close"] - s[k-1]["close"]) for k in range(1, len(s)))
    return (net / path) if path > 0 else 0.0

def calc_atr(seg, period=7):
    if len(seg) < period + 1: return 0.0
    trs = []
    for i in range(-period, 0):
        h, l, pc = seg[i]["high"], seg[i]["low"], seg[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)

# ════════════════════════════════════════════════════════════════
# S4 DETECTOR (M1, fixed TP12/SL6)
# ════════════════════════════════════════════════════════════════

def detect_s4(m1, tp=12.0, sl=6.0, er_min=0.15, uhv_range_min=1.0):
    sigs = []
    start = 30 + 12 + 2
    for i in range(start, len(m1)):
        bo = m1[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < 0.55: continue
        win = m1[i-12:i]
        avgbody = sum(abs(b["close"]-b["open"]) for b in win) / len(win)
        if body < avgbody: continue
        tw = m1[i-30:i]
        if er_min > 0 and efficiency_ratio(tw) < er_min: continue
        td = trend_dir_hh_hl(tw)
        if td == 0: continue

        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"] and (b["high"]-b["low"]) >= uhv_range_min]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                sigs.append({"side": 1, "time": bo["time"], "entry": bo["close"],
                             "tp": tp, "sl": sl, "atr": calc_atr(m1[:i+1])})
                continue

        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"] and (b["high"]-b["low"]) >= uhv_range_min]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                sigs.append({"side": -1, "time": bo["time"], "entry": bo["close"],
                             "tp": tp, "sl": sl, "atr": calc_atr(m1[:i+1])})
    return sigs

# ════════════════════════════════════════════════════════════════
# S3 DETECTOR (M5, wicking green/red breakout, no FVG for sim)
# ════════════════════════════════════════════════════════════════

def detect_s3(m5, trend_lb=24, trend_thresh=1.0, retrace_lb=30, tp_peak_lb=10,
              sl_buf=2.0, max_upper_wick=0.35, big_spread_mult=0.0):
    sigs = []
    start = trend_lb + retrace_lb + 2
    for i in range(start, len(m5)):
        bo = m5[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        # BUY: green breakout
        if bo["close"] > bo["open"]:
            # Upper wick filter
            upper_wick = bo["high"] - bo["close"]
            if max_upper_wick > 0 and rng > 0 and upper_wick / rng > max_upper_wick:
                continue

            # Uptrend check
            if i < trend_lb + 1: continue
            trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
            if trend_move <= trend_thresh: continue

            # Find UHV red in retracement
            win = m5[i - retrace_lb:i]
            reds = [b for b in win if b["close"] < b["open"]]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            uhv_h = uhv["high"]
            uhv_l = uhv["low"]

            # Big spread check
            if big_spread_mult > 0:
                avg_rng = sum(b["high"]-b["low"] for b in m5[max(0,i-10):i]) / min(10, i)
                if (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue

            # Breakout: close > UHV high, open <= UHV high
            if bo["close"] <= uhv_h or bo["open"] > uhv_h: continue

            # Sweep: some bar between UHV and breakout has low < UHV low
            uhv_idx = None
            for j, b in enumerate(win):
                if b["time"] == uhv["time"]: uhv_idx = j; break
            if uhv_idx is None: continue
            swept = any(win[k]["low"] < uhv_l for k in range(uhv_idx+1, len(win)))
            if not swept: continue

            # TP: recent peak
            peak_bars = m5[max(0, i-tp_peak_lb):i]
            tp_price = max(b["high"] for b in peak_bars)
            tp_dist = tp_price - bo["close"]
            if tp_dist < 0.2: continue

            sl_price = uhv_l - sl_buf
            sl_dist = bo["close"] - sl_price

            sigs.append({"side": 1, "time": bo["time"], "entry": bo["close"],
                         "tp": tp_dist, "sl": sl_dist, "atr": 0})

        # SELL: red breakout
        elif bo["close"] < bo["open"]:
            trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
            if trend_move <= trend_thresh: continue

            win = m5[i - retrace_lb:i]
            greens = [b for b in win if b["close"] > b["open"]]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            uhv_h = uhv["high"]
            uhv_l = uhv["low"]

            if big_spread_mult > 0:
                avg_rng = sum(b["high"]-b["low"] for b in m5[max(0,i-10):i]) / min(10, i)
                if (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue

            if bo["close"] >= uhv_l or bo["open"] < uhv_l: continue

            uhv_idx = None
            for j, b in enumerate(win):
                if b["time"] == uhv["time"]: uhv_idx = j; break
            if uhv_idx is None: continue
            swept = any(win[k]["high"] > uhv_h for k in range(uhv_idx+1, len(win)))
            if not swept: continue

            peak_bars = m5[max(0, i-tp_peak_lb):i]
            tp_price = min(b["low"] for b in peak_bars)
            tp_dist = bo["close"] - tp_price
            if tp_dist < 0.2: continue

            sl_price = uhv_h + sl_buf
            sl_dist = sl_price - bo["close"]

            sigs.append({"side": -1, "time": bo["time"], "entry": bo["close"],
                         "tp": tp_dist, "sl": sl_dist, "atr": 0})
    return sigs

# ════════════════════════════════════════════════════════════════
# S1 DETECTOR (M5, sweep + big spread, no H1 FVG for sim)
# ════════════════════════════════════════════════════════════════

def detect_s1(m5, trend_lb=24, trend_thresh=2.0, retrace_lb=15,
              sl_buf=2.0, tp_pts=7.5, big_spread_mult=1.3):
    sigs = []
    start = trend_lb + retrace_lb + 2
    for i in range(start, len(m5)):
        bo = m5[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        # BUY
        if bo["close"] > bo["open"]:
            if i < trend_lb + 1: continue
            trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
            if trend_move <= trend_thresh: continue

            win = m5[i - retrace_lb:i]
            reds = [b for b in win if b["close"] < b["open"]]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            uhv_h, uhv_l = uhv["high"], uhv["low"]

            # Big spread filter
            avg_rng = sum(b["high"]-b["low"] for b in m5[max(0,i-10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue

            if bo["close"] <= uhv_h or bo["open"] > uhv_h: continue

            # Sweep check
            uhv_idx = None
            for j, b in enumerate(win):
                if b["time"] == uhv["time"]: uhv_idx = j; break
            if uhv_idx is None: continue
            swept = any(win[k]["low"] < uhv_l for k in range(uhv_idx+1, len(win)))
            if not swept: continue

            sl_price = uhv_l - sl_buf
            sl_dist = bo["close"] - sl_price
            sigs.append({"side": 1, "time": bo["time"], "entry": bo["close"],
                         "tp": tp_pts, "sl": sl_dist, "atr": 0})

        # SELL
        elif bo["close"] < bo["open"]:
            trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
            if trend_move <= trend_thresh: continue

            win = m5[i - retrace_lb:i]
            greens = [b for b in win if b["close"] > b["open"]]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            uhv_h, uhv_l = uhv["high"], uhv["low"]

            avg_rng = sum(b["high"]-b["low"] for b in m5[max(0,i-10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue

            if bo["close"] >= uhv_l or bo["open"] < uhv_l: continue

            uhv_idx = None
            for j, b in enumerate(win):
                if b["time"] == uhv["time"]: uhv_idx = j; break
            if uhv_idx is None: continue
            swept = any(win[k]["high"] > uhv_h for k in range(uhv_idx+1, len(win)))
            if not swept: continue

            sl_price = uhv_h + sl_buf
            sl_dist = sl_price - bo["close"]
            sigs.append({"side": -1, "time": bo["time"], "entry": bo["close"],
                         "tp": tp_pts, "sl": sl_dist, "atr": 0})
    return sigs

# ════════════════════════════════════════════════════════════════
# REPLAY ENGINE
# ════════════════════════════════════════════════════════════════

def replay_fixed(m1_bars, sigs, day_end):
    """Replay with fixed TP/SL using M1 bar-by-bar."""
    trades = []
    for sig in sigs:
        entry = sig["entry"]
        is_buy = sig["side"] == 1
        tp_dist = sig["tp"]
        sl_dist = sig["sl"]

        exit_price = entry
        outcome = "EOD"

        for b in m1_bars:
            if b["time"] <= sig["time"]: continue
            if b["time"] >= day_end + timedelta(hours=2):
                exit_price = b["open"]
                outcome = "EOD"
                break

            if is_buy:
                if b["low"] <= entry - sl_dist:
                    exit_price = entry - sl_dist; outcome = "SL"; break
                if b["high"] >= entry + tp_dist:
                    exit_price = entry + tp_dist; outcome = "TP"; break
            else:
                if b["high"] >= entry + sl_dist:
                    exit_price = entry + sl_dist; outcome = "SL"; break
                if b["low"] <= entry - tp_dist:
                    exit_price = entry - tp_dist; outcome = "TP"; break

        pnl_pts = (exit_price - entry) if is_buy else (entry - exit_price)
        pnl = pnl_pts * PPP
        trades.append({"time": sig["time"], "side": "BUY" if is_buy else "SELL",
                        "entry": entry, "exit": exit_price, "pnl": pnl, "outcome": outcome})
    return trades

def replay_atr_trail(m1_bars, sigs, day_end):
    """Replay with ATR trailing stop."""
    trades = []
    for sig in sigs:
        entry = sig["entry"]
        is_buy = sig["side"] == 1
        atr_v = sig["atr"]
        if atr_v <= 0: continue
        sl_price = entry - 2.0 * atr_v if is_buy else entry + 2.0 * atr_v
        peak = 0
        be_hit = False
        exit_price = entry
        outcome = "EOD"

        for b in m1_bars:
            if b["time"] <= sig["time"]: continue
            if b["time"] >= day_end + timedelta(hours=2):
                exit_price = b["open"]; outcome = "EOD"; break

            if is_buy:
                if b["high"] - entry > peak: peak = b["high"] - entry
                if not be_hit and peak >= 1.0 * atr_v:
                    be_hit = True; sl_price = max(sl_price, entry)
                trail_sl = (entry + peak) - 2.0 * atr_v
                if trail_sl > sl_price: sl_price = trail_sl
                if b["low"] <= sl_price:
                    exit_price = sl_price; outcome = "SL"; break
            else:
                if entry - b["low"] > peak: peak = entry - b["low"]
                if not be_hit and peak >= 1.0 * atr_v:
                    be_hit = True; sl_price = min(sl_price, entry)
                trail_sl = (entry - peak) + 2.0 * atr_v
                if trail_sl < sl_price: sl_price = trail_sl
                if b["high"] >= sl_price:
                    exit_price = sl_price; outcome = "SL"; break

        pnl_pts = (exit_price - entry) if is_buy else (entry - exit_price)
        pnl = pnl_pts * PPP
        trades.append({"time": sig["time"], "side": "BUY" if is_buy else "SELL",
                        "entry": entry, "exit": exit_price, "pnl": pnl, "outcome": outcome})
    return trades

# ════════════════════════════════════════════════════════════════
# MAIN: Test all EAs on last 10 days
# ════════════════════════════════════════════════════════════════

days_m1 = defaultdict(list)
for b in bars:
    days_m1[b["time"].strftime("%Y-%m-%d")].append(b)

days_m5 = defaultdict(list)
for b in m5_bars:
    days_m5[b["time"].strftime("%Y-%m-%d")].append(b)

target_days = sorted(days_m1.keys())[-10:]

eas = [
    ("S1 (M5, TP7.5, sweep+bigSpread)", "m5", "s1", "fixed"),
    ("S3 (M5, peak-TP, sweep+wick)", "m5", "s3", "fixed"),
    ("S4 (M1, TP12/SL6, ER≥0.15)", "m1", "s4_12_6", "fixed"),
    ("S4 old (M1, TP5/SL6, ER≥0.15)", "m1", "s4_5_6", "fixed"),
    ("S4b v2.00 (M1, ATR trail)", "m1", "s4b", "atr_trail"),
]

for ea_name, tf, strategy, exit_mode in eas:
    print(f"\n{'='*100}")
    print(f"  {ea_name}")
    print(f"{'='*100}")

    all_trades = []
    for day_str in target_days:
        day_start = datetime.strptime(day_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)

        if strategy == "s1":
            sigs = [s for s in detect_s1(m5_bars) if day_start <= s["time"] < day_end]
        elif strategy == "s3":
            sigs = [s for s in detect_s3(m5_bars) if day_start <= s["time"] < day_end]
        elif strategy == "s4_12_6":
            sigs = [s for s in detect_s4(bars, tp=12.0, sl=6.0) if day_start <= s["time"] < day_end]
        elif strategy == "s4_5_6":
            sigs = [s for s in detect_s4(bars, tp=5.0, sl=6.0) if day_start <= s["time"] < day_end]
        elif strategy == "s4b":
            sigs = [s for s in detect_s4(bars) if day_start <= s["time"] < day_end]
        else:
            sigs = []

        if exit_mode == "atr_trail":
            trades = replay_atr_trail(bars, sigs, day_end)
        else:
            trades = replay_fixed(bars, sigs, day_end)

        n = len(trades)
        if n == 0:
            print(f"  {day_str}  n=  0")
            continue
        w = sum(1 for t in trades if t["pnl"] > 0)
        wr = w / n
        tot = sum(t["pnl"] for t in trades)
        print(f"  {day_str}  n={n:>3}  WR={wr:>5.1%}  P&L=${tot:>+9.1f}")
        all_trades.extend(trades)

    n = len(all_trades)
    if n > 0:
        w = sum(1 for t in all_trades if t["pnl"] > 0)
        tot = sum(t["pnl"] for t in all_trades)
        avg_w = sum(t["pnl"] for t in all_trades if t["pnl"] > 0) / w if w else 0
        avg_l = sum(t["pnl"] for t in all_trades if t["pnl"] <= 0) / (n - w) if (n - w) else 0
        print(f"  {'─'*90}")
        print(f"  TOTAL: n={n:>3}  WR={w/n:>5.1%}  W=${avg_w:>5.1f}  L=${avg_l:>+6.1f}  P&L=${tot:>+9.1f}  ({tot/len(target_days):>+.1f}/day)")
    else:
        print(f"  TOTAL: n=0 — no signals found")

# Final comparison
print(f"\n{'='*100}")
print(f"  COMPARISON TABLE — Last 10 days @ {LOTS} lots")
print(f"{'='*100}")
print(f"  {'EA':<45} {'n':>4} {'WR':>6} {'W':>8} {'L':>8} {'TOTAL':>10} {'$/day':>8}")
print(f"  {'─'*90}")

for ea_name, tf, strategy, exit_mode in eas:
    all_trades = []
    for day_str in target_days:
        day_start = datetime.strptime(day_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
        if strategy == "s1":
            sigs = [s for s in detect_s1(m5_bars) if day_start <= s["time"] < day_end]
        elif strategy == "s3":
            sigs = [s for s in detect_s3(m5_bars) if day_start <= s["time"] < day_end]
        elif strategy == "s4_12_6":
            sigs = [s for s in detect_s4(bars, tp=12.0, sl=6.0) if day_start <= s["time"] < day_end]
        elif strategy == "s4_5_6":
            sigs = [s for s in detect_s4(bars, tp=5.0, sl=6.0) if day_start <= s["time"] < day_end]
        elif strategy == "s4b":
            sigs = [s for s in detect_s4(bars) if day_start <= s["time"] < day_end]
        else: sigs = []
        if exit_mode == "atr_trail":
            trades = replay_atr_trail(bars, sigs, day_end)
        else:
            trades = replay_fixed(bars, sigs, day_end)
        all_trades.extend(trades)

    n = len(all_trades)
    if n > 0:
        w = sum(1 for t in all_trades if t["pnl"] > 0)
        tot = sum(t["pnl"] for t in all_trades)
        avg_w = sum(t["pnl"] for t in all_trades if t["pnl"] > 0) / w if w else 0
        avg_l = sum(t["pnl"] for t in all_trades if t["pnl"] <= 0) / (n - w) if (n - w) else 0
        daily = tot / len(target_days)
        print(f"  {ea_name:<45} {n:>4} {w/n:>5.1%} ${avg_w:>6.1f} ${avg_l:>+6.1f} ${tot:>+9.1f} ${daily:>+6.1f}")
    else:
        print(f"  {ea_name:<45}    0     —        —        —          —        —")

print()
print("⚠️  S1 and S3 results are WITHOUT the FVG filter (not possible from M1-only data).")
print("    Real S1/S3 will have FEWER trades and potentially higher WR due to the FVG gate.")
