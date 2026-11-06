"""zee_tick_OOS_exit_sweep.py — keep detector locked, sweep ONLY exit params across
all 23 days. Find the exit that maximizes total $ AND smoothes day-distribution.
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.20
RNG_N_MIN = 1.5; RNG_MIN = 1.5
SPR_MAX = 0.40
COOLDOWN_SEC = 60
DAILY_DD_STOP = 35.0
M5_LB = 30
CHECK_EVERY = 20


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
                   "h": max(b["h"] for b in c), "l": min(b["l"] for b in c),
                   "c": c[-1]["c"]})
    return m5


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


def run_day(ticks, m5, trail_arm, trail_gb, max_loss, skim, max_hold_sec, dd_stop):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []; last_fire_ms = {"buy": 0, "sell": 0}; daily_pnl = 0.0
    for k in range(50, len(ticks), CHECK_EVERY):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000)
        if not in_zee_window(dt): continue
        if asks[k] - bids[k] > SPR_MAX: continue
        if daily_pnl <= -dd_stop: continue
        k_60 = bisect.bisect_left(times, t - 60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: continue
        td = m5_trend(m5, t)
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        entry_px = asks[k] if side == "buy" else bids[k]; entry_ms = t
        peak = 0.0; armed = False; exit_pnl = 0; exit_why = "EOD"
        for j in range(k, len(ticks)):
            t2 = times[j]
            if (t2 - entry_ms) > max_hold_sec * 1000:
                cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
                exit_pnl = cur; exit_why = "EOH"; break
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            if cur >= skim: exit_pnl = cur; exit_why = "SKIM"; break
            if cur > peak: peak = cur
            if peak >= trail_arm: armed = True
            if armed and cur <= peak - trail_gb: exit_pnl = cur; exit_why = "TRAIL"; break
            if cur <= -max_loss: exit_pnl = cur; exit_why = "CB"; break
        pnl = exit_pnl - COST
        daily_pnl += pnl
        fills.append({"t": dt, "pnl": pnl, "why": exit_why, "peak": peak})
        last_fire_ms[side] = t
    return fills


# Load all
day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
print(f"Loading {len(day_files)} days...")
day_data = []
for path in day_files:
    day = Path(path).stem.replace("shano_ticks_", "")
    ticks = load_ticks(path)
    if len(ticks) < 1000: continue
    m5 = build(ticks)
    day_data.append((day, ticks, m5))
print(f"  Loaded {len(day_data)} days\n")

# Sweep exit configs
print(f"  {'arm':>4} {'gb':>4} {'CB':>4} {'skim':>5} {'dd':>4} | "
      f"{'fills':>5} {'WR%':>4} {'NETraw':>7} {'NET$':>7} {'wins':>4} {'losses':>4} {'sharp':>5}")
configs = []
for arm in [0.5, 1.0, 1.5, 2.0]:
    for gb in [1.0, 2.0, 3.0, 5.0]:
        for ml in [2.0, 3.0, 5.0]:
            for skim in [5.0, 10.0, 20.0, 50.0]:
                for dd in [25.0, 35.0, 50.0]:
                    configs.append((arm, gb, ml, skim, dd))

best = (-99999, None, None)
results = []
for cfg in configs:
    arm, gb, ml, skim, dd = cfg
    day_pnls = []
    total_fills = 0; total_wins = 0
    for day, ticks, m5 in day_data:
        fills = run_day(ticks, m5, arm, gb, ml, skim, 1800, dd)
        if not fills: continue
        n = len(fills); w = sum(1 for f in fills if f["pnl"]>0)
        tot = sum(f["pnl"] for f in fills)
        day_pnls.append(tot)
        total_fills += n; total_wins += w
    if not day_pnls: continue
    grand = sum(day_pnls)
    if total_fills < 100: continue
    win_days = sum(1 for p in day_pnls if p > 0)
    loss_days = sum(1 for p in day_pnls if p < 0)
    # Sharpe-like: mean/std of day PnL
    avg_day = grand / len(day_pnls)
    var = sum((p - avg_day)**2 for p in day_pnls) / max(1, len(day_pnls)-1)
    sharpe = avg_day / (var**0.5 + 0.01)
    results.append((grand, cfg, win_days, loss_days, sharpe, total_fills, total_wins))
    if grand > best[0]: best = (grand, cfg, day_pnls)

# Print top 15 by total
results.sort(key=lambda r: -r[0])
for r in results[:20]:
    grand, cfg, wd, ld, sh, tf, tw = r
    arm, gb, ml, skim, dd = cfg
    wr = 100 * tw / max(1, tf)
    print(f"  {arm:>4.1f} {gb:>4.1f} {ml:>4.1f} {skim:>5.1f} {dd:>4.0f} | "
          f"{tf:>5} {wr:>3.0f}% {grand:>+7.1f} {grand*10:>+7.0f} {wd:>4} {ld:>6} {sh:>+5.2f}")

print(f"\n=== TOP CONFIG: {best[1]} → ${best[0]*10:+.0f} dollars over {len(best[2])} days ===")
print(f"  Day pnls (raw): {[f'{p:+.1f}' for p in best[2]]}")
