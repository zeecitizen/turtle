"""VSA Reversal Entry — earlier than UHV breakout.

Pattern (long version — short is mirrored):
  1. Uptrend: current bar > highest high of bars [-30 to -10]
  2. Retracement: price dropped $3-8 from recent swing high in last 5-15 bars
  3. UHV red bar within retracement window (highest-volume bar is red)
  4. Continued retracement: at least 1 bar AFTER UHV that's red OR makes lower low
  5. Reversal trigger (current bar):
        a. Bullish engulfing: green, open <= prev close, close >= prev open
        b. 2-bar reversal: prev bar new low + closed lower half; cur closes > prev high
  6. Volume confirm: current bar volume < UHV volume (still no supply)
  7. Entry: at close of reversal bar
  8. Exit: Zee-loose tick-level (30s scratch / $10 peak / $3 reversal / $30 catastrophic / 10min hold)

Run on yesterday only (2026-05-07).
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_vsa_reversal_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100

print("[LOAD]...", flush=True)
df_full = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df_full["time_msc"].max())
last_dt = datetime.fromtimestamp(last_msc/1000, tz=timezone.utc)
target_date_str = last_dt.strftime("%Y-%m-%d")
print(f"Target day: {target_date_str}", flush=True)

df_full["m1"] = (df_full["time_msc"] // 60_000).astype(np.int64)
m1_grp = df_full.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1 = m1_grp.to_dict("records")
print(f"M1 bars total: {len(m1)}", flush=True)

ts_arr = df_full["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df_full["bid"].to_numpy(dtype=np.float64)
asks_arr = df_full["ask"].to_numpy(dtype=np.float64)

yesterday_indices = [i for i, b in enumerate(m1) if b["date"] == target_date_str]
print(f"Yesterday M1 bars: {len(yesterday_indices)}", flush=True)

# === DETECTION RULES ===
P = {
    "trend_lookback_far": 30, "trend_lookback_near": 10,
    "retr_min": 3.0, "retr_max": 8.0,
    "retr_window": 15,
    "uhv_lookback": 10, "uhv_min_post_bars": 1,
    "min_body_pct_trigger": 0.5,
    "cooldown_bars": 5,
}

def is_red(b): return b["c"] < b["o"]
def is_green(b): return b["c"] > b["o"]

def detect_long_reversal(idx):
    """Returns dict if pattern matches, None otherwise."""
    if idx < P["trend_lookback_far"] + 5: return None
    cur = m1[idx]; prev = m1[idx-1]

    # 1. Uptrend: cur high > highest high in [-30, -10]
    trend_window_h = max(m1[j]["h"] for j in range(idx - P["trend_lookback_far"], idx - P["trend_lookback_near"]))
    if cur["h"] <= trend_window_h: return None

    # 2. Retracement: find recent swing high in [-retr_window, -1]; current low must be $3-8 below it
    swing_high = max(m1[j]["h"] for j in range(idx - P["retr_window"], idx))
    drop = swing_high - cur["l"]
    if drop < P["retr_min"] or drop > P["retr_max"]: return None

    # 3. UHV red in retracement window (last retr_window bars before current)
    retr_bars = list(range(idx - P["retr_window"], idx))
    uhv_idx = max(retr_bars, key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if not is_red(uhv): return None
    if uhv["v"] == 0: return None

    # 4. Continued retracement: at least 1 bar after UHV that's red OR made lower low
    post_uhv = list(range(uhv_idx + 1, idx))
    if len(post_uhv) < P["uhv_min_post_bars"]: return None
    post_red_or_lower = sum(1 for j in post_uhv if is_red(m1[j]) or m1[j]["l"] < uhv["l"])
    if post_red_or_lower < 1: return None

    # 5. Reversal trigger: bullish engulfing OR 2BR
    is_engulf = (is_green(cur) and cur["o"] <= prev["c"] and cur["c"] >= prev["o"])
    prev_low_extreme = prev["l"] <= min(m1[j]["l"] for j in range(idx - 5, idx))
    prev_close_lower_half = (prev["c"] - prev["l"]) / max(0.001, prev["h"] - prev["l"]) <= 0.5
    is_2br = (prev_low_extreme and prev_close_lower_half and cur["c"] > prev["h"])
    if not (is_engulf or is_2br): return None

    # 6. Volume confirm: cur vol < uhv vol (no supply)
    if cur["v"] >= uhv["v"]: return None

    # body confirmation
    cur_body = abs(cur["c"] - cur["o"])
    cur_range = cur["h"] - cur["l"]
    if cur_range < 0.01 or cur_body / cur_range < P["min_body_pct_trigger"]: return None

    trigger = "ENGULF" if is_engulf else "2BR"
    return {"side": "buy", "entry_close": cur["c"], "trigger": trigger,
            "swing_high": round(swing_high, 2), "retracement": round(drop, 2),
            "uhv_idx": uhv_idx, "uhv_v": uhv["v"], "cur_v": cur["v"],
            "vol_ratio": round(cur["v"] / max(1, uhv["v"]), 2)}

def detect_short_reversal(idx):
    """Mirrored: downtrend + rally + UHV green + bearish engulfing/2BR top."""
    if idx < P["trend_lookback_far"] + 5: return None
    cur = m1[idx]; prev = m1[idx-1]

    trend_window_l = min(m1[j]["l"] for j in range(idx - P["trend_lookback_far"], idx - P["trend_lookback_near"]))
    if cur["l"] >= trend_window_l: return None

    swing_low = min(m1[j]["l"] for j in range(idx - P["retr_window"], idx))
    rise = cur["h"] - swing_low
    if rise < P["retr_min"] or rise > P["retr_max"]: return None

    rally_bars = list(range(idx - P["retr_window"], idx))
    uhv_idx = max(rally_bars, key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if not is_green(uhv): return None
    if uhv["v"] == 0: return None

    post_uhv = list(range(uhv_idx + 1, idx))
    if len(post_uhv) < P["uhv_min_post_bars"]: return None
    post_green_or_higher = sum(1 for j in post_uhv if is_green(m1[j]) or m1[j]["h"] > uhv["h"])
    if post_green_or_higher < 1: return None

    is_engulf = (is_red(cur) and cur["o"] >= prev["c"] and cur["c"] <= prev["o"])
    prev_high_extreme = prev["h"] >= max(m1[j]["h"] for j in range(idx - 5, idx))
    prev_close_upper_half = (prev["h"] - prev["c"]) / max(0.001, prev["h"] - prev["l"]) <= 0.5
    is_2br = (prev_high_extreme and prev_close_upper_half and cur["c"] < prev["l"])
    if not (is_engulf or is_2br): return None

    if cur["v"] >= uhv["v"]: return None

    cur_body = abs(cur["c"] - cur["o"])
    cur_range = cur["h"] - cur["l"]
    if cur_range < 0.01 or cur_body / cur_range < P["min_body_pct_trigger"]: return None

    trigger = "ENGULF" if is_engulf else "2BR"
    return {"side": "sell", "entry_close": cur["c"], "trigger": trigger,
            "swing_low": round(swing_low, 2), "rally": round(rise, 2),
            "uhv_idx": uhv_idx, "uhv_v": uhv["v"], "cur_v": cur["v"],
            "vol_ratio": round(cur["v"] / max(1, uhv["v"]), 2)}

# === ZEE-LOOSE TICK EXIT ===
EXIT_CFG = {"quick_scratch_sec": 30, "min_peak_to_trail_usd": 10.0,
            "reversal_exit_usd": 3.0, "catastrophic_stop_usd": 30, "max_hold_min": 10}

def simulate_zee_exit(entry_ts_ms, side, entry_price):
    end_ts = entry_ts_ms + EXIT_CFG["max_hold_min"] * 60 * 1000
    i0 = int(np.searchsorted(ts_arr, entry_ts_ms, side="left"))
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    if i1 - i0 < 5: return None
    sub_ts = ts_arr[i0:i1]; sub_bids = bids_arr[i0:i1]; sub_asks = asks_arr[i0:i1]
    peak_pnl = -1e9; peak_ts = entry_ts_ms; has_pos = False
    final = 0; reason = "TIME"; age = 0
    for k in range(len(sub_ts)):
        cur = (sub_bids[k] - entry_price) * CONTRACT_SIZE * LOTS if side == "buy" \
              else (entry_price - sub_asks[k]) * CONTRACT_SIZE * LOTS
        elapsed = (sub_ts[k] - entry_ts_ms) / 1000.0
        if cur > peak_pnl: peak_pnl = cur; peak_ts = sub_ts[k]
        if cur > 0: has_pos = True
        if cur <= -EXIT_CFG["catastrophic_stop_usd"]:
            final = cur; reason = "HARD_SL"; age = elapsed; break
        if elapsed > EXIT_CFG["quick_scratch_sec"] and not has_pos:
            final = cur; reason = "QUICK_SCRATCH"; age = elapsed; break
        if peak_pnl >= EXIT_CFG["min_peak_to_trail_usd"] and (peak_pnl - cur) >= EXIT_CFG["reversal_exit_usd"]:
            final = cur; reason = "FIRST_REVERSAL"; age = elapsed; break
    else:
        if len(sub_ts):
            final = (sub_bids[-1] - entry_price) * CONTRACT_SIZE * LOTS if side == "buy" \
                    else (entry_price - sub_asks[-1]) * CONTRACT_SIZE * LOTS
            age = (sub_ts[-1] - entry_ts_ms) / 1000.0
    return {"pnl": round(final - COMMISSION, 2), "reason": reason,
            "exit_age_s": round(age, 1),
            "peak_pnl": round(peak_pnl, 2),
            "peak_age_s": round((peak_ts - entry_ts_ms) / 1000.0, 1),
            "has_been_positive": has_pos}

# === RUN ===
def run(sydney_filter=True):
    trades = []
    last_idx = -1000
    y_start, y_end = yesterday_indices[0], yesterday_indices[-1]
    for idx in range(max(y_start, P["trend_lookback_far"] + P["retr_window"] + 5), y_end + 1):
        if idx - last_idx < P["cooldown_bars"]: continue
        sig = detect_long_reversal(idx) or detect_short_reversal(idx)
        if not sig: continue
        entry_ts = int(m1[idx]["ts_end_ms"])
        if sydney_filter:
            hr = pd.to_datetime(entry_ts, unit="ms", utc=True).hour
            if hr < 6: continue
        result = simulate_zee_exit(entry_ts, sig["side"], sig["entry_close"])
        if result is None: continue
        result.update({
            "time": pd.to_datetime(entry_ts, unit="ms", utc=True).strftime("%H:%M:%S"),
            "side": sig["side"], "entry": round(sig["entry_close"], 2),
            "trigger": sig["trigger"], "vol_ratio": sig["vol_ratio"],
            "retr_or_rally": sig.get("retracement", sig.get("rally", 0)),
        })
        trades.append(result)
        last_idx = idx
    return trades

def report(trades, label):
    print(f"\n=== {label} ===", flush=True)
    if not trades:
        print("  No signals", flush=True); return
    n = len(trades); wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    net = sum(t["pnl"] for t in trades)
    avg_peak = np.mean([t["peak_pnl"] for t in trades])
    avg_age = np.mean([t["exit_age_s"] for t in trades])
    by_reason = {}
    by_trigger = {}
    for t in trades:
        by_reason[t["reason"]] = by_reason.get(t["reason"], 0) + 1
        by_trigger[t["trigger"]] = by_trigger.get(t["trigger"], 0) + 1
    print(f"  n={n}  WR={wins/n*100:.1f}% ({wins}W / {losses}L)", flush=True)
    print(f"  Net: ${net:+.2f}   Avg peak: ${avg_peak:+.2f}   Avg exit age: {avg_age:.1f}s", flush=True)
    print(f"  By reason: {by_reason}   By trigger: {by_trigger}", flush=True)
    print(f"  {'time':>9} {'side':>4} {'entry':>8} {'trig':>7} {'volR':>5} {'move':>5} {'reason':>14} {'age':>7} {'peak':>8} {'pnl':>8}", flush=True)
    for t in trades:
        print(f"  {t['time']:>9} {t['side']:>4} {t['entry']:>8.2f} {t['trigger']:>7} {t['vol_ratio']:>5.2f} {t['retr_or_rally']:>5.2f} {t['reason']:>14} {t['exit_age_s']:>6.1f}s ${t['peak_pnl']:>+7.2f} ${t['pnl']:>+7.2f}", flush=True)

print(f"\n{'='*80}\nVSA REVERSAL ENTRY — yesterday only ({target_date_str})\n{'='*80}", flush=True)
trades_with_syd = run(sydney_filter=True)
report(trades_with_syd, "Sydney-filtered")
trades_all = run(sydney_filter=False)
report(trades_all, "All sessions (for comparison)")

doc = {
    "started": datetime.now(timezone.utc).isoformat(),
    "target_date": target_date_str,
    "params": P, "exit_cfg": EXIT_CFG,
    "sydney_filtered": trades_with_syd,
    "all_sessions": trades_all,
}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
