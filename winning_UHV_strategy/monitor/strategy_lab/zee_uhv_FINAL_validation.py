"""FINAL validation of UHV strategy with all learnings:

  Entry rules (strict v2):
    - vol_ratio ≤ 0.40, body% ≥ 0.80, UHV vol ≥ 2× recent avg, opposing wick ≤ 25%
  Time window: 08-12 UTC + 19-23 UTC (Munich-local 10-14 + 21-01)
  Exit: tight $2 TP / $5 SL / 5-second kill (matches sub-second peak capture)
  Daily loss limit: $50 (lower than before since stakes are smaller)
  Min spacing: 60s

Walk-forward split: train 70% / test 30%.
Report TRAIN performance + TEST performance + PER-DAY breakdown.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_uhv_FINAL.json")

LOTS = 0.10; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100
UHV_LOOKBACK = 20; UHV_MAX_AGE_BARS = 10; RECENT_AVG_BARS = 20
UHV_MIN_VOL_MULT = 2.0
MAX_OPPOSING_WICK = 0.25
MIN_BODY_PCT = 0.80
MAX_VOL_RATIO = 0.40
MIN_SPACING_SEC = 60
DAILY_LOSS_USD = 50.0
WINNING_HOURS = {8, 9, 10, 11, 19, 20, 21, 22}  # 08-12 UTC + 19-23 UTC

# TIGHT exits — capture small wins quickly, cut losses fast
TP_USD = 2.0
SL_USD = 5.0
KILL_SEC = 5

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1_grp = df.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1_grp["hour"] = m1_grp["dt"].dt.hour
m1 = m1_grp.to_dict("records")
ts_arr = df["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df["bid"].to_numpy(dtype=np.float64)
asks_arr = df["ask"].to_numpy(dtype=np.float64)


def detect(idx):
    if idx < UHV_LOOKBACK + RECENT_AVG_BARS + 5: return None
    win_lo = idx - UHV_LOOKBACK
    uhv_idx = max(range(win_lo, idx), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] <= 0 or (idx - uhv_idx) > UHV_MAX_AGE_BARS: return None
    rv = [m1[j]["v"] for j in range(max(0, uhv_idx - RECENT_AVG_BARS), uhv_idx) if j != uhv_idx]
    if not rv: return None
    if uhv["v"] < UHV_MIN_VOL_MULT * (sum(rv) / len(rv)): return None
    cur = m1[idx]
    if cur["v"] / uhv["v"] > MAX_VOL_RATIO: return None
    rng = cur["h"] - cur["l"]
    if rng <= 0: return None
    body = abs(cur["c"] - cur["o"])
    if body / rng < MIN_BODY_PCT: return None
    is_red = uhv["c"] < uhv["o"]; is_green = uhv["c"] > uhv["o"]
    if not (is_red or is_green): return None
    if is_red:
        if cur["c"] <= uhv["h"]: return None
        if (cur["h"] - cur["c"]) / rng > MAX_OPPOSING_WICK: return None
        side = "buy"
    else:
        if cur["c"] >= uhv["l"]: return None
        if (cur["c"] - cur["l"]) / rng > MAX_OPPOSING_WICK: return None
        side = "sell"
    return {"side": side, "ts_end_ms": cur["ts_end_ms"], "hour": cur["hour"], "date": cur["date"]}


def fill(sig):
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    if i0 >= len(ts_arr): return None
    if sig["side"] == "buy": return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def walk_tight(side, fi, entry_price, entry_ts):
    end_ts = entry_ts + (KILL_SEC + 5) * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9; cur_pnl = 0
    for k in range(fi + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy": cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:             cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        peak = max(peak, cur_pnl)
        if cur_pnl <= -SL_USD:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "age": elapsed, "peak": peak}
        if cur_pnl >= TP_USD:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TP", "age": elapsed, "peak": peak}
        if elapsed >= KILL_SEC:
            return {"pnl": cur_pnl - COMMISSION, "reason": "KILL", "age": elapsed, "peak": peak}
    return {"pnl": cur_pnl - COMMISSION, "reason": "OUT", "age": KILL_SEC, "peak": peak}


def run(date_lo, date_hi):
    trades = []; last_entry = 0; daily = {}; halted = set()
    for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + 5, len(m1)):
        bar = m1[idx]; date = bar["date"]
        if date < date_lo or date >= date_hi: continue
        if bar["hour"] not in WINNING_HOURS: continue
        if date in halted: continue
        if daily.get(date, 0) <= -DAILY_LOSS_USD: halted.add(date); continue
        if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
        sig = detect(idx)
        if not sig: continue
        f = fill(sig)
        if not f: continue
        fi, fp, ft = f
        r = walk_tight(sig["side"], fi, fp, ft)
        daily[date] = daily.get(date, 0) + r["pnl"]
        trades.append({"date": date, "hour": sig["hour"], "side": sig["side"],
                       "pnl": round(r["pnl"], 2), "reason": r["reason"], "age": round(r["age"], 1), "peak": round(r["peak"], 2)})
        last_entry = ft
    return trades, daily, halted


def report(label, trades, daily, halted):
    n = len(trades)
    print(f"\n{label}", flush=True)
    if n == 0:
        print("  No trades")
        return {"label": label, "n": 0}
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    net = sum(t["pnl"] for t in trades)
    avg = net / n
    days_p = sum(1 for p in daily.values() if p > 0)
    days_l = sum(1 for p in daily.values() if p < 0)
    reasons = {}
    for t in trades: reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    print(f"  n={n}  WR={wins/n*100:.1f}% ({wins}W / {losses}L)", flush=True)
    print(f"  NET=${net:+.2f}  avg=${avg:+.2f}", flush=True)
    print(f"  days: profit={days_p}/{len(daily)}  loss={days_l}  halted={len(halted)}", flush=True)
    print(f"  reasons: {reasons}", flush=True)
    return {"label": label, "n": n, "wins": wins, "losses": losses,
            "wr_pct": round(wins/n*100, 1), "net_usd": round(net, 2), "avg_usd": round(avg, 2),
            "days_profit": days_p, "days_loss": days_l, "days_halted": len(halted),
            "reasons": reasons,
            "daily_pnl": {d: round(p, 2) for d, p in sorted(daily.items())}}


dates = sorted(set(b["date"] for b in m1))
split = int(len(dates) * 0.70)
train_lo, train_hi = dates[0], dates[split]
test_lo,  test_hi  = dates[split], "9999-99-99"

print(f"\nFINAL VALIDATION", flush=True)
print(f"Entry: strict v2 (vol≤0.40, body≥0.80, UHV vol≥2× recent, wick≤25%)", flush=True)
print(f"Hours: 08-12 + 19-23 UTC (London open + NY late)", flush=True)
print(f"Exit:  TP=${TP_USD}  SL=${SL_USD}  kill={KILL_SEC}s", flush=True)
print(f"Daily halt: ${DAILY_LOSS_USD}  Lots: {LOTS}", flush=True)

print(f"\nTRAIN: {train_lo} .. {train_hi}", flush=True)
tr_trades, tr_daily, tr_halted = run(train_lo, train_hi)
tr_summary = report("TRAIN", tr_trades, tr_daily, tr_halted)

print(f"\nTEST: {test_lo} .. (end)", flush=True)
te_trades, te_daily, te_halted = run(test_lo, test_hi)
te_summary = report("TEST", te_trades, te_daily, te_halted)

print(f"\nFULL: {train_lo} .. (end)", flush=True)
full_trades, full_daily, full_halted = run(train_lo, "9999-99-99")
full_summary = report("FULL", full_trades, full_daily, full_halted)

OUT_J.write_text(json.dumps({
    "started": datetime.now(timezone.utc).isoformat(),
    "config": {"tp_usd": TP_USD, "sl_usd": SL_USD, "kill_sec": KILL_SEC,
               "winning_hours": sorted(WINNING_HOURS), "lots": LOTS,
               "daily_loss_usd": DAILY_LOSS_USD},
    "train": tr_summary, "test": te_summary, "full": full_summary,
}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
