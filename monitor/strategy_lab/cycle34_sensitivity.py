"""cycle34_sensitivity.py — perturb each LOCKED param by ±10/20% and re-run.
Overfit-detector: if dropping any single param by 10% tanks results, we're knife-edge.
If most perturbations stay strongly positive, the system is robust.

Reference (locked, COST=$0.50): +$477,382 total / Feb 11 +$45,599 / 94% WR / 20W/2L
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.50

# === DEFAULTS (locked) ===
D = {
    "RNG_N_MIN": 0.5,
    "RNG_MIN":   0.5,
    "SPR_MAX":   0.50,
    "COOLDOWN_SEC": 10,
    "DAILY_DD_STOP": 100.0,
    "M5_LB":     14,
    "CHECK_EVERY": 3,
    "MAX_HOLD_SEC": 2400,
    "LOSS_STREAK_N": 1,
    "LOSS_STREAK_PAUSE": 300,
    "TRAIL_ARM":   5.0,
    "TRAIL_GB":   15.0,
    "MAX_LOSS":   10.0,
    "SKIM":       10.0,
}


def in_zee_window(t):
    mins = t.hour * 60 + t.minute
    return (90 <= mins <= 150) or (1005 <= mins <= 1185)


def load_ticks(path):
    out = []
    with open(path, encoding="utf-8") as f:
        header = next(f).strip()
        is_b = header.startswith("ts_broker")
        for line in f:
            parts = line.strip().split(",")
            if is_b:
                if len(parts) < 4: continue
                try:
                    dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                    ms = int(parts[1]); t_ms = int(dt.timestamp() * 1000) + ms
                    out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
                except: continue
            else:
                if len(parts) < 3: continue
                try:
                    t_str = parts[0]; date_p, time_p = t_str.split(" ")
                    hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
                    dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
                    t_ms = int(dt.timestamp() * 1000) + int(ms_str)
                    out.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
                except: continue
    return out


def build(ticks):
    m1 = []; cur = None
    for tk in ticks:
        m_key = tk["t_ms"] // 60000
        mid = (tk["bid"] + tk["ask"]) / 2
        if cur is None or m_key != cur["m_key"]:
            if cur: m1.append(cur)
            cur = {"m_key": m_key, "o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
                   "t_start_ms": m_key*60000, "t_end_ms": (m_key+1)*60000-1}
        else:
            cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid)
            cur["c"] = mid; cur["v"] += 1
    if cur: m1.append(cur)
    m5 = []
    for i in range(0, len(m1), 5):
        c = m1[i:i+5]
        if not c: continue
        m5.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
                   "h": max(b["h"] for b in c), "l": min(b["l"] for b in c), "c": c[-1]["c"]})
    return m5


def m5_trend(m5, ts_ms, lb):
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < lb: return 0
    W = m5[idx - lb + 1:idx + 1]; h = len(W)//2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run_day(ticks, m5, P):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]; asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []; last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl = 0.0; consec_losses = 0; pause_until_ms = 0
    for k in range(50, len(ticks), P["CHECK_EVERY"]):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000)
        if not in_zee_window(dt): continue
        if asks[k] - bids[k] > P["SPR_MAX"]: continue
        if daily_pnl <= -P["DAILY_DD_STOP"]: continue
        if t < pause_until_ms: continue
        k_60 = bisect.bisect_left(times, t - 60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < P["RNG_MIN"]: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < P["RNG_N_MIN"]: continue
        td = m5_trend(m5, t, P["M5_LB"])
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < P["COOLDOWN_SEC"] * 1000: continue
        entry_px = asks[k] if side == "buy" else bids[k]; entry_ms = t
        peak = 0.0; armed = False; exit_pnl = 0
        for j in range(k, len(ticks)):
            t2 = times[j]
            if (t2 - entry_ms) > P["MAX_HOLD_SEC"] * 1000:
                cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
                exit_pnl = cur; break
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            if cur >= P["SKIM"]: exit_pnl = cur; break
            if cur > peak: peak = cur
            if peak >= P["TRAIL_ARM"]: armed = True
            if armed and cur <= peak - P["TRAIL_GB"]: exit_pnl = cur; break
            if cur <= -P["MAX_LOSS"]: exit_pnl = cur; break
        pnl = exit_pnl - COST
        daily_pnl += pnl
        if pnl > 0: consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= P["LOSS_STREAK_N"]:
                pause_until_ms = t + P["LOSS_STREAK_PAUSE"] * 1000
                consec_losses = 0
        fills.append({"t": dt, "pnl": pnl})
        last_fire_ms[side] = t
    return fills


def total_for(P, day_data):
    total = 0; tf = 0; tw = 0; wd = 0; ld = 0
    for day, ticks, m5 in day_data:
        fills = run_day(ticks, m5, P)
        if not fills: continue
        tf += len(fills); tw += sum(1 for f in fills if f["pnl"]>0)
        s = sum(f["pnl"] for f in fills)
        total += s
        if s > 0: wd += 1
        elif s < 0: ld += 1
    return total, tf, tw, wd, ld


day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
day_data = []
for path in day_files:
    day = Path(path).stem.replace("shano_ticks_", "")
    ticks = load_ticks(path)
    if len(ticks) < 1000: continue
    m5 = build(ticks)
    day_data.append((day, ticks, m5))
print(f"Loaded {len(day_data)} days\n", flush=True)

# Baseline
total, tf, tw, wd, ld = total_for(D, day_data)
baseline_dollars = total * 10
print(f"=== BASELINE ===")
print(f"  ${total*10:+.0f} total, {tf} fills, WR {100*tw/max(1,tf):.0f}%, {wd}W/{ld}L\n")

# Perturbations
INT_PARAMS = {"COOLDOWN_SEC","M5_LB","CHECK_EVERY","MAX_HOLD_SEC","LOSS_STREAK_N","LOSS_STREAK_PAUSE"}
print(f"=== SENSITIVITY (each param perturbed in isolation) ===")
print(f"  {'param':<20}{'baseline':>10}{'-20%':>12}{'-10%':>12}{'+10%':>12}{'+20%':>12}")
for k in D.keys():
    bv = D[k]
    row = [f"{bv}"]
    for delta in [-0.2, -0.1, +0.1, +0.2]:
        P = dict(D)
        nv = bv * (1 + delta)
        if k in INT_PARAMS:
            nv = max(1, int(round(nv)))
        else:
            nv = round(nv, 3)
        P[k] = nv
        total, _, _, wd, ld = total_for(P, day_data)
        row.append(f"${total*10:+.0f} ({wd}/{ld})")
    print(f"  {k:<20}{row[0]:>10}{row[1]:>12}{row[2]:>12}{row[3]:>12}{row[4]:>12}")

print(f"\n=== ROBUSTNESS VERDICT ===")
print(f"  Baseline: ${baseline_dollars:+.0f}")
print(f"  If all perturbations stay > 50% of baseline → ROBUST (not overfit)")
print(f"  If any perturbation tanks below 25% of baseline → KNIFE-EDGE")

print(f"\n=== CYCLE 34 SENSITIVITY DONE ===")
