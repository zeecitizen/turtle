"""zee_tick_detector_v2.py — add Zee time-windows + sweep rng_norm + better exits.
Test if the tick-level expansion detector + Zee-style exit can match $300+ in his
4-hour trading windows.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS_PATH = COMMON / "shano_ticks_2026-02-11.csv"
COST = 0.20


def in_zee_window(t):
    mins = t.hour * 60 + t.minute
    return (90 <= mins <= 150) or (1005 <= mins <= 1185)


print("Loading..."); ticks=[]
with open(TICKS_PATH, encoding="utf-8") as f:
    next(f)
    for line in f:
        parts = line.strip().split(",")
        if len(parts) < 3: continue
        try:
            t_str = parts[0]; date_p, time_p = t_str.split(" ")
            hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
            dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
            t_ms = int(dt.timestamp() * 1000) + int(ms_str)
            ticks.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
        except: continue
print(f"  {len(ticks):,} ticks")
m1=[]; cur=None
for tk in ticks:
    m_key = tk["t_ms"] // 60000; mid = (tk["bid"] + tk["ask"]) / 2
    if cur is None or m_key != cur["m_key"]:
        if cur: m1.append(cur)
        cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
               "t_start_ms": m_key*60000, "t_end_ms": (m_key+1)*60000-1}
    else:
        cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid)
        cur["c"] = mid; cur["v"] += 1
if cur: m1.append(cur)
for b in m1: b["t"] = datetime.fromtimestamp(b["m_key"] * 60)
m5=[]
for i in range(0, len(m1), 5):
    c = m1[i:i+5]
    if not c: continue
    m5.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
               "o": c[0]["o"], "h": max(b["h"] for b in c), "l": min(b["l"] for b in c),
               "c": c[-1]["c"], "v": sum(b["v"] for b in c), "t": c[0]["t"]})
print(f"  {len(m1)} M1 / {len(m5)} M5\n")

times=[t["t_ms"] for t in ticks]; bids=[t["bid"] for t in ticks]
asks=[t["ask"] for t in ticks];   mids=[(t["bid"]+t["ask"])/2 for t in ticks]


def m5_trend_at(ts_ms, lb=30):
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < lb: return 0
    W = m5[idx - lb + 1: idx + 1]; h = len(W)//2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def features_at_tick(k):
    if k < 50: return None
    entry_ms = times[k]
    k_60 = bisect.bisect_left(times, entry_ms - 60000)
    k_300 = bisect.bisect_left(times, entry_ms - 300000)
    if k_60 >= k - 1: return None
    w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
    rng60 = max(w60) - min(w60)
    range_300 = max(w300) - min(w300) if w300 else rng60
    rng60_norm = rng60 / max(0.10, range_300/5.0)
    v60_raw = mids[k-1] - mids[k_60]
    # position of current price in 60s range
    pos_in_60 = (mids[k-1] - min(w60)) / max(0.01, rng60)
    return {"rng60": rng60, "rng60_norm": rng60_norm, "v60_raw": v60_raw,
            "spr": asks[k] - bids[k], "pos_in_60": pos_in_60}


def run(rng_n_min, rng_min, cd, tarm, tgb, ml, choose_side_by="m5",
        skim=50.0, max_hold=1800, every=20):
    """choose_side_by: 'm5' (trade m5 trend) | 'pos' (mean-revert from extremes)
                       | 'm5_pos' (m5 trend, but only at the favorable end of 60s range)"""
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    for k in range(50, len(ticks), every):
        t = times[k]
        dt = datetime.fromtimestamp(t/1000)
        if not in_zee_window(dt): continue
        f = features_at_tick(k)
        if not f: continue
        if f["spr"] > 0.40: continue
        if f["rng60_norm"] < rng_n_min: continue
        if f["rng60"] < rng_min: continue
        td = m5_trend_at(t)
        # Pick side
        if choose_side_by == "m5":
            if td == 0: continue
            side = "buy" if td > 0 else "sell"
        elif choose_side_by == "pos":
            # mean-revert: buy when current is at low end of 60s range, sell at high
            if f["pos_in_60"] <= 0.25: side = "buy"
            elif f["pos_in_60"] >= 0.75: side = "sell"
            else: continue
        elif choose_side_by == "m5_pos":
            if td == 0: continue
            if td > 0 and f["pos_in_60"] <= 0.40: side = "buy"
            elif td < 0 and f["pos_in_60"] >= 0.60: side = "sell"
            else: continue
        else: continue
        if t - last_fire_ms[side] < cd * 1000: continue
        # exit
        entry_px = asks[k] if side == "buy" else bids[k]; entry_ms = t
        peak = 0.0; armed = False; exit_pnl = 0; exit_why = "EOD"
        for j in range(k, len(ticks)):
            t2 = times[j]
            if (t2 - entry_ms) > max_hold * 1000:
                cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
                exit_pnl = cur; exit_why = "EOH"; break
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            if cur >= skim: exit_pnl = cur; exit_why = "SKIM"; break
            if cur > peak: peak = cur
            if peak >= tarm: armed = True
            if armed and cur <= peak - tgb: exit_pnl = cur; exit_why = "TRAIL"; break
            if cur <= -ml: exit_pnl = cur; exit_why = "CB"; break
        fills.append({"t": dt, "side": side, "pnl": exit_pnl - COST, "why": exit_why,
                      "peak": peak, "rng60_norm": f["rng60_norm"], "pos": f["pos_in_60"]})
        last_fire_ms[side] = t
    return fills


ZEE_MIN = [("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
           ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
           ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
           ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
           ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
           ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell")]

print(f"  {'mode':<8} {'rng_n':>5} {'rng':>4} {'cd':>4} {'arm':>4} {'gb':>4} {'CB':>4} | "
      f"{'n':>3} {'W':>3} {'L':>3} {'WR':>3} {'raw':>7} {'dollars':>8} {'cap':>3}")

best = (-9999, None, None, 0)
for mode in ["m5", "pos", "m5_pos"]:
    for rng_n in [1.5, 2.0, 2.5]:
        for rng in [1.5, 2.5, 4.0]:
            for cd in [60, 120, 300]:
                for tgb in [2.0, 3.0, 5.0]:
                    for ml in [2.0, 3.0, 5.0]:
                        cfg = (rng_n, rng, cd, 1.0, tgb, ml, mode)
                        fills = run(*cfg)
                        n = len(fills)
                        if n < 5 or n > 100: continue
                        w = sum(1 for f in fills if f["pnl"]>0); l = n - w
                        tot = sum(f["pnl"] for f in fills)
                        matched = 0
                        for hm, sd in ZEE_MIN:
                            hh, mm = map(int, hm.split(":")); tmin = hh*60+mm
                            for f in fills:
                                if f["side"] == sd and abs(f["t"].hour*60+f["t"].minute - tmin) <= 3:
                                    matched += 1; break
                        if tot > -50 or matched >= 5:  # surface only promising rows
                            print(f"  {mode:<8} {rng_n:>5.1f} {rng:>4.1f} {cd:>4} {1.0:>4.1f} {tgb:>4.1f} {ml:>4.1f} | "
                                  f"{n:>3} {w:>3} {l:>3} {100*w/n:>2.0f}% {tot:>+7.1f} {tot*10:>+8.0f} {matched:>3}")
                        if tot > best[0]:
                            best = (tot, cfg, fills, matched)

print(f"\n=== BEST: mode={best[1][6]} rng_n={best[1][0]} rng={best[1][1]} cd={best[1][2]} "
      f"gb={best[1][4]} CB={best[1][5]} → raw ${best[0]:+.2f} = ${best[0]*10:+.0f} dollars ===")
print(f"  Captured {best[3]}/24 Zee setups")
print(f"\n  Per-fill detail:")
print(f"  {'t':>9} {'side':>4} {'raw':>6} {'dol':>7} {'why':<8} {'peak':>6} {'rngN':>5} {'pos':>5}")
for f in best[2]:
    print(f"  {f['t'].strftime('%H:%M:%S'):>9} {f['side']:>4} {f['pnl']:>+6.2f} {f['pnl']*10:>+7.1f} "
          f"{f['why']:<8} {f['peak']:>+6.2f} {f['rng60_norm']:>5.2f} {f['pos']:>5.2f}")
