"""zee_tick_detector_OOS.py — out-of-sample test of the Feb 11 tick-level detector
on April-May Blueberry tick days. If it holds OOS, write the EA.

Detector (locked from Feb 11 in-sample best):
  - Time: 01:30-02:30 + 16:45-19:45 broker EET
  - Side: M5-30 trend (HH/HL)
  - Trigger: rng60_norm >= 1.5 AND rng60 >= $1.5 AND spread <= $0.40
  - Cooldown: 60s per side
  - Exit: peak-trail arm=$1.0, giveback=$5.0, max_loss=$5.0, skim=$50, max_hold=30min
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

# Locked config
RNG_N_MIN = 0.5  # cycle 22: 1.0→0.5
RNG_MIN = 0.5    # cycle 22: locked at 0.5
SPR_MAX = 0.50  # cycle 10: 0.40→0.50 (+$2791)
COOLDOWN_SEC = 10  # cycle 26: 15→10 (+$144691). NOTE: cd=1 gave $3.3M but unrealistic broker rate-limit
TRAIL_ARM = 5.0
TRAIL_GB = 15.0  # cycle 27: 10→15 (+$60212 combined w/ CB)
MAX_LOSS = 10.0  # cycle 14: 5→10 (+$5902)
SKIM = 10.0  # cycle 16: 50→10. Total -$6911 but Feb 11 +$4931 (vs $2567), 15W/5L (vs 12/8). Stability win.
MAX_HOLD_SEC = 2400  # cycle 20: 1800→2400 (+$21780)
M5_LB = 14  # cycle 19: 20→14 (+$33758 total, Feb 11 still +$15370)
CHECK_EVERY = 3   # cycle 25: 20→3 (+$39189, 21W/1L)
ER_LB = 30
ER_MIN = 0.00
TREND_MIN_PTS = 0.0
DAILY_DD_STOP = 100.0  # cycle 21: 75→100 (+$4545, 20W/2L vs 19W/3L)
M15_LB = 8
PRESESH_RANGE_MIN = 3.0
LOSS_STREAK_N = 1     # cycle 24: 2→1 (pause after every loss)
LOSS_STREAK_PAUSE = 300  # cycle 24: 600→300 (+$12872)
M5_STAB_LB = 5
M5_STAB_MIN_AGREE = 3    # 3 of 5 (majority)


def in_zee_window(t):
    mins = t.hour * 60 + t.minute
    return (90 <= mins <= 150) or (1005 <= mins <= 1185)


def load_ticks(path):
    """Handles two formats:
       (A) Feb 11 export: header 't,bid,ask' with ts like '2026.02.11 01:00:09.108'
       (B) Apr-May logger: header 'ts_broker,ms,bid,ask,last,volume' with ts '2026.04.29 12:27:31' + sep ms"""
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
    m15 = []
    for i in range(0, len(m5), 3):
        c = m5[i:i+3]
        if not c: continue
        m15.append({"t_start_ms": c[0]["t_start_ms"], "t_end_ms": c[-1]["t_end_ms"],
                    "o": c[0]["o"], "h": max(b["h"] for b in c),
                    "l": min(b["l"] for b in c), "c": c[-1]["c"],
                    "v": sum(b["v"] for b in c), "t": c[0]["t"]})
    return m1, m5, m15


def m5_trend(m5, ts_ms, lb=M5_LB):
    """Returns (dir, er, abs_move). dir = +1/-1/0 (HH/HL or LH/LL).
    er = Kaufman efficiency ratio over lb bars (0=chop, 1=pure trend).
    abs_move = $ change over the trend window."""
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < lb: return (0, 0.0, 0.0)
    W = m5[idx - lb + 1:idx + 1]; h = len(W)//2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: d = +1
    elif rH < oH and rL < oL: d = -1
    else: d = 0
    closes = [b["c"] for b in W]
    net = abs(closes[-1] - closes[0])
    path = sum(abs(closes[k] - closes[k-1]) for k in range(1, len(closes)))
    er = net / path if path > 1e-9 else 0.0
    abs_move = closes[-1] - closes[0]
    return (d, er, abs_move)


def hh_hl_trend(bars, ts_ms, lb):
    """Generic HH/HL trend on bars list, returns +1/-1/0."""
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


def run_day(ticks, m5, m15):
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
        if not in_zee_window(dt): continue
        if asks[k] - bids[k] > SPR_MAX: continue
        if daily_pnl <= -DAILY_DD_STOP: continue
        if t < pause_until_ms: continue
        # 60-sec features
        k_60 = bisect.bisect_left(times, t - 60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: continue
        td, er, abs_move = m5_trend(m5, t)
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue
        # Exit
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
    return fills


# Run all available days
day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
# Also include Feb 11 (in-sample) for reference
print(f"Running tick detector on {len(day_files)} days...\n")
print(f"  {'date':<11} {'ticks':>8} {'M1':>4} {'M5':>4} {'fills':>5} {'W':>3} {'L':>3} "
      f"{'WR%':>4} {'raw$':>7} {'dollars':>8} {'best':>6} {'worst':>6}")
all_fills = []
totals = {"in": 0.0, "oos": 0.0}
counts = {"in": 0, "oos": 0}
for path in day_files:
    day = Path(path).stem.replace("shano_ticks_", "")
    ticks = load_ticks(path)
    if len(ticks) < 1000: continue
    m1, m5, m15 = build_m1_m5(ticks)
    fills = run_day(ticks, m5, m15)
    n = len(fills); w = sum(1 for f in fills if f["pnl"]>0); l = n - w
    tot = sum(f["pnl"] for f in fills)
    best = max((f["pnl"] for f in fills), default=0)
    worst = min((f["pnl"] for f in fills), default=0)
    is_in = (day == "2026-02-11")
    bucket = "in" if is_in else "oos"
    totals[bucket] += tot
    counts[bucket] += n
    flag = "  *IS" if is_in else ""
    print(f"  {day:<11} {len(ticks):>8} {len(m1):>4} {len(m5):>4} {n:>5} {w:>3} {l:>3} "
          f"{100*w/max(1,n):>3.0f}% {tot:>+7.1f} {tot*10:>+8.0f} {best:>+6.1f} {worst:>+6.1f}{flag}")
    all_fills.extend([(day, *f.values()) for f in fills])

print(f"\n=== SUMMARY ===")
print(f"  IN-SAMPLE  (Feb 11): n={counts['in']:>3} NET raw ${totals['in']:+.2f} = ${totals['in']*10:+.0f}")
print(f"  OUT-OF-SAMPLE (Apr-May): n={counts['oos']:>3} NET raw ${totals['oos']:+.2f} = ${totals['oos']*10:+.0f}")
total = totals["in"] + totals["oos"]
print(f"  ALL DAYS combined: ${total:+.2f} raw = ${total*10:+.0f} dollars at 0.10 lots")
