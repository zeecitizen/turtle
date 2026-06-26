"""cycle4_h1_agree.py — overnight cycle 4.
Require H1 trend direction agrees with M5 trend. Hypothesis: higher-TF confluence
filters chop. Test with sweep of H1_LB.
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.20
RNG_N_MIN = 1.5; RNG_MIN = 1.0; SPR_MAX = 0.40; COOLDOWN_SEC = 60
DAILY_DD_STOP = 35.0; M5_LB = 30; CHECK_EVERY = 20
MAX_HOLD_SEC = 1800
LOSS_STREAK_N = 4; LOSS_STREAK_PAUSE = 1200
TRAIL_ARM = 1.0; TRAIL_GB = 5.0; MAX_LOSS = 5.0; SKIM = 50.0


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
    h1 = []
    for i in range(0, len(m5), 12):  # 60 min = 12 M5
        c = m5[i:i+12]
        if not c: continue
        h1.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
                   "h": max(b["h"] for b in c), "l": min(b["l"] for b in c), "c": c[-1]["c"]})
    return m5, h1


def hh_hl(bars, ts_ms, lb):
    idx = -1
    for i, b in enumerate(bars):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < lb: return 0
    W = bars[idx - lb + 1:idx + 1]; h = len(W)//2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run_day(ticks, m5, h1, h1_lb, require_agree, allow_neutral):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]; asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []; last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl = 0.0; consec_losses = 0; pause_until_ms = 0
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
        w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: continue
        td5 = hh_hl(m5, t, M5_LB)
        if td5 == 0: continue
        if require_agree:
            td_h1 = hh_hl(h1, t, h1_lb)
            if td_h1 != td5:
                if not (allow_neutral and td_h1 == 0): continue
        side = "buy" if td5 > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        entry_px = asks[k] if side == "buy" else bids[k]; entry_ms = t
        peak = 0.0; armed = False; exit_pnl = 0
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
        if pnl > 0: consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= LOSS_STREAK_N:
                pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                consec_losses = 0
        fills.append({"t": dt, "pnl": pnl})
        last_fire_ms[side] = t
    return fills


day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
print(f"Loading {len(day_files)} days...", flush=True)
day_data = []
for path in day_files:
    day = Path(path).stem.replace("shano_ticks_", "")
    ticks = load_ticks(path)
    if len(ticks) < 1000: continue
    m5, h1 = build(ticks)
    day_data.append((day, ticks, m5, h1))
print(f"  Loaded {len(day_data)} days\n", flush=True)

print(f"  {'h1_lb':>5} {'agree':>5} {'allow0':>6} | {'fills':>5} {'WR%':>4} {'tot$':>7} {'Feb11$':>8} {'OOS$':>7} {'win_d':>5} {'loss_d':>6}", flush=True)
# baseline: no h1 filter
configs = [(0, False, False)]  # baseline
for h1_lb in [3, 4, 6, 8, 12]:
    configs.append((h1_lb, True, False))   # strict agreement
    configs.append((h1_lb, True, True))    # allow neutral H1

best = (-99999, None)
for cfg in configs:
    h1_lb, agree, allow_neutral = cfg
    feb_pnl = 0; oos_pnl = 0; tot_fills = 0; tot_wins = 0; win_d = 0; loss_d = 0
    for day, ticks, m5, h1 in day_data:
        fills = run_day(ticks, m5, h1, h1_lb, agree, allow_neutral)
        if not fills: continue
        n = len(fills); w = sum(1 for f in fills if f["pnl"]>0)
        tot = sum(f["pnl"] for f in fills)
        tot_fills += n; tot_wins += w
        if day == "2026-02-11": feb_pnl = tot
        else: oos_pnl += tot
        if tot > 0: win_d += 1
        elif tot < 0: loss_d += 1
    grand = feb_pnl + oos_pnl
    wr = 100 * tot_wins / max(1, tot_fills)
    print(f"  {h1_lb:>5} {str(agree):>5} {str(allow_neutral):>6} | {tot_fills:>5} {wr:>3.0f}% {grand*10:>+7.0f} {feb_pnl*10:>+8.0f} {oos_pnl*10:>+7.0f} {win_d:>5} {loss_d:>6}", flush=True)
    if grand > best[0]: best = (grand, cfg)

print(f"\n=== CYCLE 4 BEST: {best[1]} → ${best[0]*10:+.0f} ===", flush=True)
