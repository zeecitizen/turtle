"""UHV breakout with Zee's discretionary exit logic — TICK-LEVEL backtest on yesterday.

Zee's actual approach (from 100-consecutive-wins streak as a human trader):
  1. ENTER on UHV breakout (validated VSA setup: bg context + no-supply candle)
  2. ONLY in trend-confirmed zones (HH+HL or LH+LL clearly visible — skip ranging)
  3. EXIT QUICKLY at FIRST sign of reversal (1-10 seconds typical)
  4. KEEP TRADE ALIVE UNTIL it goes positive (don't bail early on noise)
  5. SCRATCH-EXIT if not positive within N seconds (don't let losses build)

This replaces both FEAR_IDEAL ($60 fixed loss) and TRAIL (waits for $22, books at $16).

Tested at TICK level — walks every actual bid/ask tick from entry forward, not M1 OHLC.
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_uhv_zee_style_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100; SL_BUFFER = 0.05

print("[LOAD]...", flush=True)
df_full = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df_full["time_msc"].max())
last_dt = datetime.fromtimestamp(last_msc/1000, tz=timezone.utc)
target_date = last_dt.replace(hour=0, minute=0, second=0, microsecond=0)
target_date_str = target_date.strftime("%Y-%m-%d")
print(f"Target day: {target_date_str}", flush=True)

# Build M1 bars (full history for trend detection lookback)
df_full["m1"] = (df_full["time_msc"] // 60_000).astype(np.int64)
m1_grp = df_full.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1 = m1_grp.to_dict("records")
print(f"M1 bars total: {len(m1)}", flush=True)

# Tick arrays
ts_arr = df_full["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df_full["bid"].to_numpy(dtype=np.float64)
asks_arr = df_full["ask"].to_numpy(dtype=np.float64)

yesterday_indices = [i for i, b in enumerate(m1) if b["date"] == target_date_str]
if not yesterday_indices:
    print(f"NO BARS for {target_date_str}"); raise SystemExit
print(f"Yesterday M1 bars: {len(yesterday_indices)} (idx {yesterday_indices[0]} to {yesterday_indices[-1]})", flush=True)

# === STRICTER TREND DETECTION (HH+HL with 30-bar lookback, 5-bar fractals) ===
def detect_strict_trend(idx, lookback=30, strength=5):
    if idx < lookback + strength + 5: return None
    swing_highs, swing_lows = [], []
    for j in range(idx - lookback, idx - strength):
        is_high = all(m1[j]["h"] >= m1[k]["h"] for k in range(j-strength, j+strength+1))
        is_low = all(m1[j]["l"] <= m1[k]["l"] for k in range(j-strength, j+strength+1))
        if is_high: swing_highs.append((j, m1[j]["h"]))
        if is_low: swing_lows.append((j, m1[j]["l"]))
    # Need ≥2 swing highs and ≥2 swing lows for clear HH/HL or LH/LL
    if len(swing_highs) < 2 or len(swing_lows) < 2: return None
    h_last_two = [swing_highs[-1][1], swing_highs[-2][1]]
    l_last_two = [swing_lows[-1][1], swing_lows[-2][1]]
    if h_last_two[0] > h_last_two[1] and l_last_two[0] > l_last_two[1]: return "up"
    if h_last_two[0] < h_last_two[1] and l_last_two[0] < l_last_two[1]: return "down"
    return None  # ranging or shifting — skip

# === VSA UHV SIGNAL (existing logic) ===
P = {
    "retracement_window": 10, "min_body_pct": 0.65,
    "max_vol_ratio": 0.70, "bg_lookback": 5, "bg_min_count": 3,
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
        return {"side": "buy", "entry_close": cur["c"], "uhv": uhv,
                "uhv_h": uhv["h"], "uhv_l": uhv["l"],
                "uhv_mid": (uhv["h"] + uhv["l"]) / 2,
                "vol_ratio": round(vol_ratio, 2), "bg_red": bg_red}
    if uhv_green and bg_green >= P["bg_min_count"] and cur["c"] < cur["o"] and cur["c"] < uhv["l"]:
        prior_low = min(m1[j]["l"] for j in range(bg_start, uhv_idx))
        if uhv["h"] <= prior_low + 0.20: return None
        return {"side": "sell", "entry_close": cur["c"], "uhv": uhv,
                "uhv_h": uhv["h"], "uhv_l": uhv["l"],
                "uhv_mid": (uhv["h"] + uhv["l"]) / 2,
                "vol_ratio": round(vol_ratio, 2), "bg_green": bg_green}
    return None

# === ZEE-STYLE TICK-LEVEL EXIT ===
def simulate_zee_exit(entry_ts_ms, side, entry_price, exit_cfg):
    """Walk ticks: keep alive until positive, exit on first reversal once profitable."""
    # Slice tick window (next ~10 minutes = max hold)
    end_ts = entry_ts_ms + exit_cfg["max_hold_min"] * 60 * 1000
    entry_idx = int(np.searchsorted(ts_arr, entry_ts_ms, side="left"))
    end_idx = int(np.searchsorted(ts_arr, end_ts, side="right"))
    if end_idx - entry_idx < 5: return None
    sub_ts = ts_arr[entry_idx:end_idx]
    sub_bids = bids_arr[entry_idx:end_idx]
    sub_asks = asks_arr[entry_idx:end_idx]

    peak_pnl = -1e9
    peak_ts = entry_ts_ms
    has_been_positive = False
    final_pnl = 0; reason = "TIME"; exit_age_s = 0
    for k in range(len(sub_ts)):
        if side == "buy":
            cur_pnl = (sub_bids[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:
            cur_pnl = (entry_price - sub_asks[k]) * CONTRACT_SIZE * LOTS
        elapsed_s = (sub_ts[k] - entry_ts_ms) / 1000.0
        if cur_pnl > peak_pnl:
            peak_pnl = cur_pnl
            peak_ts = sub_ts[k]
        if cur_pnl > 0: has_been_positive = True

        # Hard catastrophic stop (Chandelier-like, in $ for now)
        if cur_pnl <= -exit_cfg["catastrophic_stop_usd"]:
            final_pnl = cur_pnl; reason = "HARD_SL"; exit_age_s = elapsed_s; break
        # Quick scratch: if not positive within N seconds, exit
        if elapsed_s > exit_cfg["quick_scratch_sec"] and not has_been_positive:
            final_pnl = cur_pnl; reason = "QUICK_SCRATCH"; exit_age_s = elapsed_s; break
        # Once positive past min_peak_for_trail, exit on first reversal of N $
        if (peak_pnl >= exit_cfg["min_peak_to_trail_usd"]
            and (peak_pnl - cur_pnl) >= exit_cfg["reversal_exit_usd"]):
            final_pnl = cur_pnl; reason = "FIRST_REVERSAL"; exit_age_s = elapsed_s; break
    else:
        # ran out of ticks
        if len(sub_ts):
            if side == "buy":
                final_pnl = (sub_bids[-1] - entry_price) * CONTRACT_SIZE * LOTS
            else:
                final_pnl = (entry_price - sub_asks[-1]) * CONTRACT_SIZE * LOTS
            exit_age_s = (sub_ts[-1] - entry_ts_ms) / 1000.0
    return {"pnl": round(final_pnl - COMMISSION, 2), "reason": reason,
            "exit_age_s": round(exit_age_s, 1),
            "peak_pnl": round(peak_pnl, 2),
            "peak_age_s": round((peak_ts - entry_ts_ms) / 1000.0, 1),
            "has_been_positive": has_been_positive}

# === RUN ON YESTERDAY ONLY ===
def run_backtest(exit_cfg, require_trend=True, label=""):
    trades = []
    last_idx = -1000
    y_start, y_end = yesterday_indices[0], yesterday_indices[-1]
    for idx in range(max(y_start, P["retracement_window"] + P["bg_lookback"] + 30), y_end + 1):
        if idx - last_idx < P["cooldown_bars"]: continue
        sig = detect_setup(idx)
        if not sig: continue
        if require_trend:
            trend = detect_strict_trend(idx - 1)
            if trend is None: continue
            if sig["side"] == "buy" and trend != "up": continue
            if sig["side"] == "sell" and trend != "down": continue
        # Use the exact close of the breakout candle as entry
        entry_ts_ms = int(m1[idx]["ts_end_ms"])
        entry_price = sig["entry_close"]
        result = simulate_zee_exit(entry_ts_ms, sig["side"], entry_price, exit_cfg)
        if result is None: continue
        result.update({
            "time": pd.to_datetime(entry_ts_ms, unit="ms", utc=True).strftime("%H:%M:%S"),
            "side": sig["side"], "entry": round(entry_price, 2),
            "uhv_h": round(sig["uhv_h"], 2), "uhv_l": round(sig["uhv_l"], 2),
            "vol_ratio": sig["vol_ratio"],
        })
        trades.append(result)
        last_idx = idx
    return trades

def report_trades(trades, label):
    print(f"\n=== {label} ===", flush=True)
    if not trades:
        print("  No signals on yesterday", flush=True); return
    n = len(trades)
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    breakeven = n - wins - losses
    net = sum(t["pnl"] for t in trades)
    avg_peak = np.mean([t["peak_pnl"] for t in trades])
    avg_age = np.mean([t["exit_age_s"] for t in trades])
    by_reason = {}
    for t in trades:
        by_reason[t["reason"]] = by_reason.get(t["reason"], 0) + 1
    print(f"  n={n}  WR={wins/n*100:.1f}% ({wins}W / {losses}L / {breakeven}BE)", flush=True)
    print(f"  Net: ${net:+.2f}   Avg peak: ${avg_peak:+.2f}   Avg exit age: {avg_age:.1f}s", flush=True)
    print(f"  By reason: {by_reason}", flush=True)
    print(f"  {'time':>9} {'side':>4} {'entry':>8} {'volR':>5} {'reason':>14} {'age':>7} {'peak':>8} {'pnl':>8}", flush=True)
    for t in trades:
        print(f"  {t['time']:>9} {t['side']:>4} {t['entry']:>8.2f} {t['vol_ratio']:>5.2f} {t['reason']:>14} {t['exit_age_s']:>6.1f}s ${t['peak_pnl']:>+7.2f} ${t['pnl']:>+7.2f}", flush=True)

# === SWEEP exit configurations ===
EXIT_CONFIGS = [
    # (label, quick_scratch_sec, min_peak_to_trail_usd, reversal_exit_usd, catastrophic_stop_usd, max_hold_min)
    {"label": "Zee-tight (3s scratch / $3 peak / $1 reversal)",
     "quick_scratch_sec": 3, "min_peak_to_trail_usd": 3.0, "reversal_exit_usd": 1.0,
     "catastrophic_stop_usd": 30, "max_hold_min": 5},
    {"label": "Zee-medium (10s scratch / $5 peak / $2 reversal)",
     "quick_scratch_sec": 10, "min_peak_to_trail_usd": 5.0, "reversal_exit_usd": 2.0,
     "catastrophic_stop_usd": 30, "max_hold_min": 5},
    {"label": "Zee-loose (30s scratch / $10 peak / $3 reversal)",
     "quick_scratch_sec": 30, "min_peak_to_trail_usd": 10.0, "reversal_exit_usd": 3.0,
     "catastrophic_stop_usd": 30, "max_hold_min": 10},
    {"label": "Zee-very-loose (60s / $15 peak / $5 reversal)",
     "quick_scratch_sec": 60, "min_peak_to_trail_usd": 15.0, "reversal_exit_usd": 5.0,
     "catastrophic_stop_usd": 30, "max_hold_min": 10},
    {"label": "Zee-EA-mimic (60s / $22 peak / $6 drop, $60 catastrophic)",
     "quick_scratch_sec": 60, "min_peak_to_trail_usd": 22.0, "reversal_exit_usd": 6.0,
     "catastrophic_stop_usd": 60, "max_hold_min": 10},
]

# Run with trend filter ON
print(f"\n{'='*80}", flush=True)
print(f"WITH STRICT TREND FILTER (HH+HL or LH+LL required)", flush=True)
print(f"{'='*80}", flush=True)
all_results_with_trend = {}
for cfg in EXIT_CONFIGS:
    trades = run_backtest(cfg, require_trend=True, label=cfg["label"])
    report_trades(trades, cfg["label"])
    all_results_with_trend[cfg["label"]] = {"config": cfg, "trades": trades}

# Run without trend filter for comparison
print(f"\n{'='*80}", flush=True)
print(f"WITHOUT TREND FILTER (for comparison)", flush=True)
print(f"{'='*80}", flush=True)
all_results_no_trend = {}
for cfg in EXIT_CONFIGS:
    trades = run_backtest(cfg, require_trend=False, label=cfg["label"])
    report_trades(trades, cfg["label"] + " (no trend filter)")
    all_results_no_trend[cfg["label"]] = {"config": cfg, "trades": trades}

# Test fixed-TP variants — exit at first time profit hits $X
def simulate_fixed_tp(entry_ts_ms, side, entry_price, tp_usd, sl_usd, max_hold_min=5):
    end_ts = entry_ts_ms + max_hold_min * 60 * 1000
    entry_idx = int(np.searchsorted(ts_arr, entry_ts_ms, side="left"))
    end_idx = int(np.searchsorted(ts_arr, end_ts, side="right"))
    if end_idx - entry_idx < 5: return None
    sub_ts = ts_arr[entry_idx:end_idx]
    sub_bids = bids_arr[entry_idx:end_idx]
    sub_asks = asks_arr[entry_idx:end_idx]
    peak_pnl = -1e9
    final_pnl = 0; reason = "TIME"; exit_age_s = 0
    for k in range(len(sub_ts)):
        if side == "buy":
            cur_pnl = (sub_bids[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:
            cur_pnl = (entry_price - sub_asks[k]) * CONTRACT_SIZE * LOTS
        elapsed_s = (sub_ts[k] - entry_ts_ms) / 1000.0
        if cur_pnl > peak_pnl: peak_pnl = cur_pnl
        if cur_pnl >= tp_usd:
            final_pnl = cur_pnl; reason = "FIXED_TP"; exit_age_s = elapsed_s; break
        if cur_pnl <= -sl_usd:
            final_pnl = cur_pnl; reason = "FIXED_SL"; exit_age_s = elapsed_s; break
    else:
        if len(sub_ts):
            if side == "buy":
                final_pnl = (sub_bids[-1] - entry_price) * CONTRACT_SIZE * LOTS
            else:
                final_pnl = (entry_price - sub_asks[-1]) * CONTRACT_SIZE * LOTS
            exit_age_s = (sub_ts[-1] - entry_ts_ms) / 1000.0
    return {"pnl": round(final_pnl - COMMISSION, 2), "reason": reason,
            "exit_age_s": round(exit_age_s, 1),
            "peak_pnl": round(peak_pnl, 2), "peak_age_s": 0.0,
            "has_been_positive": peak_pnl > 0}

FIXED_TP_CONFIGS = [
    {"label": "FixedTP $3 / SL $5",  "tp": 3,  "sl": 5},
    {"label": "FixedTP $5 / SL $10", "tp": 5,  "sl": 10},
    {"label": "FixedTP $8 / SL $15", "tp": 8,  "sl": 15},
    {"label": "FixedTP $10 / SL $15","tp": 10, "sl": 15},
    {"label": "FixedTP $15 / SL $20","tp": 15, "sl": 20},
]

print(f"\n{'='*80}", flush=True)
print(f"SYDNEY FILTER (skip 00-06 GMT) + Zee-style exits", flush=True)
print(f"{'='*80}", flush=True)
sydney_filter_results = {}
for cfg in EXIT_CONFIGS:
    trades = []
    last_idx = -1000
    y_start, y_end = yesterday_indices[0], yesterday_indices[-1]
    for idx in range(max(y_start, P["retracement_window"] + P["bg_lookback"] + 30), y_end + 1):
        if idx - last_idx < P["cooldown_bars"]: continue
        sig = detect_setup(idx)
        if not sig: continue
        entry_ts_ms = int(m1[idx]["ts_end_ms"])
        hour = pd.to_datetime(entry_ts_ms, unit="ms", utc=True).hour
        if hour < 6: continue  # skip Sydney
        result = simulate_zee_exit(entry_ts_ms, sig["side"], sig["entry_close"], cfg)
        if result is None: continue
        result.update({
            "time": pd.to_datetime(entry_ts_ms, unit="ms", utc=True).strftime("%H:%M:%S"),
            "side": sig["side"], "entry": round(sig["entry_close"], 2),
            "uhv_h": round(sig["uhv_h"], 2), "uhv_l": round(sig["uhv_l"], 2),
            "vol_ratio": sig["vol_ratio"],
        })
        trades.append(result)
        last_idx = idx
    report_trades(trades, cfg["label"] + " [Sydney-filtered]")
    sydney_filter_results[cfg["label"]] = {"config": cfg, "trades": trades}

print(f"\n{'='*80}", flush=True)
print(f"FIXED TP/SL — straight take-profit at first $X gain", flush=True)
print(f"{'='*80}", flush=True)
fixed_tp_results = {}
for cfg in FIXED_TP_CONFIGS:
    trades = []
    last_idx = -1000
    y_start, y_end = yesterday_indices[0], yesterday_indices[-1]
    for idx in range(max(y_start, P["retracement_window"] + P["bg_lookback"] + 30), y_end + 1):
        if idx - last_idx < P["cooldown_bars"]: continue
        sig = detect_setup(idx)
        if not sig: continue
        entry_ts_ms = int(m1[idx]["ts_end_ms"])
        result = simulate_fixed_tp(entry_ts_ms, sig["side"], sig["entry_close"], cfg["tp"], cfg["sl"])
        if result is None: continue
        result.update({
            "time": pd.to_datetime(entry_ts_ms, unit="ms", utc=True).strftime("%H:%M:%S"),
            "side": sig["side"], "entry": round(sig["entry_close"], 2),
            "uhv_h": round(sig["uhv_h"], 2), "uhv_l": round(sig["uhv_l"], 2),
            "vol_ratio": sig["vol_ratio"],
        })
        trades.append(result)
        last_idx = idx
    report_trades(trades, cfg["label"])
    fixed_tp_results[cfg["label"]] = {"config": cfg, "trades": trades}

doc = {
    "started": datetime.now(timezone.utc).isoformat(),
    "target_date": target_date_str,
    "with_trend_filter": all_results_with_trend,
    "without_trend_filter": all_results_no_trend,
    "fixed_tp": fixed_tp_results,
    "sydney_filtered": sydney_filter_results,
}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
