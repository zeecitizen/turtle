"""zee_tick_detector_v1.py — Phase 2: tick-level detector based on Phase 1 finding:
  - GATE: M5-30 trend direction (HH/HL) gives the SIDE
  - TRIGGER: rng60_norm >= threshold (volatility expansion)
  - Optional: |v60| in trade direction OR clear mean-revert from extreme
  - Cooldown per side

EXIT: validated wide-trail on Zee's actual entries (+$310 on his 27 → $322 actual).
  - arm=$1.0 raw, gb=$5.0 raw, max_loss=$5.0, skim=$50, max_hold=30min

Compare to Zee's day-shape. Then sweep thresholds.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS_PATH = COMMON / "shano_ticks_2026-02-11.csv"
COST = 0.20

print("Loading...")
ticks = []
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

# Build M1 + M5 from ticks
m1 = []; cur = None
for tk in ticks:
    m_key = tk["t_ms"] // 60000
    mid = (tk["bid"] + tk["ask"]) / 2
    if cur is None or m_key != cur["m_key"]:
        if cur: m1.append(cur)
        cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
               "t_start_ms": m_key * 60000, "t_end_ms": (m_key + 1) * 60000 - 1}
    else:
        cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid)
        cur["c"] = mid; cur["v"] += 1
if cur: m1.append(cur)
for b in m1: b["t"] = datetime.fromtimestamp(b["m_key"] * 60)

# Build M5 by aggregating 5 M1s
m5 = []
for i in range(0, len(m1), 5):
    chunk = m1[i:i+5]
    if not chunk: continue
    m5.append({
        "t_start_ms": chunk[0]["t_start_ms"], "t_end_ms": chunk[-1]["t_end_ms"],
        "o": chunk[0]["o"], "h": max(b["h"] for b in chunk),
        "l": min(b["l"] for b in chunk), "c": chunk[-1]["c"],
        "v": sum(b["v"] for b in chunk),
        "t": chunk[0]["t"],
    })
print(f"  {len(m1)} M1 / {len(m5)} M5 bars\n")

times = [t["t_ms"] for t in ticks]
bids  = [t["bid"]   for t in ticks]
asks  = [t["ask"]   for t in ticks]
mids  = [(t["bid"] + t["ask"]) / 2 for t in ticks]


def m5_trend_at(ts_ms, lookback=30):
    """HH/HL on last `lookback` M5 bars at time ts_ms."""
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < lookback: return 0
    W = m5[idx - lookback + 1: idx + 1]
    h = len(W) // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def features_at_tick(k):
    """At tick k, compute rng60_norm, v60 (raw), spread."""
    if k < 50: return None
    entry_ms = times[k]
    k_60  = bisect.bisect_left(times, entry_ms - 60000)
    k_300 = bisect.bisect_left(times, entry_ms - 300000)
    if k_60 >= k - 1: return None
    m_now = mids[k - 1]; m_60 = mids[k_60]
    w60 = mids[k_60:k]
    rng60 = max(w60) - min(w60)
    w300 = mids[k_300:k]
    range_300 = max(w300) - min(w300) if w300 else rng60
    rng60_norm = rng60 / max(0.10, range_300 / 5.0)
    return {"rng60": rng60, "rng60_norm": rng60_norm, "v60_raw": m_now - m_60,
            "spr": asks[k] - bids[k]}


# === Detector + sweep ===

def run(rng60_norm_min, rng60_min, cooldown_sec, trail_arm, trail_gb, max_loss,
        spr_max=0.40, m5_lookback=30, max_hold_sec=1800, skim=50.0,
        check_every_n_ticks=50):
    """Fire whenever conditions met (every N-th tick to keep speed reasonable)."""
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    for k in range(50, len(ticks), check_every_n_ticks):
        t = times[k]
        f = features_at_tick(k)
        if not f: continue
        if f["spr"] > spr_max: continue
        if f["rng60_norm"] < rng60_norm_min: continue
        if f["rng60"] < rng60_min: continue
        td = m5_trend_at(t, m5_lookback)
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < cooldown_sec * 1000: continue
        # Simulate exit
        entry_px = asks[k] if side == "buy" else bids[k]
        entry_ms = t
        peak = 0.0; armed = False
        exit_reason = "EOD"; exit_pnl = 0.0
        for j in range(k, len(ticks)):
            t2 = times[j]; bid = bids[j]; ask = asks[j]
            if (t2 - entry_ms) > max_hold_sec * 1000:
                cur = (bid - entry_px) if side == "buy" else (entry_px - ask)
                exit_pnl = cur; exit_reason = "EOH"; break
            cur = (bid - entry_px) if side == "buy" else (entry_px - ask)
            if cur >= skim: exit_pnl = cur; exit_reason = "SKIM"; break
            if cur > peak: peak = cur
            if peak >= trail_arm: armed = True
            if armed and cur <= peak - trail_gb:
                exit_pnl = cur; exit_reason = "TRAIL"; break
            if cur <= -max_loss:
                exit_pnl = cur; exit_reason = "CB"; break
        fills.append({"t": datetime.fromtimestamp(t/1000), "side": side,
                      "pnl": exit_pnl - COST, "why": exit_reason, "peak": peak,
                      "rng60_norm": f["rng60_norm"], "v60_raw": f["v60_raw"]})
        last_fire_ms[side] = t
    return fills


ZEE_MIN = [("01:32","buy"),("01:59","buy"),("02:09","sell"),("02:29","buy"),
           ("16:49","buy"),("16:52","buy"),("16:54","buy"),("16:58","buy"),
           ("17:02","buy"),("17:36","buy"),("17:37","buy"),("17:49","buy"),
           ("18:24","buy"),("18:41","buy"),("19:08","sell"),("19:11","sell"),
           ("19:20","sell"),("19:26","sell"),("19:29","buy"),("19:32","buy"),
           ("19:36","buy"),("19:38","buy"),("19:41","sell"),("19:42","sell")]

print(f"  {'rng_n':>5} {'rng':>4} {'cd':>4} {'arm':>4} {'gb':>4} {'CB':>4} | "
      f"{'n':>4} {'W':>3} {'L':>3} {'WR%':>4} {'raw':>7} {'dollars':>8} {'cap':>4}")

best = (-9999, None, None)
for rng_n in [1.2, 1.5, 2.0, 2.5, 3.0]:
    for rng in [1.0, 1.5, 2.0, 3.0]:
        for cd in [120, 300, 600]:
            for tarm in [1.0, 2.0]:
                for tgb in [3.0, 5.0]:
                    for ml in [3.0, 5.0]:
                        cfg = (rng_n, rng, cd, tarm, tgb, ml)
                        fills = run(*cfg)
                        n = len(fills)
                        if n < 5 or n > 200: continue
                        w = sum(1 for f in fills if f["pnl"] > 0); l = n - w
                        tot = sum(f["pnl"] for f in fills)
                        matched = 0
                        for hm, sd in ZEE_MIN:
                            hh, mm = map(int, hm.split(":")); tmin = hh*60+mm
                            for f in fills:
                                if f["side"] == sd and abs(f["t"].hour*60 + f["t"].minute - tmin) <= 3:
                                    matched += 1; break
                        print(f"  {rng_n:>5.1f} {rng:>4.1f} {cd:>4} {tarm:>4.1f} {tgb:>4.1f} {ml:>4.1f} | "
                              f"{n:>4} {w:>3} {l:>3} {100*w/max(1,n):>3.0f}% {tot:>+7.1f} {tot*10:>+8.0f} {matched:>3}")
                        if tot > best[0]:
                            best = (tot, cfg, fills, matched)

print(f"\n=== BEST: {best[1]} → raw ${best[0]:+.2f} = ${best[0]*10:+.0f} dollars at 0.10 lots ===")
print(f"  Captured {best[3]}/24 Zee setups")
print(f"\n  Per-fill detail (first 30):")
print(f"  {'t':>9} {'side':>4} {'raw':>6} {'dol':>7} {'why':<8} {'peak':>6} {'rngN':>5} {'v60':>6}")
for f in best[2][:40]:
    print(f"  {f['t'].strftime('%H:%M:%S'):>9} {f['side']:>4} {f['pnl']:>+6.2f} {f['pnl']*10:>+7.1f} "
          f"{f['why']:<8} {f['peak']:>+6.2f} {f['rng60_norm']:>5.2f} {f['v60_raw']:>+6.2f}")
