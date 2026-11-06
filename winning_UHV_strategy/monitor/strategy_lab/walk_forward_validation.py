"""Walk-forward validation: rolling window train/test for LB, NY, VSISA strategies.

For each strategy:
  - Walk through 120-day data with rolling windows
  - Train period: 60 days
  - Test period: 30 days
  - Step: 30 days
  - Yields ~3 train/test pairs
  - Strategy is robust if ALL test periods are positive

Each strategy uses the BEST config from the prior backtest.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_walk_forward_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100; SL_BUFFER = 0.10

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
dt_full = pd.to_datetime(df["time_msc"], unit="ms", utc=True)
df["date"] = dt_full.dt.strftime("%Y-%m-%d")
df["mins_utc"] = dt_full.dt.hour * 60 + dt_full.dt.minute
all_dates = sorted(df["date"].unique())
print(f"[LOAD] {len(df):,} ticks, {len(all_dates)} days", flush=True)

# Per-day arrays for breakout strategies
day_data = {}
for date_str, sub in df.groupby("date", sort=True):
    day_data[date_str] = {
        "bid": sub["bid"].to_numpy(), "ask": sub["ask"].to_numpy(),
        "mins": sub["mins_utc"].to_numpy(),
    }

# === Breakout strategy (parameterized) ===
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
    if tf < sf: ex = tp; rs = "TP"
    elif sf < len(rb): ex = sl; rs = "SL"
    else:
        ex = float(rb[-1]) if bd == 1 else float(ra[-1])
        rs = "TIME"
    pnl_pts = (ex - bp) if bd == 1 else (bp - ex)
    pnl = pnl_pts * 100 * LOTS - COMMISSION
    return {"pnl": round(pnl, 2), "exit_reason": rs, "side": "buy" if bd == 1 else "sell"}

def stats(trades):
    if not trades: return {"n": 0}
    arr = np.array([t["pnl"] for t in trades])
    wins = arr[arr > 0]; losses = arr[arr < 0]
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(arr), "wr": round(100*len(wins)/len(arr),2),
            "pf": round(float(wins.sum()/-losses.sum()),2) if len(losses) and losses.sum() else None,
            "net": round(float(arr.sum()),2), "avg": round(float(arr.mean()),2),
            "max_dd": round(dd, 2)}

# === LB walk-forward ===
LB_CFG = {"range_start": 0, "range_end": 7*60, "bo_start": 7*60,
          "day_close": 21*60, "tp_mult": 1.0, "sl_mult": 1.0}
NY_CFG = {"range_start": 0, "range_end": 13*60, "bo_start": 13*60,
          "day_close": 21*60, "tp_mult": 1.5, "sl_mult": 1.0}

def walk_forward(strategy_fn, cfg, label):
    """Walk through dates with 60d train / 30d test, step 30d."""
    print(f"\n=== {label} WALK-FORWARD ===", flush=True)
    print(f"{'window':>30} | {'train':>30} | {'test':>30}", flush=True)
    windows = []
    train_size, test_size, step = 45, 15, 10
    i = 0
    while i + train_size + test_size <= len(all_dates):
        train_dates = all_dates[i:i+train_size]
        test_dates = all_dates[i+train_size:i+train_size+test_size]
        train_trades = []
        test_trades = []
        for d in train_dates:
            r = strategy_fn(day_data[d], **cfg) if d in day_data else None
            if r: train_trades.append(r)
        for d in test_dates:
            r = strategy_fn(day_data[d], **cfg) if d in day_data else None
            if r: test_trades.append(r)
        s_trn = stats(train_trades); s_tst = stats(test_trades)
        windows.append({"train_start": train_dates[0], "test_start": test_dates[0],
                        "test_end": test_dates[-1], "train": s_trn, "test": s_tst})
        win_label = f"{train_dates[0]}→{test_dates[-1]}"
        trn_str = f"n={s_trn['n']:>2} pf={str(s_trn.get('pf')):>5} net=${s_trn.get('net',0):>+8.2f}"
        tst_str = f"n={s_tst['n']:>2} pf={str(s_tst.get('pf')):>5} net=${s_tst.get('net',0):>+8.2f}"
        marker = " ✅" if s_tst.get('net', 0) > 0 else " ❌"
        print(f"{win_label:>30} | {trn_str:>30} | {tst_str:>30}{marker}", flush=True)
        i += step
    if windows:
        positive_tests = sum(1 for w in windows if w["test"].get("net", 0) > 0)
        print(f"\n  Positive test windows: {positive_tests}/{len(windows)}", flush=True)
    return windows

lb_windows = walk_forward(breakout_day, LB_CFG, "LONDON BREAKOUT")
ny_windows = walk_forward(breakout_day, NY_CFG, "NY BREAKOUT")

# === VSISA walk-forward ===
print("\n=== VSISA M5 — building bars ===", flush=True)
df["m5_bucket"] = (df["time_msc"] // (300*1000)).astype(np.int64)
m5_grp = df.groupby("m5_bucket", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m5_bucket")
m5_dt = pd.to_datetime(m5_grp["ts_end_ms"], unit="ms", utc=True)
m5_grp["date"] = m5_dt.dt.strftime("%Y-%m-%d")
m5 = m5_grp.to_dict("records")
print(f"M5 bars: {len(m5)}", flush=True)

def vsisa_session_thresholds(idx, lb, big, low):
    if idx < lb: return float("inf"), float("inf")
    vs = sorted(m5[i]["v"] for i in range(idx-lb, idx) if m5[i]["v"] > 0)
    if not vs: return float("inf"), float("inf")
    return vs[int(len(vs)*big)], vs[int(len(vs)*low)]

def vsisa_detect(idx, big_pct, low_pct, body_cov, lookback, require_prior):
    if idx < lookback: return None
    e, r = m5[idx-1], m5[idx]
    if e["v"] == 0 or r["v"] == 0: return None
    big_v, low_v = vsisa_session_thresholds(idx, lookback, big_pct, low_pct)
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
    if overlap / e_size < body_cov: return None
    if require_prior:
        if idx < 21: return None
        prior = sum(m5[i]["c"] for i in range(idx-21, idx-1)) / 20
        cur = m5[idx-1]["c"]
        if r_dir == "dn" and cur < prior: return None
        if r_dir == "up" and cur > prior: return None
    return ("sell" if r_dir == "dn" else "buy", idx)

def vsisa_simulate(idx, side, tp_r, max_bars=60):
    r = m5[idx]
    entry = r["c"]
    sl = (r["h"] + SL_BUFFER) if side == "sell" else (r["l"] - SL_BUFFER)
    risk = abs(entry - sl)
    if risk < 0.05: return None
    tp = entry - tp_r * risk if side == "sell" else entry + tp_r * risk
    for off in range(1, max_bars + 1):
        i = idx + off
        if i >= len(m5): break
        b = m5[i]
        if side == "sell":
            if b["h"] >= sl: return {"pnl": (entry-sl)*100*LOTS - COMMISSION, "reason": "SL"}
            if b["l"] <= tp: return {"pnl": (entry-tp)*100*LOTS - COMMISSION, "reason": "TP"}
        else:
            if b["l"] <= sl: return {"pnl": (sl-entry)*100*LOTS - COMMISSION, "reason": "SL"}
            if b["h"] >= tp: return {"pnl": (tp-entry)*100*LOTS - COMMISSION, "reason": "TP"}
    last = m5[min(idx + max_bars, len(m5)-1)]
    move = (entry - last["c"]) if side == "sell" else (last["c"] - entry)
    return {"pnl": move*100*LOTS - COMMISSION, "reason": "TIME"}

VSISA_CFG = {"big_pct": 0.50, "low_pct": 0.50, "body_cov": 0.50,
             "tp_r": 3.0, "lookback": 100, "require_prior": True}

def vsisa_walk_forward():
    print("\n=== VSISA M5 WALK-FORWARD ===", flush=True)
    print(f"{'window':>30} | {'train':>30} | {'test':>30}", flush=True)
    train_size, test_size, step = 45, 15, 10
    windows = []
    # Pre-compute all signals across all bars
    all_signals = []
    for idx in range(VSISA_CFG["lookback"], len(m5)-1):
        sig = vsisa_detect(idx, VSISA_CFG["big_pct"], VSISA_CFG["low_pct"],
                            VSISA_CFG["body_cov"], VSISA_CFG["lookback"], VSISA_CFG["require_prior"])
        if sig:
            side, _ = sig
            r = vsisa_simulate(idx, side, VSISA_CFG["tp_r"])
            if r:
                r["date"] = m5[idx]["date"]; r["side"] = side
                all_signals.append(r)
    print(f"  Total signals across full window: {len(all_signals)}", flush=True)
    i = 0
    while i + train_size + test_size <= len(all_dates):
        trn_set = set(all_dates[i:i+train_size])
        tst_set = set(all_dates[i+train_size:i+train_size+test_size])
        trn = [s for s in all_signals if s["date"] in trn_set]
        tst = [s for s in all_signals if s["date"] in tst_set]
        s_trn = stats(trn); s_tst = stats(tst)
        win_label = f"{all_dates[i]}→{all_dates[i+train_size+test_size-1]}"
        trn_str = f"n={s_trn['n']:>3} pf={str(s_trn.get('pf')):>5} net=${s_trn.get('net',0):>+8.2f}"
        tst_str = f"n={s_tst['n']:>3} pf={str(s_tst.get('pf')):>5} net=${s_tst.get('net',0):>+8.2f}"
        marker = " ✅" if s_tst.get('net', 0) > 0 else " ❌"
        print(f"{win_label:>30} | {trn_str:>30} | {tst_str:>30}{marker}", flush=True)
        windows.append({"train_start": all_dates[i],
                         "test_end": all_dates[i+train_size+test_size-1],
                         "train": s_trn, "test": s_tst})
        i += step
    if windows:
        pos = sum(1 for w in windows if w["test"].get("net", 0) > 0)
        print(f"\n  Positive test windows: {pos}/{len(windows)}", flush=True)
    return windows

vsisa_windows = vsisa_walk_forward()

doc = {"started": datetime.now(timezone.utc).isoformat(),
       "lb_windows": lb_windows, "ny_windows": ny_windows,
       "vsisa_windows": vsisa_windows}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
