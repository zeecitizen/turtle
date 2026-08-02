"""verify_s4_trend_only.py — Claude's suggestion: S4 with td24>=7 only (no hour filter).

Compares:
  A) S4 baseline (current)
  B) S4 td24>=7 only (Claude's recommendation)
  C) S4 td24>=9 + skip h12-13 (Antigravity's original recommendation)
  D) S4 td24>=7 + skip h12-13 (hybrid)

Also runs multi-split walk-forward (7 split points) for each config.
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
PPP = LOTS * CONTRACT

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

def detect_s4(m5, day_str, min_td24=0, skip_hours=None):
    sigs = []
    fired = set()
    for i in range(32, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str or bo["time"] in fired: continue
        if skip_hours and bo["time"].hour in skip_hours: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < 0.55: continue
        sb, nb = 0, 0
        for s in range(max(0, i - 12), i + 1):
            sb += abs(m5[s]["close"] - m5[s]["open"]); nb += 1
        if nb > 0 and body < sb / nb: continue
        td24 = abs(m5[i]["close"] - m5[max(0,i-24)]["close"])
        if td24 < min_td24: continue
        half = 15
        rHi = max(m5[j]["high"] for j in range(max(0, i - half), i))
        rLo = min(m5[j]["low"]  for j in range(max(0, i - half), i))
        oHi = max(m5[j]["high"] for j in range(max(0, i - 30), max(1, i - half)))
        oLo = min(m5[j]["low"]  for j in range(max(0, i - 30), max(1, i - half)))
        td = 1 if (rHi > oHi and rLo > oLo) else (-1 if (rHi < oHi and rLo < oLo) else 0)
        if bo["close"] > bo["open"] and td == 1:
            uhv_v, uhv_h = -1, 0
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] < m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] > uhv_h and bo["open"] <= uhv_h:
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str})
                fired.add(bo["time"]); continue
        if bo["close"] < bo["open"] and td == -1:
            uhv_v, uhv_l = -1, 999999
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_l = m5[s]["low"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str})
                fired.add(bo["time"])
    return sigs

def replay(ticks, sigs):
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] == "BUY":
                if bid <= u["e"] - u["sl"]: u["pnl"] = -u["sl"]*PPP; u["r"]="L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]: u["pnl"] = u["tp"]*PPP; u["r"]="W"; done.append(u); units.remove(u)
            else:
                if ask >= u["e"] + u["sl"]: u["pnl"] = -u["sl"]*PPP; u["r"]="L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]: u["pnl"] = u["tp"]*PPP; u["r"]="W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"] == "BUY" else bid
            units.append({**pend, "e": e})
            pend = next(sig_iter, None)
    for u in units:
        p = ((ticks[-1]["bid"]-u["e"]) if u["side"]=="BUY" else (u["e"]-ticks[-1]["ask"]))*PPP
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done

def run_config(m5, tick_cache, days, min_td24, skip_hours):
    all_trades = []
    for day in days:
        sigs = detect_s4(m5, day, min_td24=min_td24, skip_hours=skip_hours)
        trades = replay(tick_cache[day], sigs)
        for t in trades: t["day"] = day
        all_trades.extend(trades)
    return all_trades

def stats(trades, train_set):
    n = len(trades)
    if n == 0: return {"n":0,"wr":0,"pnl":0,"train":0,"oos":0,"wf":False,"dd":0}
    w = sum(1 for t in trades if t["r"]=="W")
    pnl = sum(t["pnl"] for t in trades)
    train = sum(t["pnl"] for t in trades if t["day"] in train_set)
    oos = sum(t["pnl"] for t in trades if t["day"] not in train_set)
    eq, pk, dd = 0, 0, 0
    for t in sorted(trades, key=lambda x: x["fire"]):
        eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
    return {"n": n, "wr": w/n*100, "pnl": pnl, "train": train, "oos": oos,
            "wf": train > 0 and oos > 0, "dd": dd}

def main():
    m1 = load_m1()
    m5 = build_m5(m1)
    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    tick_cache, days = {}, []
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]
        tks = load_ticks(tf)
        if len(tks) < 500: continue
        tick_cache[d] = tks; days.append(d)
    days.sort()
    nd = len(days)

    configs = [
        ("A) Baseline (current)", 0, None),
        ("B) td24>=7 only (Claude's rec)", 7, None),
        ("C) td24>=9 + skip h12-13 (Antigravity's rec)", 9, {12, 13}),
        ("D) td24>=7 + skip h12-13 (hybrid)", 7, {12, 13}),
        ("E) td24>=5 only", 5, None),
    ]

    # ═══════════════════════════════════════════════
    # Single-split (midpoint) results
    # ═══════════════════════════════════════════════
    print("=" * 100)
    print("  S4 CONFIG COMPARISON — Single Split (midpoint)")
    print("=" * 100)
    print()
    mid = nd // 2
    train_set = set(days[:mid])
    
    print(f"  {'Config':<48} {'n':>4} {'WR':>6} {'Total':>9} {'TRAIN':>9} {'OOS':>9} {'DD':>7} {'WF':>3}")
    print("  " + "─" * 97)
    for label, min_td, skip_h in configs:
        trades = run_config(m5, tick_cache, days, min_td, skip_h)
        s = stats(trades, train_set)
        wf = "✅" if s["wf"] else "❌"
        print(f"  {label:<48} {s['n']:>4} {s['wr']:>5.1f}% ${s['pnl']:>+7.1f} ${s['train']:>+7.1f} ${s['oos']:>+7.1f} ${s['dd']:>6.1f} {wf}")

    # ═══════════════════════════════════════════════
    # Multi-split walk-forward (7 split points)
    # ═══════════════════════════════════════════════
    print()
    print("=" * 100)
    print("  S4 MULTI-SPLIT WALK-FORWARD (7 split points)")
    print("  Each split: train on first N days, test on remaining")
    print("=" * 100)
    print()

    for label, min_td, skip_h in configs:
        print(f"  ── {label} ──")
        beats = 0
        baseline_trades_all = run_config(m5, tick_cache, days, 0, None)
        
        for split_at in range(6, 13):  # split at day 6-12 (7 splits)
            train_set = set(days[:split_at])
            
            trades = run_config(m5, tick_cache, days, min_td, skip_h)
            s = stats(trades, train_set)
            
            base_trades = run_config(m5, tick_cache, days, 0, None)
            bs = stats(base_trades, train_set)
            
            beat = s["oos"] > bs["oos"]
            if beat: beats += 1
            
            print(f"    Split@{split_at:>2}: OOS=${s['oos']:>+7.1f} (base=${bs['oos']:>+7.1f}) {'✅ BEATS' if beat else '❌ LOSES'}")
        
        print(f"    Result: {beats}/7 splits beat baseline {'✅ ROBUST' if beats >= 5 else '⚠️ FRAGILE' if beats >= 3 else '❌ OVERFIT'}")
        print()

    # ═══════════════════════════════════════════════
    # Day-by-day for the winner
    # ═══════════════════════════════════════════════
    print("=" * 100)
    print("  DAY-BY-DAY: Baseline vs td24>=7 (trend-only)")
    print("=" * 100)
    print()
    
    mid = nd // 2
    for i, day in enumerate(days):
        marker = "  " if i < mid else "⊕ "
        
        old_trades = replay(tick_cache[day], detect_s4(m5, day, 0, None))
        new_trades = replay(tick_cache[day], detect_s4(m5, day, 7, None))
        
        on, ow = len(old_trades), sum(1 for t in old_trades if t["r"]=="W")
        nn, nw = len(new_trades), sum(1 for t in new_trades if t["r"]=="W")
        op = sum(t["pnl"] for t in old_trades)
        np_ = sum(t["pnl"] for t in new_trades)
        
        owr = f"{ow/on*100:.0f}%" if on else "n/a"
        nwr = f"{nw/nn*100:.0f}%" if nn else "n/a"
        os = "🟢" if op > 0 else ("🔴" if op < 0 else "⚪")
        ns = "🟢" if np_ > 0 else ("🔴" if np_ < 0 else "⚪")
        
        print(f"  {marker}{day}  BASE: {on:>2}t {owr:>4} ${op:>+6.1f} {os}  │  td24>=7: {nn:>2}t {nwr:>4} ${np_:>+6.1f} {ns}  │ Δ${np_-op:>+6.1f}")

if __name__ == "__main__":
    main()
