"""backtest_all_eas_ticks.py — Tick-based backtest of ALL EAs on XAUUSD.

Uses real broker tick data for precise entry/exit simulation.
Tests: S1, S3, S4 (TP12/SL6), S4 old (TP5/SL6), S4b v2.00 (ATR trail)
"""
import sys, glob, csv
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
M1_CSV = COMMON / "export_m1_recent.csv"
LOTS = 0.10
CONTRACT = 100.0
PPP = LOTS * CONTRACT

# ════════════════════════════════════════════════════════════════
# LOAD DATA
# ════════════════════════════════════════════════════════════════

def load_m1():
    bars = []
    with open(M1_CSV, "r") as f:
        for row in csv.DictReader(f):
            bars.append({
                "time": datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S"),
                "open": float(row["open"]), "high": float(row["high"]),
                "low": float(row["low"]), "close": float(row["close"]),
                "vol": int(row["tick_volume"]),
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

def build_m5(m1_bars):
    m5 = []
    bucket = []
    for b in m1_bars:
        if b["time"].minute % 5 == 0 and bucket:
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
        m5.append({"time": bucket[0]["time"], "open": bucket[0]["open"],
                    "high": max(x["high"] for x in bucket), "low": min(x["low"] for x in bucket),
                    "close": bucket[-1]["close"], "vol": sum(x["vol"] for x in bucket)})
    return m5

# ════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════

def trend_hh_hl(seg, lb=30):
    if len(seg) < lb: return 0
    s = seg[-lb:]; h = lb // 2
    r, o = s[h:], s[:h]
    if max(b["high"] for b in r) > max(b["high"] for b in o) and \
       min(b["low"] for b in r) > min(b["low"] for b in o): return 1
    if max(b["high"] for b in r) < max(b["high"] for b in o) and \
       min(b["low"] for b in r) < min(b["low"] for b in o): return -1
    return 0

def eff_ratio(seg, lb=30):
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
# DETECTORS
# ════════════════════════════════════════════════════════════════

def detect_s4(m1, day_str, tp=5.0, sl=6.0, er_min=0.15, uhv_rng_min=1.0, compute_atr=False):
    sigs = []
    for i in range(44, len(m1)):
        bo = m1[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < 0.55: continue
        win = m1[i-12:i]
        avgbody = sum(abs(b["close"]-b["open"]) for b in win) / len(win)
        if body < avgbody: continue
        tw = m1[i-30:i]
        if er_min > 0 and eff_ratio(tw) < er_min: continue
        td = trend_hh_hl(tw)
        if td == 0: continue
        atr_v = calc_atr(m1[:i+1]) if compute_atr else 0

        if bo["close"] > bo["open"] and td == 1:
            reds = [b for b in win if b["close"] < b["open"] and (b["high"]-b["low"]) >= uhv_rng_min]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] > uhv["high"] and bo["open"] <= uhv["high"]:
                sigs.append({"side": 1, "fire": bo["time"] + timedelta(minutes=1),
                             "tp": tp, "sl": sl, "atr": atr_v})
                continue
        if bo["close"] < bo["open"] and td == -1:
            greens = [b for b in win if b["close"] > b["open"] and (b["high"]-b["low"]) >= uhv_rng_min]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            if bo["vol"] < uhv["vol"] and bo["close"] < uhv["low"] and bo["open"] >= uhv["low"]:
                sigs.append({"side": -1, "fire": bo["time"] + timedelta(minutes=1),
                             "tp": tp, "sl": sl, "atr": atr_v})
    return sigs

def detect_s1(m5, day_str, trend_lb=24, trend_thresh=2.0, retrace_lb=15,
              sl_buf=2.0, tp_pts=7.5, big_spread_mult=1.3):
    sigs = []
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        if bo["close"] > bo["open"]:  # BUY
            upper_wick = bo["high"] - bo["close"]
            trend_move = m5[i]["close"] - m5[i-trend_lb]["close"]
            if trend_move <= trend_thresh: continue
            win = m5[i-retrace_lb:i]
            reds = [b for b in win if b["close"] < b["open"]]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            # Big spread
            avg_rng = sum(b["high"]-b["low"] for b in m5[max(0,i-10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"]-uhv["low"]) < big_spread_mult * avg_rng: continue
            if bo["close"] <= uhv["high"] or bo["open"] > uhv["high"]: continue
            # Sweep
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["low"] < uhv["low"] for k in range(uhv_idx+1, len(win))): continue
            sl_dist = bo["close"] - (uhv["low"] - sl_buf)
            sigs.append({"side": 1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_pts, "sl": sl_dist, "atr": 0})

        elif bo["close"] < bo["open"]:  # SELL
            trend_move = m5[i-trend_lb]["close"] - m5[i]["close"]
            if trend_move <= trend_thresh: continue
            win = m5[i-retrace_lb:i]
            greens = [b for b in win if b["close"] > b["open"]]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            avg_rng = sum(b["high"]-b["low"] for b in m5[max(0,i-10):i]) / min(10, i)
            if avg_rng > 0 and (uhv["high"]-uhv["low"]) < big_spread_mult * avg_rng: continue
            if bo["close"] >= uhv["low"] or bo["open"] < uhv["low"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["high"] > uhv["high"] for k in range(uhv_idx+1, len(win))): continue
            sl_dist = (uhv["high"] + sl_buf) - bo["close"]
            sigs.append({"side": -1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_pts, "sl": sl_dist, "atr": 0})
    return sigs

def detect_s3(m5, day_str, trend_lb=24, trend_thresh=1.0, retrace_lb=30,
              tp_peak_lb=10, sl_buf=2.0, max_upper_wick=0.35):
    sigs = []
    for i in range(trend_lb + retrace_lb + 2, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue

        if bo["close"] > bo["open"]:  # BUY
            upper_wick = bo["high"] - bo["close"]
            if max_upper_wick > 0 and rng > 0 and upper_wick / rng > max_upper_wick: continue
            trend_move = m5[i]["close"] - m5[i-trend_lb]["close"]
            if trend_move <= trend_thresh: continue
            win = m5[i-retrace_lb:i]
            reds = [b for b in win if b["close"] < b["open"]]
            if not reds: continue
            uhv = max(reds, key=lambda b: b["vol"])
            if bo["close"] <= uhv["high"] or bo["open"] > uhv["high"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["low"] < uhv["low"] for k in range(uhv_idx+1, len(win))): continue
            peak = max(b["high"] for b in m5[max(0,i-tp_peak_lb):i])
            tp_dist = peak - bo["close"]
            if tp_dist < 0.2: continue
            sl_dist = bo["close"] - (uhv["low"] - sl_buf)
            sigs.append({"side": 1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_dist, "sl": sl_dist, "atr": 0})

        elif bo["close"] < bo["open"]:  # SELL
            trend_move = m5[i-trend_lb]["close"] - m5[i]["close"]
            if trend_move <= trend_thresh: continue
            win = m5[i-retrace_lb:i]
            greens = [b for b in win if b["close"] > b["open"]]
            if not greens: continue
            uhv = max(greens, key=lambda b: b["vol"])
            if bo["close"] >= uhv["low"] or bo["open"] < uhv["low"]: continue
            uhv_idx = next((j for j, b in enumerate(win) if b["time"] == uhv["time"]), None)
            if uhv_idx is None: continue
            if not any(win[k]["high"] > uhv["high"] for k in range(uhv_idx+1, len(win))): continue
            trough = min(b["low"] for b in m5[max(0,i-tp_peak_lb):i])
            tp_dist = bo["close"] - trough
            if tp_dist < 0.2: continue
            sl_dist = (uhv["high"] + sl_buf) - bo["close"]
            sigs.append({"side": -1, "fire": bo["time"] + timedelta(minutes=5),
                         "tp": tp_dist, "sl": sl_dist, "atr": 0})
    return sigs

# ════════════════════════════════════════════════════════════════
# TICK REPLAY ENGINE
# ════════════════════════════════════════════════════════════════

def replay_ticks_fixed(ticks, sigs, max_conc=3):
    done, units = [], []
    it = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(it, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] > 0:
                if bid <= u["e"] - u["sl"]:
                    u["pnl"] = -u["sl"] * PPP; u["r"] = "L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]:
                    u["pnl"] = u["tp"] * PPP; u["r"] = "W"; done.append(u); units.remove(u)
            else:
                if ask >= u["e"] + u["sl"]:
                    u["pnl"] = -u["sl"] * PPP; u["r"] = "L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]:
                    u["pnl"] = u["tp"] * PPP; u["r"] = "W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            if len(units) < max_conc:
                e = ask if pend["side"] > 0 else bid
                units.append({"side": pend["side"], "e": e, "tp": pend["tp"], "sl": pend["sl"], "t": t})
            pend = next(it, None)
    if ticks:
        for u in units:
            p = ((ticks[-1]["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - ticks[-1]["ask"])) * PPP
            u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done

def replay_ticks_atr(ticks, sigs, max_conc=3):
    done, units = [], []
    it = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(it, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            atr_v = u["atr_val"]
            if u["side"] > 0:
                cp = bid - u["e"]
                if cp > u["peak"]: u["peak"] = cp
                if not u["be"] and u["peak"] >= 1.0 * atr_v:
                    u["be"] = True; u["sl_p"] = max(u["sl_p"], u["e"])
                trail = (u["e"] + u["peak"]) - 2.0 * atr_v
                if trail > u["sl_p"]: u["sl_p"] = trail
                if bid <= u["sl_p"]:
                    u["pnl"] = (u["sl_p"] - u["e"]) * PPP
                    u["r"] = "W" if u["pnl"] > 0 else "L"
                    done.append(u); units.remove(u)
            else:
                cp = u["e"] - ask
                if cp > u["peak"]: u["peak"] = cp
                if not u["be"] and u["peak"] >= 1.0 * atr_v:
                    u["be"] = True; u["sl_p"] = min(u["sl_p"], u["e"])
                trail = (u["e"] - u["peak"]) + 2.0 * atr_v
                if trail < u["sl_p"]: u["sl_p"] = trail
                if ask >= u["sl_p"]:
                    u["pnl"] = (u["e"] - u["sl_p"]) * PPP
                    u["r"] = "W" if u["pnl"] > 0 else "L"
                    done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            if len(units) < max_conc:
                e = ask if pend["side"] > 0 else bid
                atr_v = pend["atr"]
                sl_p = e - 2.0 * atr_v if pend["side"] > 0 else e + 2.0 * atr_v
                units.append({"side": pend["side"], "e": e, "atr_val": atr_v,
                              "sl_p": sl_p, "peak": 0, "be": False, "t": t})
            pend = next(it, None)
    if ticks:
        for u in units:
            p = ((ticks[-1]["bid"] - u["e"]) if u["side"] > 0 else (u["e"] - ticks[-1]["ask"])) * PPP
            u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def stat(trades, nd):
    n = len(trades)
    if not n: return 0, 0, 0, 0
    w = sum(1 for t in trades if t.get("r") == "W")
    wr = w / n
    tot = sum(t["pnl"] for t in trades)
    avg_w = sum(t["pnl"] for t in trades if t["pnl"] > 0) / w if w else 0
    avg_l = sum(t["pnl"] for t in trades if t["pnl"] <= 0) / (n - w) if (n - w) else 0
    return wr, tot, avg_w, avg_l

def main():
    print("Loading M1 bars...")
    m1 = load_m1()
    m5 = build_m5(m1)
    print(f"  {len(m1)} M1 bars, {len(m5)} M5 bars")

    # Find tick files
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    days = []
    tick_cache = {}
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]
        ticks = load_ticks(tf)
        if len(ticks) < 100: continue
        tick_cache[d] = ticks
        days.append(d)
        print(f"  {d}: {len(ticks):,} ticks")

    nd = len(days)
    mid = nd // 2
    print(f"\n{nd} tick days loaded. Train={mid}, Test={nd-mid}")

    # EA configs
    configs = [
        ("S1 (M5, TP7.5, sweep+bigSpread)", "s1", "fixed"),
        ("S3 (M5, peak-TP, sweep+wick)", "s3", "fixed"),
        ("S4 old (M1, TP5/SL6)", "s4_5_6", "fixed"),
        ("S4 (M1, TP12/SL6)", "s4_12_6", "fixed"),
        ("S4b v2.00 (M1, ATR trail)", "s4b", "atr"),
    ]

    results = []

    for ea_name, strategy, exit_mode in configs:
        print(f"\n{'='*100}")
        print(f"  {ea_name}")
        print(f"{'='*100}")

        train_trades, test_trades, all_trades = [], [], []
        for k, d in enumerate(days):
            if strategy == "s1":
                sigs = detect_s1(m5, d)
            elif strategy == "s3":
                sigs = detect_s3(m5, d)
            elif strategy == "s4_5_6":
                sigs = detect_s4(m1, d, tp=5.0, sl=6.0)
            elif strategy == "s4_12_6":
                sigs = detect_s4(m1, d, tp=12.0, sl=6.0)
            elif strategy == "s4b":
                sigs = detect_s4(m1, d, compute_atr=True)
            else:
                sigs = []

            if exit_mode == "atr":
                trades = replay_ticks_atr(tick_cache[d], sigs)
            else:
                trades = replay_ticks_fixed(tick_cache[d], sigs)

            n = len(trades)
            w = sum(1 for t in trades if t.get("r") == "W")
            tot = sum(t["pnl"] for t in trades)
            wr = w/n if n else 0
            split = "TRAIN" if k < mid else "OOS"
            print(f"  {d} [{split}]  n={n:>3}  WR={wr:>5.1%}  P&L=${tot:>+9.1f}")
            all_trades.extend(trades)
            (train_trades if k < mid else test_trades).extend(trades)

        wr_all, tot_all, avg_w, avg_l = stat(all_trades, nd)
        wr_oos, tot_oos, _, _ = stat(test_trades, nd - mid)
        tot_train = sum(t["pnl"] for t in train_trades)
        wf = "✓" if tot_train > 0 and tot_oos > 0 else " "

        print(f"  {'─'*90}")
        print(f"    ALL: n={len(all_trades):>4}  WR={wr_all:>5.1%}  W=${avg_w:>5.1f}  L=${avg_l:>+6.1f}  P&L=${tot_all:>+9.1f}")
        print(f"    OOS: n={len(test_trades):>4}  WR={wr_oos:>5.1%}  P&L=${tot_oos:>+9.1f}")
        print(f"    WF: train=${tot_train:>+.0f} test=${tot_oos:>+.0f} [{wf}]")

        results.append({"name": ea_name, "n": len(all_trades), "wr": wr_all,
                         "avg_w": avg_w, "avg_l": avg_l, "total": tot_all,
                         "oos": tot_oos, "train": tot_train, "wf": wf,
                         "daily": tot_all / nd, "wr_oos": wr_oos})

    # Final comparison
    print(f"\n{'='*100}")
    print(f"  TICK-BASED COMPARISON — {nd} days @ {LOTS} lots")
    print(f"{'='*100}")
    print(f"  {'EA':<45} {'n':>4} {'WR':>6} {'WR_OOS':>7} {'W':>7} {'L':>7} {'TOTAL':>9} {'OOS':>9} {'$/day':>7} {'WF':>3}")
    print(f"  {'─'*100}")
    results.sort(key=lambda r: -r["total"])
    for r in results:
        print(f"  {r['name']:<45} {r['n']:>4} {r['wr']:>5.1%} {r['wr_oos']:>6.1%} ${r['avg_w']:>5.0f} ${r['avg_l']:>+5.0f} ${r['total']:>+8.0f} ${r['oos']:>+8.0f} ${r['daily']:>+5.0f}  {r['wf']}")

    print(f"\n⚠️  S1/S3 are WITHOUT the FVG filter — real results have fewer trades + higher WR.")

if __name__ == "__main__":
    main()
