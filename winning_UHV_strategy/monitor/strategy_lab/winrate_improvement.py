"""winrate_improvement.py — Find every way to improve WR for S1, S3, S4.

Analyzes:
  1. Time-of-day: which hours are toxic vs golden
  2. Trend strength: does stronger trend = higher WR
  3. Exit improvements: trailing stops, time exits, breakeven moves
"""
import sys, csv, glob, math
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

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

def calc_atr(bars, i, period=14):
    trs = []
    for s in range(max(1, i - period), i):
        h, l, pc = bars[s]["high"], bars[s]["low"], bars[s-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 1.0

def calc_trend_delta(bars, i, lookback):
    j = max(0, i - lookback)
    return bars[i]["close"] - bars[j]["close"]

def detect_s4(m5, day_str):
    sigs = []
    fired = set()
    for i in range(32, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        if bo["time"] in fired: continue
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
        atr = calc_atr(m5, i)
        td24 = calc_trend_delta(m5, i, 24)
        td60 = calc_trend_delta(m5, i, 60)
        meta = {"hour": bo["time"].hour, "dow": bo["time"].weekday(), "atr": atr,
                "td24": abs(td24), "td60": abs(td60), "bar_i": i}
        if bo["close"] > bo["open"] and td == 1:
            uhv_v, uhv_h = -1, 0
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] < m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_h = m5[s]["high"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] > uhv_h and bo["open"] <= uhv_h:
                sigs.append({"side": "BUY", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str, "ea": "S4", **meta})
                fired.add(bo["time"]); continue
        if bo["close"] < bo["open"] and td == -1:
            uhv_v, uhv_l = -1, 999999
            for s in range(max(0, i - 12), i):
                if m5[s]["close"] > m5[s]["open"] and m5[s]["vol"] > uhv_v:
                    uhv_v = m5[s]["vol"]; uhv_l = m5[s]["low"]
            if uhv_v > 0 and bo["vol"] < uhv_v and bo["close"] < uhv_l and bo["open"] >= uhv_l:
                sigs.append({"side": "SELL", "fire": bo["time"] + timedelta(minutes=5),
                             "tp": 2.0, "sl": 7.5, "day": day_str, "ea": "S4", **meta})
                fired.add(bo["time"])
    return sigs

def detect_s1(m5, day_str):
    sigs = []
    fired = set()
    for i in range(26, len(m5)):
        bo = m5[i]
        if bo["time"].strftime("%Y-%m-%d") != day_str: continue
        if bo["time"] in fired: continue
        atr = calc_atr(m5, i)
        td24 = calc_trend_delta(m5, i, 24)
        td60 = calc_trend_delta(m5, i, 60)
        meta = {"hour": bo["time"].hour, "dow": bo["time"].weekday(), "atr": atr,
                "td24": abs(td24), "td60": abs(td60), "bar_i": i}
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
                if bo["close"] <= bo["open"]: continue
                if bo["close"] <= uhv_h or bo["open"] > uhv_h: continue
                sl_dist = bo["close"] - (uhv_l - 2.0)
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
                if bo["close"] >= bo["open"]: continue
                if bo["close"] >= uhv_l or bo["open"] < uhv_l: continue
                sl_dist = (uhv_h + 2.0) - bo["close"]
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
        atr = calc_atr(m5, i)
        td24v = calc_trend_delta(m5, i, 24)
        td60v = calc_trend_delta(m5, i, 60)
        meta = {"hour": bo["time"].hour, "dow": bo["time"].weekday(), "atr": atr,
                "td24": abs(td24v), "td60": abs(td60v), "bar_i": i}
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
                    if bo["low"] >= rl: continue
                    if bo["close"] <= rl: continue
                    if bo["vol"] <= rv: continue
                    mt = m5[ri]["time"]; break
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
                    if bo["high"] <= gh: continue
                    if bo["close"] >= gh: continue
                    if bo["vol"] <= gv: continue
                    mt = m5[gi]["time"]; break
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
# TICK REPLAY (enhanced — records tick-level data for exit analysis)
# ═══════════════════════════════════════════════════════════════

def replay_enhanced(ticks, sigs, lots):
    """Returns trades with extra fields: max_fav (max favorable excursion), time_to_resolve"""
    ppp = lots * CONTRACT
    done, units = [], []
    sig_iter = iter(sorted(sigs, key=lambda x: x["fire"]))
    pend = next(sig_iter, None)
    for tk in ticks:
        t, bid, ask = tk["t"], tk["bid"], tk["ask"]
        for u in units[:]:
            if u["side"] == "BUY":
                fav = bid - u["e"]
                u["max_fav"] = max(u.get("max_fav", 0), fav)
                if bid <= u["e"] - u["sl"]:
                    u["pnl"] = -u["sl"]*ppp; u["r"]="L"; u["resolve_t"]=t; done.append(u); units.remove(u)
                elif bid >= u["e"] + u["tp"]:
                    u["pnl"] = u["tp"]*ppp; u["r"]="W"; u["resolve_t"]=t; done.append(u); units.remove(u)
            else:
                fav = u["e"] - ask
                u["max_fav"] = max(u.get("max_fav", 0), fav)
                if ask >= u["e"] + u["sl"]:
                    u["pnl"] = -u["sl"]*ppp; u["r"]="L"; u["resolve_t"]=t; done.append(u); units.remove(u)
                elif ask <= u["e"] - u["tp"]:
                    u["pnl"] = u["tp"]*ppp; u["r"]="W"; u["resolve_t"]=t; done.append(u); units.remove(u)
        while pend and t >= pend["fire"]:
            e = ask if pend["side"] == "BUY" else bid
            units.append({**pend, "e": e, "entry_t": t})
            pend = next(sig_iter, None)
    for u in units:
        p = ((ticks[-1]["bid"]-u["e"]) if u["side"]=="BUY" else (u["e"]-ticks[-1]["ask"]))*ppp
        u["pnl"] = p; u["r"] = "W" if p > 0 else "L"
        u["resolve_t"] = ticks[-1]["t"]
        u["max_fav"] = u.get("max_fav", 0)
        done.append(u)
    return done

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 90)
    print("  WINRATE IMPROVEMENT ANALYSIS — All 3 EAs")
    print("=" * 90)
    print()

    m1 = load_m1()
    m5 = build_m5(m1)
    print(f"  {len(m5)} M5 bars")

    tick_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    tick_cache, days = {}, []
    for tf in tick_files:
        d = Path(tf).stem.split("_")[-1]
        tks = load_ticks(tf)
        if len(tks) < 500: continue
        tick_cache[d] = tks; days.append(d)
    days.sort()
    nd = len(days); mid = nd // 2
    train_days, oos_days = days[:mid], days[mid:]
    print(f"  {nd} days | TRAIN {train_days[0]}→{train_days[-1]} | OOS {oos_days[0]}→{oos_days[-1]}")
    print()

    # ── Collect all trades ──
    all_trades = []
    for day in days:
        for detector in [detect_s1, detect_s3, detect_s4]:
            sigs = detector(m5, day)
            trades = replay_enhanced(tick_cache[day], sigs, LOTS)
            for t in trades:
                t["split"] = "TRAIN" if day in train_days else "OOS"
                # Time to resolve in minutes
                if "entry_t" in t and "resolve_t" in t:
                    t["resolve_mins"] = (t["resolve_t"] - t["entry_t"]).total_seconds() / 60
                else:
                    t["resolve_mins"] = 999
            all_trades.extend(trades)

    print(f"  Total trades: {len(all_trades)} (S1={sum(1 for t in all_trades if t['ea']=='S1')}, "
          f"S3={sum(1 for t in all_trades if t['ea']=='S3')}, S4={sum(1 for t in all_trades if t['ea']=='S4')})")
    print()

    # ════════════════════════════════════════════════════════════
    # 1. TIME-OF-DAY ANALYSIS
    # ════════════════════════════════════════════════════════════
    print("=" * 90)
    print("  1. TIME-OF-DAY ANALYSIS (broker hours)")
    print("=" * 90)
    print()

    for ea in ["S1", "S3", "S4"]:
        trades = [t for t in all_trades if t["ea"] == ea]
        if not trades: continue
        print(f"  ── {ea} ──")
        hour_data = defaultdict(lambda: {"n": 0, "w": 0, "pnl": 0})
        for t in trades:
            h = t["hour"]
            hour_data[h]["n"] += 1
            if t["r"] == "W": hour_data[h]["w"] += 1
            hour_data[h]["pnl"] += t["pnl"]
        
        print(f"  {'Hour':>6}  {'n':>4}  {'WR':>6}  {'P&L':>9}  {'Status'}")
        toxic_hours, golden_hours = [], []
        for h in sorted(hour_data.keys()):
            d = hour_data[h]
            wr = d["w"] / d["n"] * 100 if d["n"] else 0
            status = "🟢 GOLDEN" if wr >= 65 and d["n"] >= 3 else ("🔴 TOXIC" if wr < 40 and d["n"] >= 3 else "")
            if wr >= 65 and d["n"] >= 3: golden_hours.append(h)
            if wr < 40 and d["n"] >= 3: toxic_hours.append(h)
            print(f"  {h:>4}:00  {d['n']:>4}  {wr:>5.1f}%  ${d['pnl']:>+8.1f}  {status}")

        # Impact of skipping toxic hours
        if toxic_hours:
            filtered = [t for t in trades if t["hour"] not in toxic_hours]
            orig_pnl = sum(t["pnl"] for t in trades)
            filt_pnl = sum(t["pnl"] for t in filtered)
            orig_wr = sum(1 for t in trades if t["r"]=="W") / len(trades) * 100
            filt_wr = sum(1 for t in filtered if t["r"]=="W") / len(filtered) * 100 if filtered else 0
            print(f"\n  Skip toxic hours {toxic_hours}:")
            print(f"    Before: n={len(trades)} WR={orig_wr:.1f}% P&L=${orig_pnl:+.1f}")
            print(f"    After:  n={len(filtered)} WR={filt_wr:.1f}% P&L=${filt_pnl:+.1f}")
            print(f"    Impact: {'+' if filt_pnl > orig_pnl else ''}{filt_pnl - orig_pnl:+.1f} P&L, {'+' if filt_wr > orig_wr else ''}{filt_wr - orig_wr:+.1f}% WR")
        print()

    # ════════════════════════════════════════════════════════════
    # 2. TREND STRENGTH ANALYSIS
    # ════════════════════════════════════════════════════════════
    print("=" * 90)
    print("  2. TREND STRENGTH ANALYSIS")
    print("=" * 90)
    print()

    for ea in ["S1", "S3", "S4"]:
        trades = [t for t in all_trades if t["ea"] == ea]
        if not trades: continue
        print(f"  ── {ea} ──")
        
        for metric, label in [("td24", "Trend delta (24 bars)"), ("td60", "Trend delta (60 bars)"), ("atr", "ATR(14)")]:
            vals = sorted(set(round(t[metric], 1) for t in trades))
            if len(vals) < 3: continue
            
            # Split into terciles
            sorted_v = sorted(t[metric] for t in trades)
            t1 = sorted_v[len(sorted_v) // 3]
            t2 = sorted_v[2 * len(sorted_v) // 3]
            
            bins = {"Weak": [], "Medium": [], "Strong": []}
            for t in trades:
                v = t[metric]
                if v <= t1: bins["Weak"].append(t)
                elif v <= t2: bins["Medium"].append(t)
                else: bins["Strong"].append(t)
            
            print(f"\n    {label}:")
            for bname in ["Weak", "Medium", "Strong"]:
                bt = bins[bname]
                if not bt: continue
                n = len(bt)
                w = sum(1 for t in bt if t["r"] == "W")
                wr = w / n * 100
                pnl = sum(t["pnl"] for t in bt)
                rng = f"<={t1:.1f}" if bname == "Weak" else (f"{t1:.1f}-{t2:.1f}" if bname == "Medium" else f">{t2:.1f}")
                print(f"      {bname:<8} ({rng:<12}): n={n:>3}  WR={wr:>5.1f}%  P&L=${pnl:>+8.1f}")
        print()

    # ════════════════════════════════════════════════════════════
    # 3. TRADE DURATION ANALYSIS (time to resolve)
    # ════════════════════════════════════════════════════════════
    print("=" * 90)
    print("  3. TRADE DURATION ANALYSIS")
    print("=" * 90)
    print()

    for ea in ["S1", "S3", "S4"]:
        trades = [t for t in all_trades if t["ea"] == ea and t["resolve_mins"] < 900]
        if not trades: continue
        print(f"  ── {ea} ──")
        
        wins = [t for t in trades if t["r"] == "W"]
        losses = [t for t in trades if t["r"] == "L"]
        
        avg_win_time = sum(t["resolve_mins"] for t in wins) / len(wins) if wins else 0
        avg_loss_time = sum(t["resolve_mins"] for t in losses) / len(losses) if losses else 0
        
        print(f"    Avg win resolves in:  {avg_win_time:.0f} min")
        print(f"    Avg loss resolves in: {avg_loss_time:.0f} min")
        
        # Time-based exit simulation
        print(f"\n    Time-based exit (close at breakeven if not resolved):")
        for max_mins in [15, 30, 60, 120, 240]:
            improved = []
            for t in trades:
                if t["resolve_mins"] <= max_mins:
                    improved.append(t)
                else:
                    # Would have closed at ~breakeven (small loss for spread)
                    improved.append({**t, "pnl": -0.5 * LOTS * CONTRACT, "r": "L"})
            n = len(improved)
            w = sum(1 for t in improved if t["r"] == "W")
            pnl = sum(t["pnl"] for t in improved)
            orig_pnl = sum(t["pnl"] for t in trades)
            print(f"      Close after {max_mins:>3}min: WR={w/n*100:.1f}%  P&L=${pnl:+.1f}  (vs orig ${orig_pnl:+.1f}, diff ${pnl-orig_pnl:+.1f})")
        print()

    # ════════════════════════════════════════════════════════════
    # 4. MAX FAVORABLE EXCURSION — How much profit was "on the table"?
    # ════════════════════════════════════════════════════════════
    print("=" * 90)
    print("  4. MAX FAVORABLE EXCURSION (MFE) — Profit left on table")
    print("=" * 90)
    print()

    for ea in ["S1", "S3", "S4"]:
        trades = [t for t in all_trades if t["ea"] == ea]
        if not trades: continue
        print(f"  ── {ea} ──")
        
        losses = [t for t in trades if t["r"] == "L"]
        if losses:
            loss_mfe = [t["max_fav"] for t in losses]
            avg_mfe = sum(loss_mfe) / len(loss_mfe)
            pct_pos = sum(1 for m in loss_mfe if m > 0.5) / len(loss_mfe) * 100
            print(f"    Losing trades that went positive first:")
            print(f"      {pct_pos:.0f}% of losses saw +$0.50+ before reversing")
            print(f"      Average max favorable excursion on losers: ${avg_mfe:.2f}")
            
            # Breakeven analysis
            for be_level in [0.5, 1.0, 1.5, 2.0, 3.0]:
                saved = [t for t in losses if t["max_fav"] >= be_level]
                if saved:
                    saved_pnl = sum(t["pnl"] for t in saved)
                    print(f"      Move SL to BE after +${be_level}: would save {len(saved)} losses (${-saved_pnl:+.1f} recovered)")
        
        wins = [t for t in trades if t["r"] == "W"]
        if wins:
            win_mfe = [t["max_fav"] for t in wins]
            avg_mfe = sum(win_mfe) / len(win_mfe)
            pct_ran = sum(1 for m in win_mfe if m > t["tp"] * 1.5) / len(win_mfe) * 100 if wins else 0
            print(f"    Winning trades max excursion: avg ${avg_mfe:.2f} (TP=${wins[0]['tp']:.1f})")
        print()

    # ════════════════════════════════════════════════════════════
    # 5. CONSECUTIVE LOSS ANALYSIS
    # ════════════════════════════════════════════════════════════
    print("=" * 90)
    print("  5. CONSECUTIVE LOSS / SIGNAL SPACING")
    print("=" * 90)
    print()

    for ea in ["S1", "S3", "S4"]:
        trades = sorted([t for t in all_trades if t["ea"] == ea], key=lambda x: x["fire"])
        if not trades: continue
        print(f"  ── {ea} ──")
        
        # After N consecutive losses, what's the WR of the next trade?
        streaks = {1: {"n": 0, "w": 0}, 2: {"n": 0, "w": 0}, 3: {"n": 0, "w": 0}}
        consec_losses = 0
        for t in trades:
            for threshold in [1, 2, 3]:
                if consec_losses >= threshold:
                    streaks[threshold]["n"] += 1
                    if t["r"] == "W": streaks[threshold]["w"] += 1
            consec_losses = consec_losses + 1 if t["r"] == "L" else 0
        
        print(f"    After N consecutive losses, WR of next trade:")
        for n_losses, data in streaks.items():
            if data["n"] > 0:
                wr = data["w"] / data["n"] * 100
                print(f"      After {n_losses}+ losses: n={data['n']}  WR={wr:.1f}%  {'(stop trading here?)' if wr < 30 else ''}")
        
        # Signal spacing
        spacings_w, spacings_l = [], []
        for j in range(1, len(trades)):
            gap = (trades[j]["fire"] - trades[j-1]["fire"]).total_seconds() / 60
            if trades[j]["r"] == "W": spacings_w.append(gap)
            else: spacings_l.append(gap)
        if spacings_w and spacings_l:
            print(f"    Avg spacing before WIN:  {sum(spacings_w)/len(spacings_w):.0f} min")
            print(f"    Avg spacing before LOSS: {sum(spacings_l)/len(spacings_l):.0f} min")
        print()

    # ════════════════════════════════════════════════════════════
    # 6. SUMMARY — ACTIONABLE RECOMMENDATIONS
    # ════════════════════════════════════════════════════════════
    print("=" * 90)
    print("  6. ACTIONABLE RECOMMENDATIONS")
    print("=" * 90)
    print()
    print("  (See detailed analysis above for specific numbers)")
    print()

if __name__ == "__main__":
    main()
