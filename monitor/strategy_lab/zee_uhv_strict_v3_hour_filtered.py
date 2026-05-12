"""Round 3: strict v2 + hour filter (only trade winning hours).

v2 found: hours 9, 13, 14, 20 = 80-100% WR / +$102 net combined
         hours 10, 11, 15, 16, 18, 19 = losers

v3 tests several hour-filter configs:
  A) Strict v2 + ONLY hours {9, 13, 14, 20} (best 4)
  B) Strict v2 + extend to {7, 8, 9, 13, 14, 20, 23} (best + neutrals)
  C) Slightly relaxed entry (body 0.70, vol_ratio 0.50) + same hours as A
  D) Slightly relaxed entry + hours as B
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_uhv_strict_v3.json")

LOTS = 0.10; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100
UHV_LOOKBACK = 20; UHV_MAX_AGE_BARS = 10
RECENT_AVG_BARS = 20
UHV_MIN_VOL_MULT = 2.0
MAX_OPPOSING_WICK = 0.25
MIN_SPACING_SEC = 60
DAILY_LOSS_USD = 100.0
EXIT = {"trail_trigger": 10, "trail_drop": 3, "catastrophic_usd": 30, "scratch_sec": 30, "max_hold_min": 10}

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


def detect(idx, max_vol_ratio, min_body_pct):
    if idx < UHV_LOOKBACK + RECENT_AVG_BARS + 5: return None
    win_lo = idx - UHV_LOOKBACK
    uhv_idx = max(range(win_lo, idx), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] <= 0 or (idx - uhv_idx) > UHV_MAX_AGE_BARS: return None
    recent_vols = [m1[j]["v"] for j in range(max(0, uhv_idx - RECENT_AVG_BARS), uhv_idx) if j != uhv_idx]
    if not recent_vols: return None
    if uhv["v"] < UHV_MIN_VOL_MULT * (sum(recent_vols) / len(recent_vols)): return None
    cur = m1[idx]
    vr = cur["v"] / uhv["v"]
    if vr > max_vol_ratio: return None
    rng = cur["h"] - cur["l"]
    if rng <= 0: return None
    body = abs(cur["c"] - cur["o"])
    if body / rng < min_body_pct: return None
    is_red = uhv["c"] < uhv["o"]; is_green = uhv["c"] > uhv["o"]
    if not (is_red or is_green): return None
    if is_red:
        if cur["c"] <= uhv["h"]: return None
        if (cur["h"] - cur["c"]) / rng > MAX_OPPOSING_WICK: return None
        return {"side": "buy", "ts_end_ms": cur["ts_end_ms"], "hour": cur["hour"]}
    else:
        if cur["c"] >= uhv["l"]: return None
        if (cur["c"] - cur["l"]) / rng > MAX_OPPOSING_WICK: return None
        return {"side": "sell", "ts_end_ms": cur["ts_end_ms"], "hour": cur["hour"]}


def fill(sig):
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    if i0 >= len(ts_arr): return None
    if sig["side"] == "buy": return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def walk(side, fi, entry_price, entry_ts, cfg):
    end_ts = entry_ts + cfg["max_hold_min"] * 60 * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9; has_pos = False; armed = False
    cur_pnl = 0
    for k in range(fi + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy": cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:             cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        peak = max(peak, cur_pnl)
        if cur_pnl > 0: has_pos = True
        if cur_pnl <= -cfg["catastrophic_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "age": elapsed, "peak": peak}
        if not armed and peak >= cfg["trail_trigger"]: armed = True
        if armed and (peak - cur_pnl) >= cfg["trail_drop"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TRAIL", "age": elapsed, "peak": peak}
        if not has_pos and elapsed > cfg["scratch_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SCRATCH", "age": elapsed, "peak": peak}
    return {"pnl": cur_pnl - COMMISSION, "reason": "TIMEOUT", "age": cfg["max_hold_min"]*60, "peak": peak}


def run(label, hours_set, max_vol_ratio, min_body_pct):
    trades = []; last_entry = 0; daily = {}; halted = set()
    for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + 5, len(m1)):
        bar = m1[idx]; date = bar["date"]
        if bar["hour"] not in hours_set: continue
        if date in halted: continue
        if daily.get(date, 0) <= -DAILY_LOSS_USD: halted.add(date); continue
        if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
        sig = detect(idx, max_vol_ratio, min_body_pct)
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
    print(f"\n{label}", flush=True)
    if n == 0:
        print("  No signals"); return {"label": label, "n": 0}
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    net = sum(t["pnl"] for t in trades)
    avg = net / n
    days_p = sum(1 for p in daily.values() if p > 0)
    days_l = sum(1 for p in daily.values() if p < 0)
    print(f"  n={n}  WR={wins/n*100:.1f}%  NET=${net:+.2f}  avg=${avg:+.2f}", flush=True)
    print(f"  days: profit={days_p}/{len(daily)}  loss={days_l}  halted={len(halted)}", flush=True)
    return {"label": label, "n": n, "wins": wins, "wr_pct": round(wins/n*100, 1),
            "net_usd": round(net, 2), "avg_usd": round(avg, 2),
            "days_profit": days_p, "days_loss": days_l, "days_halted": len(halted),
            "daily_pnl": {d: round(p, 2) for d, p in sorted(daily.items())}}


WINNING_HOURS_4 = {9, 13, 14, 20}
WINNING_HOURS_7 = {7, 8, 9, 13, 14, 20, 23}

print("\n[ROUND 3] hour-filter variants on strict entry", flush=True)
results = [
    run("A: strict + only {9,13,14,20}",  WINNING_HOURS_4, 0.40, 0.80),
    run("B: strict + {7,8,9,13,14,20,23}", WINNING_HOURS_7, 0.40, 0.80),
    run("C: relaxed (vol.50/body.70) + {9,13,14,20}", WINNING_HOURS_4, 0.50, 0.70),
    run("D: relaxed + {7,8,9,13,14,20,23}",          WINNING_HOURS_7, 0.50, 0.70),
]

print("\n=== SUMMARY (sorted by net) ===", flush=True)
for r in sorted([x for x in results if x.get("n", 0) > 0], key=lambda x: -x.get("net_usd", -1e9)):
    print(f"  {r['label']:<55}  n={r['n']:>4}  WR={r['wr_pct']:>5}%  NET=${r['net_usd']:>+8.2f}  days_profit={r['days_profit']}", flush=True)

OUT_J.write_text(json.dumps({"started": datetime.now(timezone.utc).isoformat(), "variants": results}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
