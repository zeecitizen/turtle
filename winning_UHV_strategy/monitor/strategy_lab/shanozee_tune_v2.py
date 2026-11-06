"""Fine-tune Shano-Zee on the tick-replay backtester (5s polling delay model).

Strategy:
  1. Run on last 30 days only for sweep speed (~1.5 min per config)
  2. Greedy sweep one param at a time
  3. Validate winner on full 120 days at end
  4. Optimize for total P&L (mains + probes) since probes are the leakage

Output: monitor/strategy_lab/_shanozee_tune_v2.json
"""
import sys, importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

LAB = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab")
OUT_J = LAB / "_shanozee_tune_v2.json"

# We'll re-import shanozee_tick_replay logic by re-running the file with overrides.
# Simpler: write a runner that calls a parameterized version.
# Actually the cleanest path is to rewrite a function-based version. For now,
# let's use a CLI-overrideable version of the tick_replay script.

# Plan: copy core logic into a function backtest(cfg, tick_window_days) and sweep.

import pandas as pd
import numpy as np

CACHE = LAB / "_xauusd_ticks.parquet"
CONTRACT_SIZE = 100; COMMISSION = 7.0
PSIM_IDLE=0; PSIM_PROBE=1; PSIM_TRADE=2; PSIM_COOLDOWN=3; PSIM_SKIP=4
REAL_IDLE=0; REAL_PROBE=1; REAL_MAIN=2

print("[LOAD] reading parquet...", flush=True)
df_full = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df_full["time_msc"].max())

def slice_window(days_back):
    """Return ticks for the last N days."""
    cutoff = last_msc - days_back * 86400 * 1000
    return df_full[df_full["time_msc"] >= cutoff].reset_index(drop=True)

def build_bars(df, tf_sec):
    bucket = (df["time_msc"] // (tf_sec * 1000)).astype(np.int64)
    g = df.assign(_b=bucket).groupby("_b", sort=True).agg(
        open=("bid","first"), high=("bid","max"), low=("bid","min"),
        close=("bid","last"), n_ticks=("bid","count"),
        ts_end_ms=("time_msc","last"),
    ).reset_index().drop(columns="_b")
    g["body"] = (g["close"] - g["open"]).abs()
    g["range"] = g["high"] - g["low"]
    g["dir"]  = np.sign(g["close"] - g["open"]).astype(int)
    return g

def ema(values, period):
    alpha = 2/(period+1); out = np.zeros(len(values)); out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i-1]
    return out

def run_backtest(df, cfg, log=False):
    ts = df["time_msc"].to_numpy(dtype=np.int64)
    bids = df["bid"].to_numpy(dtype=np.float64)
    asks = df["ask"].to_numpy(dtype=np.float64)
    N = len(ts)

    b_m1 = build_bars(df, 60); b_m2 = build_bars(df, 120); b_m15 = build_bars(df, 900)
    m1_o = b_m1["open"].to_numpy(); m1_h = b_m1["high"].to_numpy()
    m1_l = b_m1["low"].to_numpy(); m1_c = b_m1["close"].to_numpy()
    m1_v = b_m1["n_ticks"].to_numpy(); m1_body = b_m1["body"].to_numpy()
    m1_range = b_m1["range"].to_numpy(); m1_dir = b_m1["dir"].to_numpy()
    m1_ts_end = b_m1["ts_end_ms"].to_numpy()
    m1_minute_id = (m1_ts_end // 60000).astype(np.int64)
    m1_idx_by_minute = {int(m): i for i, m in enumerate(m1_minute_id)}

    median_spread = float(np.median((df["ask"] - df["bid"]) * 100))
    m2_close = b_m2["close"].to_numpy(); m2_ts = b_m2["ts_end_ms"].to_numpy()
    m2_ema34 = ema(m2_close, 34); m2_ema89 = ema(m2_close, 89)
    m15_close = b_m15["close"].to_numpy(); m15_ts = b_m15["ts_end_ms"].to_numpy()
    m15_ema34 = ema(m15_close, 34); m15_ema89 = ema(m15_close, 89)

    def find_idx(t_ms): return int(np.searchsorted(ts, t_ms, side="right"))
    def trend_at(ts_ms, ef, es, bts, dir_sign):
        idx = int(np.searchsorted(bts, ts_ms, side="right")) - 1
        if idx < 89: return False
        f = ef[idx]; s = es[idx]; fp = ef[idx-1]
        return (f > s and f > fp) if dir_sign == 1 else (f < s and f < fp)
    def uhv_breakout_ok(sig_ts_ms, dir_sign, trigger_close):
        idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1
        if idx < cfg["uhvLookback"] + 1: return False
        lb = max(0, idx - cfg["uhvLookback"])
        look_v = m1_v[lb:idx]
        if len(look_v) == 0: return False
        uhv_g = lb + int(np.argmax(look_v))
        if dir_sign == 1: return trigger_close > m1_h[uhv_g] + cfg["triggerPastUhvPts"]
        else: return trigger_close < m1_l[uhv_g] - cfg["triggerPastUhvPts"]
    def setup1_active(sig_ts_ms, dir_sign):
        idx = int(np.searchsorted(m1_ts_end, sig_ts_ms, side="right")) - 1
        needed = cfg["setup1LookbackBars"] + cfg["setup1PatternLookback"] + 2
        if idx < needed: return False
        for trig_off in range(cfg["setup1LookbackBars"]):
            trig_idx = idx - trig_off
            s_start = max(0, trig_idx - cfg["setup1PatternLookback"]); s_end = trig_idx
            if s_end <= s_start: continue
            match_red = (dir_sign == 1)
            uhv_idx = -1; uhv_vol = -1
            for s in range(s_start, s_end):
                colored = (m1_c[s] < m1_o[s]) if match_red else (m1_c[s] > m1_o[s])
                if colored and m1_v[s] > uhv_vol: uhv_vol = m1_v[s]; uhv_idx = s
            if uhv_idx < 0: continue
            swept = False
            for s in range(uhv_idx + 1, trig_idx):
                if dir_sign == 1 and m1_l[s] < m1_l[uhv_idx]: swept = True; break
                if dir_sign == -1 and m1_h[s] > m1_h[uhv_idx]: swept = True; break
            if not swept: continue
            if cfg["setup1EffortResult"]:
                rng = m1_h[uhv_idx] - m1_l[uhv_idx]
                if rng <= 0: continue
                body_v = abs(m1_c[uhv_idx] - m1_o[uhv_idx])
                uw = m1_h[uhv_idx] - max(m1_o[uhv_idx], m1_c[uhv_idx])
                lw = min(m1_o[uhv_idx], m1_c[uhv_idx]) - m1_l[uhv_idx]
                if body_v / rng < cfg["effortBodyMin"]: continue
                if uw / rng > cfg["effortWickMax"]: continue
                if lw / rng > cfg["effortWickMax"]: continue
            if dir_sign == 1 and m1_c[trig_idx] > m1_o[trig_idx] and m1_c[trig_idx] > m1_h[uhv_idx]: return True
            if dir_sign == -1 and m1_c[trig_idx] < m1_o[trig_idx] and m1_c[trig_idx] < m1_l[uhv_idx]: return True
        return False
    def burst_delta_ok(tick_i, dir_sign):
        if tick_i == 0: return False
        cur = (bids[tick_i] + asks[tick_i]) / 2
        bi = int(np.searchsorted(ts, ts[tick_i] - cfg["burstDeltaLookbackSec"] * 1000, side="right"))
        if bi >= tick_i: return False
        back = (bids[bi] + asks[bi]) / 2
        return (cur - back) * dir_sign > 0

    psim_state = PSIM_IDLE; psim_dir = 0; psim_probe_entry = None
    psim_probe_open_minute = None; psim_trade_entry = None; psim_cooldown_start_minute = None
    real_state = REAL_IDLE
    real_probe_open_ts = None; real_probe_dir = 0; real_probe_entry = None; real_probe_peak = -1e9
    real_main_open_ts = None; real_main_dir = 0; real_main_entry = None; real_main_peak = 0.0
    real_main_is_burst = False
    pending_probe = None
    probes = []; mains = []
    chain_idx = 0; last_loss_count = 0; last_main_close_ts = None
    day_pnl = {}
    cur_minute = None; run_open = None; run_high = -1e9; run_low = 1e9
    prev_bar_body = 0.0; prev_bar_range = 0.0; prev_bar_dir = 0; prev_prev_bar_body = 0.0
    last_fired_minute = -1; big_green_minute = -1; red_count_since = 0
    BURST_GAP_SEC = 600

    for tick_i in range(N):
        t_ms = ts[tick_i]; bid = bids[tick_i]; ask = asks[tick_i]
        minute_id = t_ms // 60000
        if cur_minute is None:
            cur_minute = minute_id
            run_open = bid; run_high = bid; run_low = bid
        elif minute_id != cur_minute:
            prev_idx = m1_idx_by_minute.get(int(cur_minute))
            if prev_idx is not None:
                prev_prev_bar_body = prev_bar_body
                prev_bar_body = float(m1_body[prev_idx]); prev_bar_range = float(m1_range[prev_idx])
                prev_bar_dir = int(m1_dir[prev_idx])
                is_big = (prev_prev_bar_body > 0 and prev_bar_body > cfg["BIG_RATIO"] * prev_prev_bar_body
                          and prev_bar_range > 0 and (prev_bar_body / prev_bar_range) >= cfg["SQUARE_BAR"])
                if is_big and prev_bar_dir == 1:
                    big_green_minute = int(cur_minute); red_count_since = 0
                elif prev_bar_dir == -1 and big_green_minute >= 0: red_count_since += 1
                if psim_state == PSIM_SKIP and is_big: psim_state = PSIM_IDLE
                if psim_state == PSIM_PROBE and psim_probe_open_minute is not None:
                    if (int(cur_minute) - int(psim_probe_open_minute)) >= cfg["PINE_SIM_PROBE_MAX_B"]:
                        psim_state = PSIM_IDLE
                if psim_state == PSIM_COOLDOWN and psim_cooldown_start_minute is not None:
                    if (int(cur_minute) - int(psim_cooldown_start_minute)) >= cfg["PINE_SIM_POST_LOSS_CD"]:
                        psim_state = PSIM_IDLE
            cur_minute = minute_id
            run_open = bid; run_high = bid; run_low = bid
        if bid > run_high: run_high = bid
        if bid < run_low: run_low = bid
        run_close = bid; run_body = abs(run_close - run_open)
        run_dir = 1 if run_close > run_open else -1 if run_close < run_open else 0

        # Pine sim
        if psim_state == PSIM_IDLE:
            cooldown_ok = (last_fired_minute < 0) or ((minute_id - last_fired_minute) >= cfg["iCooldown"])
            if cooldown_ok and prev_bar_body > 0 and prev_prev_bar_body > 0:
                if prev_bar_body > cfg["BIG_RATIO"] * prev_prev_bar_body:
                    if prev_bar_range > 0 and (prev_bar_body / prev_bar_range) >= cfg["SQUARE_BAR"]:
                        if prev_bar_dir != 0 and run_dir == prev_bar_dir:
                            pullback_ok = True
                            if run_dir == -1:
                                pullback_ok = (red_count_since >= cfg["iPullbackN"]) or (big_green_minute < 0)
                            if pullback_ok:
                                last_fired_minute = minute_id
                                psim_state = PSIM_PROBE; psim_dir = run_dir
                                psim_probe_entry = run_close; psim_probe_open_minute = minute_id
                                if real_state == REAL_IDLE and pending_probe is None:
                                    pending_probe = (t_ms + cfg["SNIPER_AVG_LATENCY_MS"], run_dir, t_ms)
        elif psim_state == PSIM_PROBE:
            if psim_dir == 1: sim_pnl = (run_close - psim_probe_entry) * CONTRACT_SIZE * cfg["probeLots"]
            else: sim_pnl = (psim_probe_entry - run_close) * CONTRACT_SIZE * cfg["probeLots"]
            if sim_pnl >= cfg["PINE_SIM_PROBE_CONF"]:
                psim_state = PSIM_TRADE; psim_trade_entry = run_close
            elif sim_pnl <= -cfg["PINE_SIM_PROBE_FAIL"]:
                psim_state = PSIM_SKIP
        elif psim_state == PSIM_TRADE:
            if psim_dir == 1: sim_t = (run_close - psim_trade_entry) * CONTRACT_SIZE * cfg["PINE_SIM_REAL_LOTS"]
            else: sim_t = (psim_trade_entry - run_close) * CONTRACT_SIZE * cfg["PINE_SIM_REAL_LOTS"]
            if sim_t >= cfg["PINE_SIM_TRADE_TP"]: psim_state = PSIM_IDLE
            elif sim_t <= -cfg["PINE_SIM_TRADE_SL"]:
                psim_state = PSIM_COOLDOWN; psim_cooldown_start_minute = minute_id

        # Pending real probe
        if pending_probe is not None and real_state == REAL_IDLE:
            fire_at, p_dir, sig_ts = pending_probe
            if t_ms >= fire_at:
                fire_real = True
                if tick_i > 0 and (ts[tick_i] - ts[tick_i-1]) / 1000.0 > cfg["tickSpeedMaxSec"]:
                    fire_real = False
                elif (ask - bid) * 100 > median_spread * cfg["spreadMaxMult"]:
                    fire_real = False
                else:
                    date_key = datetime.fromtimestamp(t_ms/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    if day_pnl.get(date_key, 0) <= -cfg["dailyCap"]:
                        fire_real = False
                if fire_real:
                    real_state = REAL_PROBE; real_probe_dir = p_dir
                    real_probe_entry = ask if p_dir == 1 else bid
                    real_probe_open_ts = t_ms; real_probe_peak = -1e9
                pending_probe = None

        # Real probe
        if real_state == REAL_PROBE:
            if real_probe_dir == 1: cur_pnl = (bid - real_probe_entry) * CONTRACT_SIZE * cfg["probeLots"]
            else: cur_pnl = (real_probe_entry - ask) * CONTRACT_SIZE * cfg["probeLots"]
            if cur_pnl > real_probe_peak: real_probe_peak = cur_pnl
            outcome = None
            if cur_pnl >= cfg["probeConfirm"]: outcome = "confirm"
            elif cur_pnl <= -cfg["probeFail"]: outcome = "fail"
            elif (cfg["probeTrailEnabled"] and real_probe_peak >= cfg["probeTrailTrigger"]
                  and (real_probe_peak - cur_pnl) >= cfg["probeTrailDrop"]):
                outcome = "ptrail"
            if outcome is not None:
                probe_pnl = float(cur_pnl) - COMMISSION * cfg["probeLots"]
                probes.append({"open_ts": real_probe_open_ts, "exit_ts": t_ms, "side": real_probe_dir,
                               "outcome": outcome, "pnl": probe_pnl})
                date_key = datetime.fromtimestamp(real_probe_open_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                day_pnl[date_key] = day_pnl.get(date_key, 0) + probe_pnl
                if outcome == "confirm":
                    sig_ts = real_probe_open_ts; prob_dir = real_probe_dir
                    if last_main_close_ts is not None and (sig_ts - last_main_close_ts) / 1000.0 >= BURST_GAP_SEC:
                        last_loss_count = 0; chain_idx = 0
                    pi_minute = real_probe_open_ts // 60000
                    prev_pi = m1_idx_by_minute.get(int(pi_minute) - 1)
                    trig_close_for_uhv = float(m1_c[prev_pi]) if prev_pi is not None else float(run_close)
                    ok = True
                    if cfg["uhvFilter"] and not uhv_breakout_ok(sig_ts, prob_dir, trig_close_for_uhv): ok = False
                    if ok and cfg["trendFilter"] and not trend_at(sig_ts, m2_ema34, m2_ema89, m2_ts, prob_dir): ok = False
                    if ok and cfg["m15TrendFilter"] and not trend_at(sig_ts, m15_ema34, m15_ema89, m15_ts, prob_dir): ok = False
                    if ok and cfg["setup1Filter"] and not setup1_active(sig_ts, prob_dir): ok = False
                    if ok and cfg["burstDeltaFilter"] and not burst_delta_ok(tick_i, prob_dir): ok = False
                    if ok and last_loss_count >= cfg["chainStopAfterLoss"]: ok = False
                    if ok and chain_idx >= cfg["maxBurst"]: ok = False
                    if ok:
                        chain_idx += 1; real_main_is_burst = chain_idx > 1
                        real_main_dir = prob_dir; real_main_entry = ask if real_main_dir == 1 else bid
                        real_main_open_ts = t_ms; real_main_peak = 0.0
                        real_state = REAL_MAIN
                    else: real_state = REAL_IDLE
                else: real_state = REAL_IDLE
        elif real_state == REAL_MAIN:
            if real_main_dir == 1: cur_pnl = (bid - real_main_entry) * CONTRACT_SIZE * cfg["overrideLots"]
            else: cur_pnl = (real_main_entry - ask) * CONTRACT_SIZE * cfg["overrideLots"]
            if cur_pnl > real_main_peak: real_main_peak = cur_pnl
            elapsed_s = (t_ms - real_main_open_ts) / 1000.0
            exit_reason = None
            if real_main_is_burst and cur_pnl <= -cfg["burstSlUsd"]: exit_reason = "burstSL"
            elif cur_pnl <= -cfg["fearIdeal"]: exit_reason = "fearIdeal"
            elif real_main_peak >= cfg["trailTrigger"] and (real_main_peak - cur_pnl) >= cfg["trailDrop"]:
                exit_reason = "trail"
            elif (cfg["mainNoGreenEnabled"] and elapsed_s >= cfg["mainNoGreenSec"]
                  and real_main_peak < cfg["mainNoGreenPeakMin"]):
                exit_reason = "mainNoGreen"
            elif elapsed_s >= cfg["fearWashout"] and real_main_peak < cfg["trailTrigger"]:
                exit_reason = "washout"
            if exit_reason is not None:
                main_pnl = float(cur_pnl) - COMMISSION * cfg["overrideLots"]
                mains.append({"open_ts": real_main_open_ts, "exit_ts": t_ms, "side": real_main_dir,
                              "exit_reason": exit_reason, "pnl": main_pnl,
                              "is_burst": real_main_is_burst, "chain_idx": chain_idx})
                date_key = datetime.fromtimestamp(real_main_open_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                day_pnl[date_key] = day_pnl.get(date_key, 0) + main_pnl
                if main_pnl < 0: last_loss_count += 1
                else: last_loss_count = 0
                last_main_close_ts = t_ms
                real_state = REAL_IDLE

    return probes, mains

def stats(probes, mains):
    p_arr = np.array([p["pnl"] for p in probes]) if probes else np.array([])
    m_arr = np.array([m["pnl"] for m in mains]) if mains else np.array([])
    main_wins = int((m_arr > 0).sum()) if len(m_arr) else 0
    main_losses = int((m_arr < 0).sum()) if len(m_arr) else 0
    main_gw = float(m_arr[m_arr > 0].sum()) if len(m_arr) and (m_arr > 0).any() else 0
    main_gl = float(-m_arr[m_arr < 0].sum()) if len(m_arr) and (m_arr < 0).any() else 0
    return {
        "n_probes": len(probes), "n_mains": len(mains),
        "probe_net": round(float(p_arr.sum()), 2) if len(p_arr) else 0,
        "main_net": round(float(m_arr.sum()), 2) if len(m_arr) else 0,
        "total_net": round(float(p_arr.sum() + m_arr.sum()), 2),
        "main_wr": round(main_wins / max(1, len(m_arr)) * 100, 2),
        "main_pf": round(main_gw / main_gl, 2) if main_gl > 0 else None,
        "main_avg": round(float(m_arr.mean()), 2) if len(m_arr) else 0,
    }

# === BASELINE CONFIG ===
BASE = {
    "BIG_RATIO": 1.5, "SQUARE_BAR": 0.50,
    "probeConfirm": 0.75, "probeFail": 3.0, "probeLots": 0.01,
    "probeTrailEnabled": True, "probeTrailTrigger": 3.0, "probeTrailDrop": 1.0,
    "trailTrigger": 22.0, "trailDrop": 6.0,
    "fearIdeal": 60.0, "fearWashout": 180.0, "burstSlUsd": 15.0,
    "mainNoGreenEnabled": True, "mainNoGreenSec": 60, "mainNoGreenPeakMin": 3.0,
    "overrideLots": 0.30,
    "tickSpeedMaxSec": 15, "spreadMaxMult": 1.2,
    "uhvFilter": True, "uhvLookback": 20, "triggerPastUhvPts": 0.3,
    "trendFilter": True, "m15TrendFilter": True,
    "setup1Filter": True, "setup1LookbackBars": 3, "setup1PatternLookback": 10,
    "setup1EffortResult": True, "effortBodyMin": 0.50, "effortWickMax": 0.40,
    "burstDeltaFilter": True, "burstDeltaLookbackSec": 5,
    "chainStopAfterLoss": 2, "maxBurst": 7, "dailyCap": 500.0,
    "iCooldown": 1, "iPullbackN": 2,
    "PINE_SIM_PROBE_CONF": 0.58, "PINE_SIM_PROBE_FAIL": 3.0, "PINE_SIM_PROBE_MAX_B": 2,
    "PINE_SIM_TRADE_TP": 10.0, "PINE_SIM_TRADE_SL": 30.0, "PINE_SIM_POST_LOSS_CD": 3,
    "PINE_SIM_REAL_LOTS": 0.40, "SNIPER_POLL_INTERVAL_SEC": 5, "SNIPER_AVG_LATENCY_MS": 2500,
}

# === Train/Test split: 90 days train, last 30 days test ===
df_train = slice_window(120)  # full 120 days for "train"
# Identify the cutoff for last 30 days
cutoff_30d = last_msc - 30 * 86400 * 1000
df_train_only = df_train[df_train["time_msc"] < cutoff_30d].reset_index(drop=True)
df_test_only  = df_train[df_train["time_msc"] >= cutoff_30d].reset_index(drop=True)
print(f"[SPLIT] train={len(df_train_only):,} ticks ({(df_train_only['time_msc'].max() - df_train_only['time_msc'].min())/86400000:.0f}d)", flush=True)
print(f"[SPLIT] test={len(df_test_only):,} ticks ({(df_test_only['time_msc'].max() - df_test_only['time_msc'].min())/86400000:.0f}d)", flush=True)

# Greedy sweep on train, validate on test
TUNE_PLAN = [
    ("probeConfirm",     [0.50, 0.75, 1.00, 1.50, 2.00]),
    ("probeFail",        [1.5, 2.0, 2.5, 3.0, 4.0]),
    ("probeTrailTrigger", [2.0, 3.0, 4.0]),
    ("trailTrigger",     [15, 20, 25, 30]),
    ("trailDrop",        [3, 4, 6, 8]),
    ("fearIdeal",        [40, 50, 60, 80]),
    ("mainNoGreenSec",   [30, 60, 90, 120]),
    ("mainNoGreenPeakMin", [2.0, 3.0, 5.0]),
]

best_cfg = dict(BASE)
print(f"\n[BASELINE] running on train ({len(df_train_only):,} ticks)...", flush=True)
import time
t0 = time.time()
b_probes, b_mains = run_backtest(df_train_only, best_cfg)
b_stats = stats(b_probes, b_mains)
print(f"  baseline train: {b_stats}  (took {time.time()-t0:.0f}s)", flush=True)

results = {"started": datetime.now(timezone.utc).isoformat(), "baseline_train": b_stats, "tunes": []}
current_train = b_stats

for label, sweep_vals in TUNE_PLAN:
    print(f"\n=== TUNING {label} (current: {best_cfg[label]}) ===", flush=True)
    print(f"  {'value':>8} | {'probes':>6} {'mains':>5} {'main_wr':>7} {'main_pf':>7} {'probe_net':>9} {'main_net':>9} {'total':>9}", flush=True)
    rows = []
    for v in sweep_vals:
        cfg_v = dict(best_cfg); cfg_v[label] = v
        probes_v, mains_v = run_backtest(df_train_only, cfg_v)
        s = stats(probes_v, mains_v)
        s["value"] = v
        rows.append(s)
        print(f"  {str(v):>8} | {s['n_probes']:>6} {s['n_mains']:>5} {s['main_wr']:>7.2f} {str(s['main_pf']):>7} {s['probe_net']:>9.2f} {s['main_net']:>9.2f} {s['total_net']:>9.2f}", flush=True)
    # Pick winner by total_net
    rows.sort(key=lambda r: r["total_net"], reverse=True)
    winner = rows[0]
    if winner["total_net"] > current_train["total_net"]:
        best_cfg[label] = winner["value"]
        current_train = winner
        print(f"  -> WINNER: {label}={winner['value']} (total improved from ${current_train.get('total_net_old', b_stats['total_net'])} -> ${winner['total_net']})", flush=True)
    else:
        print(f"  -> no improvement, keeping {best_cfg[label]}", flush=True)
    results["tunes"].append({"param": label, "rows": rows, "winner_value": best_cfg[label]})

# Validate on test set
print(f"\n=== VALIDATING tuned config on TEST set (last 30 days) ===", flush=True)
t_probes, t_mains = run_backtest(df_test_only, best_cfg)
t_stats = stats(t_probes, t_mains)
print(json.dumps(t_stats, indent=2), flush=True)

print(f"\n=== BASELINE TEST (for comparison) ===", flush=True)
b_probes_test, b_mains_test = run_backtest(df_test_only, BASE)
b_test_stats = stats(b_probes_test, b_mains_test)
print(json.dumps(b_test_stats, indent=2), flush=True)

results["final_train"] = current_train
results["final_test"] = t_stats
results["baseline_test"] = b_test_stats
results["best_config"] = best_cfg
results["delta_test"] = {
    "total_net": round(t_stats["total_net"] - b_test_stats["total_net"], 2),
    "main_wr": round(t_stats["main_wr"] - b_test_stats["main_wr"], 2),
}

OUT_J.write_text(json.dumps(results, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
print(f"\nDELTA on test (tuned vs baseline): total_net ${results['delta_test']['total_net']:+.2f}, WR {results['delta_test']['main_wr']:+.2f}%", flush=True)
