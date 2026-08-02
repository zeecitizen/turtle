"""cycle29_stability.py — STABILITY & WALK-FORWARD analysis with locked params.

Tests robustness via:
  1. Per-day Sharpe ratio (daily mean / daily std)
  2. Rolling 7-day windows: best/worst window
  3. Train/test split: tune in first half (we'll just use current params), apply to second
  4. Distribution of fills: how concentrated are wins?
  5. Bootstrap: random sample of fills 1000x to estimate confidence
"""
import sys, glob, bisect, random
import statistics
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.50  # realistic live slippage assumption
RNG_N_MIN = 0.5; RNG_MIN = 0.5
SPR_MAX = 0.50; COOLDOWN_SEC = 10
DAILY_DD_STOP = 100.0; M5_LB = 14; CHECK_EVERY = 3
MAX_HOLD_SEC = 2400
LOSS_STREAK_N = 1; LOSS_STREAK_PAUSE = 300
TRAIL_ARM = 5.0; TRAIL_GB = 15.0; MAX_LOSS = 10.0; SKIM = 10.0


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


def m5_trend(m5, ts_ms):
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < M5_LB: return 0
    W = m5[idx - M5_LB + 1:idx + 1]; h = len(W)//2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run_day(ticks, m5):
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
        td = m5_trend(m5, t)
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
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
        fills.append({"t": dt, "pnl": pnl, "side": side})
        last_fire_ms[side] = t
    return fills


# === Run + analyze ===
print(f"STABILITY ANALYSIS — locked config @ COST=$0.50 (realistic live)\n", flush=True)
day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
all_fills = []
day_pnls = []
day_dates = []
for path in day_files:
    day_str = Path(path).stem.replace("shano_ticks_", "")
    ticks = load_ticks(path)
    if len(ticks) < 1000: continue
    m5 = build(ticks)
    fills = run_day(ticks, m5)
    if not fills: continue
    day_pnl = sum(f["pnl"] for f in fills)
    day_pnls.append(day_pnl)
    day_dates.append(day_str)
    all_fills.extend(fills)

print(f"Total fills: {len(all_fills):,}")
print(f"Total raw P&L: ${sum(day_pnls):.2f}")
print(f"Total $ at 0.10 lots: ${sum(day_pnls)*10:.0f}\n")

# === 1. Sharpe ratio ===
mean_daily = statistics.mean(day_pnls)
stdev_daily = statistics.stdev(day_pnls) if len(day_pnls) > 1 else 0
sharpe = mean_daily / stdev_daily if stdev_daily > 0 else 0
print(f"=== 1. Daily P&L stats ===")
print(f"  Mean daily: ${mean_daily:+.2f} raw = ${mean_daily*10:+.0f} at 0.10L")
print(f"  Stdev:      ${stdev_daily:.2f} raw")
print(f"  Sharpe:     {sharpe:.2f}   (>1 good, >2 great, >3 exceptional)")
print(f"  Min day:    ${min(day_pnls):+.2f}    Max day: ${max(day_pnls):+.2f}\n")

# === 2. Half/half split ===
n = len(day_pnls)
mid = n // 2
first_half = day_pnls[:mid]
second_half = day_pnls[mid:]
print(f"=== 2. Walk-forward halves ===")
print(f"  First {len(first_half)} days  ({day_dates[0]} → {day_dates[mid-1]}): "
      f"sum=${sum(first_half):.2f} raw = ${sum(first_half)*10:+.0f}, "
      f"win days={sum(1 for x in first_half if x>0)}")
print(f"  Last {len(second_half)} days   ({day_dates[mid]} → {day_dates[-1]}): "
      f"sum=${sum(second_half):.2f} raw = ${sum(second_half)*10:+.0f}, "
      f"win days={sum(1 for x in second_half if x>0)}")
print(f"  Both halves positive: {sum(first_half) > 0 and sum(second_half) > 0}\n")

# === 3. Concentration: top-3 days vs rest ===
sorted_pnls = sorted(day_pnls, reverse=True)
top3 = sum(sorted_pnls[:3])
rest = sum(sorted_pnls[3:])
print(f"=== 3. Concentration risk ===")
print(f"  Top 3 days:     ${top3:+.2f} raw = ${top3*10:+.0f} ({100*top3/sum(day_pnls):.0f}%)")
print(f"  Other {n-3} days: ${rest:+.2f} raw = ${rest*10:+.0f} ({100*rest/sum(day_pnls):.0f}%)")
print(f"  If top 3 were 0: total = ${rest:+.2f} raw = ${rest*10:+.0f} (still positive: {rest > 0})\n")

# === 4. Rolling 7-day windows ===
print(f"=== 4. Rolling 7-day P&L windows ===")
windows = []
for i in range(len(day_pnls) - 6):
    w = day_pnls[i:i+7]
    windows.append((day_dates[i], day_dates[i+6], sum(w), sum(1 for x in w if x>0)))
best = max(windows, key=lambda x: x[2])
worst = min(windows, key=lambda x: x[2])
print(f"  Best  7d: {best[0]}→{best[1]} ${best[2]:+.2f} ({best[3]} winning days)")
print(f"  Worst 7d: {worst[0]}→{worst[1]} ${worst[2]:+.2f} ({worst[3]} winning days)")
print(f"  All windows positive: {all(w[2] > 0 for w in windows)}\n")

# === 5. Bootstrap confidence (resample fills) ===
print(f"=== 5. Bootstrap fill confidence (1000 resamples) ===")
random.seed(42)
fill_pnls = [f["pnl"] for f in all_fills]
sims = []
for _ in range(1000):
    sample = random.choices(fill_pnls, k=len(fill_pnls))
    sims.append(sum(sample))
sims.sort()
p5 = sims[50]; p50 = sims[500]; p95 = sims[950]
print(f"  5th pctile:  ${p5:+.2f} raw = ${p5*10:+.0f}")
print(f"  Median:      ${p50:+.2f} raw = ${p50*10:+.0f}")
print(f"  95th pctile: ${p95:+.2f} raw = ${p95*10:+.0f}")
print(f"  Bootstrap range covers a {((p95-p5)/p50)*100:.0f}% spread around median\n")

# === 6. Per-fill stats ===
wins = [p for p in fill_pnls if p > 0]
losses = [p for p in fill_pnls if p <= 0]
print(f"=== 6. Per-fill stats (cost=$0.50) ===")
print(f"  Wins: n={len(wins)}, avg=${statistics.mean(wins):+.2f}, median=${statistics.median(wins):+.2f}, max=${max(wins):+.2f}")
print(f"  Losses: n={len(losses)}, avg=${statistics.mean(losses):+.2f}, median=${statistics.median(losses):+.2f}, min=${min(losses):+.2f}")
expectancy = statistics.mean(fill_pnls)
print(f"  Expectancy per fill: ${expectancy:+.4f} raw = ${expectancy*10:+.2f} at 0.10L\n")

print(f"=== CYCLE 29 STABILITY DONE ===", flush=True)
