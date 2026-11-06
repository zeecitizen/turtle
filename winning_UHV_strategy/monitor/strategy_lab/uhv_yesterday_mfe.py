"""UHV breakout backtest on YESTERDAY ONLY (2026-05-07).

For each signal: track Max Favorable Excursion (MFE) and Max Adverse Excursion (MAE).
Goal: what % of trades had price move into POSITIVE at any point — i.e., the breakout
direction was correct at least temporarily.

Uses the validated VSA config: bg context (≥3 red bars before UHV), no-supply candle
(volR ≤ 0.70), strong body (≥0.65), 10-bar retracement window.
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_uhv_yesterday_mfe.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100; SL_BUFFER = 0.05

print("[LOAD]...", flush=True)
df_full = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
# Filter to yesterday only — figure out yesterday from latest tick
last_msc = int(df_full["time_msc"].max())
last_dt = datetime.fromtimestamp(last_msc/1000, tz=timezone.utc)
yesterday = last_dt.replace(hour=0, minute=0, second=0, microsecond=0)
day_before = yesterday  # most recent full day = same as parquet's last day if before midnight UTC
# Use parquet's last full day
print(f"Parquet spans up to {last_dt}")
target_date_str = yesterday.strftime("%Y-%m-%d")
print(f"Target day (yesterday's full session): {target_date_str}", flush=True)

# Build M1 bars across the WHOLE parquet (need history before yesterday for retracement window)
df_full["m1"] = (df_full["time_msc"] // 60_000).astype(np.int64)
m1_grp = df_full.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1 = m1_grp.to_dict("records")
print(f"M1 bars total: {len(m1)}", flush=True)

# Find indices of yesterday's bars
yesterday_indices = [i for i, b in enumerate(m1) if b["date"] == target_date_str]
if not yesterday_indices:
    print(f"NO BARS for {target_date_str} — check parquet date range")
    raise SystemExit
print(f"Yesterday bars: {len(yesterday_indices)} (idx {yesterday_indices[0]} to {yesterday_indices[-1]})", flush=True)

# === Validated VSA config (best OOS performer) ===
P = {
    "retracement_window": 10,
    "tp_r": 3.0,
    "min_body_pct": 0.65,
    "max_vol_ratio": 0.70,
    "bg_lookback": 5,
    "bg_min_count": 3,
    "require_structural_trend": False,
    "use_invalidation": True,
    "cooldown_bars": 5,
}

def detect_setup(idx):
    if idx < P["retracement_window"] + P["bg_lookback"] + 5: return None
    win_start = max(0, idx - P["retracement_window"])
    uhv_idx = max(range(win_start, idx), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] == 0: return None
    if uhv_idx >= idx - 1: return None
    if uhv_idx < win_start + P["bg_lookback"]: return None
    uhv_red = uhv["c"] < uhv["o"]
    uhv_green = uhv["c"] > uhv["o"]
    bg_start = max(0, uhv_idx - P["bg_lookback"])
    bg_bars = m1[bg_start:uhv_idx]
    bg_red = sum(1 for b in bg_bars if b["c"] < b["o"])
    bg_green = sum(1 for b in bg_bars if b["c"] > b["o"])
    cur = m1[idx]
    cur_body = abs(cur["c"] - cur["o"])
    cur_range = cur["h"] - cur["l"]
    if cur_range < 0.01: return None
    if cur_body / cur_range < P["min_body_pct"]: return None
    vol_ratio = cur["v"] / max(1, uhv["v"])
    if vol_ratio > P["max_vol_ratio"]: return None
    if uhv_red and bg_red >= P["bg_min_count"] and cur["c"] > cur["o"] and cur["c"] > uhv["h"]:
        prior_high = max(m1[j]["h"] for j in range(bg_start, uhv_idx))
        if uhv["l"] >= prior_high - 0.20: return None
        return {"side": "buy", "entry": cur["c"], "uhv": uhv,
                "uhv_h": uhv["h"], "uhv_l": uhv["l"], "uhv_mid": (uhv["h"]+uhv["l"])/2,
                "breakout_wick_low": cur["l"], "vol_ratio": round(vol_ratio,2),
                "bg_red": bg_red}
    if uhv_green and bg_green >= P["bg_min_count"] and cur["c"] < cur["o"] and cur["c"] < uhv["l"]:
        prior_low = min(m1[j]["l"] for j in range(bg_start, uhv_idx))
        if uhv["h"] <= prior_low + 0.20: return None
        return {"side": "sell", "entry": cur["c"], "uhv": uhv,
                "uhv_h": uhv["h"], "uhv_l": uhv["l"], "uhv_mid": (uhv["h"]+uhv["l"])/2,
                "breakout_wick_high": cur["h"], "vol_ratio": round(vol_ratio,2),
                "bg_green": bg_green}
    return None

def simulate_with_mfe(idx, sig, max_bars=120):
    """Track MFE / MAE per trade plus normal SL/TP/INVAL/TIME exit."""
    side = sig["side"]
    entry = sig["entry"]
    if side == "buy":
        sl = sig["breakout_wick_low"] - SL_BUFFER
    else:
        sl = sig["breakout_wick_high"] + SL_BUFFER
    risk = abs(entry - sl)
    if risk < 0.05: return None
    tp = entry + P["tp_r"] * risk if side == "buy" else entry - P["tp_r"] * risk
    mfe = 0.0  # max favorable price excursion (in USD per LOTS)
    mae = 0.0
    mfe_age = 0
    final_pnl = None; reason = None; age = 0
    for off in range(1, max_bars + 1):
        i = idx + off
        if i >= len(m1): break
        b = m1[i]
        # Track MFE/MAE intra-bar via high/low
        if side == "buy":
            fav_pnl = (b["h"] - entry) * 100 * LOTS
            adv_pnl = (b["l"] - entry) * 100 * LOTS  # adverse for buy
        else:
            fav_pnl = (entry - b["l"]) * 100 * LOTS
            adv_pnl = (entry - b["h"]) * 100 * LOTS  # adverse for sell
        if fav_pnl > mfe: mfe = fav_pnl; mfe_age = off
        if adv_pnl < mae: mae = adv_pnl
        # Hard exits (using same close-based logic as before)
        if side == "buy":
            if b["l"] <= sl:
                final_pnl = (sl - entry) * 100 * LOTS - COMMISSION
                reason = "SL"; age = off; break
            if b["h"] >= tp:
                final_pnl = (tp - entry) * 100 * LOTS - COMMISSION
                reason = "TP"; age = off; break
            if P["use_invalidation"] and b["c"] < sig["uhv_mid"]:
                final_pnl = (b["c"] - entry) * 100 * LOTS - COMMISSION
                reason = "INVAL"; age = off; break
        else:
            if b["h"] >= sl:
                final_pnl = (entry - sl) * 100 * LOTS - COMMISSION
                reason = "SL"; age = off; break
            if b["l"] <= tp:
                final_pnl = (entry - tp) * 100 * LOTS - COMMISSION
                reason = "TP"; age = off; break
            if P["use_invalidation"] and b["c"] > sig["uhv_mid"]:
                final_pnl = (entry - b["c"]) * 100 * LOTS - COMMISSION
                reason = "INVAL"; age = off; break
    if final_pnl is None:
        last = m1[min(idx + max_bars, len(m1)-1)]
        move = (last["c"] - entry) if side == "buy" else (entry - last["c"])
        final_pnl = move * 100 * LOTS - COMMISSION
        reason = "TIME"; age = max_bars
    return {
        "reason": reason, "pnl": round(final_pnl, 2), "age": age,
        "mfe": round(mfe, 2), "mae": round(mae, 2), "mfe_age_bars": mfe_age,
    }

# Run on yesterday's bars only
trades = []
last_trade_idx = -1000
y_start, y_end = yesterday_indices[0], yesterday_indices[-1]
for idx in range(max(y_start, P["retracement_window"] + P["bg_lookback"] + 5), y_end + 1):
    if idx - last_trade_idx < P["cooldown_bars"]: continue
    sig = detect_setup(idx)
    if not sig: continue
    res = simulate_with_mfe(idx, sig)
    if res is None: continue
    res.update({
        "ts_end_ms": m1[idx]["ts_end_ms"],
        "time": pd.to_datetime(m1[idx]["ts_end_ms"], unit="ms", utc=True).strftime("%H:%M:%S"),
        "side": sig["side"], "entry": round(sig["entry"], 2),
        "uhv_h": round(sig["uhv_h"], 2), "uhv_l": round(sig["uhv_l"], 2),
        "vol_ratio": sig["vol_ratio"],
    })
    trades.append(res)
    last_trade_idx = idx

print(f"\n=== UHV BREAKOUT — YESTERDAY ({target_date_str}) ===", flush=True)
print(f"Total signals: {len(trades)}", flush=True)
if trades:
    n = len(trades)
    correct_direction = sum(1 for t in trades if t["mfe"] > 0)
    full_wins = sum(1 for t in trades if t["pnl"] > 0)
    sl_hits = sum(1 for t in trades if t["reason"] == "SL")
    tp_hits = sum(1 for t in trades if t["reason"] == "TP")
    inval_hits = sum(1 for t in trades if t["reason"] == "INVAL")
    time_hits = sum(1 for t in trades if t["reason"] == "TIME")
    net = sum(t["pnl"] for t in trades)
    avg_mfe = np.mean([t["mfe"] for t in trades])
    avg_mae = np.mean([t["mae"] for t in trades])
    median_mfe = np.median([t["mfe"] for t in trades])
    print(f"\n📊 BREAKOUT DIRECTION ACCURACY (MFE > 0):", flush=True)
    print(f"  Trades that EVER went into positive: {correct_direction} / {n} = {correct_direction/n*100:.1f}%", flush=True)
    print(f"\n📊 OUTCOME breakdown:", flush=True)
    print(f"  TP hit (full win):   {tp_hits} / {n} = {tp_hits/n*100:.1f}%", flush=True)
    print(f"  INVAL (early exit):  {inval_hits} / {n} = {inval_hits/n*100:.1f}%", flush=True)
    print(f"  SL hit (full loss):  {sl_hits} / {n} = {sl_hits/n*100:.1f}%", flush=True)
    print(f"  TIME (held to end):  {time_hits} / {n}", flush=True)
    print(f"  Final P&L wins:      {full_wins} / {n} = {full_wins/n*100:.1f}% WR", flush=True)
    print(f"\n💵 P&L stats:", flush=True)
    print(f"  Net P&L: ${net:.2f}", flush=True)
    print(f"  Avg MFE per trade: ${avg_mfe:.2f}", flush=True)
    print(f"  Median MFE: ${median_mfe:.2f}", flush=True)
    print(f"  Avg MAE: ${avg_mae:.2f}", flush=True)

    print(f"\n=== ALL TRADES (chronological) ===", flush=True)
    print(f"{'time':>9} {'side':>4} {'entry':>8} {'uhv':>16} {'volR':>5} {'MFE':>8} {'MAE':>8} {'reason':>7} {'pnl':>8}", flush=True)
    for t in trades:
        uhv_str = f"{t['uhv_l']}-{t['uhv_h']}"
        print(f"{t['time']:>9} {t['side']:>4} {t['entry']:>8.2f} {uhv_str:>16} {t['vol_ratio']:>5.2f} ${t['mfe']:>7.2f} ${t['mae']:>7.2f} {t['reason']:>7} ${t['pnl']:>+7.2f}", flush=True)

    doc = {
        "date": target_date_str, "n_trades": n,
        "breakout_direction_correct_pct": round(correct_direction/n*100, 2),
        "full_wr_pct": round(full_wins/n*100, 2),
        "tp_hit_pct": round(tp_hits/n*100, 2),
        "inval_hit_pct": round(inval_hits/n*100, 2),
        "sl_hit_pct": round(sl_hits/n*100, 2),
        "net_pnl": round(net, 2),
        "avg_mfe": round(avg_mfe, 2), "median_mfe": round(median_mfe, 2),
        "avg_mae": round(avg_mae, 2),
        "trades": trades,
    }
    OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
