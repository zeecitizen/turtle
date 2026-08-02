"""backtest_zee_technique_no_hard_tp.py — does Zee's REAL technique restore the WR?

Zee's words: 'our technique usually is not to set a hard TP but to let it go towards
the WIN side and then exit if tries to reverse (try to CATCH maximum profit within
the few milliseconds the trade is open).'

Current EA caps wins at $50 USD (broker TP). This backtest REMOVES the cap and lets
trail be the only exit on the win side. Sweep different TRAIL_ARM / TRAIL_GB combos
to find what matches Zee's 78-92% manual WR.

Tested on TODAY's tick file (2026-06-02). Parallel cap=4 (Atmos-safe).
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICK_FILE = COMMON / "shano_ticks_2026-06-02.csv"
COST = 0.50
LOTS = 0.05
USD_PER_PRICE = LOTS * 100

RNG_MIN = 0.5
RNG_NORM_MIN = 0.5
SPR_MAX = 0.50
COOLDOWN_SEC = 10
M5_LB = 14
CHECK_EVERY = 3
MAX_HOLD_SEC = 2400
MAX_CONCURRENT = 4

# REMOVED hard caps — let trail handle ALL wins
BROKER_SL_USD = 25.0    # keep loss cap
BROKER_TP_USD = 999.0   # essentially uncapped (never fires)
SKIM = 999.0            # uncapped (never fires)
MAX_LOSS = 5.0          # price — matches broker SL at $25 USD = $5 price

# Test combos of (TRAIL_ARM, TRAIL_GB)
TRAIL_COMBOS = [
    (0.5, 0.5),   # very tight — arm at $2.5 USD, exit on $2.5 reversal
    (0.5, 1.0),   # arm early, slightly looser exit
    (1.0, 0.5),   # arm at $5 USD, exit on $2.5 reversal
    (1.0, 1.0),   # balanced tight
    (1.0, 2.0),   # arm early, exit on $10 reversal
    (2.0, 1.0),   # arm at $10 USD, exit on $5 reversal  (Zee-like)
    (2.0, 2.0),   # balanced medium
    (3.0, 2.0),   # arm at $15 USD, exit on $10 reversal
    (5.0, 5.0),   # current setting was 5 / 15 — try equal
    (5.0, 15.0),  # CURRENT CONFIG (baseline)
]


def usd_to_price(usd): return usd / USD_PER_PRICE
def price_to_usd(price): return price * USD_PER_PRICE


def load_ticks(path):
    out = []
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 4: continue
            try:
                dt = datetime.strptime(parts[0], "%Y.%m.%d %H:%M:%S")
                ms = int(parts[1])
                t_ms = int(dt.timestamp() * 1000) + ms
                out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
            except: continue
    return out


def build_m5_bars(ticks):
    m5 = {}
    for tk in ticks:
        m_key = tk["t_ms"] // 300000
        mid = (tk["bid"] + tk["ask"]) / 2
        if m_key not in m5:
            m5[m_key] = {"o": mid, "h": mid, "l": mid, "c": mid, "t_start_ms": m_key*300000}
        b = m5[m_key]
        b["h"] = max(b["h"], mid); b["l"] = min(b["l"], mid); b["c"] = mid
    return [m5[k] for k in sorted(m5.keys())]


def m5_trend(m5_list, ts_ms, lb=M5_LB):
    idx = -1
    for i, b in enumerate(m5_list):
        if b["t_start_ms"] + 300000 > ts_ms: break
        idx = i
    if idx < lb: return 0
    W = m5_list[idx - lb + 1: idx + 1]
    h = len(W) // 2
    older, recent = W[:h], W[h:]
    rH = max(b["h"] for b in recent); rL = min(b["l"] for b in recent)
    oH = max(b["h"] for b in older); oL = min(b["l"] for b in older)
    if rH > oH and rL > oL: return +1
    if rH < oH and rL < oL: return -1
    return 0


def run_backtest(ticks, m5_list, trail_arm, trail_gb):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]

    positions = []
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl_usd = 0.0
    consec_losses = 0
    pause_until_ms = 0

    broker_sl_price = usd_to_price(BROKER_SL_USD)
    broker_tp_price = usd_to_price(BROKER_TP_USD)
    atmos_floating_limit_price = usd_to_price(100.0)

    for k in range(len(ticks)):
        t = times[k]; bid = bids[k]; ask = asks[k]

        # Manage existing positions
        i = 0
        while i < len(positions):
            p = positions[i]
            cur = (bid - p["entry"]) if p["side"] > 0 else (p["entry"] - ask)
            close_reason = None
            if cur <= -broker_sl_price: close_reason = "BSL"
            elif cur >= broker_tp_price: close_reason = "BTP"
            elif cur >= SKIM: close_reason = "SKIM"
            elif (t - p["open_ms"]) > MAX_HOLD_SEC * 1000: close_reason = "EOH"
            else:
                if cur > p["peak"]: p["peak"] = cur
                if p["peak"] >= trail_arm: p["armed"] = True
                if p["armed"] and cur <= p["peak"] - trail_gb:
                    close_reason = "TRAIL"
                elif cur <= -MAX_LOSS: close_reason = "CB"

            if close_reason:
                pnl_price = cur - COST / USD_PER_PRICE
                pnl_usd = pnl_price * USD_PER_PRICE
                daily_pnl_usd += pnl_usd
                fills.append({"pnl_usd": pnl_usd, "reason": close_reason,
                              "peak_usd": p["peak"] * USD_PER_PRICE,
                              "hold_sec": (t - p["open_ms"]) / 1000})
                if pnl_usd > 0: consec_losses = 0
                else:
                    consec_losses += 1
                    if consec_losses >= 5:
                        pause_until_ms = t + 300 * 1000
                        consec_losses = 0
                positions.pop(i)
            else:
                i += 1

        # Daily DD check
        if daily_pnl_usd <= -400.0: continue

        # New fire
        if k % CHECK_EVERY != 0: continue
        if t < pause_until_ms: continue
        if (ask - bid) > SPR_MAX: continue
        if len(positions) >= MAX_CONCURRENT: continue

        # Atmos floating check
        combined_floating = 0
        for p in positions:
            cur = (bid - p["entry"]) if p["side"] > 0 else (p["entry"] - ask)
            if cur < 0: combined_floating += cur
        if -combined_floating >= atmos_floating_limit_price: continue

        # Entry detection
        k_60 = bisect.bisect_left(times, t - 60000)
        k_300 = bisect.bisect_left(times, t - 300000)
        if k_60 >= k - 1: continue
        w60 = mids[k_60:k]
        w300 = mids[k_300:k] if k_300 < k else w60
        rng60 = max(w60) - min(w60)
        if rng60 < RNG_MIN: continue
        range_300 = max(w300) - min(w300) if w300 else rng60
        rng60_norm = rng60 / max(0.10, range_300 / 5.0)
        if rng60_norm < RNG_NORM_MIN: continue
        td = m5_trend(m5_list, t)
        if td == 0: continue
        side = "buy" if td > 0 else "sell"
        if t - last_fire_ms[side] < COOLDOWN_SEC * 1000: continue

        entry_px = ask if td > 0 else bid
        positions.append({"side": td, "entry": entry_px, "open_ms": t, "peak": 0, "armed": False})
        last_fire_ms[side] = t

    # Close remaining
    if positions:
        last_bid = bids[-1]; last_ask = asks[-1]; last_t = times[-1]
        for p in positions:
            cur = (last_bid - p["entry"]) if p["side"] > 0 else (p["entry"] - last_ask)
            pnl_usd = cur * USD_PER_PRICE - COST
            daily_pnl_usd += pnl_usd
            fills.append({"pnl_usd": pnl_usd, "reason": "EOD",
                          "peak_usd": p["peak"] * USD_PER_PRICE, "hold_sec": (last_t - p["open_ms"])/1000})

    n = len(fills)
    wins = sum(1 for f in fills if f["pnl_usd"] > 0)
    losses = n - wins
    avg_win = sum(f["pnl_usd"] for f in fills if f["pnl_usd"] > 0) / max(1, wins)
    avg_loss = sum(f["pnl_usd"] for f in fills if f["pnl_usd"] <= 0) / max(1, losses)
    biggest_win = max((f["pnl_usd"] for f in fills), default=0)
    return {"trail_arm": trail_arm, "trail_gb": trail_gb,
            "n": n, "wins": wins, "losses": losses,
            "wr_pct": 100*wins/max(1,n), "pnl_usd": daily_pnl_usd,
            "avg_win": avg_win, "avg_loss": avg_loss, "biggest_win": biggest_win,
            "trail_exits": sum(1 for f in fills if f["reason"] == "TRAIL"),
            "sl_exits": sum(1 for f in fills if f["reason"] == "BSL"),
            "eoh_exits": sum(1 for f in fills if f["reason"] == "EOH")}


print(f"Loading {TICK_FILE.name}...")
ticks = load_ticks(TICK_FILE)
m5_list = build_m5_bars(ticks)
print(f"  {len(ticks)} ticks, {len(m5_list)} M5 bars")
print()
print(f"Config: lots={LOTS}, broker_sl=${BROKER_SL_USD}, broker_tp=${BROKER_TP_USD} (uncapped), max_concurrent={MAX_CONCURRENT}")
print(f"Testing Zee's 'no hard TP, exit on reversal' technique across trail params")
print()
print(f"{'TrailArm':>9} {'TrailGB':>8} {'Fills':>7} {'WR%':>6} {'P&L USD':>10} {'AvgWin':>8} {'AvgLoss':>8} {'BiggestWin':>11} {'Trail':>6} {'SL':>5} {'EOH':>5}")
print("-" * 100)
for trail_arm, trail_gb in TRAIL_COMBOS:
    r = run_backtest(ticks, m5_list, trail_arm, trail_gb)
    marker = " ⭐" if r["wr_pct"] >= 78 else ("" if r["wr_pct"] < 49 else " ✓")
    print(f"  {r['trail_arm']:>5.1f}p  {r['trail_gb']:>5.1f}p  {r['n']:>7} {r['wr_pct']:>5.1f}% ${r['pnl_usd']:>+8.2f} ${r['avg_win']:>+6.2f} ${r['avg_loss']:>+6.2f} ${r['biggest_win']:>+9.2f} {r['trail_exits']:>6} {r['sl_exits']:>5} {r['eoh_exits']:>5}{marker}")
print()
print("Looking for: high WR (≥78% matches Zee's manual), positive P&L, lots of TRAIL exits (not SL).")
print("Baseline (5.0/15.0) = current EA config. Compare against tighter combos.")
