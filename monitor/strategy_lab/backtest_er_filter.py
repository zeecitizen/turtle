"""backtest_er_filter.py
Sweeps Kaufman Efficiency Ratio (ER) filter thresholds on S1, S3, and NSND
using real broker tick data. Tests whether adding ER >= threshold prevents
choppy-market false signals like today's 3 NSND SL hits.

ER = net price move / sum of bar-to-bar moves over a window.
0 = pure chop, 1 = perfect trend. Higher = more trending.

Usage:
    python monitor/strategy_lab/backtest_er_filter.py
"""
import sys, glob, csv, math
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON  = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1_CSV  = COMMON / "export_m1_recent.csv"
CONTRACT = 100.0

# Lot sizes matching live deployment
LOTS = {"S1": 0.06, "S3": 0.09, "NSND": 0.03}

ER_THRESHOLDS = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30]  # 0.0 = baseline (no filter)
ER_WINDOW     = 30  # bars to compute ER over (matches S4's InpERWindow)

# ════════════════════════════════════════════════════════════════
# DATA LOADERS
# ════════════════════════════════════════════════════════════════

def load_m1():
    bars = []
    with open(M1_CSV, "r") as f:
        for row in csv.DictReader(f):
            bars.append({
                "time":  datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S"),
                "open":  float(row["open"]),  "high": float(row["high"]),
                "low":   float(row["low"]),   "close": float(row["close"]),
                "vol":   int(row["tick_volume"]),
            })
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

def build_m15(m1):
    m15, bucket = [], []
    for b in m1:
        if b["time"].minute % 15 == 0 and bucket:
            m15.append({"time": bucket[0]["time"],
                        "open": bucket[0]["open"],
                        "high": max(x["high"] for x in bucket),
                        "low":  min(x["low"]  for x in bucket),
                        "close": bucket[-1]["close"],
                        "vol":  sum(x["vol"]  for x in bucket)})
            bucket = [b]
        else:
            bucket.append(b)
    if bucket:
        m15.append({"time": bucket[0]["time"],
                    "open": bucket[0]["open"],
                    "high": max(x["high"] for x in bucket),
                    "low":  min(x["low"]  for x in bucket),
                    "close": bucket[-1]["close"],
                    "vol":  sum(x["vol"]  for x in bucket)})
    return m15

# ════════════════════════════════════════════════════════════════
# ER HELPER
# ════════════════════════════════════════════════════════════════

def eff_ratio(bars, idx, window=30):
    """Kaufman Efficiency Ratio over `window` bars ending at bars[idx]."""
    start = max(0, idx - window)
    seg   = bars[start:idx + 1]
    if len(seg) < 2:
        return 0.0
    net  = abs(seg[-1]["close"] - seg[0]["close"])
    path = sum(abs(seg[k]["close"] - seg[k-1]["close"]) for k in range(1, len(seg)))
    return (net / path) if path > 0 else 0.0

def trend_hh_hl(seg, lb=30):
    if len(seg) < lb: return 0
    s = seg[-lb:]; h = lb // 2
    r, o = s[h:], s[:h]
    if max(b["high"] for b in r) > max(b["high"] for b in o) and \
       min(b["low"]  for b in r) > min(b["low"]  for b in o): return  1
    if max(b["high"] for b in r) < max(b["high"] for b in o) and \
       min(b["low"]  for b in r) < min(b["low"]  for b in o): return -1
    return 0

# ════════════════════════════════════════════════════════════════
# SIGNAL DETECTORS  (with er_min param)
# ════════════════════════════════════════════════════════════════

def detect_s3(m5, day_str, er_min=0.0,
              trend_lb=24, trend_thresh=1.0, retrace_lb=30,
              tp_peak_lb=10, sl_buf=2.0, max_upper_wick=0.35):
    sigs = []
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        # ER gate
        if er_min > 0 and eff_ratio(m5, i, ER_WINDOW) < er_min: continue

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
            if not any(win[k]["low"] < uhv["low"] for k in range(uhv_idx + 1, len(win))): continue
            peak   = max(b["high"] for b in m5[max(0, i - tp_peak_lb):i])
            tp_dist = peak - bo["close"]
            if tp_dist < 0.2: continue
            sl_dist = bo["close"] - (uhv["low"] - sl_buf)
            sigs.append({"side": 1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_dist, "sl": sl_dist})
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
            if not any(win[k]["high"] > uhv["high"] for k in range(uhv_idx + 1, len(win))): continue
            trough  = min(b["low"] for b in m5[max(0, i - tp_peak_lb):i])
            tp_dist = bo["close"] - trough
            if tp_dist < 0.2: continue
            sl_dist = (uhv["high"] + sl_buf) - bo["close"]
            sigs.append({"side": -1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_dist, "sl": sl_dist})
    return sigs


def detect_s1(m5, day_str, er_min=0.0,
              trend_lb=24, trend_thresh=2.0, retrace_lb=15,
              sl_buf=2.0, tp_pts=7.5, big_spread_mult=1.3):
    sigs = []
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        # ER gate
        if er_min > 0 and eff_ratio(m5, i, ER_WINDOW) < er_min: continue

        if bo["close"] > bo["open"]:  # BUY
            trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
            if trend_move <= trend_thresh: continue
            win  = m5[i - retrace_lb:i]
            reds = [b for b in win if b["close"] < b["open"]]
            if not reds: continue
            uhv  = max(reds, key=lambda b: b["vol"])
            avg_rng = sum(b["high"] - b["low"] for b in m5[max(0, i - 10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue
            if bo["close"] <= uhv["high"] or bo["open"] > uhv["high"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["low"] < uhv["low"] for k in range(uhv_idx + 1, len(win))): continue
            sl_dist = bo["close"] - (uhv["low"] - sl_buf)
            sigs.append({"side": 1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_pts, "sl": sl_dist})
        elif bo["close"] < bo["open"]:  # SELL
            trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
            if trend_move <= trend_thresh: continue
            win    = m5[i - retrace_lb:i]
            greens = [b for b in win if b["close"] > b["open"]]
            if not greens: continue
            uhv    = max(greens, key=lambda b: b["vol"])
            avg_rng = sum(b["high"] - b["low"] for b in m5[max(0, i - 10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"] - uhv["low"]) < big_spread_mult * avg_rng: continue
            if bo["close"] >= uhv["low"] or bo["open"] < uhv["low"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["high"] > uhv["high"] for k in range(uhv_idx + 1, len(win))): continue
            sl_dist = (uhv["high"] + sl_buf) - bo["close"]
            sigs.append({"side": -1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_pts, "sl": sl_dist})
    return sigs


def detect_nsnd(m1, m15, day_str, er_min=0.0,
                ns_max_vol_pct=0.85, sl_buf=0.30, tp_usd=12.0, lots=0.03):
    """NSND: small-spread low-volume candle after a UHV, entry on sweep+break.
       er_min applied on M1 bars at signal bar (same-TF regime check).
    """
    PPP_nsnd = lots * CONTRACT
    sigs = []

    # Build M15 FVG lookup: set of M15 bar times with a gap
    m15_fvg = set()
    for k in range(1, len(m15) - 1):
        prev, curr, nxt = m15[k-1], m15[k], m15[k+1]
        if nxt["low"] > prev["high"]:  # bullish FVG
            m15_fvg.add(curr["time"])
        if nxt["high"] < prev["low"]:  # bearish FVG
            m15_fvg.add(curr["time"])

    # Build M1 bar index lookup by time
    m1_by_time = {b["time"]: b for b in m1}

    for i in range(20, len(m1)):
        bo = m1[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        # NS/ND: small range AND low volume vs prev 2 bars
        vol_prev2 = max(m1[i-1]["vol"], m1[i-2]["vol"])
        if vol_prev2 == 0: continue
        if bo["vol"] / vol_prev2 >= ns_max_vol_pct: continue

        # ER gate on M1
        if er_min > 0 and eff_ratio(m1, i, ER_WINDOW) < er_min: continue

        # Find UHV in prior 20 bars
        window = m1[max(0, i-20):i]
        if not window: continue
        uhv = max(window, key=lambda b: b["vol"])

        # Must have M15 FVG within 30 min before signal
        cutoff = bo["time"] - timedelta(minutes=30)
        has_fvg = any(t >= cutoff and t <= bo["time"] for t in m15_fvg)
        if not has_fvg: continue

        # BUY signal: NS candle in downtrend context, entry above NS high
        if bo["close"] < bo["open"]:  # bearish NS candle = no demand
            # Sweep below NS low, then next bar closes above NS high
            if i + 1 >= len(m1): continue
            # We fire at open of next bar
            tp_pts = tp_usd / (lots * CONTRACT)
            sl_pts = sl_buf
            sigs.append({"side": 1, "fire": bo["time"] + timedelta(minutes=1),
                         "tp": tp_pts, "sl": sl_pts})
        elif bo["close"] > bo["open"]:  # bullish NS candle = no supply
            tp_pts = tp_usd / (lots * CONTRACT)
            sl_pts = sl_buf
            sigs.append({"side": -1, "fire": bo["time"] + timedelta(minutes=1),
                         "tp": tp_pts, "sl": sl_pts})
    return sigs

# ════════════════════════════════════════════════════════════════
# TICK REPLAY
# ════════════════════════════════════════════════════════════════

def replay_ticks(ticks, sigs, ppp, max_conc=3):
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] > 0:
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
            if len(units) < max_conc:
                e = ask if pend["side"] > 0 else bid
                units.append({"side": pend["side"], "e": e,
                              "tp": pend["tp"], "sl": pend["sl"], "t": t})
            pend = next(sig_iter, None)
    for u in units:  # close open at last tick
        p = ((ticks[-1]["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - ticks[-1]["ask"])) * ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done

# ════════════════════════════════════════════════════════════════
# STATS
# ════════════════════════════════════════════════════════════════

def stats(trades):
    n = len(trades)
    if not n: return None
    w   = sum(1 for t in trades if t["r"] == "W")
    wr  = w / n
    tot = sum(t["pnl"] for t in trades)
    avg_w = sum(t["pnl"] for t in trades if t["pnl"] > 0) / w if w else 0
    avg_l = sum(t["pnl"] for t in trades if t["pnl"] <= 0) / (n - w) if (n - w) else 0
    return {"n": n, "w": w, "wr": wr, "tot": tot, "avg_w": avg_w, "avg_l": avg_l}

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("Loading bars...")
    m1_all = load_m1()
    m5_all = build_m5(m1_all)
    m15_all = build_m15(m1_all)
    print(f"  {len(m1_all)} M1, {len(m5_all)} M5, {len(m15_all)} M15 bars")

    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    days, tick_cache = [], {}
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]
        if "1970" in d: continue
        ticks = load_ticks(tf)
        if len(ticks) < 500: continue
        tick_cache[d] = ticks
        days.append(d)
    days.sort()

    nd  = len(days)
    mid = nd // 2
    train_days = days[:mid]
    test_days  = days[mid:]
    print(f"\n{nd} tick days  |  TRAIN {train_days[0]}→{train_days[-1]}  |  OOS {test_days[0]}→{test_days[-1]}\n")

    # Per-EA config: (name, detector_fn, bars, lots)
    ea_cfgs = [
        ("S3",   detect_s3,   m5_all,  LOTS["S3"]),
        ("S1",   detect_s1,   m5_all,  LOTS["S1"]),
        ("NSND", detect_nsnd, m1_all,  LOTS["NSND"]),  # needs m1 + m15
    ]

    print("=" * 95)
    print(f"  {'EA':<6}  {'ER≥':<5}  {'n_all':>5}  {'WR':>6}  {'TOT':>9}  "
          f"{'$/day':>7}  {'n_oos':>5}  {'WR_OOS':>7}  {'OOS$':>9}  {'WF':>4}  {'vs base':>8}")
    print("=" * 95)

    for ea_name, detector, bars, lots in ea_cfgs:
        ppp = lots * CONTRACT
        base_tot, base_oos = None, None

        for er_thresh in ER_THRESHOLDS:
            all_trades, train_trades, oos_trades = [], [], []
            daily_pnl = {}

            for day in days:
                if day not in tick_cache: continue
                # NSND needs m1 + m15; others use m5
                if ea_name == "NSND":
                    sigs = detector(m1_all, m15_all, day, er_min=er_thresh)
                else:
                    sigs = detector(bars, day, er_min=er_thresh)

                trades = replay_ticks(tick_cache[day], sigs, ppp)
                day_pnl = sum(t["pnl"] for t in trades)
                daily_pnl[day] = day_pnl
                all_trades.extend(trades)
                (train_trades if day in train_days else oos_trades).extend(trades)

            st_all = stats(all_trades)
            st_oos = stats(oos_trades)
            if not st_all:
                print(f"  {ea_name:<6}  {er_thresh:<5.2f}  {'—':>5}  {'—':>6}  {'—':>9}  {'—':>7}  {'—':>5}  {'—':>7}  {'—':>9}  {'—':>4}  {'—':>8}")
                continue

            tot_train = sum(t["pnl"] for t in train_trades)
            tot_oos   = st_oos["tot"] if st_oos else 0
            wf_ok     = "✓" if tot_train > 0 and tot_oos > 0 else " "
            n_green   = sum(1 for d in days if daily_pnl.get(d, 0) > 0)

            if base_tot is None:
                base_tot = st_all["tot"]
                base_oos = tot_oos
                vs_base  = "  (base)"
            else:
                delta    = st_all["tot"] - base_tot
                vs_base  = f"{delta:>+8.1f}"

            label = f"≥{er_thresh:.2f}" if er_thresh > 0 else "OFF  "
            print(f"  {ea_name:<6}  {label:<5}  "
                  f"{st_all['n']:>5}  {st_all['wr']:>5.1%}  "
                  f"${st_all['tot']:>+8.1f}  ${st_all['tot']/nd:>+6.1f}  "
                  f"{(st_oos['n'] if st_oos else 0):>5}  "
                  f"{(st_oos['wr'] if st_oos else 0):>6.1%}  "
                  f"${tot_oos:>+8.1f}  {wf_ok:>4}  {vs_base}")
        print()

    print("=" * 95)
    print("""
READING THE TABLE:
  ER OFF  = no regime filter (current live behaviour)
  ER≥0.15 = skip signals when efficiency ratio < 0.15 (choppy)
  WF ✓    = both TRAIN and OOS positive (walk-forward robust)
  vs base = total P&L change vs ER OFF
  Goal: find lowest ER threshold where WF=✓ and vs-base >= 0

DEPLOYMENT RULE (same as S4):
  If a threshold passes: add InpERMin=<value> to that EA and recompile.
  Start conservative (0.15); only tighten if OOS clearly improves.
""")


if __name__ == "__main__":
    main()
