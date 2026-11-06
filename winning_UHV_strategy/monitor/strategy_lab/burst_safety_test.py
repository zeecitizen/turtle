"""burst_safety_test.py — kill-burst, tighter burst SL, and probe-alive guard tests.

Three families of tests vs LIVE baseline:
  A) maxBurst sweep (1=no bursts, 2, 3, 7=current)
  B) burst SL sweep ($15, $20, $30, $50 vs current -$100 fearIdeal)
  C) probe-alive guard: keep bursts only while the original 0.01 probe is still
     net profitable (or above some grace threshold)

Goal: find a burst-management policy that improves chain WR + total P&L by
preventing the catastrophic -$107 burst loss while preserving the +$110 burst
gains from chains [6] and [9].
"""
from __future__ import annotations
import sys, csv, random
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas, SHADOW_CSV, CONTRACT_SIZE
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, get_uhv_bar
)

random.seed(42)
PROBE_LOTS = 0.01; PROBE_CONFIRM = 0.45; HORIZON_SEC = 600; PIP_SIZE = 0.10
SLIP_PIPS = 0.5; LAT_MEAN = 300; LAT_STDEV = 100; LAT_MIN = 150; LAT_MAX = 600
COMMISSION_PER_LOT = 3.5


def slipped_fill(when, ticks, dir_sign, intended_price):
    while True:
        ms = random.gauss(LAT_MEAN, LAT_STDEV)
        if LAT_MIN <= ms <= LAT_MAX: break
    target = when + timedelta(milliseconds=ms)
    actual = None
    for dt, bid, ask in ticks:
        if dt >= target: actual = (dt, bid, ask); break
    if actual is None and ticks: actual = ticks[-1]
    if actual is None: return None, None
    dt, bid, ask = actual
    slip = SLIP_PIPS * PIP_SIZE
    return (dt, ask + slip) if dir_sign == 1 else (dt, bid - slip)


def burst_delta_pos(when, dir_sign, lookback_sec):
    end = when; start = end - timedelta(seconds=lookback_sec)
    ticks = ticks_in_range(start, end)
    if len(ticks) < 5: return True
    up = down = 0; prev_mid = None
    for _, bid, ask in ticks:
        mid = (bid + ask) / 2
        if prev_mid is not None:
            if mid > prev_mid: up += 1
            elif mid < prev_mid: down += 1
        prev_mid = mid
    if up + down < 3: return True
    delta = up - down
    return (dir_sign == 1 and delta > 0) or (dir_sign == -1 and delta < 0)


def sim_main(intended_dt, dir_sign, intended_price, ticks, fear_ideal, lots, trail_t, trail_d,
             probe_monitor=None):
    """Returns (final_pnl, exit_dt).
    probe_monitor: optional dict {entry_price, sample_every_sec, velocity_window_sec, velocity_threshold}.
    If probe_monitor set, samples probe velocity every sample_every_sec while burst is open.
    If velocity < threshold for the most recent window, exit burst immediately at current price.
    """
    if not ticks: return 0.0, None
    actual_dt, actual_price = slipped_fill(intended_dt, ticks, dir_sign, intended_price)
    if actual_dt is None: return 0.0, None
    forward = [t for t in ticks if t[0] >= actual_dt]
    if not forward: return 0.0, None
    peak = 0.0; intended_exit_dt = None; intended_exit_price = None
    last_probe_check = actual_dt
    for dt, bid, ask in forward:
        cur = bid if dir_sign == 1 else ask
        profit = ((cur - actual_price) if dir_sign == 1 else (actual_price - cur)) * lots * CONTRACT_SIZE
        if profit > peak: peak = profit
        if profit <= -fear_ideal: intended_exit_dt = dt; intended_exit_price = cur; break
        if peak >= trail_t and (peak - profit) >= trail_d: intended_exit_dt = dt; intended_exit_price = cur; break
        # Mid-trade probe-velocity monitor
        if probe_monitor and (dt - last_probe_check).total_seconds() >= probe_monitor["sample_every_sec"]:
            last_probe_check = dt
            _, vel = probe_velocity(probe_monitor["entry_price"], dir_sign, dt,
                                     probe_monitor["velocity_window_sec"])
            if vel is not None and vel < probe_monitor["velocity_threshold"]:
                intended_exit_dt = dt; intended_exit_price = cur; break
    if intended_exit_dt is None:
        intended_exit_dt = forward[-1][0]
        intended_exit_price = forward[-1][1] if dir_sign == 1 else forward[-1][2]
    actual_exit_dt, actual_exit_price = slipped_fill(intended_exit_dt, forward, -dir_sign, intended_exit_price)
    if actual_exit_dt is None: actual_exit_price = intended_exit_price
    final = ((actual_exit_price - actual_price) if dir_sign == 1 else (actual_price - actual_exit_price)) * lots * CONTRACT_SIZE
    final -= 2 * COMMISSION_PER_LOT * lots
    return round(final, 2), actual_exit_dt


def lot_for_burst(b, start, step, max_lot, min_lot=0.01):
    lot = start + b * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def probe_pnl_at(probe_dt, probe_entry_price, dir_sign, check_dt):
    """Compute probe P&L at check_dt using current bid/ask."""
    ticks = ticks_in_range(check_dt - timedelta(seconds=2), check_dt + timedelta(seconds=2))
    if not ticks: return None
    best = min(ticks, key=lambda t: abs((t[0] - check_dt).total_seconds()))
    cur = best[1] if dir_sign == 1 else best[2]
    return (cur - probe_entry_price) * dir_sign * PROBE_LOTS * CONTRACT_SIZE


def probe_velocity(probe_entry_price, dir_sign, check_dt, window_sec=5):
    """Returns (current_pnl, velocity_per_sec) over last window_sec.
    Positive velocity = probe accelerating in our favor.
    Negative velocity = probe decelerating / reversing.
    """
    pnl_now  = probe_pnl_at(None, probe_entry_price, dir_sign, check_dt)
    pnl_prev = probe_pnl_at(None, probe_entry_price, dir_sign, check_dt - timedelta(seconds=window_sec))
    if pnl_now is None or pnl_prev is None:
        return None, None
    vel = (pnl_now - pnl_prev) / window_sec
    return pnl_now, vel


def run(label, *, max_burst=7, burst_sl_usd=100, probe_alive_guard=False, probe_alive_threshold=0.0,
        probe_velocity_guard=False, probe_velocity_window=5, probe_velocity_threshold=0.0,
        midtrade_monitor=False, midtrade_sample_sec=2, midtrade_window_sec=5, midtrade_threshold=0.0):
    """probe_alive_guard: if True, before each burst check probe is still profitable >= threshold."""
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

    chains = []
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        actual_entry_dt, actual_entry = slipped_fill(entry_time, ticks, dir_sign, entry_price)
        if actual_entry_dt is None: continue
        entry_time = actual_entry_dt; entry_price = actual_entry
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in [t for t in ticks if t[0] >= entry_time]:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue
        # LIVE filter chain (same as pdf4_loo_realistic)
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] < uhv[2] + 0.3: continue
        if dir_sign == -1 and trigger[4] > uhv[3] - 0.3: continue
        ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
        if ts is None or ts > 15: continue
        if not actual_spread_check(confirm_dt, 1.2): continue
        ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10): continue

        # Probe entry price (kept alive for guard)
        probe_entry_price = entry_price

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < max_burst:
            lots = lot_for_burst(burst_idx, 0.30, -0.07, 0.30)
            # SL: for FIRST main use fearIdeal=100; for bursts use burst_sl_usd
            sl_for_this = 100 if burst_idx == 0 else burst_sl_usd
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            # Apply mid-trade probe monitor only on bursts (not first main)
            pm = None
            if midtrade_monitor and burst_idx > 0:
                pm = {"entry_price": probe_entry_price, "sample_every_sec": midtrade_sample_sec,
                      "velocity_window_sec": midtrade_window_sec, "velocity_threshold": midtrade_threshold}
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, sl_for_this, lots, 25, 8, probe_monitor=pm)
            results.append((lots, pnl))
            if pnl <= 0: break
            if exit_dt is None: break
            t2 = trend_at(exit_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t2 is None or t2 == 0 or t2 != dir_sign: break
            uhv2, _, _ = get_uhv_bar(exit_dt, bars_1m, bar_idx_1m, 20)
            if uhv2 is None: break
            recent = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if recent:
                _, b, a = recent[-1]
                cp = b if dir_sign == -1 else a
                if dir_sign == 1 and cp <= uhv2[2]: break
                if dir_sign == -1 and cp >= uhv2[3]: break
            if not burst_delta_pos(exit_dt, dir_sign, 5): break

            # Probe-alive guard: check probe still profitable BEFORE firing burst
            if probe_alive_guard:
                p_pnl = probe_pnl_at(entry_time, probe_entry_price, dir_sign, exit_dt)
                if p_pnl is None or p_pnl < probe_alive_threshold:
                    break

            # Probe-velocity guard: check probe is still ACCELERATING in our favor
            if probe_velocity_guard:
                _, vel = probe_velocity(probe_entry_price, dir_sign, exit_dt, probe_velocity_window)
                if vel is None or vel < probe_velocity_threshold:
                    break

            cur_dt = exit_dt
            nt = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
            if nt:
                _, b, a = nt[0]
                cur_intended = a if dir_sign == 1 else b
            else: break
            burst_idx += 1
        chains.append(results)

    n = len(chains); all_mains = [m for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    main_wr = wins / max(len(all_mains), 1) * 100
    chain_wr = (n - losing) / max(n, 1) * 100
    max_dd = min(chain_pnls) if chain_pnls else 0
    avg_chain = total / max(n, 1)
    return {"label": label, "chains": n, "mains": len(all_mains), "main_wr": round(main_wr, 1),
            "chain_wr": round(chain_wr, 1), "total": round(total, 2), "losing": losing,
            "max_dd": round(max_dd, 2), "avg_chain": round(avg_chain, 2)}


def fmt(s):
    return (f"  {s['label']:<48s}  chains={s['chains']:<3d}  mains={s['mains']:<3d}  "
            f"mainWR={s['main_wr']:>5.1f}%  chainWR={s['chain_wr']:>5.1f}%  "
            f"total=${s['total']:+8.2f}  losing={s['losing']:<2d}  max_DD=${s['max_dd']:+7.2f}  $/chain={s['avg_chain']:+6.2f}")


print("=" * 130)
print("BURST SAFETY TESTS — vs LIVE baseline (84.2% mainWR, 88.9% chainWR, +$303.79, 1 losing)")
print("=" * 130)
print()

print("--- BASELINE ---")
baseline = run("LIVE current (max_burst=7, burst_SL=$100)", max_burst=7, burst_sl_usd=100)
print(fmt(baseline))
print()

print("--- A) MAX_BURST SWEEP (kill bursts entirely vs allow some) ---")
for mb in [1, 2, 3, 4, 7]:
    s = run(f"max_burst={mb}, burst_SL=$100", max_burst=mb, burst_sl_usd=100)
    print(fmt(s))
print()

print("--- B) BURST SL SWEEP (cap burst losses) ---")
for sl in [10, 15, 20, 30, 50, 100]:
    s = run(f"max_burst=7, burst_SL=${sl}", max_burst=7, burst_sl_usd=sl)
    print(fmt(s))
print()

print("--- C) PROBE-ALIVE GUARD (only burst if probe still profitable) ---")
for thr in [0.45, 0.20, 0.0, -0.20, -0.50]:
    label = f"probe_alive>=${thr:+.2f}, burst_SL=$100"
    s = run(label, max_burst=7, burst_sl_usd=100, probe_alive_guard=True, probe_alive_threshold=thr)
    print(fmt(s))
print()

print("--- D) PROBE-VELOCITY GUARD (rocket-ship deceleration test) ---")
print("    velocity = $/sec rate-of-change in probe P&L over last N seconds")
for window, thr in [(3, 0.0), (3, -0.01), (3, -0.02), (5, 0.0), (5, -0.01), (5, -0.02), (10, 0.0), (10, -0.02)]:
    label = f"vel(window={window}s) >= ${thr:+.3f}/s"
    s = run(label, probe_velocity_guard=True, probe_velocity_window=window, probe_velocity_threshold=thr)
    print(fmt(s))
print()

print("--- E) COMBOS: velocity guard + tighter burst SL + max_burst cap ---")
combos = [
    {"max_burst": 7, "burst_sl_usd": 100, "probe_velocity_guard": True, "probe_velocity_window": 3, "probe_velocity_threshold": 0.0,
     "label": "vel(3s)>=0 + burst_SL=$100"},
    {"max_burst": 3, "burst_sl_usd": 100, "probe_velocity_guard": True, "probe_velocity_window": 3, "probe_velocity_threshold": 0.0,
     "label": "vel(3s)>=0 + max_burst=3 + burst_SL=$100"},
    {"max_burst": 3, "burst_sl_usd": 20, "probe_velocity_guard": True, "probe_velocity_window": 3, "probe_velocity_threshold": 0.0,
     "label": "vel(3s)>=0 + max_burst=3 + burst_SL=$20"},
    {"max_burst": 7, "burst_sl_usd": 20, "probe_velocity_guard": True, "probe_velocity_window": 5, "probe_velocity_threshold": 0.0,
     "label": "vel(5s)>=0 + burst_SL=$20"},
    {"max_burst": 3, "burst_sl_usd": 15, "label": "max_burst=3 + burst_SL=$15"},
    {"max_burst": 3, "burst_sl_usd": 20, "label": "max_burst=3 + burst_SL=$20"},
]
for cfg in combos:
    label = cfg.pop("label")
    s = run(label, **cfg)
    print(fmt(s))
print()

print("--- F) MID-TRADE PROBE-VELOCITY MONITOR (rocket-ship deceleration during open burst) ---")
print("    while burst is open, sample probe velocity every N sec; exit if it goes below threshold")
midtrade_tests = [
    {"midtrade_monitor": True, "midtrade_sample_sec": 2, "midtrade_window_sec": 5, "midtrade_threshold": 0.0,
     "label": "midtrade vel(5s sliding) >= $0 every 2s"},
    {"midtrade_monitor": True, "midtrade_sample_sec": 2, "midtrade_window_sec": 5, "midtrade_threshold": -0.005,
     "label": "midtrade vel(5s) >= $-0.005 every 2s"},
    {"midtrade_monitor": True, "midtrade_sample_sec": 1, "midtrade_window_sec": 3, "midtrade_threshold": 0.0,
     "label": "midtrade vel(3s) >= $0 every 1s"},
    {"midtrade_monitor": True, "midtrade_sample_sec": 1, "midtrade_window_sec": 3, "midtrade_threshold": -0.01,
     "label": "midtrade vel(3s) >= $-0.01 every 1s"},
    {"midtrade_monitor": True, "midtrade_sample_sec": 3, "midtrade_window_sec": 10, "midtrade_threshold": 0.0,
     "label": "midtrade vel(10s) >= $0 every 3s"},
]
for cfg in midtrade_tests:
    label = cfg.pop("label")
    s = run(label, **cfg)
    print(fmt(s))
print()

print("--- G) ULTIMATE COMBOS: midtrade monitor + max_burst cap ---")
ultimate = [
    {"max_burst": 3, "midtrade_monitor": True, "midtrade_sample_sec": 2, "midtrade_window_sec": 5, "midtrade_threshold": 0.0,
     "label": "max_burst=3 + midtrade vel(5s)>=$0 every 2s"},
    {"max_burst": 3, "midtrade_monitor": True, "midtrade_sample_sec": 1, "midtrade_window_sec": 3, "midtrade_threshold": 0.0,
     "label": "max_burst=3 + midtrade vel(3s)>=$0 every 1s"},
    {"max_burst": 7, "midtrade_monitor": True, "midtrade_sample_sec": 1, "midtrade_window_sec": 3, "midtrade_threshold": 0.0,
     "label": "max_burst=7 + midtrade vel(3s)>=$0 every 1s"},
    {"max_burst": 3, "burst_sl_usd": 20, "midtrade_monitor": True, "midtrade_sample_sec": 1, "midtrade_window_sec": 3, "midtrade_threshold": 0.0,
     "label": "max_burst=3 + burst_SL=$20 + midtrade vel(3s)>=$0 every 1s"},
]
for cfg in ultimate:
    label = cfg.pop("label")
    s = run(label, **cfg)
    print(fmt(s))
