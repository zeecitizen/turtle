"""trail_param_sweep.py — does tightening the trail-arm + give-back help or hurt?

Today (2026-06-02) on Atmos LIVE, we've seen TWO trades in a row peak at +$13 USD
then revert and hit broker SL at -$25 USD. The flaw: at 0.05 lots, TRAIL_ARM=$5 price
= $25 USD peak required to arm trail — but most chop-day peaks are smaller. Combined
with broker SL at fixed $25 USD = $5 price at 0.05 lots, the broker SL is tighter
than the trail's working range. Trail effectively disabled at 0.05 lots.

Zee asked the right question: would tightening trail keep the backtest's profit, or
crash it by cutting off big-day winners?

This script sweeps a few candidate (TRAIL_ARM, TRAIL_GB) pairs and compares total
P&L, WR%, days+, days-, and the single best/worst day. ALL using 24h trading.
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.50
RNG_N_MIN = 0.5; RNG_MIN = 0.5; SPR_MAX = 0.50
COOLDOWN_SEC = 10
MAX_LOSS = 10.0; SKIM = 10.0; MAX_HOLD_SEC = 2400
M5_LB = 14; CHECK_EVERY = 3
DAILY_DD_STOP = 100.0; LOSS_STREAK_N = 1; LOSS_STREAK_PAUSE = 300

# Trail config candidates: (name, TRAIL_ARM, TRAIL_GB)
TRAIL_CONFIGS = [
    ("current_5_15",  5.0, 15.0),  # baseline
    ("tight_2_5",     2.0,  5.0),  # the proposal
    ("tight_3_8",     3.0,  8.0),  # middle
    ("loose_8_25",    8.0, 25.0),  # opposite direction
    ("very_tight_1_3",1.0,  3.0),  # extreme tight
]


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


def run_day(ticks, m5, TRAIL_ARM, TRAIL_GB):
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
        fills.append(pnl)
        last_fire_ms[side] = t
    return fills


def run_config(name, TRAIL_ARM, TRAIL_GB):
    day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    total_pnl = 0.0; total_n = 0; total_w = 0
    days_pos = 0; days_neg = 0
    best = ("", 0); worst = ("", 0)
    feb11 = 0
    for path in day_files:
        day = Path(path).stem.replace("shano_ticks_", "")
        ticks = load_ticks(path)
        if len(ticks) < 1000: continue
        m1, m5 = build_m1_m5(ticks)
        fills = run_day(ticks, m5, TRAIL_ARM, TRAIL_GB)
        n = len(fills); w = sum(1 for f in fills if f > 0)
        tot = sum(fills)
        total_pnl += tot; total_n += n; total_w += w
        if tot > 0: days_pos += 1
        elif tot < 0: days_neg += 1
        if tot > best[1]: best = (day, tot)
        if tot < worst[1]: worst = (day, tot)
        if day == "2026-02-11": feb11 = tot
    return dict(name=name, arm=TRAIL_ARM, gb=TRAIL_GB, n=total_n, w=total_w,
                wr=100*total_w/max(1,total_n), pnl=total_pnl,
                days_pos=days_pos, days_neg=days_neg, best=best, worst=worst, feb11=feb11)


print("Trail-param sweep (24h trading, $0.50/trade cost, 26 days of real ticks)")
print(f"{'Config':<18} {'Arm':>5} {'GB':>5} {'Fills':>7} {'WR%':>5} {'@0.01 lot':>11} "
      f"{'@0.05 lot':>11} {'Days+':>6} {'Days-':>6} {'Best$':>9} {'Worst$':>8}")
print("-" * 110)
for name, arm, gb in TRAIL_CONFIGS:
    r = run_config(name, arm, gb)
    print(f"{r['name']:<18} {r['arm']:>5.1f} {r['gb']:>5.1f} {r['n']:>7} "
          f"{r['wr']:>4.1f}% ${r['pnl']:>+9.0f} ${r['pnl']*5:>+9.0f} "
          f"{r['days_pos']:>6} {r['days_neg']:>6} ${r['best'][1]:>+7.0f} ${r['worst'][1]:>+6.0f}")
print()
print("KEY: 'best/worst$' = single-day PnL @ 0.01 lot. At 0.05 lot multiply by 5.")
