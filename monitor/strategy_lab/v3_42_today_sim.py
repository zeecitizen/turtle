"""
v3_42_today_sim.py — simulate v3.42 EA logic on today's M1 bars and
compare entries to Shano's actual trades.

v3.42 differences from prior sim:
  - No UHV+side dedup
  - Detection runs every tick (we approximate by detecting on EVERY bar
    after the first valid breakout — emulates intra-bar re-detection)
  - 2-second rate-limit between fires
  - Broker-side trailing SL: peak >= $1 → SL locks at peak - $0.50

For comparing to Shano: we just need ENTRY TIMES and entry prices.
Exit P&L estimation uses the OHLC peak-trail approximation.
"""
from __future__ import annotations
import csv
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

# v3.42 parameters
MAX_LOOKBACK     = 60
MAX_BARS_BACK    = 60
PEAK_BANK_USD    = 1.0
PEAK_DROP_USD    = 0.5
EARLY_STOP_USD   = 2.0
EARLY_PEAK_GUARD = 1.0
EARLY_MIN_BARS   = 1
LOTS             = 0.10
PNL_PER_POINT    = LOTS * 100  # $10 per point on XAU 0.10 lot

# Shano's setups today
SHANO_SETUPS = [
    ('02:07:45', 'buy',  0.10,  3.58),
    ('02:09:06', 'buy',  0.02,  3.72),
    ('02:09:27', 'sell', 0.10,  0.32),
    ('02:10:01', 'sell', 0.10, 11.28),
    ('02:10:30', 'sell', 0.01,  0.38),
    ('02:11:14', 'buy',  0.10, 27.76),
    ('02:14:28', 'sell', 0.10, -0.64),
    ('02:14:42', 'sell', 0.40,  2.00),
    ('02:20:05', 'sell', 0.10, 27.76),
    ('02:22:54', 'buy',  0.10,  5.76),
    ('02:23:42', 'buy',  0.40,  8.40),
    ('02:24:40', 'buy',  0.10,  9.20),
    ('02:24:50', 'buy',  0.40, 30.40),
    ('02:27:08', 'sell', 0.10,  2.56),
    ('02:30:27', 'sell', 0.40,  5.20),
    ('02:30:35', 'sell', 0.10,  0.56),
    ('02:34:54', 'sell', 0.40,  3.20),
    ('02:35:54', 'sell', 0.40, 30.40),
]


def load_bars(path):
    bars = []
    with open(path) as f:
        for r in csv.DictReader(f):
            bars.append({
                "time": datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S"),
                "open": float(r["open"]), "high": float(r["high"]),
                "low": float(r["low"]),   "close": float(r["close"]),
                "vol": int(r["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars


def detect_at(bars, idx_bo):
    """Returns dict or None — replicates v3.42 detect on bar at idx_bo."""
    bo = bars[idx_bo]
    is_green = bo["close"] > bo["open"]
    is_red   = bo["close"] < bo["open"]

    # BUY
    if is_green:
        reds = []
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["high"] >= bo["close"]: break
            if c["close"] < c["open"]: reds.append((k, c))
        if not reds: return None
        k_uhv, uhv = max(reds, key=lambda kc: kc[1]["vol"])
        if (idx_bo - k_uhv) > MAX_BARS_BACK: return None
        if bo["close"] <= uhv["high"]: return None
        if bo["vol"] >= uhv["vol"]: return None
        return {"side": "buy", "uhv": uhv, "bars_back": idx_bo - k_uhv,
                "bo": bo, "bo_idx": idx_bo}
    # SELL
    if is_red:
        greens = []
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["low"] <= bo["close"]: break
            if c["close"] > c["open"]: greens.append((k, c))
        if not greens: return None
        k_uhv, uhv = max(greens, key=lambda kc: kc[1]["vol"])
        if (idx_bo - k_uhv) > MAX_BARS_BACK: return None
        if bo["close"] >= uhv["low"]: return None
        if bo["vol"] >= uhv["vol"]: return None
        return {"side": "sell", "uhv": uhv, "bars_back": idx_bo - k_uhv,
                "bo": bo, "bo_idx": idx_bo}
    return None


def simulate_v342(bars, window_from, window_to):
    """Walk forward bar by bar, fire entries per v3.42 logic, simulate exits
    via peak-trail with broker-side SL lock (approximated).
    """
    # Find bar indices within window
    idx_start = next((i for i, b in enumerate(bars) if b["time"] >= window_from), len(bars))
    idx_end   = next((i for i, b in enumerate(bars) if b["time"] >= window_to),   len(bars))
    if idx_start <= MAX_LOOKBACK + 5: idx_start = MAX_LOOKBACK + 5

    trades = []
    open_trade = None   # current open simulated position
    last_fire_time = None

    for i in range(idx_start, idx_end):
        b = bars[i]
        # ── MANAGE OPEN ──
        if open_trade is not None:
            entry = open_trade["entry"]
            side  = open_trade["side"]
            sl_init = open_trade["sl_init"]   # UHV.low/high catastrophic
            locked  = open_trade["locked_pnl"]
            peak    = open_trade["peak"]

            # Compute fav/adv extremes pnl for this bar
            if side == "buy":
                fav_pnl = (b["high"] - entry) * PNL_PER_POINT
                adv_pnl = (b["low"]  - entry) * PNL_PER_POINT
                sl_hit  = b["low"] <= sl_init
            else:
                fav_pnl = (entry - b["low"])  * PNL_PER_POINT
                adv_pnl = (entry - b["high"]) * PNL_PER_POINT
                sl_hit  = b["high"] >= sl_init

            new_peak = max(peak, fav_pnl)

            # If broker-trail SL is locked above current price, it would fill at lock level
            # In OHLC terms: if bar.low (buy) crosses the locked-price threshold,
            # exit at locked_pnl.
            close_now = None
            close_reason = None

            # Catastrophic SL first
            if sl_hit:
                close_now = sl_init
                close_pnl = (sl_init - entry) * PNL_PER_POINT if side == "buy" else (entry - sl_init) * PNL_PER_POINT
                close_reason = "sl"

            # Broker-trail SL active (locked > 0): bar's adverse extreme reaching lock_price triggers
            if close_now is None and locked > 0:
                # lock_price in price terms (for buy: above entry)
                if side == "buy":
                    lock_price = entry + locked / PNL_PER_POINT
                    if b["low"] <= lock_price:
                        close_now = lock_price
                        close_pnl = locked
                        close_reason = "trail_lock"
                else:
                    lock_price = entry - locked / PNL_PER_POINT
                    if b["high"] >= lock_price:
                        close_now = lock_price
                        close_pnl = locked
                        close_reason = "trail_lock"

            # Smart cut: peak < guard and adverse <= -EARLY_STOP_USD
            if close_now is None and new_peak < EARLY_PEAK_GUARD:
                if adv_pnl <= -EARLY_STOP_USD:
                    bars_in_pos = i - open_trade["entry_idx"]
                    if bars_in_pos >= EARLY_MIN_BARS:
                        close_now = entry  # approximate at -EARLY_STOP_USD
                        close_pnl = -EARLY_STOP_USD
                        close_reason = "smart_cut"

            # If new peak crossed bank threshold, set lock
            if close_now is None and new_peak >= PEAK_BANK_USD:
                target_lock = new_peak - PEAK_DROP_USD
                if target_lock > locked:
                    open_trade["locked_pnl"] = target_lock
                    locked = target_lock

            # Update peak
            open_trade["peak"] = new_peak

            if close_now is not None:
                open_trade["close_time"] = b["time"]
                open_trade["close_pnl"] = close_pnl
                open_trade["close_reason"] = close_reason
                trades.append(open_trade)
                open_trade = None
                # Note: ongoing detection in this iteration too

        # ── DETECT + FIRE (when no open trade) ──
        if open_trade is None:
            # Rate limit
            if last_fire_time is not None and (b["time"] - last_fire_time).total_seconds() < 2:
                continue
            sig = detect_at(bars, i)
            if sig is None: continue
            # v3.42 fires intra-bar in reality; in sim assume fire at bar.close timestamp
            side = sig["side"]
            entry = bars[i]["close"]   # approximation
            sl = sig["uhv"]["low"] if side == "buy" else sig["uhv"]["high"]
            open_trade = {
                "entry_time": b["time"], "side": side, "entry": entry,
                "sl_init": sl, "peak": 0.0, "locked_pnl": 0.0,
                "entry_idx": i, "uhv_time": sig["uhv"]["time"],
            }
            last_fire_time = b["time"]

    return trades


def main():
    bars = load_bars(M1_CSV)
    print(f"Loaded {len(bars)} M1 bars (last: {bars[-1]['time']})")

    # Try both candidate dates for Shano's trades
    import sys
    test_date = sys.argv[1] if len(sys.argv) > 1 else "2026-05-12"
    y, m, d = map(int, test_date.split("-"))
    today_start = datetime(y, m, d, 2, 0)
    today_end   = datetime(y, m, d, 3, 0)
    print(f"Testing window: {today_start} → {today_end}")

    has_today = any(b["time"].date() == today_start.date() for b in bars)
    if not has_today:
        print(f"ERROR: bars for {test_date} not in CSV.")
        return

    trades = simulate_v342(bars, today_start, today_end)
    print(f"\nv3.42 simulated trades 02:00-03:00: {len(trades)}")
    print(f"{'time':<10} {'side':<5} {'entry':<10} {'exit':<10} {'pnl':<9} {'reason':<12}")
    for t in trades:
        print(f"{t['entry_time']:%H:%M:%S}  {t['side']:<5} {t['entry']:<10.2f} "
              f"{t['close_time']:%H:%M:%S}  ${t['close_pnl']:<+8.2f} {t['close_reason']:<12}")

    # Compare to Shano
    print()
    print(f"{'Shano':<10} {'side':<5} {'Shano $':<10} | {'EA time':<10} {'gap':<8} {'EA $':<10} {'verdict'}")
    print('-' * 95)
    matched = set()
    captured = 0
    for st, side, lot, pnl in SHANO_SETUPS:
        zt = datetime(2026, 5, 13, int(st[:2]), int(st[3:5]), int(st[6:8]))
        best = None; best_gap = timedelta(minutes=99); best_idx = None
        for i, t in enumerate(trades):
            if i in matched: continue
            if t["side"] != side: continue
            gap = abs(t["entry_time"] - zt)
            if gap < timedelta(minutes=3) and gap < best_gap:
                best, best_gap, best_idx = t, gap, i
        if best:
            matched.add(best_idx)
            captured += 1
            print(f"{st:<10} {side:<5} ${pnl:<+8.2f} | {best['entry_time']:%H:%M:%S}  "
                  f"{int(best_gap.total_seconds()):<+6}s   ${best['close_pnl']:<+8.2f}  MATCHED")
        else:
            print(f"{st:<10} {side:<5} ${pnl:<+8.2f} | (none)                              MISSED")
    print(f"\nCaptured: {captured}/{len(SHANO_SETUPS)}  ({captured/len(SHANO_SETUPS)*100:.0f}%)")
    extras = [t for i, t in enumerate(trades) if i not in matched]
    if extras:
        print(f"\nEA fires NOT matched to Shano ({len(extras)}):")
        for t in extras: print(f"  {t['entry_time']:%H:%M:%S} {t['side']:<5} ${t['close_pnl']:+.2f}")


if __name__ == "__main__":
    main()
