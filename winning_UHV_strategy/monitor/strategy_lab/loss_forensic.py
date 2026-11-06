"""loss_forensic.py — analyze each big losing trade from 04-26 to 04-30
and check if the current ULTIMATE STACK would have prevented it.

Trades extracted from MT5 history screenshot (04-30 visible trades):
  Big losses (>$50): 7 trades on 04-30 totaling -$688
  Small losses (<$10): probe failures, 0.01 lots — minor

For each big loss, check:
  - Setup 1 pattern present at trigger time?
  - UHV breakout > 0.3pt past extreme?
  - Tick-speed <= 15s into trigger bar?
  - Spread <= 1.2x median at confirm time?
  - Burst-delta agreed at burst-fire time?
  - 2-min trend aligned?
  - M15 trend aligned?
  - Bad-hours window?
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, find_uhv_red_idx_m1, setup1_at_m1, burst_delta_positive,
    get_uhv_bar
)

# Big losses from 04-30 screenshot
LOSS_TRADES = [
    # (open_time, close_time, dir, lots, pnl)
    ("2026-04-30 16:47:33", "2026-04-30 16:47:37", "sell", 0.7, -69.30),
    ("2026-04-30 17:37:34", "2026-04-30 17:37:52", "sell", 0.7, -79.10),
    ("2026-04-30 18:45:38", "2026-04-30 18:46:13", "sell", 0.7, -98.70),
    ("2026-04-30 18:45:38", "2026-04-30 18:46:56", "sell", 0.6, -132.60),
    ("2026-04-30 19:16:33", "2026-04-30 19:16:45", "sell", 0.7, -99.40),
    ("2026-04-30 19:41:00", "2026-04-30 19:42:05", "sell", 0.7, -100.10),
    ("2026-04-30 19:45:36", "2026-04-30 19:46:29", "sell", 0.6, -109.20),
]


def analyze(open_time_str, close_time_str, dir_str, lots, pnl):
    open_time = datetime.fromisoformat(open_time_str.replace(' ', 'T'))
    dir_sign = 1 if dir_str == "buy" else -1

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

    print(f"\n{'='*100}")
    print(f"TRADE: {open_time_str} {dir_str.upper()} {lots} lots → ${pnl:+.2f}")
    print(f"{'='*100}")

    # Get UHV bar for context (open_time minute - 1 = trigger bar)
    uhv, uhv_idx, trigger_idx = get_uhv_bar(open_time, bars_1m, bar_idx_1m, 20)
    if uhv is None:
        print("  ! Cannot find UHV bar — skipping analysis")
        return None
    trigger = bars_1m[trigger_idx]
    print(f"  UHV bar @ {uhv[0].strftime('%H:%M')}: H={uhv[2]:.2f} L={uhv[3]:.2f} vol={uhv[5]}")
    print(f"  Trigger bar @ {trigger[0].strftime('%H:%M')}: O={trigger[1]:.2f} C={trigger[4]:.2f}")

    fixes = []   # (filter_name, would_block, why)

    # 1. Bad-hours
    h = open_time.hour
    bad_hour = (4 <= h <= 6) or (21 <= h <= 23)
    fixes.append(("bad_hours", bad_hour, f"hour={h}"))

    # 2. UHV breakout + 0.3pt margin
    margin = 0.3
    if dir_sign == 1:
        cleared = trigger[4] >= uhv[2] + margin
        diff = trigger[4] - uhv[2]
        fixes.append(("uhv_filter (margin 0.3)", not cleared,
                      f"trigger close {trigger[4]:.2f} vs UHV high {uhv[2]:.2f} (diff {diff:+.2f})"))
    else:
        cleared = trigger[4] <= uhv[3] - margin
        diff = uhv[3] - trigger[4]
        fixes.append(("uhv_filter (margin 0.3)", not cleared,
                      f"trigger close {trigger[4]:.2f} vs UHV low {uhv[3]:.2f} (diff {diff:+.2f})"))

    # 3. Tick-speed
    ts = actual_tick_speed(open_time, dir_sign, uhv[2], uhv[3])
    if ts is None:
        fixes.append(("tick_speed (≤15s)", True, "no UHV cross found in trigger bar"))
    else:
        fixes.append(("tick_speed (≤15s)", ts > 15, f"crossed UHV at {ts:.0f}s into trigger bar"))

    # 4. Spread (rough check)
    spread_ok = actual_spread_check(open_time, 1.2)
    fixes.append(("spread (≤1.2x)", not spread_ok, "spread baseline check"))

    # 5. 2-min trend
    t2 = trend_at(open_time, ema_f, ema_s, bar_idx_2m, 2)
    if t2 is None:
        fixes.append(("trend_2m", False, "no trend data"))
    else:
        agrees = (t2 == dir_sign)
        fixes.append(("trend_2m", not agrees and t2 != 0, f"trend={t2} dir={dir_sign}"))

    # 6. M15 trend
    ema_m15 = m15_trend_at(open_time, ema_m15_f, bar_idx_15m)
    if ema_m15 is None:
        fixes.append(("m15_trend", False, "no M15 data"))
    else:
        # For SELL: price must be BELOW M15-EMA
        # For BUY: price must be ABOVE M15-EMA
        ticks = ticks_in_range(open_time - timedelta(seconds=2), open_time + timedelta(seconds=2))
        if ticks:
            _, b, a = ticks[0]
            price = (b + a) / 2
            if dir_sign == 1: blocks = price <= ema_m15
            else: blocks = price >= ema_m15
            fixes.append(("m15_trend", blocks, f"price={price:.2f} M15-EMA={ema_m15:.2f}"))
        else:
            fixes.append(("m15_trend", False, "no tick at open time"))

    # 7. Setup 1
    s1 = setup1_active(open_time, dir_sign, bars_1m, bar_idx_1m, 3, 10)
    fixes.append(("setup1_filter", not s1, f"Setup 1 {'present' if s1 else 'NOT present'}"))

    # 8. Burst-delta at open
    bd = burst_delta_positive(open_time, dir_sign, 15)
    fixes.append(("burst_delta (15s)", not bd, "delta 15s window"))

    # Print results
    print(f"\n  Filter check (would have BLOCKED this trade?):")
    blocking_filters = []
    for name, blocks, why in fixes:
        mark = "✅ BLOCK" if blocks else "    pass"
        print(f"    {mark}  {name:<25} {why}")
        if blocks:
            blocking_filters.append(name)

    if blocking_filters:
        print(f"\n  → {len(blocking_filters)} filter(s) would PREVENT this loss: {', '.join(blocking_filters)}")
    else:
        print(f"\n  ⚠ NO FILTER blocks this — would still happen on current stack!")
    return blocking_filters


print("=" * 200)
print("FORENSIC ANALYSIS — every big loss from 04-30 vs current ULTIMATE STACK")
print("=" * 200)

results = []
for t in LOSS_TRADES:
    blockers = analyze(*t)
    results.append((t, blockers))

print()
print("=" * 200)
print("SUMMARY")
print("=" * 200)
total_loss = sum(t[4] for t in LOSS_TRADES)
n = len(LOSS_TRADES)
prevented = sum(1 for _, b in results if b)
not_prevented = n - prevented
prevented_loss = sum(t[4] for (t, b) in results if b)
not_prevented_loss = sum(t[4] for (t, b) in results if not b)
print(f"Total losses analyzed: {n}  (sum: ${total_loss:+.2f})")
print(f"  Would-be PREVENTED by current stack: {prevented}/{n}  (saved: ${prevented_loss:+.2f})")
print(f"  Would-be STILL-LOSS on current stack: {not_prevented}/{n}  (still lost: ${not_prevented_loss:+.2f})")

print()
print("Per-filter prevention count (which filters catch which losses):")
filter_catches = {}
for _, blockers in results:
    if not blockers: continue
    for f in blockers:
        filter_catches[f] = filter_catches.get(f, 0) + 1
for f, c in sorted(filter_catches.items(), key=lambda x: -x[1]):
    print(f"  {f:<25}: {c}/{n}")
