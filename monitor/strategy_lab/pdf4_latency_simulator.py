"""pdf4_latency_simulator.py — Directive Alpha from PDF #4.

Destroy the zero-latency assumption. Simulate the Pine→PineConnector→MT5 path.

Per PDF: 200-800ms Gaussian-distributed delay (mean 450ms) + 1.5pip min slippage.

Test: Does our 97.1% WR survive? If WR drops to <85%, the asymmetric risk
profile (~$10 wins vs $100 losses) breaks and we MUST change the trade structure.
"""
from __future__ import annotations
import csv, sys, random, statistics
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas, SHADOW_CSV, CONTRACT_SIZE
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, burst_delta_positive, get_uhv_bar
)

PROBE_LOTS = 0.01
PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
HORIZON_SEC = 600

# PDF #4 Directive Alpha parameters
LATENCY_MEAN_MS = 450      # Gaussian mean
LATENCY_STDEV_MS = 150     # spread to give ~95% range 200-800ms
LATENCY_MIN_MS = 200
LATENCY_MAX_MS = 800
SLIPPAGE_PIPS = 1.5        # per execution (entry AND exit) on XAUUSD
PIP_SIZE = 0.10            # 1 pip on XAUUSD = $0.10

random.seed(42)


def latency_ms():
    """Gaussian random latency clamped to 200-800ms range."""
    while True:
        ms = random.gauss(LATENCY_MEAN_MS, LATENCY_STDEV_MS)
        if LATENCY_MIN_MS <= ms <= LATENCY_MAX_MS:
            return ms


def find_tick_after(when, ticks, latency_ms_val):
    """Skip forward in tick array by latency_ms milliseconds and find the first tick at/after that time."""
    target = when + timedelta(milliseconds=latency_ms_val)
    for i, (dt, bid, ask) in enumerate(ticks):
        if dt >= target:
            return (dt, bid, ask, i)
    if ticks:
        return ticks[-1] + (len(ticks)-1,) if len(ticks[-1]) == 3 else ticks[-1]
    return None


def latency_slipped_fill(when, ticks, dir_sign, intended_price):
    """
    Find the actual fill price after latency + slippage:
    - Skip forward by latency_ms
    - Apply slippage: BUY pays MORE (ask + slippage), SELL receives LESS (bid - slippage)
    Returns (actual_dt, actual_price, slippage_dollars_vs_intended)
    """
    lat = latency_ms()
    target_t = when + timedelta(milliseconds=lat)
    # Find first tick at or after target_t
    actual = None
    for dt, bid, ask in ticks:
        if dt >= target_t:
            actual = (dt, bid, ask)
            break
    if actual is None:
        if ticks:
            actual = ticks[-1]
        else:
            return None, None, 0.0
    dt, bid, ask = actual
    # Apply slippage to whichever side we'd fill
    slip = SLIPPAGE_PIPS * PIP_SIZE  # 1.5 pips × $0.10/pip = $0.15
    if dir_sign == 1:  # buying: pay ask + slippage
        actual_price = ask + slip
    else:  # selling: receive bid - slippage
        actual_price = bid - slip
    slippage_cost = abs(actual_price - intended_price)
    return dt, actual_price, slippage_cost


def sim_one_main_with_latency(intended_entry_dt, dir_sign, intended_entry_price, ticks, fear_ideal, lots):
    """Simulate a single main trade with realistic latency+slippage on entry AND exit."""
    if not ticks: return 0.0, "no_ticks", None
    # Apply latency to entry
    actual_entry_dt, actual_entry_price, entry_slip = latency_slipped_fill(
        intended_entry_dt, ticks, dir_sign, intended_entry_price)
    if actual_entry_dt is None:
        return 0.0, "entry_failed", None
    # Walk forward from actual entry
    # Find ticks after actual_entry_dt
    forward_ticks = [t for t in ticks if t[0] >= actual_entry_dt]
    if not forward_ticks: return 0.0, "no_forward", None

    peak = 0.0; last_profit = 0.0
    intended_exit_dt = None; intended_exit_price = None; exit_reason = "horizon_end"
    for dt, bid, ask in forward_ticks:
        if dir_sign == 1:
            cur = bid  # close at bid (we'd sell back at bid)
            profit = (cur - actual_entry_price) * lots * CONTRACT_SIZE
        else:
            cur = ask  # close at ask (we'd buy back at ask)
            profit = (actual_entry_price - cur) * lots * CONTRACT_SIZE
        last_profit = profit
        if profit > peak: peak = profit
        # Check exits
        if profit <= -fear_ideal:
            intended_exit_dt = dt; intended_exit_price = cur; exit_reason = "fearIdeal"; break
        if peak >= TRAIL_TRIGGER and (peak - profit) >= TRAIL_DROP:
            intended_exit_dt = dt; intended_exit_price = cur; exit_reason = "trail"; break
    if intended_exit_dt is None:
        # Horizon end
        intended_exit_dt = forward_ticks[-1][0]
        intended_exit_price = forward_ticks[-1][1] if dir_sign == 1 else forward_ticks[-1][2]

    # Apply latency to exit (closing direction = opposite of entry)
    exit_dir = -dir_sign
    actual_exit_dt, actual_exit_price, exit_slip = latency_slipped_fill(
        intended_exit_dt, forward_ticks, exit_dir, intended_exit_price)
    if actual_exit_dt is None:
        actual_exit_price = intended_exit_price
    # Final P&L using actual entry + actual exit prices
    if dir_sign == 1:
        final_pnl = (actual_exit_price - actual_entry_price) * lots * CONTRACT_SIZE
    else:
        final_pnl = (actual_entry_price - actual_exit_price) * lots * CONTRACT_SIZE
    return round(final_pnl, 2), exit_reason, actual_exit_dt


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def sim_chain_with_latency(confirm_dt, intended_entry, dir_sign,
                            fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
                            ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
                            burst_delta=True):
    main_results = []
    cur_dt = confirm_dt
    cur_intended = intended_entry
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_reason, exit_dt = sim_one_main_with_latency(
            cur_dt, dir_sign, cur_intended, ticks, fear_ideal, lots)
        main_results.append((lots, pnl, exit_reason))
        if pnl <= 0: break
        if exit_dt is None: break
        # Burst filter checks (no latency on filter logic)
        h = exit_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): break
        t = trend_at(exit_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: break
        uhv, _, _ = get_uhv_bar(exit_dt, bars_1m, bar_idx_1m, 20)
        if uhv is None: break
        # Get latest tick price for UHV continuation check
        recent_ticks = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
        if recent_ticks:
            _, b, a = recent_ticks[-1]
            cur_price = b if dir_sign == -1 else a
            if dir_sign == 1 and cur_price <= uhv[2]: break
            if dir_sign == -1 and cur_price >= uhv[3]: break
        if burst_delta and not burst_delta_positive(exit_dt, dir_sign, 15): break
        # Next burst: use exit_dt as new "confirm" and get fresh intended entry
        cur_dt = exit_dt
        next_ticks = ticks_in_range(exit_dt, exit_dt + timedelta(seconds=2))
        if next_ticks:
            _, b, a = next_ticks[0]
            cur_intended = a if dir_sign == 1 else b
        else:
            break
        burst_idx += 1
    return main_results


def run(label, *, latency_on=True, slippage_on=True):
    """Run full LIVE stack with optional latency+slippage simulation."""
    global SLIPPAGE_PIPS
    saved_slip = SLIPPAGE_PIPS
    if not slippage_on:
        SLIPPAGE_PIPS = 0.0

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

        # Apply latency to PROBE entry too (Pine alert → PineConnector → MT5)
        if latency_on:
            actual_probe_entry_dt, actual_probe_entry, _ = latency_slipped_fill(
                entry_time, ticks, dir_sign, entry_price)
            if actual_probe_entry_dt is None: continue
            entry_time = actual_probe_entry_dt
            entry_price = actual_probe_entry

        # Find confirm with the (possibly slipped) entry
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        ticks_after = [t for t in ticks if t[0] >= entry_time]
        for dt, bid, ask in ticks_after:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        # Filter cascade (use original entry_time for pattern detection — those use bar data, not tick fills)
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        if 3 <= confirm_speed <= 8: continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        margin = 0.3
        if dir_sign == 1 and trigger[4] < uhv[2] + margin: continue
        if dir_sign == -1 and trigger[4] > uhv[3] - margin: continue
        ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
        if ts is None or ts > 15: continue
        if not actual_spread_check(confirm_dt, 1.2): continue
        ema_v = m15_trend_at(confirm_dt, ema_m15_f, bar_idx_15m)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10): continue

        # All filters pass — fire main trade with latency
        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        chain = sim_chain_with_latency(confirm_dt, intended_entry, dir_sign,
                                        fear_ideal=100, max_burst=7,
                                        ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                                        ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                                        bars_1m=bars_1m, bar_idx_1m=bar_idx_1m)
        chains.append(chain)

    SLIPPAGE_PIPS = saved_slip
    n = len(chains); all_mains = [(m[0], m[1]) for c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    chain_wr = (n - losing) / max(n, 1) * 100
    main_wr = wins / max(len(all_mains), 1) * 100
    print(f"  {label:<55}chains={n:<3}  WR={main_wr:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chain_WR={chain_wr:>5.1f}%  worst=${big_loss:+.2f}")
    return n, total, losing, main_wr


print("=" * 100)
print("PDF #4 DIRECTIVE ALPHA — Stochastic Latency + Slippage Simulator")
print("=" * 100)
print("Latency: Gaussian 450ms±150ms, clamped 200-800ms")
print("Slippage: 1.5 pips ($0.15) per fill on XAUUSD")
print("Applied to: probe entry, main entry, main exit")
print()

print("--- BASELINE (current backtest assumption: zero latency, zero slippage) ---")
run("LIVE: zero-latency (current backtest)", latency_on=False, slippage_on=False)
print()

print("--- PDF DIRECTIVE: realistic latency + slippage ---")
# Run multiple times to see variance
results = []
for i in range(5):
    n, t, l, wr = run(f"LIVE + latency + slippage (run {i+1})", latency_on=True, slippage_on=True)
    results.append((n, t, l, wr))

print()
print("--- AGGREGATE over 5 runs ---")
avg_n = statistics.mean(r[0] for r in results)
avg_total = statistics.mean(r[1] for r in results)
avg_losing = statistics.mean(r[2] for r in results)
avg_wr = statistics.mean(r[3] for r in results)
worst_total = min(r[1] for r in results)
best_total = max(r[1] for r in results)
print(f"  avg chains: {avg_n:.1f}")
print(f"  avg WR: {avg_wr:.1f}%")
print(f"  avg total: ${avg_total:+.2f}")
print(f"  avg losing chains: {avg_losing:.1f}")
print(f"  range: ${worst_total:.0f} to ${best_total:.0f}")

print()
print("--- LATENCY-ONLY (no slippage) ---")
run("LIVE + latency only", latency_on=True, slippage_on=False)

print()
print("--- SLIPPAGE-ONLY (no latency) ---")
run("LIVE + slippage only (1.5 pip)", latency_on=False, slippage_on=True)

print()
print("=" * 100)
print("VERDICT")
print("=" * 100)
print(f"Backtest 97.1% / +$720 → realistic ~{avg_wr:.0f}% / ${avg_total:+.0f}")
print(f"Per-PDF success criterion: 'If WR plummets below 65% or expectancy goes negative,")
print(f"current parameters are incompatible with retail execution infrastructure.'")
