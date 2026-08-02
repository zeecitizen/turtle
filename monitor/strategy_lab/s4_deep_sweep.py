"""s4_deep_sweep.py — Exhaustive S4 parameter sweep to find the winning config.

Tests:
  1. TP sweep: $1, $2, $3, $4, $5, $6, $7.5, $10, $12 (with SL $3, $4, $5, $6)
  2. Regime filter: ER threshold 0, 0.10, 0.15, 0.20, 0.25
  3. Timeframe: M1 vs M5
  4. Trend: same-TF HH/HL vs M5-with-implied-H1-trend (close[0]-close[60] > threshold)
  5. SL mode: fixed vs structural (UHV candle's low - buffer)

All combinations tested on 18 real tick days with walk-forward split.
"""
import sys, csv, glob
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BARS_CSV = COMMON / "ticks_for_testing.csv"
CONTRACT = 100.0
LOTS = 0.01

# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════

def load_m1():
    bars = []
    with open(BARS_CSV, "r") as f:
        for row in csv.DictReader(f):
            try:
                t = datetime.strptime(row["time_iso"], "%Y.%m.%d %H:%M:%S")
            except: continue
            bars.append({"time": t, "open": float(row["open"]), "high": float(row["high"]),
                         "low": float(row["low"]), "close": float(row["close"]), "vol": int(row["tick_volume"])})
    bars.sort(key=lambda b: b["time"])
    return bars

def build_tf(m1, minutes):
    if minutes == 1: return m1
    out, bucket = [], []
    for b in m1:
        if b["time"].minute % minutes == 0 and bucket:
            out.append({"time": bucket[0]["time"], "open": bucket[0]["open"],
                        "high": max(x["high"] for x in bucket), "low": min(x["low"] for x in bucket),
                        "close": bucket[-1]["close"], "vol": sum(x["vol"] for x in bucket)})
            bucket = [b]
        else: bucket.append(b)
    if bucket:
        out.append({"time": bucket[0]["time"], "open": bucket[0]["open"],
                    "high": max(x["high"] for x in bucket), "low": min(x["low"] for x in bucket),
                    "close": bucket[-1]["close"], "vol": sum(x["vol"] for x in bucket)})
    return out

def load_ticks(path):
    ticks = []
    with open(path, "r") as f:
        for row in csv.DictReader(f):
            try: t = datetime.strptime(row["ts_broker"], "%Y.%m.%d %H:%M:%S")
            except: continue
            ticks.append({"t": t, "bid": float(row["bid"]), "ask": float(row["ask"])})
    return ticks


# ═══════════════════════════════════════════════════════════════
# S4 DETECTOR — configurable
# ═══════════════════════════════════════════════════════════════

def detect_s4(bars, day_str, tp_pts, sl_pts, sl_mode="fixed",
              trend_lb=30, retrace_lb=12, mom_body_frac=0.55,
              er_min=0.15, trend_mode="hhhl",
              h1_trend_bars=60, h1_trend_thresh=2.0):
    """
    trend_mode: "hhhl" = same-TF HH/HL, "h1" = use close[0]-close[h1_trend_bars] for multi-TF
    sl_mode: "fixed" = fixed pts, "structural" = UHV low - buffer
    """
    sigs = []
    fired_bars = set()
    half = trend_lb // 2

    for i in range(max(trend_lb, h1_trend_bars) + 2, len(bars)):
        bo = bars[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str:
            continue
        if bo["time"] in fired_bars:
            continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < mom_body_frac: continue

        # Avg body
        sb, nb = 0, 0
        for s in range(max(0, i - retrace_lb), i + 1):
            sb += abs(bars[s]["close"] - bars[s]["open"]); nb += 1
        if nb > 0 and body < sb / nb: continue

        # ER filter
        if er_min > 0:
            net = abs(bars[i]["close"] - bars[max(0, i - trend_lb)]["close"])
            path = sum(abs(bars[s]["close"] - bars[s+1]["close"]) for s in range(max(0, i - trend_lb), i))
            er = net / path if path > 0 else 0
            if er < er_min: continue

        # Trend
        if trend_mode == "hhhl":
            rHi = max(bars[j]["high"] for j in range(max(0, i - half), i))
            rLo = min(bars[j]["low"]  for j in range(max(0, i - half), i))
            oHi = max(bars[j]["high"] for j in range(max(0, i - trend_lb), max(1, i - half)))
            oLo = min(bars[j]["low"]  for j in range(max(0, i - trend_lb), max(1, i - half)))
            td = 1 if (rHi > oHi and rLo > oLo) else (-1 if (rHi < oHi and rLo < oLo) else 0)
        else:  # "h1" — multi-timeframe trend via price delta
            delta = bars[i]["close"] - bars[max(0, i - h1_trend_bars)]["close"]
            td = 1 if delta > h1_trend_thresh else (-1 if delta < -h1_trend_thresh else 0)

        # Determine bar period in minutes for fire offset
        if i > 0:
            bar_mins = max(1, int((bars[i]["time"] - bars[i-1]["time"]).total_seconds() / 60))
        else:
            bar_mins = 1

        # BUY
        if bo["close"] > bo["open"] and td == 1:
            uhv_v, uhv_h, uhv_l_struct = -1, 0, 999999
            for s in range(max(0, i - retrace_lb), i):
                if bars[s]["close"] < bars[s]["open"]:
                    if bars[s]["vol"] > uhv_v:
                        uhv_v = bars[s]["vol"]
                        uhv_h = bars[s]["high"]
                        uhv_l_struct = bars[s]["low"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] > uhv_h and bo["open"] <= uhv_h:
                actual_sl = sl_pts if sl_mode == "fixed" else max(0.5, bo["close"] - uhv_l_struct + 0.5)
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=bar_mins),
                             "tp": tp_pts, "sl": actual_sl, "day": day_str})
                fired_bars.add(bo["time"])
                continue

        # SELL
        if bo["close"] < bo["open"] and td == -1:
            uhv_v, uhv_l, uhv_h_struct = -1, 999999, 0
            for s in range(max(0, i - retrace_lb), i):
                if bars[s]["close"] > bars[s]["open"]:
                    if bars[s]["vol"] > uhv_v:
                        uhv_v = bars[s]["vol"]
                        uhv_l = bars[s]["low"]
                        uhv_h_struct = bars[s]["high"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
                actual_sl = sl_pts if sl_mode == "fixed" else max(0.5, uhv_h_struct - bo["close"] + 0.5)
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=bar_mins),
                             "tp": tp_pts, "sl": actual_sl, "day": day_str})
                fired_bars.add(bo["time"])

    return sigs


# ═══════════════════════════════════════════════════════════════
# TICK REPLAY
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 90)
    print("  S4 DEEP PARAMETER SWEEP — Finding the Winning Config")
    print("=" * 90)
    print()

    m1 = load_m1()
    m5 = build_tf(m1, 5)
    print(f"  {len(m1)} M1 bars  |  {len(m5)} M5 bars")

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

    # ── SWEEP CONFIGS ──
    configs = []

    # 1. TP sweep (M1, HHHL trend, ER=0.15, fixed SL)
    for tp in [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 7.5, 10.0, 12.0]:
        for sl in [3.0, 4.0, 5.0, 6.0]:
            configs.append({"label": f"M1 TP{tp}/SL{sl} hhhl ER.15",
                            "bars_key": "m1", "tp": tp, "sl": sl, "sl_mode": "fixed",
                            "er_min": 0.15, "trend_mode": "hhhl"})

    # 2. ER sweep (M1, TP12/SL6)
    for er in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        configs.append({"label": f"M1 TP12/SL6 hhhl ER{er:.2f}",
                        "bars_key": "m1", "tp": 12, "sl": 6, "sl_mode": "fixed",
                        "er_min": er, "trend_mode": "hhhl"})

    # 3. M5 timeframe (teacher's primary TF) with H1 trend
    for tp in [2.0, 3.0, 5.0, 7.5, 10.0, 12.0]:
        for sl in [3.0, 5.0, 7.5]:
            configs.append({"label": f"M5 TP{tp}/SL{sl} h1trend ER0",
                            "bars_key": "m5", "tp": tp, "sl": sl, "sl_mode": "fixed",
                            "er_min": 0.0, "trend_mode": "h1",
                            "h1_trend_bars": 12, "h1_trend_thresh": 2.0})  # 12 M5 bars = 1H

    # 4. M5 with HHHL trend
    for tp in [2.0, 3.0, 5.0, 7.5, 10.0]:
        for sl in [3.0, 5.0, 7.5]:
            configs.append({"label": f"M5 TP{tp}/SL{sl} hhhl ER0",
                            "bars_key": "m5", "tp": tp, "sl": sl, "sl_mode": "fixed",
                            "er_min": 0.0, "trend_mode": "hhhl"})

    # 5. Structural SL (M1 and M5)
    for tp in [2.0, 3.0, 5.0, 7.5, 10.0]:
        configs.append({"label": f"M1 TP{tp}/structSL hhhl ER.15",
                        "bars_key": "m1", "tp": tp, "sl": 6, "sl_mode": "structural",
                        "er_min": 0.15, "trend_mode": "hhhl"})
    for tp in [2.0, 3.0, 5.0, 7.5, 10.0]:
        configs.append({"label": f"M5 TP{tp}/structSL h1trend ER0",
                        "bars_key": "m5", "tp": tp, "sl": 6, "sl_mode": "structural",
                        "er_min": 0.0, "trend_mode": "h1",
                        "h1_trend_bars": 12, "h1_trend_thresh": 2.0})

    # 6. Tiny TPs (the Feb-11 scalp hypothesis) — your $1-$3 skim
    for tp in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        for sl in [1.0, 1.5, 2.0, 3.0]:
            if tp >= sl: continue  # skip R:R >= 1:1 already tested above
            configs.append({"label": f"M1 TP{tp}/SL{sl} hhhl ER.15 (scalp)",
                            "bars_key": "m1", "tp": tp, "sl": sl, "sl_mode": "fixed",
                            "er_min": 0.15, "trend_mode": "hhhl"})

    bars_map = {"m1": m1, "m5": m5}

    # ── RUN ALL ──
    results = []
    total = len(configs)
    print(f"  Running {total} configurations...")
    print()

    for ci, cfg in enumerate(configs):
        bars = bars_map[cfg["bars_key"]]
        all_trades, train_trades, oos_trades = [], [], []

        for day in days:
            sigs = detect_s4(bars, day, cfg["tp"], cfg["sl"],
                             sl_mode=cfg.get("sl_mode", "fixed"),
                             er_min=cfg.get("er_min", 0.15),
                             trend_mode=cfg.get("trend_mode", "hhhl"),
                             h1_trend_bars=cfg.get("h1_trend_bars", 60),
                             h1_trend_thresh=cfg.get("h1_trend_thresh", 2.0))
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

        # Max drawdown
        eq, pk, dd = 0, 0, 0
        for t in sorted(all_trades, key=lambda x: x["fire"]):
            eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)

        results.append({**cfg, "n": n, "wr": w/n*100, "total": tot, "train": tot_train,
                       "oos": tot_oos, "ev": tot/n, "wf": tot_train > 0 and tot_oos > 0,
                       "dd": dd, "buy_pnl": sum(t["pnl"] for t in buys),
                       "sell_pnl": sum(t["pnl"] for t in sells)})

        if (ci + 1) % 20 == 0:
            print(f"    ... {ci+1}/{total} done")

    # ── PRINT RESULTS ──
    print()
    print("=" * 130)
    print(f"  {'Config':<45}  {'n':>4}  {'WR':>5}  {'Total':>9}  {'TRAIN':>9}  {'OOS':>9}  {'EV':>7}  {'DD':>7}  {'BUY':>8}  {'SELL':>8}  {'WF':>3}")
    print("=" * 130)

    # Sort by OOS P&L descending
    results.sort(key=lambda r: r["oos"], reverse=True)

    for r in results:
        wf = "✅" if r["wf"] else "❌"
        print(f"  {r['label']:<45}  {r['n']:>4}  {r['wr']:>4.1f}%  ${r['total']:>+8.1f}  ${r['train']:>+8.1f}  ${r['oos']:>+8.1f}  ${r['ev']:>+6.2f}  ${r['dd']:>6.1f}  ${r['buy_pnl']:>+7.1f}  ${r['sell_pnl']:>+7.1f}  {wf}")

    # ── TOP 10 BY OOS ──
    print()
    print("=" * 90)
    print("  TOP 10 CONFIGS BY OOS P&L (walk-forward positive only)")
    print("=" * 90)
    wf_results = [r for r in results if r["wf"]]
    for i, r in enumerate(wf_results[:10]):
        print(f"  #{i+1}: {r['label']}")
        print(f"      n={r['n']}  WR={r['wr']:.1f}%  Total=${r['total']:+.1f}  Train=${r['train']:+.1f}  OOS=${r['oos']:+.1f}  EV=${r['ev']:+.2f}")
        print(f"      DD=${r['dd']:.1f}  BUY=${r['buy_pnl']:+.1f}  SELL=${r['sell_pnl']:+.1f}")
        print()

    # ── INSIGHTS ──
    print("=" * 90)
    print("  KEY INSIGHTS")
    print("=" * 90)
    
    # Best M1 vs best M5
    best_m1_wf = [r for r in wf_results if r["bars_key"] == "m1"]
    best_m5_wf = [r for r in wf_results if r["bars_key"] == "m5"]
    if best_m1_wf:
        b = best_m1_wf[0]
        print(f"  Best M1 (WF+): {b['label']}  OOS=${b['oos']:+.1f}  WR={b['wr']:.1f}%")
    if best_m5_wf:
        b = best_m5_wf[0]
        print(f"  Best M5 (WF+): {b['label']}  OOS=${b['oos']:+.1f}  WR={b['wr']:.1f}%")

    # Scalp configs
    scalp_wf = [r for r in wf_results if "scalp" in r["label"]]
    if scalp_wf:
        b = scalp_wf[0]
        print(f"  Best Scalp (WF+): {b['label']}  OOS=${b['oos']:+.1f}  WR={b['wr']:.1f}%")
    else:
        print(f"  Best Scalp: NONE pass walk-forward ❌")

    # Structural SL
    struct_wf = [r for r in wf_results if r["sl_mode"] == "structural"]
    if struct_wf:
        b = struct_wf[0]
        print(f"  Best Structural SL (WF+): {b['label']}  OOS=${b['oos']:+.1f}  WR={b['wr']:.1f}%")

    # H1 trend vs HHHL
    h1_wf = [r for r in wf_results if r["trend_mode"] == "h1"]
    hhhl_wf = [r for r in wf_results if r["trend_mode"] == "hhhl"]
    if h1_wf:
        print(f"  H1 trend configs WF+: {len(h1_wf)}  (best OOS=${h1_wf[0]['oos']:+.1f})")
    if hhhl_wf:
        print(f"  HHHL trend configs WF+: {len(hhhl_wf)}  (best OOS=${hhhl_wf[0]['oos']:+.1f})")

    print()

if __name__ == "__main__":
    main()
