"""smc_setups_lower_tf.py — backtest 3 SMC setups on M1/M2/M3 bars without FVG requirement.

Setups (each detected on the chosen TF):
  Setup 1: UHV red candle exists in retracement → swept low → trigger green breaks UHV high
  Setup 2: red candle then engulfing green with LOWER volume
  Setup 3: green wicks below red low + closes inside red body + HIGHER green volume

Required context (no FVG):
  - HTF uptrend on a higher TF (M15 EMA-21)
  - Recent retracement on entry TF
  - Hour filter (skip 04-06 + 21-23)

Entry: at next bar's first tick (close of trigger TF bar).
Sizing: descending ladder 0.70 → 0.10, fearI=$100, max 7 bursts.
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, CONTRACT_SIZE, get_emas, compute_ema,
)

TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
HORIZON_SEC = 600


def aggregate_to_tf_with_vol(bars_1m, minutes):
    if minutes == 1: return list(bars_1m)
    out = []
    cur = None; o = h = l = c = None; v = 0
    for b in bars_1m:
        dt, b_o, b_h, b_l, b_c, b_v = b[0], b[1], b[2], b[3], b[4], b[5]
        if minutes >= 60:
            hr_per = minutes // 60
            bm_hr = (dt.hour // hr_per) * hr_per
            bm = dt.replace(hour=bm_hr, minute=0, second=0, microsecond=0)
        else:
            anchor = dt.minute - (dt.minute % minutes)
            bm = dt.replace(minute=anchor, second=0, microsecond=0)
        if cur is None:
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; v = b_v
        elif bm != cur:
            out.append((cur, o, h, l, c, v))
            cur = bm; o = b_o; h = b_h; l = b_l; c = b_c; v = b_v
        else:
            if b_h > h: h = b_h
            if b_l < l: l = b_l
            c = b_c; v += b_v
    if cur is not None: out.append((cur, o, h, l, c, v))
    return out


def htf_uptrend(when, ema_arr, bar_idx, bars, tf_min):
    if tf_min >= 60:
        hr_per = tf_min // 60
        bm = when.replace(hour=(when.hour // hr_per) * hr_per, minute=0, second=0, microsecond=0)
    else:
        anchor = when.minute - (when.minute % tf_min)
        bm = when.replace(minute=anchor, second=0, microsecond=0)
    idx = bar_idx.get(bm)
    if idx is None:
        for d in range(1, 30):
            t = bm - timedelta(minutes=tf_min * d)
            idx = bar_idx.get(t)
            if idx is not None: break
    if idx is None or idx >= len(ema_arr) or ema_arr[idx] is None: return 0
    ema = ema_arr[idx]; price = bars[idx][4]
    return 1 if price > ema else -1


def in_retracement(bars, idx, dir_sign, lookback=10):
    if idx < lookback: return False
    recent = bars[idx - lookback:idx + 1]
    if dir_sign == 1:
        had_green = False
        for i in range(1, len(recent)):
            cur = recent[i]; prev = recent[i-1]
            if prev[4] > prev[1]: had_green = True
            if had_green and cur[4] < cur[1] and cur[3] < prev[3]: return True
        return False
    else:
        had_red = False
        for i in range(1, len(recent)):
            cur = recent[i]; prev = recent[i-1]
            if prev[4] < prev[1]: had_red = True
            if had_red and cur[4] > cur[1] and cur[2] > prev[2]: return True
        return False


def find_uhv_idx(bars, idx, lookback, dir_sign):
    """For buys: highest-vol RED in last N. For sells: highest-vol GREEN."""
    start = max(0, idx - lookback)
    cands = []
    for i in range(start, idx):
        bar = bars[i]
        is_red = bar[4] < bar[1]; is_green = bar[4] > bar[1]
        if dir_sign == 1 and is_red: cands.append(i)
        elif dir_sign == -1 and is_green: cands.append(i)
    if not cands: return None
    return max(cands, key=lambda i: bars[i][5])


def setup1_match(bars, idx, dir_sign, lookback=10):
    if idx < 3: return False
    uhv_idx = find_uhv_idx(bars, idx, lookback, dir_sign)
    if uhv_idx is None: return False
    uhv = bars[uhv_idx]
    swept = False
    for i in range(uhv_idx + 1, idx):
        if dir_sign == 1 and bars[i][3] < uhv[3]: swept = True; break
        if dir_sign == -1 and bars[i][2] > uhv[2]: swept = True; break
    if not swept: return False
    cur = bars[idx]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False
        if cur[4] <= uhv[2]: return False
    else:
        if cur[4] >= cur[1]: return False
        if cur[4] >= uhv[3]: return False
    return True


def setup2_match(bars, idx, dir_sign, lookback=10):
    if idx < 1: return False
    cur = bars[idx]; prev = bars[idx - 1]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False
        if prev[4] >= prev[1]: return False
        if cur[4] <= prev[1] or cur[1] >= prev[4]: return False
        if cur[5] >= prev[5]: return False
    else:
        if cur[4] >= cur[1]: return False
        if prev[4] <= prev[1]: return False
        if cur[4] >= prev[1] or cur[1] <= prev[4]: return False
        if cur[5] >= prev[5]: return False
    return True


def setup3_match(bars, idx, dir_sign, lookback=10):
    if idx < 1: return False
    red_idx = None
    for i in range(idx - 1, max(0, idx - lookback) - 1, -1):
        bar = bars[i]
        if dir_sign == 1 and bar[4] < bar[1]: red_idx = i; break
        if dir_sign == -1 and bar[4] > bar[1]: red_idx = i; break
    if red_idx is None: return False
    red = bars[red_idx]; cur = bars[idx]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False
        if cur[3] >= red[3]: return False
        body_lo = min(red[1], red[4]); body_hi = max(red[1], red[4])
        if not (body_lo <= cur[4] <= body_hi): return False
        if cur[5] <= red[5]: return False
    else:
        if cur[4] >= cur[1]: return False
        if cur[2] <= red[2]: return False
        body_lo = min(red[1], red[4]); body_hi = max(red[1], red[4])
        if not (body_lo <= cur[4] <= body_hi): return False
        if cur[5] <= red[5]: return False
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


def burst_filters_allow(when, dir_sign, htf_ema, bar_idx_htf, bars_htf, tf_min):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = htf_uptrend(when, htf_ema, bar_idx_htf, bars_htf, tf_min)
    if t == 0 or t != dir_sign: return False
    return True


def sim_chain(entry_dt, entry_price, dir_sign, fear_ideal,
              max_burst, ladder_start, ladder_step, ladder_max,
              htf_ema, bar_idx_htf, bars_htf, htf_tf_min,
              horizon_sec=HORIZON_SEC):
    main_results = []
    main_entry = entry_price
    cur_dt = entry_dt
    burst_idx = 0
    while burst_idx < max_burst:
        lots = lot_for_burst(burst_idx, ladder_start, ladder_step, ladder_max)
        horizon_end = cur_dt + timedelta(seconds=horizon_sec)
        ticks = ticks_in_range(cur_dt, horizon_end)
        pnl, exit_dt, exit_price = sim_one_main(main_entry, dir_sign, ticks, fear_ideal, lots)
        main_results.append((lots, pnl))
        if pnl <= 0: break
        if exit_dt is None: break
        if not burst_filters_allow(exit_dt, dir_sign, htf_ema, bar_idx_htf, bars_htf, htf_tf_min): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run(label, *, setup_id, entry_tf=1, htf_tf=15, require_retrace=True,
         buys_only=False, sells_only=False, lookback=10):
    bars_1m = build_1m_bars()
    bars_entry = aggregate_to_tf_with_vol(bars_1m, entry_tf)
    bars_htf = aggregate_to_tf_with_vol(bars_1m, htf_tf)
    bar_idx_htf = {b[0]: i for i, b in enumerate(bars_htf)}
    htf_ema = compute_ema([b[4] for b in bars_htf], 21)

    chains = []
    last_chain_end = None
    for idx, bar in enumerate(bars_entry):
        bar_dt = bar[0]
        if last_chain_end is not None and bar_dt <= last_chain_end:
            continue
        h = bar_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        t = htf_uptrend(bar_dt, htf_ema, bar_idx_htf, bars_htf, htf_tf)
        if t == 0: continue
        dir_sign = t
        if buys_only and dir_sign != 1: continue
        if sells_only and dir_sign != -1: continue
        if require_retrace:
            if not in_retracement(bars_entry, idx, dir_sign, lookback): continue
        if setup_id == 1:
            if not setup1_match(bars_entry, idx, dir_sign, lookback): continue
        elif setup_id == 2:
            if not setup2_match(bars_entry, idx, dir_sign, lookback): continue
        elif setup_id == 3:
            if not setup3_match(bars_entry, idx, dir_sign, lookback): continue
        # Fire at close of bar = start of next bar
        entry_dt = bar_dt + timedelta(minutes=entry_tf)
        first_ticks = ticks_in_range(entry_dt, entry_dt + timedelta(seconds=30))
        if not first_ticks: continue
        first_bid, first_ask = first_ticks[0][1], first_ticks[0][2]
        entry_price = first_ask if dir_sign == 1 else first_bid

        chain = sim_chain(entry_dt, entry_price, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          htf_ema=htf_ema, bar_idx_htf=bar_idx_htf, bars_htf=bars_htf,
                          htf_tf_min=htf_tf)
        chains.append((entry_dt, dir_sign, chain))
        chain_dur = sum(1 for _ in chain) * 600
        last_chain_end = entry_dt + timedelta(seconds=chain_dur)

    n = len(chains)
    all_mains = [m for _, _, c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for _, _, c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    avg_chain_pnl = total / max(n, 1)
    print(f"  {label:<70}chains={n:<3}mains={len(all_mains):<4}WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing}  worst=${big_loss:+.2f}  avg/chain=${avg_chain_pnl:+.2f}")


print("=" * 200)
print("SMC SETUPS WITHOUT FVG REQUIREMENT — tested on M1, M2, M3 entry TFs")
print("Context: HTF uptrend on M15 EMA-21 + retracement + setup pattern + hour filter")
print("Sizing: descending ladder 0.70->0.10, fearI=$100, max 7 bursts")
print("=" * 200)
print()

print("--- SETUP 1 (UHV breakout) on different entry TFs ---")
for tf in [1, 2, 3, 5]:
    run(f"Setup 1 on M{tf} (HTF=M15)", setup_id=1, entry_tf=tf, htf_tf=15)

print()
print("--- SETUP 2 (engulfing low-vol) on different entry TFs ---")
for tf in [1, 2, 3, 5]:
    run(f"Setup 2 on M{tf} (HTF=M15)", setup_id=2, entry_tf=tf, htf_tf=15)

print()
print("--- SETUP 3 (wick reversal) on different entry TFs ---")
for tf in [1, 2, 3, 5]:
    run(f"Setup 3 on M{tf} (HTF=M15)", setup_id=3, entry_tf=tf, htf_tf=15)

print()
print("--- SETUP 1 with HTF=M5 (less strict HTF) ---")
for tf in [1, 2, 3]:
    run(f"Setup 1 on M{tf} (HTF=M5)", setup_id=1, entry_tf=tf, htf_tf=5)

print()
print("--- BUYS ONLY for top performers ---")
run("Setup 1 M1 buys only", setup_id=1, entry_tf=1, htf_tf=15, buys_only=True)
run("Setup 1 M2 buys only", setup_id=1, entry_tf=2, htf_tf=15, buys_only=True)
run("Setup 3 M1 buys only", setup_id=3, entry_tf=1, htf_tf=15, buys_only=True)
run("Setup 3 M2 buys only", setup_id=3, entry_tf=2, htf_tf=15, buys_only=True)

print()
print("--- SELLS ONLY for top performers ---")
run("Setup 1 M1 sells only", setup_id=1, entry_tf=1, htf_tf=15, sells_only=True)
run("Setup 1 M2 sells only", setup_id=1, entry_tf=2, htf_tf=15, sells_only=True)

print()
print("--- WITHOUT RETRACEMENT (just setup+HTF) ---")
for tf in [1, 2]:
    run(f"Setup 1 M{tf} no retrace", setup_id=1, entry_tf=tf, require_retrace=False)
    run(f"Setup 2 M{tf} no retrace", setup_id=2, entry_tf=tf, require_retrace=False)
    run(f"Setup 3 M{tf} no retrace", setup_id=3, entry_tf=tf, require_retrace=False)
