"""verify_improvements.py — Day-by-day backtest of the two proven improvements.

Improvement 1: S1 trend threshold $2 → $7
Improvement 2: S4 td24>=9 + skip hours 12-13
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

def detect_s1(m5, day_str, trend_min=2.0):
    sigs = []
    fired = set()
    for i in range(26, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str or bo["time"] in fired: continue
        td24 = abs(m5[i]["close"] - m5[max(0,i-24)]["close"])
        for side in ["BUY", "SELL"]:
            if side == "BUY":
                delta = m5[i]["close"] - m5[max(0,i-24)]["close"]
                if delta < trend_min: continue
                uhv_v, uhv_h, uhv_l = -1, 0, 999999
                for s in range(max(0, i - 15), i):
                    if m5[s]["close"] < m5[s]["open"] and m5[s]["vol"] > uhv_v:
                        uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]; uhv_l = m5[s]["low"]
                if uhv_v <= 0: continue
                swept = any(m5[s]["low"] < uhv_l for s in range(max(0, i - 15), i))
                if not swept: continue
                if bo["close"] <= bo["open"] or bo["close"] <= uhv_h or bo["open"] > uhv_h: continue
                sl_dist = bo["close"] - (uhv_l - 2.0)
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 7.5, "sl": sl_dist, "day": day_str, "ea": "S1", "td24": td24,
                             "hour": bo["time"].hour})
                fired.add(bo["time"]); break
            else:
                delta = m5[max(0,i-24)]["close"] - m5[i]["close"]
                if delta < trend_min: continue
                uhv_v, uhv_h, uhv_l = -1, 0, 999999
                for s in range(max(0, i - 15), i):
                    if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                        uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]; uhv_l = m5[s]["low"]
                if uhv_v <= 0: continue
                swept = any(m5[s]["high"] > uhv_h for s in range(max(0, i - 15), i))
                if not swept: continue
                if bo["close"] >= bo["open"] or bo["close"] >= uhv_l or bo["open"] < uhv_l: continue
                sl_dist = (uhv_h + 2.0) - bo["close"]
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 7.5, "sl": sl_dist, "day": day_str, "ea": "S1", "td24": td24,
                             "hour": bo["time"].hour})
                fired.add(bo["time"]); break
    return sigs

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
                             "tp": 2.0, "sl": 7.5, "day": day_str, "ea": "S4", "td24": td24,
                             "hour": bo["time"].hour})
                fired.add(bo["time"]); continue
        if bo["close"] < bo["open"] and td == -1:
            uhv_v, uhv_l = -1, 999999
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_l = m5[s]["low"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str, "ea": "S4", "td24": td24,
                             "hour": bo["time"].hour})
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
    mid = len(days) // 2

    # ═══════════════════════════════════════════════════════════
    # S1: trend threshold $2 (current) vs $7 (improved)
    # ═══════════════════════════════════════════════════════════
    print("=" * 110)
    print("  S1 VERIFICATION: Trend Threshold $2.00 (current) vs $7.00 (improved)")
    print("=" * 110)
    print()
    print(f"  {'Day':<12} │ {'── CURRENT (td>=$2) ──':^34} │ {'── IMPROVED (td>=$7) ──':^34} │ {'Δ P&L':>7}")
    print(f"  {'':─<12} │ {'n':>4} {'W':>3} {'L':>3} {'WR':>6} {'P&L':>9} │ {'n':>4} {'W':>3} {'L':>3} {'WR':>6} {'P&L':>9} │ {'':>7}")
    print("  " + "─" * 107)

    s1_old_total, s1_new_total = 0, 0
    s1_old_trades_all, s1_new_trades_all = [], []
    s1_old_green, s1_new_green = 0, 0

    for i, day in enumerate(days):
        split = "TRAIN" if i < mid else "OOS"
        
        old_sigs = detect_s1(m5, day, trend_min=2.0)
        old_trades = replay(tick_cache[day], old_sigs)
        old_n = len(old_trades)
        old_w = sum(1 for t in old_trades if t["r"]=="W")
        old_l = old_n - old_w
        old_wr = old_w/old_n*100 if old_n else 0
        old_pnl = sum(t["pnl"] for t in old_trades)
        
        new_sigs = detect_s1(m5, day, trend_min=7.0)
        new_trades = replay(tick_cache[day], new_sigs)
        new_n = len(new_trades)
        new_w = sum(1 for t in new_trades if t["r"]=="W")
        new_l = new_n - new_w
        new_wr = new_w/new_n*100 if new_n else 0
        new_pnl = sum(t["pnl"] for t in new_trades)
        
        diff = new_pnl - old_pnl
        s1_old_total += old_pnl; s1_new_total += new_pnl
        s1_old_trades_all.extend(old_trades); s1_new_trades_all.extend(new_trades)
        if old_pnl > 0: s1_old_green += 1
        if new_pnl > 0: s1_new_green += 1
        
        marker = "  " if i < mid else "⊕ "
        day_status_old = "🟢" if old_pnl > 0 else "🔴"
        day_status_new = "🟢" if new_pnl > 0 else "🔴"
        print(f"  {marker}{day:<10} │ {old_n:>4} {old_w:>3} {old_l:>3} {old_wr:>5.1f}% ${old_pnl:>+7.1f} {day_status_old} │ {new_n:>4} {new_w:>3} {new_l:>3} {new_wr:>5.1f}% ${new_pnl:>+7.1f} {day_status_new} │ ${diff:>+6.1f}")

    print("  " + "─" * 107)
    on = len(s1_old_trades_all); ow = sum(1 for t in s1_old_trades_all if t["r"]=="W")
    nn = len(s1_new_trades_all); nw = sum(1 for t in s1_new_trades_all if t["r"]=="W")
    owr = ow/on*100 if on else 0; nwr = nw/nn*100 if nn else 0
    print(f"  {'TOTAL':<12} │ {on:>4} {ow:>3} {on-ow:>3} {owr:>5.1f}% ${s1_old_total:>+7.1f}    │ {nn:>4} {nw:>3} {nn-nw:>3} {nwr:>5.1f}% ${s1_new_total:>+7.1f}    │ ${s1_new_total-s1_old_total:>+6.1f}")
    
    # Train/OOS split
    old_train = sum(t["pnl"] for i,d in enumerate(days) if i<mid for t in replay(tick_cache[d], detect_s1(m5, d, 2.0)))
    old_oos = s1_old_total - old_train
    new_train = sum(t["pnl"] for i,d in enumerate(days) if i<mid for t in replay(tick_cache[d], detect_s1(m5, d, 7.0)))
    new_oos = s1_new_total - new_train
    
    # Max DD
    eq, pk, dd_old = 0, 0, 0
    for t in sorted(s1_old_trades_all, key=lambda x: x["fire"]):
        eq += t["pnl"]; pk = max(pk, eq); dd_old = max(dd_old, pk - eq)
    eq, pk, dd_new = 0, 0, 0
    for t in sorted(s1_new_trades_all, key=lambda x: x["fire"]):
        eq += t["pnl"]; pk = max(pk, eq); dd_new = max(dd_new, pk - eq)

    print()
    print(f"  Summary:")
    print(f"    {'':30} {'CURRENT':>12} {'IMPROVED':>12} {'Change':>12}")
    print(f"    {'Trades':<30} {on:>12} {nn:>12} {nn-on:>+12}")
    print(f"    {'Win Rate':<30} {owr:>11.1f}% {nwr:>11.1f}% {nwr-owr:>+11.1f}%")
    print(f"    {'Total P&L':<30} ${s1_old_total:>+10.1f} ${s1_new_total:>+10.1f} ${s1_new_total-s1_old_total:>+10.1f}")
    print(f"    {'TRAIN P&L':<30} ${old_train:>+10.1f} ${new_train:>+10.1f} ${new_train-old_train:>+10.1f}")
    print(f"    {'OOS P&L':<30} ${old_oos:>+10.1f} ${new_oos:>+10.1f} ${new_oos-old_oos:>+10.1f}")
    print(f"    {'Max Drawdown':<30} ${dd_old:>10.1f} ${dd_new:>10.1f} ${dd_new-dd_old:>+10.1f}")
    print(f"    {'Green Days':<30} {s1_old_green:>10}/{len(days)} {s1_new_green:>10}/{len(days)}")
    print(f"    {'Walk-Forward':<30} {'✅':>12} {'✅' if new_train > 0 and new_oos > 0 else '❌':>12}")
    print()

    # ═══════════════════════════════════════════════════════════
    # S4: baseline vs td24>=9 + skip h12-13
    # ═══════════════════════════════════════════════════════════
    print("=" * 110)
    print("  S4 VERIFICATION: Baseline vs td24>=9 + skip hours 12-13")
    print("=" * 110)
    print()
    print(f"  {'Day':<12} │ {'── CURRENT (baseline) ──':^34} │ {'── IMPROVED (td24>=9,!h12-13) ──':^34} │ {'Δ P&L':>7}")
    print(f"  {'':─<12} │ {'n':>4} {'W':>3} {'L':>3} {'WR':>6} {'P&L':>9} │ {'n':>4} {'W':>3} {'L':>3} {'WR':>6} {'P&L':>9} │ {'':>7}")
    print("  " + "─" * 107)

    s4_old_total, s4_new_total = 0, 0
    s4_old_trades_all, s4_new_trades_all = [], []
    s4_old_green, s4_new_green = 0, 0

    for i, day in enumerate(days):
        old_sigs = detect_s4(m5, day, min_td24=0, skip_hours=None)
        old_trades = replay(tick_cache[day], old_sigs)
        old_n = len(old_trades)
        old_w = sum(1 for t in old_trades if t["r"]=="W")
        old_l = old_n - old_w
        old_wr = old_w/old_n*100 if old_n else 0
        old_pnl = sum(t["pnl"] for t in old_trades)
        
        new_sigs = detect_s4(m5, day, min_td24=9, skip_hours={12, 13})
        new_trades = replay(tick_cache[day], new_sigs)
        new_n = len(new_trades)
        new_w = sum(1 for t in new_trades if t["r"]=="W")
        new_l = new_n - new_w
        new_wr = new_w/new_n*100 if new_n else 0
        new_pnl = sum(t["pnl"] for t in new_trades)
        
        diff = new_pnl - old_pnl
        s4_old_total += old_pnl; s4_new_total += new_pnl
        s4_old_trades_all.extend(old_trades); s4_new_trades_all.extend(new_trades)
        if old_pnl > 0: s4_old_green += 1
        if new_pnl > 0: s4_new_green += 1
        
        marker = "  " if i < mid else "⊕ "
        day_status_old = "🟢" if old_pnl > 0 else ("🔴" if old_pnl < 0 else "⚪")
        day_status_new = "🟢" if new_pnl > 0 else ("🔴" if new_pnl < 0 else "⚪")
        wr_old_s = f"{old_wr:.1f}%" if old_n else "  n/a"
        wr_new_s = f"{new_wr:.1f}%" if new_n else "  n/a"
        print(f"  {marker}{day:<10} │ {old_n:>4} {old_w:>3} {old_l:>3} {wr_old_s:>6} ${old_pnl:>+7.1f} {day_status_old} │ {new_n:>4} {new_w:>3} {new_l:>3} {wr_new_s:>6} ${new_pnl:>+7.1f} {day_status_new} │ ${diff:>+6.1f}")

    print("  " + "─" * 107)
    on = len(s4_old_trades_all); ow = sum(1 for t in s4_old_trades_all if t["r"]=="W")
    nn = len(s4_new_trades_all); nw = sum(1 for t in s4_new_trades_all if t["r"]=="W")
    owr = ow/on*100 if on else 0; nwr = nw/nn*100 if nn else 0
    print(f"  {'TOTAL':<12} │ {on:>4} {ow:>3} {on-ow:>3} {owr:>5.1f}% ${s4_old_total:>+7.1f}    │ {nn:>4} {nw:>3} {nn-nw:>3} {nwr:>5.1f}% ${s4_new_total:>+7.1f}    │ ${s4_new_total-s4_old_total:>+6.1f}")

    old_train = sum(t["pnl"] for i,d in enumerate(days) if i<mid for t in replay(tick_cache[d], detect_s4(m5, d, 0, None)))
    old_oos = s4_old_total - old_train
    new_train = sum(t["pnl"] for i,d in enumerate(days) if i<mid for t in replay(tick_cache[d], detect_s4(m5, d, 9, {12,13})))
    new_oos = s4_new_total - new_train

    eq, pk, dd_old = 0, 0, 0
    for t in sorted(s4_old_trades_all, key=lambda x: x["fire"]):
        eq += t["pnl"]; pk = max(pk, eq); dd_old = max(dd_old, pk - eq)
    eq, pk, dd_new = 0, 0, 0
    for t in sorted(s4_new_trades_all, key=lambda x: x["fire"]):
        eq += t["pnl"]; pk = max(pk, eq); dd_new = max(dd_new, pk - eq)

    print()
    print(f"  Summary:")
    print(f"    {'':30} {'CURRENT':>12} {'IMPROVED':>12} {'Change':>12}")
    print(f"    {'Trades':<30} {on:>12} {nn:>12} {nn-on:>+12}")
    print(f"    {'Win Rate':<30} {owr:>11.1f}% {nwr:>11.1f}% {nwr-owr:>+11.1f}%")
    print(f"    {'Total P&L':<30} ${s4_old_total:>+10.1f} ${s4_new_total:>+10.1f} ${s4_new_total-s4_old_total:>+10.1f}")
    print(f"    {'TRAIN P&L':<30} ${old_train:>+10.1f} ${new_train:>+10.1f} ${new_train-old_train:>+10.1f}")
    print(f"    {'OOS P&L':<30} ${old_oos:>+10.1f} ${new_oos:>+10.1f} ${new_oos-old_oos:>+10.1f}")
    print(f"    {'Max Drawdown':<30} ${dd_old:>10.1f} ${dd_new:>10.1f} ${dd_new-dd_old:>+10.1f}")
    print(f"    {'Green Days':<30} {s4_old_green:>10}/{len(days)} {s4_new_green:>10}/{len(days)}")
    print(f"    {'Walk-Forward':<30} {'✅':>12} {'✅' if new_train > 0 and new_oos > 0 else '❌':>12}")
    print()

    # ═══════════════════════════════════════════════════════════
    # COMBINED
    # ═══════════════════════════════════════════════════════════
    print("=" * 60)
    print("  COMBINED IMPROVEMENT IMPACT")
    print("=" * 60)
    print()
    old_combined = s1_old_total + s4_old_total
    new_combined = s1_new_total + s4_new_total
    print(f"  S1 + S4 Current:  ${old_combined:+.1f}")
    print(f"  S1 + S4 Improved: ${new_combined:+.1f}")
    print(f"  Net Improvement:  ${new_combined - old_combined:+.1f}")
    print()
    print(f"  ⊕ = OOS day (out-of-sample)")

if __name__ == "__main__":
    main()
