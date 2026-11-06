"""descending_ladder_test.py — backtest ascending vs descending lot ladder.

Theory under test: trend strength is HIGHEST at UHV breakout and decays as the
chain extends. Therefore the FIRST main (max conviction) should carry the
biggest position; subsequent bursts (declining conviction) should shrink.

Compares:
  - Ascending  (0.10 → 0.70 step +0.10)  ← what we ran today
  - Descending (0.70 → 0.10 step -0.10)  ← user's new theory
  - Constant 0.40                          ← simple baseline
  - Constant 0.70                          ← original Shano-Zee (no ladder)
  - Plus chain-by-chain breakdown for inspection
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

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
                         bars_1m, bar_idx_1m, uhv_lookback=20):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = trend_at(when, ema_f, ema_s, bar_idx_2m, 2)
    if t is None or t == 0 or t != dir_sign: return False
    uhv_high, uhv_low = get_uhv_extremes(when, bars_1m, bar_idx_1m, uhv_lookback)
    if uhv_high is None: return False
    if dir_sign == 1 and price <= uhv_high: return False
    if dir_sign == -1 and price >= uhv_low: return False
    return True


def sim_one_main(entry, dir_sign, ticks, fear_ideal, lots,
                 trail_trig=TRAIL_TRIGGER, trail_drop=TRAIL_DROP):
    if not ticks: return 0.0, None, entry, "no_data"
    peak = 0.0; last_profit = 0.0; last_dt = ticks[-1][0]; last_price = entry
    for dt, bid, ask in ticks:
        if dir_sign == 1:
            profit = (bid - entry) * lots * CONTRACT_SIZE
            cur_price = bid
        else:
            profit = (entry - ask) * lots * CONTRACT_SIZE
            cur_price = ask
        last_profit = profit; last_dt = dt; last_price = cur_price
        if profit > peak: peak = profit
        if profit <= -fear_ideal: return round(profit, 2), dt, cur_price, "fearIdeal"
        if peak >= trail_trig and (peak - profit) >= trail_drop:
            return round(profit, 2), dt, cur_price, "trail"
    return round(last_profit, 2), last_dt, last_price, "horizon"


def lot_for_burst(burst_idx, start, step, max_lot, min_lot=0.01):
    """Burst index 0 = first main."""
    lot = start + burst_idx * step
    if lot > max_lot: lot = max_lot
    if lot < min_lot: lot = min_lot
    return round(lot, 2)


def sim_chain(probe_entry_time, dir_sign, confirm_dt, confirm_bid, confirm_ask,
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
        pnl, exit_dt, exit_price, reason = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl, reason))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, exit_price,
                                    ema_f, ema_s, bar_idx_2m,
                                    bars_1m, bar_idx_1m, uhv_lookback): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run_test(label, *, fear_ideal=80, max_burst=7,
             ladder_start=0.10, ladder_step=0.10, ladder_max=0.70,
             show_chains=False):
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
        h = confirm_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = trend_at(confirm_dt, ema_f, ema_s, bar_idx_2m, 2)
        if t is None or t == 0 or t != dir_sign: continue
        if 3 <= confirm_speed <= 8: continue
        uhv_h, uhv_l = get_uhv_extremes(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv_h is None: continue
        bm = entry_time.replace(second=0, microsecond=0)
        idx = bar_idx_1m.get(bm)
        if idx is None or idx < 1: continue
        trigger_close = bars_1m[idx - 1][4]
        if dir_sign == 1 and trigger_close <= uhv_h: continue
        if dir_sign == -1 and trigger_close >= uhv_l: continue

        chain = sim_chain(entry_time, dir_sign, confirm_dt, confirm_bid, confirm_ask,
                          fear_ideal, max_burst, ladder_start, ladder_step, ladder_max,
                          ema_f, ema_s, bar_idx_2m, bars_1m, bar_idx_1m)
        chains.append((entry_time, dir_sign, chain))

    n_chains = len(chains)
    all_mains = [m for _, _, c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = [m for m in all_mains if m[1] > 0]
    losses = [m for m in all_mains if m[1] <= 0]
    fearI = sum(1 for m in all_mains if m[2] == "fearIdeal")
    big_loss = min((m[1] for m in losses), default=0)
    chain_pnls = [sum(m[1] for m in c) for _, _, c in chains]
    losing_chains = sum(1 for p in chain_pnls if p < 0)
    avg_chain_len = len(all_mains) / max(n_chains, 1)

    print(f"  {label}")
    print(f"    chains={n_chains}  mains={len(all_mains)}  avg chain len={avg_chain_len:.2f}")
    print(f"    main WR={len(wins)/max(len(all_mains),1)*100:.1f}%  total=${total:+8.2f}")
    print(f"    losing chains={losing_chains}/{n_chains}  fearI hits={fearI}  worst single loss=${big_loss:+.2f}")

    if show_chains:
        print(f"    Per-chain breakdown:")
        for i, (et, ds, c) in enumerate(chains):
            cp = sum(m[1] for m in c)
            seq = " ".join(f"{m[0]:.2f}={m[1]:+.0f}" for m in c)
            mark = "  <-- LOSER" if cp < 0 else ""
            print(f"      #{i+1} {et.strftime('%m-%d %H:%M')} {'BUY' if ds==1 else 'SELL'} ({len(c)} mains, ${cp:+7.2f}): {seq}{mark}")
    print()


print("=" * 140)
print("DESCENDING vs ASCENDING LADDER — full backtest on 172 probes")
print("All variants: probeConfirm=0.45, trail=$12/$4, fearI=$80, maxBurst=7, UHV(20) filter")
print("=" * 140)
print()

print("--- HEAD TO HEAD ---")
run_test("ASCENDING:  0.10→0.70 step +0.10  (what we ran today)",
         ladder_start=0.10, ladder_step=0.10, ladder_max=0.70, show_chains=True)

run_test("DESCENDING: 0.70→0.10 step -0.10  (user's new theory)",
         ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70, show_chains=True)

print("--- CONSTANT BASELINES (no ladder) ---")
run_test("Constant 0.40 lot, max 7 bursts",
         ladder_start=0.40, ladder_step=0.0, ladder_max=0.40)
run_test("Constant 0.70 lot, max 7 bursts",
         ladder_start=0.70, ladder_step=0.0, ladder_max=0.70)
run_test("Constant 0.70 lot, max 1 burst (no burst at all)",
         max_burst=1, ladder_start=0.70, ladder_step=0.0, ladder_max=0.70)

print("--- DESCENDING VARIANTS ---")
run_test("DESCENDING shallow: 0.50→0.10 step -0.07",
         ladder_start=0.50, ladder_step=-0.07, ladder_max=0.50)
run_test("DESCENDING aggressive: 1.00→0.10 step -0.15",
         ladder_start=1.00, ladder_step=-0.15, ladder_max=1.00)
run_test("DESCENDING short: 0.70→0.20 step -0.10 max 6",
         max_burst=6, ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70)

print("--- DESCENDING + FEARIDEAL TUNING ---")
for fi in [50, 60, 70, 80, 100]:
    run_test(f"DESCENDING 0.70→0.10 + fearI=${fi}",
             fear_ideal=fi, ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70)
