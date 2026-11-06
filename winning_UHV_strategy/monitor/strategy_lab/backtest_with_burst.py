"""backtest_with_burst.py — full backtest of new Shano-Zee with lot ladder + filtered burst.

Models the actual live behavior:
  1. Probe confirms + filters (hour + 2-min trend + skip-fast + UHV breakout) pass → main 1 opens at 0.10 lot
  2. Main 1 trails to exit (trail $12/$4 trigger, fearIdeal $100)
  3. If main 1 profitable AND BurstFiltersAllow at exit (hour + trend + UHV-still-extending) → burst 2 opens at 0.20 lot
  4. Repeat until filter fails, fearIdeal hits, or burst chain hits maxBurst (7)

Compares:
  - Current Shano-Zee (no burst, lots=0.70)  ← what backtest assumed before
  - Shano-Zee + lot ladder + filtered burst  ← new live behavior
  - And toggles to isolate effect
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, SHADOW_CSV, CONTRACT_SIZE, get_emas,
)

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


def get_uhv_extremes(when, bars_1m, bar_idx_1m, lookback=20):
    """Return (uhv_high, uhv_low) of the highest-tickcount bar in the prior `lookback` 1-min bars."""
    bm = when.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < lookback + 1: return None, None
    lookback_bars = bars_1m[max(0, idx - 1 - lookback):idx - 1]
    if not lookback_bars: return None, None
    uhv = max(lookback_bars, key=lambda b: b[5])
    return uhv[2], uhv[3]


def burst_filters_allow(when, dir_sign, price, ema_f, ema_s, bar_idx_2m,
                         bars_1m, bar_idx_1m, *,
                         skip_bad_hours=True, trend_filter=True, uhv_filter=True,
                         uhv_lookback=20):
    """Mirror of EA's BurstFiltersAllow."""
    if skip_bad_hours:
        h = when.hour
        if (4 <= h <= 6) or (21 <= h <= 23): return False
    if trend_filter:
        t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0: return False
        if t != dir_sign: return False
    if uhv_filter:
        uhv_high, uhv_low = get_uhv_extremes(when, bars_1m, bar_idx_1m, uhv_lookback)
        if uhv_high is None: return False
        # Continuation: price must STILL be beyond UHV extreme
        if dir_sign == 1 and price <= uhv_high: return False
        if dir_sign == -1 and price >= uhv_low: return False
    return True


def sim_one_main(entry, dir_sign, ticks, fear_ideal, lots,
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP):
    """Sim a single main from entry → exit. Returns (pnl, exit_dt, exit_price, exit_reason)."""
    if not ticks: return 0.0, None, entry, "no_data"
    peak = 0.0; last_profit = 0.0; last_dt = ticks[-1][0]; last_price = entry
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry) * lots * CONTRACT_SIZE
            cur_price = bid  # for exit
        else:
            profit = (entry - ask) * lots * CONTRACT_SIZE
            cur_price = ask
        last_profit = profit; last_dt = dt; last_price = cur_price
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return round(profit, 2), dt, cur_price, "fearIdeal"
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur_price, "trail"
    return round(last_profit, 2), last_dt, last_price, "horizon"


def sim_chain(probe_entry_time, dir_sign, confirm_dt, confirm_bid, confirm_ask,
              fear_ideal, max_burst,
              ladder_start, ladder_step, ladder_max,
              ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
              uhv_lookback=20, horizon_sec=HORIZON_SEC):
    """Sim a burst chain starting from probe confirm. Each next burst checks BurstFiltersAllow."""
    main_results = []  # list of (lot, pnl, reason)
    main_entry = confirm_ask if dir_sign == 1 else confirm_bid
    cur_dt = confirm_dt
    burst_idx = 0  # 0 = first main
    while burst_idx < max_burst:
        lots = min(ladder_start + burst_idx * ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price, reason = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl, reason))
        # Burst chain breaks on losing main
        if pnl <= 0: break
        # Check filters at exit moment to see if we burst again
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price,
                                    ema_f, ema_s, bar_idx_2m,
                                    bars_1m, bar_idx_1m,
                                    uhv_lookback=uhv_lookback): break
        # Open next burst at the current price
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run_backtest(label, *,
                 fear_ideal=100,
                 max_burst=1,         # 1 = no burst (just the original main)
                 ladder_start=0.70, ladder_step=0.0, ladder_max=0.70,  # constant lot
                 uhv_filter=True, uhv_lookback=20):
    rows = []
    with open(SHADOW_CSV, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f): rows.append(r)
    rows.sort(key=lambda r: r.get("entry_time", ""))

    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)

    confirmed = 0
    chains = []  # list of list-of-(lot,pnl,reason)
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
            close_time = datetime.fromisoformat(r["close_time"])
            entry_price = float(r["entry_price"])
            dir_sign = 1 if r["dir"] == "buy" else -1
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
        if confirm_dt is None: continue
        confirmed += 1

        # Apply Shano-Zee filters (same as live ShouldOpenMain)
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        if uhv_filter:
            uhv_h, uhv_l = get_uhv_extremes(entry_time, bars_1m, bar_idx_1m, uhv_lookback)
            if uhv_h is None: continue
            # Trigger candle (the 1-min bar before entry minute) must close beyond UHV extreme
            bm = entry_time.replace(second=0, microsecond=0)
            idx = bar_idx_1m.get(bm)
            if idx is None or idx < 1: continue
            trigger_close = bars_1m[idx - 1][4]
            if dir_sign == 1 and trigger_close <= uhv_h: continue
            if dir_sign == -1 and trigger_close >= uhv_l: continue

        chain = sim_chain(entry_time, dir_sign, confirm_dt, confirm_bid, confirm_ask,
                          fear_ideal, max_burst,
                          ladder_start, ladder_step, ladder_max,
                          ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m,
                          uhv_lookback=uhv_lookback)
        chains.append(chain)

    # Aggregate
    n_chains = len(chains)
    all_mains = [m for c in chains for m in c]  # flatten
    n_mains = len(all_mains)
    wins = [m for m in all_mains if m[1] > 0]
    losses = [m for m in all_mains if m[1] <= 0]
    total = sum(m[1] for m in all_mains)
    avg_chain_len = n_mains / max(n_chains, 1)
    fearI_hits = sum(1 for m in all_mains if m[2] == "fearIdeal")
    big_loss = min((m[1] for m in losses), default=0)

    print(f"  {label}")
    print(f"    chains={n_chains}  mains={n_mains}  avg chain len={avg_chain_len:.2f}")
    print(f"    main WR={len(wins)/max(n_mains,1)*100:.1f}%  total=${total:+8.2f}")
    print(f"    fearIdeal hits={fearI_hits}  worst loss=${big_loss:+.2f}")
    # Lot histogram
    from collections import Counter
    lots_count = Counter(round(m[0],2) for m in all_mains)
    lot_str = " | ".join(f"{lot}×{count}" for lot, count in sorted(lots_count.items()))
    print(f"    lot distribution: {lot_str}")
    print()


print("=" * 130)
print("Shano-Zee BURST + LADDER backtest — 172 probe dataset")
print("All variants: probeConfirm=0.45, trail=$12/$4, hour+2min trend+skipFast+UHV(20) filters, fearI=$100")
print("=" * 130)
print()

print("--- BASELINE (no burst, what backtest assumed before) ---")
run_backtest("0.70 lot, no burst (CURRENT BACKTEST ASSUMPTION)",
             max_burst=1, ladder_start=0.70, ladder_step=0.0, ladder_max=0.70)

print("--- WITH FILTERED BURST (no ladder, constant 0.70 lot) ---")
run_backtest("0.70 lot, max 5 bursts (filtered, constant lot)",
             max_burst=5, ladder_start=0.70, ladder_step=0.0, ladder_max=0.70)
run_backtest("0.70 lot, max 7 bursts (filtered, constant lot)",
             max_burst=7, ladder_start=0.70, ladder_step=0.0, ladder_max=0.70)

print("--- WITH LOT LADDER (0.10 → 0.70 step 0.10, max 7 bursts) ---")
run_backtest("LADDER: 0.10→0.70 step 0.10, max 7 bursts (NEW LIVE)",
             max_burst=7, ladder_start=0.10, ladder_step=0.10, ladder_max=0.70)

print("--- LADDER VARIANTS (alternative ladders) ---")
run_backtest("LADDER: 0.20→0.70 step 0.10, max 6 bursts",
             max_burst=6, ladder_start=0.20, ladder_step=0.10, ladder_max=0.70)
run_backtest("LADDER: 0.10→1.00 step 0.15, max 7 bursts (more aggressive)",
             max_burst=7, ladder_start=0.10, ladder_step=0.15, ladder_max=1.00)
run_backtest("LADDER: 0.10→0.40 step 0.05, max 7 bursts (conservative)",
             max_burst=7, ladder_start=0.10, ladder_step=0.05, ladder_max=0.40)

print("--- ABLATION: turn off UHV but keep ladder ---")
run_backtest("LADDER no UHV: 0.10→0.70 step 0.10, max 7 bursts",
             max_burst=7, ladder_start=0.10, ladder_step=0.10, ladder_max=0.70,
             uhv_filter=False)

print("--- FEARIDEAL SWEEP on the new live config ---")
for fi in [60, 80, 100, 120, 150]:
    run_backtest(f"LADDER + fearI=${fi}",
                 fear_ideal=fi, max_burst=7,
                 ladder_start=0.10, ladder_step=0.10, ladder_max=0.70)
