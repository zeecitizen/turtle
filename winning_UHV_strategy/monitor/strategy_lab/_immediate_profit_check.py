"""For each post-Asian UHV entry yesterday, check tick-by-tick:
  - Time to first positive tick
  - PnL at +1s, +3s, +5s, +10s
  - Did it go negative first? How deep?
Uses bar-end timestamp matching what backtest actually used.
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
LOTS = 0.30; CONTRACT_SIZE = 100

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
ts_arr = df["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df["bid"].to_numpy(dtype=np.float64)
asks_arr = df["ask"].to_numpy(dtype=np.float64)

# Build M1 bars to get true ts_end_ms (last tick of each minute)
df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1_grp = df.groupby("m1", sort=True).agg(
    ts_end_ms=("time_msc", "last"),
).reset_index()
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
# Index by HH:MM:00 for lookup
m1_grp["minute_str"] = m1_grp["dt"].dt.strftime("%Y-%m-%d %H:%M")
ts_end_lookup = dict(zip(m1_grp["minute_str"], m1_grp["ts_end_ms"]))

ENTRIES = [
    {"time": "09:48", "side": "sell", "entry": 4739.16},
    {"time": "14:28", "side": "sell", "entry": 4731.43},
    {"time": "18:33", "side": "buy",  "entry": 4745.29},
]

for e in ENTRIES:
    side = e["side"]; entry_px = e["entry"]
    minute_key = f"2026-05-07 {e['time']}"
    entry_ts = int(ts_end_lookup.get(minute_key, 0))
    if entry_ts == 0:
        print(f"NO BAR for {minute_key}"); continue
    actual_dt = datetime.fromtimestamp(entry_ts/1000, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    end_ts = entry_ts + 30 * 1000
    i0 = int(np.searchsorted(ts_arr, entry_ts, side="left"))
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    sub_ts = ts_arr[i0:i1]
    sub_bids = bids_arr[i0:i1]
    sub_asks = asks_arr[i0:i1]
    n = len(sub_ts)
    print(f"\n=== {e['time']} {side.upper()} @ {entry_px:.2f}  (entry_ts={actual_dt}, {n} ticks in next 30s) ===", flush=True)

    first_positive_t = None
    min_pnl = 0; min_t = 0
    pnl_at = {0.5: None, 1.0: None, 3.0: None, 5.0: None, 10.0: None}
    went_negative_first = False
    for k in range(n):
        if side == "buy":
            cur = (sub_bids[k] - entry_px) * CONTRACT_SIZE * LOTS
        else:
            cur = (entry_px - sub_asks[k]) * CONTRACT_SIZE * LOTS
        elapsed = (sub_ts[k] - entry_ts) / 1000.0
        if elapsed < 0: continue
        if cur < min_pnl:
            min_pnl = cur; min_t = elapsed
        if first_positive_t is None and cur > 0:
            first_positive_t = elapsed
        if first_positive_t is None and cur < 0:
            went_negative_first = True
        for tgt in pnl_at.keys():
            if pnl_at[tgt] is None and elapsed >= tgt:
                pnl_at[tgt] = cur

    if first_positive_t is None:
        print(f"  Never positive in 30s window  ❌", flush=True)
    else:
        print(f"  First positive: {first_positive_t:.3f}s  ({'IMMEDIATELY' if first_positive_t < 0.5 else 'after dip' if went_negative_first else 'clean'})", flush=True)
    print(f"  Worst dip: ${min_pnl:+.2f} at {min_t:.2f}s", flush=True)
    for t, v in pnl_at.items():
        if v is not None:
            print(f"  PnL @ +{t}s : ${v:+.2f}", flush=True)
