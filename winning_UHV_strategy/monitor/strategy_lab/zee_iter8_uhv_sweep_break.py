"""ITER 8 — Zee's teacher: 'before breakout of high of UHV red, if price breaks below UHV low first, that's a better setup.'

Pattern:
  1. UHV red M1 candle in retracement, inside M5 buy FVG
  2. Within next N bars, price wicks BELOW the UHV's LOW (stop hunt)
  3. Then within M more bars, candle CLOSES ABOVE the UHV's HIGH (breakout)
  4. Entry at close of breakout candle
For SELL: mirror.
"""
import pandas as pd, numpy as np
import statistics
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)

def bars(df, p):
    df = df.copy()
    df["p"] = (df["time_msc"] // p).astype(np.int64)
    g = df.groupby("p", sort=True).agg(o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"), v=("bid","count"), ts=("time_msc","last")).reset_index().drop(columns="p")
    return g.to_dict("records")

m1 = bars(df, 60_000)
m5 = bars(df, 5*60_000)
ts_arr = df["time_msc"].to_numpy(dtype=np.int64)
bid_arr = df["bid"].to_numpy(dtype=np.float64)
ask_arr = df["ask"].to_numpy(dtype=np.float64)

def is_red(b): return b["c"] < b["o"]
def is_green(b): return b["c"] > b["o"]
def avg_vol(idx, lb=20):
    lo = max(0, idx - lb)
    vs = [m1[k]["v"] for k in range(lo, idx) if k != idx]
    return sum(vs)/len(vs) if vs else 0

FVG_MAX_AGE_M5 = 30
fvgs = []
for i in range(2, len(m5)):
    c0, c2 = m5[i-2], m5[i]
    if c0["h"] < c2["l"]:
        fvgs.append({"side":"buy","hi":c2["l"],"lo":c0["h"],"formed_ts":c2["ts"]})
    elif c0["l"] > c2["h"]:
        fvgs.append({"side":"sell","hi":c0["l"],"lo":c2["h"],"formed_ts":c2["ts"]})
import bisect
fs = sorted(fvgs, key=lambda f: f["formed_ts"])
ftl = [f["formed_ts"] for f in fs]
LOTS = 0.10
CONTRACT = 100
COMMISSION = 7.0 * LOTS

UHV_VOL_MULT_MIN = 1.5
UHV_MIN_BODY_PCT = 0.40
MAX_BARS_LOOKAHEAD = 8
MAX_BARS_SWEEP_TO_BREAK = 5

raw_signals = []
for j in range(2, len(m1)-MAX_BARS_LOOKAHEAD):
    cur = m1[j]
    cur_ts = cur["ts"]
    end_idx = bisect.bisect_left(ftl, cur_ts)
    start_idx = bisect.bisect_left(ftl, cur_ts - FVG_MAX_AGE_M5 * 5 * 60_000)
    in_buy_fvg = any((cur["l"] <= f["hi"]) and (cur["h"] >= f["lo"]) and f["side"] == "buy" for f in fs[start_idx:end_idx])
    in_sell_fvg = any((cur["l"] <= f["hi"]) and (cur["h"] >= f["lo"]) and f["side"] == "sell" for f in fs[start_idx:end_idx])

    cur_rng = cur["h"] - cur["l"]
    if cur_rng <= 0:
        continue
    cur_body_pct = abs(cur["c"] - cur["o"]) / cur_rng
    if cur_body_pct < UHV_MIN_BODY_PCT:
        continue
    av = avg_vol(j, 20)
    if av == 0 or cur["v"] < UHV_VOL_MULT_MIN * av:
        continue

    if is_red(cur) and in_buy_fvg:
        uhv_low = cur["l"]; uhv_high = cur["h"]
        sweep_idx = None
        for k in range(j+1, min(j+1+MAX_BARS_LOOKAHEAD, len(m1))):
            if m1[k]["l"] < uhv_low:
                sweep_idx = k; break
        if sweep_idx is None:
            continue
        for kk in range(sweep_idx, min(sweep_idx+1+MAX_BARS_SWEEP_TO_BREAK, len(m1))):
            if m1[kk]["c"] > uhv_high:
                raw_signals.append(("buy", m1[kk]["ts"], m1[kk]["c"]))
                break
    if is_green(cur) and in_sell_fvg:
        uhv_low = cur["l"]; uhv_high = cur["h"]
        sweep_idx = None
        for k in range(j+1, min(j+1+MAX_BARS_LOOKAHEAD, len(m1))):
            if m1[k]["h"] > uhv_high:
                sweep_idx = k; break
        if sweep_idx is None:
            continue
        for kk in range(sweep_idx, min(sweep_idx+1+MAX_BARS_SWEEP_TO_BREAK, len(m1))):
            if m1[kk]["c"] < uhv_low:
                raw_signals.append(("sell", m1[kk]["ts"], m1[kk]["c"]))
                break

seen = set()
signals = []
for s in raw_signals:
    key = (s[1] // 60000, s[0])
    if key in seen: continue
    seen.add(key); signals.append(s)
print(f"Iter 8 signals: {len(signals)}")

peaks_30s = []
for side, entry_ts, entry_px in signals:
    end_ts = entry_ts + 30_000
    i0 = int(np.searchsorted(ts_arr, entry_ts, side="right"))
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9
    for k in range(i0, i1):
        if side == "buy":
            pnl = (bid_arr[k] - entry_px) * CONTRACT * LOTS
        else:
            pnl = (entry_px - ask_arr[k]) * CONTRACT * LOTS
        if pnl > peak: peak = pnl
    peaks_30s.append(peak)
print(f"MFE 30s: median ${statistics.median(peaks_30s):+.2f}  mean ${statistics.mean(peaks_30s):+.2f}")
print(f"% peak > $2 in 30s: {sum(1 for p in peaks_30s if p > 2)/len(peaks_30s)*100:.1f}%")
print(f"% peak > $5 in 30s: {sum(1 for p in peaks_30s if p > 5)/len(peaks_30s)*100:.1f}%")
print(f"% peak > $10 in 30s: {sum(1 for p in peaks_30s if p > 10)/len(peaks_30s)*100:.1f}%")
print()
print(f"{'label':<35} {'WR%':>6} {'NET$':>10} {'avg':>7}")
configs = [
    ("fixed_tp3_sl3_60s", 3, 3, 60),
    ("fixed_tp5_sl3_60s", 5, 3, 60),
    ("fixed_tp5_sl5_60s", 5, 5, 60),
    ("fixed_tp3_sl5_60s", 3, 5, 60),
    ("fixed_tp8_sl5_120s", 8, 5, 120),
    ("fixed_tp10_sl5_180s", 10, 5, 180),
]
for label, tp, sl, hold in configs:
    trades = []
    for side, entry_ts, entry_px in signals:
        end_ts = entry_ts + hold*1000
        i0 = int(np.searchsorted(ts_arr, entry_ts, side="right"))
        i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
        pnl = 0
        for k in range(i0, i1):
            if side == "buy":
                pnl = (bid_arr[k] - entry_px) * CONTRACT * LOTS
            else:
                pnl = (entry_px - ask_arr[k]) * CONTRACT * LOTS
            if pnl >= tp or pnl <= -sl: break
        else:
            if i1 > i0:
                k = i1 - 1
                if side == "buy":
                    pnl = (bid_arr[k] - entry_px) * CONTRACT * LOTS
                else:
                    pnl = (entry_px - ask_arr[k]) * CONTRACT * LOTS
        trades.append(pnl - COMMISSION)
    n = len(trades); wins = sum(1 for p in trades if p > 0); net = sum(trades)
    wr = wins/n*100 if n else 0; avg = net/n if n else 0
    print(f"{label:<35} {wr:>5.1f}% ${net:>+9.2f} ${avg:>+5.2f}")

print()
print("Trailing:")
configs2 = [
    ("scratch3_trail5_drop2_120s", 3, 5, 2, 120),
    ("scratch2_trail3_drop1_60s", 2, 3, 1, 60),
    ("scratch3_trail10_drop3_300s", 3, 10, 3, 300),
    ("scratch5_trail15_drop5_300s", 5, 15, 5, 300),
]
for label, scratch, trig, drop, hold in configs2:
    trades = []
    for side, entry_ts, entry_px in signals:
        end_ts = entry_ts + hold*1000
        i0 = int(np.searchsorted(ts_arr, entry_ts, side="right"))
        i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
        peak = -1e9; pnl = 0; trail = False
        for k in range(i0, i1):
            if side == "buy":
                pnl = (bid_arr[k] - entry_px) * CONTRACT * LOTS
            else:
                pnl = (entry_px - ask_arr[k]) * CONTRACT * LOTS
            peak = max(peak, pnl)
            if not trail and pnl <= -scratch: break
            if not trail and peak >= trig: trail = True
            if trail and pnl <= peak - drop: break
        trades.append(pnl - COMMISSION)
    n = len(trades); wins = sum(1 for p in trades if p > 0); net = sum(trades)
    wr = wins/n*100 if n else 0; avg = net/n if n else 0
    print(f"{label:<35} {wr:>5.1f}% ${net:>+9.2f} ${avg:>+5.2f}")
