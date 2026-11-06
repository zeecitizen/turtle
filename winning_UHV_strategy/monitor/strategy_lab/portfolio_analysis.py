"""Combine LB + NY + VSISA into a portfolio. Compute correlations + combined stats.

A diversified portfolio (uncorrelated edges) gives better risk-adjusted returns than any
single strategy. Test if our 3 strategies are uncorrelated (good) or correlated (bad).
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_portfolio_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; SL_BUFFER = 0.10

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
dt = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
df["date"] = dt.dt.strftime("%Y-%m-%d")
df["mins_utc"] = dt.dt.hour * 60 + dt.dt.minute

# Per-day arrays for breakout
day_data = {}
for ds, sub in df.groupby("date", sort=True):
    day_data[ds] = {"bid": sub["bid"].to_numpy(), "ask": sub["ask"].to_numpy(),
                    "mins": sub["mins_utc"].to_numpy()}

def breakout_day(d, range_start, range_end, bo_start, day_close, tp_mult, sl_mult):
    mins, bid, ask = d["mins"], d["bid"], d["ask"]
    rm = (mins >= range_start) & (mins < range_end)
    if rm.sum() < 50: return None
    a_high = float(bid[rm].max()); a_low = float(bid[rm].min())
    a_range = a_high - a_low
    if a_range < 0.05: return None
    bm = (mins >= bo_start) & (mins < day_close)
    if bm.sum() < 50: return None
    bbid = bid[bm]; bask = ask[bm]
    above = bbid > a_high; below = bbid < a_low
    fa = int(np.argmax(above)) if above.any() else len(bbid)
    fb = int(np.argmax(below)) if below.any() else len(bbid)
    if fa >= len(bbid) and fb >= len(bbid): return None
    if fa < fb:
        bd = 1; bo = fa; bp = float(bask[bo])
    else:
        bd = -1; bo = fb; bp = float(bbid[bo])
    sl = bp - sl_mult*a_range if bd == 1 else bp + sl_mult*a_range
    tp = bp + tp_mult*a_range if bd == 1 else bp - tp_mult*a_range
    rb = bbid[bo:]; ra = bask[bo:]
    if bd == 1:
        sh = rb <= sl; th = rb >= tp
    else:
        sh = ra >= sl; th = ra <= tp
    sf = int(np.argmax(sh)) if sh.any() else len(rb)
    tf = int(np.argmax(th)) if th.any() else len(rb)
    if tf < sf: ex = tp
    elif sf < len(rb): ex = sl
    else: ex = float(rb[-1]) if bd == 1 else float(ra[-1])
    pnl_pts = (ex - bp) if bd == 1 else (bp - ex)
    return pnl_pts * 100 * LOTS - COMMISSION

# Run LB and NY
LB_CFG = {"range_start": 0, "range_end": 7*60, "bo_start": 7*60,
          "day_close": 21*60, "tp_mult": 1.0, "sl_mult": 1.0}
NY_CFG = {"range_start": 0, "range_end": 13*60, "bo_start": 13*60,
          "day_close": 21*60, "tp_mult": 1.5, "sl_mult": 1.0}

lb_pnl = {}  # date -> pnl
ny_pnl = {}
for ds in sorted(day_data):
    p = breakout_day(day_data[ds], **LB_CFG)
    if p is not None: lb_pnl[ds] = p
    p = breakout_day(day_data[ds], **NY_CFG)
    if p is not None: ny_pnl[ds] = p

# VSISA
df["m5_b"] = (df["time_msc"] // (300*1000)).astype(np.int64)
m5_grp = df.groupby("m5_b", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m5_b")
m5_grp["date"] = pd.to_datetime(m5_grp["ts_end_ms"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
m5 = m5_grp.to_dict("records")

def vsisa_thresh(idx, lb, big, low):
    if idx < lb: return float("inf"), float("inf")
    vs = sorted(m5[i]["v"] for i in range(idx-lb, idx) if m5[i]["v"] > 0)
    if not vs: return float("inf"), float("inf")
    return vs[int(len(vs)*big)], vs[int(len(vs)*low)]

vsisa_trades = []
for idx in range(100, len(m5)-1):
    e, r = m5[idx-1], m5[idx]
    if e["v"] == 0 or r["v"] == 0: continue
    big_v, low_v = vsisa_thresh(idx, 100, 0.50, 0.50)
    if e["v"] < big_v: continue
    if r["v"] >= low_v: continue
    e_dir = "up" if e["c"] > e["o"] else "dn"
    r_dir = "up" if r["c"] > r["o"] else "dn"
    if e_dir == r_dir: continue
    e_lo, e_hi = min(e["o"], e["c"]), max(e["o"], e["c"])
    r_lo, r_hi = min(r["o"], r["c"]), max(r["o"], r["c"])
    e_size = e_hi - e_lo
    if e_size <= 0: continue
    overlap = max(0.0, min(e_hi, r_hi) - max(e_lo, r_lo))
    if overlap / e_size < 0.50: continue
    if idx < 21: continue
    prior = sum(m5[i]["c"] for i in range(idx-21, idx-1)) / 20
    cur = m5[idx-1]["c"]
    if r_dir == "dn" and cur < prior: continue
    if r_dir == "up" and cur > prior: continue
    side = "sell" if r_dir == "dn" else "buy"
    entry = r["c"]
    sl = (r["h"] + SL_BUFFER) if side == "sell" else (r["l"] - SL_BUFFER)
    risk = abs(entry - sl)
    if risk < 0.05: continue
    tp = entry - 3.0*risk if side == "sell" else entry + 3.0*risk
    pnl = None
    for off in range(1, 61):
        if idx + off >= len(m5): break
        b = m5[idx + off]
        if side == "sell":
            if b["h"] >= sl: pnl = (entry-sl)*100*LOTS - COMMISSION; break
            if b["l"] <= tp: pnl = (entry-tp)*100*LOTS - COMMISSION; break
        else:
            if b["l"] <= sl: pnl = (sl-entry)*100*LOTS - COMMISSION; break
            if b["h"] >= tp: pnl = (tp-entry)*100*LOTS - COMMISSION; break
    if pnl is None:
        last = m5[min(idx+60, len(m5)-1)]
        move = (entry - last["c"]) if side == "sell" else (last["c"] - entry)
        pnl = move*100*LOTS - COMMISSION
    vsisa_trades.append({"date": r["date"], "pnl": pnl})

# Daily aggregation for VSISA
vsisa_daily = {}
for t in vsisa_trades:
    vsisa_daily[t["date"]] = vsisa_daily.get(t["date"], 0) + t["pnl"]

# Combine into daily series across all dates
all_dates = sorted(set(list(lb_pnl) + list(ny_pnl) + list(vsisa_daily)))
combined = []
for d in all_dates:
    lb = lb_pnl.get(d, 0)
    ny = ny_pnl.get(d, 0)
    vs = vsisa_daily.get(d, 0)
    combined.append({"date": d, "lb": lb, "ny": ny, "vsisa": vs, "total": lb + ny + vs})

print(f"\nDays with at least one trade: {len(combined)}")

# Stats per strategy
def stats_pnl_series(arr):
    arr = np.array(arr)
    if len(arr) == 0: return {"n": 0}
    pos = arr[arr > 0]; neg = arr[arr < 0]
    eq = arr.cumsum()
    dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n_days_traded": int((arr != 0).sum()),
            "win_days": int(len(pos)), "loss_days": int(len(neg)),
            "net": round(float(arr.sum()), 2),
            "avg": round(float(arr.mean()), 2),
            "best_day": round(float(arr.max()), 2),
            "worst_day": round(float(arr.min()), 2),
            "max_dd": round(dd, 2),
            "sharpe_daily": round(float(arr.mean() / arr.std()), 3) if arr.std() > 0 else 0}

print(f"\n=== INDIVIDUAL STRATEGY STATS (daily P&L series) ===")
print(f"{'strategy':>10} | {'days':>5} {'win/loss':>9} {'net':>10} {'avg':>7} {'best':>8} {'worst':>8} {'maxDD':>8} {'sharpe':>7}")
for label, key in [("LB", "lb"), ("NY", "ny"), ("VSISA", "vsisa"), ("COMBINED", "total")]:
    s = stats_pnl_series([c[key] for c in combined])
    print(f"{label:>10} | {s['n_days_traded']:>5} {s['win_days']}/{s['loss_days']:>5} {s['net']:>10.2f} {s['avg']:>7.2f} {s['best_day']:>8.2f} {s['worst_day']:>8.2f} {s['max_dd']:>8.2f} {s['sharpe_daily']:>7.3f}")

# Correlations between strategies (only days where both traded)
print(f"\n=== CORRELATIONS (days where both strategies traded) ===")
def corr(key_a, key_b):
    pairs = [(c[key_a], c[key_b]) for c in combined if c[key_a] != 0 and c[key_b] != 0]
    if len(pairs) < 5: return None, len(pairs)
    a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])
    return round(float(np.corrcoef(a, b)[0, 1]), 3), len(pairs)
for (la, ka), (lb, kb) in [(("LB", "lb"), ("NY", "ny")),
                            (("LB", "lb"), ("VSISA", "vsisa")),
                            (("NY", "ny"), ("VSISA", "vsisa"))]:
    c, n = corr(ka, kb)
    print(f"  {la} vs {lb}: corr={c if c is not None else 'n/a'} (n={n} overlapping days)")

# Save
doc = {"started": datetime.now(timezone.utc).isoformat(),
       "n_days": len(combined),
       "stats": {
           "lb": stats_pnl_series([c["lb"] for c in combined]),
           "ny": stats_pnl_series([c["ny"] for c in combined]),
           "vsisa": stats_pnl_series([c["vsisa"] for c in combined]),
           "combined": stats_pnl_series([c["total"] for c in combined]),
       },
       "daily_combined": combined}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
