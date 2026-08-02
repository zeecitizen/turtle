"""bias_check.py — Check if S1 and S3 are truly buy-biased on real tick data.
Runs both detectors on bars_for_gravity.csv and counts BUY vs SELL signals,
win rates per direction, and P&L per direction on real ticks.
"""
import sys, csv, glob
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON   = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BARS_CSV = COMMON / "bars_for_gravity.csv"
CONTRACT = 100.0

# ════════════════════════════════════════════════════════════════
# LOAD DATA
# ════════════════════════════════════════════════════════════════

def load_bars():
    bars = []
    with open(BARS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S")
            except (ValueError, KeyError):
                try:
                    t = datetime.strptime(row["time_iso"], "%Y-%m-%d %H:%M:%S")
                except:
                    continue
            bars.append({
                "time":  t,
                "open":  float(row["open"]),
                "high":  float(row["high"]),
                "low":   float(row["low"]),
                "close": float(row["close"]),
                "vol":   int(row["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars

def load_ticks(path):
    ticks = []
    with open(path, "r") as f:
        for row in csv.DictReader(f):
            try:
                t = datetime.strptime(row["ts_broker"], "%Y.%m.%d %H:%M:%S")
            except ValueError:
                continue
            ticks.append({"t": t, "bid": float(row["bid"]), "ask": float(row["ask"])})
    return ticks

def build_m5(m1):
    m5, bucket = [], []
    for b in m1:
        if b["time"].minute % 5 == 0 and bucket:
            m5.append({"time": bucket[0]["time"],
                       "open": bucket[0]["open"],
                       "high": max(x["high"] for x in bucket),
                       "low":  min(x["low"]  for x in bucket),
                       "close": bucket[-1]["close"],
                       "vol":  sum(x["vol"]  for x in bucket)})
            bucket = [b]
        else:
            bucket.append(b)
    if bucket:
        m5.append({"time": bucket[0]["time"],
                   "open": bucket[0]["open"],
                   "high": max(x["high"] for x in bucket),
                   "low":  min(x["low"]  for x in bucket),
                   "close": bucket[-1]["close"],
                   "vol":  sum(x["vol"]  for x in bucket)})
    return m5

# ════════════════════════════════════════════════════════════════
# SIGNAL DETECTORS
# ════════════════════════════════════════════════════════════════

def detect_s1(m5, trend_lb=24, trend_thresh=2.0, retrace_lb=15,
              sl_buf=2.0, tp_pts=7.5, big_spread_mult=1.3):
    sigs = []
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        if bo["close"] > bo["open"]:  # BUY
            trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
            if trend_move <= trend_thresh: continue
            win  = m5[i - retrace_lb:i]
            reds = [b for b in win if b["close"] < b["open"]]
            if not reds: continue
            uhv  = max(reds, key=lambda b: b["vol"])
            avg_rng = sum(b["high"] - b["low"] for b in m5[max(0, i-10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue
            if bo["close"] <= uhv["high"] or bo["open"] > uhv["high"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["low"] < uhv["low"] for k in range(uhv_idx+1, len(win))): continue
            sl_dist = bo["close"] - (uhv["low"] - sl_buf)
            sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_pts, "sl": sl_dist, "day": bo["time"].strftime("%Y-%m-%d")})

        elif bo["close"] < bo["open"]:  # SELL
            trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
            if trend_move <= trend_thresh: continue
            win    = m5[i - retrace_lb:i]
            greens = [b for b in win if b["close"] > b["open"]]
            if not greens: continue
            uhv    = max(greens, key=lambda b: b["vol"])
            avg_rng = sum(b["high"] - b["low"] for b in m5[max(0, i-10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue
            if bo["close"] >= uhv["low"] or bo["open"] < uhv["low"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["high"] > uhv["high"] for k in range(uhv_idx+1, len(win))): continue
            sl_dist = (uhv["high"] + sl_buf) - bo["close"]
            sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_pts, "sl": sl_dist, "day": bo["time"].strftime("%Y-%m-%d")})
    return sigs


def detect_s3(m5, trend_lb=24, trend_thresh=1.0, retrace_lb=30,
              tp_peak_lb=10, sl_buf=2.0, max_upper_wick=0.35):
    sigs = []
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        if bo["close"] > bo["open"]:  # BUY
            upper_wick = bo["high"] - bo["close"]
            if max_upper_wick > 0 and rng > 0 and upper_wick / rng > max_upper_wick: continue
            trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
            if trend_move <= trend_thresh: continue
            win  = m5[i - retrace_lb:i]
            reds = [b for b in win if b["close"] < b["open"]]
            if not reds: continue
            uhv  = max(reds, key=lambda b: b["vol"])
            if bo["close"] <= uhv["high"] or bo["open"] > uhv["high"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["low"] < uhv["low"] for k in range(uhv_idx+1, len(win))): continue
            peak    = max(b["high"] for b in m5[max(0, i - tp_peak_lb):i])
            tp_dist = peak - bo["close"]
            if tp_dist < 0.2: continue
            sl_dist = bo["close"] - (uhv["low"] - sl_buf)
            sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_dist, "sl": sl_dist, "day": bo["time"].strftime("%Y-%m-%d")})

        elif bo["close"] < bo["open"]:  # SELL
            trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
            if trend_move <= trend_thresh: continue
            win    = m5[i - retrace_lb:i]
            greens = [b for b in win if b["close"] > b["open"]]
            if not greens: continue
            uhv    = max(greens, key=lambda b: b["vol"])
            if bo["close"] >= uhv["low"] or bo["open"] < uhv["low"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["high"] > uhv["high"] for k in range(uhv_idx+1, len(win))): continue
            trough  = min(b["low"] for b in m5[max(0, i - tp_peak_lb):i])
            tp_dist = bo["close"] - trough
            if tp_dist < 0.2: continue
            sl_dist = (uhv["high"] + sl_buf) - bo["close"]
            sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_dist, "sl": sl_dist, "day": bo["time"].strftime("%Y-%m-%d")})
    return sigs

# ════════════════════════════════════════════════════════════════
# TICK REPLAY
# ════════════════════════════════════════════════════════════════

def replay(ticks, sigs, lots=0.10):
    ppp  = lots * CONTRACT
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] == "BUY":
                if bid <= u["e"] - u["sl"]:
                    u["pnl"] = -u["sl"] * ppp; u["r"] = "L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]:
                    u["pnl"] =  u["tp"] * ppp; u["r"] = "W"; done.append(u); units.remove(u)
            else:
                if ask >= u["e"] + u["sl"]:
                    u["pnl"] = -u["sl"] * ppp; u["r"] = "L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]:
                    u["pnl"] =  u["tp"] * ppp; u["r"] = "W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            if len(units) < 3:
                e = ask if pend["side"] == "BUY" else bid
                units.append({**pend, "e": e})
            pend = next(sig_iter, None)
    for u in units:
        p = ((ticks[-1]["bid"] - u["e"]) if u["side"] == "BUY" else (u["e"] - ticks[-1]["ask"])) * ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done

def dir_stats(trades, side):
    t = [x for x in trades if x["side"] == side]
    n = len(t)
    if not n: return n, 0, 0, 0
    w   = sum(1 for x in t if x["r"] == "W")
    tot = sum(x["pnl"] for x in t)
    ev  = tot / n
    return n, w, w/n*100, tot

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("Loading bars from bars_for_gravity.csv ...")
    m1 = load_bars()
    m5 = build_m5(m1)
    print(f"  {len(m1)} M1 bars  |  {len(m5)} M5 bars")
    print(f"  Range: {m1[0]['time'].date()} → {m1[-1]['time'].date()}")

    # Load all tick files
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    tick_cache, days = {}, []
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]
        ticks = load_ticks(tf)
        if len(ticks) < 500: continue
        tick_cache[d] = ticks
        days.append(d)
    print(f"  {len(days)} tick days: {days[0]} → {days[-1]}\n")

    for ea_name, detector in [("S1", detect_s1), ("S3", detect_s3)]:
        sigs = detector(m5)
        buys  = [s for s in sigs if s["side"] == "BUY"]
        sells = [s for s in sigs if s["side"] == "SELL"]

        print(f"{'='*70}")
        print(f"  {ea_name}  —  {len(sigs)} total signals")
        print(f"{'='*70}")
        print(f"  BUY  signals: {len(buys):>4}  ({len(buys)/len(sigs)*100:.1f}%)")
        print(f"  SELL signals: {len(sells):>4}  ({len(sells)/len(sigs)*100:.1f}%)")

        # Replay on ticks
        all_trades = []
        for day in days:
            if day not in tick_cache: continue
            day_sigs = [s for s in sigs if s["day"] == day]
            trades   = replay(tick_cache[day], day_sigs)
            all_trades.extend(trades)

        if not all_trades:
            print("  No trades matched to tick days.")
            print()
            continue

        n_b, w_b, wr_b, tot_b = dir_stats(all_trades, "BUY")
        n_s, w_s, wr_s, tot_s = dir_stats(all_trades, "SELL")
        n_tot = len(all_trades)
        tot   = sum(x["pnl"] for x in all_trades)

        print(f"\n  {'Direction':<8} {'Signals':>8} {'Replayed':>9} {'WR':>7} {'Total P&L':>11} {'EV/trade':>10}")
        print(f"  {'-'*58}")
        print(f"  {'BUY':<8} {len(buys):>8} {n_b:>9} {wr_b:>6.1f}% ${tot_b:>+10.2f} ${tot_b/n_b if n_b else 0:>+9.2f}")
        print(f"  {'SELL':<8} {len(sells):>8} {n_s:>9} {wr_s:>6.1f}% ${tot_s:>+10.2f} ${tot_s/n_s if n_s else 0:>+9.2f}")
        print(f"  {'TOTAL':<8} {len(sigs):>8} {n_tot:>9}         ${tot:>+10.2f}")

        # Count by day
        print(f"\n  Daily signal direction breakdown:")
        day_buys  = defaultdict(int)
        day_sells = defaultdict(int)
        for s in sigs:
            if s["day"] in days:
                (day_buys if s["side"]=="BUY" else day_sells)[s["day"]] += 1
        print(f"  {'Date':<12} {'BUY':>5} {'SELL':>6}  {'Bias'}")
        print(f"  {'-'*35}")
        for d in sorted(set(list(day_buys.keys())+list(day_sells.keys()))):
            b = day_buys[d]; s = day_sells[d]
            bias = "BUY-biased" if b > s*1.5 else "SELL-biased" if s > b*1.5 else "BALANCED"
            print(f"  {d}  {b:>5}  {s:>6}  {bias}")
        print()

    print("NOTE: This backtest does NOT include the live EA's M5 FVG filter,")
    print("so signal counts are higher than live. But direction BIAS is accurate.")

if __name__ == "__main__":
    main()
