"""backtest_parallel_capped.py - canonical Python detector with a MAX_CONCURRENT cap.

Zee 2026-06-04 insight: brokers in Hedging mode allow parallel positions, so
the EA *could* be rewritten to stack trades (Path B). But infinite overlap
(canonical Python's behaviour) is unrealistic — it ignores margin, broker
rate limits, and the DD policing the prop firm enforces.

This script puts a realistic ceiling on parallelism and reports what the
EA could earn if rewritten to allow N concurrent positions per side.

Grid: max_concurrent ∈ {1, 2, 3, 5, 10, 20, ∞}
For each, run on 27-day tick set and report:
  total fills, win rate, total $ at 0.05L, $ per day, peak concurrent
"""
import sys, glob, bisect
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.20
LOTS = 0.05
USD_PER_PRICE = LOTS * 100

# AGGRESSIVE canonical config — keeping at 0.5/10s/3 ticks (matches zee_tick_detector_OOS.py)
RNG_N_MIN = 0.5; RNG_MIN = 0.5; SPR_MAX = 0.50
COOLDOWN_SEC = 10; M5_LB = 14; CHECK_EVERY = 3
MAX_HOLD_SEC = 2400; LOSS_STREAK_N = 1; LOSS_STREAK_PAUSE = 300
TRAIL_ARM = 5.0; TRAIL_GB = 15.0; MAX_LOSS = 10.0; SKIM = 10.0
DAILY_DD_PRICE = 100.0


def in_zee_window(t_dt):
    m = t_dt.hour * 60 + t_dt.minute
    return (90 <= m <= 150) or (1005 <= m <= 1185)


def load_ticks(path):
    out = []
    with open(path, encoding="utf-8") as f:
        header = next(f).strip()
        is_b = header.startswith("ts_broker")
        for line in f:
            parts = line.strip().split(",")
            try:
                if is_b:
                    if len(parts) < 4: continue
                    dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                    ms = int(parts[1])
                    t_ms = int(dt.replace(tzinfo=UTC).timestamp() * 1000) + ms
                    out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
                else:
                    if len(parts) < 3: continue
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
    oH = max(b["h"] for b in older);  oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run_day_capped(ticks, m5, max_concurrent):
    """Like canonical Python but TRACKS open positions; new fires blocked if
    max_concurrent already reached. Each open position is managed (trail/CB/skim)
    independently as ticks advance."""
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]

    positions = []   # list of dicts: {side, entry, entry_ms, peak, armed}
    last_fire = {"buy": 0, "sell": 0}
    daily_pnl_price = 0.0
    consec_losses = 0
    pause_until_ms = 0
    fills = []
    peak_concurrent = 0

    def check_exits(j):
        """Walk through positions at tick index j, close any that hit exit conditions."""
        nonlocal consec_losses, pause_until_ms, daily_pnl_price
        survivors = []
        for p in positions:
            bid2 = bids[j]; ask2 = asks[j]
            cur = (bid2 - p["entry"]) if p["side"] > 0 else (p["entry"] - ask2)
            t2 = times[j]
            exit_pnl = None; reason = None
            if (t2 - p["entry_ms"]) > MAX_HOLD_SEC * 1000:
                exit_pnl = cur; reason = "EOH"
            elif cur >= SKIM:
                exit_pnl = cur; reason = "SKIM"
            elif cur <= -MAX_LOSS:
                exit_pnl = cur; reason = "CB"
            else:
                if cur > p["peak"]: p["peak"] = cur
                if p["peak"] >= TRAIL_ARM: p["armed"] = True
                if p["armed"] and cur <= p["peak"] - TRAIL_GB:
                    exit_pnl = cur; reason = "TRAIL"
            if reason:
                pnl = exit_pnl - COST
                daily_pnl_price += exit_pnl
                if exit_pnl > 0: consec_losses = 0
                else:
                    consec_losses += 1
                    if consec_losses >= LOSS_STREAK_N:
                        pause_until_ms = t2 + LOSS_STREAK_PAUSE * 1000
                        consec_losses = 0
                fills.append({"pnl_usd": exit_pnl * USD_PER_PRICE - COST, "reason": reason,
                              "side": "buy" if p["side"] > 0 else "sell"})
            else:
                survivors.append(p)
        positions[:] = survivors

    k = 50
    while k < len(ticks):
        t = times[k]
        # Process exits FIRST at this tick
        if positions: check_exits(k)
        if positions: peak_concurrent = max(peak_concurrent, len(positions))

        dt = datetime.fromtimestamp(t / 1000, tz=UTC)
        if not in_zee_window(dt): k += CHECK_EVERY; continue
        if asks[k] - bids[k] > SPR_MAX: k += CHECK_EVERY; continue
        if daily_pnl_price <= -DAILY_DD_PRICE: k += CHECK_EVERY; continue
        if t < pause_until_ms: k += CHECK_EVERY; continue
        if len(positions) >= max_concurrent: k += CHECK_EVERY; continue

        k_60 = bisect.bisect_left(times, t - 60_000)
        k_300 = bisect.bisect_left(times, t - 300_000)
        if k_60 >= k - 1: k += CHECK_EVERY; continue
        w60 = mids[k_60:k]; w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: k += CHECK_EVERY; continue
        range_300 = (max(w300) - min(w300)) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: k += CHECK_EVERY; continue

        td = m5_trend(m5, t)
        if td == 0: k += CHECK_EVERY; continue

        side = +1 if td > 0 else -1
        side_key = "buy" if side > 0 else "sell"
        if t - last_fire[side_key] < COOLDOWN_SEC * 1000: k += CHECK_EVERY; continue

        # FIRE — add to positions list
        entry_px = asks[k] if side > 0 else bids[k]
        positions.append({
            "side": side, "entry": entry_px, "entry_ms": t,
            "peak": 0.0, "armed": False,
        })
        last_fire[side_key] = t
        k += CHECK_EVERY

    # Close any still-open at end of data
    if positions:
        for p in positions:
            bid2 = bids[-1]; ask2 = asks[-1]
            cur = (bid2 - p["entry"]) if p["side"] > 0 else (p["entry"] - ask2)
            fills.append({"pnl_usd": cur * USD_PER_PRICE - COST, "reason": "EOD",
                          "side": "buy" if p["side"] > 0 else "sell"})

    return fills, peak_concurrent


def main():
    caps = [1, 2, 3, 5, 10, 20, 999]
    print("Parallel-cap backtest (AGGRESSIVE canonical config, 0.05 lots, 27 days)")
    print("=" * 90)
    print(f"{'max_par':>8}{'fills':>7}{'WR%':>6}{'27d_PnL$':>12}{'$/day':>10}{'peak_par':>10}")
    print("-" * 90)
    for cap in caps:
        total_pnl = 0
        total_n = 0; total_w = 0; total_l = 0
        global_peak = 0
        for path in sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv"))):
            ticks = load_ticks(path)
            if len(ticks) < 1000: continue
            m5 = build_m5(ticks)
            fills, peak = run_day_capped(ticks, m5, cap)
            total_pnl += sum(f["pnl_usd"] for f in fills)
            total_n += len(fills)
            total_w += sum(1 for f in fills if f["pnl_usd"] > 0)
            total_l += sum(1 for f in fills if f["pnl_usd"] < 0)
            global_peak = max(global_peak, peak)
        wr = 100 * total_w / max(1, total_w + total_l) if (total_w + total_l) else 0
        cap_str = "∞" if cap >= 999 else str(cap)
        print(f"{cap_str:>8}{total_n:>7}{wr:>5.1f}%{total_pnl:>+12.2f}{total_pnl/27:>+9.2f}{global_peak:>10}")


if __name__ == "__main__":
    main()
