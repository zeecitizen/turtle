"""prove_all_improvements.py — Multi-split walk-forward proof for EVERY recommendation.

Tests each improvement across 7 different train/OOS splits.
A config is ROBUST if it beats baseline in 5+ out of 7 splits.
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

# ═══════════════════════════════════════════════════════════════
# DETECTORS
# ═══════════════════════════════════════════════════════════════
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
                if not any(m5[s]["low"] < uhv_l for s in range(max(0, i - 15), i)): continue
                if bo["close"] <= bo["open"] or bo["close"] <= uhv_h or bo["open"] > uhv_h: continue
                sl_dist = bo["close"] - (uhv_l - 2.0)
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 7.5, "sl": sl_dist, "day": day_str, "td24": td24, "hour": bo["time"].hour})
                fired.add(bo["time"]); break
            else:
                delta = m5[max(0,i-24)]["close"] - m5[i]["close"]
                if delta < trend_min: continue
                uhv_v, uhv_h, uhv_l = -1, 0, 999999
                for s in range(max(0, i - 15), i):
                    if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                        uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]; uhv_l = m5[s]["low"]
                if uhv_v <= 0: continue
                if not any(m5[s]["high"] > uhv_h for s in range(max(0, i - 15), i)): continue
                if bo["close"] >= bo["open"] or bo["close"] >= uhv_l or bo["open"] < uhv_l: continue
                sl_dist = (uhv_h + 2.0) - bo["close"]
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 7.5, "sl": sl_dist, "day": day_str, "td24": td24, "hour": bo["time"].hour})
                fired.add(bo["time"]); break
    return sigs

def detect_s3(m5, day_str):
    sigs = []
    fired_reds = set()
    for i in range(55, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        td24 = abs(m5[i]["close"] - m5[max(0,i-24)]["close"])
        td60 = abs(m5[i]["close"] - m5[max(0,i-60)]["close"])
        for side in ["BUY", "SELL"]:
            if side == "BUY":
                if bo["close"] <= bo["open"]: continue
                if (bo["high"] - bo["close"]) / rng > 0.35: continue
                if m5[i]["close"] - m5[max(0,i-24)]["close"] < 1.0: continue
                reds = []
                for goff in range(2, 31):
                    gi = i - goff
                    if gi < 0: break
                    g = m5[gi]
                    if g["close"] <= g["open"]: continue
                    gl = g["low"]
                    any_b, tmp = False, []
                    for joff in range(goff - 1, 0, -1):
                        ji = i - joff
                        if ji < 0 or ji >= i: continue
                        r = m5[ji]
                        if r["close"] < r["open"]:
                            if r["close"] < gl or r["low"] < gl: any_b = True
                            tmp.append(ji)
                    if any_b and tmp: reds = tmp; break
                if not reds: continue
                mt = None
                for ri in reds:
                    if bo["low"] >= m5[ri]["low"] or bo["close"] <= m5[ri]["low"] or bo["vol"] <= m5[ri]["vol"]: continue
                    mt = m5[ri]["time"]; break
                if mt is None or mt in fired_reds: continue
                sl_dist = bo["close"] - (bo["low"] - 5.0)
                tp_peak = max(m5[j]["high"] for j in range(max(0, i - 10), i))
                tp_dist = tp_peak - bo["close"]
                if tp_dist <= 0.2: continue
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist, "day": day_str, "td24": td24, "td60": td60, "hour": bo["time"].hour})
                fired_reds.add(mt); break
            else:
                if bo["close"] >= bo["open"]: continue
                if m5[max(0,i-24)]["close"] - m5[i]["close"] < 1.0: continue
                greens = []
                for roff in range(2, 31):
                    ri = i - roff
                    if ri < 0: break
                    r = m5[ri]
                    if r["close"] >= r["open"]: continue
                    rh = r["high"]
                    any_b, tmp = False, []
                    for joff in range(roff - 1, 0, -1):
                        ji = i - joff
                        if ji < 0 or ji >= i: continue
                        g = m5[ji]
                        if g["close"] > g["open"]:
                            if g["close"] > rh or g["high"] > rh: any_b = True
                            tmp.append(ji)
                    if any_b and tmp: greens = tmp; break
                if not greens: continue
                mt = None
                for gi in greens:
                    if bo["high"] <= m5[gi]["high"] or bo["close"] >= m5[gi]["high"] or bo["vol"] <= m5[gi]["vol"]: continue
                    mt = m5[gi]["time"]; break
                if mt is None or mt in fired_reds: continue
                sl_dist = (bo["high"] + 5.0) - bo["close"]
                tp_trough = min(m5[j]["low"] for j in range(max(0, i - 10), i))
                tp_dist = bo["close"] - tp_trough
                if tp_dist <= 0.2: continue
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist, "day": day_str, "td24": td24, "td60": td60, "hour": bo["time"].hour})
                fired_reds.add(mt); break
    return sigs

def detect_s4(m5, day_str):
    sigs = []
    fired = set()
    for i in range(32, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str or bo["time"] in fired: continue
        rng = bo["high"] - bo["low"]
        if rng <= 0: continue
        body = abs(bo["close"] - bo["open"])
        if body / rng < 0.55: continue
        sb, nb = 0, 0
        for s in range(max(0, i - 12), i + 1):
            sb += abs(m5[s]["close"] - m5[s]["open"]); nb += 1
        if nb > 0 and body < sb / nb: continue
        td24 = abs(m5[i]["close"] - m5[max(0,i-24)]["close"])
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
                             "tp": 2.0, "sl": 7.5, "day": day_str, "td24": td24, "hour": bo["time"].hour})
                fired.add(bo["time"]); continue
        if bo["close"] < bo["open"] and td == -1:
            uhv_v, uhv_l = -1, 999999
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_l = m5[s]["low"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str, "td24": td24, "hour": bo["time"].hour})
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

def multi_split_test(label, get_base_trades, get_filtered_trades, days):
    """Run 7-split walk-forward. Returns (beats, total_pnl, total_wr, total_dd)"""
    nd = len(days)
    beats = 0
    results = []
    for split_at in range(6, 13):
        train_set = set(days[:split_at])
        base_oos = sum(t["pnl"] for t in get_base_trades() if t["day"] not in train_set)
        filt_oos = sum(t["pnl"] for t in get_filtered_trades() if t["day"] not in train_set)
        beat = filt_oos > base_oos
        if beat: beats += 1
        results.append((split_at, filt_oos, base_oos, beat))
    
    # Total stats
    all_t = get_filtered_trades()
    n = len(all_t)
    w = sum(1 for t in all_t if t["r"]=="W")
    pnl = sum(t["pnl"] for t in all_t)
    eq, pk, dd = 0, 0, 0
    for t in sorted(all_t, key=lambda x: x["fire"]):
        eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
    
    return beats, results, n, w/n*100 if n else 0, pnl, dd

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

    # Pre-detect all signals (unfiltered)
    print("  Loading and detecting signals...", flush=True)
    s1_base, s3_base, s4_base = [], [], []
    for day in days:
        for s in detect_s1(m5, day, trend_min=2.0):
            s1_base.append(dict(**s))
        for s in detect_s3(m5, day):
            s3_base.append(dict(**s))
        for s in detect_s4(m5, day):
            s4_base.append(dict(**s))
    
    # Replay all baselines
    s1_base_trades, s3_base_trades, s4_base_trades = [], [], []
    for day in days:
        s1_day = [s for s in s1_base if s["day"] == day]
        s1_base_trades.extend(replay(tick_cache[day], s1_day))
        s3_day = [s for s in s3_base if s["day"] == day]
        s3_base_trades.extend(replay(tick_cache[day], s3_day))
        s4_day = [s for s in s4_base if s["day"] == day]
        s4_base_trades.extend(replay(tick_cache[day], s4_day))
    
    # Tag days
    for t in s1_base_trades + s3_base_trades + s4_base_trades:
        if "day" not in t: t["day"] = "unknown"

    print("  Done. Running multi-split tests...\n")

    # ═══════════════════════════════════════════════════════════
    print("=" * 110)
    print("  MULTI-SPLIT WALK-FORWARD PROOF — ALL IMPROVEMENTS")
    print("  7 split points (train on first 6-12 days, test on rest)")
    print("  ROBUST = beats baseline OOS in 5+ of 7 splits")
    print("=" * 110)

    all_results = []

    # ── S1 IMPROVEMENTS ──
    print("\n" + "─" * 110)
    print("  S1 IMPROVEMENTS (baseline: trend >= $2)")
    print("─" * 110)

    s1_configs = [
        ("S1: td24 >= $5", lambda t: t.get("td24",0) >= 5),
        ("S1: td24 >= $7 ★ RECOMMENDED", lambda t: t.get("td24",0) >= 7),
        ("S1: td24 >= $9", lambda t: t.get("td24",0) >= 9),
        ("S1: td24 >= $11", lambda t: t.get("td24",0) >= 11),
        ("S1: skip h12-13", lambda t: t.get("hour",0) not in [12, 13]),
        ("S1: td24>=$7 + skip h12-13", lambda t: t.get("td24",0) >= 7 and t.get("hour",0) not in [12, 13]),
        ("S1: skip NY session (h14-20)", lambda t: t.get("hour",0) not in range(14, 21)),
    ]

    for label, filt in s1_configs:
        filtered = [t for t in s1_base_trades if filt(t)]
        beats = 0
        split_details = []
        for split_at in range(6, 13):
            train_set = set(days[:split_at])
            base_oos = sum(t["pnl"] for t in s1_base_trades if t["day"] not in train_set)
            filt_oos = sum(t["pnl"] for t in filtered if t["day"] not in train_set)
            beat = filt_oos > base_oos
            if beat: beats += 1
            split_details.append(("✅" if beat else "❌", filt_oos, base_oos))
        
        n = len(filtered)
        w = sum(1 for t in filtered if t["r"]=="W")
        pnl = sum(t["pnl"] for t in filtered)
        wr = w/n*100 if n else 0
        eq, pk, dd = 0, 0, 0
        for t in sorted(filtered, key=lambda x: x["fire"]):
            eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
        
        verdict = "✅ ROBUST" if beats >= 5 else ("⚠️ FRAGILE" if beats >= 3 else "❌ OVERFIT")
        star = " ★" if beats >= 5 else ""
        print(f"\n  {label}")
        print(f"    n={n}  WR={wr:.1f}%  P&L=${pnl:+.1f}  DD=${dd:.1f}")
        splits_str = " ".join(f"{d[0]}" for d in split_details)
        print(f"    Splits: {splits_str}  →  {beats}/7  {verdict}")
        all_results.append((label, beats, n, wr, pnl, dd, verdict))

    # ── S3 IMPROVEMENTS ──
    print("\n" + "─" * 110)
    print("  S3 IMPROVEMENTS (baseline: current v2.31)")
    print("─" * 110)

    s3_configs = [
        ("S3: td60 >= $5", lambda t: t.get("td60",0) >= 5),
        ("S3: td60 >= $7", lambda t: t.get("td60",0) >= 7),
        ("S3: td60 >= $9", lambda t: t.get("td60",0) >= 9),
        ("S3: skip h12-13 ★ RECOMMENDED", lambda t: t.get("hour",0) not in [12, 13]),
        ("S3: td60>=$5 + skip h12-13", lambda t: t.get("td60",0) >= 5 and t.get("hour",0) not in [12, 13]),
        ("S3: td60>=$9 + skip h12-13", lambda t: t.get("td60",0) >= 9 and t.get("hour",0) not in [12, 13]),
        ("S3: td24>=$7 + td60>=$9", lambda t: t.get("td24",0) >= 7 and t.get("td60",0) >= 9),
    ]

    for label, filt in s3_configs:
        filtered = [t for t in s3_base_trades if filt(t)]
        beats = 0
        split_details = []
        for split_at in range(6, 13):
            train_set = set(days[:split_at])
            base_oos = sum(t["pnl"] for t in s3_base_trades if t["day"] not in train_set)
            filt_oos = sum(t["pnl"] for t in filtered if t["day"] not in train_set)
            beat = filt_oos > base_oos
            if beat: beats += 1
            split_details.append(("✅" if beat else "❌", filt_oos, base_oos))
        
        n = len(filtered)
        w = sum(1 for t in filtered if t["r"]=="W")
        pnl = sum(t["pnl"] for t in filtered)
        wr = w/n*100 if n else 0
        eq, pk, dd = 0, 0, 0
        for t in sorted(filtered, key=lambda x: x["fire"]):
            eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
        
        verdict = "✅ ROBUST" if beats >= 5 else ("⚠️ FRAGILE" if beats >= 3 else "❌ OVERFIT")
        print(f"\n  {label}")
        print(f"    n={n}  WR={wr:.1f}%  P&L=${pnl:+.1f}  DD=${dd:.1f}")
        splits_str = " ".join(f"{d[0]}" for d in split_details)
        print(f"    Splits: {splits_str}  →  {beats}/7  {verdict}")
        all_results.append((label, beats, n, wr, pnl, dd, verdict))

    # ── S4 IMPROVEMENTS ──
    print("\n" + "─" * 110)
    print("  S4 IMPROVEMENTS (baseline: current v2.00)")
    print("─" * 110)

    s4_configs = [
        ("S4: td24 >= $5", lambda t: t.get("td24",0) >= 5),
        ("S4: td24 >= $7", lambda t: t.get("td24",0) >= 7),
        ("S4: td24 >= $9", lambda t: t.get("td24",0) >= 9),
        ("S4: skip h12-13", lambda t: t.get("hour",0) not in [12, 13]),
        ("S4: td24>=$7 + skip h12-13 ★ RECOMMENDED", lambda t: t.get("td24",0) >= 7 and t.get("hour",0) not in [12, 13]),
        ("S4: td24>=$9 + skip h12-13", lambda t: t.get("td24",0) >= 9 and t.get("hour",0) not in [12, 13]),
    ]

    for label, filt in s4_configs:
        filtered = [t for t in s4_base_trades if filt(t)]
        beats = 0
        split_details = []
        for split_at in range(6, 13):
            train_set = set(days[:split_at])
            base_oos = sum(t["pnl"] for t in s4_base_trades if t["day"] not in train_set)
            filt_oos = sum(t["pnl"] for t in filtered if t["day"] not in train_set)
            beat = filt_oos > base_oos
            if beat: beats += 1
            split_details.append(("✅" if beat else "❌", filt_oos, base_oos))
        
        n = len(filtered)
        w = sum(1 for t in filtered if t["r"]=="W")
        pnl = sum(t["pnl"] for t in filtered)
        wr = w/n*100 if n else 0
        eq, pk, dd = 0, 0, 0
        for t in sorted(filtered, key=lambda x: x["fire"]):
            eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
        
        verdict = "✅ ROBUST" if beats >= 5 else ("⚠️ FRAGILE" if beats >= 3 else "❌ OVERFIT")
        print(f"\n  {label}")
        print(f"    n={n}  WR={wr:.1f}%  P&L=${pnl:+.1f}  DD=${dd:.1f}")
        splits_str = " ".join(f"{d[0]}" for d in split_details)
        print(f"    Splits: {splits_str}  →  {beats}/7  {verdict}")
        all_results.append((label, beats, n, wr, pnl, dd, verdict))

    # ═══════════════════════════════════════════════════════════
    # FINAL SCOREBOARD
    # ═══════════════════════════════════════════════════════════
    print("\n" + "=" * 110)
    print("  FINAL SCOREBOARD — All Improvements Ranked by Multi-Split Robustness")
    print("=" * 110)
    print()
    print(f"  {'Improvement':<48} {'Splits':>7} {'n':>5} {'WR':>6} {'P&L':>9} {'DD':>7} {'Verdict'}")
    print("  " + "─" * 107)
    
    all_results.sort(key=lambda x: (-x[1], -x[4]))
    for label, beats, n, wr, pnl, dd, verdict in all_results:
        print(f"  {label:<48} {beats:>3}/7  {n:>5} {wr:>5.1f}% ${pnl:>+7.1f} ${dd:>6.1f}  {verdict}")

if __name__ == "__main__":
    main()
