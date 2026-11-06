"""Fix B test: gate the 2nd-bar direction by a minimum body distance.

Current detection: `sig = big_prev & dir_prev_match & current_dir_match`
  where current_dir_match = sign(close - open) matches.

Fix B:                  `sig = big_prev & dir_prev_match & (curr_body_signed >= min_body_2nd in dir)`
  i.e., 2nd bar must move at least min_body_2nd points in the prev direction.

Sweep: 0, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0, 2.0, 3.0, 5.0
On top of phase-2 winning baseline (the +$88 config).
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE  = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
PHASE2 = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_filter_results.json")
OUT_J  = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_minbody_results.json")

M5_SECONDS = 300
CONTRACT_SIZE = 100
PROBE_LOT = 0.01
MAIN_LOT  = 0.40
COMMISSION = 7.0
PROBE_COMM = COMMISSION * PROBE_LOT
MAIN_COMM  = COMMISSION * MAIN_LOT
MAIN_HOLD_CAP_S = 3600

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)
ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)

df["m5_bucket"] = (df["time_msc"] // (M5_SECONDS * 1000)).astype(np.int64)
bars_full = df.groupby("m5_bucket", sort=True).agg(
    open=("bid","first"), close=("bid","last"),
    ts_end_ms=("time_msc","last"),
).reset_index()
bars_full["body"]   = (bars_full["close"] - bars_full["open"]).abs()
bars_full["signed"] = (bars_full["close"] - bars_full["open"])
bars_full["dir"]    = np.sign(bars_full["signed"]).astype(int)
bars_full["hour_utc"] = pd.to_datetime(bars_full["ts_end_ms"], unit="ms", utc=True).dt.hour
print(f"[BARS] {len(bars_full):,} M5 bars", flush=True)

def detect(big_ratio, min_body_2nd):
    body   = bars_full["body"].to_numpy()
    signed = bars_full["signed"].to_numpy()
    direction = bars_full["dir"].to_numpy()
    n = len(body)
    big_prev = np.zeros(n, dtype=bool)
    big_prev[2:] = body[1:-1] > big_ratio * body[:-2]
    dir_prev = np.roll(direction, 1)
    if min_body_2nd > 0:
        sig_buy  = big_prev & (dir_prev == 1)  & (signed >=  min_body_2nd)
        sig_sell = big_prev & (dir_prev == -1) & (signed <= -min_body_2nd)
    else:
        sig_buy  = big_prev & (dir_prev == 1)  & (direction == 1)
        sig_sell = big_prev & (dir_prev == -1) & (direction == -1)
    sig_buy[:2] = False; sig_sell[:2] = False
    return sig_buy, sig_sell

def find_idx(t_ms):
    return int(np.searchsorted(ts, t_ms, side="right"))

def simulate(big_ratio, probe_confirm, probe_fail, probe_timeout_s,
             main_tp, main_sl, min_body_2nd=0.0,
             hours_block=None, max_spread_pts=None,
             post_loss_cooldown_min=0, daily_cap_loss=None):
    sb, ss = detect(big_ratio, min_body_2nd)
    sigs = []
    for i in np.where(sb)[0]:
        sigs.append((int(bars_full.iloc[i]["ts_end_ms"]), "buy", int(bars_full.iloc[i]["hour_utc"])))
    for i in np.where(ss)[0]:
        sigs.append((int(bars_full.iloc[i]["ts_end_ms"]), "sell", int(bars_full.iloc[i]["hour_utc"])))
    sigs.sort()
    if hours_block:
        bs = set(hours_block); sigs = [s for s in sigs if s[2] not in bs]
    trades = []; last_loss_ts = -1; daily_pnl = {}
    for sig_ts, side, hr in sigs:
        if post_loss_cooldown_min > 0 and last_loss_ts > 0:
            if (sig_ts - last_loss_ts) / 60000.0 < post_loss_cooldown_min: continue
        date_key = datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if daily_cap_loss is not None and daily_pnl.get(date_key, 0) <= -abs(daily_cap_loss): continue
        pi = find_idx(sig_ts)
        if pi >= len(ts): continue
        if max_spread_pts is not None and (asks[pi]-bids[pi])*100 > max_spread_pts: continue
        p_entry = asks[pi] if side == "buy" else bids[pi]
        timeout_ts = ts[pi] + probe_timeout_s * 1000
        end_idx = find_idx(timeout_ts)
        if end_idx <= pi: continue
        if side == "buy":
            pnl_arr = (bids[pi:end_idx] - p_entry) * CONTRACT_SIZE * PROBE_LOT
        else:
            pnl_arr = (p_entry - asks[pi:end_idx]) * CONTRACT_SIZE * PROBE_LOT
        sub_ts = ts[pi:end_idx]
        c_idx = int(np.argmax(pnl_arr >= probe_confirm)) if (pnl_arr >= probe_confirm).any() else -1
        f_idx = int(np.argmax(pnl_arr <= probe_fail))    if (pnl_arr <= probe_fail).any() else -1
        if c_idx >= 0 and (f_idx < 0 or c_idx <= f_idx):
            outcome = "confirm"; ex = c_idx
        elif f_idx >= 0:
            outcome = "fail"; ex = f_idx
        else:
            outcome = "timeout"; ex = len(pnl_arr) - 1
        probe_pnl = float(pnl_arr[ex]); probe_exit_ts = int(sub_ts[ex])
        total = probe_pnl - PROBE_COMM
        if outcome == "confirm":
            mi = find_idx(probe_exit_ts)
            if mi < len(ts):
                m_entry = asks[mi] if side == "buy" else bids[mi]
                cap_ts = ts[mi] + MAIN_HOLD_CAP_S * 1000
                ei2 = find_idx(cap_ts)
                if ei2 > mi:
                    if side == "buy":
                        m_pnl = (bids[mi:ei2] - m_entry) * CONTRACT_SIZE * MAIN_LOT
                    else:
                        m_pnl = (m_entry - asks[mi:ei2]) * CONTRACT_SIZE * MAIN_LOT
                    tpi = int(np.argmax(m_pnl >= main_tp)) if (m_pnl >= main_tp).any() else -1
                    sli = int(np.argmax(m_pnl <= -abs(main_sl))) if (m_pnl <= -abs(main_sl)).any() else -1
                    if tpi >= 0 and (sli < 0 or tpi <= sli):
                        m_real = float(m_pnl[tpi])
                    elif sli >= 0:
                        m_real = float(m_pnl[sli])
                    else:
                        m_real = float(m_pnl[-1])
                    total += (m_real - MAIN_COMM)
        trades.append((sig_ts, side, hr, outcome, probe_pnl, total))
        if total < 0: last_loss_ts = sig_ts
        daily_pnl[date_key] = daily_pnl.get(date_key, 0) + total
    if not trades:
        return {"n":0,"wr":0,"net_pnl":0,"pf":0,"max_dd":0,"avg_pnl":0}
    arr = np.array([t[5] for t in trades])
    wins = (arr > 0).sum()
    gw = arr[arr > 0].sum(); gl = -arr[arr < 0].sum()
    eq = arr.cumsum()
    dd = float((np.maximum.accumulate(eq) - eq).max())
    return {
        "n": len(trades),
        "wr": round(wins/len(trades)*100, 2),
        "net_pnl": round(float(arr.sum()), 2),
        "avg_pnl": round(float(arr.mean()), 3),
        "pf": round(float(gw/gl), 2) if gl > 0 else None,
        "max_dd": round(dd, 2),
        "best": round(float(arr.max()), 2),
        "worst": round(float(arr.min()), 2),
    }

phase2 = json.loads(PHASE2.read_text())
baseline = dict(phase2["final_baseline"])
print("[BASELINE]:", json.dumps(baseline, default=str), flush=True)
b0 = simulate(min_body_2nd=0.0, **baseline)
print(f"  baseline (min_body_2nd=0): n={b0['n']} WR={b0['wr']}% net=${b0['net_pnl']} PF={b0['pf']} DD=${b0['max_dd']}", flush=True)

print("\n=== MIN_BODY_2ND SWEEP (price units; 0.01 = 1 point on XAUUSD) ===", flush=True)
print(f"{'min_body':>10} | {'n':>5} | {'WR%':>6} | {'net':>10} | {'PF':>5} | {'DD':>9} | {'avg':>7}", flush=True)
print("-" * 80, flush=True)

results = {"started": datetime.now(timezone.utc).isoformat(), "baseline_config": baseline, "baseline_stats": b0, "sweep": []}
for mb in [0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0, 2.0, 3.0, 5.0]:
    s = simulate(min_body_2nd=mb, **baseline)
    print(f"{mb:>10.2f} | {s['n']:>5} | {s['wr']:>6.2f} | {s['net_pnl']:>10.2f} | {str(s['pf']):>5} | {s['max_dd']:>9.2f} | {s['avg_pnl']:>7.3f}", flush=True)
    results["sweep"].append({"min_body_2nd": mb, **s})

# Pick best by net_pnl among non-zero
best = max((r for r in results["sweep"] if r.get("n",0) > 0), key=lambda r: r["net_pnl"])
results["best"] = best
print(f"\n  -> BEST: min_body_2nd={best['min_body_2nd']} | net=${best['net_pnl']} | WR={best['wr']}% | n={best['n']}", flush=True)
print(f"  delta vs current: ${best['net_pnl'] - b0['net_pnl']:+.2f}", flush=True)

OUT_J.write_text(json.dumps(results, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
