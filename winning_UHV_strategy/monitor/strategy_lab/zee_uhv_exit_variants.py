"""Iterate Zee's strict UHV entry against MULTIPLE exit configs on full 86-day parquet.

Entry rules (Zee verbatim 2026-05-11):
  - UHV = highest-vol M1 bar in last 20 closed (excl current)
  - vol_ratio = cur_vol / uhv_vol  → must be ≤ 0.70 (no-supply confirmation)
  - cur body% ≥ 0.65 (momentum candle)
  - cur close past UHV high (BUY) / low (SELL)
  - opposing wick ≤ 25% of range (no rejection)
  - Sydney filter ON (skip 00-06 GMT)
  - Min spacing 60s, daily loss halt $100

Exit variants tested:
  A) Zee-loose (validated on 2026-05-07 single day = 100% WR): peak $10 trigger, $3 drop, $30 catastrophic, 30s scratch, 10min hold
  B) Tighter trail: $5 trigger, $2 drop
  C) Wider trail: $15 trigger, $5 drop
  D) BE+lock: trail $10/$3 but ALSO move SL to entry after $5 peak
  E) Fixed $5 TP (vs $3 before — let winners reach better levels)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_uhv_exit_variants.json")

LOTS = 0.10
COMMISSION = 7.0 * LOTS
CONTRACT_SIZE = 100

# === ENTRY RULES (Zee verbatim) ===
UHV_LOOKBACK = 20
UHV_MAX_AGE_BARS = 10
MIN_BODY_PCT = 0.65
MAX_VOL_RATIO = 0.70
MAX_OPPOSING_WICK_PCT = 0.25
SKIP_SYDNEY = True
MIN_SPACING_SEC = 60
DAILY_LOSS_USD = 100.0

print("[LOAD] parquet...", flush=True)
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
print(f"  M1 bars: {len(m1):,}  {m1[0]['date']}..{m1[-1]['date']}", flush=True)

ts_arr   = df["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df["bid"].to_numpy(dtype=np.float64)
asks_arr = df["ask"].to_numpy(dtype=np.float64)


def detect(idx):
    if idx < UHV_LOOKBACK + 2: return None
    win_lo = idx - UHV_LOOKBACK
    uhv_idx = max(range(win_lo, idx), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] <= 0 or (idx - uhv_idx) > UHV_MAX_AGE_BARS: return None
    cur = m1[idx]
    if cur["v"] / uhv["v"] > MAX_VOL_RATIO: return None
    rng = cur["h"] - cur["l"]
    if rng <= 0: return None
    body = abs(cur["c"] - cur["o"])
    if body / rng < MIN_BODY_PCT: return None
    is_red = uhv["c"] < uhv["o"]
    is_green = uhv["c"] > uhv["o"]
    if not (is_red or is_green): return None
    if is_red:
        if cur["c"] <= uhv["h"]: return None
        upper = cur["h"] - cur["c"]
        if upper / rng > MAX_OPPOSING_WICK_PCT: return None
        return {"side": "buy", "ts_end_ms": cur["ts_end_ms"], "uhv_h": uhv["h"], "uhv_l": uhv["l"],
                "vol_ratio": cur["v"]/uhv["v"], "body_pct": body/rng}
    else:
        if cur["c"] >= uhv["l"]: return None
        lower = cur["c"] - cur["l"]
        if lower / rng > MAX_OPPOSING_WICK_PCT: return None
        return {"side": "sell", "ts_end_ms": cur["ts_end_ms"], "uhv_h": uhv["h"], "uhv_l": uhv["l"],
                "vol_ratio": cur["v"]/uhv["v"], "body_pct": body/rng}


def fill(sig):
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    if i0 >= len(ts_arr): return None
    if sig["side"] == "buy":  return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def walk_trail(side, fill_idx, entry_price, entry_ts, cfg):
    """Peak-based trail with catastrophic SL + scratch + max hold."""
    end_ts = entry_ts + cfg["max_hold_min"] * 60 * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9; has_pos = False; trail_armed = False
    be_armed = cfg.get("be_arm_at", 0) > 0
    sl_price = None  # break-even SL replacement
    for k in range(fill_idx + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
            exit_px = bids_arr[k]
        else:
            cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
            exit_px = asks_arr[k]
        peak = max(peak, cur_pnl)
        if cur_pnl > 0: has_pos = True
        # BE arming: once peak ≥ be_arm_at, switch SL to entry (i.e., exit on cur_pnl <= 0)
        if be_armed and peak >= cfg["be_arm_at"] and sl_price is None:
            sl_price = 0.0  # break-even
        # Catastrophic
        if cur_pnl <= -cfg["catastrophic_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "age": elapsed, "peak": peak}
        # Break-even SL (if armed)
        if sl_price is not None and cur_pnl <= sl_price:
            return {"pnl": cur_pnl - COMMISSION, "reason": "BE", "age": elapsed, "peak": peak}
        # Arm trail
        if not trail_armed and peak >= cfg["trail_trigger"]: trail_armed = True
        # Trail exit
        if trail_armed and (peak - cur_pnl) >= cfg["trail_drop"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TRAIL", "age": elapsed, "peak": peak}
        # Scratch
        if not has_pos and elapsed > cfg["scratch_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SCRATCH", "age": elapsed, "peak": peak}
    # End of window
    return {"pnl": cur_pnl - COMMISSION if 'cur_pnl' in dir() else -COMMISSION, "reason": "TIMEOUT", "age": cfg["max_hold_min"]*60, "peak": peak}


def walk_fixed_tp(side, fill_idx, entry_price, entry_ts, cfg):
    end_ts = entry_ts + cfg["max_hold_sec"] * 1000 + 5000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9
    for k in range(fill_idx + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:
            cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        peak = max(peak, cur_pnl)
        if cur_pnl <= -cfg["sl_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "age": elapsed, "peak": peak}
        if cur_pnl >= cfg["tp_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TP", "age": elapsed, "peak": peak}
        if elapsed >= cfg["max_hold_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "KILL", "age": elapsed, "peak": peak}
    return {"pnl": 0, "reason": "OUT", "age": 0, "peak": peak}


VARIANTS = [
    ("A: Zee-loose ($10/$3 trail, $30 cat)",
     walk_trail, {"trail_trigger": 10, "trail_drop": 3, "catastrophic_usd": 30, "scratch_sec": 30, "max_hold_min": 10}),
    ("B: Tighter trail ($5/$2, $20 cat)",
     walk_trail, {"trail_trigger": 5, "trail_drop": 2, "catastrophic_usd": 20, "scratch_sec": 20, "max_hold_min": 5}),
    ("C: Wider trail ($15/$5, $30 cat)",
     walk_trail, {"trail_trigger": 15, "trail_drop": 5, "catastrophic_usd": 30, "scratch_sec": 30, "max_hold_min": 15}),
    ("D: Trail with BE-arm at $5 peak",
     walk_trail, {"trail_trigger": 10, "trail_drop": 3, "catastrophic_usd": 30, "scratch_sec": 30, "max_hold_min": 10, "be_arm_at": 5}),
    ("E: Fixed $5 TP / $15 SL / 30s hold",
     walk_fixed_tp, {"tp_usd": 5, "sl_usd": 15, "max_hold_sec": 30}),
]


def run(label, exit_fn, cfg):
    trades = []; last_entry = 0; daily = {}; halted = set()
    for idx in range(UHV_LOOKBACK + 5, len(m1)):
        bar = m1[idx]; date = bar["date"]
        if SKIP_SYDNEY and bar["hour"] < 6: continue
        if date in halted: continue
        if daily.get(date, 0) <= -DAILY_LOSS_USD: halted.add(date); continue
        if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
        sig = detect(idx)
        if not sig: continue
        f = fill(sig)
        if not f: continue
        fi, fp, ft = f
        r = exit_fn(sig["side"], fi, fp, ft, cfg)
        daily[date] = daily.get(date, 0) + r["pnl"]
        trades.append({"date": date, "side": sig["side"], "pnl": round(r["pnl"], 2),
                       "reason": r["reason"], "age": round(r["age"], 1), "peak": round(r["peak"], 2),
                       "volR": round(sig["vol_ratio"], 2), "body": round(sig["body_pct"], 2)})
        last_entry = ft

    n = len(trades)
    if n == 0: return {"label": label, "n": 0}
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    net = sum(t["pnl"] for t in trades)
    avg = net / n
    reasons = {}
    for t in trades: reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    days_p = sum(1 for p in daily.values() if p > 0)
    days_l = sum(1 for p in daily.values() if p < 0)
    print(f"\n{label}", flush=True)
    print(f"  n={n}  WR={wins/n*100:.1f}%  NET=${net:+.2f}  avg=${avg:+.2f}", flush=True)
    print(f"  days: profit={days_p}/{len(daily)}  loss={days_l}  halted={len(halted)}", flush=True)
    print(f"  reasons: {reasons}", flush=True)
    return {"label": label, "n": n, "wins": wins, "losses": losses,
            "wr_pct": round(wins/n*100,1), "net_usd": round(net,2), "avg_usd": round(avg,2),
            "days_profit": days_p, "days_loss": days_l, "days_halted": len(halted),
            "reasons": reasons,
            "daily_pnl": {d: round(p,2) for d,p in sorted(daily.items())}}


print("\n[BACKTEST] 5 exit variants on Zee's strict UHV entries", flush=True)
results = [run(label, fn, cfg) for label, fn, cfg in VARIANTS]
print("\n=== SUMMARY ===", flush=True)
for r in sorted(results, key=lambda x: -x.get("net_usd", -1e9)):
    if r.get("n", 0) > 0:
        print(f"  {r['label']:<50}  n={r['n']:>4}  WR={r['wr_pct']:>5}%  NET=${r['net_usd']:>+8.2f}  days_profit={r['days_profit']}", flush=True)

OUT_J.write_text(json.dumps({
    "started": datetime.now(timezone.utc).isoformat(),
    "entry_rules": "vol_ratio<0.70, body%>=0.65, opposing_wick<=25%, sydney_filter ON, $100 daily halt",
    "variants": results,
}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
