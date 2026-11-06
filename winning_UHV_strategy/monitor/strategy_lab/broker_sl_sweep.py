"""broker_sl_sweep.py — sweep broker_sl_usd to find optimal cap.

Today live: 8 of 10 losses cluster at -$23 to -$26 (broker SL hitting). Zee asked
if lowering broker SL would reduce per-trade loss. Trade-off: tighter SL = more
noise stop-outs but smaller per-loss; looser SL = less stops but bigger losses.

This backtest properly models the broker SL parachute at 0.05 lots and compares
to the EA's other exits (SKIM/TRAIL/CB/EOH).

24h trading. Tests broker_sl_usd in {15, 20, 25, 30, 50, 75}. All other params held
at current LIVE config (rng60=0.5, rng60_norm=0.5, cooldown=10, trail 5/15, etc).
"""
import sys, glob, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
COST = 0.50
LOTS = 0.05         # live size on Atmos

# Live aggressive params (post-runtime switch at 21:51 broker today)
RNG_N_MIN = 0.5
RNG_MIN = 0.5
SPR_MAX = 0.50
COOLDOWN_SEC = 10
TRAIL_ARM = 5.0
TRAIL_GB = 15.0
SKIM = 10.0           # EA's SKIM in price units = $50 USD at 0.05 lots
MAX_LOSS = 10.0       # EA's CB in price units = $50 USD at 0.05 lots
BROKER_TP_USD = 50.0  # broker TP fixed at $50 USD
MAX_HOLD_SEC = 2400
M5_LB = 14
CHECK_EVERY = 3
DAILY_DD_STOP = 70.0   # in price units = $350 USD at 0.05 lots
LOSS_STREAK_N = 1
LOSS_STREAK_PAUSE = 300

# Lot scaling factor: $1 USD = lot_factor * price-unit
# At 0.05 lots, $1 price move = $5 USD PnL, so 1 USD = 1/5 = 0.2 price
USD_PER_PRICE = LOTS * 100  # 5 at 0.05 lots

BROKER_SL_CANDIDATES = [15.0, 20.0, 25.0, 30.0, 50.0, 75.0, 100.0]

def usd_to_price(usd): return usd / USD_PER_PRICE  # for 0.05 lots

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


def run_day(ticks, m5, broker_sl_usd):
    """Models BOTH EA exits AND broker SL/TP parachute. Whichever hits first."""
    broker_sl_price = usd_to_price(broker_sl_usd)
    broker_tp_price = usd_to_price(BROKER_TP_USD)
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl = 0.0
    consec_losses = 0
    pause_until_ms = 0
    sl_hits = 0; tp_hits = 0; skim_hits = 0; cb_hits = 0; trail_hits = 0; eoh_hits = 0
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
            cur = (bids[j] - entry_px) if side == "buy" else (entry_px - asks[j])
            # Broker SL parachute (USD-based, scales with lots) — fires FIRST on loss
            if cur <= -broker_sl_price:
                exit_pnl = cur; sl_hits += 1; break
            # Broker TP parachute (USD-based)
            if cur >= broker_tp_price:
                exit_pnl = cur; tp_hits += 1; break
            # EA's SKIM (price-based, at 0.05 lots = $50 USD)
            if cur >= SKIM:
                exit_pnl = cur; skim_hits += 1; break
            # Max hold
            if (t2 - entry_ms) > MAX_HOLD_SEC * 1000:
                exit_pnl = cur; eoh_hits += 1; break
            # Trail
            if cur > peak: peak = cur
            if peak >= TRAIL_ARM: armed = True
            if armed and cur <= peak - TRAIL_GB:
                exit_pnl = cur; trail_hits += 1; break
            # EA's CB
            if cur <= -MAX_LOSS:
                exit_pnl = cur; cb_hits += 1; break
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
    return fills, {"sl": sl_hits, "tp": tp_hits, "skim": skim_hits, "cb": cb_hits, "trail": trail_hits, "eoh": eoh_hits}


def run_config(broker_sl_usd):
    day_files = sorted(glob.glob(str(COMMON / "shano_ticks_2026-*.csv")))
    total_pnl = 0.0; total_n = 0; total_w = 0
    days_pos = 0; days_neg = 0; days_count = 0
    hit_counts = {"sl":0,"tp":0,"skim":0,"cb":0,"trail":0,"eoh":0}
    best = ("", 0); worst = ("", 0)
    feb11_pnl = 0
    for path in day_files:
        day = Path(path).stem.replace("shano_ticks_", "")
        ticks = load_ticks(path)
        if len(ticks) < 1000: continue
        m1, m5 = build_m1_m5(ticks)
        fills, hits = run_day(ticks, m5, broker_sl_usd)
        n = len(fills); w = sum(1 for f in fills if f > 0)
        tot = sum(fills)
        days_count += 1
        total_pnl += tot; total_n += n; total_w += w
        for k in hit_counts: hit_counts[k] += hits[k]
        if tot > 0: days_pos += 1
        elif tot < 0: days_neg += 1
        if tot > best[1]: best = (day, tot)
        if tot < worst[1]: worst = (day, tot)
        if day == "2026-02-11": feb11_pnl = tot
    return {"sl_usd": broker_sl_usd, "n": total_n, "w": total_w,
            "wr": 100*total_w/max(1,total_n), "pnl_usd_at_005lot": total_pnl * USD_PER_PRICE,
            "days_pos": days_pos, "days_neg": days_neg, "days": days_count,
            "best": best, "worst": worst, "feb11_usd": feb11_pnl * USD_PER_PRICE,
            "hits": hit_counts}


print(f"Broker SL parachute sweep — 24h trading, 0.05 lots, aggressive params, all other exits ON")
print(f"USD per price unit: \${USD_PER_PRICE} (at {LOTS} lots)")
print()
print(f"{'broker_sl_usd':>12} {'in price':>9} {'fills':>7} {'WR%':>6} {'@0.05 USD':>12} "
      f"{'Days+':>6} {'Days-':>6} {'Best$ (price)':>15} {'Worst$ (price)':>15} {'SL hits':>9} {'TP hits':>9}")
print("-" * 130)
results = []
for sl_usd in BROKER_SL_CANDIDATES:
    r = run_config(sl_usd)
    results.append(r)
    sl_price = usd_to_price(sl_usd)
    print(f"{r['sl_usd']:>10.0f}  ${sl_price:>7.2f}  {r['n']:>7} {r['wr']:>5.1f}% ${r['pnl_usd_at_005lot']:>+10.0f} "
          f"{r['days_pos']:>6} {r['days_neg']:>6} {r['best'][0][-5:]+':$'+f'{r['best'][1]:+.0f}':>15} "
          f"{r['worst'][0][-5:]+':$'+f'{r['worst'][1]:+.0f}':>15} "
          f"{r['hits']['sl']:>9} {r['hits']['tp']:>9}")
print()
print("Pick the row with highest @0.05 USD that ALSO doesn't have an outlier worst day.")
