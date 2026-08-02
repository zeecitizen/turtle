"""backtest_lesson02_uhv_simple.py — Zee's Lesson 02 baseline EXACTLY as taught.

Pattern (UPTREND BUY):
  1. M5 trend = UP (simple: last close > 10-bar-ago close)
  2. Find UHV: red candle in last 10 bars with highest volume
  3. Wait for green candle to body-break UHV's HIGH with LOWER volume
  4. Enter at break close
  5. Stop: below UHV's LOW
  6. TP: 1:1 RR from entry (Zee's exact words)

Same for SELL mirror.

Goal: see if SIMPLEST mechanical interpretation produces meaningful WR.
"""
import sys, bisect
from datetime import datetime
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")   # no console under pythonw -> stdout is None
except Exception:
    pass

COMMON = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
TEST_FILES = [
    COMMON / "shano_ticks_2026-02-11.csv",
    COMMON / "shano_ticks_2026-06-01.csv",
    COMMON / "shano_ticks_2026-06-02.csv",
]

LOTS = 0.05
USD_PER_PRICE = LOTS * 100
SPREAD_MAX = 0.50
COOLDOWN_SEC = 60
MAX_HOLD_SEC = 600
MAX_CONCURRENT = 4

UHV_LOOKBACK = 10
UHV_VOL_MULT = 1.5
BREAKOUT_BUFFER = 0.05
COST_USD = 1.0
BROKER_SL_USD = 25.0  # max ultimate parachute


def load_ticks(path):
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
    bars = {}
    for tk in ticks:
        m_key = tk["t_ms"] // period_ms
        mid = (tk["bid"] + tk["ask"]) / 2
        if m_key not in bars:
            bars[m_key] = {"o": mid, "h": mid, "l": mid, "c": mid, "v": 1,
                           "t_start_ms": m_key * period_ms, "t_end_ms": (m_key + 1) * period_ms - 1}
        b = bars[m_key]
        b["h"] = max(b["h"], mid); b["l"] = min(b["l"], mid); b["c"] = mid; b["v"] += 1
    return [bars[k] for k in sorted(bars.keys())]


def trend_up(bars, idx, lb=10):
    """Trend up if current close > close lb bars ago by at least $0.5."""
    if idx < lb: return False
    return bars[idx-1]["c"] - bars[idx-lb]["c"] >= 0.5


def trend_down(bars, idx, lb=10):
    if idx < lb: return False
    return bars[idx-lb]["c"] - bars[idx-1]["c"] >= 0.5


def find_uhv_red_in_lookback(m1_bars, idx, lookback):
    """Find the RED candle with highest volume in last `lookback` bars before idx."""
    best_idx = -1; best_vol = 0
    for i in range(max(0, idx - lookback), idx):
        b = m1_bars[i]
        if b["c"] < b["o"] and b["v"] > best_vol:
            best_vol = b["v"]; best_idx = i
    if best_idx == -1: return None
    # Verify it's "ultra high" — at least UHV_VOL_MULT × average of others
    other_vols = [m1_bars[i]["v"] for i in range(max(0, idx-lookback), idx) if i != best_idx]
    if not other_vols: return None
    avg_other = sum(other_vols) / len(other_vols)
    if best_vol < UHV_VOL_MULT * avg_other: return None
    return m1_bars[best_idx]


def find_uhv_green_in_lookback(m1_bars, idx, lookback):
    best_idx = -1; best_vol = 0
    for i in range(max(0, idx - lookback), idx):
        b = m1_bars[i]
        if b["c"] > b["o"] and b["v"] > best_vol:
            best_vol = b["v"]; best_idx = i
    if best_idx == -1: return None
    other_vols = [m1_bars[i]["v"] for i in range(max(0, idx-lookback), idx) if i != best_idx]
    if not other_vols: return None
    avg_other = sum(other_vols) / len(other_vols)
    if best_vol < UHV_VOL_MULT * avg_other: return None
    return m1_bars[best_idx]


def run_backtest(ticks, m1_bars, m5_bars):
    times = [t["t_ms"] for t in ticks]
    bids = [t["bid"] for t in ticks]
    asks = [t["ask"] for t in ticks]
    positions = []
    fills = []
    last_fire_ms = 0
    diag = {"checks": 0, "trend_fail": 0, "no_uhv": 0, "no_break": 0, "entries": 0}
    broker_sl_price = BROKER_SL_USD / USD_PER_PRICE

    m1_idx = 0
    for tick_idx in range(len(ticks)):
        t = times[tick_idx]; bid = bids[tick_idx]; ask = asks[tick_idx]

        # Manage positions
        i = 0
        while i < len(positions):
            p = positions[i]
            cur = (bid - p["entry"]) if p["side"] > 0 else (p["entry"] - ask)
            close_reason = None
            if p["side"] > 0:
                if bid <= p["sl"]: close_reason = "SL"
                elif bid >= p["tp"]: close_reason = "TP"
            else:
                if ask >= p["sl"]: close_reason = "SL"
                elif ask <= p["tp"]: close_reason = "TP"
            if not close_reason and cur <= -broker_sl_price: close_reason = "BSL"
            if not close_reason and (t - p["open_ms"]) > MAX_HOLD_SEC * 1000:
                close_reason = "EOH"
            if close_reason:
                pnl_usd = cur * USD_PER_PRICE - COST_USD
                fills.append({"pnl_usd": pnl_usd, "reason": close_reason})
                positions.pop(i)
            else: i += 1

        # New M1 bar close → check entry
        while m1_idx < len(m1_bars) - 1 and m1_bars[m1_idx]["t_end_ms"] < t:
            check_bar_idx = m1_idx
            if (check_bar_idx >= UHV_LOOKBACK + 1 and len(positions) < MAX_CONCURRENT
                and (ask - bid) <= SPREAD_MAX and (t - last_fire_ms) >= COOLDOWN_SEC * 1000):
                diag["checks"] += 1
                bar = m1_bars[check_bar_idx]

                # Try LONG (uptrend + UHV red + green breakout)
                if trend_up(m1_bars, check_bar_idx, lb=10):
                    uhv = find_uhv_red_in_lookback(m1_bars, check_bar_idx, UHV_LOOKBACK)
                    if uhv is None:
                        diag["no_uhv"] += 1
                    elif bar["c"] > uhv["h"] + BREAKOUT_BUFFER and bar["c"] > bar["o"] and bar["v"] < uhv["v"]:
                        # Entry!
                        entry_px = ask
                        sl_px = uhv["l"] - 0.05
                        risk = entry_px - sl_px
                        if risk > 0 and risk < broker_sl_price + 1:  # only if RR feasible
                            tp_px = entry_px + risk  # 1:1 RR
                            positions.append({"side": +1, "entry": entry_px, "open_ms": t,
                                              "sl": sl_px, "tp": tp_px})
                            last_fire_ms = t
                            diag["entries"] += 1
                    else:
                        diag["no_break"] += 1
                elif trend_down(m1_bars, check_bar_idx, lb=10):
                    uhv = find_uhv_green_in_lookback(m1_bars, check_bar_idx, UHV_LOOKBACK)
                    if uhv is None:
                        diag["no_uhv"] += 1
                    elif bar["c"] < uhv["l"] - BREAKOUT_BUFFER and bar["c"] < bar["o"] and bar["v"] < uhv["v"]:
                        entry_px = bid
                        sl_px = uhv["h"] + 0.05
                        risk = sl_px - entry_px
                        if risk > 0 and risk < broker_sl_price + 1:
                            tp_px = entry_px - risk
                            positions.append({"side": -1, "entry": entry_px, "open_ms": t,
                                              "sl": sl_px, "tp": tp_px})
                            last_fire_ms = t
                            diag["entries"] += 1
                    else:
                        diag["no_break"] += 1
                else:
                    diag["trend_fail"] += 1
            m1_idx += 1

    # End-of-data close
    if positions:
        last_bid = bids[-1]; last_ask = asks[-1]
        for p in positions:
            cur = (last_bid - p["entry"]) if p["side"] > 0 else (p["entry"] - last_ask)
            pnl_usd = cur * USD_PER_PRICE - COST_USD
            fills.append({"pnl_usd": pnl_usd, "reason": "EOD"})

    n = len(fills)
    wins = sum(1 for f in fills if f["pnl_usd"] > 0)
    pnl = sum(f["pnl_usd"] for f in fills)
    return {"n": n, "wins": wins, "wr": 100*wins/max(1,n), "pnl_usd": pnl, "diag": diag,
            "fills": fills}


print("=== Lesson 02 — UHV Simple Backtest (1:1 R:R as Zee taught) ===\n")
all_n = 0; all_w = 0; all_pnl = 0
for path in TEST_FILES:
    if not path.exists(): continue
    label = path.stem.replace("shano_ticks_", "")
    print(f"--- {label} ---")
    ticks = load_ticks(path)
    m1 = build_bars(ticks, 60_000)
    m5 = build_bars(ticks, 300_000)
    print(f"  {len(ticks)} ticks, {len(m1)} M1 bars")
    r = run_backtest(ticks, m1, m5)
    print(f"  Trades: {r['n']}  WR: {r['wr']:.1f}% ({r['wins']}W/{r['n']-r['wins']}L)  P&L: ${r['pnl_usd']:+.2f}")
    if r['fills']:
        reasons = {}
        for f in r['fills']:
            reasons[f['reason']] = reasons.get(f['reason'], 0) + 1
        print(f"  Reasons: {reasons}")
    print(f"  Diag: {r['diag']}")
    all_n += r['n']; all_w += r['wins']; all_pnl += r['pnl_usd']
    print()

print(f"=== TOTAL ===")
print(f"Trades: {all_n}, WR: {100*all_w/max(1,all_n):.1f}%, P&L: ${all_pnl:+.2f}")
