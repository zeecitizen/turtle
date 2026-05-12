"""Compare bigness signal performance across bar timeframes (M1..D1).

For each TF:
  1. Re-aggregate ticks into bars at that TF
  2. Run RAW simulation (no filters) with phase-1 probe/main params
  3. Run with phase-2 winning filter stack (hours/spread/cooldown)
  4. Compare n / WR / PF / net / DD

Output: monitor/strategy_lab/_real_tick_tf_compare.json
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE  = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J  = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_tf_compare.json")
PHASE2 = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_filter_results.json")

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
df_time_msc = df["time_msc"]
df_bid = df["bid"]

phase2 = json.loads(PHASE2.read_text())
PARAMS = dict(phase2["final_baseline"])
PARAMS_RAW = {**PARAMS, "hours_block": None, "max_spread_pts": None, "post_loss_cooldown_min": 0, "daily_cap_loss": None}

def find_idx(t_ms):
    return int(np.searchsorted(ts, t_ms, side="right"))

def build_bars(tf_sec):
    bucket = (df_time_msc // (tf_sec * 1000)).astype(np.int64)
    g = df.assign(_b=bucket).groupby("_b", sort=True).agg(
        open=("bid","first"), close=("bid","last"),
        ts_end_ms=("time_msc","last"),
    ).reset_index()
    g["body"] = (g["close"] - g["open"]).abs()
    g["dir"]  = np.sign(g["close"] - g["open"]).astype(int)
    g["hour_utc"] = pd.to_datetime(g["ts_end_ms"], unit="ms", utc=True).dt.hour
    return g

def detect(bars, big_ratio):
    body = bars["body"].to_numpy(); direction = bars["dir"].to_numpy()
    n = len(body)
    big = np.zeros(n, dtype=bool)
    big[2:] = body[1:-1] > big_ratio * body[:-2]
    dir_prev = np.roll(direction, 1)
    sb = big & (dir_prev == 1) & (direction == 1)
    ss = big & (dir_prev == -1) & (direction == -1)
    sb[:2] = False; ss[:2] = False
    return sb, ss

def simulate(bars, big_ratio, probe_confirm, probe_fail, probe_timeout_s,
             main_tp, main_sl,
             hours_block=None, max_spread_pts=None,
             post_loss_cooldown_min=0, daily_cap_loss=None):
    sb, ss = detect(bars, big_ratio)
    sigs = []
    for i in np.where(sb)[0]:
        sigs.append((int(bars.iloc[i]["ts_end_ms"]), "buy", int(bars.iloc[i]["hour_utc"])))
    for i in np.where(ss)[0]:
        sigs.append((int(bars.iloc[i]["ts_end_ms"]), "sell", int(bars.iloc[i]["hour_utc"])))
    sigs.sort()
    if hours_block:
        bs = set(hours_block)
        sigs = [s for s in sigs if s[2] not in bs]
    trades = []
    last_loss_ts = -1; daily_pnl = {}
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
        probe_pnl = float(pnl_arr[ex])
        probe_exit_ts = int(sub_ts[ex])
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
        return {"n":0,"wr":0,"net_pnl":0,"pf":0,"max_dd":0,"avg_pnl":0,"raw_signals":int(sb.sum()+ss.sum())}
    arr = np.array([t[5] for t in trades])
    wins = (arr > 0).sum()
    gw = arr[arr > 0].sum(); gl = -arr[arr < 0].sum()
    eq = arr.cumsum()
    dd = float((np.maximum.accumulate(eq) - eq).max())
    return {
        "n": len(trades),
        "raw_signals": int(sb.sum() + ss.sum()),
        "wr": round(wins/len(trades)*100, 2),
        "net_pnl": round(float(arr.sum()), 2),
        "avg_pnl": round(float(arr.mean()), 3),
        "pf": round(float(gw/gl), 2) if gl > 0 else None,
        "max_dd": round(dd, 2),
        "best": round(float(arr.max()), 2),
        "worst": round(float(arr.min()), 2),
    }

TFS = [
    ("M1",   60),
    ("M5",   300),
    ("M15",  900),
    ("M30",  1800),
    ("H1",   3600),
    ("H4",   14400),
    ("D1",   86400),
]

results = {"started": datetime.now(timezone.utc).isoformat(), "params_raw": PARAMS_RAW, "params_filtered": PARAMS, "by_tf": {}}

print("\n=== TIMEFRAME COMPARISON ===", flush=True)
print(f"{'TF':>4} | {'bars':>7} | {'sigs':>7} | "
      f"{'RAW: n':>6} {'WR%':>6} {'net':>9} {'PF':>5} {'DD':>9} | "
      f"{'FILT: n':>7} {'WR%':>6} {'net':>9} {'PF':>5} {'DD':>9}", flush=True)
print("-" * 132, flush=True)

for label, sec in TFS:
    bars = build_bars(sec)
    raw = simulate(bars, **PARAMS_RAW)
    flt = simulate(bars, **PARAMS)
    results["by_tf"][label] = {"tf_seconds": sec, "n_bars": len(bars), "raw": raw, "filtered": flt}
    print(f"{label:>4} | {len(bars):>7,} | {raw['raw_signals']:>7,} | "
          f"{raw['n']:>6} {raw['wr']:>6.1f} {raw['net_pnl']:>9.2f} {str(raw['pf']):>5} {raw['max_dd']:>9.2f} | "
          f"{flt['n']:>7} {flt['wr']:>6.1f} {flt['net_pnl']:>9.2f} {str(flt['pf']):>5} {flt['max_dd']:>9.2f}",
          flush=True)

OUT_J.write_text(json.dumps(results, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
