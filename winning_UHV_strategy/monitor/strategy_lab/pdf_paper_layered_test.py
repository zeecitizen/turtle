"""pdf_paper_layered_test.py — backtest the testable claims from "Comprehensive Analysis of Ultra-High Win Rate Trading Strategies".

Layered on top of CURRENT LIVE config (84.2% baseline). For each claim, add ONE new
gate to the standard LIVE filter chain and measure delta vs baseline.

Tests:
  T1. "Strong UHV is a trap" — skip setups where UHV body is in top X% of historical distribution.
      Hypothesis: huge UHV bars represent institutional absorption (stealth distribution),
      not genuine momentum. Forensic 2026-05-02 confirmed our 1 losing chain had the
      strongest UHV of all 9 setups.

  T2. "Liquidity grab candle shapes" — skip setups where the UHV bar is a Dragonfly Doji
      (long lower wick, small body) for SELL or Gravestone Doji (long upper wick, small body)
      for BUY. PDF claim: such shapes indicate absorbed momentum / failed sweep.

  T3. "Regime classification — abstain in Volatile regimes" — classify each setup's regime by
      ATR-20 / ATR-100 ratio. Skip setups where regime is Volatile (ratio > 1.5).
      Hypothesis: mean-reversion/scalping fails in volatile expansion regimes.

  T4. "Direction inversion on extreme UHV" — the PDF says liquidity grabs reverse direction.
      Test: when UHV body > top-decile threshold, INVERT the trade direction (buy when red UHV).

Validation: fire main 0.30 lot at confirm time with LIVE filter stack, trail 25/8, SL $100
catastrophic + $15 burst SL.
"""
from __future__ import annotations
import sys, csv, random, statistics
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

# Burst safety (matches LIVE deployment 2026-05-02)
BURST_SL_USD       = 15.0   # tighter SL on bursts
FIRST_MAIN_FEAR    = 100.0  # catastrophic on first main only


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


def body(bar): return abs(bar[4] - bar[1])
def rng(bar): return bar[2] - bar[3]


# ─────────── PDF claim filter predicates ───────────

def t1_strong_uhv_trap(uhv, all_uhv_bodies, percentile=90):
    """Returns True if UHV body is in TOP percentile (i.e., should SKIP this setup).
    Hypothesis: top X% UHV bars are absorption traps, not momentum.
    """
    if not all_uhv_bodies: return False
    threshold = sorted(all_uhv_bodies)[int(len(all_uhv_bodies) * percentile / 100)]
    return body(uhv) >= threshold


def t2_dragonfly_doji(uhv, dir_sign):
    """UHV is a Dragonfly Doji (long lower wick, small body) for SELL setups,
    or Gravestone Doji (long upper wick, small body) for BUY setups.
    Returns True if the candle shape is a liquidity grab (should SKIP).
    """
    r = rng(uhv)
    if r <= 0: return False
    o, h, l, c = uhv[1], uhv[2], uhv[3], uhv[4]
    body_pct = body(uhv) / r
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    upper_pct = upper_wick / r
    lower_pct = lower_wick / r
    if body_pct > 0.30: return False  # not doji-like; substantial body
    if dir_sign == -1:  # SELL setup: dragonfly = absorbed selling
        return lower_pct > 0.50 and lower_wick > 2 * upper_wick
    else:  # BUY setup: gravestone = absorbed buying
        return upper_pct > 0.50 and upper_wick > 2 * lower_wick


def t3_compute_atr_ratio(bars_1m, bar_idx_1m, entry_time, lookback_short=20, lookback_long=100):
    """Returns ATR-short / ATR-long ratio. >1.5 = volatile regime."""
    bm = entry_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 5):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < lookback_long: return None
    short_atr = sum(rng(bars_1m[i]) for i in range(idx - lookback_short, idx)) / lookback_short
    long_atr = sum(rng(bars_1m[i]) for i in range(idx - lookback_long, idx)) / lookback_long
    if long_atr <= 0: return None
    return short_atr / long_atr


def t3b_compute_realized_vol_ratio(bars_1m, bar_idx_1m, entry_time, short_min=5, long_min=60):
    """Realized volatility ratio: short-window stdev of log returns / long-window stdev.
    More responsive than ATR because it measures variance of MOVES, not absolute range.
    >1.5 = local burst of activity vs session baseline.
    """
    import math
    bm = entry_time.replace(second=0, microsecond=0)
    idx = bar_idx_1m.get(bm)
    if idx is None:
        for d in range(1, 5):
            t = bm - timedelta(minutes=d)
            idx = bar_idx_1m.get(t)
            if idx is not None: break
    if idx is None or idx < long_min + 1: return None

    def realized_vol(start_idx, end_idx):
        rets = []
        for i in range(start_idx + 1, end_idx + 1):
            p1 = bars_1m[i - 1][4]; p2 = bars_1m[i][4]
            if p1 > 0 and p2 > 0:
                rets.append(math.log(p2 / p1))
        if len(rets) < 2: return None
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r) ** 2 for r in rets) / (len(rets) - 1)
        return math.sqrt(var)

    rv_short = realized_vol(idx - short_min, idx)
    rv_long = realized_vol(idx - long_min, idx)
    if rv_short is None or rv_long is None or rv_long <= 0: return None
    return rv_short / rv_long


# ─────────── Runner ───────────

def collect_uhv_bodies(rows, bars_1m, bar_idx_1m):
    """Pre-pass: collect UHV body sizes across all SHADOW probes for percentile threshold."""
    bodies = []
    for r in rows:
        try:
            entry_time = datetime.fromisoformat(r["entry_time"])
        except (ValueError, KeyError): continue
        uhv, _, _ = get_uhv_bar(entry_time, bars_1m, bar_idx_1m, 20)
        if uhv is not None:
            bodies.append(body(uhv))
    return bodies


def run(label, *, t1_skip_top_pct=None, t2_skip_grab=False, t3_skip_volatile=False,
        t3_volatile_ratio=1.5, t4_invert_on_top_pct=None, all_uhv_bodies=None,
        t3b_skip_volatile=False, t3b_volatile_ratio=1.5, t3b_short_min=5, t3b_long_min=60):
    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    ema_f, ema_s, bar_idx_2m, _ = get_emas(34, 89, 2)
    ema_m15_f, _, bar_idx_15m, _ = get_emas(21, 21, 15)

    chains = []
    blocked = {}
    def block(name): blocked[name] = blocked.get(name, 0) + 1

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

        # ── PDF FILTERS LAYERED ON TOP ──
        if t1_skip_top_pct is not None and all_uhv_bodies:
            if t1_strong_uhv_trap(uhv, all_uhv_bodies, percentile=t1_skip_top_pct):
                block('t1_strong_uhv'); continue

        if t2_skip_grab:
            if t2_dragonfly_doji(uhv, dir_sign):
                block('t2_grab_shape'); continue

        if t3_skip_volatile:
            ratio = t3_compute_atr_ratio(bars_1m, bar_idx_1m, entry_time)
            if ratio is not None and ratio > t3_volatile_ratio:
                block('t3_volatile_regime'); continue

        if t3b_skip_volatile:
            ratio_b = t3b_compute_realized_vol_ratio(bars_1m, bar_idx_1m, entry_time,
                                                      short_min=t3b_short_min, long_min=t3b_long_min)
            if ratio_b is not None and ratio_b > t3b_volatile_ratio:
                block('t3b_realized_vol_regime'); continue

        # T4: invert direction if UHV is in top percentile
        if t4_invert_on_top_pct is not None and all_uhv_bodies:
            if t1_strong_uhv_trap(uhv, all_uhv_bodies, percentile=t4_invert_on_top_pct):
                dir_sign = -dir_sign

        # Main + bursts (matches LIVE with burstSlUsd=$15)
        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < 7:
            lots = lot_for_burst(burst_idx, 0.30, -0.07, 0.30)
            sl_for_this = FIRST_MAIN_FEAR if burst_idx == 0 else BURST_SL_USD
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, sl_for_this, lots, 25, 8)
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
    return n, total, losing, main_wr, chain_wr, blocked


def main():
    print("=" * 130)
    print("PDF PAPER LAYERED TEST — testable claims from 'Comprehensive Analysis of Ultra-High WR Strategies'")
    print("All filters layered on CURRENT LIVE config (with burstSlUsd=$15 deployed)")
    print("=" * 130)
    print()

    rows = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
    rows.sort(key=lambda r: r.get("entry_time", ""))
    bars_1m = build_1m_bars()
    bar_idx_1m = {b[0]: i for i, b in enumerate(bars_1m)}
    print(f"Pre-pass: collecting UHV body distribution from {len(rows)} SHADOW probes...")
    all_uhv_bodies = collect_uhv_bodies(rows, bars_1m, bar_idx_1m)
    if all_uhv_bodies:
        s = sorted(all_uhv_bodies); n = len(s)
        print(f"  UHV bodies (n={n}): min={s[0]:.2f}  q25={s[n//4]:.2f}  median={s[n//2]:.2f}  q75={s[3*n//4]:.2f}  q90={s[int(n*0.9)]:.2f}  max={s[-1]:.2f}")
    print()

    print("--- BASELINE (LIVE + burstSlUsd=$15) ---")
    base = run("LIVE + burstSL=$15", all_uhv_bodies=all_uhv_bodies)
    print()

    print("--- T1: Skip setups where UHV body is in top X% (Stealth Distribution / liquidity grab) ---")
    for pct in [99, 95, 90, 85, 75]:
        s = run(f"T1: skip top {100-pct}% strongest UHV", t1_skip_top_pct=pct, all_uhv_bodies=all_uhv_bodies)
        print(f"      blocks: {s[5]}")
    print()

    print("--- T2: Skip setups where UHV is a Dragonfly/Gravestone Doji (liquidity grab shape) ---")
    s = run("T2: skip Dragonfly/Gravestone UHV", t2_skip_grab=True, all_uhv_bodies=all_uhv_bodies)
    print(f"      blocks: {s[5]}")
    print()

    print("--- T3: Skip Volatile regimes (ATR-20 / ATR-100 ratio > X) ---")
    for ratio_thr in [1.2, 1.5, 1.8, 2.0]:
        s = run(f"T3: skip if ATR-20/ATR-100 > {ratio_thr}", t3_skip_volatile=True, t3_volatile_ratio=ratio_thr, all_uhv_bodies=all_uhv_bodies)
        print(f"      blocks: {s[5]}")
    print()

    print("--- T4: INVERT direction when UHV is in top X% (PDF claim: liquidity grab reverses) ---")
    for pct in [95, 90, 85, 75]:
        s = run(f"T4: invert direction on top {100-pct}% UHV", t4_invert_on_top_pct=pct, all_uhv_bodies=all_uhv_bodies)
    print()

    print("--- COMBO: T1 (skip top 10%) + T3 (skip volatile 1.5+) ---")
    s = run("T1+T3 combo", t1_skip_top_pct=90, t3_skip_volatile=True, t3_volatile_ratio=1.5, all_uhv_bodies=all_uhv_bodies)
    print(f"      blocks: {s[5]}")
    print()

    print("--- T3b: REALIZED-VOL regime (short-window stdev / long-window stdev) — finer than ATR ratio ---")
    print("    Hypothesis: rv-ratio > X = local burst of variance vs session baseline")
    for short, long_, ratio_thr in [(3, 30, 1.5), (5, 60, 1.5), (5, 60, 2.0), (5, 60, 2.5),
                                      (10, 120, 1.5), (10, 120, 2.0)]:
        label = f"T3b: skip if rv({short}m)/rv({long_}m) > {ratio_thr}"
        s = run(label, t3b_skip_volatile=True, t3b_volatile_ratio=ratio_thr,
                t3b_short_min=short, t3b_long_min=long_, all_uhv_bodies=all_uhv_bodies)
        print(f"      blocks: {s[5]}")


if __name__ == "__main__":
    main()
