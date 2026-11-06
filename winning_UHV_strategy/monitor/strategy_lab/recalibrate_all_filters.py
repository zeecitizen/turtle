"""recalibrate_all_filters.py — re-tune every meaningful filter under calibrated lognormal slippage.

The previous parameter optima (burstSlUsd=$15, trail 25/8, tickSpeedMaxSec=15, etc.)
were chosen under the OLD constant 0.5pip slippage model. Under the calibrated
lognormal model (mean 1.14pips, p99.9=22pips), the optima may shift because
slippage variance changes the cost-benefit calculus of each filter.

Sweeps performed (each under lognormal sampling, 3 MC runs per scenario):
  T1. burstSlUsd: $8 → $100
  T2. max_burst: 1 → 7
  T3. trail (trigger × drop): (15,5), (20,6), (20,8), (25,8), (30,10), (35,12)
  T4. tick_speed_max_sec: 5, 10, 15, 20, 30
  T5. spread_mult: 1.0, 1.2, 1.5, 2.0
  T6. trigger_past_uhv_pts: 0, 0.2, 0.3, 0.5
  T7. fearIdeal first-main SL: $50, $80, $100, $150
  T8. effort body/wick: (0.40, 0.50), (0.50, 0.40), (0.60, 0.30)

Each scenario reports: total $, chain WR, max DD, MC range.
Final comparison: which parameter's optimum SHIFTED under calibration.
"""
from __future__ import annotations
import sys, csv, random, json
from pathlib import Path
from datetime import datetime, timedelta

LAB_DIR = Path(__file__).parent
sys.path.insert(0, str(LAB_DIR))
from unified_backtester import build_1m_bars, ticks_in_range, get_emas, SHADOW_CSV, CONTRACT_SIZE
from filter_loo_correct import (
    actual_tick_speed, actual_spread_check, trend_at, m15_trend_at,
    setup1_active, get_uhv_bar
)
from slip_calibrator import sample_slip_pips, set_mode

set_mode("lognormal")  # calibrated default

PROBE_LOTS = 0.01; PROBE_CONFIRM = 0.45; HORIZON_SEC = 600; PIP_SIZE = 0.10
LAT_MEAN = 300; LAT_STDEV = 100; LAT_MIN = 150; LAT_MAX = 600
COMMISSION_PER_LOT = 3.5
N_RUNS = 3  # MC iterations (3 is statistically light but tractable; full sweep is many scenarios)

# Defaults match LIVE config
DEFAULTS = {
    "burst_sl_usd": 15.0,
    "max_burst": 7,
    "trail_t": 25, "trail_d": 8,
    "tick_speed_max": 15,
    "spread_mult": 1.2,
    "trigger_past_pts": 0.3,
    "fear_ideal": 100,
    "effort_body_min": 0.50, "effort_wick_max": 0.40,
}

# Pre-cache heavy reads ONCE
print("Caching SHADOW + bars + EMAs once...")
ROWS = list(csv.DictReader(open(SHADOW_CSV, "r", encoding="utf-8")))
ROWS.sort(key=lambda r: r.get("entry_time", ""))
BARS_1M = build_1m_bars()
BAR_IDX_1M = {b[0]: i for i, b in enumerate(BARS_1M)}
EMA_F, EMA_S, BAR_IDX_2M, _ = get_emas(34, 89, 2)
EMA_M15_F, _, BAR_IDX_15M, _ = get_emas(21, 21, 15)
print(f"  {len(ROWS)} probes, {len(BARS_1M)} M1 bars, EMAs ready")
print()


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
    slip = sample_slip_pips() * PIP_SIZE
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


def run_once(p):
    """One full backtest with parameter dict p (overrides defaults)."""
    cfg = {**DEFAULTS, **p}
    chains = []
    for r in ROWS:
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
                confirm_dt = dt; confirm_bid = bid; confirm_ask = ask; break
        if confirm_dt is None: continue

        t = trend_at(confirm_dt, EMA_F, EMA_S, BAR_IDX_2M, 2)
        if t is None or t == 0 or t != dir_sign: continue
        uhv, _, trigger_idx = get_uhv_bar(entry_time, BARS_1M, BAR_IDX_1M, 20)
        if uhv is None: continue
        trigger = BARS_1M[trigger_idx]
        if dir_sign == 1 and trigger[4] < uhv[2] + cfg["trigger_past_pts"]: continue
        if dir_sign == -1 and trigger[4] > uhv[3] - cfg["trigger_past_pts"]: continue
        if cfg["tick_speed_max"] > 0:
            ts = actual_tick_speed(entry_time, dir_sign, uhv[2], uhv[3])
            if ts is None or ts > cfg["tick_speed_max"]: continue
        if cfg["spread_mult"] > 0:
            if not actual_spread_check(confirm_dt, cfg["spread_mult"]): continue
        ema_v = m15_trend_at(confirm_dt, EMA_M15_F, BAR_IDX_15M)
        if ema_v is not None:
            price = (confirm_bid + confirm_ask) / 2
            if dir_sign == 1 and price <= ema_v: continue
            if dir_sign == -1 and price >= ema_v: continue
        if not setup1_active(entry_time, dir_sign, BARS_1M, BAR_IDX_1M, 3, 10): continue

        intended_entry = confirm_ask if dir_sign == 1 else confirm_bid
        cur_dt = confirm_dt; cur_intended = intended_entry; burst_idx = 0
        results = []
        while burst_idx < cfg["max_burst"]:
            lots = lot_for_burst(burst_idx, 0.30, -0.07, 0.30)
            sl_for_this = cfg["fear_ideal"] if burst_idx == 0 else cfg["burst_sl_usd"]
            horizon_end = cur_dt + timedelta(seconds=HORIZON_SEC)
            tt = ticks_in_range(cur_dt, horizon_end)
            pnl, exit_dt = sim_main(cur_dt, dir_sign, cur_intended, tt, sl_for_this, lots, cfg["trail_t"], cfg["trail_d"])
            results.append((lots, pnl))
            if pnl <= 0: break
            if exit_dt is None: break
            t2 = trend_at(exit_dt, EMA_F, EMA_S, BAR_IDX_2M, 2)
            if t2 is None or t2 == 0 or t2 != dir_sign: break
            uhv2, _, _ = get_uhv_bar(exit_dt, BARS_1M, BAR_IDX_1M, 20)
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
    return n, len(all_mains), main_wr, chain_wr, total, losing, max_dd


def avg_runs(label, p):
    runs = []
    for i in range(N_RUNS):
        random.seed(42 + i)
        runs.append(run_once(p))
    n        = sum(r[0] for r in runs) / N_RUNS
    mains    = sum(r[1] for r in runs) / N_RUNS
    main_wr  = sum(r[2] for r in runs) / N_RUNS
    chain_wr = sum(r[3] for r in runs) / N_RUNS
    total_avg = sum(r[4] for r in runs) / N_RUNS
    total_min = min(r[4] for r in runs)
    total_max = max(r[4] for r in runs)
    losing   = sum(r[5] for r in runs) / N_RUNS
    max_dd   = sum(r[6] for r in runs) / N_RUNS
    print(f"  {label:<55s}  ch~{n:.1f}  mWR={main_wr:.1f}%  cWR={chain_wr:.1f}%  $={total_avg:+8.2f}  [${total_min:+.0f}..${total_max:+.0f}]  losing~{losing:.1f}  DD=${max_dd:+.0f}")
    return {"label": label, "params": p, "total": total_avg, "total_min": total_min,
            "total_max": total_max, "chain_wr": chain_wr, "main_wr": main_wr,
            "max_dd": max_dd, "losing": losing, "chains": n}


# ────────── SWEEPS ──────────

def header(title):
    print()
    print("=" * 110)
    print(title)
    print("=" * 110)


results = {}

header("BASELINE (current LIVE: burstSL=$15, max_burst=7, trail 25/8, tickSpeed=15, spread=1.2x, trigger=0.3pt, fearI=$100)")
results["baseline"] = avg_runs("baseline (LIVE config)", {})

header("T1. burstSlUsd sweep (calibrated)")
for sl in [8, 10, 12, 15, 18, 20, 25, 30, 50, 100]:
    results[f"t1_sl{sl}"] = avg_runs(f"burstSL=${sl}", {"burst_sl_usd": sl})

header("T2. max_burst sweep (calibrated, with current burstSL=$15)")
for mb in [1, 2, 3, 4, 5, 7]:
    results[f"t2_mb{mb}"] = avg_runs(f"max_burst={mb}", {"max_burst": mb})

header("T3. trail (trigger × drop) sweep")
for t, d in [(15, 5), (20, 6), (20, 8), (25, 8), (25, 10), (30, 10), (30, 8), (35, 12)]:
    results[f"t3_t{t}d{d}"] = avg_runs(f"trail {t}/{d}", {"trail_t": t, "trail_d": d})

header("T4. tick_speed_max_sec sweep")
for ts in [5, 10, 15, 20, 30, 60]:
    results[f"t4_ts{ts}"] = avg_runs(f"tick_speed<={ts}s", {"tick_speed_max": ts})

header("T5. spread_mult sweep")
for sp in [1.0, 1.2, 1.5, 2.0]:
    results[f"t5_sp{sp}"] = avg_runs(f"spread_mult<={sp}x", {"spread_mult": sp})

header("T6. trigger_past_uhv_pts sweep")
for tp in [0.0, 0.1, 0.2, 0.3, 0.5, 1.0]:
    results[f"t6_tp{tp}"] = avg_runs(f"trigger_past_uhv={tp}pt", {"trigger_past_pts": tp})

header("T7. fearIdeal (first-main catastrophic SL) sweep")
for fi in [50, 80, 100, 150, 200]:
    results[f"t7_fi{fi}"] = avg_runs(f"fearIdeal=${fi}", {"fear_ideal": fi})

header("T8. effort-result body/wick sweep")
for body, wick in [(0.40, 0.50), (0.50, 0.40), (0.60, 0.30), (0.70, 0.30)]:
    results[f"t8_b{body}w{wick}"] = avg_runs(f"effort body>={body} wick<={wick}",
                                              {"effort_body_min": body, "effort_wick_max": wick})

header("T9. COMBOS — best-of-each stacked")
# Pick best from each sweep (will identify after)
# For now, test a few promising combos manually:
results["c1"] = avg_runs("combo: burstSL=$15 + max_burst=3 (best of T1/T2)", {"burst_sl_usd": 15, "max_burst": 3})
results["c2"] = avg_runs("combo: burstSL=$10 + max_burst=3", {"burst_sl_usd": 10, "max_burst": 3})
results["c3"] = avg_runs("combo: burstSL=$15 + trail 30/10", {"burst_sl_usd": 15, "trail_t": 30, "trail_d": 10})
results["c4"] = avg_runs("combo: burstSL=$10 + max_burst=3 + fearI=$80", {"burst_sl_usd": 10, "max_burst": 3, "fear_ideal": 80})

# Save final results
out_path = LAB_DIR / "recalibrate_results.json"
out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
print()
print(f"Saved full results to {out_path.name}")

# Print summary: best of each tier
print()
print("=" * 110)
print("BEST OF EACH TIER (sorted by total $ desc, secondary: chain_wr desc, tertiary: max_dd asc)")
print("=" * 110)
def rank_key(r): return (-r["total"], -r["chain_wr"], r["max_dd"])
for tier_label, tier_keys in [
    ("Baseline", ["baseline"]),
    ("T1 burstSL", [k for k in results if k.startswith("t1_")]),
    ("T2 max_burst", [k for k in results if k.startswith("t2_")]),
    ("T3 trail", [k for k in results if k.startswith("t3_")]),
    ("T4 tick_speed", [k for k in results if k.startswith("t4_")]),
    ("T5 spread", [k for k in results if k.startswith("t5_")]),
    ("T6 trigger_past", [k for k in results if k.startswith("t6_")]),
    ("T7 fearIdeal", [k for k in results if k.startswith("t7_")]),
    ("T8 effort", [k for k in results if k.startswith("t8_")]),
    ("T9 combos", [k for k in results if k.startswith("c")]),
]:
    if not tier_keys: continue
    sorted_tier = sorted([results[k] for k in tier_keys], key=rank_key)
    best = sorted_tier[0]
    print(f"  {tier_label:<18s}  BEST: {best['label']:<48s}  $={best['total']:+7.2f}  cWR={best['chain_wr']:.1f}%  DD=${best['max_dd']:+.0f}")
