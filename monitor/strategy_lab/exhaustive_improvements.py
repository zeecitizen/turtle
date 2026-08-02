"""exhaustive_improvements.py — Test EVERY possible improvement on real ticks.

Phase 1: Breakeven SL simulation (tick-by-tick, NET effect including killed winners)
Phase 2: Exact trend threshold optimization for each EA
Phase 3: Candle quality features (what makes a good vs bad signal)
Phase 4: Session filters (Asian/London/NY)
Phase 5: Trailing stop simulation
Phase 6: Multi-EA confirmation (do signals in same direction boost WR?)
Phase 7: Combination filters (best trend + best time + best candle quality)
"""
import sys, csv, glob, math
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

# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════
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
# DETECTORS (with rich metadata)
# ═══════════════════════════════════════════════════════════════
def calc_atr(bars, i, period=14):
    trs = []
    for s in range(max(1, i - period), i):
        h, l, pc = bars[s]["high"], bars[s]["low"], bars[s-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 1.0

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
        half = 15
        rHi = max(m5[j]["high"] for j in range(max(0, i - half), i))
        rLo = min(m5[j]["low"]  for j in range(max(0, i - half), i))
        oHi = max(m5[j]["high"] for j in range(max(0, i - 30), max(1, i - half)))
        oLo = min(m5[j]["low"]  for j in range(max(0, i - 30), max(1, i - half)))
        td = 1 if (rHi > oHi and rLo > oLo) else (-1 if (rHi < oHi and rLo < oLo) else 0)
        
        # Rich metadata
        td24 = abs(m5[i]["close"] - m5[max(0,i-24)]["close"])
        td60 = abs(m5[i]["close"] - m5[max(0,i-60)]["close"])
        atr = calc_atr(m5, i)
        body_ratio = body / rng
        # Volume ratio: breakout vol / UHV vol
        green_count = sum(1 for s in range(max(0,i-5), i) if m5[s]["close"] > m5[s]["open"])
        meta = {"hour": bo["time"].hour, "dow": bo["time"].weekday(), "atr": atr,
                "td24": td24, "td60": td60, "body_ratio": body_ratio,
                "green5": green_count, "bar_i": i}

        if bo["close"] > bo["open"] and td == 1:
            uhv_v, uhv_h = -1, 0
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] < m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] > uhv_h and bo["open"] <= uhv_h:
                meta["vol_ratio"] = bo["vol"] / uhv_v if uhv_v > 0 else 1
                meta["break_dist"] = bo["close"] - uhv_h
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str, "ea": "S4", **meta})
                fired.add(bo["time"]); continue
        if bo["close"] < bo["open"] and td == -1:
            uhv_v, uhv_l = -1, 999999
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_l = m5[s]["low"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
                meta["vol_ratio"] = bo["vol"] / uhv_v if uhv_v > 0 else 1
                meta["break_dist"] = uhv_l - bo["close"]
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str, "ea": "S4", **meta})
                fired.add(bo["time"])
    return sigs

def detect_s1(m5, day_str):
    sigs = []
    fired = set()
    for i in range(26, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str or bo["time"] in fired: continue
        rng = bo["high"] - bo["low"]
        body = abs(bo["close"] - bo["open"]) if rng > 0 else 0
        td24 = abs(m5[i]["close"] - m5[max(0,i-24)]["close"])
        td60 = abs(m5[i]["close"] - m5[max(0,i-60)]["close"])
        atr = calc_atr(m5, i)
        green_count = sum(1 for s in range(max(0,i-5), i) if m5[s]["close"] > m5[s]["open"])
        meta = {"hour": bo["time"].hour, "dow": bo["time"].weekday(), "atr": atr,
                "td24": td24, "td60": td60, "body_ratio": body/rng if rng > 0 else 0,
                "green5": green_count, "bar_i": i}
        for side in ["BUY", "SELL"]:
            if side == "BUY":
                if m5[i]["close"] - m5[max(0,i-24)]["close"] < 2.0: continue
                uhv_v, uhv_h, uhv_l = -1, 0, 999999
                for s in range(max(0, i - 15), i):
                    if m5[s]["close"] < m5[s]["open"] and m5[s]["vol"] > uhv_v:
                        uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]; uhv_l = m5[s]["low"]
                if uhv_v <= 0: continue
                swept = any(m5[s]["low"] < uhv_l for s in range(max(0, i - 15), i))
                if not swept: continue
                if bo["close"] <= bo["open"] or bo["close"] <= uhv_h or bo["open"] > uhv_h: continue
                sl_dist = bo["close"] - (uhv_l - 2.0)
                meta["vol_ratio"] = bo["vol"] / uhv_v if uhv_v > 0 else 1
                meta["break_dist"] = bo["close"] - uhv_h
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 7.5, "sl": sl_dist, "day": day_str, "ea": "S1", **meta})
                fired.add(bo["time"]); break
            else:
                if m5[max(0,i-24)]["close"] - m5[i]["close"] < 2.0: continue
                uhv_v, uhv_h, uhv_l = -1, 0, 999999
                for s in range(max(0, i - 15), i):
                    if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                        uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]; uhv_l = m5[s]["low"]
                if uhv_v <= 0: continue
                swept = any(m5[s]["high"] > uhv_h for s in range(max(0, i - 15), i))
                if not swept: continue
                if bo["close"] >= bo["open"] or bo["close"] >= uhv_l or bo["open"] < uhv_l: continue
                sl_dist = (uhv_h + 2.0) - bo["close"]
                meta["vol_ratio"] = bo["vol"] / uhv_v if uhv_v > 0 else 1
                meta["break_dist"] = uhv_l - bo["close"]
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 7.5, "sl": sl_dist, "day": day_str, "ea": "S1", **meta})
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
        body = abs(bo["close"] - bo["open"])
        td24 = abs(m5[i]["close"] - m5[max(0,i-24)]["close"])
        td60 = abs(m5[i]["close"] - m5[max(0,i-60)]["close"])
        atr = calc_atr(m5, i)
        green_count = sum(1 for s in range(max(0,i-5), i) if m5[s]["close"] > m5[s]["open"])
        meta = {"hour": bo["time"].hour, "dow": bo["time"].weekday(), "atr": atr,
                "td24": td24, "td60": td60, "body_ratio": body/rng,
                "green5": green_count, "bar_i": i, "vol_ratio": 0, "break_dist": 0}
        for side in ["BUY", "SELL"]:
            if side == "BUY":
                if bo["close"] <= bo["open"]: continue
                if (bo["high"] - bo["close"]) / rng > 0.35: continue
                td = m5[i]["close"] - m5[max(0,i-24)]["close"]
                if td < 1.0: continue
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
                    rl, rv = m5[ri]["low"], m5[ri]["vol"]
                    if bo["low"] >= rl or bo["close"] <= rl or bo["vol"] <= rv: continue
                    mt = m5[ri]["time"]
                    meta["vol_ratio"] = bo["vol"] / rv if rv > 0 else 1
                    meta["break_dist"] = bo["close"] - rl
                    break
                if mt is None or mt in fired_reds: continue
                sl_dist = bo["close"] - (bo["low"] - 5.0)
                tp_peak = max(m5[j]["high"] for j in range(max(0, i - 10), i))
                tp_dist = tp_peak - bo["close"]
                if tp_dist <= 0.2: continue
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist, "day": day_str, "ea": "S3", **meta})
                fired_reds.add(mt); break
            else:
                if bo["close"] >= bo["open"]: continue
                td = m5[max(0,i-24)]["close"] - m5[i]["close"]
                if td < 1.0: continue
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
                    gh, gv = m5[gi]["high"], m5[gi]["vol"]
                    if bo["high"] <= gh or bo["close"] >= gh or bo["vol"] <= gv: continue
                    mt = m5[gi]["time"]
                    meta["vol_ratio"] = bo["vol"] / gv if gv > 0 else 1
                    meta["break_dist"] = gh - bo["close"]
                    break
                if mt is None or mt in fired_reds: continue
                sl_dist = (bo["high"] + 5.0) - bo["close"]
                tp_trough = min(m5[j]["low"] for j in range(max(0, i - 10), i))
                tp_dist = bo["close"] - tp_trough
                if tp_dist <= 0.2: continue
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": tp_dist, "sl": sl_dist, "day": day_str, "ea": "S3", **meta})
                fired_reds.add(mt); break
    return sigs

# ═══════════════════════════════════════════════════════════════
# ENHANCED REPLAY — supports breakeven, trailing stop, time exit
# ═══════════════════════════════════════════════════════════════
def replay_with_exit(ticks, sigs, be_trigger=None, trail_trigger=None, trail_dist=None, max_mins=None):
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] == "BUY":
                fav = bid - u["e"]
                u["max_fav"] = max(u.get("max_fav", 0), fav)
                cur_sl = u.get("cur_sl", u["sl"])
                # Breakeven
                if be_trigger and fav >= be_trigger and u.get("be_armed") != True:
                    u["cur_sl"] = u["e"] - u["e"] + 0.1  # essentially 0.1 above entry → breakeven
                    u["be_armed"] = True
                    cur_sl = 0.1
                # Trailing stop
                if trail_trigger and fav >= trail_trigger:
                    new_sl = fav - trail_dist
                    if new_sl > u.get("trail_sl", -999):
                        u["trail_sl"] = new_sl
                        cur_sl = min(cur_sl, u["e"] + new_sl) if False else new_sl  # trail from entry
                # Time exit
                if max_mins and "entry_t" in u:
                    elapsed = (t - u["entry_t"]).total_seconds() / 60
                    if elapsed >= max_mins:
                        p = (bid - u["e"]) * PPP
                        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u); units.remove(u); continue
                # Check SL
                if be_trigger and u.get("be_armed"):
                    if bid <= u["e"] + 0.05:  # breakeven (tiny buffer)
                        u["pnl"] = 0.05 * PPP; u["r"] = "BE"; done.append(u); units.remove(u); continue
                elif trail_trigger and u.get("trail_sl") is not None:
                    trail_price = u["e"] + u["trail_sl"]
                    if bid <= trail_price:
                        u["pnl"] = u["trail_sl"] * PPP; u["r"] = "W" if u["trail_sl"] > 0 else "L"
                        done.append(u); units.remove(u); continue
                
                if bid <= u["e"] - u["sl"]:
                    u["pnl"] = -u["sl"] * PPP; u["r"] = "L"; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]:
                    u["pnl"] = u["tp"] * PPP; u["r"] = "W"; done.append(u); units.remove(u)
            else:  # SELL
                fav = u["e"] - ask
                u["max_fav"] = max(u.get("max_fav", 0), fav)
                if be_trigger and fav >= be_trigger and u.get("be_armed") != True:
                    u["be_armed"] = True
                if max_mins and "entry_t" in u:
                    elapsed = (t - u["entry_t"]).total_seconds() / 60
                    if elapsed >= max_mins:
                        p = (u["e"] - ask) * PPP
                        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u); units.remove(u); continue
                if be_trigger and u.get("be_armed"):
                    if ask >= u["e"] - 0.05:
                        u["pnl"] = 0.05 * PPP; u["r"] = "BE"; done.append(u); units.remove(u); continue
                if trail_trigger and fav >= trail_trigger:
                    new_sl = fav - trail_dist
                    if new_sl > u.get("trail_sl", -999):
                        u["trail_sl"] = new_sl
                if trail_trigger and u.get("trail_sl") is not None:
                    trail_price = u["e"] - u["trail_sl"]
                    if ask >= trail_price:
                        u["pnl"] = u["trail_sl"] * PPP; u["r"] = "W" if u["trail_sl"] > 0 else "L"
                        done.append(u); units.remove(u); continue
                if ask >= u["e"] + u["sl"]:
                    u["pnl"] = -u["sl"] * PPP; u["r"] = "L"; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]:
                    u["pnl"] = u["tp"] * PPP; u["r"] = "W"; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"] == "BUY" else bid
            units.append({**pend, "e": e, "entry_t": t})
            pend = next(sig_iter, None)
    for u in units:
        p = ((ticks[-1]["bid"]-u["e"]) if u["side"]=="BUY" else (u["e"]-ticks[-1]["ask"]))*PPP
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"; done.append(u)
    return done

def replay_baseline(ticks, sigs):
    return replay_with_exit(ticks, sigs)

def stats(trades, train_days):
    n = len(trades)
    if n == 0: return {"n":0,"wr":0,"pnl":0,"train":0,"oos":0,"wf":False,"dd":0}
    w = sum(1 for t in trades if t["r"] == "W" or t["r"] == "BE")
    pnl = sum(t["pnl"] for t in trades)
    train = sum(t["pnl"] for t in trades if t["day"] in train_days)
    oos = sum(t["pnl"] for t in trades if t["day"] not in train_days)
    eq, pk, dd = 0, 0, 0
    for t in sorted(trades, key=lambda x: x["fire"]):
        eq += t["pnl"]; pk = max(pk, eq); dd = max(dd, pk - eq)
    return {"n": n, "wr": w/n*100, "pnl": pnl, "train": train, "oos": oos,
            "wf": train > 0 and oos > 0, "dd": dd}

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    print("=" * 100)
    print("  EXHAUSTIVE IMPROVEMENT SEARCH — Every Possible Combination")
    print("=" * 100)
    print()

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
    nd = len(days); mid = nd // 2
    train_days = set(days[:mid])
    print(f"  {len(m5)} M5 bars | {nd} tick days | TRAIN {days[0]}→{days[mid-1]} | OOS {days[mid]}→{days[-1]}")

    # Pre-detect all signals
    print("  Detecting signals...", end="", flush=True)
    all_sigs = {ea: {} for ea in ["S1", "S3", "S4"]}
    for day in days:
        for ea, det in [("S1", detect_s1), ("S3", detect_s3), ("S4", detect_s4)]:
            all_sigs[ea][day] = det(m5, day)
    print(" done")
    for ea in ["S1","S3","S4"]:
        n = sum(len(v) for v in all_sigs[ea].values())
        print(f"    {ea}: {n} signals")
    print()

    # ════════════════════════════════════════════════════════════
    # PHASE 1: BREAKEVEN SL (full tick simulation, NET effect)
    # ════════════════════════════════════════════════════════════
    print("=" * 100)
    print("  PHASE 1: BREAKEVEN SL SIMULATION (tick-by-tick, NET effect)")
    print("=" * 100)
    for ea in ["S1", "S3", "S4"]:
        print(f"\n  ── {ea} ──")
        # Baseline
        base_trades = []
        for day in days:
            base_trades.extend(replay_baseline(tick_cache[day], all_sigs[ea][day]))
        bs = stats(base_trades, train_days)
        print(f"  BASELINE: n={bs['n']}  WR={bs['wr']:.1f}%  P&L=${bs['pnl']:+.1f}  TRAIN=${bs['train']:+.1f}  OOS=${bs['oos']:+.1f}  DD=${bs['dd']:.1f}  WF={'✅' if bs['wf'] else '❌'}")
        
        for be in [0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
            trades = []
            for day in days:
                trades.extend(replay_with_exit(tick_cache[day], all_sigs[ea][day], be_trigger=be))
            s = stats(trades, train_days)
            be_count = sum(1 for t in trades if t.get("r") == "BE")
            diff = s["pnl"] - bs["pnl"]
            print(f"  BE@+${be:<4}: n={s['n']}  WR={s['wr']:.1f}%  P&L=${s['pnl']:+.1f} ({'+' if diff>=0 else ''}{diff:.1f})  OOS=${s['oos']:+.1f}  DD=${s['dd']:.1f}  BE'd={be_count}  WF={'✅' if s['wf'] else '❌'}")

    # ════════════════════════════════════════════════════════════
    # PHASE 2: TREND THRESHOLD SWEEP
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  PHASE 2: TREND THRESHOLD OPTIMIZATION")
    print("=" * 100)
    
    for ea in ["S1", "S3", "S4"]:
        print(f"\n  ── {ea} — 24-bar trend minimum ──")
        base_trades = []
        for day in days:
            base_trades.extend(replay_baseline(tick_cache[day], all_sigs[ea][day]))
        bs = stats(base_trades, train_days)
        
        for min_td in [0, 3, 5, 7, 9, 11, 13, 15, 18, 20, 25]:
            filtered_trades = [t for t in base_trades if t["td24"] >= min_td]
            s = stats(filtered_trades, train_days)
            diff = s["pnl"] - bs["pnl"]
            print(f"  td24>=${min_td:<3}: n={s['n']:>4}  WR={s['wr']:>5.1f}%  P&L=${s['pnl']:>+8.1f} ({'+' if diff>=0 else ''}{diff:.1f})  OOS=${s['oos']:>+8.1f}  DD=${s['dd']:.1f}  WF={'✅' if s['wf'] else '❌'}")

        print(f"\n  ── {ea} — 60-bar trend minimum ──")
        for min_td in [0, 3, 5, 7, 9, 12, 15, 20, 25, 30]:
            filtered_trades = [t for t in base_trades if t["td60"] >= min_td]
            s = stats(filtered_trades, train_days)
            diff = s["pnl"] - bs["pnl"]
            print(f"  td60>=${min_td:<3}: n={s['n']:>4}  WR={s['wr']:>5.1f}%  P&L=${s['pnl']:>+8.1f} ({'+' if diff>=0 else ''}{diff:.1f})  OOS=${s['oos']:>+8.1f}  DD=${s['dd']:.1f}  WF={'✅' if s['wf'] else '❌'}")

    # ════════════════════════════════════════════════════════════
    # PHASE 3: CANDLE QUALITY FEATURES
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  PHASE 3: CANDLE QUALITY FEATURES")
    print("=" * 100)

    for ea in ["S1", "S3", "S4"]:
        base_trades = []
        for day in days:
            base_trades.extend(replay_baseline(tick_cache[day], all_sigs[ea][day]))
        if not base_trades: continue
        print(f"\n  ── {ea} ──")
        
        # Volume ratio (breakout vol / UHV vol)
        vr_trades = [t for t in base_trades if t.get("vol_ratio", 0) > 0]
        if vr_trades:
            sorted_vr = sorted(t["vol_ratio"] for t in vr_trades)
            t1 = sorted_vr[len(sorted_vr)//3]
            t2 = sorted_vr[2*len(sorted_vr)//3]
            print(f"  Volume ratio (breakout/UHV):")
            for label, lo, hi in [("Low", 0, t1), ("Med", t1, t2), ("High", t2, 999)]:
                bt = [t for t in vr_trades if lo <= t["vol_ratio"] < hi]
                if bt:
                    w = sum(1 for t in bt if t["r"]=="W"); wr = w/len(bt)*100
                    pnl = sum(t["pnl"] for t in bt)
                    print(f"    {label:<5} ({lo:.2f}-{hi:.2f}): n={len(bt):>3}  WR={wr:>5.1f}%  P&L=${pnl:>+8.1f}")

        # Breakout distance (how far past the UHV line)
        bd_trades = [t for t in base_trades if t.get("break_dist", 0) > 0]
        if bd_trades:
            sorted_bd = sorted(t["break_dist"] for t in bd_trades)
            t1 = sorted_bd[len(sorted_bd)//3]
            t2 = sorted_bd[2*len(sorted_bd)//3]
            print(f"  Breakout distance past UHV line:")
            for label, lo, hi in [("Small", 0, t1), ("Med", t1, t2), ("Large", t2, 999)]:
                bt = [t for t in bd_trades if lo <= t["break_dist"] < hi]
                if bt:
                    w = sum(1 for t in bt if t["r"]=="W"); wr = w/len(bt)*100
                    pnl = sum(t["pnl"] for t in bt)
                    print(f"    {label:<5} ({lo:.1f}-{hi:.1f}): n={len(bt):>3}  WR={wr:>5.1f}%  P&L=${pnl:>+8.1f}")

        # Body ratio of breakout candle
        print(f"  Breakout candle body ratio:")
        for label, lo, hi in [("<60%", 0, 0.6), ("60-75%", 0.6, 0.75), ("75-90%", 0.75, 0.9), (">90%", 0.9, 1.01)]:
            bt = [t for t in base_trades if lo <= t.get("body_ratio", 0) < hi]
            if bt:
                w = sum(1 for t in bt if t["r"]=="W"); wr = w/len(bt)*100
                pnl = sum(t["pnl"] for t in bt)
                print(f"    {label:<8}: n={len(bt):>3}  WR={wr:>5.1f}%  P&L=${pnl:>+8.1f}")

        # Recent momentum (green candles in last 5)
        print(f"  Green candles in last 5 bars:")
        for gc in range(6):
            bt = [t for t in base_trades if t.get("green5", 0) == gc]
            if bt and len(bt) >= 3:
                w = sum(1 for t in bt if t["r"]=="W"); wr = w/len(bt)*100
                pnl = sum(t["pnl"] for t in bt)
                print(f"    {gc} green: n={len(bt):>3}  WR={wr:>5.1f}%  P&L=${pnl:>+8.1f}")

    # ════════════════════════════════════════════════════════════
    # PHASE 4: SESSION FILTER
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  PHASE 4: SESSION FILTER (broker time)")
    print("=" * 100)
    sessions = {"Asian (0-7)": (0, 7), "London (7-14)": (7, 14), "NY (14-21)": (14, 21), "Late (21-24)": (21, 24)}
    
    for ea in ["S1", "S3", "S4"]:
        base_trades = []
        for day in days:
            base_trades.extend(replay_baseline(tick_cache[day], all_sigs[ea][day]))
        if not base_trades: continue
        print(f"\n  ── {ea} ──")
        for sname, (sh, eh) in sessions.items():
            bt = [t for t in base_trades if sh <= t["hour"] < eh]
            if bt:
                s = stats(bt, train_days)
                print(f"  {sname:<16}: n={s['n']:>3}  WR={s['wr']:>5.1f}%  P&L=${s['pnl']:>+8.1f}  OOS=${s['oos']:>+8.1f}")

    # ════════════════════════════════════════════════════════════
    # PHASE 5: TRAILING STOP
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  PHASE 5: TRAILING STOP SIMULATION")
    print("=" * 100)
    
    for ea in ["S1", "S3", "S4"]:
        print(f"\n  ── {ea} ──")
        base_trades = []
        for day in days:
            base_trades.extend(replay_baseline(tick_cache[day], all_sigs[ea][day]))
        bs = stats(base_trades, train_days)
        print(f"  BASELINE: n={bs['n']}  WR={bs['wr']:.1f}%  P&L=${bs['pnl']:+.1f}  OOS=${bs['oos']:+.1f}")
        
        for trig, dist in [(1.0, 0.5), (1.5, 0.75), (2.0, 1.0), (3.0, 1.5), (4.0, 2.0), (5.0, 2.5)]:
            trades = []
            for day in days:
                trades.extend(replay_with_exit(tick_cache[day], all_sigs[ea][day], trail_trigger=trig, trail_dist=dist))
            s = stats(trades, train_days)
            diff = s["pnl"] - bs["pnl"]
            print(f"  Trail@+${trig}/${dist}: n={s['n']}  WR={s['wr']:.1f}%  P&L=${s['pnl']:+.1f} ({'+' if diff>=0 else ''}{diff:.1f})  OOS=${s['oos']:+.1f}  WF={'✅' if s['wf'] else '❌'}")

    # ════════════════════════════════════════════════════════════
    # PHASE 6: MULTI-EA CONFIRMATION
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  PHASE 6: MULTI-EA CONFIRMATION")
    print("=" * 100)
    
    # Check if signals from different EAs in same direction within X minutes boost WR
    for ea1, ea2 in [("S1","S4"), ("S1","S3"), ("S3","S4")]:
        print(f"\n  ── {ea1} confirmed by {ea2} (within 30 min) ──")
        base_trades = []
        for day in days:
            base_trades.extend(replay_baseline(tick_cache[day], all_sigs[ea1][day]))
        
        confirmed, unconfirmed = [], []
        for t in base_trades:
            # Check if ea2 fired same direction within 30 min
            ea2_sigs_day = all_sigs[ea2].get(t["day"], [])
            has_confirm = any(
                s["side"] == t["side"] and abs((s["fire"] - t["fire"]).total_seconds()) < 1800
                for s in ea2_sigs_day
            )
            if has_confirm: confirmed.append(t)
            else: unconfirmed.append(t)
        
        if confirmed:
            cs = stats(confirmed, train_days)
            us = stats(unconfirmed, train_days)
            print(f"  Confirmed:   n={cs['n']:>3}  WR={cs['wr']:>5.1f}%  P&L=${cs['pnl']:>+8.1f}")
            print(f"  Unconfirmed: n={us['n']:>3}  WR={us['wr']:>5.1f}%  P&L=${us['pnl']:>+8.1f}")
        else:
            print(f"  No confirmed trades found")

    # ════════════════════════════════════════════════════════════
    # PHASE 7: BEST COMBINATION
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("  PHASE 7: BEST FILTER COMBINATIONS")
    print("=" * 100)

    for ea in ["S1", "S3", "S4"]:
        print(f"\n  ── {ea} ──")
        base_trades = []
        for day in days:
            base_trades.extend(replay_baseline(tick_cache[day], all_sigs[ea][day]))
        bs = stats(base_trades, train_days)
        print(f"  BASELINE: n={bs['n']}  WR={bs['wr']:.1f}%  P&L=${bs['pnl']:+.1f}  OOS=${bs['oos']:+.1f}  DD=${bs['dd']:.1f}")

        # Test combinations of filters
        combos = [
            ("td24>=9", lambda t: t["td24"] >= 9),
            ("td24>=7", lambda t: t["td24"] >= 7),
            ("td60>=9", lambda t: t["td60"] >= 9),
            ("td60>=7", lambda t: t["td60"] >= 7),
            ("skip h12-13", lambda t: t["hour"] not in [12, 13]),
            ("td24>=9 + skip h12-13", lambda t: t["td24"] >= 9 and t["hour"] not in [12, 13]),
            ("td60>=9 + skip h12-13", lambda t: t["td60"] >= 9 and t["hour"] not in [12, 13]),
            ("td24>=7 + td60>=9", lambda t: t["td24"] >= 7 and t["td60"] >= 9),
            ("td24>=9 + td60>=9", lambda t: t["td24"] >= 9 and t["td60"] >= 9),
            ("td24>=7 + td60>=9 + skip h12-13", lambda t: t["td24"] >= 7 and t["td60"] >= 9 and t["hour"] not in [12, 13]),
        ]
        for label, filt in combos:
            ft = [t for t in base_trades if filt(t)]
            s = stats(ft, train_days)
            diff = s["pnl"] - bs["pnl"]
            print(f"  {label:<38}: n={s['n']:>3}  WR={s['wr']:>5.1f}%  P&L=${s['pnl']:>+8.1f} ({'+' if diff>=0 else ''}{diff:.1f})  OOS=${s['oos']:>+8.1f}  DD=${s['dd']:.1f}  WF={'✅' if s['wf'] else '❌'}")

    print("\n" + "=" * 100)
    print("  ANALYSIS COMPLETE")
    print("=" * 100)

if __name__ == "__main__":
    main()
