"""Turtle Trader Desk optimized settings — yesterday tick replay.
Tests TWO modes:
  A) PINE-SIM (idealized): fill EXACTLY at trigger price (level - $1) — what chart shows
  B) REALISTIC: fill at next tick after bar-close confirmation — what PineConnector actually does

Settings (from screenshots):
  - UHV detection: highest-volume bar in last 20 bars (no filters)
  - Pre-breakout offset = $1
  - SL = 15 pips ($1.50), TP varies
  - Kill timer = 5s
  - Invalidation: UHV midpoint cross (+ 0.3 tolerance)
  - Min spacing: 5 minutes
  - Lots = 0.4
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_turtle_optimized_results.json")
LOTS = 0.4
COMMISSION = 7.0 * LOTS
CONTRACT_SIZE = 100
PIP = 0.10

print("[LOAD]...", flush=True)
df_full = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df_full["time_msc"].max())
target_date_str = datetime.fromtimestamp(last_msc/1000, tz=timezone.utc).strftime("%Y-%m-%d")
print(f"Target day: {target_date_str}", flush=True)

df_full["m1"] = (df_full["time_msc"] // 60_000).astype(np.int64)
m1_grp = df_full.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1 = m1_grp.to_dict("records")

ts_arr = df_full["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df_full["bid"].to_numpy(dtype=np.float64)
asks_arr = df_full["ask"].to_numpy(dtype=np.float64)

yesterday_indices = [i for i, b in enumerate(m1) if b["date"] == target_date_str]
print(f"Yesterday M1 bars: {len(yesterday_indices)}", flush=True)

P = {"uhv_lookback_bars": 20, "max_bars_after_uhv": 10, "pre_breakout_offset": 1.0,
     "min_minutes_between": 5, "uhv_midpoint_tol": 0.3}

def is_red(b): return b["c"] < b["o"]
def is_green(b): return b["c"] > b["o"]

def find_uhv(idx):
    if idx < P["uhv_lookback_bars"] + 5: return None
    win = list(range(idx - P["uhv_lookback_bars"], idx))
    uhv_idx = max(win, key=lambda j: m1[j]["v"])
    if m1[uhv_idx]["v"] == 0 or uhv_idx >= idx: return None
    if (idx - uhv_idx) > P["max_bars_after_uhv"]: return None
    return uhv_idx, m1[uhv_idx]

def walk_exit(entry_ts, entry_price, side, uhv_mid, tp_pips, sl_pips, kill_sec, end_idx_max):
    """Walk ticks from entry_ts forward, return exit info."""
    tp_dist = tp_pips * PIP; sl_dist = sl_pips * PIP
    i0 = int(np.searchsorted(ts_arr, entry_ts, side="left"))
    i1 = min(end_idx_max, int(np.searchsorted(ts_arr, entry_ts + 30*60*1000, side="right")))
    for k in range(i0, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_price_pnl = bids_arr[k] - entry_price
            exit_price = bids_arr[k]
        else:
            cur_price_pnl = entry_price - asks_arr[k]
            exit_price = asks_arr[k]
        cur_usd = cur_price_pnl * CONTRACT_SIZE * LOTS
        if cur_price_pnl >= tp_dist:
            return {"pnl_usd": cur_usd - COMMISSION, "exit_price": exit_price, "reason": "TP", "elapsed_s": elapsed}
        if cur_price_pnl <= -sl_dist:
            return {"pnl_usd": cur_usd - COMMISSION, "exit_price": exit_price, "reason": "SL", "elapsed_s": elapsed}
        if elapsed >= kill_sec:
            return {"pnl_usd": cur_usd - COMMISSION, "exit_price": exit_price, "reason": "KILL", "elapsed_s": elapsed}
        if side == "buy" and bids_arr[k] < uhv_mid - P["uhv_midpoint_tol"]:
            return {"pnl_usd": cur_usd - COMMISSION, "exit_price": exit_price, "reason": "INVALID", "elapsed_s": elapsed}
        if side == "sell" and asks_arr[k] > uhv_mid + P["uhv_midpoint_tol"]:
            return {"pnl_usd": cur_usd - COMMISSION, "exit_price": exit_price, "reason": "INVALID", "elapsed_s": elapsed}
    return None

def run_pine_sim(tp_pips, sl_pips, kill_sec):
    """MODE A: Idealized — fill at trigger price = level - pre_off. What Pine sim shows."""
    trades = []; last_entry_ms = 0
    y_start, y_end = yesterday_indices[0], yesterday_indices[-1]
    for idx in range(max(y_start, P["uhv_lookback_bars"] + 5), y_end + 1):
        uhv_result = find_uhv(idx)
        if not uhv_result: continue
        uhv_idx, uhv = uhv_result
        cur = m1[idx]
        if is_red(uhv) and cur["c"] > uhv["h"]:
            side = "buy"; level = uhv["h"]
        elif is_green(uhv) and cur["c"] < uhv["l"]:
            side = "sell"; level = uhv["l"]
        else: continue
        if cur["ts_end_ms"] - last_entry_ms < P["min_minutes_between"] * 60 * 1000: continue
        # IDEALIZED FILL: at trigger price
        trigger = level - P["pre_breakout_offset"] if side == "buy" else level + P["pre_breakout_offset"]
        entry_ts = int(cur["ts_end_ms"])
        entry_price = trigger  # idealized — we get exactly the trigger price
        uhv_mid = (uhv["h"] + uhv["l"]) / 2
        i_max = len(ts_arr)
        result = walk_exit(entry_ts, entry_price, side, uhv_mid, tp_pips, sl_pips, kill_sec, i_max)
        if not result: continue
        result.update({"time": pd.to_datetime(entry_ts, unit="ms", utc=True).strftime("%H:%M:%S"),
                       "side": side, "entry": round(entry_price, 2),
                       "uhv_h": round(uhv["h"], 2), "uhv_l": round(uhv["l"], 2),
                       "level": round(level, 2)})
        trades.append(result); last_entry_ms = cur["ts_end_ms"]
    return trades

def run_realistic(tp_pips, sl_pips, kill_sec):
    """MODE B: Realistic — alert fires at bar close, fill at next tick ASK/BID."""
    trades = []; last_entry_ms = 0
    y_start, y_end = yesterday_indices[0], yesterday_indices[-1]
    for idx in range(max(y_start, P["uhv_lookback_bars"] + 5), y_end + 1):
        uhv_result = find_uhv(idx)
        if not uhv_result: continue
        uhv_idx, uhv = uhv_result
        cur = m1[idx]
        if is_red(uhv) and cur["c"] > uhv["h"]:
            side = "buy"; level = uhv["h"]
        elif is_green(uhv) and cur["c"] < uhv["l"]:
            side = "sell"; level = uhv["l"]
        else: continue
        if cur["ts_end_ms"] - last_entry_ms < P["min_minutes_between"] * 60 * 1000: continue
        entry_ts = int(cur["ts_end_ms"])
        # REALISTIC FILL: first tick AFTER bar close, fill at ASK (buy) or BID (sell)
        i_after = int(np.searchsorted(ts_arr, entry_ts, side="right"))
        if i_after >= len(ts_arr): continue
        entry_price = asks_arr[i_after] if side == "buy" else bids_arr[i_after]
        actual_entry_ts = int(ts_arr[i_after])
        uhv_mid = (uhv["h"] + uhv["l"]) / 2
        result = walk_exit(actual_entry_ts, entry_price, side, uhv_mid, tp_pips, sl_pips, kill_sec, len(ts_arr))
        if not result: continue
        result.update({"time": pd.to_datetime(entry_ts, unit="ms", utc=True).strftime("%H:%M:%S"),
                       "side": side, "entry": round(entry_price, 2),
                       "level": round(level, 2),
                       "slippage": round(entry_price - level if side == "buy" else level - entry_price, 2)})
        trades.append(result); last_entry_ms = cur["ts_end_ms"]
    return trades

def report(trades, label):
    print(f"\n=== {label} ===", flush=True)
    if not trades: print("  No signals"); return
    n = len(trades); wins = sum(1 for t in trades if t["pnl_usd"] > 0)
    losses = sum(1 for t in trades if t["pnl_usd"] < 0)
    net = sum(t["pnl_usd"] for t in trades)
    by_reason = {}
    for t in trades:
        by_reason[t["reason"]] = by_reason.get(t["reason"], 0) + 1
    print(f"  n={n}  WR={wins/n*100:.1f}% ({wins}W/{losses}L)  Net: ${net:+.2f}  By reason: {by_reason}", flush=True)

print(f"\n{'='*100}\n  PINE-SIM (idealized — fill at trigger price exactly)\n{'='*100}", flush=True)
configs = [
    {"tp": 3, "sl": 15, "kill": 5, "label": "TP=3 SL=15 kill=5s"},
    {"tp": 5, "sl": 15, "kill": 5, "label": "TP=5 SL=15 kill=5s"},
    {"tp": 3, "sl": 15, "kill": 10, "label": "TP=3 SL=15 kill=10s"},
    {"tp": 8, "sl": 15, "kill": 10, "label": "TP=8 SL=15 kill=10s"},
]
pine_results = {}
for cfg in configs:
    trades = run_pine_sim(cfg["tp"], cfg["sl"], cfg["kill"])
    report(trades, f"PINE-SIM  {cfg['label']}")
    pine_results[cfg["label"]] = trades

print(f"\n{'='*100}\n  REALISTIC (fill at next tick after bar close — what PineConnector does)\n{'='*100}", flush=True)
real_results = {}
for cfg in configs:
    trades = run_realistic(cfg["tp"], cfg["sl"], cfg["kill"])
    report(trades, f"REALISTIC  {cfg['label']}")
    real_results[cfg["label"]] = trades

# Show slippage analysis for realistic mode
print(f"\n{'='*100}\n  SLIPPAGE: difference between idealized and realistic entries\n{'='*100}", flush=True)
real_trades = real_results["TP=3 SL=15 kill=5s"]
slips = [t["slippage"] for t in real_trades]
if slips:
    print(f"  N trades: {len(slips)}", flush=True)
    print(f"  Avg slippage: ${np.mean(slips):+.2f}  Median: ${np.median(slips):+.2f}", flush=True)
    print(f"  Max slippage: ${max(slips):+.2f}  Min: ${min(slips):+.2f}", flush=True)
    print(f"  Slips > $0.50: {sum(1 for s in slips if s > 0.5)}/{len(slips)}", flush=True)
    print(f"  Slips > $1.00: {sum(1 for s in slips if s > 1.0)}/{len(slips)}", flush=True)
    print(f"  Slips > $2.00: {sum(1 for s in slips if s > 2.0)}/{len(slips)}", flush=True)

doc = {"started": datetime.now(timezone.utc).isoformat(),
       "target_date": target_date_str, "pine_sim": pine_results, "realistic": real_results}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
