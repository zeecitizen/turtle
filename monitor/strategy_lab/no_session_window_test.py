"""no_session_window_test.py — does removing the EA's session windows IMPROVE
performance (catching more setups across the day) or DEGRADE it (more chop /
overnight low-liquidity whipsaws)?

Zee asked this 2026-06-02 morning: his Feb 11 broker statement shows 18+ hours
of activity but actually clusters into the same two windows our EA uses
(01:30-02:30 + 16:45-19:45 broker). The 14-hour mid-day gap in his real data
matches our defaults. But empirical proof > my analysis — let me actually run it.

Compares 4 configurations across 23 days of real tick data:
  A) Current EA: BOTH sessions (S1 + S2)
  B) S2 only (the "afternoon-burst-only" theory)
  C) S1 only (the "early-Europe-only" theory)
  D) ALL DAY: no session filter at all (Zee's hypothesis tested)

Everything else (rng60, M5 trend, spread, cooldown, trail) stays identical.
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.50  # realistic round-trip slippage + commission

# Locked detector config (same as zee_tick_detector_OOS_hardened.py)
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

# Session window configs (broker time = UTC for these tick files, captured on Exness GMT+0)
CONFIGS = {
    "A_both_sessions":   {"windows": [(90, 150), (1005, 1185)]},  # current EA default
    "B_S2_only":         {"windows": [(1005, 1185)]},
    "C_S1_only":         {"windows": [(90, 150)]},
    "D_all_day_24h":     {"windows": [(0, 1440)]},  # Zee's hypothesis
}


def in_windows(t, windows):
    if not windows: return True
    mins = t.hour * 60 + t.minute
    for s, e in windows:
        if s <= mins <= e:
            return True
    return False


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


def run_day(ticks, m5, windows):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl = 0.0
    consec_losses = 0
    pause_until_ms = 0
    for k in range(50, len(ticks), CHECK_EVERY):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000)
        if not in_windows(dt, windows): continue
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
        exit_pnl = 0
        for j in range(k, len(ticks)):
            t2 = times[j]
            if (t2 - entry_ms) > MAX_HOLD_SEC * 1000:
                cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
                exit_pnl = cur; break
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            if cur >= SKIM: exit_pnl = cur; break
            if cur > peak: peak = cur
            if peak >= TRAIL_ARM: armed = True
            if armed and cur <= peak - TRAIL_GB: exit_pnl = cur; break
            if cur <= -MAX_LOSS: exit_pnl = cur; break
        pnl = exit_pnl - COST
        daily_pnl += pnl
        if pnl > 0:
            consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= LOSS_STREAK_N:
                pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                consec_losses = 0
        fills.append({"t": dt, "side": side, "pnl": pnl})
        last_fire_ms[side] = t
    return fills


def run_config(name, windows):
    day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    total_pnl = 0.0; total_n = 0; total_w = 0
    days_pos = 0; days_neg = 0
    feb11_pnl = 0.0
    worst_day = ("", 0.0)
    best_day = ("", 0.0)
    for path in day_files:
        day = Path(path).stem.replace("shano_ticks_", "")
        ticks = load_ticks(path)
        if len(ticks) < 1000: continue
        m1, m5 = build_m1_m5(ticks)
        fills = run_day(ticks, m5, windows)
        n = len(fills); w = sum(1 for f in fills if f["pnl"] > 0)
        tot = sum(f["pnl"] for f in fills)
        total_pnl += tot; total_n += n; total_w += w
        if tot > 0: days_pos += 1
        elif tot < 0: days_neg += 1
        if tot < worst_day[1]: worst_day = (day, tot)
        if tot > best_day[1]: best_day = (day, tot)
        if day == "2026-02-11":
            feb11_pnl = tot
    return {
        "config": name,
        "fills": total_n,
        "wins": total_w,
        "wr": 100 * total_w / max(1, total_n),
        "pnl_001": total_pnl,
        "pnl_010": total_pnl * 10,
        "days_pos": days_pos,
        "days_neg": days_neg,
        "feb11": feb11_pnl,
        "worst_day": worst_day,
        "best_day": best_day,
    }


print("=" * 100)
print(f" SESSION-WINDOW SENSITIVITY — does removing session filter help or hurt?")
print(f" Test cost: ${COST}/trade (realistic slippage). Other filters unchanged.")
print("=" * 100)
print()
header = f"{'Config':<22} {'Fills':>7} {'WR%':>6} {'@0.01lot':>11} {'@0.10lot':>11} " \
         f"{'Days+':>6} {'Days-':>6} {'Feb11':>9} {'Worst':>15} {'Best':>14}"
print(header)
print("-" * len(header))
results = []
for name, cfg in CONFIGS.items():
    r = run_config(name, cfg["windows"])
    results.append(r)
    worst_str = f"{r['worst_day'][0][-5:]}:${r['worst_day'][1]:+.0f}"
    best_str = f"{r['best_day'][0][-5:]}:${r['best_day'][1]:+.0f}"
    print(f"{r['config']:<22} {r['fills']:>7} {r['wr']:>5.1f}% "
          f"${r['pnl_001']:>+9.2f} ${r['pnl_010']:>+9.0f} "
          f"{r['days_pos']:>6} {r['days_neg']:>6} "
          f"${r['feb11']:>+7.2f} {worst_str:>15} {best_str:>14}")
print()

A = results[0]; D = results[3]
print(f"=== HEADLINE: A (current) vs D (24h Zee's hypothesis) ===")
delta = D['pnl_001'] - A['pnl_001']
print(f"  Going 24h adds:  {D['fills']-A['fills']:+d} fills,  "
      f"WR shift: {D['wr']-A['wr']:+.1f}pp,  "
      f"PnL @0.01: ${delta:+.2f}  ({'BETTER' if delta>0 else 'WORSE'})")
print(f"  Days going negative: {A['days_neg']} → {D['days_neg']}  "
      f"({'+' if D['days_neg']>A['days_neg'] else '-'}{abs(D['days_neg']-A['days_neg'])})")
print()
print(f"=== If D > A: Zee was right; relax the session filter. ===")
print(f"=== If D < A: the gap hours bleed; keep the windows. ===")
