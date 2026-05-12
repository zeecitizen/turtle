"""London Breakout with PEAK-TRAIL exit option — does Zee's hypothesis improve LB?
Adds a runtime peak-tracking trail: once peak >= trigger, close on drop of `drop` from peak.
Tests if early profit-booking improves LB's PF/net beyond the validated 1:1 R:R config."""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_lb_peaktrail_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
dt = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
df["date_str"] = dt.dt.strftime("%Y-%m-%d")
df["mins_utc"] = dt.dt.hour * 60 + dt.dt.minute

day_data = {}
for date_str, sub in df.groupby("date_str", sort=True):
    day_data[date_str] = {
        "bid": sub["bid"].to_numpy(), "ask": sub["ask"].to_numpy(),
        "mins": sub["mins_utc"].to_numpy(),
    }

def simulate_day(d, asian_start, asian_end, london_start, day_close,
                 tp_mult, sl_mult, peak_trigger=None, peak_drop=None):
    mins, bid, ask = d["mins"], d["bid"], d["ask"]
    am = (mins >= asian_start) & (mins < asian_end)
    if am.sum() < 50: return None
    a_high = float(bid[am].max()); a_low = float(bid[am].min())
    a_range = a_high - a_low
    if a_range < 0.05: return None
    lm = (mins >= london_start) & (mins < day_close)
    if lm.sum() < 50: return None
    lbid = bid[lm]; lask = ask[lm]
    above = lbid > a_high; below = lbid < a_low
    fa = int(np.argmax(above)) if above.any() else len(lbid)
    fb = int(np.argmax(below)) if below.any() else len(lbid)
    if fa >= len(lbid) and fb >= len(lbid): return None
    if fa < fb:
        bd = 1; bo = fa; bp = float(lask[bo])
    else:
        bd = -1; bo = fb; bp = float(lbid[bo])
    sl = bp - sl_mult*a_range if bd == 1 else bp + sl_mult*a_range
    tp = bp + tp_mult*a_range if bd == 1 else bp - tp_mult*a_range
    rb = lbid[bo:]; ra = lask[bo:]
    # Walk tick-by-tick to support peak-trail
    if bd == 1:
        running_pnl = (rb - bp) * CONTRACT_SIZE * LOTS
    else:
        running_pnl = (bp - ra) * CONTRACT_SIZE * LOTS
    sl_pnl_thresh = -abs(sl_mult * a_range) * CONTRACT_SIZE * LOTS
    tp_pnl_thresh = abs(tp_mult * a_range) * CONTRACT_SIZE * LOTS
    peak = -1e9
    exit_idx = -1; exit_reason = None
    for i in range(len(running_pnl)):
        v = float(running_pnl[i])
        if v > peak: peak = v
        # Hard SL/TP (the baseline checks)
        if v <= sl_pnl_thresh:
            exit_idx = i; exit_reason = "SL"; break
        if v >= tp_pnl_thresh:
            exit_idx = i; exit_reason = "TP"; break
        # Peak-trail
        if peak_trigger is not None and peak >= peak_trigger and (peak - v) >= peak_drop:
            exit_idx = i; exit_reason = "PEAK_TRAIL"; break
    if exit_idx < 0:
        exit_idx = len(running_pnl) - 1
        exit_reason = "TIME"
    pnl = float(running_pnl[exit_idx]) - COMMISSION
    return {"side": "buy" if bd == 1 else "sell", "range_pts": round(a_range*100, 1),
            "entry": round(bp, 2), "exit_idx": exit_idx, "exit_reason": exit_reason,
            "pnl": round(pnl, 2), "peak": round(peak, 2), "lifetime_ticks": exit_idx + 1}

def backtest(cfg):
    trades = []
    for date_str, d in day_data.items():
        r = simulate_day(d, **cfg)
        if r: r["date"] = date_str; trades.append(r)
    return trades

def stats(trades):
    if not trades: return {"n": 0}
    arr = np.array([t["pnl"] for t in trades])
    wins = arr[arr > 0]; losses = arr[arr < 0]
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(arr), "wr": round(100*len(wins)/len(arr),2),
            "pf": round(float(wins.sum()/-losses.sum()),2) if len(losses) and losses.sum() else None,
            "net": round(float(arr.sum()),2), "avg": round(float(arr.mean()),2),
            "max_dd": round(dd, 2)}

# === Baseline: no peak-trail (validated config) ===
BASE = {"asian_start": 0, "asian_end": 7*60, "london_start": 7*60,
        "day_close": 21*60, "tp_mult": 1.0, "sl_mult": 1.0,
        "peak_trigger": None, "peak_drop": None}
print("\n[BASELINE] no peak-trail", flush=True)
b_trades = backtest(BASE)
b_stats = stats(b_trades)
print(f"  {b_stats}", flush=True)

# === Peak-trail variants ===
print("\n=== PEAK-TRAIL VARIANTS (n>=30) ===", flush=True)
print(f"{'trigger':>7} {'drop':>4} | {'n':>3} {'wr%':>5} {'pf':>5} {'net$':>9} {'dd':>8} {'delta_vs_base':>13}", flush=True)
results = [{"variant": "baseline", "trigger": None, "drop": None, **b_stats}]
for trig in [3, 5, 8, 10, 15, 20, 30, 50, 100]:
    for drop in [1, 2, 5, 10, 20]:
        if drop >= trig: continue
        cfg = {**BASE, "peak_trigger": trig, "peak_drop": drop}
        trades = backtest(cfg)
        s = stats(trades)
        delta = s["net"] - b_stats["net"]
        results.append({"variant": f"trail T={trig}/${drop}", "trigger": trig, "drop": drop, **s})
        marker = " ⭐" if s["net"] > b_stats["net"] else ""
        print(f"{trig:>7} {drop:>4} | {s['n']:>3} {s['wr']:>5.1f} {str(s['pf']):>5} {s['net']:>9.2f} {s['max_dd']:>8.2f} {delta:>+12.2f}{marker}", flush=True)

# Train/test split on best variant
best = max((r for r in results if r["n"] >= 30), key=lambda r: r["net"])
print(f"\n=== BEST: {best.get('variant', '?')} ===", flush=True)
print(json.dumps(best, indent=2, default=str), flush=True)

# Train/test
print(f"\n=== TRAIN/TEST on best ===", flush=True)
if best["variant"] != "baseline":
    cfg = {**BASE, "peak_trigger": best["trigger"], "peak_drop": best["drop"]}
else:
    cfg = BASE
trades = backtest(cfg)
all_dates = sorted(set(t["date"] for t in trades))
cutoff = all_dates[int(len(all_dates) * 0.75)]
trn = [t for t in trades if t["date"] < cutoff]
tst = [t for t in trades if t["date"] >= cutoff]
print(f"  Train ({len(trn)} trades, cutoff {cutoff}): {stats(trn)}", flush=True)
print(f"  Test  ({len(tst)} trades): {stats(tst)}", flush=True)

doc = {"started": datetime.now(timezone.utc).isoformat(), "baseline": b_stats,
       "results": results, "best": best,
       "train_test": {"cutoff": cutoff, "train": stats(trn), "test": stats(tst)}}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
