"""ITERATION 4 — Pattern-validity check via P&L (parquet feed differs from Zee's broker).

Acknowledging broker-feed mismatch (OANDA parquet vs BlueberryMarkets has ~15-17pt gaps),
the goal pivots from "match exact timestamps" to "validate pattern profitability."

Pattern (Lesson 10 final refinement):
  - M5 FVG zone formed earlier
  - Price returns to FVG on M1
  - Last opposite-color candle in mitigation
  - Next same-direction candle sweep wicks beyond opposite candle's extreme
  - Same candle closes back inside opposite candle's body
  - Volume of trigger candle > volume of swept candle

Backtest: 1m exits with structural SL + 1:1 RR TP. Lots=0.1.
"""
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_fvg_v4_iter4.json")

# Build M1 + M5 bars across entire parquet
print("[1/6] Loading parquet ticks (full)...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"  ticks: {len(df):,}  span: {pd.to_datetime(df.time_msc.iloc[0],unit='ms',utc=True)} to {pd.to_datetime(df.time_msc.iloc[-1],unit='ms',utc=True)}", flush=True)

def bars(df, period_ms):
    df = df.copy()
    df["p"] = (df["time_msc"] // period_ms).astype(np.int64)
    g = df.groupby("p", sort=True).agg(
        o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
        v=("bid","count"), ts=("time_msc","last"),
    ).reset_index().drop(columns="p")
    g["dt"] = pd.to_datetime(g["ts"], unit="ms", utc=True)
    g["utc"] = g["dt"].dt.strftime("%Y-%m-%d %H:%M")
    return g.to_dict("records")

print("[2/6] Building M1 + M5 bars...", flush=True)
m1 = bars(df, 60_000)
m5 = bars(df, 5*60_000)
print(f"  M1: {len(m1):,}  M5: {len(m5):,}", flush=True)
ts_arr = df["time_msc"].to_numpy(dtype=np.int64)
bid_arr = df["bid"].to_numpy(dtype=np.float64)
ask_arr = df["ask"].to_numpy(dtype=np.float64)

# PARAMS
SWEEP_MIN_PTS = 0.05
VOL_RATIO_MIN = 1.1
UPPER_WICK_MAX = 0.30
RED_MIN_RANGE_PTS = 0.15
FVG_MAX_AGE_M5 = 30
SL_BUFFER_PTS = 0.20
TP_RR = 1.0
MAX_HOLD_MIN = 30
LOTS = 0.10
CONTRACT = 100
COMMISSION = 7.0 * LOTS  # $0.70 per trade

def is_red(b): return b["c"] < b["o"]
def is_green(b): return b["c"] > b["o"]

# Detect FVGs on M5
print("[3/6] Detecting M5 FVGs...", flush=True)
fvgs = []
for i in range(2, len(m5)):
    c0, c2 = m5[i-2], m5[i]
    if c0["h"] < c2["l"]:
        fvgs.append({"side":"buy","hi":c2["l"],"lo":c0["h"],"formed_ts":c2["ts"]})
    elif c0["l"] > c2["h"]:
        fvgs.append({"side":"sell","hi":c0["l"],"lo":c2["h"],"formed_ts":c2["ts"]})
print(f"  FVGs: {len(fvgs)}", flush=True)
fvgs_sorted = sorted(fvgs, key=lambda f: f["formed_ts"])
# Build fvg index by ts for fast lookup
import bisect
fvg_ts_list = [f["formed_ts"] for f in fvgs_sorted]

# Scan M1 bars for setup
print("[4/6] Scanning M1 bars for setups...", flush=True)
signals = []
for j in range(1, len(m1)):
    cur, prev = m1[j], m1[j-1]
    cur_ts = cur["ts"]
    # Find active FVGs (formed before cur, within age, zone overlaps cur range)
    # active FVGs index range
    end_idx = bisect.bisect_left(fvg_ts_list, cur_ts)
    start_idx = bisect.bisect_left(fvg_ts_list, cur_ts - FVG_MAX_AGE_M5 * 5 * 60_000)
    active_buy = []
    active_sell = []
    for f in fvgs_sorted[start_idx:end_idx]:
        if not ((cur["l"] <= f["hi"]) and (cur["h"] >= f["lo"])):
            continue
        if f["side"] == "buy":
            active_buy.append(f)
        else:
            active_sell.append(f)
    # BUY: prev red, cur green, sweep+engulf
    if active_buy and is_red(prev) and is_green(cur):
        if (prev["h"] - prev["l"]) >= RED_MIN_RANGE_PTS and \
           cur["l"] < prev["l"] - SWEEP_MIN_PTS and \
           cur["c"] > prev["l"] and \
           cur["v"] >= VOL_RATIO_MIN * prev["v"]:
            rng = cur["h"] - cur["l"]
            if rng > 0:
                upper = cur["h"] - max(cur["c"], cur["o"])
                if upper / rng <= UPPER_WICK_MAX:
                    signals.append({"side":"buy","entry_ts":cur["ts"],"entry_px":cur["c"],
                                    "sl_px":cur["l"]-SL_BUFFER_PTS, "utc":cur["utc"]})
    if active_sell and is_green(prev) and is_red(cur):
        if (prev["h"] - prev["l"]) >= RED_MIN_RANGE_PTS and \
           cur["h"] > prev["h"] + SWEEP_MIN_PTS and \
           cur["c"] < prev["h"] and \
           cur["v"] >= VOL_RATIO_MIN * prev["v"]:
            rng = cur["h"] - cur["l"]
            if rng > 0:
                lower = min(cur["c"], cur["o"]) - cur["l"]
                if lower / rng <= UPPER_WICK_MAX:
                    signals.append({"side":"sell","entry_ts":cur["ts"],"entry_px":cur["c"],
                                    "sl_px":cur["h"]+SL_BUFFER_PTS, "utc":cur["utc"]})
print(f"  signals: {len(signals)}", flush=True)

# Run P&L simulation
print("[5/6] Running P&L simulation (1:1 RR, structural SL)...", flush=True)
trades = []
for s in signals:
    entry_ts = int(s["entry_ts"])
    entry_px = s["entry_px"]
    sl_px = s["sl_px"]
    side = s["side"]
    risk = abs(entry_px - sl_px)
    tp_px = entry_px + risk * TP_RR if side == "buy" else entry_px - risk * TP_RR
    end_ts = entry_ts + MAX_HOLD_MIN * 60_000
    i0 = int(np.searchsorted(ts_arr, entry_ts, side="right"))
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    outcome = "TIMEOUT"; exit_px = entry_px; exit_ts = end_ts
    for k in range(i0, i1):
        if side == "buy":
            if bid_arr[k] <= sl_px:
                outcome = "SL"; exit_px = sl_px; exit_ts = int(ts_arr[k]); break
            if bid_arr[k] >= tp_px:
                outcome = "TP"; exit_px = tp_px; exit_ts = int(ts_arr[k]); break
        else:
            if ask_arr[k] >= sl_px:
                outcome = "SL"; exit_px = sl_px; exit_ts = int(ts_arr[k]); break
            if ask_arr[k] <= tp_px:
                outcome = "TP"; exit_px = tp_px; exit_ts = int(ts_arr[k]); break
    pnl_pts = (exit_px - entry_px) if side == "buy" else (entry_px - exit_px)
    pnl_usd = pnl_pts * CONTRACT * LOTS - COMMISSION
    duration_sec = (exit_ts - entry_ts) / 1000
    trades.append({"utc":s["utc"],"side":side,"entry":round(entry_px,2),"sl":round(sl_px,2),
                   "tp":round(tp_px,2),"exit":round(exit_px,2),"outcome":outcome,
                   "pnl_usd":round(pnl_usd,2),"dur_s":round(duration_sec,0)})

# Stats
n = len(trades)
wins = sum(1 for t in trades if t["pnl_usd"] > 0)
losses = sum(1 for t in trades if t["pnl_usd"] < 0)
net = sum(t["pnl_usd"] for t in trades)
wr = wins / n * 100 if n else 0
avg_win = np.mean([t["pnl_usd"] for t in trades if t["pnl_usd"]>0]) if wins else 0
avg_loss = np.mean([t["pnl_usd"] for t in trades if t["pnl_usd"]<0]) if losses else 0
reasons = {}
for t in trades:
    reasons[t["outcome"]] = reasons.get(t["outcome"], 0) + 1

print(f"\nITER 4 PATTERN P&L RESULTS:")
print(f"  Trades: {n}")
print(f"  Wins:   {wins}   Losses: {losses}")
print(f"  WR:     {wr:.1f}%")
print(f"  NET:    ${net:+.2f}")
print(f"  Avg W:  ${avg_win:+.2f}   Avg L: ${avg_loss:+.2f}")
print(f"  Outcomes: {reasons}")

# Per-day breakdown
days = {}
for t in trades:
    d = t["utc"][:10]
    days.setdefault(d, []).append(t["pnl_usd"])
profitable_days = sum(1 for d, l in days.items() if sum(l) > 0)
loss_days = sum(1 for d, l in days.items() if sum(l) < 0)
print(f"  Days: {len(days)} total / {profitable_days} profitable / {loss_days} loss")

# Save
OUT_J.write_text(json.dumps({
    "iteration": 4,
    "params": {"SWEEP_MIN_PTS":SWEEP_MIN_PTS,"VOL_RATIO_MIN":VOL_RATIO_MIN,
               "UPPER_WICK_MAX":UPPER_WICK_MAX,"RED_MIN_RANGE_PTS":RED_MIN_RANGE_PTS,
               "FVG_MAX_AGE_M5":FVG_MAX_AGE_M5,"SL_BUFFER_PTS":SL_BUFFER_PTS,
               "TP_RR":TP_RR,"MAX_HOLD_MIN":MAX_HOLD_MIN,"LOTS":LOTS},
    "trades_count":n,"wins":wins,"losses":losses,"wr_pct":round(wr,1),
    "net_usd":round(net,2),"avg_win":round(float(avg_win),2),"avg_loss":round(float(avg_loss),2),
    "outcomes":reasons,
    "days_total":len(days),"days_profitable":profitable_days,"days_loss":loss_days,
    "daily_pnl":{d:round(sum(l),2) for d,l in sorted(days.items())},
    "trades_first_20":trades[:20],
    "trades_last_5":trades[-5:],
    "ts":datetime.now(timezone.utc).isoformat(),
}, indent=2, default=str))
print(f"[6/6] saved -> {OUT_J}", flush=True)
