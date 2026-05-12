"""Zee's manual UHV strategy — verbatim from his 2026-05-11 message.

Direct quote:
  "mein dekhta tha aik UHV, phir usska breakout high ka, breakout candle ka
   volume low ho aur momentum candle ho (rejection na ho uss mein), aur
   close kar deta tha foran hee jaisay hee trade profit mein jati thi"

Rules:
  1. UHV candle visible (highest-vol bar in last 20 closed M1 bars)
  2. Breakout of UHV HIGH (BUY) / LOW (SELL) on next bars
  3. Breakout candle volume < UHV volume × 0.70  (low-volume confirmation)
  4. Breakout candle is momentum candle — body% >= 0.65
  5. NO REJECTION — opposite-side wick <= 25% of candle range
  6. Exit: close at FIRST positive P&L tick (after spread absorbed)
     Backup: scratch-cut at 10s if never positive, $15 catastrophic SL

Runs two exit modes for comparison:
  A) Zee-exact: close at first positive
  B) Traditional: $3 fixed TP (for control)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_manual_replica_results.json")

LOTS          = 0.10
COMMISSION    = 7.0 * LOTS
CONTRACT_SIZE = 100

# === ZEE'S EXACT RULES ===
UHV_LOOKBACK         = 20
UHV_MAX_AGE_BARS     = 10
MIN_BODY_PCT         = 0.65            # rule 4: momentum candle
MAX_VOL_RATIO        = 0.70            # rule 3: breakout candle low-vol
MAX_OPPOSING_WICK_PCT = 0.25           # rule 5: no rejection — opposing wick ≤ 25% of range
PRE_OFFSET_PTS       = 1.0
SKIP_SYDNEY          = True
MIN_SPACING_SEC      = 60
DAILY_LOSS_USD       = 100.0

EXIT_MODE_FIRST_POSITIVE = {
    "label":          "Mode A: Close at first positive tick (Zee's exact)",
    "use_first_pos":  True,
    "scratch_sec":    10,
    "sl_usd":         15.0,
    "max_hold_sec":   30,
}
EXIT_MODE_FIXED_TP = {
    "label":          "Mode B: $3 fixed TP (control)",
    "use_first_pos":  False,
    "tp_usd":         3.0,
    "sl_usd":         15.0,
    "kill_sec":       5,
}

print("[LOAD] parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1_grp = df.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"]   = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1_grp["hour"] = m1_grp["dt"].dt.hour
m1 = m1_grp.to_dict("records")
print(f"  M1 bars: {len(m1):,}  over {m1[0]['date']} .. {m1[-1]['date']}", flush=True)

ts_arr   = df["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df["bid"].to_numpy(dtype=np.float64)
asks_arr = df["ask"].to_numpy(dtype=np.float64)


def detect_zee_signal(idx):
    """Apply Zee's 5 rules. Returns dict if all pass, else None."""
    if idx < UHV_LOOKBACK + 2:
        return None

    # Rule 1: find UHV (highest-vol closed bar in last N)
    win_lo = idx - UHV_LOOKBACK
    uhv_idx = max(range(win_lo, idx), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] <= 0:
        return None
    if (idx - uhv_idx) > UHV_MAX_AGE_BARS:
        return None

    cur = m1[idx]
    # Rule 3: breakout candle vol < UHV vol × 0.70
    vol_ratio = cur["v"] / uhv["v"]
    if vol_ratio > MAX_VOL_RATIO:
        return None

    # Rule 4: momentum candle — strong body
    rng = cur["h"] - cur["l"]
    if rng <= 0:
        return None
    body = abs(cur["c"] - cur["o"])
    body_pct = body / rng
    if body_pct < MIN_BODY_PCT:
        return None

    # Determine direction from UHV color (red UHV = exhausted sellers → BUY break of UHV high)
    is_uhv_red   = uhv["c"] < uhv["o"]
    is_uhv_green = uhv["c"] > uhv["o"]
    if not (is_uhv_red or is_uhv_green):
        return None

    if is_uhv_red:
        # BUY setup — current bar must close above UHV high (breakout)
        if cur["c"] <= uhv["h"]:
            return None
        # Rule 5: no rejection — for BUY, opposing wick = upper wick (high - close)
        upper_wick = cur["h"] - cur["c"]
        if (upper_wick / rng) > MAX_OPPOSING_WICK_PCT:
            return None
        side = "buy"; trigger = uhv["h"]
    else:
        # SELL setup — current bar must close below UHV low
        if cur["c"] >= uhv["l"]:
            return None
        # Rule 5: opposing wick for SELL = lower wick (close - low)
        lower_wick = cur["c"] - cur["l"]
        if (lower_wick / rng) > MAX_OPPOSING_WICK_PCT:
            return None
        side = "sell"; trigger = uhv["l"]

    return {
        "side": side, "trigger": trigger, "ts_end_ms": cur["ts_end_ms"],
        "uhv_h": uhv["h"], "uhv_l": uhv["l"], "vol_ratio": vol_ratio,
        "body_pct": body_pct,
    }


def find_fill(sig):
    """First tick AFTER bar close where price has actually crossed level."""
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    i1 = int(np.searchsorted(ts_arr, sig["ts_end_ms"] + 5*60*1000, side="right"))
    if i1 - i0 < 2:
        return None
    # Market-order fill: take first tick after bar close at ask (buy) or bid (sell)
    if sig["side"] == "buy":
        return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def walk_exit_first_positive(side, fill_idx, entry_price, entry_ts, cfg):
    """Close at FIRST positive P&L tick. Scratch at scratch_sec. SL at sl_usd."""
    end_ts = entry_ts + (cfg["max_hold_sec"] + 5) * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9
    for k in range(fill_idx + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
            exit_px = bids_arr[k]
        else:
            cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
            exit_px = asks_arr[k]
        peak = max(peak, cur_pnl)
        # Catastrophic SL
        if cur_pnl <= -cfg["sl_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "age": elapsed, "peak": peak, "exit_px": exit_px}
        # Zee's exit: first positive after spread absorbed
        if cur_pnl > 0:
            return {"pnl": cur_pnl - COMMISSION, "reason": "FIRST_POS", "age": elapsed, "peak": peak, "exit_px": exit_px}
        # Scratch
        if elapsed >= cfg["scratch_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SCRATCH", "age": elapsed, "peak": peak, "exit_px": exit_px}
        if elapsed >= cfg["max_hold_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TIMEOUT", "age": elapsed, "peak": peak, "exit_px": exit_px}
    return {"pnl": 0.0, "reason": "OUT_OF_DATA", "age": 0, "peak": peak, "exit_px": entry_price}


def walk_exit_fixed_tp(side, fill_idx, entry_price, entry_ts, cfg):
    """Traditional $X TP with kill timer + SL — for comparison."""
    end_ts = entry_ts + (cfg["kill_sec"] + 5) * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9
    for k in range(fill_idx + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
            exit_px = bids_arr[k]
        else:
            cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
            exit_px = asks_arr[k]
        peak = max(peak, cur_pnl)
        if cur_pnl <= -cfg["sl_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "age": elapsed, "peak": peak, "exit_px": exit_px}
        if cur_pnl >= cfg["tp_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TP", "age": elapsed, "peak": peak, "exit_px": exit_px}
        if elapsed >= cfg["kill_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "KILL", "age": elapsed, "peak": peak, "exit_px": exit_px}
    return {"pnl": 0.0, "reason": "OUT_OF_DATA", "age": 0, "peak": peak, "exit_px": entry_price}


def run(mode_cfg, exit_fn):
    print(f"\n{'='*80}\n{mode_cfg['label']}\n{'='*80}", flush=True)
    trades = []
    last_entry_ts = 0
    daily_pnl = {}
    halted_dates = set()
    for idx in range(UHV_LOOKBACK + 5, len(m1)):
        bar = m1[idx]
        date = bar["date"]
        if SKIP_SYDNEY and bar["hour"] < 6:
            continue
        if date in halted_dates:
            continue
        if daily_pnl.get(date, 0) <= -DAILY_LOSS_USD:
            halted_dates.add(date); continue
        if int(bar["ts_end_ms"]) - last_entry_ts < MIN_SPACING_SEC * 1000:
            continue
        sig = detect_zee_signal(idx)
        if not sig:
            continue
        fill = find_fill(sig)
        if not fill:
            continue
        fill_idx, fill_price, fill_ts = fill
        result = exit_fn(sig["side"], fill_idx, fill_price, fill_ts, mode_cfg)
        daily_pnl[date] = daily_pnl.get(date, 0) + result["pnl"]
        trades.append({
            "date": date,
            "time": pd.to_datetime(fill_ts, unit="ms", utc=True).strftime("%H:%M:%S"),
            "side": sig["side"],
            "entry": round(fill_price, 2),
            "uhv_h": round(sig["uhv_h"], 2), "uhv_l": round(sig["uhv_l"], 2),
            "vol_ratio": round(sig["vol_ratio"], 2),
            "body_pct":  round(sig["body_pct"], 2),
            "pnl": round(result["pnl"], 2),
            "reason": result["reason"],
            "age_s": round(result["age"], 1),
            "peak": round(result["peak"], 2),
        })
        last_entry_ts = fill_ts

    n = len(trades)
    if n == 0:
        print("  No signals", flush=True); return {"n": 0}
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    net = sum(t["pnl"] for t in trades)
    avg = net / n
    by_reason = {}
    for t in trades:
        by_reason[t["reason"]] = by_reason.get(t["reason"], 0) + 1
    days_traded = len(set(t["date"] for t in trades))
    days_profit = sum(1 for p in daily_pnl.values() if p > 0)
    days_loss   = sum(1 for p in daily_pnl.values() if p < 0)
    print(f"  Trades:   {n}", flush=True)
    print(f"  WR:       {wins/n*100:.1f}%  ({wins}W / {losses}L)", flush=True)
    print(f"  Net:      ${net:+.2f}   Avg/trade: ${avg:+.2f}", flush=True)
    print(f"  Days:     traded {days_traded}   profit {days_profit}   loss {days_loss}   halted {len(halted_dates)}", flush=True)
    print(f"  Reasons:  {by_reason}", flush=True)
    print(f"  Sample (most recent 10):", flush=True)
    for t in trades[-10:]:
        print(f"    {t['date']} {t['time']} {t['side']:>4}  volR={t['vol_ratio']:.2f}  body={t['body_pct']:.2f}  pnl=${t['pnl']:+7.2f}  ({t['reason']:>9} {t['age_s']:>4.1f}s)  peak=${t['peak']:+.2f}", flush=True)
    return {
        "label": mode_cfg["label"], "n": n, "wins": wins, "losses": losses,
        "wr_pct": round(wins/n*100, 1), "net_usd": round(net, 2), "avg_usd": round(avg, 2),
        "days_traded": days_traded, "days_profit": days_profit, "days_loss": days_loss,
        "by_reason": by_reason,
        "daily_pnl": {d: round(p, 2) for d, p in sorted(daily_pnl.items())},
        "trades": trades,
    }


print(f"\n[BACKTEST] Zee's manual UHV recipe (exact verbatim rules)", flush=True)
print(f"  Lots: {LOTS}   Commission: ${COMMISSION:.2f}", flush=True)
print(f"  Rules: vol_ratio<{MAX_VOL_RATIO}  body%>{MIN_BODY_PCT}  opposing_wick<{MAX_OPPOSING_WICK_PCT}", flush=True)
print(f"  Sydney filter: {'ON' if SKIP_SYDNEY else 'OFF'}   Daily halt: ${DAILY_LOSS_USD}", flush=True)

results = {
    "started": datetime.now(timezone.utc).isoformat(),
    "lots": LOTS,
    "data_range": f"{m1[0]['date']} .. {m1[-1]['date']}",
    "rules": "vol_ratio<0.70, body%>=0.65, opposing_wick<=25%",
    "mode_first_positive": run(EXIT_MODE_FIRST_POSITIVE, walk_exit_first_positive),
    "mode_fixed_tp":       run(EXIT_MODE_FIXED_TP,       walk_exit_fixed_tp),
}

# Slim JSON without per-trade detail
slim = {k: v for k, v in results.items() if k not in ("mode_first_positive", "mode_fixed_tp")}
for k in ("mode_first_positive", "mode_fixed_tp"):
    if results[k].get("n", 0) > 0:
        slim[k] = {kk: vv for kk, vv in results[k].items() if kk != "trades"}
    else:
        slim[k] = results[k]
OUT_J.write_text(json.dumps(slim, indent=2, default=str))

# Save CSVs for inspection
for key, label in [("mode_first_positive", "first_pos"), ("mode_fixed_tp", "fixed_tp")]:
    if results[key].get("trades"):
        pd.DataFrame(results[key]["trades"]).to_csv(OUT_J.parent / f"_zee_replica_{label}.csv", index=False)

print(f"\n[DONE] -> {OUT_J}", flush=True)
