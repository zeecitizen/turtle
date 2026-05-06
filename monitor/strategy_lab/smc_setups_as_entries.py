"""smc_setups_as_entries.py — backtest the 3 SMC setups as PRIMARY ENTRY signals.

Model: walk M5 bars chronologically. When a setup matches at M5 close, FIRE entry
at that close price. No probe needed — the setup IS the entry trigger.

Sizing: descending ladder 0.70 → 0.10 per chain (same as Shano-Zee).
Exits: trail $12/$4, fearIdeal $100, max 7 bursts (same as Shano-Zee).
Hour filter: skip 04-06 + 21-23 broker.

All 3 setups require:
  - HTF uptrend (price above H1 21-EMA, for buys; mirror for sells)
  - Retracement context (recent red candles after green for buys; mirror)
  - H1 FVG tapped on M5 within last K bars
  - Specific candle pattern (UHV breakout / engulfing low-vol / wick-back-inside)
"""
from __future__ import annotations
import csv, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import (
    Config, build_1m_bars, ticks_in_range, COMMON_DIR, CONTRACT_SIZE, get_emas, compute_ema,
)

TRAIL_TRIGGER = 12.0
TRAIL_DROP = 4.0
HORIZON_SEC = 600


def aggregate_to_tf_with_vol(bars_1m, minutes):
    """Return bars with (dt, o, h, l, c, vol)."""
    out = []
    cur = None; o = h = l = c = None; v = 0
    for b in bars_1m:
        dt, b_o, b_h, b_l, b_c, b_v = b[0], b[1], b[2], b[3], b[4], b[5]
        if minutes >= 60:
            hr_per_bucket = minutes // 60
            bm_hr = (dt.hour // hr_per_bucket) * hr_per_bucket
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


def detect_h1_fvgs_running(h1_bars, up_to_idx):
    """Return list of FVGs that were FORMED by index up_to_idx (inclusive).
    FVG bullish: bar[i-2].low > bar[i].high, zone = [bar[i].high, bar[i-2].low]
    FVG bearish: bar[i-2].high < bar[i].low, zone = [bar[i-2].high, bar[i].low]"""
    fvgs = []
    for i in range(2, up_to_idx + 1):
        prev = h1_bars[i-2]; cur = h1_bars[i]
        if prev[3] > cur[2]:
            fvgs.append((i, h1_bars[i][0], 1, cur[2], prev[3]))
        if prev[2] < cur[3]:
            fvgs.append((i, h1_bars[i][0], -1, prev[2], cur[3]))
    return fvgs


def htf_uptrend(when, h1_ema, h1_bar_idx, h1_bars):
    """Return 1 (uptrend), -1 (downtrend), 0 (n/a)."""
    bm_hr = (when.hour // 1) * 1
    bm = when.replace(hour=bm_hr, minute=0, second=0, microsecond=0)
    idx = h1_bar_idx.get(bm)
    if idx is None:
        for d in range(1, 24):
            t = bm - timedelta(hours=d)
            idx = h1_bar_idx.get(t)
            if idx is not None: break
    if idx is None or idx >= len(h1_ema) or h1_ema[idx] is None: return 0
    ema = h1_ema[idx]; price = h1_bars[idx][4]
    return 1 if price > ema else -1


def m5_in_retracement(m5_bars, m5_idx, dir_sign, lookback=10):
    if m5_idx < lookback: return False
    recent = m5_bars[m5_idx - lookback:m5_idx + 1]
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


def m5_tapped_active_fvg(m5_idx, m5_bars, dir_sign, h1_fvgs, lookback_m5=20):
    """Return True if any active H1 FVG of given direction was tapped by M5 bars in last lookback_m5."""
    relevant = [f for f in h1_fvgs if f[2] == dir_sign]
    if not relevant: return False
    start = max(0, m5_idx - lookback_m5)
    for f in relevant:
        _, fvg_dt, _, zlo, zhi = f
        for i in range(start, m5_idx + 1):
            bar = m5_bars[i]
            if bar[0] < fvg_dt: continue  # FVG not yet formed
            if bar[3] <= zhi and bar[2] >= zlo: return True
    return False


def find_uhv_red_idx(m5_bars, m5_idx, lookback, dir_sign):
    """Find highest-vol red (for buys) or green (for sells) in last N bars."""
    start = max(0, m5_idx - lookback)
    cands = []
    for i in range(start, m5_idx):
        bar = m5_bars[i]
        is_red = bar[4] < bar[1]; is_green = bar[4] > bar[1]
        if dir_sign == 1 and is_red: cands.append(i)
        elif dir_sign == -1 and is_green: cands.append(i)
    if not cands: return None
    return max(cands, key=lambda i: m5_bars[i][5])


def setup1_match(m5_bars, m5_idx, dir_sign, lookback=10):
    """UHV breakout: previous bars contain UHV-red, swept by intermediate, current bar broke high."""
    if m5_idx < 3: return False
    uhv_idx = find_uhv_red_idx(m5_bars, m5_idx, lookback, dir_sign)
    if uhv_idx is None: return False
    uhv = m5_bars[uhv_idx]
    swept = False
    for i in range(uhv_idx + 1, m5_idx):
        if dir_sign == 1 and m5_bars[i][3] < uhv[3]: swept = True; break
        if dir_sign == -1 and m5_bars[i][2] > uhv[2]: swept = True; break
    if not swept: return False
    cur = m5_bars[m5_idx]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False
        if cur[4] <= uhv[2]: return False
    else:
        if cur[4] >= cur[1]: return False
        if cur[4] >= uhv[3]: return False
    return True


def setup2_match(m5_bars, m5_idx, dir_sign, lookback=10):
    """Engulfing with LOWER volume than red."""
    if m5_idx < 1: return False
    cur = m5_bars[m5_idx]; prev = m5_bars[m5_idx - 1]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False  # cur green
        if prev[4] >= prev[1]: return False  # prev red
        if cur[4] <= prev[1] or cur[1] >= prev[4]: return False  # engulfing
        if cur[5] >= prev[5]: return False  # lower vol
    else:
        if cur[4] >= cur[1]: return False
        if prev[4] <= prev[1]: return False
        if cur[4] >= prev[1] or cur[1] <= prev[4]: return False
        if cur[5] >= prev[5]: return False
    return True


def setup3_match(m5_bars, m5_idx, dir_sign, lookback=10):
    """Wick below red low, close back inside red body, HIGHER green vol."""
    if m5_idx < 1: return False
    red_idx = None
    for i in range(m5_idx - 1, max(0, m5_idx - lookback) - 1, -1):
        bar = m5_bars[i]
        if dir_sign == 1 and bar[4] < bar[1]: red_idx = i; break
        if dir_sign == -1 and bar[4] > bar[1]: red_idx = i; break
    if red_idx is None: return False
    red = m5_bars[red_idx]; cur = m5_bars[m5_idx]
    if dir_sign == 1:
        if cur[4] <= cur[1]: return False  # cur green
        if cur[3] >= red[3]: return False  # cur wicks below red low
        body_lo = min(red[1], red[4]); body_hi = max(red[1], red[4])
        if not (body_lo <= cur[4] <= body_hi): return False  # cur close inside red body
        if cur[5] <= red[5]: return False  # cur green vol > red vol
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


def burst_filters_allow(when, dir_sign, h1_ema, bar_idx_h1, h1_bars):
    h = when.hour
    if (4 <= h <= 6) or (21 <= h <= 23): return False
    t = htf_uptrend(when, h1_ema, bar_idx_h1, h1_bars)
    if t == 0 or t != dir_sign: return False
    return True


def sim_chain(entry_dt, entry_price, dir_sign, fear_ideal,
              max_burst, ladder_start, ladder_step, ladder_max,
              h1_ema, bar_idx_h1, h1_bars, horizon_sec=HORIZON_SEC):
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
        if not burst_filters_allow(exit_dt, dir_sign, h1_ema, bar_idx_h1, h1_bars): break
        cur_dt = exit_dt
        main_entry = exit_price
        burst_idx += 1
    return main_results


def run(label, *, setup_id, require_h1_fvg=True, require_retrace=True, require_htf_trend=True,
         buys_only=False, sells_only=False, fvg_lookback_m5=20):
    bars_1m = build_1m_bars()
    bars_5m = aggregate_to_tf_with_vol(bars_1m, 5)
    bars_h1 = aggregate_to_tf_with_vol(bars_1m, 60)
    bar_idx_5m = {b[0]: i for i, b in enumerate(bars_5m)}
    bar_idx_h1 = {b[0]: i for i, b in enumerate(bars_h1)}
    h1_ema = compute_ema([b[4] for b in bars_h1], 21)

    # Walk M5 bars, fire on setup match
    chains = []
    last_chain_end = None  # avoid overlapping chains
    for m5_idx, bar in enumerate(bars_5m):
        bar_dt = bar[0]
        if last_chain_end is not None and bar_dt <= last_chain_end:
            continue  # in-flight from previous chain
        # Hour filter
        h = bar_dt.hour
        if (4 <= h <= 6) or (21 <= h <= 23): continue
        # Determine direction by HTF trend (uptrend = buys, downtrend = sells)
        t = htf_uptrend(bar_dt, h1_ema, bar_idx_h1, bars_h1)
        if t == 0: continue
        dir_sign = t
        if buys_only and dir_sign != 1: continue
        if sells_only and dir_sign != -1: continue

        # Detect FVGs formed by current H1
        bm_hr = bar_dt.replace(minute=0, second=0, microsecond=0)
        h1_idx = bar_idx_h1.get(bm_hr, -1)
        if h1_idx < 2: continue
        h1_fvgs = detect_h1_fvgs_running(bars_h1, h1_idx)
        if require_h1_fvg:
            if not m5_tapped_active_fvg(m5_idx, bars_5m, dir_sign, h1_fvgs, fvg_lookback_m5): continue
        if require_retrace:
            if not m5_in_retracement(bars_5m, m5_idx, dir_sign): continue
        if require_htf_trend:
            if t != dir_sign: continue
        # Setup match
        if setup_id == 1:
            if not setup1_match(bars_5m, m5_idx, dir_sign): continue
        elif setup_id == 2:
            if not setup2_match(bars_5m, m5_idx, dir_sign): continue
        elif setup_id == 3:
            if not setup3_match(bars_5m, m5_idx, dir_sign): continue
        elif setup_id is not None:
            continue

        # Fire entry at M5 close (close of current bar, just confirmed)
        # Entry time: bar close time = bar_dt + 5min (start of next bar)
        entry_dt = bar_dt + timedelta(minutes=5)
        # Get tick at that time for entry price
        first_ticks = ticks_in_range(entry_dt, entry_dt + timedelta(seconds=30))
        if not first_ticks: continue
        first_bid, first_ask = first_ticks[0][1], first_ticks[0][2]
        entry_price = first_ask if dir_sign == 1 else first_bid

        chain = sim_chain(entry_dt, entry_price, dir_sign,
                          fear_ideal=100, max_burst=7,
                          ladder_start=0.70, ladder_step=-0.10, ladder_max=0.70,
                          h1_ema=h1_ema, bar_idx_h1=bar_idx_h1, h1_bars=bars_h1)
        chains.append((entry_dt, dir_sign, chain))
        # Update last_chain_end so we don't fire overlapping chains during the chain run
        chain_dur = sum(1 for m in chain) * 600  # assume each main lasts up to horizon
        last_chain_end = entry_dt + timedelta(seconds=chain_dur)

    n = len(chains)
    all_mains = [m for _, _, c in chains for m in c]
    total = sum(m[1] for m in all_mains)
    wins = sum(1 for m in all_mains if m[1] > 0)
    chain_pnls = [sum(m[1] for m in c) for _, _, c in chains]
    losing = sum(1 for p in chain_pnls if p < 0)
    big_loss = min((m[1] for m in all_mains if m[1] <= 0), default=0)
    print(f"  {label:<70}chains={n:<3}mains={len(all_mains):<4}WR={wins/max(len(all_mains),1)*100:>5.1f}%  total=${total:+8.2f}  losing={losing}  worst=${big_loss:+.2f}")


print("=" * 180)
print("SMC SETUPS AS PRIMARY ENTRY SIGNAL — walk M5 bars, fire on setup match")
print("Sizing: descending ladder 0.70->0.10, fearI=$100, max 7 bursts. Hour filter applied.")
print("=" * 180)
print()

print("--- INDIVIDUAL SETUPS (no extra context, just setup match + hour + HTF trend) ---")
run("Setup 1 alone (UHV breakout)", setup_id=1, require_h1_fvg=False, require_retrace=False, require_htf_trend=True)
run("Setup 2 alone (engulfing low-vol)", setup_id=2, require_h1_fvg=False, require_retrace=False, require_htf_trend=True)
run("Setup 3 alone (wick reversal)", setup_id=3, require_h1_fvg=False, require_retrace=False, require_htf_trend=True)

print()
print("--- + RETRACEMENT context ---")
run("Setup 1 + retracement", setup_id=1, require_h1_fvg=False, require_retrace=True)
run("Setup 2 + retracement", setup_id=2, require_h1_fvg=False, require_retrace=True)
run("Setup 3 + retracement", setup_id=3, require_h1_fvg=False, require_retrace=True)

print()
print("--- + H1 FVG TAP (full theory) ---")
run("Setup 1 + retracement + H1 FVG (FULL)", setup_id=1, require_h1_fvg=True, require_retrace=True)
run("Setup 2 + retracement + H1 FVG (FULL)", setup_id=2, require_h1_fvg=True, require_retrace=True)
run("Setup 3 + retracement + H1 FVG (FULL)", setup_id=3, require_h1_fvg=True, require_retrace=True)

print()
print("--- TUNING H1 FVG lookback for SETUP 1 (most promising) ---")
for lb in [10, 20, 40, 80]:
    run(f"Setup 1 + retracement + H1 FVG (m5 lb={lb})", setup_id=1, require_retrace=True, fvg_lookback_m5=lb)

print()
print("--- BUYS ONLY vs SELLS ONLY (Setup 1 full) ---")
run("Setup 1 BUYS only + retrace + FVG", setup_id=1, require_retrace=True, buys_only=True)
run("Setup 1 SELLS only + retrace + FVG", setup_id=1, require_retrace=True, sells_only=True)
