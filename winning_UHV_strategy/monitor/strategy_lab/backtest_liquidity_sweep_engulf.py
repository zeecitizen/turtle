"""backtest_liquidity_sweep_engulf.py — Lesson 10 strategy on real ticks.

Implements Zee's Lesson 10 mechanics:
  Setup (UPTREND BUY):
    1. D1 trend = UP (last 3 daily closes ascending)
    2. FVG marked on M15 (3-bar gap pattern: bar1.high < bar3.low = bullish FVG)
    3. Market retraces to TAP the FVG
    4. At FVG zone: find the LAST RED CANDLE before reversal
    5. GREEN candle forms with:
       - Wick BELOW sweeps the red's LOW
       - CLOSE inside the red body
       - Volume > volume of red (institutional engulfing)
       - Small wick ABOVE (no upper rejection)
    6. ENTRY: at close of the sweep+engulf green candle
    7. STOP: below the swept wick low
    8. TARGET: structural high (previous swing high)

  Mirror for DOWNTREND SELL.

Tests on June 1, June 2 (Atmos data we have). Reports WR + P&L + exit reasons.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TEST_FILES = [
    COMMON / "shano_ticks_2026-02-11.csv",   # Zee's $835/65W/4L gold-standard day
    COMMON / "shano_ticks_2026-06-01.csv",
    COMMON / "shano_ticks_2026-06-02.csv",
]

LOTS = 0.05
USD_PER_PRICE = LOTS * 100
SPREAD_MAX = 0.50
COOLDOWN_SEC = 60
MAX_HOLD_SEC = 1800   # 30 min — pattern works on faster moves
MAX_CONCURRENT = 4

# Detection params — Zee said red can be SMALL volume, GREEN just needs to be BIGGER
FVG_LOOKBACK_M15 = 20
FVG_MIN_SIZE = 0.30
RETRACE_TAP_TOLERANCE = 0.05
SWEEP_MIN_WICK = 0.08
ENGULF_VOL_MULT = 1.05        # just bigger than red (Zee's exact words)
UPPER_WICK_MAX_RATIO = 0.30
ENGULF_MIN_BODY_RATIO = 0.40
CLOSE_INSIDE_DEPTH = 0.50     # NEW: close must be at least 50% into red's body
COST_USD = 1.0

# Per-position exits (matches Atmos broker SL/TP we use)
BROKER_SL_USD = 25.0
BROKER_TP_USD = 50.0  # initial TP — we'll trail beyond this on hold


def load_ticks(path):
    """Handles BOTH formats:
       (A) Feb 11 export: 't,bid,ask' header, ts='2026.02.11 01:00:09.108'
       (B) ShanoTickLogger: 'ts_broker,ms,bid,ask,last,volume', ts='2026.06.02 12:24:37'"""
    if not path.exists(): return []
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
                    t_ms = int(dt.timestamp() * 1000) + ms
                    out.append({"t_ms": t_ms, "bid": float(parts[2]), "ask": float(parts[3])})
                else:
                    if len(parts) < 3: continue
                    t_str = parts[0]
                    date_p, time_p = t_str.split(" ")
                    hms, ms_str = time_p.split(".") if "." in time_p else (time_p, "0")
                    dt = datetime.strptime(date_p + " " + hms, "%Y.%m.%d %H:%M:%S")
                    t_ms = int(dt.timestamp() * 1000) + int(ms_str)
                    out.append({"t_ms": t_ms, "bid": float(parts[1]), "ask": float(parts[2])})
            except: continue
    return out


def build_bars(ticks, period_ms):
    """Build OHLCV bars from ticks at given period."""
    bars = {}
    for tk in ticks:
        m_key = tk["t_ms"] // period_ms
        mid = (tk["bid"] + tk["ask"]) / 2
        if m_key not in bars:
            bars[m_key] = {"o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
                           "t_start_ms": m_key * period_ms, "t_end_ms": (m_key + 1) * period_ms - 1}
        b = bars[m_key]
        b["h"] = max(b["h"], mid)
        b["l"] = min(b["l"], mid)
        b["c"] = mid
        b["v"] += 1
    return [bars[k] for k in sorted(bars.keys())]


def detect_fvgs(m15_bars):
    """Find FVGs in M15 bars. Returns list of {type, top, bottom, formed_at_ms}.
    Bullish FVG: bar[i+2].low > bar[i].high  (gap between bar[i] and bar[i+2])
    Bearish FVG: bar[i+2].high < bar[i].low"""
    fvgs = []
    for i in range(len(m15_bars) - 2):
        b1, b2, b3 = m15_bars[i], m15_bars[i+1], m15_bars[i+2]
        # Bullish FVG (gap up): b3.low > b1.high
        if b3["l"] > b1["h"] and (b3["l"] - b1["h"]) >= FVG_MIN_SIZE:
            fvgs.append({"type": "bull", "top": b3["l"], "bottom": b1["h"],
                         "formed_at_ms": b3["t_start_ms"], "mitigated": False})
        # Bearish FVG (gap down): b3.high < b1.low
        elif b3["h"] < b1["l"] and (b1["l"] - b3["h"]) >= FVG_MIN_SIZE:
            fvgs.append({"type": "bear", "top": b1["l"], "bottom": b3["h"],
                         "formed_at_ms": b3["t_start_ms"], "mitigated": False})
    return fvgs


def trend_dir(bars, ts_ms, lb=10):
    """Simple trend: current price vs price `lb` bars ago. Above MA = uptrend.
    More robust against retracements than HH+HL since retracement IS the entry."""
    relevant = [b for b in bars if b["t_end_ms"] < ts_ms]
    if len(relevant) < lb: return 0
    # Compare current close vs close `lb` bars ago
    cur_close = relevant[-1]["c"]
    past_close = relevant[-lb]["c"]
    diff = cur_close - past_close
    # Require meaningful diff (>= $1 over the lookback period)
    if diff >= 1.0: return +1
    if diff <= -1.0: return -1
    return 0


def d1_trend(d1_bars, ts_ms):
    """Backward-compat name."""
    return trend_dir(d1_bars, ts_ms, lb=3)


def is_at_fvg(price, fvg):
    """Check if price is within the FVG range (tapping it)."""
    return fvg["bottom"] - RETRACE_TAP_TOLERANCE <= price <= fvg["top"] + RETRACE_TAP_TOLERANCE


def detect_sweep_engulf_long(m1_bars, idx, last_red_bar):
    """Green sweep+engulf at idx of last_red_bar (BUY setup)."""
    bar = m1_bars[idx]
    if bar["c"] <= bar["o"]: return False  # must be green
    rng = bar["h"] - bar["l"]
    if rng <= 0: return False
    body = abs(bar["c"] - bar["o"])
    if body / rng < ENGULF_MIN_BODY_RATIO: return False
    # Sweep wick below red's low
    if bar["l"] >= last_red_bar["l"] - SWEEP_MIN_WICK: return False
    # Close inside red's body AND deep (closer to red's high than its low)
    red_body_low = min(last_red_bar["o"], last_red_bar["c"])
    red_body_high = max(last_red_bar["o"], last_red_bar["c"])
    red_body_range = red_body_high - red_body_low
    if red_body_range <= 0: return False
    if bar["c"] < red_body_low: return False  # close must be above red's body bottom
    # Close depth into red's body (0=at low, 1=at high)
    depth = (bar["c"] - red_body_low) / red_body_range
    if depth < CLOSE_INSIDE_DEPTH: return False
    # Volume bigger than red
    if bar["v"] <= last_red_bar["v"] * ENGULF_VOL_MULT: return False
    # Small upper wick
    upper_wick = bar["h"] - bar["c"]
    if upper_wick / rng > UPPER_WICK_MAX_RATIO: return False
    return True


def detect_sweep_engulf_short(m1_bars, idx, last_green_bar):
    bar = m1_bars[idx]
    if bar["c"] >= bar["o"]: return False
    rng = bar["h"] - bar["l"]
    if rng <= 0: return False
    body = abs(bar["c"] - bar["o"])
    if body / rng < ENGULF_MIN_BODY_RATIO: return False
    if bar["h"] <= last_green_bar["h"] + SWEEP_MIN_WICK: return False
    grn_body_low = min(last_green_bar["o"], last_green_bar["c"])
    grn_body_high = max(last_green_bar["o"], last_green_bar["c"])
    grn_body_range = grn_body_high - grn_body_low
    if grn_body_range <= 0: return False
    if bar["c"] > grn_body_high: return False
    depth = (grn_body_high - bar["c"]) / grn_body_range
    if depth < CLOSE_INSIDE_DEPTH: return False
    if bar["v"] <= last_green_bar["v"] * ENGULF_VOL_MULT: return False
    lower_wick = bar["c"] - bar["l"]
    if lower_wick / rng > UPPER_WICK_MAX_RATIO: return False
    return True


def find_last_red_in_window(m1_bars, start_idx, end_idx):
    for i in range(end_idx - 1, start_idx - 1, -1):
        if m1_bars[i]["c"] < m1_bars[i]["o"]:
            return i, m1_bars[i]
    return -1, None


def find_last_green_in_window(m1_bars, start_idx, end_idx):
    for i in range(end_idx - 1, start_idx - 1, -1):
        if m1_bars[i]["c"] > m1_bars[i]["o"]:
            return i, m1_bars[i]
    return -1, None


def find_structural_high(m1_bars, ref_idx, lookback=30):
    """Find highest high in last `lookback` bars before ref_idx."""
    start = max(0, ref_idx - lookback)
    return max(m1_bars[i]["h"] for i in range(start, ref_idx))


def find_structural_low(m1_bars, ref_idx, lookback=30):
    start = max(0, ref_idx - lookback)
    return min(m1_bars[i]["l"] for i in range(start, ref_idx))


def run_backtest(ticks, m1_bars, m15_bars, h1_bars, d1_bars, verbose=False):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    fvgs = detect_fvgs(m15_bars)

    positions = []
    fills = []
    last_fire_ms = 0
    daily_pnl_usd = 0
    diag = {"new_m1_bars": 0, "fvg_tap_candidates": 0, "trend_fail": 0,
            "no_red_found": 0, "no_green_found": 0,
            "sweep_engulf_fail_long": 0, "sweep_engulf_fail_short": 0,
            "entries": 0}

    # Lesson 10 EXITS: stop below sweep wick, TP at structural high
    # Hard cap broker SL only as ultimate safety
    broker_sl_price_max = BROKER_SL_USD / USD_PER_PRICE   # ultimate parachute

    # Iterate M1 bars (decisions made at M1 close)
    m1_idx = 0
    for tick_idx in range(len(ticks)):
        t = times[tick_idx]
        bid = bids[tick_idx]
        ask = asks[tick_idx]

        # Manage open positions — Lesson 10 exits: stop below sweep wick, TP at structural high
        i = 0
        while i < len(positions):
            p = positions[i]
            cur = (bid - p["entry"]) if p["side"] > 0 else (p["entry"] - ask)
            close_reason = None
            # Pattern-specific stop (below sweep wick)
            if p["side"] > 0:
                # Stop: bid below sweep_low
                if bid <= p["sweep_low"]: close_reason = "PSL"
                # TP: bid reaches structural_high
                elif bid >= p["target"]: close_reason = "PTP"
            else:
                if ask >= p["sweep_high"]: close_reason = "PSL"
                elif ask <= p["target"]: close_reason = "PTP"
            # Safety: broker SL as ultimate parachute
            if not close_reason and cur <= -broker_sl_price_max: close_reason = "BSL"
            # Time stop
            if not close_reason and (t - p["open_ms"]) > MAX_HOLD_SEC * 1000:
                close_reason = "EOH"
            if close_reason:
                pnl_usd = cur * USD_PER_PRICE - COST_USD
                daily_pnl_usd += pnl_usd
                fills.append({"pnl_usd": pnl_usd, "reason": close_reason,
                              "hold_sec": (t - p["open_ms"]) / 1000})
                positions.pop(i)
            else: i += 1

        # Move m1_idx forward to bar containing this tick
        while m1_idx < len(m1_bars) - 1 and m1_bars[m1_idx]["t_end_ms"] < t:
            # New M1 bar just closed — check for entry signal
            check_bar_idx = m1_idx
            diag["new_m1_bars"] += 1
            if check_bar_idx >= 5 and len(positions) < MAX_CONCURRENT:
                if (ask - bid) <= SPREAD_MAX and (t - last_fire_ms) >= COOLDOWN_SEC * 1000:
                    bar = m1_bars[check_bar_idx]
                    # Use H1 trend (more reliable than D1 for intraday data)
                    # Loosen trend check: lb=4 (was 6) so more setups qualify
                    trend = trend_dir(h1_bars, t, lb=4)
                    # Find active FVG that this bar TAPS
                    for fvg in fvgs:
                        if fvg["mitigated"]: continue
                        if fvg["formed_at_ms"] >= t: continue
                        # Check if bar touches the FVG zone
                        bar_touches_fvg = (
                            (fvg["type"] == "bull" and bar["l"] <= fvg["top"] + RETRACE_TAP_TOLERANCE)
                            or (fvg["type"] == "bear" and bar["h"] >= fvg["bottom"] - RETRACE_TAP_TOLERANCE)
                        )
                        if not bar_touches_fvg: continue
                        diag["fvg_tap_candidates"] += 1
                        # Trend check
                        if (trend == +1 and fvg["type"] == "bull"):
                            red_idx, red_bar = find_last_red_in_window(m1_bars, max(0, check_bar_idx - 5), check_bar_idx)
                            if red_bar is None: diag["no_red_found"] += 1; continue
                            if detect_sweep_engulf_long(m1_bars, check_bar_idx, red_bar):
                                entry_px = ask
                                # Pattern stops + targets
                                sweep_low = m1_bars[check_bar_idx]["l"] - 0.05  # buffer below wick
                                structural_high = find_structural_high(m1_bars, check_bar_idx, lookback=30)
                                # If structural high is below entry (shouldn't happen) → use 1:1 RR
                                if structural_high <= entry_px:
                                    structural_high = entry_px + (entry_px - sweep_low)  # 1:1 RR
                                positions.append({"side": +1, "entry": entry_px, "open_ms": t,
                                                  "fvg": fvg, "red_idx": red_idx,
                                                  "sweep_low": sweep_low, "target": structural_high})
                                last_fire_ms = t
                                fvg["mitigated"] = True
                                diag["entries"] += 1
                                break
                            else:
                                diag["sweep_engulf_fail_long"] += 1
                        elif (trend == -1 and fvg["type"] == "bear"):
                            grn_idx, grn_bar = find_last_green_in_window(m1_bars, max(0, check_bar_idx - 5), check_bar_idx)
                            if grn_bar is None: diag["no_green_found"] += 1; continue
                            if detect_sweep_engulf_short(m1_bars, check_bar_idx, grn_bar):
                                entry_px = bid
                                sweep_high = m1_bars[check_bar_idx]["h"] + 0.05
                                structural_low = find_structural_low(m1_bars, check_bar_idx, lookback=30)
                                if structural_low >= entry_px:
                                    structural_low = entry_px - (sweep_high - entry_px)
                                positions.append({"side": -1, "entry": entry_px, "open_ms": t,
                                                  "fvg": fvg, "green_idx": grn_idx,
                                                  "sweep_high": sweep_high, "target": structural_low})
                                last_fire_ms = t
                                fvg["mitigated"] = True
                                diag["entries"] += 1
                                break
                            else:
                                diag["sweep_engulf_fail_short"] += 1
                        else:
                            diag["trend_fail"] += 1
            m1_idx += 1

    # Close remaining at end
    if positions:
        last_bid = bids[-1]; last_ask = asks[-1]
        for p in positions:
            cur = (last_bid - p["entry"]) if p["side"] > 0 else (p["entry"] - last_ask)
            pnl_usd = cur * USD_PER_PRICE - COST_USD
            daily_pnl_usd += pnl_usd
            fills.append({"pnl_usd": pnl_usd, "reason": "EOD",
                          "hold_sec": (times[-1] - p["open_ms"]) / 1000})

    n = len(fills)
    wins = sum(1 for f in fills if f["pnl_usd"] > 0)
    return {"n": n, "wins": wins, "wr": 100*wins/max(1,n), "pnl_usd": daily_pnl_usd,
            "n_fvgs": len(fvgs), "fills": fills, "diag": diag}


print("=== Lesson 10 — Liquidity Sweep + Engulf — BACKTEST ===")
print(f"Lot: {LOTS}, broker SL: ${BROKER_SL_USD}, broker TP: ${BROKER_TP_USD}, max concurrent: {MAX_CONCURRENT}")
print(f"FVG: M15 lookback={FVG_LOOKBACK_M15}, min size=${FVG_MIN_SIZE}, tap tolerance=${RETRACE_TAP_TOLERANCE}")
print(f"Sweep: wick >= ${SWEEP_MIN_WICK} beyond extreme")
print(f"Engulf: vol ratio >= {ENGULF_VOL_MULT}× swept candle vol")
print()

# Need D1 bars — we don't have D1 tick files, so synthesize from M1 if available
# For now, treat each day's data as a single D1 with simple trend detection

all_trades = 0; all_wins = 0; all_pnl = 0
for path in TEST_FILES:
    if not path.exists():
        print(f"SKIP {path.name} (missing)")
        continue
    label = path.stem.replace("shano_ticks_", "")
    print(f"\n--- {label} ---")
    ticks = load_ticks(path)
    m1 = build_bars(ticks, 60_000)
    m5 = build_bars(ticks, 300_000)
    m15 = build_bars(ticks, 900_000)
    h1 = build_bars(ticks, 3_600_000)
    d1 = [{"o": ticks[0]["bid"], "h": max(t["bid"] for t in ticks),
           "l": min(t["bid"] for t in ticks), "c": ticks[-1]["bid"],
           "t_start_ms": ticks[0]["t_ms"], "t_end_ms": ticks[-1]["t_ms"]}] if ticks else []
    print(f"  {len(ticks)} ticks, {len(m1)} M1, {len(m15)} M15, {len(h1)} H1")
    r = run_backtest(ticks, m1, m15, h1, d1)
    print(f"  FVGs detected on M15: {r['n_fvgs']}")
    print(f"  Trades: {r['n']}  ({r['wins']}W / {r['n']-r['wins']}L = {r['wr']:.1f}% WR)")
    print(f"  P&L: ${r['pnl_usd']:+.2f}")
    print(f"  Diagnostic: {r['diag']}")
    if r['fills']:
        reasons = {}
        for f in r['fills']:
            reasons[f['reason']] = reasons.get(f['reason'], 0) + 1
        print(f"  Exit reasons: {reasons}")
    all_trades += r['n']; all_wins += r['wins']; all_pnl += r['pnl_usd']

print(f"\n=== TOTAL ===")
print(f"Trades: {all_trades}, WR: {100*all_wins/max(1,all_trades):.1f}%, P&L: ${all_pnl:+.2f}")
