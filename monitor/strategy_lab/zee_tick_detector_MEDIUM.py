"""zee_tick_detector_MEDIUM.py - Python canonical for MEDIUM variant.

Identical to zee_tick_detector_OOS.py except:
  RNG_N_MIN: 0.5 -> 0.8 (medium: stricter normalised range)
  RNG_MIN:   0.5 -> 0.8 (medium: stricter absolute range)
  COOLDOWN_SEC: 10 -> 30 (medium: less frequent)
  CHECK_EVERY:  3 -> 10 (medium: less aggressive)

DD_STOP stays in raw PRICE units (cycle21 = 100). Do NOT scale by lots
in the loop — Python detector treats `daily_pnl` as price, dollarising
only at the report stage via `tot * 10` for 0.10 lots.

If this reproduces +$128k MEDIUM claim, then MEDIUM filter is genuinely
valid and live EA divergence is purely execution (broker/spread/latency).
If not, MEDIUM is broken and AGGRESSIVE is the only path forward.
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.20

# MEDIUM-variant overrides (rest match AGGRESSIVE canonical):
RNG_N_MIN = 0.8
RNG_MIN = 0.8
SPR_MAX = 0.50
COOLDOWN_SEC = 30
TRAIL_ARM = 5.0
TRAIL_GB = 15.0
MAX_LOSS = 10.0
SKIM = 10.0
MAX_HOLD_SEC = 2400
M5_LB = 14
CHECK_EVERY = 10
DAILY_DD_STOP = 100.0
LOSS_STREAK_N = 1
LOSS_STREAK_PAUSE = 300


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
                    date_p, time_p = parts[0].split(" ")
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
    m5 = []
    for i in range(0, len(m1), 5):
        c = m1[i:i+5]
        if not c: continue
        m5.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
                   "o": c[0]["o"], "h": max(b["h"] for b in c),
                   "l": min(b["l"] for b in c), "c": c[-1]["c"]})
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


def run_day(ticks, m5):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl = 0.0   # PRICE UNITS, do not scale by lots inside the loop
    consec_losses = 0
    pause_until_ms = 0
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


day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
print(f"MEDIUM canonical Python detector on {len(day_files)} days\n")
print(f"{'date':<11} {'fills':>5} {'W':>3} {'L':>3} {'WR%':>4} {'raw$':>7} {'dollars':>8}")
totals = 0.0
for path in day_files:
    day = Path(path).stem.replace("shano_ticks_", "")
    ticks = load_ticks(path)
    if len(ticks) < 1000: continue
    m1, m5 = build_m1_m5(ticks)
    fills = run_day(ticks, m5)
    n = len(fills); w = sum(1 for f in fills if f["pnl"]>0); l = n - w
    tot = sum(f["pnl"] for f in fills)
    totals += tot
    flag = "  *Feb11" if day == "2026-02-11" else ""
    print(f"{day:<11} {n:>5} {w:>3} {l:>3} {100*w/max(1,n):>3.0f}% {tot:>+7.1f} {tot*10:>+8.0f}{flag}")

print(f"\n=== MEDIUM TOTAL ===")
print(f"  Raw: ${totals:+.2f}    At 0.10 lots: ${totals*10:+.0f}    At 0.05 lots: ${totals*5:+.0f}")
