"""setup1_tuning.py — push Setup 1 HARD GATE WR from 84.5% toward 95%.

Sweep variables:
  - setup1LookbackBars (1, 2, 3, 5, 7)
  - setup1PatternLookback (5, 7, 10, 15, 20)
  - Combine with: M5 hidden div, tighter spread, tighter tick-speed
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, get_emas, compute_ema,
)
from advanced_features import compute_atr

PROBE_CONFIRM = 0.45
TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
PROBE_LOTS = 0.01
HORIZON_SEC = 600


def trend_at(when, ema_f, ema_s, bar_idx_2m, tf=2):
    anchor = when.minute - (when.minute % tf)
    bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx_2m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf * d)
            idx = bar_idx_2m.get(t)
            if idx is not None: break
        if idx is None: return None
    if idx < 89: return None
    f = ema_f[idx]; s = ema_s[idx]; fp = ema_f[idx-1]
    if f is None or s is None or fp is None: return None
    if f > s and f > fp: return 1
    if f < s and f < fp: return -1
    return 0


def get_uhv_bar(when, bars_1m, bar_idx_1m, lookback=20):
    bm = when.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < lookback + 1: return None, None, None
    trigger_idx = idx - 1
    lookback_bars = bars_1m[max(0, trigger_idx - lookback):trigger_idx]
    if not lookback_bars: return None, None, None
    uhv = max(lookback_bars, key=lambda b: b[5])
    uhv_global_idx = bars_1m.index(uhv)
    return uhv, uhv_global_idx, trigger_idx


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback=20):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
    if t is None or t == 0 or t != dir_sign: return False
    uhv, _, _ = get_uhv_bar(when, bars_1m, bar_idx_1m, uhv_lookback)
    if uhv is None: return False
    if dir_sign == 1 and price <= uhv[2]: return False
    if dir_sign == -1 and price >= uhv[3]: return False
    return True


def sim_one_main(entry, dir_sign, ticks, fear_ideal, lots,
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP):
    if not ticks: return 0.0, None, entry
    peak = 0.0; last = 0.0; last_dt = ticks[-1][0]; last_price = entry
    for dt, bid, ask in ticks:
        if dir_sign == 1: profit = (bid - entry) * lots * CONTRACT_SIZE; cur = bid
        else: profit = (entry - ask) * lots * CONTRACT_SIZE; cur = ask
        last = profit; last_dt = dt; last_price = cur
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return round(profit, 2), dt, cur
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur
    return round(last, 2), last_dt, last_price


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
              fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
              ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
              uhv_lookback=20, horizon_sec=HORIZON_SEC):
    main_results = []
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price, ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m, uhv_lookback): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def find_uhv_red_idx_m1(bars_1m, idx, lookback, dir_sign):
    start = max(0, idx - lookback)
    cands = []
    for i in range(start, idx):
        bar = bars_1m[i]
        is_red = bar[4] < bar[1]; is_green = bar[4] > bar[1]
        if dir_sign == 1 and is_red: cands.append(i)
        elif dir_sign == -1 and is_green: cands.append(i)
    if not cands: return None
    return max(cands, key=lambda i: bars_1m[i][5])


def setup1_at_m1(bars_1m, idx, dir_sign, lookback=10):
    if idx < 3: return False
    uhv_idx = find_uhv_red_idx_m1(bars_1m, idx, lookback, dir_sign)
    if uhv_idx is None: return False
    uhv = bars_1m[uhv_idx]
    swept = False
    for i in range(uhv_idx + 1, idx):
        if dir_sign == 1 and bars_1m[i][3] < uhv[3]: swept = True; break
        if dir_sign == -1 and bars_1m[i][2] > uhv[2]: swept = True; break
    if not swept: return False
    cur = bars_1m[idx]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False
        if cur[4] <= uhv[2]: return False
    else:
        if cur[4] >= cur[1]: return False
        if cur[4] >= uhv[3]: return False
    return True


def setup1_active(probe_time, dir_sign, bars_1m, bar_idx_1m, lookback_bars, pattern_lookback):
    bm = probe_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None: return False
    start = max(pattern_lookback, idx - lookback_bars)
    for i in range(start, idx + 1):
        if setup1_at_m1(bars_1m, i, dir_sign, pattern_lookback):
            return True
    return False


def run(label, *, lb_bars=3, pattern_lb=10,
        require_buys_only=False, require_setup1=True,
        extra_uhv_strict=False,
        fear_ideal=100, trail_trig=12, trail_drop=4):
    """Run with Setup 1 HARD GATE + tunable extras."""
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    chains = []
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
        except (ValueError, KeyError): continue
        if require_buys_only and dir_sign != 1: continue
        ticks = ticks_in_range(entry_time, close_time)
        if not ticks: continue
        confirm_dt = confirm_bid = confirm_ask = None; confirm_speed = None
        for dt, bid, ask in ticks:
            if dir_sign == 1: fav = (bid - entry_price) * PROBE_LOTS * CONTRACT_SIZE
            else: fav = (entry_price - ask) * PROBE_LOTS * CONTRACT_SIZE
            if fav >= PROBE_CONFIRM:
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask
                confirm_speed = (dt - entry_time).total_seconds(); break
        if confirm_dt is None: continue

        # Standard Shano-Zee BIG STACK base filters
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is None: continue
        trigger = bars_1m[trigger_idx]
        if dir_sign == 1 and trigger[4] <= uhv[2]: continue
        if dir_sign == -1 and trigger[4] >= uhv[3]: continue

        # OPTIONAL: stricter UHV — trigger close must be > UHV high by some buffer
        if extra_uhv_strict:
            if dir_sign == 1 and (trigger[4] - uhv[2]) < 0.5: continue
            if dir_sign == -1 and (uhv[3] - trigger[4]) < 0.5: continue

        # Setup 1 HARD GATE
        if require_setup1:
            if not setup1_active(entry_time, dir_sign, bars_1m, bar_idx_1m, lb_bars, pattern_lb): continue

        chain = sim_chain(confirm_dt, confirm_bid, confirm_ask, dir_sign,
                          fear_ideal=fear_ideal, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          ema_f=ema_f, ema_s=ema_s, bar_idx_2m=bar_idx_2m,
                          bars_1m=bars_1m, bar_idx_1m=bar_idx_1m)
        chains.append((entry_time, dir_sign, chain))

    n = len(chains); all_mains = [m for _, _, c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for _, _, c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    chain_wr = (n - losing) / max(n, 1) * 100
    print(f"  {label:<70}chains={n:<3}  WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing:<2}  chain_WR={chain_wr:>5.1f}%  worst=${big_loss:+.2f}")


print("=" * 200)
print("SETUP 1 HARD GATE TUNING — push 84.5% WR / 14 chains / 4 losing toward 95% / 0-1 losing")
print("=" * 200)
print()
print("--- BASELINE ---")
run("Current LIVE: lb_bars=3, pattern=10", lb_bars=3, pattern_lb=10)

print()
print("--- LOOKBACK BARS sweep (how recent the setup match must be) ---")
for lb in [1, 2, 3, 4, 5, 7, 10]:
    run(f"lb_bars={lb}, pattern=10", lb_bars=lb, pattern_lb=10)

print()
print("--- PATTERN LOOKBACK sweep (how far to search for UHV in the setup) ---")
for pl in [5, 7, 10, 12, 15, 20]:
    run(f"lb_bars=3, pattern={pl}", lb_bars=3, pattern_lb=pl)

print()
print("--- BUYS ONLY (sells underperform in our data) ---")
for lb in [1, 2, 3, 5]:
    run(f"lb={lb}, pattern=10, BUYS only", lb_bars=lb, pattern_lb=10, require_buys_only=True)

print()
print("--- STRICTER UHV BREAKOUT (trigger must be >= 0.5pt past UHV) + Setup 1 ---")
for lb in [3, 5]:
    run(f"lb={lb} + strict UHV", lb_bars=lb, pattern_lb=10, extra_uhv_strict=True)
    run(f"lb={lb} + strict UHV BUYS only", lb_bars=lb, pattern_lb=10, extra_uhv_strict=True, require_buys_only=True)

print()
print("--- TIGHTER FEARIDEAL / TRAIL ---")
for fi in [60, 80, 100, 120]:
    run(f"lb=3 fearI=${fi}", lb_bars=3, pattern_lb=10, fear_ideal=fi)

print()
print("--- COMBOS: BUYS + STRICTER UHV + DIFFERENT FEARIDEAL ---")
for lb in [1, 2, 3]:
    run(f"BUYS + strict UHV lb={lb} fearI=$80", lb_bars=lb, pattern_lb=10,
        require_buys_only=True, extra_uhv_strict=True, fear_ideal=80)
    run(f"BUYS + strict UHV lb={lb} fearI=$120", lb_bars=lb, pattern_lb=10,
        require_buys_only=True, extra_uhv_strict=True, fear_ideal=120)
