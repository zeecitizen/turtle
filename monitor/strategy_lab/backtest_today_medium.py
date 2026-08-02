"""backtest_today_medium.py - replay TODAY's tick file with the MEDIUM-variant
config that matches the live Feb11TickMedium EA. Compare to actual live fills.

Per Zee's request 2026-06-03:
  'rerun validated config backtest on today's real tick data. see why our EA
   missed those entries taken by the backtest'

CONFIG (matches mt5/Feb11TickMedium.mq5 inputs exactly):
  RNG_N_MIN = 0.8         (medium: stricter than aggressive 0.5)
  RNG_MIN   = 0.8         (medium: stricter than 0.5)
  SPR_MAX   = 0.50
  COOLDOWN  = 30s         (medium: was 10s aggressive)
  CHECK_EVERY = 10 ticks  (medium: was 3 aggressive)
  M5_LB     = 14
  TRAIL_ARM = $5
  TRAIL_GB  = $15
  SKIM_CAP  = $10
  MAX_LOSS  = $10
  MAX_HOLD  = 2400s
  LOSS_STREAK_N = 1
  LOSS_STREAK_PAUSE = 300s
  DAILY_DD  = $70
  COST      = $0.20 round-trip
  LOTS      = 0.05 (today's live)
  SESSIONS  = 01:30-02:30 + 16:45-19:45 UTC (broker-time GMT+3 = 04:30-05:30 + 19:45-22:45)
"""
import sys, csv, bisect
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass
UTC = timezone.utc

COMMON   = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICK_CSV = COMMON / "shano_ticks_2026-06-03.csv"
FILLS_CSV = COMMON / "turtle_fills.csv"

# === MEDIUM VARIANT CONFIG (matches live Feb11TickMedium v1.17) ===
RNG_N_MIN         = 0.8
RNG_MIN           = 0.8
SPR_MAX           = 0.50
COOLDOWN_SEC      = 30
CHECK_EVERY       = 10
M5_LB             = 14
TRAIL_ARM         = 5.0
TRAIL_GB          = 15.0
SKIM_CAP          = 10.0
MAX_LOSS          = 10.0
MAX_HOLD_SEC      = 2400
LOSS_STREAK_N     = 1
LOSS_STREAK_PAUSE = 300
DAILY_DD_STOP     = 70.0      # live uses 70, validated was 100
COST              = 0.20
LOTS              = 0.05
USD_PER_PRICE_LIVE = LOTS * 100   # XAUUSD: 100 USD per $1 move per 1.0 lot


def in_session_utc(t_dt):
    """Same window the backtest used: UTC 01:30-02:30 + 16:45-19:45."""
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
    daily_pnl = 0.0; consec_losses = 0; pause_until_ms = 0
    rejects = {"out_session": 0, "spread": 0, "daily_dd": 0, "pause": 0,
               "rng60_small": 0, "rng60norm_small": 0, "no_trend": 0,
               "cooldown": 0}

    for k in range(50, len(ticks), CHECK_EVERY):
        t = times[k]
        dt = datetime.fromtimestamp(t / 1000, tz=UTC)
        if not in_session_utc(dt): rejects["out_session"] += 1; continue
        if asks[k] - bids[k] > SPR_MAX:                 rejects["spread"] += 1; continue
        if daily_pnl <= -DAILY_DD_STOP:                 rejects["daily_dd"] += 1; continue
        if t < pause_until_ms:                          rejects["pause"] += 1; continue
        k_60  = bisect.bisect_left(times, t -  60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60  = mids[k_60:k]
        w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: rejects["rng60_small"] += 1; continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_N_MIN: rejects["rng60norm_small"] += 1; continue
        td = m5_trend(m5, t)
        if td == 0: rejects["no_trend"] += 1; continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000:
            rejects["cooldown"] += 1; continue
        # FIRE
        entry_px = asks[k] if side == "buy" else bids[k]
        entry_ms = t; peak = 0.0; armed = False; exit_pnl = 0; exit_reason = "?"
        for j in range(k, len(ticks)):
            t2 = times[j]
            if (t2 - entry_ms) > MAX_HOLD_SEC * 1000:
                cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
                exit_pnl = cur; exit_reason = "EOH"; break
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            if cur >= SKIM_CAP:    exit_pnl = cur; exit_reason = "SKIM"; break
            if cur > peak: peak = cur
            if peak >= TRAIL_ARM: armed = True
            if armed and cur <= peak - TRAIL_GB:
                exit_pnl = cur; exit_reason = "TRAIL"; break
            if cur <= -MAX_LOSS:   exit_pnl = cur; exit_reason = "MAXLOSS"; break
        pnl_price = exit_pnl
        pnl_usd = pnl_price * USD_PER_PRICE_LIVE - COST
        daily_pnl += pnl_usd
        if pnl_usd > 0: consec_losses = 0
        else:
            consec_losses += 1
            if consec_losses >= LOSS_STREAK_N:
                pause_until_ms = t + LOSS_STREAK_PAUSE * 1000
                consec_losses = 0
        fills.append({
            "t_ms": t, "t": dt.strftime("%H:%M:%S"), "side": side,
            "entry": round(entry_px, 2), "pnl_price": round(pnl_price, 2),
            "pnl_usd": round(pnl_usd, 2), "reason": exit_reason,
        })
        last_fire_ms[side] = t
    return fills, daily_pnl, rejects


def load_live_fills(today_str):
    out = []
    if not FILLS_CSV.exists(): return out
    with open(FILLS_CSV, encoding="utf-8", errors="replace") as f:
        rdr = csv.reader(f); next(rdr, None)
        for r in rdr:
            if not r or not r[0].startswith(today_str): continue
            try:
                pnl = float(r[7]); vol = r[5]
                out.append({"t": r[0][11:], "side": r[4], "vol": vol, "pnl": pnl})
            except: continue
    return out


def main():
    if not TICK_CSV.exists():
        print(f"NO tick file: {TICK_CSV}"); return
    print(f"Loading {TICK_CSV.name}...", flush=True)
    ticks = load_ticks(TICK_CSV)
    print(f"  {len(ticks):,} ticks")
    m5 = build_m5(ticks)
    print(f"  {len(m5)} M5 bars\n")

    print("=" * 78)
    print("BACKTEST: MEDIUM config on TODAY's ticks (matches live Feb11TickMedium v1.17)")
    print(f"Sessions: UTC 01:30-02:30 + 16:45-19:45   Lots: {LOTS}   Cost: ${COST}/trade")
    print("=" * 78)
    fills, daily_pnl, rejects = run(ticks, m5)
    n = len(fills)
    wins   = sum(1 for f in fills if f["pnl_usd"] > 0)
    losses = sum(1 for f in fills if f["pnl_usd"] < 0)
    wr     = 100 * wins / max(1, wins + losses) if (wins + losses) else 0

    print(f"\nBACKTEST RESULT:")
    print(f"  Trades: {n}    Wins: {wins}    Losses: {losses}    WR: {wr:.1f}%")
    print(f"  Daily P&L: ${daily_pnl:+.2f}")
    print(f"  Rejects: {rejects}")

    print(f"\nBACKTEST FILLS:")
    print(f"  {'time':<10}{'side':<6}{'entry':>9}{'pnl':>8}  reason")
    for f in fills:
        marker = "✓" if f["pnl_usd"] > 0 else "✗"
        print(f"  {f['t']:<10}{f['side']:<6}{f['entry']:>9}{f['pnl_usd']:>+8.2f}  {marker} {f['reason']}")

    # Load live fills today
    live = load_live_fills("2026.06.03")
    live_pnl = sum(x["pnl"] for x in live)
    live_w = sum(1 for x in live if x["pnl"] > 0)
    live_l = sum(1 for x in live if x["pnl"] < 0)
    live_wr = 100 * live_w / max(1, live_w + live_l)

    print(f"\n" + "=" * 78)
    print("LIVE vs BACKTEST (same config, same day, same ticks)")
    print("=" * 78)
    print(f"  {'metric':<15}{'BACKTEST':>14}{'LIVE':>14}{'diff':>12}")
    print(f"  {'trades':<15}{n:>14}{len(live):>14}{(len(live)-n):>+12}")
    print(f"  {'wins':<15}{wins:>14}{live_w:>14}{(live_w-wins):>+12}")
    print(f"  {'losses':<15}{losses:>14}{live_l:>14}{(live_l-losses):>+12}")
    print(f"  {'WR%':<15}{wr:>13.1f}%{live_wr:>13.1f}%")
    print(f"  {'P&L USD':<15}{daily_pnl:>+14.2f}{live_pnl:>+14.2f}{(live_pnl-daily_pnl):>+12.2f}")


if __name__ == "__main__":
    main()
