"""Walk-forward on SIGNAL DIRECTION (decoupled from exit).

Question: do "100% directional within 30s" hours from train hold on test?

Method:
  1. Train (first 60 days): for each hour, count % of strict-v2 signals that went positive within 30s
  2. Select hours with ≥ 75% positive AND n ≥ 3
  3. Test (last 26 days): re-measure same hours' directional accuracy
  4. If test direction stays ≥ 70%, we have a real signal-quality edge → can solve exit separately
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_direction_walkforward.json")

LOTS = 0.10; CONTRACT_SIZE = 100
UHV_LOOKBACK = 20; UHV_MAX_AGE_BARS = 10; RECENT_AVG_BARS = 20
UHV_MIN_VOL_MULT = 2.0
MAX_OPPOSING_WICK = 0.25
MIN_BODY_PCT = 0.80
MAX_VOL_RATIO = 0.40
MIN_SPACING_SEC = 60
WINDOW_SEC = 30
TRAIN_MIN_PCT = 75
TRAIN_MIN_N = 3

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


def directional_outcome(side, fill_idx, entry_price, entry_ts):
    """Did P&L go positive at any point within WINDOW_SEC after fill?"""
    end_ts = entry_ts + WINDOW_SEC * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    max_pnl = -1e9
    for k in range(fill_idx + 1, i1):
        if side == "buy":
            cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:
            cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        if cur_pnl > max_pnl: max_pnl = cur_pnl
        if cur_pnl > 0: return True, max_pnl
    return False, max_pnl


def collect_signals(date_lo, date_hi):
    out = []
    last_entry = 0
    for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + 5, len(m1)):
        bar = m1[idx]; date = bar["date"]
        if date < date_lo or date >= date_hi: continue
        if bar["hour"] < 6: continue
        if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
        sig = detect(idx)
        if not sig: continue
        i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
        if i0 >= len(ts_arr): continue
        entry_price = asks_arr[i0] if sig["side"] == "buy" else bids_arr[i0]
        entry_ts = int(ts_arr[i0])
        went_pos, max_pnl = directional_outcome(sig["side"], i0, entry_price, entry_ts)
        out.append({"date": sig["date"], "hour": sig["hour"], "side": sig["side"],
                    "went_positive": went_pos, "max_pnl": round(max_pnl, 2)})
        last_entry = entry_ts
    return out


dates = sorted(set(b["date"] for b in m1))
split = int(len(dates) * 0.70)
train_lo, train_hi = dates[0], dates[split]
test_lo,  test_hi  = dates[split], "9999-99-99"

print(f"\nTRAIN: {train_lo}..{train_hi}  ({split} days)", flush=True)
print(f"TEST:  {test_lo}..(end)        ({len(dates)-split} days)", flush=True)

# === TRAIN: per-hour positivity ===
train_sigs = collect_signals(train_lo, train_hi)
print(f"\nTRAIN signals: {len(train_sigs)}", flush=True)
by_hr = {}
for s in train_sigs:
    by_hr.setdefault(s["hour"], []).append(s)

print(f"\n  TRAIN per-hour direction:", flush=True)
print(f"  {'hr':>4} {'n':>4} {'%pos':>6}", flush=True)
selected_hours = set()
for hr in sorted(by_hr):
    ss = by_hr[hr]
    pct = sum(1 for s in ss if s["went_positive"]) / len(ss) * 100
    mk = " ⭐" if pct >= TRAIN_MIN_PCT and len(ss) >= TRAIN_MIN_N else ""
    print(f"  {hr:>4} {len(ss):>4} {pct:>5.0f}%{mk}", flush=True)
    if pct >= TRAIN_MIN_PCT and len(ss) >= TRAIN_MIN_N:
        selected_hours.add(hr)

print(f"\n  Selected hours: {sorted(selected_hours)}", flush=True)

# === TEST: how do those hours perform out-of-sample? ===
test_sigs = collect_signals(test_lo, test_hi)
print(f"\nTEST signals (all hours): {len(test_sigs)}", flush=True)
test_filtered = [s for s in test_sigs if s["hour"] in selected_hours]

if not test_filtered:
    print(f"\n  No TEST signals in selected hours")
    test_pct = None; verdict = "NO_TRADES"
else:
    test_pos = sum(1 for s in test_filtered if s["went_positive"])
    test_pct = test_pos / len(test_filtered) * 100
    verdict = "GENERALIZES" if test_pct >= 70 else "OVERFIT"
    print(f"\n  TEST direction in selected hours:", flush=True)
    print(f"  n={len(test_filtered)}  positive={test_pos}  pct={test_pct:.1f}%   verdict={verdict}", flush=True)
    print(f"\n  Per-hour TEST breakdown:", flush=True)
    by_hr_t = {}
    for s in test_filtered:
        by_hr_t.setdefault(s["hour"], []).append(s)
    for hr in sorted(by_hr_t):
        ss = by_hr_t[hr]
        pct = sum(1 for s in ss if s["went_positive"]) / len(ss) * 100
        print(f"    hr={hr:>2}  n={len(ss):>3}  %pos={pct:>5.0f}%", flush=True)

# Compare test ALL HOURS vs FILTERED
if test_sigs:
    test_all_pos = sum(1 for s in test_sigs if s["went_positive"])
    print(f"\n  TEST baseline (all hours): n={len(test_sigs)}  positive={test_all_pos}  pct={test_all_pos/len(test_sigs)*100:.1f}%", flush=True)

OUT_J.write_text(json.dumps({
    "started": datetime.now(timezone.utc).isoformat(),
    "train_period": f"{train_lo}..{train_hi}", "test_period": f"{test_lo}..end",
    "selected_hours_train": sorted(selected_hours),
    "test_pct_in_selected_hours": round(test_pct, 1) if test_pct is not None else None,
    "test_n_in_selected_hours": len(test_filtered) if test_filtered else 0,
    "test_baseline_pct_all_hours": round(sum(1 for s in test_sigs if s["went_positive"])/max(1,len(test_sigs))*100, 1) if test_sigs else None,
    "verdict": verdict,
}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
