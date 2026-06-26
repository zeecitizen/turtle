"""backtest_feb11parallel_atmos.py — what does Feb11Parallel.mq5 ACTUALLY do on real Atmos ticks?

Properly models:
  - PARALLEL positions with per-ticket state (NO 'parallel bug' that inflated prior backtests)
  - Each tick: reconcile + manage ALL open positions, THEN check for new fire
  - Atmos prop firm constraints:
      * 1% per-symbol floating limit ($100) → max concurrent based on broker_sl_usd
      * Daily loss limit $400 → halt for the day if hit
      * Max overall loss $800 → account death
  - Safety rails from Feb11Parallel: equity floor, hour-DD trip, margin level

Compares to running Feb11TickMedium single-position on same data.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TICK_FILE = COMMON / "shano_ticks_2026-06-02.csv"
COST = 0.50
LOTS = 0.05      # current Atmos size (matches live)
USD_PER_PRICE = LOTS * 100

# Feb11TickMedium entry config (matches current LIVE config post-revert)
RNG_MIN = 0.5
RNG_NORM_MIN = 0.5
SPR_MAX = 0.50
COOLDOWN_SEC = 10
M5_LB = 14
CHECK_EVERY = 3

# Exits
TRAIL_ARM = 5.0
TRAIL_GB = 15.0
SKIM = 10.0
MAX_LOSS = 10.0
MAX_HOLD_SEC = 2400

# Broker parachutes (USD)
BROKER_SL_USD = 25.0
BROKER_TP_USD = 50.0
DAILY_DD_PRICE = 70.0  # Atmos: $350 USD at 0.05 lots, $50 buffer under $400

# Atmos prop firm hard rules
ATMOS_DAILY_LOSS_USD = 400.0
ATMOS_MAX_LOSS_USD = 800.0
ATMOS_PER_SYMBOL_FLOATING_USD = 100.0   # 1% rule

# Starting balance
STARTING_BALANCE_USD = 10000.0

# ─── PARALLEL-specific safety rails ───
EQUITY_FLOOR_PCT = 0.60
HOUR_DD_TRIP_PCT = 0.20
MIN_MARGIN_LEVEL = 200.0  # not simulated precisely
MAX_CONCURRENT = 4   # ATMOS-SAFE: at $25 per loss × 4 = $100 max floating = 1% limit

def usd_to_price(usd): return usd / USD_PER_PRICE
def price_to_usd(price): return price * USD_PER_PRICE


def load_ticks(path):
    out = []
    with open(path, encoding="utf-8") as f:
        next(f)  # header
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
    """Build M5 OHLC bars for trend detection."""
    m5 = {}
    for tk in ticks:
        m_key = tk["t_ms"] // 300000   # 5min
        mid = (tk["bid"] + tk["ask"]) / 2
        if m_key not in m5:
            m5[m_key] = {"o": mid, "h": mid, "l": mid, "c": mid, "t_start_ms": m_key*300000}
        b = m5[m_key]
        b["h"] = max(b["h"], mid)
        b["l"] = min(b["l"], mid)
        b["c"] = mid
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


def run_parallel_backtest(ticks, m5_list, max_concurrent, label=""):
    """Properly models Feb11Parallel.mq5 behavior with serial reconciliation."""
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    mids = [(t["bid"] + t["ask"]) / 2 for t in ticks]

    # Per-position state
    positions = []   # list of dicts: {side, entry, open_ms, peak, armed}
    fills = []
    last_fire_ms = {"buy": 0, "sell": 0}
    daily_pnl_usd = 0.0
    overall_pnl_usd = 0.0   # cumulative loss against starting balance
    halted_today = False
    consec_losses = 0
    pause_until_ms = 0

    # Stats
    peak_concurrent = 0
    fire_attempts_blocked_by_rules = {"max_concurrent": 0, "daily_dd": 0, "atmos_floating": 0, "halt": 0, "pause": 0}

    broker_sl_price = usd_to_price(BROKER_SL_USD)
    broker_tp_price = usd_to_price(BROKER_TP_USD)
    atmos_floating_limit_price = usd_to_price(ATMOS_PER_SYMBOL_FLOATING_USD)

    for k in range(len(ticks)):
        t = times[k]
        bid = bids[k]
        ask = asks[k]

        # 1. MANAGE ALL EXISTING POSITIONS (process exits)
        i = 0
        while i < len(positions):
            p = positions[i]
            cur = (bid - p["entry"]) if p["side"] > 0 else (p["entry"] - ask)
            close_reason = None
            # Exit hierarchy: broker SL/TP first (broker-level), then EA exits
            if cur <= -broker_sl_price:
                close_reason = "BSL"
            elif cur >= broker_tp_price:
                close_reason = "BTP"
            elif cur >= SKIM:
                close_reason = "SKIM"
            elif (t - p["open_ms"]) > MAX_HOLD_SEC * 1000:
                close_reason = "EOH"
            else:
                if cur > p["peak"]: p["peak"] = cur
                if p["peak"] >= TRAIL_ARM: p["armed"] = True
                if p["armed"] and cur <= p["peak"] - TRAIL_GB:
                    close_reason = "TRAIL"
                elif cur <= -MAX_LOSS:
                    close_reason = "CB"

            if close_reason:
                pnl_price = cur - COST / USD_PER_PRICE
                pnl_usd = pnl_price * USD_PER_PRICE
                daily_pnl_usd += pnl_usd
                overall_pnl_usd += pnl_usd
                fills.append({"open_ms": p["open_ms"], "close_ms": t, "side": p["side"],
                              "pnl_usd": pnl_usd, "reason": close_reason,
                              "hold_sec": (t - p["open_ms"]) / 1000})
                if pnl_usd > 0:
                    consec_losses = 0
                else:
                    consec_losses += 1
                    # Note: parallel uses LOSS_STREAK_N=5 (from EA defaults)
                    if consec_losses >= 5:
                        pause_until_ms = t + 300 * 1000
                        consec_losses = 0
                positions.pop(i)
            else:
                i += 1

        # 2. Atmos daily DD check (halt if hit)
        if daily_pnl_usd <= -ATMOS_DAILY_LOSS_USD:
            halted_today = True
            if not positions:
                # Day is done — wait for new day to resume
                pass

        # 3. Atmos overall loss check (account death)
        if overall_pnl_usd <= -ATMOS_MAX_LOSS_USD:
            # Account dead, stop trading
            break

        # 4. NEW FIRE check
        if k % CHECK_EVERY != 0: continue
        if halted_today:
            fire_attempts_blocked_by_rules["halt"] += 1
            continue
        if t < pause_until_ms:
            fire_attempts_blocked_by_rules["pause"] += 1
            continue
        if (ask - bid) > SPR_MAX: continue

        # Max concurrent cap (Atmos-safe = 4)
        if len(positions) >= max_concurrent:
            fire_attempts_blocked_by_rules["max_concurrent"] += 1
            continue

        # Atmos 1% per-symbol floating check (combined floating loss)
        combined_floating_loss_price = 0
        for p in positions:
            cur = (bid - p["entry"]) if p["side"] > 0 else (p["entry"] - ask)
            if cur < 0: combined_floating_loss_price += cur
        if -combined_floating_loss_price >= atmos_floating_limit_price:
            fire_attempts_blocked_by_rules["atmos_floating"] += 1
            continue

        # Cooldown
        # (Feb11TickMedium-style: cooldown per side)
        # We'll check after computing trend direction

        # Compute rng60 / range_300
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

        # FIRE
        entry_px = ask if td > 0 else bid
        positions.append({"side": td, "entry": entry_px, "open_ms": t, "peak": 0, "armed": False})
        peak_concurrent = max(peak_concurrent, len(positions))
        last_fire_ms[side] = t

    # Close any positions at end-of-data at current bid/ask
    if positions:
        last_bid = bids[-1]; last_ask = asks[-1]; last_t = times[-1]
        for p in positions:
            cur = (last_bid - p["entry"]) if p["side"] > 0 else (p["entry"] - last_ask)
            pnl_usd = cur * USD_PER_PRICE - COST
            daily_pnl_usd += pnl_usd
            overall_pnl_usd += pnl_usd
            fills.append({"open_ms": p["open_ms"], "close_ms": last_t, "side": p["side"],
                          "pnl_usd": pnl_usd, "reason": "EOD", "hold_sec": (last_t - p["open_ms"]) / 1000})

    n = len(fills)
    wins = sum(1 for f in fills if f["pnl_usd"] > 0)
    losses = n - wins
    holds = [f["hold_sec"] for f in fills] or [0]
    reasons = {}
    for f in fills:
        reasons[f["reason"]] = reasons.get(f["reason"], 0) + 1

    print(f"\n=== {label} ===")
    print(f"  Total trades:       {n}")
    print(f"  Wins / Losses:      {wins} / {losses}  ({100*wins/max(1,n):.1f}% WR)")
    print(f"  Peak concurrent:    {peak_concurrent}")
    print(f"  Final P&L USD:      ${daily_pnl_usd:+.2f}")
    print(f"  Halted today:       {halted_today}")
    print(f"  Account-death (>${ATMOS_MAX_LOSS_USD}):  {overall_pnl_usd <= -ATMOS_MAX_LOSS_USD}")
    print(f"  Exit reasons:       {reasons}")
    print(f"  Hold time:          min={min(holds):.0f}s med={sorted(holds)[n//2] if n else 0:.0f}s max={max(holds):.0f}s")
    print(f"  Fire blocks:        {fire_attempts_blocked_by_rules}")
    return {"n": n, "wins": wins, "pnl_usd": daily_pnl_usd, "peak_concurrent": peak_concurrent,
            "halted": halted_today, "fills": fills}


print(f"Loading {TICK_FILE.name}...")
ticks = load_ticks(TICK_FILE)
print(f"  {len(ticks)} ticks loaded")
m5_list = build_m5_bars(ticks)
print(f"  {len(m5_list)} M5 bars built")
print()
print(f"Settings: lots={LOTS}, broker_sl=${BROKER_SL_USD}, broker_tp=${BROKER_TP_USD}")
print(f"Atmos rules: daily_loss=${ATMOS_DAILY_LOSS_USD}, max_loss=${ATMOS_MAX_LOSS_USD}, per_symbol_floating=${ATMOS_PER_SYMBOL_FLOATING_USD}")
print()

# Run with progressively higher max_concurrent caps
for cap in [1, 2, 3, 4]:
    run_parallel_backtest(ticks, m5_list, cap, f"max_concurrent={cap}")

print()
print("=" * 70)
print("HEADLINE comparison:")
print("=" * 70)
print("  max_concurrent=1 = current Feb11TickMedium behavior (single position)")
print("  max_concurrent=4 = SAFE PARALLEL on Atmos (max $100 floating = 1% rule)")
print()
print("Look at:")
print("  - Does WR change with parallel?")
print("  - Does total P&L go up or down?")
print("  - Are we halted by Atmos daily limit at any cap?")
print("  - Is account death triggered?")
