"""VSISA (Sajid Ahmad) on Blueberry real ticks — M5 + M15 sweep.

Pattern: big-volume effort bar + opposite-direction low-volume engulf reaction.
Volume proxy = tick count per bar (broker ticks have volume_real=0).

Sweeps params on each timeframe; reports best config + stats.
Output: monitor/strategy_lab/_vsisa_real_ticks_results.json
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_vsisa_real_ticks_results.json")

LOTS = 0.30
DOLLAR_PER_PT = LOTS * 100.0
SL_BUFFER_PT = 0.10
SLIP_COST = 1.0
COMMISSION = 7.0 * LOTS  # $/trade RT

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

def build_bars(tf_sec):
    bucket = (df["time_msc"] // (tf_sec * 1000)).astype(np.int64)
    g = df.assign(_b=bucket).groupby("_b", sort=True).agg(
        o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
        v=("bid","count"),  # tick count = volume proxy
        ts_end_ms=("time_msc","last"),
    ).reset_index().drop(columns="_b")
    g["ts"] = pd.to_datetime(g["ts_end_ms"], unit="ms", utc=True)
    return g.to_dict("records")

print("[BARS] building M5 / M15 / H1 (for trend filter)...", flush=True)
m5  = build_bars(300)
m15 = build_bars(900)
h1  = build_bars(3600)
print(f"  M5={len(m5)} M15={len(m15)} H1={len(h1)}", flush=True)

def session_volume_thresholds(bars, idx, lookback_bars, big_pct, low_pct):
    if idx < lookback_bars: return float("inf"), float("inf")
    vols = sorted(b["v"] for b in bars[max(0, idx-lookback_bars):idx] if b["v"] > 0)
    if not vols: return float("inf"), float("inf")
    return vols[int(len(vols)*big_pct)], vols[int(len(vols)*low_pct)]

def detect_setup(bars, idx, big_pct, low_pct, body_coverage, lookback_bars):
    if idx < 1: return None
    e, r = bars[idx-1], bars[idx]
    if e["v"] == 0 or r["v"] == 0: return None
    big_v, low_v = session_volume_thresholds(bars, idx, lookback_bars, big_pct, low_pct)
    if e["v"] < big_v: return None
    if r["v"] >= low_v: return None
    e_dir = "up" if e["c"] > e["o"] else "dn"
    r_dir = "up" if r["c"] > r["o"] else "dn"
    if e_dir == r_dir: return None
    e_lo, e_hi = min(e["o"], e["c"]), max(e["o"], e["c"])
    r_lo, r_hi = min(r["o"], r["c"]), max(r["o"], r["c"])
    e_size = e_hi - e_lo
    if e_size <= 0: return None
    overlap = max(0.0, min(e_hi, r_hi) - max(e_lo, r_lo))
    if overlap / e_size < body_coverage: return None
    if r_dir == "dn" and r_lo > e_lo: return None
    if r_dir == "up" and r_hi < e_hi: return None
    return ("sell", idx-1) if r_dir == "dn" else ("buy", idx-1)

def ema_arr(values, period):
    out = [None] * len(values)
    if not values: return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i-1] * (1 - k)
    return out

def trend_at_h1(h1_bars, ts_end_ms, ema_vals, lookback=3):
    """Return 'up' / 'dn' / 'neutral' based on H1 EMA vs price."""
    idx = -1
    for i, b in enumerate(h1_bars):
        if b["ts_end_ms"] <= ts_end_ms: idx = i
        else: break
    if idx < lookback + 1 or ema_vals[idx] is None or ema_vals[max(0, idx-lookback)] is None:
        return "neutral"
    slope = ema_vals[idx] - ema_vals[max(0, idx-lookback)]
    px = h1_bars[idx]["c"]
    if px > ema_vals[idx] and slope > 0: return "up"
    if px < ema_vals[idx] and slope < 0: return "dn"
    return "neutral"

def simulate(bars, sig_idx, direction, entry, sl, tp_r, max_bars=60):
    risk = abs(entry - sl)
    if risk < 0.05: return None
    tp = entry - tp_r * risk if direction == "sell" else entry + tp_r * risk
    for offset in range(1, max_bars+1):
        i = sig_idx + offset
        if i >= len(bars): break
        b = bars[i]
        if direction == "sell" and b["h"] >= sl:
            return {"reason": "sl", "pnl": (entry-sl)*DOLLAR_PER_PT - SLIP_COST - COMMISSION, "R": -1.0, "age": offset}
        if direction == "buy" and b["l"] <= sl:
            return {"reason": "sl", "pnl": (sl-entry)*DOLLAR_PER_PT - SLIP_COST - COMMISSION, "R": -1.0, "age": offset}
        if direction == "sell" and b["l"] <= tp:
            return {"reason": "tp", "pnl": (entry-tp)*DOLLAR_PER_PT - SLIP_COST - COMMISSION, "R": tp_r, "age": offset}
        if direction == "buy" and b["h"] >= tp:
            return {"reason": "tp", "pnl": (tp-entry)*DOLLAR_PER_PT - SLIP_COST - COMMISSION, "R": tp_r, "age": offset}
    last = bars[min(sig_idx + max_bars, len(bars)-1)]
    move = (entry - last["c"]) if direction == "sell" else (last["c"] - entry)
    R = move / risk
    return {"reason": "time", "pnl": move*DOLLAR_PER_PT - SLIP_COST - COMMISSION, "R": R, "age": max_bars}

# Pre-compute H1 EMA for trend filter
h1_close = [b["c"] for b in h1]
h1_ema = ema_arr(h1_close, 21)

def backtest(bars, params):
    trades = []
    for idx in range(params["lookback_bars"], len(bars) - 1):
        sig = detect_setup(bars, idx, params["big_pct"], params["low_pct"], params["body_cov"], params["lookback_bars"])
        if not sig: continue
        direction, _ = sig
        r = bars[idx]
        entry = r["c"]
        sl = (r["h"] + SL_BUFFER_PT) if direction == "sell" else (r["l"] - SL_BUFFER_PT)
        if params["use_h1"]:
            t = trend_at_h1(h1, r["ts_end_ms"], h1_ema)
            if direction == "sell" and t != "dn": continue
            if direction == "buy" and t != "up": continue
        out = simulate(bars, idx, direction, entry, sl, params["tp_r"])
        if out is None: continue
        out.update({"ts": r["ts"].strftime("%Y-%m-%d %H:%M"), "dir": direction, "entry": entry, "sl": sl})
        trades.append(out)
    return trades

def stats(trades):
    if not trades:
        return {"n": 0, "wr": 0, "net": 0, "avg_R": 0, "pf": 0, "max_dd": 0, "best": 0, "worst": 0}
    arr = np.array([t["pnl"] for t in trades])
    wins = arr[arr > 0]; losses = arr[arr < 0]
    wr = 100.0 * len(wins) / len(arr)
    net = float(arr.sum())
    avg_R = sum(t["R"] for t in trades) / len(trades)
    gw = float(wins.sum()) if len(wins) else 0
    gl = float(-losses.sum()) if len(losses) else 0
    pf = gw / gl if gl > 0 else None
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(arr), "wr": round(wr, 2), "net": round(net, 2),
            "avg_R": round(avg_R, 3), "pf": round(pf, 2) if pf else None,
            "max_dd": round(dd, 2), "best": round(float(arr.max()), 2),
            "worst": round(float(arr.min()), 2)}

# === SWEEP ===
SWEEP = []
for big_pct in [0.65, 0.75, 0.80, 0.85]:
    for low_pct in [0.40, 0.50, 0.60]:
        for body_cov in [0.70, 0.80, 0.90]:
            for tp_r in [1.5, 2.0, 3.0]:
                for use_h1 in [False, True]:
                    SWEEP.append({"big_pct": big_pct, "low_pct": low_pct, "body_cov": body_cov,
                                  "tp_r": tp_r, "use_h1": use_h1, "lookback_bars": 100})

print(f"[SWEEP] {len(SWEEP)} configs × 2 timeframes = {len(SWEEP)*2} runs", flush=True)

results = {"started": datetime.now(timezone.utc).isoformat(), "by_tf": {}}

for tf_label, bars_for_tf in [("M5", m5), ("M15", m15)]:
    print(f"\n=== {tf_label} ===", flush=True)
    rows = []
    for cfg in SWEEP:
        trades = backtest(bars_for_tf, cfg)
        s = stats(trades)
        rows.append({**cfg, **s})
    rows.sort(key=lambda r: (r["pf"] or 0) * r["wr"], reverse=True)
    print(f"\nTop 10 configs (by pf×wr):", flush=True)
    print(f"{'big':>5} {'low':>5} {'body':>5} {'tp':>4} {'h1':>5} | {'n':>4} {'wr%':>6} {'pf':>5} {'net$':>9} {'avgR':>6} {'dd':>8}", flush=True)
    for r in rows[:10]:
        print(f"{r['big_pct']:>5.2f} {r['low_pct']:>5.2f} {r['body_cov']:>5.2f} {r['tp_r']:>4.1f} {str(r['use_h1']):>5} | {r['n']:>4} {r['wr']:>6.2f} {str(r['pf']):>5} {r['net']:>9.2f} {r['avg_R']:>6.3f} {r['max_dd']:>8.2f}", flush=True)
    results["by_tf"][tf_label] = {"top10": rows[:10], "all_count": len(rows)}

# Best of best
best = None; best_tf = None; best_score = -1
for tf, data in results["by_tf"].items():
    for r in data["top10"]:
        score = (r.get("pf") or 0) * r.get("wr", 0)
        if r.get("n", 0) >= 10 and score > best_score:
            best_score = score; best = r; best_tf = tf

print(f"\n=== OVERALL BEST: {best_tf} ===", flush=True)
print(json.dumps(best, indent=2, default=str), flush=True)
results["overall_best"] = best
results["overall_best_tf"] = best_tf

OUT_J.write_text(json.dumps(results, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
