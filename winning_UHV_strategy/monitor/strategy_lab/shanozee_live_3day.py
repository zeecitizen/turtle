"""3-day Shano-Zee LIVE backtest on real Blueberry ticks.

Replicates the active live config (Common\\Files\\shano_config.json):
  Detection:  M5 2-candle bigness (body > 1.5x prev1, same direction)
  Filters:
    - UHV breakout (M1, lookback=20, triggerPastUhvPts=0.3)
    - 2-min EMA 34/89 trend
    - Setup 1 hard gate (lookback 3, pattern 10) + effort/result
    - M15 trend (EMA 34/89 on M15)
    - Tick-speed (last tick must be within 15s)
    - Spread max (1.2x median)
    - Burst-delta (5s tick delta in trade direction)
    - chainStopAfterLoss=2, maxBurst=7, maxPositions=3, dailyCap=$500
  Probe:    0.01 lot, confirm 0.75, fail 3.0, no timeout, probeTrail (3/1)
  Main:     0.30 lot, trail 22/6, fearIdeal=$60, fearWashout=180s,
            burstSlUsd=$15 (burst-only), mainNoGreen=60s/peak$3
  Skip:     cddDivExit (deferred — needs tick velocity analysis)

Output: monitor/strategy_lab/_shanozee_live_3day.json + .csv
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_shanozee_live_3day.json")
OUT_C = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_shanozee_live_3day_trades.csv")

# === LIVE CONFIG (mirror of Common\Files\shano_config.json, 2026-05-07) ===
CFG = {
    "probeConfirm": 0.75, "probeFail": 3.0, "probeLots": 0.01, "probeTimeout": 0,
    "probeTrailEnabled": True, "probeTrailTrigger": 3.0, "probeTrailDrop": 1.0,
    "trailTrigger": 22.0, "trailDrop": 6.0,
    "fearIdeal": 60.0, "fearWashout": 180.0, "burstSlUsd": 15.0,
    "mainNoGreenEnabled": True, "mainNoGreenSec": 60, "mainNoGreenPeakMin": 3.0,
    "lotLadder": True, "lotLadderStart": 0.30, "lotLadderStep": -0.07, "lotLadderMax": 0.30,
    "overrideLots": 0.30,
    "tickSpeedMaxSec": 15, "spreadMaxMult": 1.2,
    "uhvFilter": True, "uhvLookback": 20, "triggerPastUhvPts": 0.3,
    "trendFilter": True, "trendTfMinutes": 2,
    "m15TrendFilter": True,
    "setup1Filter": True, "setup1LookbackBars": 3, "setup1PatternLookback": 10,
    "setup1EffortResult": True, "effortBodyMin": 0.50, "effortWickMax": 0.40,
    "burstDeltaFilter": True, "burstDeltaLookbackSec": 5,
    "chainStopAfterLoss": 2,
    "maxBurst": 7, "maxPositions": 3, "dailyCap": 500.0,
    "sellOnly": False,
    "BIG_RATIO": 1.5,  # Pine: body > 1.5x prev1
}
CONTRACT_SIZE = 100
COMMISSION = 7.0  # $/lot RT

# === LOAD: last 3 days of ticks ===
print("[LOAD] reading parquet (last 3 days only)...", flush=True)
df_full = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df_full["time_msc"].max())
window_start_msc = last_msc - 3 * 86400 * 1000
df = df_full[df_full["time_msc"] >= window_start_msc].reset_index(drop=True)
del df_full
print(f"[LOAD] {len(df):,} ticks in last 3 days", flush=True)
ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)
mids = (bids + asks) / 2

def find_idx(t_ms): return int(np.searchsorted(ts, t_ms, side="right"))

# === BUILD BARS at M1, M2, M5, M15 ===
def build_bars(tf_sec):
    bucket = (df["time_msc"] // (tf_sec * 1000)).astype(np.int64)
    g = df.assign(_b=bucket).groupby("_b", sort=True).agg(
        open=("bid","first"), high=("bid","max"), low=("bid","min"),
        close=("bid","last"), n_ticks=("bid","count"),
        ts_start_ms=("time_msc","first"), ts_end_ms=("time_msc","last"),
    ).reset_index().drop(columns="_b")
    g["body"] = (g["close"] - g["open"]).abs()
    g["dir"]  = np.sign(g["close"] - g["open"]).astype(int)
    return g

print("[BARS] building M1/M2/M5/M15...", flush=True)
b_m1 = build_bars(60)
b_m2 = build_bars(120)
b_m5 = build_bars(300)
b_m15 = build_bars(900)
print(f"  M1={len(b_m1)} M2={len(b_m2)} M5={len(b_m5)} M15={len(b_m15)}", flush=True)

# Median spread (in pts) for spreadMaxMult
spread_pts_all = ((df["ask"] - df["bid"]) * 100).to_numpy()
median_spread = float(np.median(spread_pts_all))
print(f"  median spread: {median_spread:.1f} pts", flush=True)

# === EMA on M2 + M15 (trend filter) ===
def ema(values, period):
    alpha = 2 / (period + 1)
    out = np.zeros(len(values))
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i-1]
    return out

m2_close = b_m2["close"].to_numpy()
m2_ts    = b_m2["ts_end_ms"].to_numpy()
m2_ema34 = ema(m2_close, 34)
m2_ema89 = ema(m2_close, 89)

m15_close = b_m15["close"].to_numpy()
m15_ts    = b_m15["ts_end_ms"].to_numpy()
m15_ema34 = ema(m15_close, 34)
m15_ema89 = ema(m15_close, 89)

def trend_at(ts_ms, ema_f_arr, ema_s_arr, bar_ts_arr, dir_sign):
    """Return True if M2/M15 trend agrees with dir_sign."""
    idx = int(np.searchsorted(bar_ts_arr, ts_ms, side="right")) - 1
    if idx < 89: return False
    f = ema_f_arr[idx]; s = ema_s_arr[idx]; fp = ema_f_arr[idx-1]
    if dir_sign == 1:
        return f > s and f > fp
    else:
        return f < s and f < fp

# === UHV BREAKOUT FILTER (M1, lookback 20, +0.3 margin) ===
m1_o = b_m1["open"].to_numpy()
m1_h = b_m1["high"].to_numpy()
m1_l = b_m1["low"].to_numpy()
m1_c = b_m1["close"].to_numpy()
m1_v = b_m1["n_ticks"].to_numpy()
m1_ts_end = b_m1["ts_end_ms"].to_numpy()

def uhv_breakout_ok(sig_ts_ms, dir_sign, trigger_close):
    idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1  # bar that just closed
    if idx < CFG["uhvLookback"] + 1: return False
    lookback_start = max(0, idx - CFG["uhvLookback"])
    look_v = m1_v[lookback_start:idx]
    if len(look_v) == 0: return False
    uhv_local = int(np.argmax(look_v))
    uhv_global = lookback_start + uhv_local
    if dir_sign == 1:
        return trigger_close > m1_h[uhv_global] + CFG["triggerPastUhvPts"]
    else:
        return trigger_close < m1_l[uhv_global] - CFG["triggerPastUhvPts"]

# === SETUP 1 HARD GATE (M1) ===
def setup1_active(sig_ts_ms, dir_sign):
    idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1
    needed = CFG["setup1LookbackBars"] + CFG["setup1PatternLookback"] + 2
    if idx < needed: return False
    for trig_off in range(CFG["setup1LookbackBars"]):
        trig_idx = idx - trig_off
        # Find UHV (highest tick-vol matching color) in pattern lookback BEFORE trigger
        s_start = max(0, trig_idx - CFG["setup1PatternLookback"])
        s_end = trig_idx
        if s_end <= s_start: continue
        match_color = (dir_sign == 1)  # dir 1=BUY, find RED UHV; dir -1=SELL, find GREEN UHV
        uhv_idx = -1; uhv_vol = -1
        for s in range(s_start, s_end):
            isRed = m1_c[s] < m1_o[s]
            isGreen = m1_c[s] > m1_o[s]
            colored = isRed if match_color else isGreen
            if colored and m1_v[s] > uhv_vol:
                uhv_vol = m1_v[s]; uhv_idx = s
        if uhv_idx < 0: continue
        # Sweep: any bar between uhv_idx+1 and trig_idx-1 broke UHV extreme
        swept = False
        for s in range(uhv_idx + 1, trig_idx):
            if dir_sign == 1 and m1_l[s] < m1_l[uhv_idx]: swept = True; break
            if dir_sign == -1 and m1_h[s] > m1_h[uhv_idx]: swept = True; break
        if not swept: continue
        # Effort/result on UHV bar
        if CFG["setup1EffortResult"]:
            rng = m1_h[uhv_idx] - m1_l[uhv_idx]
            if rng <= 0: continue
            body = abs(m1_c[uhv_idx] - m1_o[uhv_idx])
            uw = m1_h[uhv_idx] - max(m1_o[uhv_idx], m1_c[uhv_idx])
            lw = min(m1_o[uhv_idx], m1_c[uhv_idx]) - m1_l[uhv_idx]
            if body / rng < CFG["effortBodyMin"]: continue
            if uw / rng > CFG["effortWickMax"]: continue
            if lw / rng > CFG["effortWickMax"]: continue
        # Trigger: green for buy AND closed > UHV high; red for sell AND closed < UHV low
        isGreenT = m1_c[trig_idx] > m1_o[trig_idx]
        isRedT = m1_c[trig_idx] < m1_o[trig_idx]
        if dir_sign == 1 and isGreenT and m1_c[trig_idx] > m1_h[uhv_idx]: return True
        if dir_sign == -1 and isRedT and m1_c[trig_idx] < m1_l[uhv_idx]: return True
    return False

# === BIGNESS SIGNAL DETECTION (M5, body > 1.5x prev1) ===
def detect_signals():
    body = b_m5["body"].to_numpy()
    direction = b_m5["dir"].to_numpy()
    n = len(body)
    big_prev = np.zeros(n, dtype=bool)
    big_prev[2:] = body[1:-1] > CFG["BIG_RATIO"] * body[:-2]
    dir_prev = np.roll(direction, 1)
    sb = big_prev & (dir_prev == 1) & (direction == 1)
    ss = big_prev & (dir_prev == -1) & (direction == -1)
    sb[:2] = False; ss[:2] = False
    sigs = []
    for i in np.where(sb)[0]:
        sigs.append((int(b_m5.iloc[i]["ts_end_ms"]), 1, float(b_m5.iloc[i]["close"])))
    for i in np.where(ss)[0]:
        sigs.append((int(b_m5.iloc[i]["ts_end_ms"]), -1, float(b_m5.iloc[i]["close"])))
    sigs.sort()
    return sigs

# === BURST-DELTA FILTER (5s tick delta in dir direction) ===
def burst_delta_ok(sig_ts_ms, dir_sign):
    pi = find_idx(sig_ts_ms)
    if pi >= len(ts) or pi == 0: return False
    cur_price = (bids[pi] + asks[pi]) / 2
    back_ts = ts[pi] - CFG["burstDeltaLookbackSec"] * 1000
    bi = find_idx(back_ts)
    if bi >= pi: return False
    back_price = (bids[bi] + asks[bi]) / 2
    delta = (cur_price - back_price) * dir_sign
    return delta > 0  # any movement in dir direction

# === MAIN SIMULATION ===
print("[SIG] detecting signals...", flush=True)
sigs = detect_signals()
print(f"[SIG] {len(sigs)} raw bigness signals", flush=True)

# Filter chain stats
chain_stats = {"raw": len(sigs), "after_uhv": 0, "after_trend2m": 0, "after_m15trend": 0,
               "after_setup1": 0, "after_tickspeed": 0, "after_spread": 0, "after_burstdelta": 0,
               "after_chain_state": 0, "executed": 0}

trades = []
last_loss_count = 0          # consecutive losses in current chain
chain_idx = 0                # main count in current burst chain
last_main_close_ts = None    # for burst chain detection (close to close gap)
day_pnl = {}
open_positions = []          # (entry_ts, side) — simplified, no concurrent for now

BURST_GAP_SEC = 600  # if main closes within 10min of next signal, it's same burst

for sig_ts, side, trig_close in sigs:
    side_str = "buy" if side == 1 else "sell"
    if CFG["sellOnly"] and side == 1: continue
    date_key = datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")

    # Daily cap
    if day_pnl.get(date_key, 0) <= -CFG["dailyCap"]: continue

    # === FILTER STACK ===
    if CFG["uhvFilter"] and not uhv_breakout_ok(sig_ts, side, trig_close): continue
    chain_stats["after_uhv"] += 1
    if CFG["trendFilter"] and not trend_at(sig_ts, m2_ema34, m2_ema89, m2_ts, side): continue
    chain_stats["after_trend2m"] += 1
    if CFG["m15TrendFilter"] and not trend_at(sig_ts, m15_ema34, m15_ema89, m15_ts, side): continue
    chain_stats["after_m15trend"] += 1
    if CFG["setup1Filter"] and not setup1_active(sig_ts, side): continue
    chain_stats["after_setup1"] += 1

    # tick-speed check: last tick must be within 15s
    pi = find_idx(sig_ts)
    if pi >= len(ts): continue
    if pi > 0 and (ts[pi] - ts[pi-1]) / 1000.0 > CFG["tickSpeedMaxSec"]: continue
    chain_stats["after_tickspeed"] += 1

    # spread check
    cur_spread_pts = (asks[pi] - bids[pi]) * 100
    if cur_spread_pts > median_spread * CFG["spreadMaxMult"]: continue
    chain_stats["after_spread"] += 1

    if CFG["burstDeltaFilter"] and not burst_delta_ok(sig_ts, side): continue
    chain_stats["after_burstdelta"] += 1

    # Chain state: post-loss cooldown
    if last_loss_count >= CFG["chainStopAfterLoss"]:
        # This trade would start a NEW chain; check time gap
        if last_main_close_ts is not None and (sig_ts - last_main_close_ts) / 1000.0 < BURST_GAP_SEC:
            continue
        else:
            last_loss_count = 0; chain_idx = 0
    if chain_idx >= CFG["maxBurst"]:
        if last_main_close_ts is not None and (sig_ts - last_main_close_ts) / 1000.0 < BURST_GAP_SEC:
            continue
        else:
            chain_idx = 0
    chain_stats["after_chain_state"] += 1

    # === PROBE ===
    p_entry_ts = ts[pi]
    p_entry = asks[pi] if side == 1 else bids[pi]
    # No timeout — walk until probe confirm or fail
    max_horizon = 600 * 1000  # 10-min horizon to bound the loop
    end_idx_probe = find_idx(p_entry_ts + max_horizon)
    sub_bid = bids[pi:end_idx_probe]; sub_ask = asks[pi:end_idx_probe]; sub_ts = ts[pi:end_idx_probe]
    if side == 1:
        pnl_arr = (sub_bid - p_entry) * CONTRACT_SIZE * CFG["probeLots"]
    else:
        pnl_arr = (p_entry - sub_ask) * CONTRACT_SIZE * CFG["probeLots"]
    confirm_mask = pnl_arr >= CFG["probeConfirm"]
    fail_mask    = pnl_arr <= -CFG["probeFail"]
    c_idx = int(np.argmax(confirm_mask)) if confirm_mask.any() else -1
    f_idx = int(np.argmax(fail_mask))    if fail_mask.any() else -1
    # Probe trail (banks profit if it pulls back from peak by drop)
    if CFG["probeTrailEnabled"]:
        peak = -1e9; pt_idx = -1
        for k in range(len(pnl_arr)):
            if pnl_arr[k] > peak: peak = pnl_arr[k]
            if peak >= CFG["probeTrailTrigger"] and (peak - pnl_arr[k]) >= CFG["probeTrailDrop"]:
                pt_idx = k; break
            if confirm_mask[k] or fail_mask[k]: break
    else:
        pt_idx = -1

    # Determine probe outcome: confirm > probe-trail > fail
    candidates = [(c_idx, "confirm"), (pt_idx, "ptrail"), (f_idx, "fail")]
    candidates = [(i, lbl) for i, lbl in candidates if i >= 0]
    if not candidates: continue
    candidates.sort()
    exit_local, outcome = candidates[0]
    probe_pnl = float(pnl_arr[exit_local]) - COMMISSION * CFG["probeLots"]
    probe_exit_ts = int(sub_ts[exit_local])

    if outcome != "confirm":
        # Probe didn't confirm — log probe-only trade
        trades.append({
            "ts": datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).isoformat(),
            "date": date_key, "side": side_str, "outcome": outcome,
            "probe_pnl": round(probe_pnl, 2),
            "main_pnl": 0.0, "total_pnl": round(probe_pnl, 2),
            "chain_idx": chain_idx,
        })
        day_pnl[date_key] = day_pnl.get(date_key, 0) + probe_pnl
        if probe_pnl < 0:
            last_loss_count += 1
        last_main_close_ts = probe_exit_ts
        continue

    # === MAIN ===
    chain_stats["executed"] += 1
    chain_idx += 1
    is_burst = chain_idx > 1
    main_lots = CFG["overrideLots"]  # lot ladder is single-step, ignored
    mi = find_idx(probe_exit_ts)
    if mi >= len(ts): continue
    m_entry_ts = ts[mi]
    m_entry = asks[mi] if side == 1 else bids[mi]
    main_horizon = max(int(CFG["fearWashout"] * 1000), 600 * 1000)
    end_idx_main = find_idx(m_entry_ts + main_horizon)
    sub_bid_m = bids[mi:end_idx_main]; sub_ask_m = asks[mi:end_idx_main]; sub_ts_m = ts[mi:end_idx_main]
    if side == 1:
        m_pnl_arr = (sub_bid_m - m_entry) * CONTRACT_SIZE * main_lots
    else:
        m_pnl_arr = (m_entry - sub_ask_m) * CONTRACT_SIZE * main_lots

    # Walk tick by tick applying exit rules
    peak = 0.0; m_realized = None; m_exit_local = None; exit_reason = None
    for k in range(len(m_pnl_arr)):
        cur_pnl = m_pnl_arr[k]
        elapsed_s = (sub_ts_m[k] - m_entry_ts) / 1000.0
        if cur_pnl > peak: peak = cur_pnl
        # SL: burst-only tighter
        if is_burst and cur_pnl <= -CFG["burstSlUsd"]:
            m_realized = float(cur_pnl); m_exit_local = k; exit_reason = "burstSL"; break
        if cur_pnl <= -CFG["fearIdeal"]:
            m_realized = float(cur_pnl); m_exit_local = k; exit_reason = "fearIdeal"; break
        # Trail
        if peak >= CFG["trailTrigger"] and (peak - cur_pnl) >= CFG["trailDrop"]:
            m_realized = float(cur_pnl); m_exit_local = k; exit_reason = "trail"; break
        # mainNoGreen (close if peak < $3 by 60s)
        if CFG["mainNoGreenEnabled"] and elapsed_s >= CFG["mainNoGreenSec"] and peak < CFG["mainNoGreenPeakMin"]:
            m_realized = float(cur_pnl); m_exit_local = k; exit_reason = "mainNoGreen"; break
        # fearWashout: close after 180s if not yet at trail trigger
        if elapsed_s >= CFG["fearWashout"] and peak < CFG["trailTrigger"]:
            m_realized = float(cur_pnl); m_exit_local = k; exit_reason = "washout"; break

    if m_exit_local is None:
        m_realized = float(m_pnl_arr[-1])
        m_exit_local = len(m_pnl_arr) - 1
        exit_reason = "horizon"

    main_pnl = m_realized - COMMISSION * main_lots
    total = probe_pnl + main_pnl
    main_exit_ts = int(sub_ts_m[m_exit_local])

    trades.append({
        "ts": datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).isoformat(),
        "date": date_key, "side": side_str, "outcome": "main",
        "exit_reason": exit_reason,
        "probe_pnl": round(probe_pnl, 2),
        "main_pnl": round(main_pnl, 2),
        "total_pnl": round(total, 2),
        "chain_idx": chain_idx, "is_burst": is_burst,
        "main_dur_s": round((main_exit_ts - m_entry_ts) / 1000.0, 1),
    })
    day_pnl[date_key] = day_pnl.get(date_key, 0) + total
    if total < 0:
        last_loss_count += 1
    else:
        last_loss_count = 0
    last_main_close_ts = main_exit_ts

# === STATS ===
tdf = pd.DataFrame(trades)
if len(tdf):
    tdf.to_csv(OUT_C, index=False)
    arr = tdf["total_pnl"].to_numpy()
    main_only = tdf[tdf["outcome"] == "main"]
    wins = (arr > 0).sum(); losses = (arr < 0).sum()
    gw = arr[arr > 0].sum(); gl = -arr[arr < 0].sum()
    eq = arr.cumsum()
    dd = float((np.maximum.accumulate(eq) - eq).max())
    stats_all = {
        "n_total": int(len(tdf)),
        "n_main": int(len(main_only)),
        "wr_all": round(wins/len(tdf)*100, 2),
        "wr_main": round((main_only["total_pnl"]>0).sum()/max(1,len(main_only))*100, 2),
        "wins": int(wins), "losses": int(losses),
        "net_pnl": round(float(arr.sum()), 2),
        "avg_pnl": round(float(arr.mean()), 3),
        "pf": round(float(gw/gl), 2) if gl > 0 else None,
        "max_dd": round(dd, 2),
        "best": round(float(arr.max()), 2),
        "worst": round(float(arr.min()), 2),
    }
    by_day = tdf.groupby("date").agg(n=("total_pnl","count"), net=("total_pnl","sum"),
                                       wr=("total_pnl", lambda x: (x>0).sum()/len(x)*100)).round(2).to_dict("index")
    exit_reasons = tdf[tdf["outcome"]=="main"]["exit_reason"].value_counts().to_dict() if len(main_only) else {}
else:
    stats_all = {"n_total": 0}
    by_day = {}
    exit_reasons = {}

# === OUTPUT ===
print("\n=== SHANO-ZEE LIVE BACKTEST (3 days, real Blueberry ticks) ===", flush=True)
print(f"data window: {datetime.fromtimestamp(window_start_msc/1000, tz=timezone.utc).isoformat()} -> {datetime.fromtimestamp(last_msc/1000, tz=timezone.utc).isoformat()}", flush=True)
print(f"\n=== FILTER FUNNEL (signals surviving each gate) ===", flush=True)
for k, v in chain_stats.items():
    pct = round(v / max(1, chain_stats["raw"]) * 100, 1)
    print(f"  {k:>22}: {v:>5}  ({pct:>5.1f}%)", flush=True)
print(f"\n=== STATS ===", flush=True)
print(json.dumps(stats_all, indent=2, default=str), flush=True)
print(f"\n=== BY DAY ===", flush=True)
print(json.dumps(by_day, indent=2, default=str), flush=True)
print(f"\n=== MAIN EXIT REASONS ===", flush=True)
print(json.dumps(exit_reasons, indent=2, default=str), flush=True)

result = {
    "ran_at": datetime.now(timezone.utc).isoformat(),
    "window": {"start": datetime.fromtimestamp(window_start_msc/1000, tz=timezone.utc).isoformat(),
               "end":   datetime.fromtimestamp(last_msc/1000, tz=timezone.utc).isoformat()},
    "config": CFG, "median_spread_pts": median_spread,
    "filter_funnel": chain_stats,
    "stats": stats_all, "by_day": by_day, "exit_reasons": exit_reasons,
}
OUT_J.write_text(json.dumps(result, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
