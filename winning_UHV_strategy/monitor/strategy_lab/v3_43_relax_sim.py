"""v3.43 RELAXED detector — drops bo.vol < uhv.vol check and changes lookback
loop to non-fatal exclusion (just skip overlap candidates, don't break the walk).

Measures Shano-match rate vs v3.42 strict detector.
"""
import csv
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

COMMON = Path(os.environ.get("APPDATA", r"C:\Users\zeesh\AppData\Roaming")) / "MetaQuotes" / "Terminal" / "Common" / "Files"
M1_CSV = COMMON / "rev_eng_m1.csv"

MAX_LOOKBACK = 60
MAX_BARS_BACK = 60
PEAK_BANK_USD = 1.0
PEAK_DROP_USD = 0.5
EARLY_STOP_USD = 2.0
EARLY_PEAK_GUARD = 1.0
EARLY_MIN_BARS = 1
LOTS = 0.10
PNL_PER_POINT = LOTS * 100

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
                "low": float(r["low"]), "close": float(r["close"]),
                "vol": int(r["tick_volume"]),
            })
    bars.sort(key=lambda b: b["time"])
    return bars


def detect_relaxed(bars, idx_bo, mode_strict_vol=False, mode_break=False, mode_color=True):
    """v3.43 relaxed detector.

    Flags:
      mode_strict_vol=True  → keep bo.vol < uhv.vol check (v3.42 strict)
      mode_break=True       → break loop on overlap (v3.42 strict)
      mode_color=True       → require green for buy, red for sell

    Default (all False except color) = full relax.
    """
    bo = bars[idx_bo]
    results = []  # may have buy AND sell candidates

    # BUY candidate
    if not mode_color or bo["close"] > bo["open"]:
        reds = []
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["high"] >= bo["close"]:
                if mode_break:
                    break
                else:
                    continue   # exclude this candidate, keep walking
            if c["close"] < c["open"]:
                reds.append((k, c))
        if reds:
            k_uhv, uhv = max(reds, key=lambda kc: kc[1]["vol"])
            bars_back = idx_bo - k_uhv
            ok = True
            if bars_back > MAX_BARS_BACK: ok = False
            if bo["close"] <= uhv["high"]: ok = False
            if mode_strict_vol and bo["vol"] >= uhv["vol"]: ok = False
            if ok:
                results.append({"side": "buy", "uhv": uhv, "bars_back": bars_back, "bo": bo, "bo_idx": idx_bo})

    # SELL candidate
    if not mode_color or bo["close"] < bo["open"]:
        greens = []
        for j in range(1, MAX_LOOKBACK + 1):
            k = idx_bo - j
            if k < 0: break
            c = bars[k]
            if c["low"] <= bo["close"]:
                if mode_break:
                    break
                else:
                    continue
            if c["close"] > c["open"]:
                greens.append((k, c))
        if greens:
            k_uhv, uhv = max(greens, key=lambda kc: kc[1]["vol"])
            bars_back = idx_bo - k_uhv
            ok = True
            if bars_back > MAX_BARS_BACK: ok = False
            if bo["close"] >= uhv["low"]: ok = False
            if mode_strict_vol and bo["vol"] >= uhv["vol"]: ok = False
            if ok:
                results.append({"side": "sell", "uhv": uhv, "bars_back": bars_back, "bo": bo, "bo_idx": idx_bo})

    return results


def simulate(bars, window_from, window_to, mode):
    idx_start = next((i for i, b in enumerate(bars) if b["time"] >= window_from), len(bars))
    idx_end   = next((i for i, b in enumerate(bars) if b["time"] >= window_to),   len(bars))
    if idx_start <= MAX_LOOKBACK + 5: idx_start = MAX_LOOKBACK + 5

    trades = []
    open_trade = None
    last_fire_time = None

    for i in range(idx_start, idx_end):
        b = bars[i]
        # MANAGE OPEN
        if open_trade is not None:
            entry = open_trade["entry"]
            side = open_trade["side"]
            sl_init = open_trade["sl_init"]
            locked = open_trade["locked_pnl"]
            peak = open_trade["peak"]

            if side == "buy":
                fav_pnl = (b["high"] - entry) * PNL_PER_POINT
                adv_pnl = (b["low"] - entry) * PNL_PER_POINT
                sl_hit = b["low"] <= sl_init
            else:
                fav_pnl = (entry - b["low"]) * PNL_PER_POINT
                adv_pnl = (entry - b["high"]) * PNL_PER_POINT
                sl_hit = b["high"] >= sl_init

            new_peak = max(peak, fav_pnl)

            close_now = None; close_pnl = None; close_reason = None
            if sl_hit:
                close_now = sl_init
                close_pnl = (sl_init - entry) * PNL_PER_POINT if side == "buy" else (entry - sl_init) * PNL_PER_POINT
                close_reason = "sl"
            if close_now is None and locked > 0:
                if side == "buy":
                    lock_price = entry + locked / PNL_PER_POINT
                    if b["low"] <= lock_price:
                        close_pnl = locked; close_reason = "trail_lock"; close_now = lock_price
                else:
                    lock_price = entry - locked / PNL_PER_POINT
                    if b["high"] >= lock_price:
                        close_pnl = locked; close_reason = "trail_lock"; close_now = lock_price
            if close_now is None and new_peak < EARLY_PEAK_GUARD:
                if adv_pnl <= -EARLY_STOP_USD:
                    if i - open_trade["entry_idx"] >= EARLY_MIN_BARS:
                        close_pnl = -EARLY_STOP_USD; close_reason = "smart_cut"; close_now = entry
            if close_now is None and new_peak >= PEAK_BANK_USD:
                target_lock = new_peak - PEAK_DROP_USD
                if target_lock > locked:
                    open_trade["locked_pnl"] = target_lock
            open_trade["peak"] = new_peak

            if close_now is not None:
                open_trade["close_time"] = b["time"]
                open_trade["close_pnl"] = close_pnl
                open_trade["close_reason"] = close_reason
                trades.append(open_trade)
                open_trade = None

        # DETECT + FIRE
        if open_trade is None:
            if last_fire_time is not None and (b["time"] - last_fire_time).total_seconds() < 2:
                continue
            sigs = detect_relaxed(bars, i, **mode)
            if not sigs: continue
            # Pick first candidate (could refine later)
            sig = sigs[0]
            side = sig["side"]
            entry = b["close"]
            sl = sig["uhv"]["low"] if side == "buy" else sig["uhv"]["high"]
            open_trade = {
                "entry_time": b["time"], "side": side, "entry": entry,
                "sl_init": sl, "peak": 0.0, "locked_pnl": 0.0,
                "entry_idx": i, "uhv_time": sig["uhv"]["time"],
            }
            last_fire_time = b["time"]

    return trades


def evaluate_mode(trades, name):
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
            matched.add(best_idx); captured += 1
    extras = len(trades) - captured
    total_pnl = sum(t["close_pnl"] for t in trades)
    print(f"{name:<35}: fires={len(trades):<4}  captured={captured:>2}/{len(SHANO_SETUPS)}  ({100*captured/len(SHANO_SETUPS):.0f}%)  extras={extras}  sim_P&L=${total_pnl:+.2f}")


def main():
    bars = load_bars(M1_CSV)
    start = datetime(2026, 5, 13, 2, 0)
    end = datetime(2026, 5, 13, 3, 0)

    modes = [
        ("v3.42 (strict vol + break + color)",   {"mode_strict_vol": True,  "mode_break": True,  "mode_color": True}),
        ("drop vol check",                       {"mode_strict_vol": False, "mode_break": True,  "mode_color": True}),
        ("relax lookback (no break on overlap)", {"mode_strict_vol": True,  "mode_break": False, "mode_color": True}),
        ("drop vol + relax lookback",            {"mode_strict_vol": False, "mode_break": False, "mode_color": True}),
        ("drop vol + relax + allow both sides",  {"mode_strict_vol": False, "mode_break": False, "mode_color": False}),
    ]
    print(f"Shano: {len(SHANO_SETUPS)} setups in 02:00-03:00\n")
    for name, mode in modes:
        trades = simulate(bars, start, end, mode)
        evaluate_mode(trades, name)


if __name__ == "__main__":
    main()
