"""Test UHV filter + Shano-style bursts on LB and NY breakout strategies.

UHV filter: only enter breakout if breakout candle had tick-volume in top X% of recent bars.
Burst pyramiding: when an open trade hits +$X profit, fire ANOTHER 0.30 lot same direction
                  with its own SL/TP. Stack up to N bursts per chain.

Tests:
  1. LB baseline (no UHV, no burst) - control
  2. LB + UHV
  3. LB + Burst (no UHV)
  4. LB + UHV + Burst
  5. Same for NY breakout
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_lb_ny_uhv_burst_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
dt = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
df["date_str"] = dt.dt.strftime("%Y-%m-%d")
df["mins_utc"] = dt.dt.hour * 60 + dt.dt.minute
df["m1_bucket"] = (df["time_msc"] // 60000).astype(np.int64)

# Pre-compute M1 bars with tick volume across full window
m1_grp = df.groupby("m1_bucket", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1_bucket")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date_str"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1_ts = m1_grp["ts_end_ms"].to_numpy()
m1_v = m1_grp["v"].to_numpy()
print(f"M1 bars: {len(m1_grp)}", flush=True)

# Per-day arrays
day_data = {}
for ds, sub in df.groupby("date_str", sort=True):
    day_data[ds] = {
        "bid": sub["bid"].to_numpy(), "ask": sub["ask"].to_numpy(),
        "mins": sub["mins_utc"].to_numpy(),
        "ts": sub["time_msc"].to_numpy(),
    }

def uhv_check(breakout_ts_ms, dir_sign, lookback_m1_bars=20, top_pct=0.30):
    """Check if breakout candle's M1 has tick-volume in top top_pct of last lookback bars.
    Returns True if UHV-confirmed (breakout has volume backing)."""
    idx = int(np.searchsorted(m1_ts, breakout_ts_ms, side="right")) - 1
    if idx < lookback_m1_bars + 1: return False  # not enough history
    bo_vol = m1_v[idx]
    lookback_vols = m1_v[idx - lookback_m1_bars:idx]
    if len(lookback_vols) == 0: return False
    threshold = np.percentile(lookback_vols, 100 * (1 - top_pct))
    return bo_vol >= threshold

def simulate_with_options(d, range_start, range_end, bo_start, day_close,
                           tp_mult, sl_mult, use_uhv=False, uhv_top_pct=0.30,
                           burst_triggers=None, max_bursts=0, burst_lots=LOTS):
    """Returns list of trades for this day (multiple if burst enabled)."""
    mins, bid, ask, ts = d["mins"], d["bid"], d["ask"], d["ts"]
    rm = (mins >= range_start) & (mins < range_end)
    if rm.sum() < 50: return []
    a_high = float(bid[rm].max()); a_low = float(bid[rm].min())
    a_range = a_high - a_low
    if a_range < 0.05: return []
    bm = (mins >= bo_start) & (mins < day_close)
    if bm.sum() < 50: return []
    bbid = bid[bm]; bask = ask[bm]; bts = ts[bm]
    above = bbid > a_high; below = bbid < a_low
    fa = int(np.argmax(above)) if above.any() else len(bbid)
    fb = int(np.argmax(below)) if below.any() else len(bbid)
    if fa >= len(bbid) and fb >= len(bbid): return []
    if fa < fb: bd = 1; bo = fa; bp = float(bask[bo])
    else:       bd = -1; bo = fb; bp = float(bbid[bo])
    bo_ts = int(bts[bo])

    # UHV filter
    if use_uhv:
        if not uhv_check(bo_ts, bd, lookback_m1_bars=20, top_pct=uhv_top_pct):
            return []  # blocked

    # Main trade
    sl = bp - sl_mult*a_range if bd == 1 else bp + sl_mult*a_range
    tp = bp + tp_mult*a_range if bd == 1 else bp - tp_mult*a_range
    rb = bbid[bo:]; ra = bask[bo:]; rts = bts[bo:]
    # Walk tick-by-tick to also capture burst triggers
    trades = []
    if bd == 1:
        running_pnl = (rb - bp) * CONTRACT_SIZE * LOTS
    else:
        running_pnl = (bp - ra) * CONTRACT_SIZE * LOTS
    sl_thresh = -abs(sl_mult * a_range) * CONTRACT_SIZE * LOTS
    tp_thresh = abs(tp_mult * a_range) * CONTRACT_SIZE * LOTS

    main_exit_idx = -1; main_exit_reason = None
    for i in range(len(running_pnl)):
        v = float(running_pnl[i])
        if v <= sl_thresh: main_exit_idx = i; main_exit_reason = "SL"; break
        if v >= tp_thresh: main_exit_idx = i; main_exit_reason = "TP"; break
    if main_exit_idx < 0:
        main_exit_idx = len(running_pnl) - 1
        main_exit_reason = "TIME"
    main_pnl = float(running_pnl[main_exit_idx]) - COMMISSION
    trades.append({"role": "main", "side": "buy" if bd == 1 else "sell",
                   "entry": bp, "exit_idx": main_exit_idx,
                   "exit_reason": main_exit_reason, "pnl": round(main_pnl, 2)})

    # Burst entries: at each trigger profit level, open a new same-direction trade
    if burst_triggers and max_bursts > 0:
        n_bursts = 0
        triggers_remaining = list(burst_triggers)
        for i in range(min(main_exit_idx, len(running_pnl) - 1)):
            v = float(running_pnl[i])
            if not triggers_remaining or n_bursts >= max_bursts: break
            next_trig = triggers_remaining[0]
            if v >= next_trig:
                # Fire a burst at this tick
                triggers_remaining.pop(0)
                burst_entry = float(ra[i]) if bd == 1 else float(rb[i])
                burst_sl = burst_entry - sl_mult*a_range if bd == 1 else burst_entry + sl_mult*a_range
                burst_tp = burst_entry + tp_mult*a_range if bd == 1 else burst_entry - tp_mult*a_range
                # Walk from i+1 to end of day for burst exit
                if bd == 1:
                    b_pnl_arr = (rb[i:] - burst_entry) * CONTRACT_SIZE * burst_lots
                else:
                    b_pnl_arr = (burst_entry - ra[i:]) * CONTRACT_SIZE * burst_lots
                b_sl_thresh = -abs(sl_mult * a_range) * CONTRACT_SIZE * burst_lots
                b_tp_thresh = abs(tp_mult * a_range) * CONTRACT_SIZE * burst_lots
                bex = -1; brs = None
                for j in range(len(b_pnl_arr)):
                    bv = float(b_pnl_arr[j])
                    if bv <= b_sl_thresh: bex = j; brs = "SL"; break
                    if bv >= b_tp_thresh: bex = j; brs = "TP"; break
                if bex < 0: bex = len(b_pnl_arr) - 1; brs = "TIME"
                burst_pnl = float(b_pnl_arr[bex]) - COMMISSION
                trades.append({"role": f"burst{n_bursts+1}", "side": "buy" if bd == 1 else "sell",
                               "entry": burst_entry, "exit_idx": bex,
                               "exit_reason": brs, "pnl": round(burst_pnl, 2)})
                n_bursts += 1
    return trades

def stats(daily_pnls):
    """daily_pnls: list of total daily P&L (one per day, summing all trades that day)."""
    if not daily_pnls: return {"n": 0}
    arr = np.array(daily_pnls)
    pos = arr[arr > 0]; neg = arr[arr < 0]
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n_days_traded": int((arr != 0).sum()),
            "win_days": int(len(pos)), "loss_days": int(len(neg)),
            "net": round(float(arr.sum()), 2),
            "avg_per_traded_day": round(float(arr[arr != 0].mean()), 2) if (arr != 0).any() else 0,
            "best_day": round(float(arr.max()), 2),
            "worst_day": round(float(arr.min()), 2),
            "max_dd": round(dd, 2),
            "sharpe": round(float(arr.mean() / arr.std()), 3) if arr.std() > 0 else 0,
            "total_trades": int(sum(1 for d in daily_pnls if d != 0)) if False else None,
            }

def run_backtest(label, range_start, range_end, bo_start, tp_mult, sl_mult,
                 use_uhv=False, uhv_top_pct=0.30,
                 burst_triggers=None, max_bursts=0):
    daily_totals = []
    n_trades = 0
    n_bursts_fired = 0
    for ds in sorted(day_data):
        trs = simulate_with_options(day_data[ds], range_start, range_end, bo_start,
                                     21*60, tp_mult, sl_mult, use_uhv, uhv_top_pct,
                                     burst_triggers, max_bursts)
        if not trs: continue
        n_trades += len(trs)
        n_bursts_fired += sum(1 for t in trs if t["role"].startswith("burst"))
        daily_totals.append(sum(t["pnl"] for t in trs))
    s = stats(daily_totals)
    s["n_trades"] = n_trades
    s["n_bursts"] = n_bursts_fired
    return label, s

def print_row(label, s):
    print(f"  {label:>30} | "
          f"days={s.get('n_days_traded', 0):>3} "
          f"wins={s.get('win_days', 0):>3}/{s.get('loss_days', 0):>3} "
          f"trades={s.get('n_trades', 0):>4} "
          f"bursts={s.get('n_bursts', 0):>3} | "
          f"net=${s.get('net', 0):>+9.2f} "
          f"avg=${s.get('avg_per_traded_day', 0):>+7.2f} "
          f"DD=${s.get('max_dd', 0):>7.2f} "
          f"sharpe={s.get('sharpe', 0):>5.3f}", flush=True)

# === LB SWEEP ===
print(f"\n=== LONDON BREAKOUT (Asian range 0-7 UTC, breakout from 7 UTC) ===", flush=True)
print(f"  {'config':>30} | days  win/loss  trades bursts | net   avg DD sharpe", flush=True)
results = {}

# Baseline
label, s = run_backtest("baseline (no UHV, no burst)", 0, 7*60, 7*60, 1.0, 1.0)
print_row(label, s); results["lb_baseline"] = s

# UHV variants
for top_pct in [0.20, 0.30, 0.50]:
    label, s = run_backtest(f"+ UHV (top {int(top_pct*100)}%)", 0, 7*60, 7*60, 1.0, 1.0,
                              use_uhv=True, uhv_top_pct=top_pct)
    print_row(label, s); results[f"lb_uhv_{int(top_pct*100)}"] = s

# Burst variants (no UHV)
for triggers, n_max in [
    ([300], 1), ([500], 1), ([300, 600], 2), ([200, 400, 800], 3),
]:
    label = f"+ burst @{triggers}"
    _, s = run_backtest(label, 0, 7*60, 7*60, 1.0, 1.0,
                         burst_triggers=triggers, max_bursts=n_max)
    print_row(label, s); results[f"lb_burst_{n_max}"] = s

# UHV + Burst combo
label, s = run_backtest("+ UHV(30%) + burst @[300,600]", 0, 7*60, 7*60, 1.0, 1.0,
                          use_uhv=True, uhv_top_pct=0.30,
                          burst_triggers=[300, 600], max_bursts=2)
print_row(label, s); results["lb_uhv_burst"] = s

# === NY SWEEP ===
print(f"\n=== NY BREAKOUT (range 0-13 UTC, breakout from 13 UTC) ===", flush=True)
print(f"  {'config':>30} | days  win/loss  trades bursts | net   avg DD sharpe", flush=True)

label, s = run_backtest("baseline", 0, 13*60, 13*60, 1.5, 1.0)
print_row(label, s); results["ny_baseline"] = s

for top_pct in [0.20, 0.30, 0.50]:
    label, s = run_backtest(f"+ UHV (top {int(top_pct*100)}%)", 0, 13*60, 13*60, 1.5, 1.0,
                              use_uhv=True, uhv_top_pct=top_pct)
    print_row(label, s); results[f"ny_uhv_{int(top_pct*100)}"] = s

for triggers, n_max in [([300], 1), ([500], 1), ([300, 600], 2), ([200, 400, 800], 3)]:
    label = f"+ burst @{triggers}"
    _, s = run_backtest(label, 0, 13*60, 13*60, 1.5, 1.0,
                         burst_triggers=triggers, max_bursts=n_max)
    print_row(label, s); results[f"ny_burst_{n_max}"] = s

label, s = run_backtest("+ UHV(30%) + burst @[300,600]", 0, 13*60, 13*60, 1.5, 1.0,
                          use_uhv=True, uhv_top_pct=0.30,
                          burst_triggers=[300, 600], max_bursts=2)
print_row(label, s); results["ny_uhv_burst"] = s

# Save
doc = {"started": datetime.now(timezone.utc).isoformat(), "results": results}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
