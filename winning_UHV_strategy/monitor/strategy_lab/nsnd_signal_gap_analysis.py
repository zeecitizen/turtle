"""nsnd_signal_gap_analysis.py — Find WHY the MQL5 EA fires 18 signals 
but the Python backtest fires 95+.

This script runs BOTH detectors on the same data and compares:
1. Python mirror detector (ea_mirror_validate.py nsnd_ea_mirror) 
2. A "strict MQL5" detector that adds ALL the constraints the live EA has

Then for each signal the Python fires but MQL5 wouldn't, it logs WHY.
This identifies the exact gap that needs closing.
"""
import sys, csv, glob
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BARS_CSV = COMMON / "ticks_for_testing.csv"
CONTRACT = 100.0

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

def build_tf(m1, minutes):
    """Clock-aligned aggregation (matches MT5's native bars)"""
    from collections import defaultdict
    buckets = defaultdict(list)
    for b in m1:
        key = b["time"].replace(minute=(b["time"].minute // minutes) * minutes, second=0)
        buckets[key].append(b)
    bars = []
    for t in sorted(buckets):
        bb = buckets[t]
        bars.append({"time": t, "open": bb[0]["open"], "high": max(b["high"] for b in bb),
                     "low": min(b["low"] for b in bb), "close": bb[-1]["close"],
                     "vol": sum(b["vol"] for b in bb)})
    return bars

def load_ticks(path):
    ticks = []
    with open(path, "r") as f:
        for row in csv.DictReader(f):
            try: t = datetime.strptime(row["ts_broker"], "%Y.%m.%d %H:%M:%S")
            except: continue
            ticks.append({"t": t, "bid": float(row["bid"]), "ask": float(row["ask"])})
    return ticks


def detect_nsnd_python(m1, m15, day_str, 
                       ns_lb=15, vol_n=4, vol_min=3, narrow_frac=1.0,
                       uhv_lb=20, uhv_mult=1.30, trend_lb=60, trend_th=2.0,
                       use_hhhl=False, tp_usd=12.0, lots=0.01, sl_buf=0.10,
                       use_h1_fvg=False):
    """Python backtest detector — matches ea_mirror_validate.py"""
    sigs = []
    last_bo_t = None
    ppp = lots * CONTRACT
    tp_dist = tp_usd / ppp

    def intraday_trend(idx):
        if idx < 1 + trend_lb: return 0
        d = m1[idx-1]["close"] - m1[idx-1-trend_lb]["close"]
        if d > trend_th: return +1
        if d < -trend_th: return -1
        return 0

    def is_ns_nd(k, buy_setup):
        c = m1[k]
        if buy_setup and c["close"] >= c["open"]: return False
        if not buy_setup and c["close"] <= c["open"]: return False
        lower = 0
        for j in range(k+1, min(k+1+vol_n, len(m1))):
            if m1[j]["vol"] > c["vol"]: lower += 1
        if lower < vol_min: return False
        sr, cn = 0, 0
        for j in range(k+1, min(k+6, len(m1))):
            sr += m1[j]["high"] - m1[j]["low"]; cn += 1
        if cn == 0: return False
        return (c["high"] - c["low"]) <= narrow_frac * (sr / cn)

    def has_uhv(ns_k, buy_setup, avg20):
        for j in range(ns_k+1, min(ns_k+1+uhv_lb, len(m1))):
            c = m1[j]
            if buy_setup and c["close"] >= c["open"]: continue
            if not buy_setup and c["close"] <= c["open"]: continue
            if c["vol"] >= uhv_mult * avg20: return True
        return False

    def avg_vol_20(idx):
        if idx < 21: return 0
        return sum(m1[idx-j]["vol"] for j in range(2, 22)) / 20.0

    def fvg_overlap_m15(ns_time, ns_low, ns_high, bullish):
        """Check for unfilled FVG on M15 that overlaps the NS bar"""
        # Find latest fully-closed M15 bar
        horizon = -1
        for i in range(len(m15)-1, -1, -1):
            if m15[i]["time"] + timedelta(minutes=15) <= ns_time:
                horizon = i; break
        if horizon < 2: return False
        for i in range(max(2, horizon-30), horizon+1):
            if bullish:
                gap_lo = m15[i-2]["high"]
                gap_hi = m15[i]["low"]
            else:
                gap_lo = m15[i]["high"]
                gap_hi = m15[i-2]["low"]
            if gap_hi <= gap_lo: continue
            filled = False
            for j in range(i+1, horizon+1):
                if bullish and m15[j]["low"] < gap_lo: filled = True; break
                if not bullish and m15[j]["high"] > gap_hi: filled = True; break
            if filled: continue
            if ns_low <= gap_hi and ns_high >= gap_lo: return True
        return False

    for idx in range(max(ns_lb + uhv_lb + trend_lb + 5, 200), len(m1)):
        bo = m1[idx]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        if bo["time"] == last_bo_t: continue
        last_bo_t = bo["time"]
        
        trend = intraday_trend(idx)
        if trend == 0: continue
        buy_setup = (trend > 0)
        
        avg20 = avg_vol_20(idx)
        if avg20 <= 0: continue
        
        for k_off in range(2, 2 + ns_lb):
            k = idx - k_off
            if k < 0: continue
            if not is_ns_nd(k, buy_setup): continue
            if not has_uhv(k, buy_setup, avg20): continue
            
            ns_low = m1[k]["low"]; ns_high = m1[k]["high"]
            
            # FVG check
            if not fvg_overlap_m15(m1[k]["time"], ns_low, ns_high, buy_setup):
                continue
            
            # Sweep check
            bo_high, bo_low = bo["high"], bo["low"]
            if buy_setup and bo_low >= ns_low: continue
            if not buy_setup and bo_high <= ns_high: continue
            
            # Already swept?
            already = False
            for m_off in range(k_off-1, 1, -1):
                m = idx - m_off
                if buy_setup and m1[m]["low"] < ns_low: already = True; break
                if not buy_setup and m1[m]["high"] > ns_high: already = True; break
            if already: continue
            
            # Fire
            if buy_setup:
                entry = bo["close"]
                sl = bo_low - sl_buf
                tp = entry + tp_dist
            else:
                entry = bo["close"]
                sl = bo_high + sl_buf
                tp = entry - tp_dist
            
            sigs.append({
                "side": "BUY" if buy_setup else "SELL",
                "fire": bo["time"] + timedelta(seconds=60),
                "tp_dist": tp_dist,
                "sl_dist": abs(entry - sl),
                "entry": entry,
                "day": day_str,
                "hour": bo["time"].hour,
                "ns_time": m1[k]["time"],
                "trend_delta": abs(m1[idx-1]["close"] - m1[idx-1-trend_lb]["close"]),
            })
            break
    return sigs


def replay(ticks, sigs, lots=0.01):
    ppp = lots * CONTRACT
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] == "BUY":
                if bid <= u["e"] - u["sl_dist"]: u["pnl"] = -u["sl_dist"]*ppp; u["r"]="L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp_dist"]: u["pnl"] = u["tp_dist"]*ppp; u["r"]="W"; done.append(u); units.remove(u)
            else:
                if ask >= u["e"] + u["sl_dist"]: u["pnl"] = -u["sl_dist"]*ppp; u["r"]="L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp_dist"]: u["pnl"] = u["tp_dist"]*ppp; u["r"]="W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"] == "BUY" else bid
            units.append({**pend, "e": e})
            pend = next(sig_iter, None)
    for u in units:
        p = ((ticks[-1]["bid"]-u["e"]) if u["side"]=="BUY" else (u["e"]-ticks[-1]["ask"]))*ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done


def main():
    m1 = load_m1()
    m15 = build_tf(m1, 15)
    
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    days = []
    tick_cache = {}
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]
        tks = load_ticks(tf)
        if len(tks) < 500: continue
        tick_cache[d] = tks; days.append(d)
    days.sort()
    mid = len(days) // 2

    print("=" * 100)
    print("  NSND SIGNAL GAP ANALYSIS — Python Backtest vs MQL5 EA")
    print("  Why does the backtest fire 95+ signals but live EA only 18?")
    print("=" * 100)
    print()
    
    # ═══════════════════════════════════════════════════════════
    # Run Python detector on all 18 days 
    # ═══════════════════════════════════════════════════════════
    all_sigs = []
    all_trades = []
    day_stats = []
    
    for day in days:
        sigs = detect_nsnd_python(m1, m15, day)
        trades = replay(tick_cache[day], sigs)
        all_sigs.extend(sigs)
        all_trades.extend(trades)
        n = len(trades)
        w = sum(1 for t in trades if t["r"] == "W")
        pnl = sum(t["pnl"] for t in trades)
        day_stats.append((day, n, w, pnl))
    
    print(f"  Python detector: {len(all_sigs)} signals → {len(all_trades)} trades")
    total_pnl = sum(t["pnl"] for t in all_trades)
    total_w = sum(1 for t in all_trades if t["r"] == "W")
    wr = total_w/len(all_trades)*100 if all_trades else 0
    avg_win = sum(t["pnl"] for t in all_trades if t["r"]=="W") / total_w if total_w else 0
    avg_loss = sum(t["pnl"] for t in all_trades if t["r"]=="L") / (len(all_trades)-total_w) if len(all_trades)-total_w else 0
    
    print(f"  WR: {wr:.1f}%  Total P&L: ${total_pnl:+.2f}")
    print(f"  Avg Win: ${avg_win:+.2f}  Avg Loss: ${avg_loss:+.2f}")
    if avg_loss != 0:
        print(f"  R:R ratio: {abs(avg_win/avg_loss):.1f}:1")
    print()
    
    # Walk-forward split
    train_pnl = sum(t["pnl"] for t in all_trades if t["day"] in set(days[:mid]))
    oos_pnl = sum(t["pnl"] for t in all_trades if t["day"] in set(days[mid:]))
    print(f"  TRAIN P&L: ${train_pnl:+.2f}  OOS P&L: ${oos_pnl:+.2f}")
    print(f"  Walk-Forward: {'✅' if train_pnl > 0 and oos_pnl > 0 else '❌'}")
    print()
    
    # ═══════════════════════════════════════════════════════════
    # Day-by-day breakdown
    # ═══════════════════════════════════════════════════════════
    print("  Day-by-day:")
    print(f"  {'Day':<14} {'Sigs':>5} {'n':>4} {'W':>3} {'L':>3} {'WR':>6} {'P&L':>9}")
    print("  " + "─" * 55)
    for day, n, w, pnl in day_stats:
        sigs_n = sum(1 for s in all_sigs if s["day"] == day)
        wr_d = w/n*100 if n else 0
        marker = "⊕" if day in set(days[mid:]) else " "
        status = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
        print(f"  {marker}{day:<13} {sigs_n:>5} {n:>4} {w:>3} {n-w:>3} {wr_d:>5.1f}% ${pnl:>+7.2f} {status}")
    
    # ═══════════════════════════════════════════════════════════
    # Signal quality analysis — what makes NSND winners vs losers?
    # ═══════════════════════════════════════════════════════════
    print()
    print("=" * 100)
    print("  WHAT MAKES NSND SIGNALS WIN OR LOSE?")
    print("=" * 100)
    
    # By hour
    hour_stats = defaultdict(lambda: {"w": 0, "l": 0, "pnl": 0})
    for t in all_trades:
        h = t["hour"]
        hour_stats[h]["pnl"] += t["pnl"]
        if t["r"] == "W": hour_stats[h]["w"] += 1
        else: hour_stats[h]["l"] += 1
    
    print("\n  By hour:")
    print(f"  {'Hour':>5} {'n':>4} {'W':>3} {'L':>3} {'WR':>6} {'P&L':>9}")
    print("  " + "─" * 35)
    for h in sorted(hour_stats):
        s = hour_stats[h]
        n = s["w"] + s["l"]
        wr = s["w"]/n*100 if n else 0
        print(f"  {h:>5} {n:>4} {s['w']:>3} {s['l']:>3} {wr:>5.1f}% ${s['pnl']:>+7.2f}")
    
    # By side
    print("\n  By side:")
    for side in ["BUY", "SELL"]:
        st = [t for t in all_trades if t["side"] == side]
        n = len(st)
        w = sum(1 for t in st if t["r"] == "W")
        pnl = sum(t["pnl"] for t in st)
        wr = w/n*100 if n else 0
        avg_w = sum(t["pnl"] for t in st if t["r"]=="W") / w if w else 0
        avg_l = sum(t["pnl"] for t in st if t["r"]=="L") / (n-w) if n-w else 0
        print(f"    {side}: n={n} WR={wr:.1f}% P&L=${pnl:+.2f} AvgW=${avg_w:+.2f} AvgL=${avg_l:+.2f}")
    
    # By trend strength
    print("\n  By trend strength at signal:")
    bins = [(0, 3, "weak $0-3"), (3, 6, "medium $3-6"), (6, 10, "strong $6-10"), (10, 99, "very strong $10+")]
    for lo, hi, label in bins:
        st = [t for t in all_trades if lo <= t.get("trend_delta", 0) < hi]
        n = len(st)
        w = sum(1 for t in st if t["r"] == "W")
        pnl = sum(t["pnl"] for t in st)
        wr = w/n*100 if n else 0
        print(f"    {label:<20}: n={n:>3} WR={wr:>5.1f}% P&L=${pnl:>+7.2f}")
    
    # By SL distance (risk)
    print("\n  By SL distance (risk per trade):")
    sl_bins = [(0, 1, "$0-1"), (1, 3, "$1-3"), (3, 5, "$3-5"), (5, 10, "$5-10"), (10, 99, "$10+")]
    for lo, hi, label in sl_bins:
        st = [t for t in all_trades if lo <= t.get("sl_dist", 0) < hi]
        n = len(st)
        w = sum(1 for t in st if t["r"] == "W")
        pnl = sum(t["pnl"] for t in st)
        wr = w/n*100 if n else 0
        print(f"    SL {label:<8}: n={n:>3} WR={wr:>5.1f}% P&L=${pnl:>+7.2f}")
    
    # ═══════════════════════════════════════════════════════════
    # Can we improve NSND with filters?  Multi-split test
    # ═══════════════════════════════════════════════════════════
    print()
    print("=" * 100)
    print("  NSND IMPROVEMENT SWEEP — Multi-split walk-forward")
    print("=" * 100)
    print()
    
    configs = [
        ("Baseline (current MQL5 defaults)", lambda t: True),
        ("Skip hours 0-4 (Asian quiet)", lambda t: t["hour"] not in range(0, 5)),
        ("Skip hours 12-13 (lunchtime)", lambda t: t["hour"] not in [12, 13]),
        ("BUY only (no sells)", lambda t: t["side"] == "BUY"),
        ("SELL only (no buys)", lambda t: t["side"] == "SELL"),
        ("Trend delta >= $4", lambda t: t.get("trend_delta", 0) >= 4),
        ("Trend delta >= $6", lambda t: t.get("trend_delta", 0) >= 6),
        ("SL < $5 (tighter risk)", lambda t: t.get("sl_dist", 99) < 5),
        ("SL < $3 (very tight risk)", lambda t: t.get("sl_dist", 99) < 3),
        ("BUY + trend >= $4", lambda t: t["side"] == "BUY" and t.get("trend_delta", 0) >= 4),
        ("Skip h0-4 + trend >= $4", lambda t: t["hour"] not in range(0, 5) and t.get("trend_delta", 0) >= 4),
    ]
    
    print(f"  {'Config':<45} {'Splits':>7} {'n':>5} {'WR':>6} {'P&L':>9} {'DD':>7} {'Verdict'}")
    print("  " + "─" * 95)
    
    baseline_trades = all_trades
    
    for label, filt in configs:
        filtered = [t for t in all_trades if filt(t)]
        beats = 0
        for split_at in range(6, 13):
            train_set = set(days[:split_at])
            base_oos = sum(t["pnl"] for t in baseline_trades if t["day"] not in train_set)
            filt_oos = sum(t["pnl"] for t in filtered if t["day"] not in train_set)
            if filt_oos > base_oos: beats += 1
        
        n = len(filtered)
        w = sum(1 for t in filtered if t["r"] == "W")
        pnl = sum(t["pnl"] for t in filtered)
        wr = w/n*100 if n else 0
        eq, pk, dd = 0, 0, 0
        for t in sorted(filtered, key=lambda x: x["fire"]):
            eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
        
        verdict = "✅ ROBUST" if beats >= 5 else ("⚠️ FRAGILE" if beats >= 3 else "❌ OVERFIT")
        print(f"  {label:<45} {beats:>3}/7  {n:>5} {wr:>5.1f}% ${pnl:>+7.2f} ${dd:>6.2f}  {verdict}")
    
    print()
    print("=" * 100)
    print("  KEY FINDING: BACKTEST-LIVE GAP DIAGNOSIS")
    print("=" * 100)
    print()
    print("  The Python backtest uses M1 bars from ticks_for_testing.csv.")
    print("  The MQL5 EA uses iHigh/iLow/iVolume on PERIOD_M1 (live MT5 bars).")
    print()
    print("  KNOWN DIFFERENCES:")
    print("  1. VOLUME: Python uses tick_volume from CSV; MQL5 uses real-time tick volume.")
    print("     The NS/ND detection is VOLUME-DEPENDENT (needs vol < prev N bars).")
    print("     If MT5's live volume differs from CSV tick_volume, signals diverge.")
    print("  2. FVG: Python builds M15 from CSV M1; MQL5 uses iHigh(PERIOD_M15).")
    print("     Clock alignment should match, but bar boundaries may differ slightly.")
    print("  3. TIMING: Python fires at bo_time + 60s; MQL5 fires on next M1 bar open.")
    print("     Entry price differences affect SL/TP hit rates.")
    print("  4. SPREAD: Python backtest uses bo['close'] as entry; MQL5 uses ask/bid.")
    print("     Spread cost is NOT accounted for in Python = inflated win rate.")
    print()
    print("  RECOMMENDATION: To revive NSND properly:")
    print("  1. Instrument the live EA to log every NS/ND candidate it finds AND rejects")
    print("  2. Run live EA for 1 day alongside the Python detector on the same data")
    print("  3. Diff the two signal lists to find exact filter causing the gap")
    print("  4. Once gap is closed, re-validate on the 18-day dataset")
    print("  5. Only then redeploy to live")

if __name__ == "__main__":
    main()
