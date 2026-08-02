"""zee_tick_detector_OOS_hardened.py — re-validate Feb 11 detector with REAL-WORLD costs.

Differences vs zee_tick_detector_OOS.py:
  - COST scaled to actual measured slippage from shano_open_log.csv:
      mean one-way slip = $0.16  (round-trip ≈ $0.32)
      p75  one-way slip = $0.17
      worst typical     = $0.55–$0.88
  - We sweep COST=[0.20 (original), 0.50 (realistic), 0.75 (stress), 1.00 (pessimistic)]
  - Adds broker-side SL=$25 / TP=$50 parachute (won't trigger inside EA's tight CB=$10/SKIM=$10,
    but it's there for connection-loss insurance — shouldn't change backtest outcome materially).
  - Otherwise IDENTICAL to OOS detector (locked 14 params).
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")

# Locked detector config (identical to zee_tick_detector_OOS.py)
RNG_N_MIN = 0.5
RNG_MIN = 0.5
SPR_MAX = 0.50
COOLDOWN_SEC = 10
TRAIL_ARM = 5.0
TRAIL_GB = 15.0
MAX_LOSS = 10.0
SKIM = 10.0
MAX_HOLD_SEC = 2400
M5_LB = 14
CHECK_EVERY = 3
DAILY_DD_STOP = 100.0
LOSS_STREAK_N = 1
LOSS_STREAK_PAUSE = 300

# Broker-side parachute (sanity check — shouldn't fire inside EA's CB=$10 / SKIM=$10)
BROKER_SL = 25.0
BROKER_TP = 50.0


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
                    ms = int(parts[1])
                    t_ms = int(dt.timestamp() * 1000) + ms
                    out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
                except: continue
            else:
                if len(parts) < 3: continue
                try:
                    t_str = parts[0]
                    date_p, time_p = t_str.split(" ")
                    hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
                    dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
                    t_ms = int(dt.timestamp() * 1000) + int(ms_str)
                    out.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
                except: continue
    return out


def build_m1_m5(ticks):
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
    for b in m1: b["t"] = datetime.fromtimestamp(b["m_key"] * 60)
    m5 = []
    for i in range(0, len(m1), 5):
        c = m1[i:i+5]
        if not c: continue
        m5.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
                   "o": c[0]["o"], "h": max(b["h"] for b in c),
                   "l": min(b["l"] for b in c), "c": c[-1]["c"],
                   "v": sum(b["v"] for b in c), "t": c[0]["t"]})
    return m1, m5


def m5_trend(m5, ts_ms, lb=M5_LB):
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


def run_day(ticks, m5, COST):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl = 0.0
    consec_losses = 0
    pause_until_ms = 0
    parachute_hits = {"SL": 0, "TP": 0}
    for k in range(50, len(ticks), CHECK_EVERY):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000)
        if not in_zee_window(dt): continue
        if asks[k] - bids[k] > SPR_MAX: continue
        if daily_pnl <= -DAILY_DD_STOP: continue
        if t < pause_until_ms: continue
        k_60 = bisect.bisect_left(times, t - 60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]
        w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: continue
        td = m5_trend(m5, t)
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        entry_px = asks[k] if side == "buy" else bids[k]
        entry_ms = t
        peak = 0.0; armed = False
        exit_pnl = 0; exit_why = "EOD"
        for j in range(k, len(ticks)):
            t2 = times[j]
            if (t2 - entry_ms) > MAX_HOLD_SEC * 1000:
                cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
                exit_pnl = cur; exit_why = "EOH"; break
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            # Broker-side parachute — should NOT fire inside EA's CB=$10/SKIM=$10
            if cur <= -BROKER_SL:
                exit_pnl = cur; exit_why = "BROKER_SL"; parachute_hits["SL"] += 1; break
            if cur >= BROKER_TP:
                exit_pnl = cur; exit_why = "BROKER_TP"; parachute_hits["TP"] += 1; break
            # EA-driven exits
            if cur >= SKIM: exit_pnl = cur; exit_why = "SKIM"; break
            if cur > peak: peak = cur
            if peak >= TRAIL_ARM: armed = True
            if armed and cur <= peak - TRAIL_GB: exit_pnl = cur; exit_why = "TRAIL"; break
            if cur <= -MAX_LOSS: exit_pnl = cur; exit_why = "CB"; break
        pnl = exit_pnl - COST
        daily_pnl += pnl
        if pnl > 0:
            consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= LOSS_STREAK_N:
                pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                consec_losses = 0
        fills.append({"t": dt, "side": side, "pnl": pnl, "why": exit_why, "peak": peak})
        last_fire_ms[side] = t
    return fills, parachute_hits


def run_with_cost(COST):
    day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    total_pnl_raw = 0.0
    total_n = 0; total_w = 0
    total_parachute = {"SL": 0, "TP": 0}
    days_pos = 0; days_neg = 0
    feb11_pnl = 0.0
    for path in day_files:
        day = Path(path).stem.replace("shano_ticks_", "")
        ticks = load_ticks(path)
        if len(ticks) < 1000: continue
        m1, m5 = build_m1_m5(ticks)
        fills, parachute = run_day(ticks, m5, COST)
        n = len(fills); w = sum(1 for f in fills if f["pnl"] > 0)
        tot = sum(f["pnl"] for f in fills)
        total_pnl_raw += tot
        total_n += n; total_w += w
        total_parachute["SL"] += parachute["SL"]
        total_parachute["TP"] += parachute["TP"]
        if tot > 0: days_pos += 1
        elif tot < 0: days_neg += 1
        if day == "2026-02-11":
            feb11_pnl = tot
    return {
        "cost": COST,
        "n": total_n,
        "w": total_w,
        "wr": 100 * total_w / max(1, total_n),
        "raw_pnl": total_pnl_raw,
        "pnl_010lot": total_pnl_raw * 10,
        "pnl_001lot": total_pnl_raw,
        "days_pos": days_pos,
        "days_neg": days_neg,
        "feb11_raw": feb11_pnl,
        "feb11_001lot": feb11_pnl,
        "parachute_sl": total_parachute["SL"],
        "parachute_tp": total_parachute["TP"],
    }


print("=" * 95)
print(" Cost sweep — does the Feb 11 detector survive realistic slippage?")
print("=" * 95)
print(" Measured one-way slip from 17 fills (shano_open_log.csv):")
print("   mean=$0.16   median≈$0.05   p75≈$0.17   p95≈$0.55   worst=$0.88")
print(" So round-trip $0.20 ≈ original optimistic; $0.50–$0.75 ≈ realistic; $1.00 ≈ pessimistic.")
print()
header = f"{'COST/trade':>11} {'fills':>6} {'wins':>5} {'WR%':>5} {'raw_pnl':>10} " \
         f"{'@0.01lot':>9} {'@0.10lot':>10} {'days+':>5} {'days-':>5} {'Feb11raw':>9} {'parach_SL':>9} {'parach_TP':>9}"
print(header)
print("-" * len(header))
results = []
for cost in [0.20, 0.50, 0.75, 1.00]:
    r = run_with_cost(cost)
    results.append(r)
    print(f"  ${r['cost']:>5.2f}/tr  {r['n']:>6} {r['w']:>5} {r['wr']:>4.1f}% "
          f"${r['raw_pnl']:>+9.2f} ${r['pnl_001lot']:>+8.2f} ${r['pnl_010lot']:>+9.0f} "
          f"{r['days_pos']:>5} {r['days_neg']:>5} ${r['feb11_raw']:>+8.2f} "
          f"{r['parachute_sl']:>9} {r['parachute_tp']:>9}")
print()
print("=" * 95)
print(" Verdict at REALISTIC ($0.50 round-trip slippage + commission):")
print("=" * 95)
realistic = next(r for r in results if r["cost"] == 0.50)
days_total = realistic["days_pos"] + realistic["days_neg"]
print(f"  At 0.01 lots (Shano's live):  ${realistic['pnl_001lot']:+.2f} across {days_total} trading days")
print(f"  At 0.10 lots (paper):         ${realistic['pnl_010lot']:+,.0f}")
print(f"  Win-rate:                     {realistic['wr']:.1f}%  ({realistic['w']}W / {realistic['n']-realistic['w']}L)")
print(f"  Positive days:                {realistic['days_pos']}/{days_total}")
print(f"  Broker-SL hits:               {realistic['parachute_sl']} (should be 0 — EA CB=$10 fires first)")
print(f"  Broker-TP hits:               {realistic['parachute_tp']} (should be 0 — EA SKIM=$10 fires first)")
print()
print(" If raw_pnl stays positive at COST=$0.75 → strong edge, Monday-deployable.")
print(" If raw_pnl flips negative at COST=$0.50 → edge marginal, watch live first 30 trades.")
