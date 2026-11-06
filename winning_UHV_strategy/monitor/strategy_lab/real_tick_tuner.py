"""Sequential filter tuner on Blueberry real-tick data.

Workflow:
  1. Load ticks + build M5 bars (cached)
  2. For each filter in TUNE_ORDER:
     - Sweep candidate values, hold others at current baseline
     - Print comparison table (n / WR / net / PF / DD)
     - Pick winner by SCORE function
     - Update baseline
  3. Print final stacked baseline + delta vs starting point

Output: monitor/strategy_lab/_real_tick_tuning_results.json
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json, sys

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_tuning_results.json")

# # ---strategy constants (not tuned) ---
M5_SECONDS = 300
CONTRACT_SIZE = 100
PROBE_LOT = 0.01
MAIN_LOT  = 0.40
COMMISSION_PER_LOT_RT = 7.0   # $/lot round-trip — Blueberry ~$7 typical
PROBE_COMM = COMMISSION_PER_LOT_RT * PROBE_LOT
MAIN_COMM  = COMMISSION_PER_LOT_RT * MAIN_LOT
MAIN_HOLD_CAP_S = 3600        # max main-hold; mirrors fearIdeal-ish exit

# Score function: prioritize profit + WR, penalize drawdown
def score(stats):
    if stats["n"] == 0: return -1e9
    return stats["net_pnl"] - 0.5 * stats["max_dd"]

# # ---data load (once) ---
print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)

# M5 bars on bid
df["m5_bucket"] = (df["time_msc"] // (M5_SECONDS * 1000)).astype(np.int64)
bars_full = df.groupby("m5_bucket", sort=True).agg(
    open=("bid", "first"), high=("bid", "max"), low=("bid", "min"),
    close=("bid", "last"), n=("bid", "count"),
    ts_start_ms=("time_msc", "first"), ts_end_ms=("time_msc", "last"),
).reset_index()
bars_full["body"] = (bars_full["close"] - bars_full["open"]).abs()
bars_full["dir"]  = np.sign(bars_full["close"] - bars_full["open"]).astype(int)
print(f"[BARS] {len(bars_full):,} M5 bars built", flush=True)

# Hour-of-day for session filter (UTC)
bars_full["hour_utc"] = pd.to_datetime(bars_full["ts_end_ms"], unit="ms", utc=True).dt.hour

# # ---signal detection (depends on BIG_RATIO) ---
def detect_signals(big_ratio: float):
    body = bars_full["body"].to_numpy()
    direction = bars_full["dir"].to_numpy()
    n = len(body)
    big_prev_arr = np.zeros(n, dtype=bool)
    big_prev_arr[2:] = body[1:-1] > big_ratio * body[:-2]
    dir_prev = np.roll(direction, 1)
    sig_buy  = big_prev_arr & (dir_prev == 1) & (direction == 1)
    sig_sell = big_prev_arr & (dir_prev == -1) & (direction == -1)
    sig_buy[:2] = False; sig_sell[:2] = False
    return sig_buy, sig_sell

def precompute_signals(big_ratio, hours_block=None, max_spread_pts=None):
    sig_buy, sig_sell = detect_signals(big_ratio)
    sigs = []
    for i in np.where(sig_buy)[0]:
        sigs.append((int(bars_full.iloc[i]["ts_end_ms"]), "buy", int(bars_full.iloc[i]["hour_utc"])))
    for i in np.where(sig_sell)[0]:
        sigs.append((int(bars_full.iloc[i]["ts_end_ms"]), "sell", int(bars_full.iloc[i]["hour_utc"])))
    sigs.sort()
    if hours_block:
        sigs = [s for s in sigs if s[2] not in hours_block]
    return sigs

# # ---per-signal window precomputation ---
# For each signal, precompute the full pnl trajectory through the maximum probe window
# and (if confirmed under any config) the main window. We'll evaluate different thresholds
# against these precomputed arrays.
def find_idx(t_ms):
    return int(np.searchsorted(ts, t_ms, side="right"))

def simulate(big_ratio, probe_confirm, probe_fail, probe_timeout_s,
             main_tp, main_sl,
             hours_block=None, max_spread_pts=None,
             post_loss_cooldown_min=0, daily_cap_loss=None):
    sigs = precompute_signals(big_ratio, hours_block=hours_block)
    trades = []
    last_loss_ts = -1
    daily_pnl = {}
    for (sig_ts, side, hour_utc) in sigs:
        if post_loss_cooldown_min > 0 and last_loss_ts > 0:
            if (sig_ts - last_loss_ts) / 1000.0 / 60.0 < post_loss_cooldown_min:
                continue
        date_key = datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if daily_cap_loss is not None and daily_pnl.get(date_key, 0) <= -abs(daily_cap_loss):
            continue
        pi = find_idx(sig_ts)
        if pi >= len(ts): continue
        if max_spread_pts is not None:
            spread_pts_now = (asks[pi] - bids[pi]) * 100
            if spread_pts_now > max_spread_pts: continue
        p_entry_ts = ts[pi]
        p_entry = asks[pi] if side == "buy" else bids[pi]

        timeout_ts = p_entry_ts + probe_timeout_s * 1000
        end_idx = find_idx(timeout_ts)
        if end_idx <= pi: continue
        if side == "buy":
            pnl_arr = (bids[pi:end_idx] - p_entry) * CONTRACT_SIZE * PROBE_LOT
        else:
            pnl_arr = (p_entry - asks[pi:end_idx]) * CONTRACT_SIZE * PROBE_LOT
        sub_ts = ts[pi:end_idx]

        confirm_mask = pnl_arr >= probe_confirm
        fail_mask    = pnl_arr <= probe_fail
        c_idx = int(np.argmax(confirm_mask)) if confirm_mask.any() else -1
        f_idx = int(np.argmax(fail_mask))    if fail_mask.any() else -1
        if c_idx >= 0 and (f_idx < 0 or c_idx <= f_idx):
            outcome = "confirm"; exit_idx_local = c_idx
        elif f_idx >= 0:
            outcome = "fail"; exit_idx_local = f_idx
        else:
            outcome = "timeout"; exit_idx_local = len(pnl_arr) - 1
        probe_pnl = float(pnl_arr[exit_idx_local])
        probe_exit_ts = int(sub_ts[exit_idx_local])

        total = probe_pnl - PROBE_COMM

        if outcome == "confirm":
            mi = find_idx(probe_exit_ts)
            if mi >= len(ts):
                pass
            else:
                m_entry = asks[mi] if side == "buy" else bids[mi]
                main_cap_ts = ts[mi] + MAIN_HOLD_CAP_S * 1000
                end_idx2 = find_idx(main_cap_ts)
                if end_idx2 > mi:
                    if side == "buy":
                        m_pnl_arr = (bids[mi:end_idx2] - m_entry) * CONTRACT_SIZE * MAIN_LOT
                    else:
                        m_pnl_arr = (m_entry - asks[mi:end_idx2]) * CONTRACT_SIZE * MAIN_LOT
                    tp_mask = m_pnl_arr >= main_tp
                    sl_mask = m_pnl_arr <= -abs(main_sl)
                    tp_idx = int(np.argmax(tp_mask)) if tp_mask.any() else -1
                    sl_idx = int(np.argmax(sl_mask)) if sl_mask.any() else -1
                    if tp_idx >= 0 and (sl_idx < 0 or tp_idx <= sl_idx):
                        m_realized = float(m_pnl_arr[tp_idx])
                    elif sl_idx >= 0:
                        m_realized = float(m_pnl_arr[sl_idx])
                    else:
                        m_realized = float(m_pnl_arr[-1])
                    total += (m_realized - MAIN_COMM)

        trades.append((sig_ts, side, outcome, probe_pnl, total))
        if total < 0:
            last_loss_ts = sig_ts
        daily_pnl[date_key] = daily_pnl.get(date_key, 0) + total

    if not trades:
        return {"n": 0, "wr": 0, "wins": 0, "losses": 0, "net_pnl": 0, "pf": 0, "max_dd": 0,
                "avg_pnl": 0, "n_confirmed": 0, "wr_confirmed": 0, "best": 0, "worst": 0}
    arr = np.array([t[4] for t in trades])
    wins = (arr > 0).sum(); losses = (arr < 0).sum()
    gross_w = arr[arr > 0].sum(); gross_l = -arr[arr < 0].sum()
    eq = arr.cumsum()
    dd = float((np.maximum.accumulate(eq) - eq).max())
    confirmed = [t for t in trades if t[2] == "confirm"]
    conf_arr = np.array([t[4] for t in confirmed]) if confirmed else np.array([])
    return {
        "n": len(trades),
        "wr": round(wins / len(trades) * 100, 2),
        "wins": int(wins), "losses": int(losses),
        "net_pnl": round(float(arr.sum()), 2),
        "avg_pnl": round(float(arr.mean()), 3),
        "pf": round(float(gross_w / gross_l), 2) if gross_l > 0 else None,
        "max_dd": round(dd, 2),
        "best": round(float(arr.max()), 2),
        "worst": round(float(arr.min()), 2),
        "n_confirmed": len(confirmed),
        "wr_confirmed": round((conf_arr > 0).sum() / len(confirmed) * 100, 2) if confirmed else 0,
    }

# # ---tune one filter at a time ---
def tune_param(label, current_value, sweep, baseline, key):
    rows = []
    print(f"\n=== TUNING {label} (current={current_value}) ===", flush=True)
    print(f"{'value':>12} | {'n':>5} | {'WR%':>6} | {'net':>10} | {'PF':>5} | {'DD':>9} | {'avg':>7} | score", flush=True)
    print("-" * 88, flush=True)
    best_score = None; best_val = None; best_stats = None
    for v in sweep:
        cfg = dict(baseline)
        cfg[key] = v
        s = simulate(**cfg)
        sc = score(s)
        marker = ""
        rows.append({"value": v, **s, "score": round(sc, 2)})
        print(f"{str(v):>12} | {s['n']:>5} | {s['wr']:>6.2f} | {s['net_pnl']:>10.2f} | {str(s['pf']):>5} | {s['max_dd']:>9.2f} | {s['avg_pnl']:>7.3f} | {sc:>9.2f}", flush=True)
        if best_score is None or sc > best_score:
            best_score = sc; best_val = v; best_stats = s
    print(f"  -> BEST: {label}={best_val} | net=${best_stats['net_pnl']} | WR={best_stats['wr']}% | PF={best_stats['pf']}", flush=True)
    return best_val, rows, best_stats

# # ---tuning sequence ---
baseline = {
    "big_ratio": 1.5,
    "probe_confirm": 0.58,
    "probe_fail": -3.0,
    "probe_timeout_s": 50,
    "main_tp": 10.0,
    "main_sl": 10.0,
    "hours_block": None,
    "max_spread_pts": None,
    "post_loss_cooldown_min": 0,
    "daily_cap_loss": None,
}

print("\n[BASELINE] running starting config...", flush=True)
start_stats = simulate(**baseline)
print(f"  baseline: n={start_stats['n']} WR={start_stats['wr']}% net=${start_stats['net_pnl']} PF={start_stats['pf']} DD=${start_stats['max_dd']}", flush=True)

results = {"started": datetime.now(timezone.utc).isoformat(), "starting_baseline": dict(baseline), "starting_stats": start_stats, "tunes": {}}

TUNE_PLAN = [
    ("BIG_RATIO",       "big_ratio",       [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.8, 2.0, 2.5, 3.0]),
    ("PROBE_CONFIRM",   "probe_confirm",   [0.20, 0.30, 0.45, 0.58, 0.75, 1.00, 1.50, 2.00, 3.00]),
    ("PROBE_FAIL",      "probe_fail",      [-0.50, -1.0, -2.0, -3.0, -5.0, -10.0, -20.0]),
    ("PROBE_TIMEOUT_S", "probe_timeout_s", [10, 20, 30, 50, 75, 100, 180, 300]),
    ("MAIN_TP",         "main_tp",         [3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 50.0, 80.0]),
    ("MAIN_SL",         "main_sl",         [3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 50.0, 80.0]),
]

for label, key, sweep in TUNE_PLAN:
    best_val, rows, best_stats = tune_param(label, baseline[key], sweep, baseline, key)
    baseline[key] = best_val
    results["tunes"][label] = {"best": best_val, "table": rows, "post_stats": best_stats}

print("\n=== FINAL STACKED BASELINE ===", flush=True)
final_stats = simulate(**baseline)
print(json.dumps(baseline, indent=2, default=str), flush=True)
print(f"  net=${final_stats['net_pnl']} WR={final_stats['wr']}% PF={final_stats['pf']} DD=${final_stats['max_dd']}", flush=True)
print(f"  delta vs starting: ${final_stats['net_pnl'] - start_stats['net_pnl']:+.2f} | WR Δ {final_stats['wr'] - start_stats['wr']:+.2f}%", flush=True)
results["final_baseline"] = dict(baseline)
results["final_stats"] = final_stats

OUT_J.write_text(json.dumps(results, indent=2, default=str))
print(f"\n[DONE] results → {OUT_J}", flush=True)
