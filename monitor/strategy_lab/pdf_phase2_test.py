"""pdf_phase2_test.py — test new filter ideas from PDFs to push WR above 84.2%.

Already deployed and tested: M15 trend, UHV breakout, tick-speed, spread, Setup 1 sweep,
trigger margin, burst-delta, CDD-div exit, chain-stop. All live.

NEW filters to test:
  A) Session overlap (London/NY 12-16 GMT = broker 14-18 if GMT+2)
  B) UHV close near extreme (close in top/bottom 25% of range)
  C) Effort-vs-Result: UHV body must be ≥50% of range AND wicks ≤40% of range
  D) UHV range ≥ 1.5× ATR(14) — re-test under current realistic config
  E) Pre-breakout contraction: bars before UHV must show drying volume + narrow spreads
  F) Background alignment: UHV must form near recent swing high/low (significant level)
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
    setup1_active, find_uhv_red_idx_m1, get_uhv_bar
)
from advanced_features import compute_atr

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


def find_setup1_uhv_bar(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars=3, pattern_lookback=10):
    """Find the UHV bar that catalyzed the most-recent Setup 1 match."""
    bm = probe_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None: return None, None
    start = max(pattern_lookback, idx - lookback_bars)
    for trig in range(idx, start - 1, -1):
        # check setup1_at_m1 manually inline
        if trig < 3: continue
        uhv_idx = find_uhv_red_idx_m1(bars_1m, trig, pattern_lookback, dir_sign)
        if uhv_idx is None: continue
        uhv = bars_1m[uhv_idx]
        swept = False
        for i in range(uhv_idx + 1, trig):
            if dir_sign == 1 and bars_1m[i][3] < uhv[3]: swept = True; break
            if dir_sign == -1 and bars_1m[i][2] > uhv[2]: swept = True; break
        if not swept: continue
        cur = bars_1m[trig]
        if dir_sign == 1:
            if cur[4] <= cur[1]: continue
            if cur[4] <= uhv[2]: continue
        else:
            if cur[4] >= cur[1]: continue
            if cur[4] >= uhv[3]: continue
        return uhv, bars_1m[uhv_idx-1] if uhv_idx > 0 else None  # return UHV + bar before it
    return None, None


# ─── NEW FILTER FUNCTIONS ──────────────────────────

def session_overlap_ok(when, mode='lon_ny'):
    """London-NY overlap. Broker time GMT+2 typical for Blueberry → 14-18 broker = 12-16 GMT."""
    h = when.hour
    if mode == 'lon_ny':
        return 14 <= h <= 18  # broker hours roughly mapping to 12-16 GMT
    elif mode == 'london':
        return 9 <= h <= 12  # London open
    elif mode == 'wide':
        return 9 <= h <= 19  # London open through NY close
    return True


def uhv_close_near_extreme(uhv, dir_sign, threshold=0.25):
    """For BUY (RED UHV): close should be in BOTTOM 25% of range (showing absorption — close didn't bounce up).
    Wait actually - we want UHV that closed near its extreme showing strong directional move.
    For RED UHV (catalyst for BUY): we want close at LOW of range (drove price down hard)
    For GREEN UHV (catalyst for SELL): close at HIGH of range (drove price up hard)
    """
    o, h, l, c = uhv[1], uhv[2], uhv[3], uhv[4]
    rng = h - l
    if rng <= 0: return False
    if dir_sign == 1:  # BUY needs RED UHV with close near LOW
        # close position from low: 0 = at low, 1 = at high
        pos = (c - l) / rng
        return pos <= threshold  # close in bottom 25%
    else:  # SELL needs GREEN UHV with close near HIGH
        pos = (c - l) / rng
        return pos >= (1 - threshold)  # close in top 25%


def uhv_effort_result(uhv, body_min=0.50, wick_max=0.40):
    """Effort-vs-Result: body ≥ 50% of range AND no wick > 40% of range."""
    o, h, l, c = uhv[1], uhv[2], uhv[3], uhv[4]
    rng = h - l
    if rng <= 0: return False
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    if body / rng < body_min: return False
    if upper_wick / rng > wick_max: return False
    if lower_wick / rng > wick_max: return False
    return True


def uhv_wide_range(uhv, atr_val, mult=1.5):
    """UHV range ≥ mult × ATR(14)."""
    if atr_val is None or atr_val <= 0: return False
    rng = uhv[2] - uhv[3]
    return rng >= mult * atr_val


def pre_breakout_contraction(uhv_idx, bars_1m, lookback=3):
    """Bars before UHV must show: lower volume than UHV AND tighter range than UHV."""
    if uhv_idx < lookback: return False
    uhv = bars_1m[uhv_idx]
    uhv_vol = uhv[5]
    uhv_rng = uhv[2] - uhv[3]
    for i in range(uhv_idx - lookback, uhv_idx):
        b = bars_1m[i]
        b_vol = b[5]
        b_rng = b[2] - b[3]
        # bars BEFORE UHV should be lower-volume AND tighter than UHV (compression)
        if b_vol >= uhv_vol * 0.7: return False  # not low-volume enough
        if b_rng >= uhv_rng * 0.7: return False  # not tight enough
    return True


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


def run(label, *,
        require_session=False, session_mode='lon_ny',
        require_close_extreme=False, close_threshold=0.25,
        require_effort_result=False, body_min=0.50, wick_max=0.40,
        require_wide_uhv=False, atr_mult=1.5,
        require_contraction=False, contract_lookback=3,
        lot_start=0.30, trail_t=25, trail_d=8):
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    atr_1m = compute_atr(bars_1m, 14)
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
        # Existing live filters (skipBadHours and skipFastConfirm OFF in current LIVE)
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

        # NEW FILTERS
        if require_session:
            if not session_overlap_ok(confirm_dt, session_mode): continue

        # Get the Setup 1 UHV bar for new filters that target it
        s1_uhv, _ = find_setup1_uhv_bar(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10)
        if s1_uhv is None: s1_uhv = uhv  # fallback

        if require_close_extreme:
            if not uhv_close_near_extreme(s1_uhv, dir_sign, close_threshold): continue
        if require_effort_result:
            if not uhv_effort_result(s1_uhv, body_min, wick_max): continue
        if require_wide_uhv:
            uhv_dt = s1_uhv[0]
            uhv_idx = bar_idx_1m.get(uhv_dt)
            atr_val = atr_1m[uhv_idx] if uhv_idx is not None and uhv_idx < len(atr_1m) else None
            if not uhv_wide_range(s1_uhv, atr_val, atr_mult): continue
        if require_contraction:
            uhv_dt = s1_uhv[0]
            uhv_idx = bar_idx_1m.get(uhv_dt)
            if uhv_idx is None or not pre_breakout_contraction(uhv_idx, bars_1m, contract_lookback): continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, lot_start, -0.07, lot_start)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, 100, lots, trail_t, trail_d)
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
    print(f"  {label:<55}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chainWR={chain_wr:>5.1f}%")


print("=" * 100)
print("PHASE 2 — test new filter ideas to push WR above 84.2%")
print("=" * 100)
print()
print("--- BASELINE (current LIVE) ---")
run("LIVE: full stack")

print()
print("=== A) SESSION OVERLAP ===")
run("+ session lon-ny (broker 14-18)", require_session=True, session_mode='lon_ny')
run("+ session london (broker 9-12)", require_session=True, session_mode='london')
run("+ session wide (broker 9-19)", require_session=True, session_mode='wide')

print()
print("=== B) UHV CLOSE NEAR EXTREME ===")
for thresh in [0.25, 0.33, 0.40, 0.50]:
    run(f"+ UHV close in {int(thresh*100)}% of range edge", require_close_extreme=True, close_threshold=thresh)

print()
print("=== C) EFFORT-VS-RESULT (body/wick) ===")
for body, wick in [(0.40, 0.50), (0.50, 0.40), (0.60, 0.30), (0.50, 0.50)]:
    run(f"+ body>={body:.0%} wicks<={wick:.0%}", require_effort_result=True, body_min=body, wick_max=wick)

print()
print("=== D) WIDE UHV (range >= X*ATR) ===")
for mult in [1.0, 1.2, 1.5, 1.8, 2.0]:
    run(f"+ UHV range >= {mult}x ATR(14)", require_wide_uhv=True, atr_mult=mult)

print()
print("=== E) PRE-BREAKOUT CONTRACTION ===")
for lb in [2, 3, 4]:
    run(f"+ {lb}-bar contraction before UHV", require_contraction=True, contract_lookback=lb)
