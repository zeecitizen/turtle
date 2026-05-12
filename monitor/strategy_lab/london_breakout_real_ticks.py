"""London Breakout (Asian Range) on Blueberry real ticks — fast version.

Pre-builds per-day numpy arrays once, then iterates configs.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_london_breakout_results.json")

LOTS = 0.30
COMMISSION = 7.0 * LOTS

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

dt = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
df["date_str"] = dt.dt.strftime("%Y-%m-%d")
df["mins_utc"] = dt.dt.hour * 60 + dt.dt.minute

print("[INDEX] grouping ticks by day...", flush=True)
# Pre-build per-day arrays
day_data = {}
for date_str, sub in df.groupby("date_str", sort=True):
    day_data[date_str] = {
        "ts":   sub["time_msc"].to_numpy(),
        "bid":  sub["bid"].to_numpy(),
        "ask":  sub["ask"].to_numpy(),
        "mins": sub["mins_utc"].to_numpy(),
    }
print(f"[INDEX] {len(day_data)} days indexed", flush=True)

def simulate_day(d, asian_start_min, asian_end_min, london_start_min,
                 day_close_min, tp_mult, sl_mult, min_range_pts, max_range_pts,
                 use_pinbar_filter):
    mins = d["mins"]; bid = d["bid"]; ask = d["ask"]
    asian_mask = (mins >= asian_start_min) & (mins < asian_end_min)
    if asian_mask.sum() < 50: return None
    asian_bid = bid[asian_mask]
    a_high = float(asian_bid.max())
    a_low  = float(asian_bid.min())
    a_range = a_high - a_low
    range_pts = a_range * 100
    if range_pts < min_range_pts or range_pts > max_range_pts: return None

    london_mask = (mins >= london_start_min) & (mins < day_close_min)
    if london_mask.sum() < 50: return None
    london_idx = np.where(london_mask)[0]
    london_bid = bid[london_mask]
    london_ask = ask[london_mask]

    # Find first breakout
    above_high = london_bid > a_high
    below_low  = london_bid < a_low
    first_above = int(np.argmax(above_high)) if above_high.any() else len(london_bid)
    first_below = int(np.argmax(below_low))  if below_low.any()  else len(london_bid)
    if first_above >= len(london_bid) and first_below >= len(london_bid): return None
    if first_above < first_below:
        breakout_dir = 1; bo_local = first_above
        breakout_price = float(london_ask[bo_local])
    else:
        breakout_dir = -1; bo_local = first_below
        breakout_price = float(london_bid[bo_local])

    # Pin bar filter (5-min window after breakout)
    if use_pinbar_filter:
        # ~150 ticks ≈ 5 min on XAUUSD; use 200 for safety
        bo_end = min(bo_local + 200, len(london_bid))
        win_bid = london_bid[bo_local:bo_end]
        win_ask = london_ask[bo_local:bo_end]
        if breakout_dir == 1:
            if win_bid.min() < breakout_price - 0.5 * a_range: return None
        else:
            if win_ask.max() > breakout_price + 0.5 * a_range: return None

    # SL/TP
    sl_offset = sl_mult * a_range
    tp_offset = tp_mult * a_range
    if breakout_dir == 1:
        sl_price = breakout_price - sl_offset
        tp_price = breakout_price + tp_offset
    else:
        sl_price = breakout_price + sl_offset
        tp_price = breakout_price - tp_offset

    # Walk remaining london ticks for SL/TP/timeout
    rem_bid = london_bid[bo_local:]
    rem_ask = london_ask[bo_local:]
    if breakout_dir == 1:
        sl_hits = rem_bid <= sl_price
        tp_hits = rem_bid >= tp_price
    else:
        sl_hits = rem_ask >= sl_price
        tp_hits = rem_ask <= tp_price
    sl_first = int(np.argmax(sl_hits)) if sl_hits.any() else len(rem_bid)
    tp_first = int(np.argmax(tp_hits)) if tp_hits.any() else len(rem_bid)
    if tp_first < sl_first:
        exit_price = tp_price; exit_reason = "TP"
    elif sl_first < len(rem_bid):
        exit_price = sl_price; exit_reason = "SL"
    else:
        exit_price = float(rem_bid[-1]) if breakout_dir == 1 else float(rem_ask[-1])
        exit_reason = "TIME"

    pnl_pts = (exit_price - breakout_price) if breakout_dir == 1 else (breakout_price - exit_price)
    pnl_dollars = pnl_pts * 100 * LOTS - COMMISSION
    return {
        "side": "buy" if breakout_dir == 1 else "sell",
        "range_pts": round(range_pts, 1),
        "entry": round(breakout_price, 2),
        "sl": round(sl_price, 2), "tp": round(tp_price, 2),
        "exit": round(exit_price, 2), "exit_reason": exit_reason,
        "pnl": round(pnl_dollars, 2),
    }

def backtest(cfg):
    trades = []
    for date_str, d in day_data.items():
        result = simulate_day(d, **cfg)
        if result is None: continue
        result["date"] = date_str
        trades.append(result)
    return trades

def stats(trades):
    if not trades: return {"n": 0}
    arr = np.array([t["pnl"] for t in trades])
    wins = arr[arr > 0]; losses = arr[arr < 0]
    wr = 100.0 * len(wins) / len(trades)
    net = float(arr.sum())
    pf = float(wins.sum()) / float(-losses.sum()) if len(losses) and losses.sum() != 0 else None
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(trades), "wr": round(wr, 2), "net": round(net, 2),
            "pf": round(pf, 2) if pf else None, "max_dd": round(dd, 2),
            "avg": round(float(arr.mean()), 2)}

# === SWEEP ===
SWEEP = []
for asian_start, asian_end, london_start in [(0, 7*60, 7*60), (0, 5*60, 7*60), (0, 8*60, 8*60), (1*60, 7*60, 7*60)]:
    for tp_mult in [1.0, 1.5, 2.0, 2.5]:
        for sl_mult in [0.5, 0.75, 1.0]:
            for min_range_pts in [0, 100]:
                for max_range_pts in [500, 1000, 99999]:
                    for use_pinbar in [False, True]:
                        SWEEP.append({
                            "asian_start_min": asian_start, "asian_end_min": asian_end,
                            "london_start_min": london_start, "day_close_min": 21*60,
                            "tp_mult": tp_mult, "sl_mult": sl_mult,
                            "min_range_pts": min_range_pts, "max_range_pts": max_range_pts,
                            "use_pinbar_filter": use_pinbar,
                        })

print(f"[SWEEP] {len(SWEEP)} configs", flush=True)
results = []
import time; t0 = time.time()
for i, cfg in enumerate(SWEEP):
    trades = backtest(cfg)
    s = stats(trades)
    s.update(cfg)
    results.append(s)
    if (i+1) % 50 == 0: print(f"  done {i+1}/{len(SWEEP)}  ({time.time()-t0:.0f}s)", flush=True)

ok = [r for r in results if r.get("n", 0) >= 30]
ok.sort(key=lambda r: r["net"], reverse=True)
print(f"\n=== TOP 15 (n>=30) ===", flush=True)
print(f"{'asian':>9} {'ldn':>3} {'tp':>4} {'sl':>4} {'min':>4} {'max':>5} {'pin':>5} | {'n':>3} {'wr%':>5} {'pf':>5} {'net$':>9} {'dd':>7}", flush=True)
for r in ok[:15]:
    asn = f"{r['asian_start_min']//60:02d}-{r['asian_end_min']//60:02d}"
    ldn = f"{r['london_start_min']//60:02d}"
    print(f"{asn:>9} {ldn:>3} {r['tp_mult']:>4.1f} {r['sl_mult']:>4.2f} {r['min_range_pts']:>4} {r['max_range_pts']:>5} {str(r['use_pinbar_filter']):>5} | {r['n']:>3} {r['wr']:>5.1f} {str(r['pf']):>5} {r['net']:>9.2f} {r['max_dd']:>7.2f}", flush=True)

best = ok[0] if ok else None
print(f"\n=== BEST OVERALL ===", flush=True)
print(json.dumps(best, indent=2, default=str), flush=True)

result = {"started": datetime.now(timezone.utc).isoformat(), "best": best, "top15": ok[:15], "all_count": len(results)}
OUT_J.write_text(json.dumps(result, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
