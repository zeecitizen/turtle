"""v3.44 PYRAMID sim — allow up to MAX_CONCURRENT positions.

Reuses v3.43 detector. Per-position state: entry, side, sl_init, peak,
locked, entry_idx. On each bar:
  1. Manage every open position independently (peak / trail / smart-cut / sl)
  2. If detector fires AND open_count < MAX_CONCURRENT AND rate-limit OK → open new
"""
import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

from v3_43_relax_sim import (
    load_bars, detect_relaxed, M1_CSV, SHANO_SETUPS,
    PEAK_BANK_USD, PEAK_DROP_USD, EARLY_STOP_USD, EARLY_PEAK_GUARD,
    EARLY_MIN_BARS, PNL_PER_POINT, MAX_LOOKBACK,
)


def manage(positions, bar, i):
    """Update each open position; return list of closed trades + remaining open."""
    closed = []
    remaining = []
    for p in positions:
        entry = p["entry"]; side = p["side"]; sl_init = p["sl_init"]
        locked = p["locked_pnl"]; peak = p["peak"]

        if side == "buy":
            fav_pnl = (bar["high"] - entry) * PNL_PER_POINT
            adv_pnl = (bar["low"] - entry) * PNL_PER_POINT
            sl_hit = bar["low"] <= sl_init
        else:
            fav_pnl = (entry - bar["low"]) * PNL_PER_POINT
            adv_pnl = (entry - bar["high"]) * PNL_PER_POINT
            sl_hit = bar["high"] >= sl_init

        new_peak = max(peak, fav_pnl)
        close_now = None; close_pnl = None; close_reason = None

        if sl_hit:
            close_pnl = (sl_init - entry) * PNL_PER_POINT if side == "buy" else (entry - sl_init) * PNL_PER_POINT
            close_reason = "sl"; close_now = sl_init

        if close_now is None and locked > 0:
            if side == "buy":
                lock_price = entry + locked / PNL_PER_POINT
                if bar["low"] <= lock_price:
                    close_pnl = locked; close_reason = "trail_lock"; close_now = lock_price
            else:
                lock_price = entry - locked / PNL_PER_POINT
                if bar["high"] >= lock_price:
                    close_pnl = locked; close_reason = "trail_lock"; close_now = lock_price

        if close_now is None and new_peak < EARLY_PEAK_GUARD:
            if adv_pnl <= -EARLY_STOP_USD:
                if i - p["entry_idx"] >= EARLY_MIN_BARS:
                    close_pnl = -EARLY_STOP_USD; close_reason = "smart_cut"; close_now = entry

        if close_now is None and new_peak >= PEAK_BANK_USD:
            target_lock = new_peak - PEAK_DROP_USD
            if target_lock > locked:
                p["locked_pnl"] = target_lock

        p["peak"] = new_peak

        if close_now is not None:
            p["close_time"] = bar["time"]
            p["close_pnl"] = close_pnl
            p["close_reason"] = close_reason
            closed.append(p)
        else:
            remaining.append(p)
    return closed, remaining


def simulate(bars, window_from, window_to, mode, max_concurrent):
    idx_start = next((i for i, b in enumerate(bars) if b["time"] >= window_from), len(bars))
    idx_end = next((i for i, b in enumerate(bars) if b["time"] >= window_to), len(bars))
    if idx_start <= MAX_LOOKBACK + 5: idx_start = MAX_LOOKBACK + 5

    trades = []
    positions = []
    last_fire_time = None

    for i in range(idx_start, idx_end):
        b = bars[i]
        closed, positions = manage(positions, b, i)
        trades.extend(closed)

        if len(positions) >= max_concurrent: continue
        if last_fire_time is not None and (b["time"] - last_fire_time).total_seconds() < 2: continue
        sigs = detect_relaxed(bars, i, **mode)
        if not sigs: continue

        sig = sigs[0]
        side = sig["side"]
        entry = b["close"]
        sl = sig["uhv"]["low"] if side == "buy" else sig["uhv"]["high"]
        positions.append({
            "entry_time": b["time"], "side": side, "entry": entry,
            "sl_init": sl, "peak": 0.0, "locked_pnl": 0.0,
            "entry_idx": i, "uhv_time": sig["uhv"]["time"],
        })
        last_fire_time = b["time"]

    # close remaining at last bar
    for p in positions:
        bar = bars[idx_end - 1]
        if p["side"] == "buy":
            pnl = (bar["close"] - p["entry"]) * PNL_PER_POINT
        else:
            pnl = (p["entry"] - bar["close"]) * PNL_PER_POINT
        p["close_time"] = bar["time"]; p["close_pnl"] = pnl; p["close_reason"] = "eod"
        trades.append(p)
    return trades


def evaluate(trades, setups, day, label):
    used = set()
    captured = 0
    for st, side, lot, pnl in setups:
        zt = datetime(*day, int(st[:2]), int(st[3:5]), int(st[6:8]))
        best = None; best_gap = timedelta(minutes=99); best_idx = None
        for i, t in enumerate(trades):
            if i in used: continue
            if t["side"] != side: continue
            gap = abs(t["entry_time"] - zt)
            if gap < timedelta(minutes=3) and gap < best_gap:
                best, best_gap, best_idx = t, gap, i
        if best:
            used.add(best_idx); captured += 1
    total = sum(t["close_pnl"] for t in trades)
    wins = sum(1 for t in trades if t["close_pnl"] > 0)
    losses = sum(1 for t in trades if t["close_pnl"] < 0)
    wr = 100 * wins / (wins + losses) if (wins + losses) else 0
    print(f"{label:<35}: fires={len(trades):<4} captured={captured:>2}/{len(setups)} ({100*captured/len(setups):.0f}%) WR={wr:.0f}% P&L=${total:+.2f}")


def main():
    bars = load_bars(M1_CSV)
    mode = {"mode_strict_vol": False, "mode_break": False, "mode_color": True}

    print("=== SHANO WINDOW (May 13 02:00-03:00) ===")
    s_start = datetime(2026, 5, 13, 2, 0)
    s_end = datetime(2026, 5, 13, 3, 0)
    for n in [1, 2, 3, 5, 8]:
        trades = simulate(bars, s_start, s_end, mode, max_concurrent=n)
        evaluate(trades, SHANO_SETUPS, (2026, 5, 13), f"max_concurrent={n}")

    print("\n=== FEB 11 BASELINE (full day, Zee's 20 entries) ===")
    ZEE = [
        ("01:59:04", "buy",  0.10, 6.65), ("02:09:38", "sell", 0.10, 11.69),
        ("02:29:02", "buy",  0.10, 20.01), ("16:49:07", "buy", 0.10, 17.12),
        ("16:52:21", "buy",  0.10, 8.85), ("16:54:10", "buy", 0.10, 8.26),
        ("16:58:03", "buy",  0.10, 5.73), ("17:02:45", "buy", 0.10, 54.93),
        ("17:36:11", "buy",  0.10, 3.29), ("17:36:13", "buy", 0.10, 14.50),
        ("17:37:26", "buy",  0.10, 7.08), ("17:49:59", "buy", 0.10, 52.78),
        ("18:24:18", "buy",  0.10, 8.51), ("18:41:50", "buy", 0.10, -1.43),
        ("19:20:34", "sell", 0.10, 14.21), ("19:26:06", "sell", 0.10, 14.55),
        ("19:29:31", "buy",  0.10, 0.84), ("19:36:19", "buy", 0.10, 10.60),
        ("19:38:39", "buy",  0.10, 11.02), ("19:38:59", "buy", 0.10, 0.92),
    ]
    f_start = datetime(2026, 2, 11, 1, 0)
    f_end = datetime(2026, 2, 11, 21, 0)
    for n in [1, 2, 3, 5, 8]:
        trades = simulate(bars, f_start, f_end, mode, max_concurrent=n)
        evaluate(trades, ZEE, (2026, 2, 11), f"max_concurrent={n}")


if __name__ == "__main__":
    main()
