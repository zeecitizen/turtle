"""c2_quality_on_live_test.py — layer candle-2 quality filters on top of CURRENT LIVE config.

Uses production backtester (unified_backtester + filter_loo_correct), runs the FULL LIVE
filter stack (the one that produces ~84% WR in pdf4_loo_realistic baseline), then adds
a candle-2 quality filter as the FINAL gate before main fires.

c1 = M1 bar just before the bar containing entry_time (Shano bigness trigger)
c2 = M1 bar containing entry_time           (Shano same-direction confirm)

Tests:
  baseline                  — current LIVE stack (no c2 filter)
  +c2_body>=c1_body         — confirm bar body must match trigger body
  +c2_body>=0.7*c1_body     — looser version
  +c2_strength70+momentum2  — strongest combo from candle2_quality_test
  +c2_strength70_only       — strength alone
  +c2_momentum2_only        — momentum alone
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


def sim_main(intended_dt, dir_sign, intended_price, ticks, fear_ideal, lots, trail_t, trail_d):
    if not ticks: return 0.0, None
    actual_dt, actual_price = slipped_fill(intended_dt, ticks, dir_sign, intended_price)
    if actual_dt is None: return 0.0, None
    forward = [t for t in ticks if t[0] >= actual_dt]
    if not forward: return 0.0, None
    peak = 0.0; intended_exit_dt = None; intended_exit_price = None
    for dt, bid, ask in forward:
        cur = bid if dir_sign == 1 else ask
        profit = ((cur - actual_price) if dir_sign == 1 else (actual_price - cur)) * lots * CONTRACT_SIZE
        if profit > peak: peak = profit
        if profit <= -fear_ideal: intended_exit_dt = dt; intended_exit_price = cur; break
        if peak >= trail_t and (peak - profit) >= trail_d: intended_exit_dt = dt; intended_exit_price = cur; break
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


# ── candle-2 quality predicates ──
def body(bar): return abs(bar[4] - bar[1])
def rng(bar):  return bar[2] - bar[3]


def get_c1_c2(entry_time, bars_1m, bar_idx_1m):
    """Returns (c1, c2) M1 bars or (None, None)."""
    bm = entry_time.replace(second=0, microsecond=0)
    c2_idx = bar_idx_1m.get(bm)
    if c2_idx is None:
        # Bar containing entry not in index — try walking back
        for d in range(1, 5):
            t = bm - timedelta(minutes=d)
            c2_idx = bar_idx_1m.get(t)
            if c2_idx is not None: break
    if c2_idx is None or c2_idx < 1: return None, None
    return bars_1m[c2_idx - 1], bars_1m[c2_idx]


C2_FILTERS = {
    "none":                       lambda c1, c2: True,
    "c2_body>=c1_body":           lambda c1, c2: body(c1) > 0 and body(c2) >= body(c1),
    "c2_body>=0.7*c1_body":       lambda c1, c2: body(c1) > 0 and body(c2) >= 0.7 * body(c1),
    "c2_body>=0.5*c1_body":       lambda c1, c2: body(c1) > 0 and body(c2) >= 0.5 * body(c1),
    "c2_strength>=70%":           lambda c1, c2: rng(c2) > 0 and body(c2) / rng(c2) >= 0.70,
    "c2_momentum>=2pt":           lambda c1, c2: body(c2) >= 2.0,
    "c2_strength70+momentum2":    lambda c1, c2: (rng(c2) > 0 and body(c2) / rng(c2) >= 0.70) and body(c2) >= 2.0,
    "c2_strength50+momentum1":    lambda c1, c2: (rng(c2) > 0 and body(c2) / rng(c2) >= 0.50) and body(c2) >= 1.0,
}


def run(label, c2_filter_name, *, skip_bad_hours=False, skip_fast_confirm=False,
        trend_filter=True, uhv_filter=True, trigger_past_pts=0.3, tick_speed_max=15,
        spread_mult=1.2, m15_trend=True, setup1_filter=True, burst_delta_filter=True,
        burst_delta_lb=5, trail_t=25, trail_d=8, fear_ideal=100, lot_start=0.30):
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)
    c2_pred = C2_FILTERS[c2_filter_name]

    chains = []
    blocked_by = {}
    def block(name): blocked_by[name] = blocked_by.get(name, 0) + 1

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

        if skip_bad_hours:
            h = confirm_dt.hour
            if (4 <= h <= 6) or (21 <= h <= 23): block('bad_hours'); continue
        if skip_fast_confirm:
            if 3 <= confirm_speed <= 8: block('fast_confirm'); continue
        if trend_filter:
            t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
            if t is None or t == 0 or t != dir_sign: block('trend_2m'); continue

        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: block('no_uhv_data'); continue
        trigger = bars_1m[trigger_idx]
        if uhv_filter:
            margin = trigger_past_pts
            if dir_sign == 1 and trigger[4] < uhv[2] + margin: block('uhv_filter'); continue
            if dir_sign == -1 and trigger[4] > uhv[3] - margin: block('uhv_filter'); continue
        if tick_speed_max > 0:
            ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
            if ts is None or ts > tick_speed_max: block('tick_speed'); continue
        if spread_mult > 0:
            if not actual_spread_check(confirm_dt, spread_mult): block('spread'); continue
        if m15_trend:
            ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
            if ema_v is not None:
                price = (confirm_bid + confirm_ask) / 2
                if dir_sign == 1 and price <= ema_v: block('m15_trend'); continue
                if dir_sign == -1 and price >= ema_v: block('m15_trend'); continue
        if setup1_filter:
            if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10):
                block('setup1'); continue

        # ── NEW: candle-2 quality filter ──
        c1, c2 = get_c1_c2(entry_time, bars_1m, bar_idx_1m)
        if c1 is None or c2 is None: block('no_c1c2_data'); continue
        try:
            c2_pass = c2_pred(c1, c2)
        except Exception:
            c2_pass = False
        if not c2_pass: block('c2_quality'); continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, lot_start, -0.07, lot_start)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, fear_ideal, lots, trail_t, trail_d)
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
            if burst_delta_filter and not burst_delta_pos(exit_dt, dir_sign, burst_delta_lb): break
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
    avg_per_chain = total / max(n, 1)
    print(f"  {label:<48s}  chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chainWR={chain_wr:>5.1f}%  $/chain={avg_per_chain:+6.2f}")
    return n, total, losing, main_wr, chain_wr, blocked_by


print("=" * 110)
print("Candle-2 quality filters layered on CURRENT LIVE config (Direct Raw, 0.30 lots, trail 25/8, bd 5s)")
print("=" * 110)
print()
print("--- BASELINE (LIVE stack, no c2 filter) ---")
n_base, t_base, l_base, wr_base, cw_base, blocks = run("LIVE baseline (no c2 filter)", "none")
print()
print("Per-filter blocks in baseline:")
for k, v in sorted(blocks.items(), key=lambda x: -x[1]):
    print(f"  {k:<20} blocked {v:>3}")
print()
print("=" * 110)
print("LAYER c2-quality filters ON TOP")
print("=" * 110)

for fname in ["c2_body>=c1_body", "c2_body>=0.7*c1_body", "c2_body>=0.5*c1_body",
              "c2_strength>=70%", "c2_momentum>=2pt",
              "c2_strength70+momentum2", "c2_strength50+momentum1"]:
    n, t, l, wr, cw, _ = run(f"+ {fname}", fname)
    dn, dt_, dl, dwr, dcw = n - n_base, t - t_base, l - l_base, wr - wr_base, cw - cw_base
    print(f"      delta: chains={dn:+d}  total=${dt_:+.2f}  losing={dl:+d}  mainWR={dwr:+.1f}%  chainWR={dcw:+.1f}%")
    print()
