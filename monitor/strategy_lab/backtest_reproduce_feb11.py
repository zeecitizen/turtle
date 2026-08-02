"""backtest_reproduce_feb11.py - re-run the AGGRESSIVE config on Feb 11 ticks.

If overnight claim +$45,599 (Feb 11 alone, 0.10 lots) reproduces here, the
edge IS real on Blueberry data. If not, the overnight backtest was buggy
even on the data it was tested with.

CONFIG = exactly cycle27_re_trail_cb.py for the AGGRESSIVE variant:
  RNG_N_MIN = 0.5; RNG_MIN = 0.5
  SPR_MAX = 0.50; COOLDOWN_SEC = 10
  DAILY_DD = 100; M5_LB = 14; CHECK_EVERY = 3
  MAX_HOLD = 2400; LOSS_STREAK_N = 1; LOSS_STREAK_PAUSE = 300
  TRAIL_ARM = 5.0; TRAIL_GB = 15; SKIM = 10; MAX_LOSS = 10
  COST = 0.50 (per cycle27); LOTS = 0.10 (per overnight claim)
"""
import sys, bisect
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICK_CSV = COMMON / "shano_ticks_2026-02-11.csv"

# AGGRESSIVE config matching cycle27
RNG_N_MIN         = 0.5
RNG_MIN           = 0.5
SPR_MAX           = 0.50
COOLDOWN_SEC      = 10
DAILY_DD_STOP     = 100.0
M5_LB             = 14
CHECK_EVERY       = 3
MAX_HOLD_SEC      = 2400
LOSS_STREAK_N     = 1
LOSS_STREAK_PAUSE = 300
TRAIL_ARM         = 5.0
TRAIL_GB          = 15.0
SKIM_CAP          = 10.0
MAX_LOSS          = 10.0
COST              = 0.50
LOTS              = 0.10
USD_PER_PRICE     = LOTS * 100   # $10 per $1 move at 0.10L XAUUSD


def in_zee_window_utc(t_dt):
    m = t_dt.hour * 60 + t_dt.minute
    return (90 <= m <= 150) or (1005 <= m <= 1185)


def load_ticks(path):
    out = []
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 3: continue
            try:
                date_p, time_p = parts[0].split(" ")
                hms, ms_str = (time_p.split(".", 1) if "." in time_p else (time_p, "0"))
                dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
                t_ms = int(dt.replace(tzinfo=UTC).timestamp() * 1000) + int(ms_str)
                out.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
            except: continue
    return out


def build_m5(ticks):
    m1 = []; cur = None
    for tk in ticks:
        m_key = tk["t_ms"] // 60000
        mid = (tk["bid"] + tk["ask"]) / 2
        if cur is None or m_key != cur["m_key"]:
            if cur: m1.append(cur)
            cur = {"m_key": m_key, "h": mid, "l": mid, "c": mid,
                   "t_start_ms": m_key * 60000, "t_end_ms": (m_key + 1) * 60000 - 1}
        else:
            cur["h"] = max(cur["h"], mid); cur["l"] = min(cur["l"], mid); cur["c"] = mid
    if cur: m1.append(cur)
    m5 = []
    for i in range(0, len(m1), 5):
        c = m1[i:i + 5]
        if not c: continue
        m5.append({"t_end_ms": c[-1]["t_end_ms"],
                   "h": max(b["h"] for b in c), "l": min(b["l"] for b in c)})
    return m5


def m5_trend(m5, ts_ms):
    idx = -1
    for i, b in enumerate(m5):
        if b["t_end_ms"] > ts_ms: break
        idx = i
    if idx < M5_LB: return 0
    W = m5[idx - M5_LB + 1:idx + 1]; h = len(W) // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run(ticks, m5):
    times = [t["t_ms"] for t in ticks]
    bids  = [t["bid"]  for t in ticks]
    asks  = [t["ask"]  for t in ticks]
    mids  = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl_price = 0.0; consec_losses = 0; pause_until_ms = 0

    for k in range(50, len(ticks), CHECK_EVERY):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000, tz=UTC)
        if not in_zee_window_utc(dt): continue
        if asks[k] - bids[k] > SPR_MAX: continue
        if daily_pnl_price * USD_PER_PRICE <= -DAILY_DD_STOP: continue
        if t < pause_until_ms: continue
        k_60  = bisect.bisect_left(times, t -  60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60  = mids[k_60:k]
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
        # FIRE
        entry_px = asks[k] if side == "buy" else bids[k]; entry_ms = t
        peak = 0.0; armed = False; exit_pnl = 0.0
        for j in range(k, len(ticks)):
            t2 = times[j]
            if (t2 - entry_ms) > MAX_HOLD_SEC * 1000:
                cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
                exit_pnl = cur; break
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            if cur >= SKIM_CAP:    exit_pnl = cur; break
            if cur > peak: peak = cur
            if peak >= TRAIL_ARM: armed = True
            if armed and cur <= peak - TRAIL_GB: exit_pnl = cur; break
            if cur <= -MAX_LOSS:   exit_pnl = cur; break
        daily_pnl_price += exit_pnl
        if exit_pnl > 0: consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= LOSS_STREAK_N:
                pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                consec_losses = 0
        fills.append({"t": dt, "side": side, "exit_pnl_price": exit_pnl})
        last_fire_ms[side] = t
    return fills, daily_pnl_price


def main():
    ticks = load_ticks(TICK_CSV)
    print(f"Loaded {len(ticks):,} ticks from {TICK_CSV.name}")
    m5 = build_m5(ticks)
    print(f"  {len(m5)} M5 bars\n")

    fills, total_price = run(ticks, m5)
    n = len(fills)
    wins = sum(1 for f in fills if f["exit_pnl_price"] > 0)
    losses = sum(1 for f in fills if f["exit_pnl_price"] < 0)
    wr = 100 * wins / max(1, wins + losses) if (wins + losses) else 0
    total_usd = total_price * USD_PER_PRICE - n * COST

    print(f"AGGRESSIVE CONFIG (cycle27 verbatim) on Feb 11 ticks:")
    print(f"  Trades:        {n}")
    print(f"  Wins / Losses: {wins} / {losses}  (WR {wr:.1f}%)")
    print(f"  Gross P&L:     ${total_price * USD_PER_PRICE:+,.2f} (at 0.10 lots)")
    print(f"  Cost:          ${n * COST:+,.2f}")
    print(f"  Net P&L:       ${total_usd:+,.2f}")
    print()
    print(f"OVERNIGHT CLAIM for Feb 11 AGGRESSIVE: +$45,599 at 0.10 lots, 94% WR")
    print(f"DIFF from claim: ${total_usd - 45599:+,.2f}")


if __name__ == "__main__":
    main()
