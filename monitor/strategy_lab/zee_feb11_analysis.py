"""Analyze Zee's actual Feb 11 2026 trade history and overlay on parquet ticks.

Goal: identify the EXACT pattern that produced 65 wins / 4 losses (94% WR).
Per-setup analysis: group bursts by minute, examine M1 bar context.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

# Raw trade data parsed from PDF — all BlueberryMarkets-Live02, Feb 11 2026
# Times are BROKER server time (EET = UTC+2 in winter)
TRADES_RAW = """
01:32:19,buy,5045.07,01:47:30,5045.94,7.32
01:32:20,buy,5045.02,01:47:30,5045.94,7.74
01:59:04,buy,5042.17,02:00:43,5042.96,6.65
01:59:04,buy,5042.17,02:00:43,5042.96,6.65
02:09:38,sell,5040.68,02:10:18,5039.29,11.69
02:09:39,sell,5040.61,02:10:18,5039.25,11.44
02:29:02,buy,5039.03,02:30:28,5041.41,20.01
02:29:02,buy,5039.03,02:30:28,5041.41,20.01
16:49:07,buy,5047.93,16:51:03,5049.96,17.12
16:49:07,buy,5047.90,16:51:03,5049.85,16.45
16:49:07,buy,5047.24,16:51:03,5049.96,22.95
16:52:21,buy,5050.77,16:52:27,5051.82,8.85
16:54:10,buy,5056.74,16:54:20,5057.72,8.26
16:54:10,buy,5056.59,16:54:20,5057.71,9.44
16:58:03,buy,5064.26,16:58:27,5064.94,5.73
16:58:03,buy,5064.31,16:58:27,5064.93,5.23
16:58:03,buy,5064.29,16:58:27,5064.94,5.48
17:02:45,buy,5055.71,17:03:51,5062.23,54.93
17:02:46,buy,5056.24,17:03:51,5062.23,50.47
17:02:47,buy,5056.52,17:03:51,5062.23,48.11
17:36:11,buy,5056.53,17:36:26,5056.92,3.29
17:36:11,buy,5056.53,17:36:26,5056.92,3.29
17:36:13,buy,5057.05,17:52:56,5058.77,14.50
17:37:26,buy,5045.82,17:40:02,5046.66,7.08
17:37:27,buy,5045.33,17:40:02,5046.66,11.22
17:49:59,buy,5048.32,17:52:33,5054.58,52.78
17:49:59,buy,5048.37,17:52:33,5054.57,52.27
17:49:59,buy,5048.38,17:52:33,5054.56,52.10
18:24:18,buy,5059.26,18:28:33,5060.27,8.51
18:24:19,buy,5059.39,18:28:33,5060.27,7.42
18:24:19,buy,5059.42,18:28:33,5060.27,7.16
18:41:50,buy,5078.10,19:06:41,5077.93,-1.43
18:41:50,buy,5078.12,19:06:41,5077.93,-1.60
18:41:50,buy,5078.11,19:06:41,5077.93,-1.51
18:41:51,buy,5078.02,19:06:41,5077.93,-0.76
18:41:51,buy,5077.91,19:06:41,5077.93,0.17
18:41:51,buy,5077.91,19:06:41,5077.93,0.17
19:08:59,sell,5083.28,19:09:08,5082.35,7.82
19:08:59,sell,5083.24,19:09:08,5082.35,7.49
19:08:59,sell,5083.16,19:09:08,5082.35,6.82
19:08:59,sell,5083.17,19:09:08,5082.29,7.40
19:11:05,sell,5083.39,19:11:27,5083.02,3.11
19:11:05,sell,5083.31,19:11:27,5083.02,2.44
19:11:06,sell,5083.30,19:11:27,5083.02,2.36
19:11:51,sell,5083.79,19:19:10,5081.77,16.99
19:11:51,sell,5083.79,19:19:10,5081.77,16.99
19:11:52,sell,5083.75,19:19:10,5081.77,16.66
19:11:52,sell,5083.75,19:19:10,5081.77,16.66
19:20:34,sell,5084.21,19:20:40,5082.52,14.21
19:20:34,sell,5084.24,19:20:40,5082.52,14.47
19:20:34,sell,5084.21,19:20:40,5082.52,14.21
19:20:35,sell,5084.15,19:20:40,5082.52,13.71
19:26:06,sell,5089.16,19:26:50,5087.43,14.55
19:26:06,sell,5089.38,19:26:50,5087.43,16.40
19:26:06,sell,5089.41,19:26:50,5087.43,16.65
19:29:31,buy,5086.34,19:39:03,5086.44,0.84
19:29:31,buy,5086.34,19:39:03,5086.44,0.84
19:29:32,buy,5086.34,19:39:03,5086.44,0.84
19:32:48,buy,5084.71,19:37:34,5085.41,5.89
19:32:48,buy,5084.83,19:37:34,5085.41,4.88
19:36:19,buy,5082.91,19:37:19,5084.17,10.60
19:36:19,buy,5082.93,19:37:19,5084.17,10.43
19:38:39,buy,5083.28,19:38:50,5084.59,11.02
19:38:59,buy,5086.33,19:39:03,5086.44,0.92
19:38:59,buy,5086.29,19:39:03,5086.44,1.26
19:41:59,sell,5091.09,19:42:54,5090.93,1.35
19:41:59,sell,5091.09,19:42:54,5090.94,1.26
19:42:26,sell,5093.18,19:42:40,5092.05,9.50
19:42:27,sell,5092.97,19:42:40,5092.09,7.40
"""

# Build dataframe
rows = []
DATE = "2026-02-11"
for line in TRADES_RAW.strip().split("\n"):
    parts = line.split(",")
    open_t, side, open_px, close_t, close_px, profit = parts
    open_dt_broker  = datetime.fromisoformat(f"{DATE}T{open_t}+02:00")   # EET winter
    close_dt_broker = datetime.fromisoformat(f"{DATE}T{close_t}+02:00")
    if close_dt_broker < open_dt_broker:
        close_dt_broker += timedelta(days=1)
    rows.append({
        "open_broker": open_t,
        "open_utc":  open_dt_broker.astimezone(timezone.utc).strftime("%H:%M:%S"),
        "close_broker": close_t,
        "close_utc": close_dt_broker.astimezone(timezone.utc).strftime("%H:%M:%S"),
        "side": side,
        "open_px":  float(open_px),
        "close_px": float(close_px),
        "profit": float(profit),
        "open_ts_utc_ms": int(open_dt_broker.astimezone(timezone.utc).timestamp() * 1000),
        "close_ts_utc_ms": int(close_dt_broker.astimezone(timezone.utc).timestamp() * 1000),
        "duration_sec": int((close_dt_broker - open_dt_broker).total_seconds()),
    })

trades = pd.DataFrame(rows)
print(f"=== ZEE'S FEB 11 2026 TRADES — RAW STATS ===")
print(f"Total trades:    {len(trades)}")
print(f"Wins:            {(trades['profit'] > 0).sum()}")
print(f"Losses:          {(trades['profit'] < 0).sum()}")
print(f"WR:              {(trades['profit'] > 0).mean() * 100:.1f}%")
print(f"NET P&L:         ${trades['profit'].sum():+.2f}")
print(f"Avg win:         ${trades.loc[trades['profit'] > 0, 'profit'].mean():+.2f}")
print(f"Avg loss:        ${trades.loc[trades['profit'] < 0, 'profit'].mean():+.2f}")
print(f"Biggest win:     ${trades['profit'].max():+.2f}")
print(f"Biggest loss:    ${trades['profit'].min():+.2f}")
print(f"Avg duration:    {trades['duration_sec'].mean():.0f}s ({trades['duration_sec'].mean()/60:.1f}min)")
print()

# Cluster trades by entry-minute to identify SETUPS (bursts of multi-trades same second-1min are 1 setup)
trades["entry_minute_utc"] = (trades["open_ts_utc_ms"] // 60000) * 60000
setups = trades.groupby("entry_minute_utc").agg(
    n_trades=("profit", "count"),
    open_broker=("open_broker", "first"),
    open_utc=("open_utc", "first"),
    side=("side", "first"),
    open_px=("open_px", "mean"),
    close_px=("close_px", "mean"),
    profit=("profit", "sum"),
    duration=("duration_sec", "mean"),
).reset_index().sort_values("entry_minute_utc")
print(f"=== {len(setups)} DISTINCT SETUPS (grouped by entry minute) ===")
print(f"{'broker':>9} {'utc':>9} {'side':>4} {'n':>3} {'avg_px':>9} {'net_$':>9} {'avg_dur_s':>10}")
for _, s in setups.iterrows():
    flag = " ✗" if s.profit < 0 else ""
    print(f"{s.open_broker:>9} {s.open_utc:>9} {s.side:>4} {int(s.n_trades):>3} {s.open_px:>9.2f} ${s.profit:>+8.2f} {s.duration:>9.0f}s{flag}")

print()
print(f"=== UTC HOUR DISTRIBUTION ===")
trades["utc_hour"] = trades["open_utc"].str[:2].astype(int)
hour_stats = trades.groupby("utc_hour").agg(n=("profit","count"), wins=("profit", lambda x: (x>0).sum()), net=("profit","sum"))
hour_stats["wr_pct"] = (hour_stats["wins"] / hour_stats["n"] * 100).round(1)
print(hour_stats.to_string())

# Compare with parquet ticks for that day — find M1 bar around each setup
CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
print(f"\n=== LOADING PARQUET TICKS for Feb 11 ===", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
feb11_lo = int(datetime(2026, 2, 10, 23, 0, tzinfo=timezone.utc).timestamp() * 1000)
feb11_hi = int(datetime(2026, 2, 12,  1, 0, tzinfo=timezone.utc).timestamp() * 1000)
df = df[(df["time_msc"] >= feb11_lo) & (df["time_msc"] <= feb11_hi)].reset_index(drop=True)
print(f"  Ticks in Feb 11 window: {len(df):,}")
if len(df) == 0:
    print("  NO TICK DATA FOR FEB 11 — parquet doesn't cover this date")
    print(f"  Parquet range likely after Feb 11. Will skip M1 overlay.")
else:
    df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
    m1_grp = df.groupby("m1", sort=True).agg(
        o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
        v=("bid","count"), ts_end_ms=("time_msc","last"),
    ).reset_index().drop(columns="m1")
    m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
    m1 = m1_grp.to_dict("records")
    print(f"  M1 bars: {len(m1):,}")
    print()
    print(f"=== PER-SETUP M1 CONTEXT ===")
    print(f"  For each setup: show entry-bar OHLCV + UHV-in-last-20 + vol ratio + body%")
    print(f"{'utc':>10} {'side':>4} {'entry_min_ago':>14} {'cur_v':>6} {'uhv_v':>6} {'uhv_mult':>9} {'vol_ratio':>10} {'body%':>7}")
    for _, s in setups.iterrows():
        entry_ts = int(s.entry_minute_utc)
        # Find M1 bar at this entry minute
        bar_idx = None
        for i, b in enumerate(m1):
            if b["ts_end_ms"] // 60000 * 60000 == entry_ts:
                bar_idx = i; break
        if bar_idx is None or bar_idx < 25:
            print(f"{s.open_utc:>10} {s.side:>4}  no_bar_found")
            continue
        cur = m1[bar_idx]
        # UHV = highest-vol bar in last 20 closed
        win_lo = bar_idx - 20
        uhv_idx = max(range(win_lo, bar_idx), key=lambda j: m1[j]["v"])
        uhv = m1[uhv_idx]
        # Vol multiplier
        recent_vols = [m1[j]["v"] for j in range(max(0, uhv_idx - 20), uhv_idx) if j != uhv_idx]
        uhv_mult = uhv["v"] / (sum(recent_vols)/len(recent_vols)) if recent_vols else 0
        vol_ratio = cur["v"] / max(1, uhv["v"])
        rng = cur["h"] - cur["l"]
        body = abs(cur["c"] - cur["o"])
        body_pct = body / rng if rng > 0 else 0
        print(f"{s.open_utc:>10} {s.side:>4}  uhv@-{bar_idx-uhv_idx}m  {cur['v']:>5} {uhv['v']:>6} {uhv_mult:>8.1f}x {vol_ratio:>9.2f} {body_pct:>6.2f}")
