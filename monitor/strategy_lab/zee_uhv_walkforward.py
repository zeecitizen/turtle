"""Walk-forward validation: did v3 results overfit?

Method:
  1. Split 86 days into TRAIN (first 60) + TEST (last 26)
  2. On TRAIN: run strict v2, find hours with WR ≥ 70% AND net > 0
  3. On TEST: apply strict v2 entry + those hour filters ONLY
  4. Report TEST result (the unbiased number)

If TEST net is still positive, the strategy generalizes. If negative, it was curve-fit.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_uhv_walkforward.json")

LOTS = 0.10; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100
UHV_LOOKBACK = 20; UHV_MAX_AGE_BARS = 10; RECENT_AVG_BARS = 20
UHV_MIN_VOL_MULT = 2.0
MAX_OPPOSING_WICK = 0.25
MIN_BODY_PCT = 0.80
MAX_VOL_RATIO = 0.40
MIN_SPACING_SEC = 60
DAILY_LOSS_USD = 100.0
EXIT = {"trail_trigger": 10, "trail_drop": 3, "catastrophic_usd": 30, "scratch_sec": 30, "max_hold_min": 10}
WINNING_HOUR_MIN_WR = 70  # %
WINNING_HOUR_MIN_TRADES = 2

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
        return {"side": "buy", "ts_end_ms": cur["ts_end_ms"], "hour": cur["hour"], "date": cur["date"]}
    else:
        if cur["c"] >= uhv["l"]: return None
        if (cur["c"] - cur["l"]) / rng > MAX_OPPOSING_WICK: return None
        return {"side": "sell", "ts_end_ms": cur["ts_end_ms"], "hour": cur["hour"], "date": cur["date"]}


def fill(sig):
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    if i0 >= len(ts_arr): return None
    if sig["side"] == "buy": return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def walk(side, fi, entry_price, entry_ts, cfg):
    end_ts = entry_ts + cfg["max_hold_min"] * 60 * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9; has_pos = False; armed = False; cur_pnl = 0
    for k in range(fi + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy": cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:             cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        peak = max(peak, cur_pnl)
        if cur_pnl > 0: has_pos = True
        if cur_pnl <= -cfg["catastrophic_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "peak": peak}
        if not armed and peak >= cfg["trail_trigger"]: armed = True
        if armed and (peak - cur_pnl) >= cfg["trail_drop"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TRAIL", "peak": peak}
        if not has_pos and elapsed > cfg["scratch_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SCRATCH", "peak": peak}
    return {"pnl": cur_pnl - COMMISSION, "reason": "TIMEOUT", "peak": peak}


def run_window(date_lo, date_hi, hours_set=None):
    """Run on bars whose date is in [date_lo, date_hi). If hours_set is None, all hours."""
    trades = []; last_entry = 0; daily = {}; halted = set()
    for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + 5, len(m1)):
        bar = m1[idx]; date = bar["date"]
        if date < date_lo or date >= date_hi: continue
        if bar["hour"] < 6: continue  # Sydney
        if hours_set is not None and bar["hour"] not in hours_set: continue
        if date in halted: continue
        if daily.get(date, 0) <= -DAILY_LOSS_USD: halted.add(date); continue
        if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
        sig = detect(idx)
        if not sig: continue
        f = fill(sig)
        if not f: continue
        fi, fp, ft = f
        r = walk(sig["side"], fi, fp, ft, EXIT)
        daily[date] = daily.get(date, 0) + r["pnl"]
        trades.append({"date": date, "hour": sig["hour"], "side": sig["side"],
                       "pnl": round(r["pnl"], 2), "reason": r["reason"], "peak": round(r["peak"], 2)})
        last_entry = ft
    return trades, daily, halted


# Determine train/test split
dates = sorted(set(b["date"] for b in m1))
print(f"  Total dates: {len(dates)}  ({dates[0]} .. {dates[-1]})", flush=True)
split_idx = int(len(dates) * 0.70)
train_lo = dates[0]
train_hi = dates[split_idx]   # exclusive
test_lo  = dates[split_idx]
test_hi  = (datetime.strptime(dates[-1], "%Y-%m-%d").replace(day=datetime.strptime(dates[-1], "%Y-%m-%d").day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

print(f"  TRAIN: {train_lo} .. {train_hi}  ({split_idx} days)", flush=True)
print(f"  TEST:  {test_lo} .. (end)        ({len(dates) - split_idx} days)", flush=True)

# === STEP 1: Run all-hours on TRAIN, build per-hour stats ===
print(f"\n[TRAIN] all-hour run (find winning hours)...", flush=True)
train_trades, train_daily, train_halted = run_window(train_lo, train_hi, hours_set=None)
print(f"  Train trades: {len(train_trades)}", flush=True)

# Per-hour aggregation
by_hr = {}
for t in train_trades:
    by_hr.setdefault(t["hour"], []).append(t)

print(f"\n  TRAIN per-hour:", flush=True)
print(f"  {'Hr':>4} {'n':>4} {'WR%':>5} {'Net':>9}", flush=True)
winning_hours = set()
for hr in sorted(by_hr):
    ts = by_hr[hr]
    w = sum(1 for t in ts if t["pnl"] > 0)
    net = sum(t["pnl"] for t in ts)
    wr = w / len(ts) * 100
    marker = " ⭐" if wr >= WINNING_HOUR_MIN_WR and len(ts) >= WINNING_HOUR_MIN_TRADES and net > 0 else ""
    print(f"  {hr:>4} {len(ts):>4} {wr:>4.0f}% ${net:>+8.2f}{marker}", flush=True)
    if wr >= WINNING_HOUR_MIN_WR and len(ts) >= WINNING_HOUR_MIN_TRADES and net > 0:
        winning_hours.add(hr)

print(f"\n  Selected winning hours (train-derived): {sorted(winning_hours)}", flush=True)

# === STEP 2: Apply those hours on TEST ===
print(f"\n[TEST] apply train-derived winning hours on never-seen data...", flush=True)
test_trades, test_daily, test_halted = run_window(test_lo, test_hi, hours_set=winning_hours)
if not test_trades:
    print(f"  No trades on TEST window — filter too strict")
    result_summary = {"verdict": "NO_TRADES_TEST", "winning_hours_train": sorted(winning_hours)}
else:
    n = len(test_trades)
    wins = sum(1 for t in test_trades if t["pnl"] > 0)
    net = sum(t["pnl"] for t in test_trades)
    days_p = sum(1 for p in test_daily.values() if p > 0)
    days_l = sum(1 for p in test_daily.values() if p < 0)
    verdict = "GENERALIZES" if net > 0 else "OVERFIT"
    print(f"  n={n}  WR={wins/n*100:.1f}%  NET=${net:+.2f}", flush=True)
    print(f"  days: profit={days_p}/{len(test_daily)}  loss={days_l}  halted={len(test_halted)}", flush=True)
    print(f"\n  ===> VERDICT: {verdict}", flush=True)
    if net > 0:
        print(f"  ✅ Strategy generalizes to out-of-sample data.", flush=True)
        print(f"     Avg per trade: ${net/n:+.2f}   Trades/day: {n/(len(dates)-split_idx):.2f}", flush=True)
    else:
        print(f"  ❌ Winning hours from train don't hold on test — likely curve-fit.", flush=True)
    result_summary = {
        "verdict": verdict, "winning_hours_train": sorted(winning_hours),
        "test_n": n, "test_wr_pct": round(wins/n*100, 1), "test_net_usd": round(net, 2),
        "test_days_profit": days_p, "test_days_loss": days_l,
        "test_daily_pnl": {d: round(p, 2) for d, p in sorted(test_daily.items())},
    }

OUT_J.write_text(json.dumps({
    "started": datetime.now(timezone.utc).isoformat(),
    "train_period": f"{train_lo} .. {train_hi}",
    "test_period":  f"{test_lo} .. end",
    "result": result_summary,
}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
