"""Rerun Shano-Zee backtest on today (M1 signal detection) to match live MT5 trades."""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_shanozee_today_match.json")

CFG = {
    "probeConfirm": 0.75, "probeFail": 3.0, "probeLots": 0.01,
    "probeTrailEnabled": True, "probeTrailTrigger": 3.0, "probeTrailDrop": 1.0,
    "trailTrigger": 22.0, "trailDrop": 6.0,
    "fearIdeal": 60.0, "fearWashout": 180.0, "burstSlUsd": 15.0,
    "mainNoGreenEnabled": True, "mainNoGreenSec": 60, "mainNoGreenPeakMin": 3.0,
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
    "BIG_RATIO": 1.5,  # Pine inputs: iBodyMult=1.5, iLookback=1
    "SQUARE_BAR": 0.50,  # Pine: iSquareBar — body/range >= 0.50 for trigger candle
}
CONTRACT_SIZE = 100
COMMISSION = 7.0

print("[LOAD] reading parquet (today only)...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df["time_msc"].max())
last_dt = datetime.fromtimestamp(last_msc/1000, tz=timezone.utc)
today_start = datetime(last_dt.year, last_dt.month, last_dt.day, 0, 0, 0, tzinfo=timezone.utc)
# pull a 3-day window for filter context (need lookback for UHV/Setup1/M15 EMA)
context_start = today_start - timedelta(days=3)
mask = (df["time_msc"] >= int(context_start.timestamp() * 1000))
df = df[mask].reset_index(drop=True)
today_start_ms = int(today_start.timestamp() * 1000)
print(f"[LOAD] {len(df):,} ticks across context window {context_start.date()} -> {last_dt.date()}", flush=True)

ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)
def find_idx(t_ms): return int(np.searchsorted(ts, t_ms, side="right"))

def build_bars(tf_sec):
    bucket = (df["time_msc"] // (tf_sec * 1000)).astype(np.int64)
    g = df.assign(_b=bucket).groupby("_b", sort=True).agg(
        open=("bid","first"), high=("bid","max"), low=("bid","min"),
        close=("bid","last"), n_ticks=("bid","count"),
        ts_end_ms=("time_msc","last"),
    ).reset_index().drop(columns="_b")
    g["body"] = (g["close"] - g["open"]).abs()
    g["dir"]  = np.sign(g["close"] - g["open"]).astype(int)
    return g

print("[BARS] building M1/M2/M15...", flush=True)
b_m1  = build_bars(60)
b_m2  = build_bars(120)
b_m15 = build_bars(900)
print(f"  M1={len(b_m1)} M2={len(b_m2)} M15={len(b_m15)}", flush=True)

spread_pts_all = ((df["ask"] - df["bid"]) * 100).to_numpy()
median_spread = float(np.median(spread_pts_all))
print(f"  median spread: {median_spread:.1f} pts", flush=True)

def ema(values, period):
    alpha = 2 / (period + 1); out = np.zeros(len(values))
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i-1]
    return out

m2_close, m2_ts = b_m2["close"].to_numpy(), b_m2["ts_end_ms"].to_numpy()
m2_ema34, m2_ema89 = ema(m2_close, 34), ema(m2_close, 89)
m15_close, m15_ts = b_m15["close"].to_numpy(), b_m15["ts_end_ms"].to_numpy()
m15_ema34, m15_ema89 = ema(m15_close, 34), ema(m15_close, 89)

def trend_at(ts_ms, ef, es, bts, dir_sign):
    idx = int(np.searchsorted(bts, ts_ms, side="right")) - 1
    if idx < 89: return False
    f = ef[idx]; s = es[idx]; fp = ef[idx-1]
    return (f > s and f > fp) if dir_sign == 1 else (f < s and f < fp)

m1_o = b_m1["open"].to_numpy(); m1_h = b_m1["high"].to_numpy()
m1_l = b_m1["low"].to_numpy(); m1_c = b_m1["close"].to_numpy()
m1_v = b_m1["n_ticks"].to_numpy(); m1_ts_end = b_m1["ts_end_ms"].to_numpy()

def uhv_breakout_ok(sig_ts_ms, dir_sign, trigger_close):
    idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1
    if idx < CFG["uhvLookback"] + 1: return False
    lb = max(0, idx - CFG["uhvLookback"])
    look_v = m1_v[lb:idx]
    if len(look_v) == 0: return False
    uhv_g = lb + int(np.argmax(look_v))
    if dir_sign == 1:  return trigger_close > m1_h[uhv_g] + CFG["triggerPastUhvPts"]
    else:              return trigger_close < m1_l[uhv_g] - CFG["triggerPastUhvPts"]

def setup1_active(sig_ts_ms, dir_sign):
    idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1
    needed = CFG["setup1LookbackBars"] + CFG["setup1PatternLookback"] + 2
    if idx < needed: return False
    for trig_off in range(CFG["setup1LookbackBars"]):
        trig_idx = idx - trig_off
        s_start = max(0, trig_idx - CFG["setup1PatternLookback"]); s_end = trig_idx
        if s_end <= s_start: continue
        match_red = (dir_sign == 1)
        uhv_idx = -1; uhv_vol = -1
        for s in range(s_start, s_end):
            isRed = m1_c[s] < m1_o[s]; isGreen = m1_c[s] > m1_o[s]
            colored = isRed if match_red else isGreen
            if colored and m1_v[s] > uhv_vol:
                uhv_vol = m1_v[s]; uhv_idx = s
        if uhv_idx < 0: continue
        swept = False
        for s in range(uhv_idx + 1, trig_idx):
            if dir_sign == 1 and m1_l[s] < m1_l[uhv_idx]: swept = True; break
            if dir_sign == -1 and m1_h[s] > m1_h[uhv_idx]: swept = True; break
        if not swept: continue
        if CFG["setup1EffortResult"]:
            rng = m1_h[uhv_idx] - m1_l[uhv_idx]
            if rng <= 0: continue
            body = abs(m1_c[uhv_idx] - m1_o[uhv_idx])
            uw = m1_h[uhv_idx] - max(m1_o[uhv_idx], m1_c[uhv_idx])
            lw = min(m1_o[uhv_idx], m1_c[uhv_idx]) - m1_l[uhv_idx]
            if body / rng < CFG["effortBodyMin"]: continue
            if uw / rng > CFG["effortWickMax"]: continue
            if lw / rng > CFG["effortWickMax"]: continue
        isGreenT = m1_c[trig_idx] > m1_o[trig_idx]; isRedT = m1_c[trig_idx] < m1_o[trig_idx]
        if dir_sign == 1 and isGreenT and m1_c[trig_idx] > m1_h[uhv_idx]: return True
        if dir_sign == -1 and isRedT and m1_c[trig_idx] < m1_l[uhv_idx]: return True
    return False

# === M1 signal detection (matching live Pine on M1 chart) ===
body = b_m1["body"].to_numpy(); direction = b_m1["dir"].to_numpy()
m1_high = b_m1["high"].to_numpy(); m1_low = b_m1["low"].to_numpy()
m1_range = m1_high - m1_low
# iSquareBar gate: trigger candle (the BIG one, i.e. prev-bar) must have body/range >= 0.50
square_ok_prev = np.zeros(len(body), dtype=bool)
prev_body = np.roll(body, 1); prev_range = np.roll(m1_range, 1)
square_ok_prev[1:] = np.where(prev_range[1:] > 0, prev_body[1:] / prev_range[1:] >= CFG["SQUARE_BAR"], False)
n = len(body)
big_prev = np.zeros(n, dtype=bool)
big_prev[2:] = body[1:-1] > CFG["BIG_RATIO"] * body[:-2]
dir_prev = np.roll(direction, 1)
sig_buy  = big_prev & (dir_prev == 1)  & (direction == 1) & square_ok_prev
sig_sell = big_prev & (dir_prev == -1) & (direction == -1) & square_ok_prev
sig_buy[:2] = False; sig_sell[:2] = False
sigs = []
for i in np.where(sig_buy)[0]:
    sigs.append((int(b_m1.iloc[i]["ts_end_ms"]), 1, float(b_m1.iloc[i]["close"])))
for i in np.where(sig_sell)[0]:
    sigs.append((int(b_m1.iloc[i]["ts_end_ms"]), -1, float(b_m1.iloc[i]["close"])))
sigs.sort()
sigs_today = [s for s in sigs if s[0] >= today_start_ms]
print(f"[SIG] {len(sigs)} total signals (M1 detection), {len(sigs_today)} today", flush=True)

# Filter funnel for today
funnel = {"raw": 0, "uhv": 0, "trend2m": 0, "m15trend": 0, "setup1": 0,
          "tickspeed": 0, "spread": 0, "burstdelta": 0, "chain": 0, "executed_main": 0}
probe_attempts = []  # everything that survived to probe-entry stage
main_entries = []    # probes that confirmed and went to main
last_loss_count = 0; chain_idx = 0; last_main_close_ts = None; day_pnl = 0.0
BURST_GAP_SEC = 600

def burst_delta_ok(sig_ts_ms, dir_sign):
    pi = find_idx(sig_ts_ms)
    if pi >= len(ts) or pi == 0: return False
    cur = (bids[pi] + asks[pi]) / 2
    bi = find_idx(ts[pi] - CFG["burstDeltaLookbackSec"] * 1000)
    if bi >= pi: return False
    back = (bids[bi] + asks[bi]) / 2
    return (cur - back) * dir_sign > 0

for sig_ts, side, trig_close in sigs_today:
    funnel["raw"] += 1
    # Light-only filters at PROBE entry (matches Python sniper behavior)
    pi = find_idx(sig_ts)
    if pi >= len(ts): continue
    if pi > 0 and (ts[pi] - ts[pi-1]) / 1000.0 > CFG["tickSpeedMaxSec"]: continue
    funnel["tickspeed"] += 1
    if (asks[pi] - bids[pi]) * 100 > median_spread * CFG["spreadMaxMult"]: continue
    funnel["spread"] += 1
    # Note: UHV/trend/setup1/m15/burstdelta/chain ALL apply at MAIN entry, not probe

    # Probe simulation
    p_entry_ts = ts[pi]
    p_entry = asks[pi] if side == 1 else bids[pi]
    end_idx = find_idx(p_entry_ts + 600 * 1000)
    if side == 1:
        pnl_arr = (bids[pi:end_idx] - p_entry) * CONTRACT_SIZE * CFG["probeLots"]
    else:
        pnl_arr = (p_entry - asks[pi:end_idx]) * CONTRACT_SIZE * CFG["probeLots"]
    sub_ts = ts[pi:end_idx]
    confirm_mask = pnl_arr >= CFG["probeConfirm"]; fail_mask = pnl_arr <= -CFG["probeFail"]
    c_idx = int(np.argmax(confirm_mask)) if confirm_mask.any() else -1
    f_idx = int(np.argmax(fail_mask))    if fail_mask.any() else -1
    pt_idx = -1
    if CFG["probeTrailEnabled"]:
        peak = -1e9
        for k in range(len(pnl_arr)):
            if pnl_arr[k] > peak: peak = pnl_arr[k]
            if peak >= CFG["probeTrailTrigger"] and (peak - pnl_arr[k]) >= CFG["probeTrailDrop"]:
                pt_idx = k; break
            if confirm_mask[k] or fail_mask[k]: break
    cands = [(i, lbl) for i, lbl in [(c_idx,"confirm"),(pt_idx,"ptrail"),(f_idx,"fail")] if i >= 0]
    if not cands: continue
    cands.sort()
    exit_local, outcome = cands[0]
    probe_pnl = float(pnl_arr[exit_local]) - COMMISSION * CFG["probeLots"]
    probe_exit_ts = int(sub_ts[exit_local])
    probe_attempts.append({
        "ts": datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%H:%M:%S"),
        "side": "buy" if side == 1 else "sell",
        "outcome": outcome, "probe_pnl": round(probe_pnl, 2),
    })

    if outcome != "confirm":
        # NOTE: probe fails do NOT count toward chainStopAfterLoss — only main losses do
        last_main_close_ts = probe_exit_ts
        day_pnl += probe_pnl
        continue

    # === MAIN-ENTRY FILTERS (the heavy stack — only apply once probe confirms) ===
    if CFG["uhvFilter"] and not uhv_breakout_ok(sig_ts, side, trig_close):
        day_pnl += probe_pnl; last_main_close_ts = probe_exit_ts
        continue
    funnel["uhv"] += 1
    if CFG["trendFilter"] and not trend_at(sig_ts, m2_ema34, m2_ema89, m2_ts, side):
        day_pnl += probe_pnl; last_main_close_ts = probe_exit_ts
        continue
    funnel["trend2m"] += 1
    if CFG["m15TrendFilter"] and not trend_at(sig_ts, m15_ema34, m15_ema89, m15_ts, side):
        day_pnl += probe_pnl; last_main_close_ts = probe_exit_ts
        continue
    funnel["m15trend"] += 1
    if CFG["setup1Filter"] and not setup1_active(sig_ts, side):
        day_pnl += probe_pnl; last_main_close_ts = probe_exit_ts
        continue
    funnel["setup1"] += 1
    if CFG["burstDeltaFilter"] and not burst_delta_ok(sig_ts, side):
        day_pnl += probe_pnl; last_main_close_ts = probe_exit_ts
        continue
    funnel["burstdelta"] += 1
    # Chain-state gate at main entry
    if last_loss_count >= CFG["chainStopAfterLoss"]:
        if last_main_close_ts is not None and (sig_ts - last_main_close_ts) / 1000.0 < BURST_GAP_SEC:
            day_pnl += probe_pnl; continue
        else: last_loss_count = 0; chain_idx = 0
    if chain_idx >= CFG["maxBurst"]:
        if last_main_close_ts is not None and (sig_ts - last_main_close_ts) / 1000.0 < BURST_GAP_SEC:
            day_pnl += probe_pnl; continue
        else: chain_idx = 0
    funnel["chain"] += 1

    # Main
    funnel["executed_main"] += 1; chain_idx += 1
    is_burst = chain_idx > 1
    mi = find_idx(probe_exit_ts)
    if mi >= len(ts): continue
    m_entry_ts = ts[mi]; m_entry = asks[mi] if side == 1 else bids[mi]
    end_idx2 = find_idx(m_entry_ts + max(int(CFG["fearWashout"] * 1000), 600 * 1000))
    if side == 1:
        m_pnl_arr = (bids[mi:end_idx2] - m_entry) * CONTRACT_SIZE * CFG["overrideLots"]
    else:
        m_pnl_arr = (m_entry - asks[mi:end_idx2]) * CONTRACT_SIZE * CFG["overrideLots"]
    sub_ts2 = ts[mi:end_idx2]
    peak = 0.0; m_realized = None; m_exit_local = None; reason = None
    for k in range(len(m_pnl_arr)):
        cur = m_pnl_arr[k]; el_s = (sub_ts2[k] - m_entry_ts) / 1000.0
        if cur > peak: peak = cur
        if is_burst and cur <= -CFG["burstSlUsd"]:
            m_realized, m_exit_local, reason = float(cur), k, "burstSL"; break
        if cur <= -CFG["fearIdeal"]:
            m_realized, m_exit_local, reason = float(cur), k, "fearIdeal"; break
        if peak >= CFG["trailTrigger"] and (peak - cur) >= CFG["trailDrop"]:
            m_realized, m_exit_local, reason = float(cur), k, "trail"; break
        if CFG["mainNoGreenEnabled"] and el_s >= CFG["mainNoGreenSec"] and peak < CFG["mainNoGreenPeakMin"]:
            m_realized, m_exit_local, reason = float(cur), k, "mainNoGreen"; break
        if el_s >= CFG["fearWashout"] and peak < CFG["trailTrigger"]:
            m_realized, m_exit_local, reason = float(cur), k, "washout"; break
    if m_exit_local is None:
        m_realized = float(m_pnl_arr[-1]); m_exit_local = len(m_pnl_arr) - 1; reason = "horizon"
    main_pnl = m_realized - COMMISSION * CFG["overrideLots"]
    total = probe_pnl + main_pnl
    main_exit_ts = int(sub_ts2[m_exit_local])
    main_entries.append({
        "ts": datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%H:%M:%S"),
        "side": "buy" if side == 1 else "sell",
        "exit_reason": reason, "probe_pnl": round(probe_pnl, 2),
        "main_pnl": round(main_pnl, 2), "total": round(total, 2),
        "burst": is_burst, "chain_idx": chain_idx,
    })
    day_pnl += total
    if total < 0: last_loss_count += 1
    else: last_loss_count = 0
    last_main_close_ts = main_exit_ts

# === Output ===
print(f"\n=== TODAY ({today_start.date()}) BACKTEST vs LIVE ===", flush=True)
print(f"\n=== FILTER FUNNEL (today only, M1 signals) ===")
for k, v in funnel.items():
    pct = round(v / max(1, funnel["raw"]) * 100, 1)
    print(f"  {k:>16}: {v:>5}  ({pct:>5.1f}%)")
print(f"\n=== ALL PROBE ATTEMPTS ({len(probe_attempts)} total) ===")
for p in probe_attempts:
    print(f"  {p['ts']} | {p['side']:>4} | {p['outcome']:>8} | ${p['probe_pnl']:>+6.2f}")
print(f"\n=== MAIN ENTRIES ({len(main_entries)} total) ===")
for m in main_entries:
    print(f"  {m['ts']} | {m['side']:>4} | exit={m['exit_reason']:>10} | probe=${m['probe_pnl']:>+6.2f} | main=${m['main_pnl']:>+7.2f} | total=${m['total']:>+7.2f} | burst={m['burst']} chain#{m['chain_idx']}")
print(f"\nday_pnl = ${day_pnl:.2f}")

print(f"\n=== LIVE COMPARISON ===")
print(f"  Live probes opened:  107  (PineConnector v3.53.4-XXXX)")
print(f"  Backtest probes:     {len(probe_attempts)}")
print(f"  Live mains opened:    5  (Shano_Main_Burst1 ×4 + Shano_MG_Burst2 ×1)")
print(f"  Backtest mains:      {len(main_entries)}")

result = {
    "ran_at": datetime.now(timezone.utc).isoformat(),
    "today_utc": today_start.strftime("%Y-%m-%d"),
    "funnel": funnel, "probe_count": len(probe_attempts), "main_count": len(main_entries),
    "live_probes": 107, "live_mains": 5,
    "probe_attempts": probe_attempts, "main_entries": main_entries, "day_pnl": round(day_pnl, 2),
}
OUT_J.write_text(json.dumps(result, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}")
