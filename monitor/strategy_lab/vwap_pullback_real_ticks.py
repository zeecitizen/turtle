"""VWAP Pullback / Mean Reversion on Blueberry real ticks — 120-day backtest.

Rules:
  1. Session-anchored VWAP, reset at 00:00 UTC daily
  2. Trend filter: VWAP slope (rising = bullish bias) over N M1 bars
  3. Entry (long): price > VWAP, pulls back to touch VWAP, bounces (M1 close > VWAP)
  4. Entry (short): price < VWAP, pulls back to touch VWAP, rejects (M1 close < VWAP)
  5. SL: opposite side of VWAP by SL_BUFFER pts (or fixed R-multiple of recent ATR)
  6. TP: 1.5R / 2R / day high/low

Volume note: Blueberry CFD has volume_real=0 so VWAP uses tick count as volume proxy
(this becomes effectively TWAP — Time-Weighted Average Price since tick rate is the
weighting, not deal size). This is the documented limitation we already saw with VSISA.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_vwap_pullback_results.json")

CONTRACT_SIZE = 100
LOTS = 0.30
COMMISSION = 7.0 * LOTS

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

# Build M1 bars with tick count (= volume proxy)
df["m1_bucket"] = (df["time_msc"] // 60_000).astype(np.int64)
m1 = df.groupby("m1_bucket", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"),
    ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1_bucket")
m1["typical"] = (m1["h"] + m1["l"] + m1["c"]) / 3
m1["dt"] = pd.to_datetime(m1["ts_end_ms"], unit="ms", utc=True)
m1["date"] = m1["dt"].dt.strftime("%Y-%m-%d")
m1["mins_utc"] = m1["dt"].dt.hour * 60 + m1["dt"].dt.minute
m1["pv"] = m1["typical"] * m1["v"]
print(f"[BARS] {len(m1)} M1 bars", flush=True)

# Compute session-anchored VWAP per day
def compute_vwap(date_df):
    """Cumulative VWAP within a single trading day."""
    cum_pv = date_df["pv"].cumsum()
    cum_v  = date_df["v"].cumsum()
    return (cum_pv / cum_v).values

# Pre-compute VWAP per day
m1["vwap"] = 0.0
for date_str in m1["date"].unique():
    mask = m1["date"] == date_str
    m1.loc[mask, "vwap"] = compute_vwap(m1.loc[mask])

m1_o = m1["o"].to_numpy(); m1_h = m1["h"].to_numpy()
m1_l = m1["l"].to_numpy(); m1_c = m1["c"].to_numpy()
m1_vwap = m1["vwap"].to_numpy()
m1_ts_end = m1["ts_end_ms"].to_numpy()
m1_date = m1["date"].to_numpy()
m1_mins = m1["mins_utc"].to_numpy()

ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)
def find_idx(t_ms): return int(np.searchsorted(ts, t_ms, side="right"))

def detect_signal(idx, slope_lookback, extend_pts, pullback_max_pts):
    """Return ('buy'/'sell', None) if pullback signal at bar idx."""
    if idx < slope_lookback + 5: return None
    cur_vwap = m1_vwap[idx]; prev_vwap = m1_vwap[idx - slope_lookback]
    slope = cur_vwap - prev_vwap
    cur_close = m1_c[idx]; cur_low = m1_l[idx]; cur_high = m1_h[idx]
    # Recent extension: did price extend beyond VWAP by extend_pts in the last slope_lookback bars?
    win_start = max(0, idx - slope_lookback)
    win_high = m1_h[win_start:idx+1].max()
    win_low  = m1_l[win_start:idx+1].min()
    extended_up = (win_high - cur_vwap) >= extend_pts / 100.0
    extended_down = (cur_vwap - win_low) >= extend_pts / 100.0

    # Long signal: above VWAP trend, extended up, current bar pulled to VWAP and closed above
    if slope > 0 and extended_up:
        # Pulled to VWAP this bar (low touched VWAP within tolerance)
        if cur_low <= cur_vwap + (pullback_max_pts / 100.0) and cur_close > cur_vwap:
            return ("buy", cur_vwap)
    # Short
    if slope < 0 and extended_down:
        if cur_high >= cur_vwap - (pullback_max_pts / 100.0) and cur_close < cur_vwap:
            return ("sell", cur_vwap)
    return None

def simulate_trade(idx, side, vwap_at_entry, sl_buffer_pts, tp_r, max_hold_bars):
    """Walk M1 bars until SL/TP/timeout."""
    entry = m1_c[idx]
    if side == "buy":
        sl = vwap_at_entry - sl_buffer_pts / 100.0
    else:
        sl = vwap_at_entry + sl_buffer_pts / 100.0
    risk = abs(entry - sl)
    if risk < 0.05: return None
    tp = entry + tp_r * risk if side == "buy" else entry - tp_r * risk
    for off in range(1, max_hold_bars + 1):
        i = idx + off
        if i >= len(m1_c): break
        # New day? Stop holding overnight
        if m1_date[i] != m1_date[idx]:
            exit_price = m1_c[i-1]
            move = (exit_price - entry) if side == "buy" else (entry - exit_price)
            return {"reason": "EOD", "exit": exit_price, "pnl": move * 100 * LOTS - COMMISSION,
                    "R": move/risk, "age": off-1}
        if side == "buy":
            if m1_l[i] <= sl:
                return {"reason": "SL", "exit": sl, "pnl": (sl-entry)*100*LOTS - COMMISSION,
                        "R": -1, "age": off}
            if m1_h[i] >= tp:
                return {"reason": "TP", "exit": tp, "pnl": (tp-entry)*100*LOTS - COMMISSION,
                        "R": tp_r, "age": off}
        else:
            if m1_h[i] >= sl:
                return {"reason": "SL", "exit": sl, "pnl": (entry-sl)*100*LOTS - COMMISSION,
                        "R": -1, "age": off}
            if m1_l[i] <= tp:
                return {"reason": "TP", "exit": tp, "pnl": (entry-tp)*100*LOTS - COMMISSION,
                        "R": tp_r, "age": off}
    last = m1_c[min(idx + max_hold_bars, len(m1_c)-1)]
    move = (last - entry) if side == "buy" else (entry - last)
    return {"reason": "TIME", "exit": last, "pnl": move * 100 * LOTS - COMMISSION,
            "R": move/risk, "age": max_hold_bars}

def backtest(cfg):
    trades = []
    last_trade_idx = -1000  # cooldown
    for idx in range(cfg["slope_lookback"] + 5, len(m1) - 1):
        # session restriction (only trade during high-volume hours)
        if not (cfg["sess_start_min"] <= m1_mins[idx] < cfg["sess_end_min"]): continue
        # cooldown between trades
        if idx - last_trade_idx < cfg["cooldown_bars"]: continue
        sig = detect_signal(idx, cfg["slope_lookback"], cfg["extend_pts"], cfg["pullback_max_pts"])
        if sig is None: continue
        side, vwap_at = sig
        result = simulate_trade(idx, side, vwap_at, cfg["sl_buffer_pts"], cfg["tp_r"], cfg["max_hold_bars"])
        if result is None: continue
        result.update({"date": m1_date[idx], "side": side, "entry": m1_c[idx], "vwap": vwap_at})
        trades.append(result)
        last_trade_idx = idx
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
for slope_lookback in [10, 20, 30, 60]:  # M1 bars
    for extend_pts in [50, 100, 200]:  # how far price must extend from VWAP
        for pullback_max_pts in [10, 20, 50]:  # how close to VWAP for pullback
            for sl_buffer_pts in [20, 40, 80]:
                for tp_r in [1.0, 1.5, 2.0]:
                    for sess_start, sess_end in [(7*60, 18*60), (12*60, 21*60), (0*60, 24*60)]:
                        SWEEP.append({
                            "slope_lookback": slope_lookback, "extend_pts": extend_pts,
                            "pullback_max_pts": pullback_max_pts, "sl_buffer_pts": sl_buffer_pts,
                            "tp_r": tp_r, "max_hold_bars": 60, "cooldown_bars": 30,
                            "sess_start_min": sess_start, "sess_end_min": sess_end,
                        })

print(f"[SWEEP] {len(SWEEP)} configs", flush=True)
results = []
for i, cfg in enumerate(SWEEP):
    trades = backtest(cfg)
    s = stats(trades)
    s.update(cfg)
    results.append(s)
    if (i+1) % 50 == 0: print(f"  done {i+1}/{len(SWEEP)}", flush=True)

ok = [r for r in results if r.get("n", 0) >= 20]
ok.sort(key=lambda r: r["net"], reverse=True)
print(f"\n=== TOP 15 by NET (n>=20) ===", flush=True)
print(f"{'slope':>5} {'ext':>4} {'pull':>4} {'slbuf':>5} {'tp':>4} {'sess':>9} | {'n':>4} {'wr%':>5} {'pf':>5} {'net$':>9} {'dd':>7}", flush=True)
for r in ok[:15]:
    sess = f"{r['sess_start_min']//60:02d}-{r['sess_end_min']//60:02d}"
    print(f"{r['slope_lookback']:>5} {r['extend_pts']:>4} {r['pullback_max_pts']:>4} {r['sl_buffer_pts']:>5} {r['tp_r']:>4.1f} {sess:>9} | {r['n']:>4} {r['wr']:>5.1f} {str(r['pf']):>5} {r['net']:>9.2f} {r['max_dd']:>7.2f}", flush=True)

best = ok[0] if ok else None
print(f"\n=== BEST OVERALL ===", flush=True)
print(json.dumps(best, indent=2, default=str), flush=True)

result = {"started": datetime.now(timezone.utc).isoformat(), "best": best, "top15": ok[:15], "all_count": len(results)}
OUT_J.write_text(json.dumps(result, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
