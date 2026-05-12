"""Tick-by-tick mid-bar Shano-Zee backtest — matches live Pine iMidBar=true behavior.

Walks every tick chronologically:
  1. Maintains running M1 bar (open / running_close / running_high / running_low)
  2. When sim_state == IDLE and running bar qualifies (bigness + same-dir + iSquareBar),
     fires probe at that exact tick (replicates Pine signal counter incrementing)
  3. Tracks probe → confirm/fail tick-by-tick
  4. On probe confirm: applies main-entry filter stack (UHV, M2 trend, M15 trend, Setup 1,
     burst-delta), opens main if all pass
  5. Tracks main → exit (trail/fearIdeal/burstSL/mainNoGreen/fearWashout)

Validation target: today's live MT5 trades (107 probes, 5 mains).
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_shanozee_tick_replay.json")

CFG = {
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
    "chainStopAfterLoss": 2,
    "maxBurst": 7, "dailyCap": 500.0,
    "iCooldown": 1,  # Pine: 1-bar (1-min) cooldown between signal fires
    "iPullbackN": 2, # Pine: SELLs require N+ red bars since last big green
    # Pine sim's own thresholds (NOT the same as real probe/main thresholds)
    "PINE_SIM_PROBE_CONF": 0.58, "PINE_SIM_PROBE_FAIL": 3.0, "PINE_SIM_PROBE_MAX_B": 2,
    "PINE_SIM_TRADE_TP": 10.0, "PINE_SIM_TRADE_SL": 30.0, "PINE_SIM_POST_LOSS_CD": 3,
    "PINE_SIM_REAL_LOTS": 0.40,  # Pine's iRealLots used in sim trade
    "SNIPER_POLL_INTERVAL_SEC": 5,  # Python sniper polls Pine signal counter every 5s
    "SNIPER_AVG_LATENCY_MS": 2500, # Avg latency from signal fire to real probe open (poll midpoint)
}
CONTRACT_SIZE = 100; COMMISSION = 7.0
BURST_GAP_SEC = 600  # gap between mains that resets chain
# Pine sim states (controls signal counter)
PSIM_IDLE = 0; PSIM_PROBE = 1; PSIM_TRADE = 2; PSIM_COOLDOWN = 3; PSIM_SKIP = 4
# Real trade states (controls actual P&L)
REAL_IDLE = 0; REAL_PROBE = 1; REAL_MAIN = 2

# === LOAD ===
print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
last_msc = int(df["time_msc"].max())
last_dt = datetime.fromtimestamp(last_msc/1000, tz=timezone.utc)
today_start = datetime(last_dt.year, last_dt.month, last_dt.day, 0, 0, 0, tzinfo=timezone.utc)
context_start = datetime.fromtimestamp(int(df["time_msc"].min())/1000, tz=timezone.utc)
# Use full parquet (120 days) for multi-day eval — no slicing
ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)
N = len(ts)
print(f"[LOAD] {N:,} ticks across {context_start.date()} -> {last_dt.date()}", flush=True)

# Pre-compute closed M1 bars for filter lookups (UHV, Setup 1, trend, M15)
def build_bars(tf_sec):
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

print("[BARS] precomputing M1/M2/M15...", flush=True)
b_m1 = build_bars(60); b_m2 = build_bars(120); b_m15 = build_bars(900)
m1_o = b_m1["open"].to_numpy(); m1_h = b_m1["high"].to_numpy()
m1_l = b_m1["low"].to_numpy(); m1_c = b_m1["close"].to_numpy()
m1_v = b_m1["n_ticks"].to_numpy(); m1_body = b_m1["body"].to_numpy()
m1_range = b_m1["range"].to_numpy(); m1_dir = b_m1["dir"].to_numpy()
m1_ts_end = b_m1["ts_end_ms"].to_numpy()
m1_minute_id = (m1_ts_end // 60000).astype(np.int64)

# Map each minute_id to its closed-bar index
m1_idx_by_minute = {int(m): i for i, m in enumerate(m1_minute_id)}

median_spread = float(np.median((df["ask"] - df["bid"]) * 100))
print(f"  M1={len(b_m1)} M2={len(b_m2)} M15={len(b_m15)} | median spread={median_spread:.1f}pts", flush=True)

def ema(values, period):
    alpha = 2/(period+1); out = np.zeros(len(values)); out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i-1]
    return out

m2_close = b_m2["close"].to_numpy(); m2_ts = b_m2["ts_end_ms"].to_numpy()
m2_ema34 = ema(m2_close, 34); m2_ema89 = ema(m2_close, 89)
m15_close = b_m15["close"].to_numpy(); m15_ts = b_m15["ts_end_ms"].to_numpy()
m15_ema34 = ema(m15_close, 34); m15_ema89 = ema(m15_close, 89)

def trend_at(ts_ms, ef, es, bts, dir_sign):
    idx = int(np.searchsorted(bts, ts_ms, side="right")) - 1
    if idx < 89: return False
    f = ef[idx]; s = es[idx]; fp = ef[idx-1]
    return (f > s and f > fp) if dir_sign == 1 else (f < s and f < fp)

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
            colored = (m1_c[s] < m1_o[s]) if match_red else (m1_c[s] > m1_o[s])
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
            body_v = abs(m1_c[uhv_idx] - m1_o[uhv_idx])
            uw = m1_h[uhv_idx] - max(m1_o[uhv_idx], m1_c[uhv_idx])
            lw = min(m1_o[uhv_idx], m1_c[uhv_idx]) - m1_l[uhv_idx]
            if body_v / rng < CFG["effortBodyMin"]: continue
            if uw / rng > CFG["effortWickMax"]: continue
            if lw / rng > CFG["effortWickMax"]: continue
        if dir_sign == 1 and m1_c[trig_idx] > m1_o[trig_idx] and m1_c[trig_idx] > m1_h[uhv_idx]: return True
        if dir_sign == -1 and m1_c[trig_idx] < m1_o[trig_idx] and m1_c[trig_idx] < m1_l[uhv_idx]: return True
    return False

def burst_delta_ok(tick_i, dir_sign):
    if tick_i == 0: return False
    cur = (bids[tick_i] + asks[tick_i]) / 2
    back_ts = ts[tick_i] - CFG["burstDeltaLookbackSec"] * 1000
    bi = int(np.searchsorted(ts, back_ts, side="right"))
    if bi >= tick_i: return False
    back = (bids[bi] + asks[bi]) / 2
    return (cur - back) * dir_sign > 0

# === TICK-BY-TICK STATE MACHINE ===
print("[REPLAY] walking ticks tick-by-tick...", flush=True)

# Pine sim state (gates signal counter)
psim_state = PSIM_IDLE
psim_dir = 0
psim_probe_entry = None
psim_probe_open_minute = None
psim_trade_entry = None
psim_cooldown_start_minute = None

# Real trade state (independent of Pine sim)
real_state = REAL_IDLE
real_probe_open_ts = None; real_probe_dir = 0; real_probe_entry = None; real_probe_peak = -1e9
real_main_open_ts = None; real_main_dir = 0; real_main_entry = None; real_main_peak = 0.0
real_main_is_burst = False

# Pending probe fire (Python sniper polling delay): (fire_at_ts_ms, dir, signal_ts)
pending_probe = None

probes = []; mains = []
chain_idx = 0; last_loss_count = 0; last_main_close_ts = None
day_pnl = {}

# Running M1 bar state
cur_minute = None
run_open = None; run_high = -1e9; run_low = 1e9
prev_bar_body = 0.0; prev_bar_range = 0.0; prev_bar_dir = 0  # bar that just closed
prev_prev_bar_body = 0.0  # bar before that

# Track most recent fired-signal minute to avoid double-firing within same minute
last_fired_minute = -1
# Pullback tracker (Pine: bigGreenBar + redCountSince)
big_green_minute = -1  # last minute where isBull (big bull) fired
red_count_since = 0    # red bars since last big_green_minute

probe_attempts_today = []
mains_today = []
filter_funnel = {"raw_signals": 0, "tickspeed": 0, "spread": 0, "executed_probe": 0,
                 "probe_confirmed": 0, "uhv_pass": 0, "trend2m_pass": 0, "m15_pass": 0,
                 "setup1_pass": 0, "burstdelta_pass": 0, "chain_pass": 0, "executed_main": 0}

# Iterate ticks
for tick_i in range(N):
    t_ms = ts[tick_i]
    bid = bids[tick_i]; ask = asks[tick_i]
    minute_id = t_ms // 60000

    # Bar boundary: previous bar just closed
    if cur_minute is None:
        cur_minute = minute_id
        run_open = bid; run_high = bid; run_low = bid
    elif minute_id != cur_minute:
        # New bar started; previous one is now "closed"
        prev_idx = m1_idx_by_minute.get(int(cur_minute))
        if prev_idx is not None:
            prev_prev_bar_body = prev_bar_body
            prev_bar_body = float(m1_body[prev_idx])
            prev_bar_range = float(m1_range[prev_idx])
            prev_bar_dir   = int(m1_dir[prev_idx])
            # Update pullback tracker
            is_big = (prev_prev_bar_body > 0 and prev_bar_body > CFG["BIG_RATIO"] * prev_prev_bar_body
                      and prev_bar_range > 0 and (prev_bar_body / prev_bar_range) >= CFG["SQUARE_BAR"])
            if is_big and prev_bar_dir == 1:
                big_green_minute = int(cur_minute)
                red_count_since = 0
            elif prev_bar_dir == -1 and big_green_minute >= 0:
                red_count_since += 1
            # Pine sim state transitions on bar boundary
            if psim_state == PSIM_SKIP and is_big:
                psim_state = PSIM_IDLE
            if psim_state == PSIM_PROBE and psim_probe_open_minute is not None:
                if (int(cur_minute) - int(psim_probe_open_minute)) >= CFG["PINE_SIM_PROBE_MAX_B"]:
                    psim_state = PSIM_IDLE  # 2-bar timeout
            if psim_state == PSIM_COOLDOWN and psim_cooldown_start_minute is not None:
                if (int(cur_minute) - int(psim_cooldown_start_minute)) >= CFG["PINE_SIM_POST_LOSS_CD"]:
                    psim_state = PSIM_IDLE
        cur_minute = minute_id
        run_open = bid; run_high = bid; run_low = bid

    # Update running bar
    if bid > run_high: run_high = bid
    if bid < run_low: run_low = bid
    run_close = bid
    run_body = abs(run_close - run_open)
    if run_close > run_open: run_dir = 1
    elif run_close < run_open: run_dir = -1
    else: run_dir = 0

    is_today = t_ms >= int(today_start.timestamp() * 1000)

    # === PINE SIM STATE MACHINE (gates signal counter, INDEPENDENT of real trades) ===
    if psim_state == PSIM_IDLE:
        cooldown_ok = (last_fired_minute < 0) or ((minute_id - last_fired_minute) >= CFG["iCooldown"])
        if cooldown_ok and prev_bar_body > 0 and prev_prev_bar_body > 0:
            if prev_bar_body > CFG["BIG_RATIO"] * prev_prev_bar_body:
                if prev_bar_range > 0 and (prev_bar_body / prev_bar_range) >= CFG["SQUARE_BAR"]:
                    if prev_bar_dir != 0 and run_dir == prev_bar_dir:
                        pullback_ok = True
                        if run_dir == -1:
                            pullback_ok = (red_count_since >= CFG["iPullbackN"]) or (big_green_minute < 0)
                        if pullback_ok:
                            # SIGNAL FIRES — transition Pine sim, attempt real probe
                            if is_today: filter_funnel["raw_signals"] += 1
                            last_fired_minute = minute_id
                            psim_state = PSIM_PROBE
                            psim_dir = run_dir
                            psim_probe_entry = run_close
                            psim_probe_open_minute = minute_id

                            # Queue real probe with 5s polling delay (Python sniper)
                            if real_state == REAL_IDLE and pending_probe is None:
                                fire_at = t_ms + CFG["SNIPER_AVG_LATENCY_MS"]
                                pending_probe = (fire_at, run_dir, t_ms)

    elif psim_state == PSIM_PROBE:
        # Sim probe — uses Pine's own thresholds (0.58 / 3.0)
        if psim_dir == 1:
            sim_pnl = (run_close - psim_probe_entry) * CONTRACT_SIZE * CFG["probeLots"]
        else:
            sim_pnl = (psim_probe_entry - run_close) * CONTRACT_SIZE * CFG["probeLots"]
        if sim_pnl >= CFG["PINE_SIM_PROBE_CONF"]:
            psim_state = PSIM_TRADE
            psim_trade_entry = run_close
        elif sim_pnl <= -CFG["PINE_SIM_PROBE_FAIL"]:
            psim_state = PSIM_SKIP

    elif psim_state == PSIM_TRADE:
        if psim_dir == 1:
            sim_trade_pnl = (run_close - psim_trade_entry) * CONTRACT_SIZE * CFG["PINE_SIM_REAL_LOTS"]
        else:
            sim_trade_pnl = (psim_trade_entry - run_close) * CONTRACT_SIZE * CFG["PINE_SIM_REAL_LOTS"]
        if sim_trade_pnl >= CFG["PINE_SIM_TRADE_TP"]:
            psim_state = PSIM_IDLE
        elif sim_trade_pnl <= -CFG["PINE_SIM_TRADE_SL"]:
            psim_state = PSIM_COOLDOWN
            psim_cooldown_start_minute = minute_id

    # PSIM_COOLDOWN and PSIM_SKIP transitions handled at bar boundary above
    # PSIM_PROBE timeout handled at bar boundary too — let's add it

    # === Pending probe fire (Python sniper polling delay) ===
    if pending_probe is not None and real_state == REAL_IDLE:
        fire_at, p_dir, sig_ts = pending_probe
        if t_ms >= fire_at:
            # Light filters at probe stage (evaluated at delayed entry tick)
            fire_real = True
            if tick_i > 0 and (ts[tick_i] - ts[tick_i-1]) / 1000.0 > CFG["tickSpeedMaxSec"]:
                fire_real = False
            elif (ask - bid) * 100 > median_spread * CFG["spreadMaxMult"]:
                fire_real = False
            else:
                date_key = datetime.fromtimestamp(t_ms/1000, tz=timezone.utc).strftime("%Y-%m-%d")
                if day_pnl.get(date_key, 0) <= -CFG["dailyCap"]:
                    fire_real = False
            sig_today = sig_ts >= int(today_start.timestamp() * 1000)
            if fire_real:
                if sig_today:
                    filter_funnel["tickspeed"] += 1; filter_funnel["spread"] += 1; filter_funnel["executed_probe"] += 1
                real_state = REAL_PROBE
                real_probe_dir = p_dir
                real_probe_entry = ask if p_dir == 1 else bid
                real_probe_open_ts = t_ms
                real_probe_peak = -1e9
                if sig_today:
                    probe_attempts_today.append({
                        "ts": datetime.fromtimestamp(t_ms/1000, tz=timezone.utc).strftime("%H:%M:%S"),
                        "side": "buy" if p_dir == 1 else "sell",
                        "entry": round(real_probe_entry, 2),
                        "minute_close": round((bid + ask) / 2, 2),
                        "sig_ts": datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%H:%M:%S"),
                        "delay_s": round((t_ms - sig_ts) / 1000.0, 1),
                    })
            pending_probe = None

    # === REAL PROBE: track confirm/fail (independent of Pine sim) ===
    if real_state == REAL_PROBE:
        if real_probe_dir == 1:
            cur_pnl = (bid - real_probe_entry) * CONTRACT_SIZE * CFG["probeLots"]
        else:
            cur_pnl = (real_probe_entry - ask) * CONTRACT_SIZE * CFG["probeLots"]
        if cur_pnl > real_probe_peak: real_probe_peak = cur_pnl

        outcome = None
        if cur_pnl >= CFG["probeConfirm"]:
            outcome = "confirm"
        elif cur_pnl <= -CFG["probeFail"]:
            outcome = "fail"
        elif (CFG["probeTrailEnabled"] and real_probe_peak >= CFG["probeTrailTrigger"]
              and (real_probe_peak - cur_pnl) >= CFG["probeTrailDrop"]):
            outcome = "ptrail"

        if outcome is not None:
            probe_pnl = float(cur_pnl) - COMMISSION * CFG["probeLots"]
            today_p = real_probe_open_ts >= int(today_start.timestamp() * 1000)
            if today_p and len(probe_attempts_today):
                probe_attempts_today[-1]["outcome"] = outcome
                probe_attempts_today[-1]["pnl"] = round(probe_pnl, 2)
            probes.append({
                "open_ts": real_probe_open_ts, "exit_ts": t_ms, "side": real_probe_dir,
                "outcome": outcome, "pnl": probe_pnl,
            })
            date_key = datetime.fromtimestamp(real_probe_open_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            day_pnl[date_key] = day_pnl.get(date_key, 0) + probe_pnl

            if outcome == "confirm":
                if today_p: filter_funnel["probe_confirmed"] += 1
                sig_ts = real_probe_open_ts
                prob_dir = real_probe_dir

                # Proactively reset chain counters if gap > BURST_GAP_SEC since last main close
                if last_main_close_ts is not None and (sig_ts - last_main_close_ts) / 1000.0 >= BURST_GAP_SEC:
                    last_loss_count = 0; chain_idx = 0

                # Use prev closed bar's close as trigger for UHV check (per EA logic)
                pi_minute = real_probe_open_ts // 60000
                prev_pi = m1_idx_by_minute.get(int(pi_minute) - 1)
                trig_close_for_uhv = float(m1_c[prev_pi]) if prev_pi is not None else float(run_close)

                ok = True
                if CFG["uhvFilter"] and not uhv_breakout_ok(sig_ts, prob_dir, trig_close_for_uhv):
                    ok = False
                elif today_p:
                    filter_funnel["uhv_pass"] += 1
                if ok and CFG["trendFilter"] and not trend_at(sig_ts, m2_ema34, m2_ema89, m2_ts, prob_dir):
                    ok = False
                elif ok and today_p:
                    filter_funnel["trend2m_pass"] += 1
                if ok and CFG["m15TrendFilter"] and not trend_at(sig_ts, m15_ema34, m15_ema89, m15_ts, prob_dir):
                    ok = False
                elif ok and today_p:
                    filter_funnel["m15_pass"] += 1
                if ok and CFG["setup1Filter"] and not setup1_active(sig_ts, prob_dir):
                    ok = False
                elif ok and today_p:
                    filter_funnel["setup1_pass"] += 1
                if ok and CFG["burstDeltaFilter"] and not burst_delta_ok(tick_i, prob_dir):
                    ok = False
                elif ok and today_p:
                    filter_funnel["burstdelta_pass"] += 1
                # Chain state — block if too many losses in current chain
                if ok and last_loss_count >= CFG["chainStopAfterLoss"]:
                    ok = False
                if ok and chain_idx >= CFG["maxBurst"]:
                    ok = False
                if ok and today_p:
                    filter_funnel["chain_pass"] += 1

                if ok:
                    # OPEN REAL MAIN
                    if today_p: filter_funnel["executed_main"] += 1
                    chain_idx += 1
                    real_main_is_burst = chain_idx > 1
                    real_main_dir = prob_dir
                    real_main_entry = ask if real_main_dir == 1 else bid
                    real_main_open_ts = t_ms
                    real_main_peak = 0.0
                    real_state = REAL_MAIN
                else:
                    real_state = REAL_IDLE
            else:
                # probe failed or trailed in real world — back to REAL_IDLE (Pine sim handles its own state)
                real_state = REAL_IDLE

    # === REAL MAIN: track exit ===
    elif real_state == REAL_MAIN:
        if real_main_dir == 1:
            cur_pnl = (bid - real_main_entry) * CONTRACT_SIZE * CFG["overrideLots"]
        else:
            cur_pnl = (real_main_entry - ask) * CONTRACT_SIZE * CFG["overrideLots"]
        if cur_pnl > real_main_peak: real_main_peak = cur_pnl
        elapsed_s = (t_ms - real_main_open_ts) / 1000.0

        exit_reason = None
        if real_main_is_burst and cur_pnl <= -CFG["burstSlUsd"]:
            exit_reason = "burstSL"
        elif cur_pnl <= -CFG["fearIdeal"]:
            exit_reason = "fearIdeal"
        elif real_main_peak >= CFG["trailTrigger"] and (real_main_peak - cur_pnl) >= CFG["trailDrop"]:
            exit_reason = "trail"
        elif (CFG["mainNoGreenEnabled"] and elapsed_s >= CFG["mainNoGreenSec"]
              and real_main_peak < CFG["mainNoGreenPeakMin"]):
            exit_reason = "mainNoGreen"
        elif elapsed_s >= CFG["fearWashout"] and real_main_peak < CFG["trailTrigger"]:
            exit_reason = "washout"

        if exit_reason is not None:
            main_pnl = float(cur_pnl) - COMMISSION * CFG["overrideLots"]
            today_m = real_main_open_ts >= int(today_start.timestamp() * 1000)
            mains.append({
                "open_ts": real_main_open_ts, "exit_ts": t_ms, "side": real_main_dir,
                "exit_reason": exit_reason, "pnl": main_pnl,
                "is_burst": real_main_is_burst, "chain_idx": chain_idx,
            })
            if today_m:
                mains_today.append({
                    "ts": datetime.fromtimestamp(real_main_open_ts/1000, tz=timezone.utc).strftime("%H:%M:%S"),
                    "side": "buy" if real_main_dir == 1 else "sell",
                    "entry": round(real_main_entry, 2),
                    "exit_reason": exit_reason,
                    "pnl": round(main_pnl, 2),
                    "burst": real_main_is_burst,
                    "chain": chain_idx,
                    "duration_s": round(elapsed_s, 1),
                })
            date_key = datetime.fromtimestamp(real_main_open_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")
            day_pnl[date_key] = day_pnl.get(date_key, 0) + main_pnl
            if main_pnl < 0: last_loss_count += 1
            else: last_loss_count = 0
            last_main_close_ts = t_ms
            real_state = REAL_IDLE

# === REPORT ===
today_str = today_start.strftime("%Y-%m-%d")
print(f"\n{'='*80}\nTICK-BY-TICK MID-BAR REPLAY — full 120-day eval (today: {today_str})\n{'='*80}", flush=True)
print(f"\nTotal: {len(probes)} probes, {len(mains)} mains across full window", flush=True)

# Aggregate stats across all mains
if mains:
    arr_main = np.array([m["pnl"] for m in mains])
    arr_probe = np.array([p["pnl"] for p in probes])
    main_wins = (arr_main > 0).sum()
    main_losses = (arr_main < 0).sum()
    main_gw = float(arr_main[arr_main > 0].sum()) if (arr_main > 0).any() else 0
    main_gl = float(-arr_main[arr_main < 0].sum()) if (arr_main < 0).any() else 0
    eq_main = arr_main.cumsum()
    main_dd = float((np.maximum.accumulate(eq_main) - eq_main).max())
    print(f"\n=== FULL-WINDOW MAIN STATS ===", flush=True)
    print(f"  n: {len(mains)}", flush=True)
    print(f"  WR: {main_wins/len(mains)*100:.1f}% ({main_wins}W / {main_losses}L)", flush=True)
    print(f"  Net P&L: ${arr_main.sum():.2f}", flush=True)
    print(f"  PF: {main_gw/main_gl:.2f}" if main_gl > 0 else "  PF: inf", flush=True)
    print(f"  Avg/trade: ${arr_main.mean():.2f}", flush=True)
    print(f"  Max DD: ${main_dd:.2f}", flush=True)
    print(f"  Best: ${arr_main.max():.2f} | Worst: ${arr_main.min():.2f}", flush=True)
    # Including probe pnl too
    total_pnl = float(arr_main.sum() + arr_probe.sum())
    print(f"\n  Total P&L (probes + mains): ${total_pnl:.2f}", flush=True)
    print(f"  Probes: {len(probes)} | Probe net: ${arr_probe.sum():.2f}", flush=True)
    # Daily breakdown
    daily = {}
    for m in mains:
        d = datetime.fromtimestamp(m["open_ts"]/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        daily.setdefault(d, []).append(m["pnl"])
    win_days = sum(1 for d, lst in daily.items() if sum(lst) > 0)
    loss_days = sum(1 for d, lst in daily.items() if sum(lst) < 0)
    print(f"  Profitable days: {win_days} / {len(daily)} ({win_days/len(daily)*100:.0f}%)", flush=True)

probes_today_count = sum(1 for p in probes if p["open_ts"] >= int(today_start.timestamp() * 1000))
mains_today_count  = sum(1 for m in mains  if m["open_ts"] >= int(today_start.timestamp() * 1000))

print(f"\nTODAY ONLY:", flush=True)
print(f"  Backtest probes:  {probes_today_count}  (live: 107)", flush=True)
print(f"  Backtest mains:   {mains_today_count}  (live: 5)", flush=True)

print(f"\nFILTER FUNNEL (today):", flush=True)
for k, v in filter_funnel.items():
    print(f"  {k:>22}: {v}", flush=True)

print(f"\nALL TODAY MAINS:", flush=True)
for m in mains_today:
    print(f"  {m['ts']} | {m['side']:>4} {m['entry']} | {m['exit_reason']:>12} | ${m['pnl']:+.2f} | burst={m['burst']} chain#{m['chain']} dur={m['duration_s']}s", flush=True)

print(f"\nLIVE MAINS (for reference):", flush=True)
for hms, sd, pr, lbl in [("01:01:00","buy",4696.74,"Burst1"), ("13:15:00","buy",4735.35,"Burst1"),
                          ("13:15:59","buy",4735.99,"MG_Burst2"), ("17:25:17","buy",4758.99,"Burst1"),
                          ("19:16:22","sell",4711.57,"Burst1")]:
    print(f"  {hms} | {sd:>4} {pr} | {lbl}", flush=True)

print(f"\nDAY P&L: ${day_pnl.get(today_str, 0):.2f}  (live ~ -$220)", flush=True)

# Save
result = {
    "ran_at": datetime.now(timezone.utc).isoformat(),
    "today": today_str,
    "total_context_probes": len(probes), "total_context_mains": len(mains),
    "today_probes": probes_today_count, "today_mains": mains_today_count,
    "live_probes": 107, "live_mains": 5,
    "filter_funnel_today": filter_funnel,
    "today_main_entries": mains_today,
    "today_probe_attempts_first50": probe_attempts_today[:50],
    "day_pnl": day_pnl,
}
OUT_J.write_text(json.dumps(result, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
