"""VSISA proper M5 backtest — second attempt with relaxed thresholds + VSA context.

Key changes from first attempt:
  1. Volume proxy = tick count per M5 bar (same), but thresholds RELAXED for Blueberry's
     compressed tick-count distribution (3:1 typical vs 10:1 on real volume)
  2. Add VOLUME RATIO mode (effort_vol / reaction_vol) instead of just percentiles
  3. Add VSA CONTEXT: prior trend (need uptrend before "no demand" sell signal)
  4. H1 trend filter as documented in Sir Sajid's videos
  5. Session filter (London/NY only — high-volume sessions)
  6. Train/test split (75/25) to validate edge survives OOS

Pattern (per VSA_RULE_SPEC.md):
  SELL setup:
    - Prior trend: up (current price above N-bar SMA)
    - Effort bar: big volume (top X% OR ratio threshold)
    - Reaction bar: bearish + engulfs effort body + low volume
    - Optional H1 filter: H1 EMA slope down or H1 close below H1 EMA
  BUY setup: mirror
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_vsisa_m5_proper_results.json")

LOTS = 0.30
COMMISSION = 7.0 * LOTS
SL_BUFFER_PT = 0.10

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

def build_bars(tf_sec):
    bucket = (df["time_msc"] // (tf_sec * 1000)).astype(np.int64)
    g = df.assign(_b=bucket).groupby("_b", sort=True).agg(
        o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
        v=("bid","count"), ts_end_ms=("time_msc","last"),
    ).reset_index().drop(columns="_b")
    g["dt"] = pd.to_datetime(g["ts_end_ms"], unit="ms", utc=True)
    g["mins_utc"] = g["dt"].dt.hour * 60 + g["dt"].dt.minute
    return g.to_dict("records")

print("[BARS] building M5 / H1...", flush=True)
m5 = build_bars(300)
h1 = build_bars(3600)
print(f"  M5={len(m5)}  H1={len(h1)}", flush=True)

def ema(values, period):
    out = [None] * len(values)
    if not values: return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i-1] * (1 - k)
    return out

h1_close = [b["c"] for b in h1]
h1_ema21 = ema(h1_close, 21)

# Diagnose volume distribution
m5_vols = np.array([b["v"] for b in m5 if b["v"] > 0])
print(f"\n[VOL DIST] M5 tick counts:")
print(f"  min={m5_vols.min()} median={int(np.median(m5_vols))} mean={int(m5_vols.mean())} max={m5_vols.max()}")
print(f"  pct10={int(np.percentile(m5_vols, 10))} pct25={int(np.percentile(m5_vols, 25))} pct50={int(np.percentile(m5_vols, 50))} pct75={int(np.percentile(m5_vols, 75))} pct90={int(np.percentile(m5_vols, 90))}")
print(f"  high/low ratio at 90/10: {np.percentile(m5_vols,90)/max(1,np.percentile(m5_vols,10)):.2f}")

def session_thresholds(bars, idx, lookback, big_pct, low_pct):
    if idx < lookback: return float("inf"), float("inf")
    vols = sorted(b["v"] for b in bars[max(0, idx-lookback):idx] if b["v"] > 0)
    if not vols: return float("inf"), float("inf")
    return vols[int(len(vols)*big_pct)], vols[int(len(vols)*low_pct)]

def detect_setup(bars, idx, mode, p):
    """mode: 'pct' = percentile thresholds, 'ratio' = vol ratio
    Returns (direction, effort_idx) or None."""
    if idx < p["lookback"]: return None
    e, r = bars[idx-1], bars[idx]
    if e["v"] == 0 or r["v"] == 0: return None

    if mode == "pct":
        big_v, low_v = session_thresholds(bars, idx, p["lookback"], p["big_pct"], p["low_pct"])
        if e["v"] < big_v: return None
        if r["v"] >= low_v: return None
    else:  # ratio mode
        if e["v"] / max(1, r["v"]) < p["vol_ratio"]: return None
        # Also require effort bar is "big" relative to its peers
        big_v, _ = session_thresholds(bars, idx, p["lookback"], p["big_pct"], 0.5)
        if e["v"] < big_v: return None

    e_dir = "up" if e["c"] > e["o"] else "dn"
    r_dir = "up" if r["c"] > r["o"] else "dn"
    if e_dir == r_dir: return None  # opposite direction reaction
    e_lo, e_hi = min(e["o"], e["c"]), max(e["o"], e["c"])
    r_lo, r_hi = min(r["o"], r["c"]), max(r["o"], r["c"])
    e_size = e_hi - e_lo
    if e_size <= 0: return None
    overlap = max(0.0, min(e_hi, r_hi) - max(e_lo, r_lo))
    if overlap / e_size < p["body_cov"]: return None

    # Prior trend (VSA context): for SELL want uptrend, for BUY want downtrend
    if p.get("require_prior_trend", False):
        if idx < 21: return None
        prior_avg = sum(b["c"] for b in bars[idx-21:idx-1]) / 20
        cur = bars[idx-1]["c"]
        if r_dir == "dn" and cur < prior_avg: return None  # need uptrend for sell
        if r_dir == "up" and cur > prior_avg: return None  # need downtrend for buy

    # Session filter
    if p.get("session_start_min") is not None:
        if not (p["session_start_min"] <= bars[idx]["mins_utc"] < p["session_end_min"]):
            return None

    return ("sell", idx-1) if r_dir == "dn" else ("buy", idx-1)

def h1_trend_at(ts_ms):
    idx = -1
    for i, b in enumerate(h1):
        if b["ts_end_ms"] <= ts_ms: idx = i
        else: break
    if idx < 25 or h1_ema21[idx] is None or h1_ema21[idx-3] is None: return "neutral"
    px = h1[idx]["c"]; em = h1_ema21[idx]; em_p = h1_ema21[idx-3]
    if px > em and em > em_p: return "up"
    if px < em and em < em_p: return "dn"
    return "neutral"

def simulate(bars, sig_idx, direction, entry, sl, tp_r, max_bars=60):
    risk = abs(entry - sl)
    if risk < 0.05: return None
    tp = entry - tp_r * risk if direction == "sell" else entry + tp_r * risk
    for off in range(1, max_bars + 1):
        i = sig_idx + off
        if i >= len(bars): break
        b = bars[i]
        if direction == "sell":
            if b["h"] >= sl: return {"reason": "SL", "pnl": (entry-sl)*100*LOTS - COMMISSION, "R": -1, "age": off}
            if b["l"] <= tp: return {"reason": "TP", "pnl": (entry-tp)*100*LOTS - COMMISSION, "R": tp_r, "age": off}
        else:
            if b["l"] <= sl: return {"reason": "SL", "pnl": (sl-entry)*100*LOTS - COMMISSION, "R": -1, "age": off}
            if b["h"] >= tp: return {"reason": "TP", "pnl": (tp-entry)*100*LOTS - COMMISSION, "R": tp_r, "age": off}
    last = bars[min(sig_idx + max_bars, len(bars)-1)]
    move = (entry - last["c"]) if direction == "sell" else (last["c"] - entry)
    return {"reason": "TIME", "pnl": move*100*LOTS - COMMISSION, "R": move/risk, "age": max_bars}

def backtest(p):
    trades = []
    for idx in range(p["lookback"], len(m5) - 1):
        sig = detect_setup(m5, idx, p.get("mode", "pct"), p)
        if not sig: continue
        direction, _ = sig
        r = m5[idx]
        entry = r["c"]
        sl = (r["h"] + SL_BUFFER_PT) if direction == "sell" else (r["l"] - SL_BUFFER_PT)
        if p.get("use_h1_trend", False):
            t = h1_trend_at(r["ts_end_ms"])
            if direction == "sell" and t != "dn": continue
            if direction == "buy" and t != "up": continue
        out = simulate(m5, idx, direction, entry, sl, p["tp_r"])
        if out is None: continue
        out.update({"date": r["dt"].strftime("%Y-%m-%d"), "side": direction,
                    "entry": entry, "sl": sl, "ts_end_ms": r["ts_end_ms"]})
        trades.append(out)
    return trades

def stats(trades):
    if not trades: return {"n": 0}
    arr = np.array([t["pnl"] for t in trades])
    wins = arr[arr > 0]; losses = arr[arr < 0]
    wr = 100 * len(wins) / len(trades)
    pf = float(wins.sum()) / float(-losses.sum()) if len(losses) and losses.sum() != 0 else None
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(arr), "wr": round(wr, 2),
            "pf": round(pf, 2) if pf else None,
            "net": round(float(arr.sum()), 2), "avg": round(float(arr.mean()), 2),
            "max_dd": round(dd, 2), "best": round(float(arr.max()), 2),
            "worst": round(float(arr.min()), 2)}

# === SWEEP ===
SWEEP = []

# Percentile mode
for big_pct in [0.50, 0.60, 0.70, 0.80]:
    for low_pct in [0.40, 0.50, 0.60, 0.70]:
        for body_cov in [0.30, 0.50, 0.70]:
            for tp_r in [1.0, 1.5, 2.0, 3.0]:
                for require_prior in [False, True]:
                    for use_h1 in [False, True]:
                        SWEEP.append({"mode": "pct", "big_pct": big_pct, "low_pct": low_pct,
                                      "body_cov": body_cov, "tp_r": tp_r,
                                      "require_prior_trend": require_prior,
                                      "use_h1_trend": use_h1, "lookback": 100})

# Ratio mode
for vol_ratio in [1.5, 2.0, 3.0, 5.0]:
    for big_pct in [0.50, 0.70]:
        for body_cov in [0.30, 0.50, 0.70]:
            for tp_r in [1.0, 1.5, 2.0, 3.0]:
                for require_prior in [False, True]:
                    SWEEP.append({"mode": "ratio", "vol_ratio": vol_ratio, "big_pct": big_pct,
                                  "body_cov": body_cov, "tp_r": tp_r,
                                  "require_prior_trend": require_prior,
                                  "use_h1_trend": False, "lookback": 100})

print(f"\n[SWEEP] {len(SWEEP)} configs", flush=True)

results = []
import time; t0 = time.time()
for i, p in enumerate(SWEEP):
    trades = backtest(p)
    s = stats(trades)
    s.update(p)
    s["trades"] = trades  # keep for OOS analysis
    results.append(s)
    if (i+1) % 100 == 0: print(f"  done {i+1}/{len(SWEEP)} ({time.time()-t0:.0f}s)", flush=True)

# Filter to n>=30 for significance, sort by net
ok = [r for r in results if r.get("n", 0) >= 30]
ok.sort(key=lambda r: r["net"], reverse=True)
print(f"\n[FILTER] {len(ok)} configs with n>=30 (out of {len(results)})", flush=True)

# Show top 15
print(f"\n=== TOP 15 by NET P&L (n>=30) ===", flush=True)
print(f"{'mode':>5} {'big':>5} {'low':>5} {'body':>5} {'tp':>4} {'prior':>5} {'h1':>5} | {'n':>4} {'wr%':>5} {'pf':>5} {'net$':>9} {'dd':>8}", flush=True)
for r in ok[:15]:
    mode = r["mode"]
    big = f"{r['big_pct']:.2f}" if mode == "pct" else f"r{r.get('vol_ratio', 0):.1f}"
    low = f"{r.get('low_pct', '-'):.2f}" if mode == "pct" else "-"
    print(f"{mode:>5} {big:>5} {low:>5} {r['body_cov']:>5.2f} {r['tp_r']:>4.1f} {str(r['require_prior_trend']):>5} {str(r.get('use_h1_trend', False)):>5} | {r['n']:>4} {r['wr']:>5.1f} {str(r['pf']):>5} {r['net']:>9.2f} {r['max_dd']:>8.2f}", flush=True)

# Train/test split — 75/25 by date
all_dates = sorted(set(t["date"] for r in ok for t in r.get("trades", [])))
if all_dates:
    cutoff_idx = int(len(all_dates) * 0.75)
    cutoff = all_dates[cutoff_idx]
    print(f"\n=== TRAIN/TEST SPLIT (cutoff: {cutoff}) ===", flush=True)
    print(f"{'mode':>5} {'big':>5} {'tp':>4} {'h1':>5} | {'train_n':>7} {'tr_wr':>5} {'tr_pf':>5} {'tr_net':>8} || {'test_n':>6} {'te_wr':>5} {'te_pf':>5} {'te_net':>8}", flush=True)
    train_test_results = []
    for r in ok[:20]:  # top 20 for OOS check
        trn = [t for t in r["trades"] if t["date"] < cutoff]
        tst = [t for t in r["trades"] if t["date"] >= cutoff]
        s_trn = stats(trn) if trn else {"n": 0}
        s_tst = stats(tst) if tst else {"n": 0}
        if s_tst.get("n", 0) >= 5:  # need at least 5 OOS trades
            mode = r["mode"]
            big = f"{r['big_pct']:.2f}" if mode == "pct" else f"r{r.get('vol_ratio', 0):.1f}"
            print(f"{mode:>5} {big:>5} {r['tp_r']:>4.1f} {str(r.get('use_h1_trend', False)):>5} | {s_trn['n']:>7} {s_trn['wr']:>5.1f} {str(s_trn['pf']):>5} {s_trn['net']:>8.2f} || {s_tst['n']:>6} {s_tst['wr']:>5.1f} {str(s_tst['pf']):>5} {s_tst['net']:>8.2f}", flush=True)
            train_test_results.append({"config": {k: v for k, v in r.items() if k != "trades"},
                                       "train": s_trn, "test": s_tst})

# Save
def serialize(r):
    return {k: v for k, v in r.items() if k != "trades"}

result_doc = {
    "started": datetime.now(timezone.utc).isoformat(),
    "vol_distribution": {
        "min": int(m5_vols.min()), "median": int(np.median(m5_vols)),
        "mean": int(m5_vols.mean()), "max": int(m5_vols.max()),
        "p10": int(np.percentile(m5_vols, 10)), "p90": int(np.percentile(m5_vols, 90)),
    },
    "all_count": len(results), "n30_count": len(ok),
    "top15": [serialize(r) for r in ok[:15]],
    "train_test_top20": train_test_results,
}
OUT_J.write_text(json.dumps(result_doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
