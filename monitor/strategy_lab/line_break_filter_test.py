"""line_break_filter_test.py — test 3-line-break confirmation as a setup filter.

Theory: a Setup 1 trigger that ALSO coincides with a fresh line-break in the same
direction is "structural" (institutional momentum), while a trigger without line-break
confirmation is more likely 1-minute noise.

3-line break (3LB) construction from M1 closes:
  - Start with the first M1 bar as line 1.
  - For each subsequent M1 close:
    * If close > max-high of last 3 lines AND last line is RED: new GREEN line.
    * If close < min-low of last 3 lines AND last line is GREEN: new RED line.
    * If close > last GREEN line's high (continuing UP): extend GREEN.
    * If close < last RED line's low (continuing DOWN): extend RED.
    * Otherwise: no new line.

Test: layer line-break confirmation on top of LIVE filter stack.
  - Variant A: trigger direction must match the CURRENT (most recent) 3LB line color.
  - Variant B: a NEW line-break in trigger direction occurred within last N minutes.
  - Variant C: the last 3LB transition was in trigger direction (last line is fresh-flipped).
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

LB_COUNT = 3   # 3-line-break


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


# ── 3-Line Break construction ──
def build_line_break(bars_1m, lb_count=LB_COUNT):
    """Returns list of (line_open_time, line_open, line_close, line_high, line_low, color, source_bar_idx).
    color: 1=GREEN (up), -1=RED (down).
    """
    if not bars_1m: return []
    lines = []
    # Initialize with first bar as a line
    first = bars_1m[0]
    init_color = 1 if first[4] >= first[1] else -1
    lines.append({"time": first[0], "open": first[1], "close": first[4], "high": first[2], "low": first[3], "color": init_color, "src_idx": 0})

    for i in range(1, len(bars_1m)):
        bar = bars_1m[i]
        c = bar[4]
        last_line = lines[-1]
        # max-high and min-low of last lb_count lines
        recent = lines[-lb_count:]
        max_hi = max(l["high"] for l in recent)
        min_lo = min(l["low"] for l in recent)

        if last_line["color"] == 1:
            # Continuing UP: new green line if close > last green high
            if c > last_line["high"]:
                lines.append({"time": bar[0], "open": last_line["close"], "close": c,
                              "high": c, "low": last_line["close"], "color": 1, "src_idx": i})
            # Reversal to RED: close < min-low of last lb_count lines
            elif c < min_lo:
                lines.append({"time": bar[0], "open": last_line["close"], "close": c,
                              "high": last_line["close"], "low": c, "color": -1, "src_idx": i})
        else:  # last is RED
            if c < last_line["low"]:
                lines.append({"time": bar[0], "open": last_line["close"], "close": c,
                              "high": last_line["close"], "low": c, "color": -1, "src_idx": i})
            elif c > max_hi:
                lines.append({"time": bar[0], "open": last_line["close"], "close": c,
                              "high": c, "low": last_line["close"], "color": 1, "src_idx": i})
    return lines


def line_at(lines, dt):
    """Return the most recent line whose time <= dt. None if no such line."""
    candidates = [l for l in lines if l["time"] <= dt]
    return candidates[-1] if candidates else None


def lines_in_window(lines, start_dt, end_dt):
    return [l for l in lines if start_dt <= l["time"] <= end_dt]


# ── line-break filter predicates ──
def lb_match_current_color(lines, entry_dt, dir_sign):
    """Variant A: most recent line color matches trigger direction."""
    l = line_at(lines, entry_dt)
    if l is None: return False
    return l["color"] == dir_sign


def lb_new_within(lines, entry_dt, dir_sign, minutes):
    """Variant B: a new line in trigger direction formed within last N minutes."""
    start = entry_dt - timedelta(minutes=minutes)
    recent = lines_in_window(lines, start, entry_dt)
    return any(l["color"] == dir_sign for l in recent)


def lb_fresh_flip(lines, entry_dt, dir_sign, minutes):
    """Variant C: most recent line is in trigger direction AND it represents a flip
    from prior color (within last N minutes)."""
    candidates = [(i, l) for i, l in enumerate(lines) if l["time"] <= entry_dt]
    if not candidates: return False
    last_idx, last = candidates[-1]
    if last["color"] != dir_sign: return False
    # Was this line a flip (vs the prior)?
    if last_idx == 0: return True
    prior = lines[last_idx - 1]
    if prior["color"] == dir_sign:
        return False  # not a flip, just a continuation
    # Is the flip recent enough?
    return (entry_dt - last["time"]).total_seconds() <= minutes * 60


# ── runner ──
def run(label, lb_filter_fn, lines):
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
        # LIVE filter chain
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

        # NEW: line-break filter
        if lb_filter_fn is not None:
            if not lb_filter_fn(lines, entry_time, dir_sign): continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, 0.30, -0.07, 0.30)
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, 100, lots, 25, 8)
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
    max_dd = min(chain_pnls) if chain_pnls else 0
    print(f"  {label:<55s}  chains={n:<3d}  mainWR={main_wr:>5.1f}%  chainWR={chain_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2d}  max_DD=${max_dd:+7.2f}")


def main():
    print("Building 3-line-break series from all available M1 bars...")
    bars_1m = build_1m_bars()
    lines = build_line_break(bars_1m, LB_COUNT)
    print(f"Built {len(lines)} 3LB lines from {len(bars_1m)} M1 bars")
    color_counts = {1: sum(1 for l in lines if l["color"] == 1), -1: sum(1 for l in lines if l["color"] == -1)}
    print(f"  GREEN lines: {color_counts[1]}  RED lines: {color_counts[-1]}")
    print()

    print("=" * 130)
    print("LINE-BREAK CONFIRMATION ON TOP OF LIVE STACK")
    print("=" * 130)
    print()

    print("--- BASELINE (no line-break filter) ---")
    run("baseline (LIVE stack only)", None, lines)
    print()
    print("--- A) Most recent 3LB line color matches trigger direction ---")
    run("3LB current color matches trigger", lb_match_current_color, lines)
    print()
    print("--- B) Fresh 3LB line in trigger direction within N minutes ---")
    for mins in [5, 10, 20, 30, 60]:
        run(f"3LB new-line within {mins:>2}min in trigger dir", lambda L,e,d,m=mins: lb_new_within(L,e,d,m), lines)
    print()
    print("--- C) Most recent 3LB line is a fresh-flip (color change) within N minutes ---")
    for mins in [5, 10, 20, 30, 60]:
        run(f"3LB fresh-flip within {mins:>2}min in trigger dir", lambda L,e,d,m=mins: lb_fresh_flip(L,e,d,m), lines)


if __name__ == "__main__":
    main()
