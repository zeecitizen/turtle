"""filter_examples.py — find concrete BLOCKED vs PASSED trade examples for each filter.

Used to power the risk-management report. For each filter, surface:
  - 1 example trade where filter BLOCKED a probe that would have lost
  - 1 example trade where filter PASSED a probe that became a winner

This grounds the abstract filter logic in real data the user can see.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas, SHADOW_CSV, CONTRACT_SIZE
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, find_uhv_red_idx_m1, setup1_at_m1, burst_delta_positive,
    get_uhv_bar
)

PROBE_LOTS = 0.01
PROBE_CONFIRM = 0.45

print("=" * 100)
print("Filter Examples — surface BLOCKED-by-X and PASSED-by-X trades from probe_shadow")
print("=" * 100)

rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
rows.sort(key=lambda r: r.get("entry_time", ""))

bars_1m = build_1m_bars()
bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

# Examples bucket: filter_name -> {"blocked": [], "passed_winners": []}
examples = {}

def add_blocked(filter_name, info):
    examples.setdefault(filter_name, {"blocked": [], "passed_winners": []})["blocked"].append(info)

def add_pass(filter_name, info):
    examples.setdefault(filter_name, {"blocked": [], "passed_winners": []})["passed_winners"].append(info)


for r in rows:
    try:
        entry_time = datetime.fromisoformat(r["entry_time"])
        close_time = datetime.fromisoformat(r["close_time"])
        entry_price = float(r["entry_price"])
        dir_sign = 1 if r["dir"] == "buy" else -1
        outcome_pnl = float(r.get("net_pnl", 0))  # at probe size
    except (ValueError, KeyError): continue
    ticks = ticks_in_range(entry_time, close_time)
    if not ticks: continue
    confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
    for dt, bid, ask in ticks:
        if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
        else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
        if fav >= PROBE_CONFIRM:
            confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
            confirm_speed = (dt - entry_time).total_seconds(); break
    if confirm_dt is None:
        continue  # probe failed, no main fired

    info = {
        "time": entry_time.strftime("%m-%d %H:%M:%S"),
        "dir": "BUY" if dir_sign == 1 else "SELL",
        "entry": entry_price,
        "confirm_speed": confirm_speed,
    }

    h = confirm_dt.hour
    bad_hour = (4 <= h <= 6) or (21 <= h <= 23)
    if bad_hour: add_blocked("bad_hours", {**info, "why": f"hour={h}"})

    fast = 3 <= confirm_speed <= 8
    if fast: add_blocked("fast_confirm", {**info, "why": f"confirm_speed={confirm_speed:.1f}s"})

    t2 = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
    if t2 is None or t2 == 0 or t2 != dir_sign:
        add_blocked("trend_2m", {**info, "why": f"2m trend={t2} dir={dir_sign}"})

    uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
    if uhv is None: continue
    trigger = bars_1m[trigger_idx]

    # UHV breakout + 0.3pt margin
    if dir_sign == 1:
        diff = trigger[4] - uhv[2]
        if diff < 0.3:
            add_blocked("uhv_filter+margin", {**info, "why": f"close {trigger[4]:.2f} only {diff:+.2f}pt past UHV high {uhv[2]:.2f}"})
    else:
        diff = uhv[3] - trigger[4]
        if diff < 0.3:
            add_blocked("uhv_filter+margin", {**info, "why": f"close {trigger[4]:.2f} only {diff:+.2f}pt past UHV low {uhv[3]:.2f}"})

    ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
    if ts is None or ts > 15:
        add_blocked("tick_speed_15s", {**info, "why": f"UHV crossed at {ts}s into trigger bar"})

    spread_ok = actual_spread_check(confirm_dt, 1.2)
    if not spread_ok: add_blocked("spread_1.2x", {**info, "why": f"spread > 1.2x median"})

    s1 = setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, 3, 10)
    if not s1: add_blocked("setup1_hardgate", {**info, "why": "no Setup 1 pattern in last 3 M1 bars"})

    bd = burst_delta_positive(entry_time, dir_sign, 15)
    if not bd: add_blocked("burst_delta_15s", {**info, "why": f"delta against direction"})

    # If ALL pass and probe was winner — example of GOOD pass-through
    all_pass = (not bad_hour and not fast and t2 == dir_sign and
                ((dir_sign == 1 and trigger[4] - uhv[2] >= 0.3) or
                 (dir_sign == -1 and uhv[3] - trigger[4] >= 0.3)) and
                (ts is not None and ts <= 15) and spread_ok and s1 and bd)
    if all_pass and outcome_pnl > 0:
        ex = {**info, "why": "passed full ULTIMATE stack", "pnl_at_probe_size": outcome_pnl}
        add_pass("all_filters", ex)


# Print one example per filter
print()
for fname in ["bad_hours", "fast_confirm", "trend_2m", "uhv_filter+margin",
              "tick_speed_15s", "spread_1.2x", "setup1_hardgate", "burst_delta_15s"]:
    e = examples.get(fname, {})
    blocked = e.get("blocked", [])
    print(f"\n[{fname}]  blocked count: {len(blocked)}")
    if blocked:
        ex = blocked[0]
        print(f"  BLOCKED example: {ex['time']} {ex['dir']} @ {ex['entry']:.2f}")
        print(f"    Reason: {ex['why']}")

# Show 3 GOOD passes
e = examples.get("all_filters", {})
ex = e.get("passed_winners", [])
print(f"\n[all filters PASS + winning probe]  count: {len(ex)}")
for x in ex[:5]:
    print(f"  GOOD: {x['time']} {x['dir']} @ {x['entry']:.2f} → probe pnl ${x['pnl_at_probe_size']:+.2f} (would scale to ~${x['pnl_at_probe_size']*70:.0f} at 0.7 lots)")
