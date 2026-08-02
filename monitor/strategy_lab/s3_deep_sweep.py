"""s3_deep_sweep.py — Find the best walk-forward S3 config.

S3 = "Effort vs Result" wicking pattern:
  - Uptrend + find pivot green + reds break below it
  - Breakout candle wicks below a red's low, closes back above it
  - Higher volume than the red, small upper wick (momentum)
  
Sweep: TP (fixed vs peak-based), SL buffer, upper wick limit,
       trend threshold, retrace lookback, TP peak lookback.
"""
import sys, csv, glob
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BARS_CSV = COMMON / "ticks_for_testing.csv"
CONTRACT = 100.0
LOTS = 0.01

def load_m1():
    bars = []
    with open(BARS_CSV, "r") as f:
        for row in csv.DictReader(f):
            try: t = datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S")
            except: continue
            bars.append({"time": t, "open": float(row["open"]), "high": float(row["high"]),
                         "low": float(row["low"]), "close": float(row["close"]), "vol": int(row["tick_volume"])})
    bars.sort(key=lambda b: b["time"])
    return bars

def build_m5(m1):
    m5, bucket = [], []
    for b in m1:
        if b["time"].minute % 5 == 0 and bucket:
            m5.append({"time": bucket[0]["time"], "open": bucket[0]["open"],
                        "high": max(x["high"] for x in bucket), "low": min(x["low"] for x in bucket),
                        "close": bucket[-1]["close"], "vol": sum(x["vol"] for x in bucket)})
            bucket = [b]
        else: bucket.append(b)
    if bucket:
        m5.append({"time": bucket[0]["time"], "open": bucket[0]["open"],
                    "high": max(x["high"] for x in bucket), "low": min(x["low"] for x in bucket),
                    "close": bucket[-1]["close"], "vol": sum(x["vol"] for x in bucket)})
    return m5

def load_ticks(path):
    ticks = []
    with open(path, "r") as f:
        for row in csv.DictReader(f):
            try: t = datetime.strptime(row["ts_broker"], "%Y.%m.%d %H:%M:%S")
            except: continue
            ticks.append({"t": t, "bid": float(row["bid"]), "ask": float(row["ask"])})
    return ticks


def detect_s3(m5, day_str, trend_lb=24, trend_thresh=1.0, retrace_lb=30,
              tp_peak_lb=10, sl_buf=2.0, max_upper_wick=0.35,
              fixed_tp=None, fixed_sl=None, min_tp_dist=0.2):
    """
    If fixed_tp is set, use fixed TP instead of peak-based.
    If fixed_sl is set, use fixed SL instead of structural.
    """
    sigs = []
    fired_reds = set()

    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str:
            continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        for side in ["BUY", "SELL"]:
            if side == "BUY":
                if bo["close"] <= bo["open"]: continue
                if max_upper_wick > 0:
                    if (bo["high"] - bo["close"]) / rng > max_upper_wick: continue
                trend_move = m5[i]["close"] - m5[i - trend_lb]["close"]
                if trend_move <= trend_thresh: continue

                # Find pivot green + retracement reds
                reds, max_red_shift = [], 0
                for back_g_offset in range(2, retrace_lb + 1):
                    gi = i - back_g_offset
                    if gi < 0: break
                    g = m5[gi]
                    if g["close"] <= g["open"]: continue
                    g_l = g["low"]
                    any_broke = False
                    tmp_reds = []
                    for j_offset in range(back_g_offset - 1, 0, -1):
                        ji = i - j_offset
                        if ji < 0 or ji >= i: continue
                        r = m5[ji]
                        if r["close"] < r["open"]:
                            if r["close"] < g_l or r["low"] < g_l: any_broke = True
                            tmp_reds.append(ji)
                    if any_broke and tmp_reds:
                        reds = tmp_reds
                        max_red_shift = max(i - r for r in reds)
                        break
                if not reds: continue

                # Wicking pattern
                matching_red_t = None
                for ri in reds:
                    r_l, r_v = m5[ri]["low"], m5[ri]["vol"]
                    if bo["low"] >= r_l: continue
                    if bo["close"] <= r_l: continue
                    if bo["vol"] <= r_v: continue
                    matching_red_t = m5[ri]["time"]
                    break
                if matching_red_t is None: continue
                if matching_red_t in fired_reds: continue

                if fixed_sl is not None:
                    sl_dist = fixed_sl
                else:
                    sl_dist = bo["close"] - (bo["low"] - sl_buf)

                if fixed_tp is not None:
                    tp_dist = fixed_tp
                else:
                    tp = max(m5[j]["high"] for j in range(max(0, i - tp_peak_lb), i))
                    tp_dist = tp - bo["close"]
                    if tp_dist <= min_tp_dist: continue

                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist, "day": day_str, "red_t": matching_red_t})
                fired_reds.add(matching_red_t)

            else:  # SELL
                if bo["close"] >= bo["open"]: continue
                trend_move = m5[i - trend_lb]["close"] - m5[i]["close"]
                if trend_move <= trend_thresh: continue

                greens, max_green_shift = [], 0
                for back_r_offset in range(2, retrace_lb + 1):
                    ri = i - back_r_offset
                    if ri < 0: break
                    r = m5[ri]
                    if r["close"] >= r["open"]: continue
                    r_h = r["high"]
                    any_broke = False
                    tmp_greens = []
                    for j_offset in range(back_r_offset - 1, 0, -1):
                        ji = i - j_offset
                        if ji < 0 or ji >= i: continue
                        g = m5[ji]
                        if g["close"] > g["open"]:
                            if g["close"] > r_h or g["high"] > r_h: any_broke = True
                            tmp_greens.append(ji)
                    if any_broke and tmp_greens:
                        greens = tmp_greens
                        max_green_shift = max(i - g for g in greens)
                        break
                if not greens: continue

                matching_green_t = None
                for gi in greens:
                    g_h, g_v = m5[gi]["high"], m5[gi]["vol"]
                    if bo["high"] <= g_h: continue
                    if bo["close"] >= g_h: continue
                    if bo["vol"] <= g_v: continue
                    matching_green_t = m5[gi]["time"]
                    break
                if matching_green_t is None: continue
                if matching_green_t in fired_reds: continue

                if fixed_sl is not None:
                    sl_dist = fixed_sl
                else:
                    sl_dist = (bo["high"] + sl_buf) - bo["close"]

                if fixed_tp is not None:
                    tp_dist = fixed_tp
                else:
                    trough = min(m5[j]["low"] for j in range(max(0, i - tp_peak_lb), i))
                    tp_dist = bo["close"] - trough
                    if tp_dist <= min_tp_dist: continue

                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist, "day": day_str, "red_t": matching_green_t})
                fired_reds.add(matching_green_t)
    return sigs


def replay(ticks, sigs, lots):
    ppp = lots * CONTRACT
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] == "BUY":
                if bid <= u["e"] - u["sl"]: u["pnl"] = -u["sl"]*ppp; u["r"]="L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]: u["pnl"] = u["tp"]*ppp; u["r"]="W"; done.append(u); units.remove(u)
            else:
                if ask >= u["e"] + u["sl"]: u["pnl"] = -u["sl"]*ppp; u["r"]="L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]: u["pnl"] = u["tp"]*ppp; u["r"]="W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"] == "BUY" else bid
            units.append({**pend, "e": e})
            pend = next(sig_iter, None)
    for u in units:
        p = ((ticks[-1]["bid"]-u["e"]) if u["side"]=="BUY" else (u["e"]-ticks[-1]["ask"]))*ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done


def main():
    print("=" * 90)
    print("  S3 DEEP PARAMETER SWEEP — Finding the Best Walk-Forward Config")
    print("=" * 90)
    print()

    m1 = load_m1()
    m5 = build_m5(m1)
    print(f"  {len(m5)} M5 bars")

    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    tick_cache, days = {}, []
    for tf_path in tick_files:
        d = Path(tf_path).stem.split("_")[-1]
        tks = load_ticks(tf_path)
        if len(tks) < 500: continue
        tick_cache[d] = tks; days.append(d)
    days.sort()
    nd = len(days); mid = nd // 2
    train_days, oos_days = days[:mid], days[mid:]
    print(f"  {nd} tick days  |  TRAIN: {train_days[0]}→{train_days[-1]}  |  OOS: {oos_days[0]}→{oos_days[-1]}")
    print()

    configs = []

    # 1. Baseline (current v2.30): peak TP, structural SL, wick=0.35
    configs.append({"label": "BASELINE peak-TP SL2.0 wick.35 trend1.0",
                    "tp_peak_lb": 10, "sl_buf": 2.0, "max_upper_wick": 0.35,
                    "trend_thresh": 1.0, "retrace_lb": 30})

    # 2. Fixed TP sweep (with structural SL)
    for tp in [2.0, 3.0, 5.0, 7.5, 10.0, 12.0, 15.0]:
        for sl in [2.0, 3.0, 5.0, 7.5]:
            configs.append({"label": f"fixTP{tp}/SL{sl} wick.35 trend1.0",
                            "fixed_tp": tp, "fixed_sl": sl, "max_upper_wick": 0.35,
                            "trend_thresh": 1.0, "retrace_lb": 30})

    # 3. Upper wick sweep
    for wick in [0.20, 0.25, 0.30, 0.40, 0.50, 1.0]:
        configs.append({"label": f"peak-TP SL2.0 wick{wick:.2f} trend1.0",
                        "tp_peak_lb": 10, "sl_buf": 2.0, "max_upper_wick": wick,
                        "trend_thresh": 1.0, "retrace_lb": 30})

    # 4. Trend threshold sweep
    for thresh in [0.5, 1.0, 1.5, 2.0, 3.0]:
        configs.append({"label": f"peak-TP SL2.0 wick.35 trend{thresh}",
                        "tp_peak_lb": 10, "sl_buf": 2.0, "max_upper_wick": 0.35,
                        "trend_thresh": thresh, "retrace_lb": 30})

    # 5. SL buffer sweep (peak TP)
    for sl_buf in [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
        configs.append({"label": f"peak-TP SL{sl_buf} wick.35 trend1.0",
                        "tp_peak_lb": 10, "sl_buf": sl_buf, "max_upper_wick": 0.35,
                        "trend_thresh": 1.0, "retrace_lb": 30})

    # 6. TP peak lookback sweep
    for pk_lb in [5, 10, 15, 20, 30]:
        configs.append({"label": f"peak-TP(lb{pk_lb}) SL2.0 wick.35 trend1.0",
                        "tp_peak_lb": pk_lb, "sl_buf": 2.0, "max_upper_wick": 0.35,
                        "trend_thresh": 1.0, "retrace_lb": 30})

    # 7. Retrace lookback sweep
    for rlb in [15, 20, 25, 30, 40]:
        configs.append({"label": f"peak-TP SL2.0 wick.35 trend1.0 retrace{rlb}",
                        "tp_peak_lb": 10, "sl_buf": 2.0, "max_upper_wick": 0.35,
                        "trend_thresh": 1.0, "retrace_lb": rlb})

    # 8. Best fixed TP combos with different wick/trend
    for tp in [3.0, 5.0, 7.5]:
        for sl in [3.0, 5.0, 7.5]:
            for wick in [0.35, 0.50, 1.0]:
                configs.append({"label": f"fixTP{tp}/SL{sl} wick{wick:.2f} trend1.0",
                                "fixed_tp": tp, "fixed_sl": sl, "max_upper_wick": wick,
                                "trend_thresh": 1.0, "retrace_lb": 30})

    total = len(configs)
    print(f"  Running {total} configurations...")
    print()

    results = []
    for ci, cfg in enumerate(configs):
        all_trades, train_trades, oos_trades = [], [], []
        for day in days:
            sigs = detect_s3(m5, day,
                             trend_thresh=cfg.get("trend_thresh", 1.0),
                             retrace_lb=cfg.get("retrace_lb", 30),
                             tp_peak_lb=cfg.get("tp_peak_lb", 10),
                             sl_buf=cfg.get("sl_buf", 2.0),
                             max_upper_wick=cfg.get("max_upper_wick", 0.35),
                             fixed_tp=cfg.get("fixed_tp"),
                             fixed_sl=cfg.get("fixed_sl"))
            trades = replay(tick_cache[day], sigs, LOTS)
            all_trades.extend(trades)
            (train_trades if day in train_days else oos_trades).extend(trades)

        n = len(all_trades)
        if n == 0:
            results.append({**cfg, "n": 0, "wr": 0, "total": 0, "train": 0, "oos": 0,
                           "ev": 0, "wf": False, "dd": 0, "buy_pnl": 0, "sell_pnl": 0})
            continue

        w = sum(1 for t in all_trades if t["r"] == "W")
        tot = sum(t["pnl"] for t in all_trades)
        tot_train = sum(t["pnl"] for t in train_trades)
        tot_oos = sum(t["pnl"] for t in oos_trades)
        buys = [t for t in all_trades if t["side"] == "BUY"]
        sells = [t for t in all_trades if t["side"] == "SELL"]

        eq, pk, dd = 0, 0, 0
        for t in sorted(all_trades, key=lambda x: x["fire"]):
            eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)

        green_d = 0
        dpnl = {}
        for t in all_trades:
            dpnl[t["day"]] = dpnl.get(t["day"], 0) + t["pnl"]
        green_d = sum(1 for v in dpnl.values() if v > 0)

        results.append({**cfg, "n": n, "wr": w/n*100, "total": tot, "train": tot_train,
                       "oos": tot_oos, "ev": tot/n, "wf": tot_train > 0 and tot_oos > 0,
                       "dd": dd, "buy_pnl": sum(t["pnl"] for t in buys),
                       "sell_pnl": sum(t["pnl"] for t in sells), "green": green_d,
                       "red": len(dpnl) - green_d})

        if (ci + 1) % 20 == 0:
            print(f"    ... {ci+1}/{total} done")

    # Sort by OOS
    results.sort(key=lambda r: r["oos"], reverse=True)

    print()
    print("=" * 140)
    print(f"  {'Config':<50}  {'n':>4}  {'WR':>5}  {'Total':>9}  {'TRAIN':>9}  {'OOS':>9}  {'EV':>7}  {'DD':>7}  {'BUY':>8}  {'SELL':>8}  {'G/R':>5}  {'WF':>3}")
    print("=" * 140)
    for r in results:
        wf = "✅" if r["wf"] else "❌"
        print(f"  {r['label']:<50}  {r['n']:>4}  {r['wr']:>4.1f}%  ${r['total']:>+8.1f}  ${r['train']:>+8.1f}  ${r['oos']:>+8.1f}  ${r['ev']:>+6.2f}  ${r['dd']:>6.1f}  ${r['buy_pnl']:>+7.1f}  ${r['sell_pnl']:>+7.1f}  {r['green']}/{r['red']}  {wf}")

    print()
    print("=" * 90)
    print("  TOP 10 BY OOS P&L (walk-forward positive only)")
    print("=" * 90)
    wf_results = [r for r in results if r["wf"]]
    for i, r in enumerate(wf_results[:10]):
        print(f"  #{i+1}: {r['label']}")
        print(f"      n={r['n']}  WR={r['wr']:.1f}%  Total=${r['total']:+.1f}  Train=${r['train']:+.1f}  OOS=${r['oos']:+.1f}")
        print(f"      DD=${r['dd']:.1f}  BUY=${r['buy_pnl']:+.1f}  SELL=${r['sell_pnl']:+.1f}  Green/Red={r['green']}/{r['red']}")
        print()

if __name__ == "__main__":
    main()
