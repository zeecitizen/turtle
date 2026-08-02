"""zee_tick_forensics_real.py — Phase 1 of Option A.

For each of Zee's 27 Feb 11 entries on REAL Blueberry ticks, measure tick-level
features in the seconds before/at the entry:

  v3       : 3-sec price velocity (mid_now - mid_3s_ago)
  v10      : 10-sec price velocity
  v30      : 30-sec price velocity
  rng60    : 60-sec price range (high - low of mid in last 60s)
  rng60_norm: rng60 / 5-min avg 60s-range  (was 60s tight relative to recent?)
  spr_at   : spread (ask-bid) at entry
  spr_avg60: avg spread last 60s
  spr_ratio: spr_at / spr_avg60  (tightening = ratio < 1)
  tick_density: ticks/sec over last 10s  (intensity)
  v_accel  : v3 - (v10/3.33)  (positive = accelerating into entry direction)

Output: per-entry table + ALL/buy/sell aggregates + suggested thresholds.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
import statistics
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICKS_PATH = COMMON / "shano_ticks_2026-02-11.csv"

ZEE = [
    ("01:32:19","buy",5045.07), ("01:59:04","buy",5042.17), ("02:09:38","sell",5040.68),
    ("02:29:02","buy",5039.03), ("16:49:07","buy",5047.93), ("16:52:21","buy",5050.77),
    ("16:54:10","buy",5056.74), ("16:58:03","buy",5064.26), ("17:02:45","buy",5055.71),
    ("17:36:11","buy",5056.53), ("17:36:13","buy",5057.05), ("17:37:26","buy",5045.82),
    ("17:49:59","buy",5048.32), ("18:24:18","buy",5059.26), ("18:41:50","buy",5078.10),
    ("19:08:59","sell",5083.28),("19:11:05","sell",5083.39),("19:11:51","sell",5083.79),
    ("19:20:34","sell",5084.21),("19:26:06","sell",5089.16),("19:29:31","buy",5086.34),
    ("19:32:48","buy",5084.71), ("19:36:19","buy",5082.91),("19:38:39","buy",5083.28),
    ("19:38:59","buy",5086.33), ("19:41:59","sell",5091.09),("19:42:26","sell",5093.18),
]

print(f"Loading Blueberry Feb 11 ticks...")
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
print(f"  {len(ticks):,} ticks loaded\n")

times = [t["t_ms"] for t in ticks]
bids  = [t["bid"]   for t in ticks]
asks  = [t["ask"]   for t in ticks]
mids  = [(t["bid"] + t["ask"]) / 2 for t in ticks]


def zee_to_ms(hms):
    hh, mm, ss = map(int, hms.split(":"))
    return int(datetime(2026,2,11,hh,mm,ss).timestamp() * 1000)


def features_at(entry_k, side):
    """Compute features looking BACK from entry tick."""
    if entry_k < 5: return None
    entry_ms = times[entry_k]
    # find back-pointers for 3s / 10s / 30s / 60s
    k_3  = bisect.bisect_left(times, entry_ms - 3000)
    k_10 = bisect.bisect_left(times, entry_ms - 10000)
    k_30 = bisect.bisect_left(times, entry_ms - 30000)
    k_60 = bisect.bisect_left(times, entry_ms - 60000)
    k_300 = bisect.bisect_left(times, entry_ms - 300000)
    if k_60 >= entry_k - 1: return None

    m_now = mids[entry_k - 1]
    m_3   = mids[k_3] if k_3 < entry_k else m_now
    m_10  = mids[k_10] if k_10 < entry_k else m_now
    m_30  = mids[k_30] if k_30 < entry_k else m_now
    m_60  = mids[k_60] if k_60 < entry_k else m_now

    # signed velocity in TRADE direction
    if side == "buy":
        v3, v10, v30, v60 = m_now - m_3, m_now - m_10, m_now - m_30, m_now - m_60
    else:
        v3, v10, v30, v60 = m_3 - m_now, m_10 - m_now, m_30 - m_now, m_60 - m_now

    # rng60 (mid)
    w60 = mids[k_60:entry_k]
    rng60 = max(w60) - min(w60)

    # rng60_norm: prior 5 min worth of rolling-60s ranges
    # Estimate as: 5-min total range / 5 (rough proxy for avg 60s range)
    w300 = mids[k_300:entry_k]
    range_300 = max(w300) - min(w300) if w300 else rng60
    rng60_norm = rng60 / max(0.10, range_300 / 5.0)

    # spread features
    spr_at = asks[entry_k] - bids[entry_k]
    w60_spr = [asks[i] - bids[i] for i in range(k_60, entry_k)]
    spr_avg60 = sum(w60_spr) / len(w60_spr) if w60_spr else spr_at
    spr_ratio = spr_at / max(0.01, spr_avg60)

    # tick density
    n_in_10s = entry_k - k_10
    tps = n_in_10s / 10.0

    # acceleration
    v_accel = v3 - (v10 / 10.0 * 3.0)  # v3 vs scaled v10

    return {
        "v3": v3, "v10": v10, "v30": v30, "v60": v60,
        "rng60": rng60, "rng60_norm": rng60_norm,
        "spr_at": spr_at, "spr_avg60": spr_avg60, "spr_ratio": spr_ratio,
        "tps": tps, "v_accel": v_accel,
    }


# Run on each Zee entry
print(f"=== TICK-LEVEL FEATURES AT ZEE'S ENTRIES ===")
print(f"  {'time':>9} {'side':>4} {'entry':>8}  "
      f"{'v3':>6} {'v10':>6} {'v30':>6} {'v60':>6} {'rng60':>6} {'rng60n':>6} "
      f"{'spr':>5} {'spr_r':>6} {'tps':>5} {'vacc':>6}")

ent_feats = []
for hms, side, price in ZEE:
    ms = zee_to_ms(hms)
    k = bisect.bisect_left(times, ms)
    if k >= len(ticks): continue
    f = features_at(k, side)
    if not f: continue
    ent_feats.append((hms, side, f))
    print(f"  {hms:>9} {side:>4} {price:>8.2f}  "
          f"{f['v3']:>+6.2f} {f['v10']:>+6.2f} {f['v30']:>+6.2f} {f['v60']:>+6.2f} "
          f"{f['rng60']:>6.2f} {f['rng60_norm']:>6.2f} "
          f"{f['spr_at']:>5.2f} {f['spr_ratio']:>6.2f} {f['tps']:>5.1f} {f['v_accel']:>+6.2f}")


def stats(vals, label):
    if not vals: return
    n = len(vals); mn = min(vals); mx = max(vals)
    md = statistics.median(vals); avg = sum(vals) / n
    p25 = sorted(vals)[n//4]; p75 = sorted(vals)[(3*n)//4]
    print(f"  {label:<14} n={n:>2}  min={mn:>+6.2f}  p25={p25:>+6.2f}  med={md:>+6.2f}  "
          f"avg={avg:>+6.2f}  p75={p75:>+6.2f}  max={mx:>+6.2f}")


print(f"\n=== DISTRIBUTION SUMMARY (ALL ENTRIES, signed in trade direction) ===")
for key in ["v3", "v10", "v30", "v60", "rng60", "rng60_norm", "spr_at", "spr_ratio", "tps", "v_accel"]:
    vals = [f[key] for _,_,f in ent_feats]
    stats(vals, key)

print(f"\n=== BUY-ONLY ===")
buys = [(h,s,f) for h,s,f in ent_feats if s == "buy"]
for key in ["v3", "v10", "rng60_norm", "spr_ratio"]:
    vals = [f[key] for _,_,f in buys]
    stats(vals, key + " (buy)")

print(f"\n=== SELL-ONLY ===")
sells = [(h,s,f) for h,s,f in ent_feats if s == "sell"]
for key in ["v3", "v10", "rng60_norm", "spr_ratio"]:
    vals = [f[key] for _,_,f in sells]
    stats(vals, key + " (sell)")
