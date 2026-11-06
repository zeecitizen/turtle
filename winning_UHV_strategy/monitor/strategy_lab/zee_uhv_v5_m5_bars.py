"""v5: same strict UHV rules but on M5 bars (5-min aggregation) instead of M1.

Hypothesis: M1 too noisy; M5 captures fewer but more meaningful volume spikes.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_uhv_v5_m5.json")

LOTS = 0.10; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100
UHV_LOOKBACK = 20; UHV_MAX_AGE_BARS = 6  # ~30 min in M5 terms
RECENT_AVG_BARS = 20
UHV_MIN_VOL_MULT = 2.0
MAX_OPPOSING_WICK = 0.25
MIN_BODY_PCT = 0.65   # slightly looser since M5 candles are bigger
MAX_VOL_RATIO = 0.50
MIN_SPACING_SEC = 300  # 5 min on M5
DAILY_LOSS_USD = 100.0
EXIT = {"trail_trigger": 10, "trail_drop": 3, "catastrophic_usd": 30, "scratch_sec": 45, "max_hold_min": 15}

print("[LOAD] parquet -> M5 bars...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
df["m5"] = (df["time_msc"] // (5 * 60_000)).astype(np.int64)
m5_grp = df.groupby("m5", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m5")
m5_grp["dt"] = pd.to_datetime(m5_grp["ts_end_ms"], unit="ms", utc=True)
m5_grp["date"] = m5_grp["dt"].dt.strftime("%Y-%m-%d")
m5_grp["hour"] = m5_grp["dt"].dt.hour
m5 = m5_grp.to_dict("records")
print(f"  M5 bars: {len(m5):,}", flush=True)

ts_arr = df["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df["bid"].to_numpy(dtype=np.float64)
asks_arr = df["ask"].to_numpy(dtype=np.float64)


def detect(idx):
    if idx < UHV_LOOKBACK + RECENT_AVG_BARS + 5: return None
    win_lo = idx - UHV_LOOKBACK
    uhv_idx = max(range(win_lo, idx), key=lambda j: m5[j]["v"])
    uhv = m5[uhv_idx]
    if uhv["v"] <= 0 or (idx - uhv_idx) > UHV_MAX_AGE_BARS: return None
    rv = [m5[j]["v"] for j in range(max(0, uhv_idx - RECENT_AVG_BARS), uhv_idx) if j != uhv_idx]
    if not rv: return None
    if uhv["v"] < UHV_MIN_VOL_MULT * (sum(rv) / len(rv)): return None
    cur = m5[idx]
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


def run(date_lo, date_hi, label=""):
    trades = []; last_entry = 0; daily = {}; halted = set()
    for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + 5, len(m5)):
        bar = m5[idx]; date = bar["date"]
        if date < date_lo or date >= date_hi: continue
        if bar["hour"] < 6: continue
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
    n = len(trades)
    if n == 0:
        print(f"{label}: NO TRADES", flush=True)
        return {"label": label, "n": 0}
    wins = sum(1 for t in trades if t["pnl"] > 0)
    net = sum(t["pnl"] for t in trades)
    days_p = sum(1 for p in daily.values() if p > 0)
    print(f"{label}: n={n}  WR={wins/n*100:.1f}%  NET=${net:+.2f}  days_profit={days_p}/{len(daily)}", flush=True)
    return {"label": label, "n": n, "wins": wins, "wr_pct": round(wins/n*100, 1),
            "net_usd": round(net, 2), "days_profit": days_p, "days_total": len(daily)}


dates = sorted(set(b["date"] for b in m5))
split_idx = int(len(dates) * 0.70)
print(f"\nM5 strict v2 entry rules")
full = run(dates[0], "9999-99-99", "FULL  (Jan 7 - May 7)")
print()
tr = run(dates[0], dates[split_idx], "TRAIN (Jan 7 - Apr 1)")
te = run(dates[split_idx], "9999-99-99", "TEST  (Apr 1 - May 7)")

OUT_J.write_text(json.dumps({"started": datetime.now(timezone.utc).isoformat(),
                              "full": full, "train": tr, "test": te}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
