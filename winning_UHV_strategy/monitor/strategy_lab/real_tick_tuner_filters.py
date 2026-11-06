"""Phase 2: structural filter tuning on top of phase-1-optimized baseline.

Loads phase 1 optimized baseline, then sequentially tunes:
  1. Per-hour session analysis (which UTC hours bleed)
  2. Progressive session-block (block worst-N hours)
  3. Max-spread cutoff
  4. Post-loss cooldown
  5. Daily-loss cap

Output: monitor/strategy_lab/_real_tick_filter_results.json
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
PHASE1 = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_tuning_results.json")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_real_tick_filter_results.json")

M5_SECONDS = 300
CONTRACT_SIZE = 100
PROBE_LOT = 0.01
MAIN_LOT  = 0.40
COMMISSION_PER_LOT_RT = 7.0
PROBE_COMM = COMMISSION_PER_LOT_RT * PROBE_LOT
MAIN_COMM  = COMMISSION_PER_LOT_RT * MAIN_LOT
MAIN_HOLD_CAP_S = 3600

def score(s):
    if s["n"] == 0: return -1e9
    return s["net_pnl"] - 0.5 * s["max_dd"]

print("[LOAD] reading parquet...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

ts   = df["time_msc"].to_numpy(dtype=np.int64)
bids = df["bid"].to_numpy(dtype=np.float64)
asks = df["ask"].to_numpy(dtype=np.float64)

df["m5_bucket"] = (df["time_msc"] // (M5_SECONDS * 1000)).astype(np.int64)
bars_full = df.groupby("m5_bucket", sort=True).agg(
    open=("bid","first"), high=("bid","max"), low=("bid","min"),
    close=("bid","last"), n=("bid","count"),
    ts_start_ms=("time_msc","first"), ts_end_ms=("time_msc","last"),
).reset_index()
bars_full["body"] = (bars_full["close"] - bars_full["open"]).abs()
bars_full["dir"]  = np.sign(bars_full["close"] - bars_full["open"]).astype(int)
bars_full["hour_utc"] = pd.to_datetime(bars_full["ts_end_ms"], unit="ms", utc=True).dt.hour
print(f"[BARS] {len(bars_full):,} M5 bars", flush=True)

def detect_signals(big_ratio: float):
    body = bars_full["body"].to_numpy(); direction = bars_full["dir"].to_numpy()
    n = len(body)
    big_prev_arr = np.zeros(n, dtype=bool)
    big_prev_arr[2:] = body[1:-1] > big_ratio * body[:-2]
    dir_prev = np.roll(direction, 1)
    sig_buy  = big_prev_arr & (dir_prev == 1) & (direction == 1)
    sig_sell = big_prev_arr & (dir_prev == -1) & (direction == -1)
    sig_buy[:2] = False; sig_sell[:2] = False
    return sig_buy, sig_sell

def precompute_signals(big_ratio):
    sig_buy, sig_sell = detect_signals(big_ratio)
    sigs = []
    for i in np.where(sig_buy)[0]:
        sigs.append((int(bars_full.iloc[i]["ts_end_ms"]), "buy", int(bars_full.iloc[i]["hour_utc"])))
    for i in np.where(sig_sell)[0]:
        sigs.append((int(bars_full.iloc[i]["ts_end_ms"]), "sell", int(bars_full.iloc[i]["hour_utc"])))
    sigs.sort()
    return sigs

def find_idx(t_ms):
    return int(np.searchsorted(ts, t_ms, side="right"))

def simulate(big_ratio, probe_confirm, probe_fail, probe_timeout_s,
             main_tp, main_sl,
             hours_block=None, max_spread_pts=None,
             post_loss_cooldown_min=0, daily_cap_loss=None,
             return_per_trade=False):
    sigs = precompute_signals(big_ratio)
    if hours_block:
        block_set = set(hours_block)
        sigs = [s for s in sigs if s[2] not in block_set]
    trades = []
    last_loss_ts = -1
    daily_pnl = {}
    for (sig_ts, side, hour_utc) in sigs:
        if post_loss_cooldown_min > 0 and last_loss_ts > 0:
            if (sig_ts - last_loss_ts) / 1000.0 / 60.0 < post_loss_cooldown_min:
                continue
        date_key = datetime.fromtimestamp(sig_ts/1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if daily_cap_loss is not None and daily_pnl.get(date_key, 0) <= -abs(daily_cap_loss):
            continue
        pi = find_idx(sig_ts)
        if pi >= len(ts): continue
        if max_spread_pts is not None:
            spread_pts_now = (asks[pi] - bids[pi]) * 100
            if spread_pts_now > max_spread_pts: continue
        p_entry_ts = ts[pi]
        p_entry = asks[pi] if side == "buy" else bids[pi]

        timeout_ts = p_entry_ts + probe_timeout_s * 1000
        end_idx = find_idx(timeout_ts)
        if end_idx <= pi: continue
        if side == "buy":
            pnl_arr = (bids[pi:end_idx] - p_entry) * CONTRACT_SIZE * PROBE_LOT
        else:
            pnl_arr = (p_entry - asks[pi:end_idx]) * CONTRACT_SIZE * PROBE_LOT
        sub_ts = ts[pi:end_idx]

        c_idx = int(np.argmax(pnl_arr >= probe_confirm)) if (pnl_arr >= probe_confirm).any() else -1
        f_idx = int(np.argmax(pnl_arr <= probe_fail))    if (pnl_arr <= probe_fail).any() else -1
        if c_idx >= 0 and (f_idx < 0 or c_idx <= f_idx):
            outcome = "confirm"; exit_idx_local = c_idx
        elif f_idx >= 0:
            outcome = "fail"; exit_idx_local = f_idx
        else:
            outcome = "timeout"; exit_idx_local = len(pnl_arr) - 1
        probe_pnl = float(pnl_arr[exit_idx_local])
        probe_exit_ts = int(sub_ts[exit_idx_local])
        total = probe_pnl - PROBE_COMM

        if outcome == "confirm":
            mi = find_idx(probe_exit_ts)
            if mi < len(ts):
                m_entry = asks[mi] if side == "buy" else bids[mi]
                main_cap_ts = ts[mi] + MAIN_HOLD_CAP_S * 1000
                end_idx2 = find_idx(main_cap_ts)
                if end_idx2 > mi:
                    if side == "buy":
                        m_pnl_arr = (bids[mi:end_idx2] - m_entry) * CONTRACT_SIZE * MAIN_LOT
                    else:
                        m_pnl_arr = (m_entry - asks[mi:end_idx2]) * CONTRACT_SIZE * MAIN_LOT
                    tp_idx = int(np.argmax(m_pnl_arr >= main_tp)) if (m_pnl_arr >= main_tp).any() else -1
                    sl_idx = int(np.argmax(m_pnl_arr <= -abs(main_sl))) if (m_pnl_arr <= -abs(main_sl)).any() else -1
                    if tp_idx >= 0 and (sl_idx < 0 or tp_idx <= sl_idx):
                        m_realized = float(m_pnl_arr[tp_idx])
                    elif sl_idx >= 0:
                        m_realized = float(m_pnl_arr[sl_idx])
                    else:
                        m_realized = float(m_pnl_arr[-1])
                    total += (m_realized - MAIN_COMM)

        trades.append((sig_ts, side, hour_utc, outcome, probe_pnl, total))
        if total < 0:
            last_loss_ts = sig_ts
        daily_pnl[date_key] = daily_pnl.get(date_key, 0) + total

    if not trades:
        empty = {"n":0,"wr":0,"wins":0,"losses":0,"net_pnl":0,"pf":0,"max_dd":0,"avg_pnl":0,"best":0,"worst":0}
        return (empty, trades) if return_per_trade else empty
    arr = np.array([t[5] for t in trades])
    wins = (arr > 0).sum(); losses = (arr < 0).sum()
    gross_w = arr[arr > 0].sum(); gross_l = -arr[arr < 0].sum()
    eq = arr.cumsum()
    dd = float((np.maximum.accumulate(eq) - eq).max())
    s = {
        "n": len(trades),
        "wr": round(wins/len(trades)*100, 2),
        "wins": int(wins), "losses": int(losses),
        "net_pnl": round(float(arr.sum()), 2),
        "avg_pnl": round(float(arr.mean()), 3),
        "pf": round(float(gross_w/gross_l), 2) if gross_l > 0 else None,
        "max_dd": round(dd, 2),
        "best": round(float(arr.max()), 2),
        "worst": round(float(arr.min()), 2),
    }
    return (s, trades) if return_per_trade else s

# Load phase 1 winner
phase1 = json.loads(PHASE1.read_text())
baseline = dict(phase1["final_baseline"])
print("[BASELINE from phase 1]:", json.dumps(baseline, default=str), flush=True)
b0 = simulate(**{k: v for k, v in baseline.items() if k != "return_per_trade"})
print(f"  pre-filter: n={b0['n']} WR={b0['wr']}% net=${b0['net_pnl']} PF={b0['pf']} DD=${b0['max_dd']}", flush=True)

results = {"started": datetime.now(timezone.utc).isoformat(), "phase1_baseline": dict(baseline), "phase1_stats": b0}

# ===== 1. PER-HOUR ANALYSIS =====
print("\n=== PER-HOUR ANALYSIS (UTC) ===", flush=True)
print(f"{'hour':>4} | {'n':>5} | {'WR%':>6} | {'net':>10} | {'avg':>7} | impact_if_blocked", flush=True)
print("-" * 80, flush=True)
_, all_trades = simulate(return_per_trade=True, **{k: v for k, v in baseline.items() if k != "return_per_trade"})
hour_breakdown = {}
for h in range(24):
    h_trades = [t for t in all_trades if t[2] == h]
    if not h_trades:
        hour_breakdown[h] = {"n": 0, "wr": 0, "net": 0, "avg": 0}
        continue
    arr = np.array([t[5] for t in h_trades])
    wins = (arr > 0).sum()
    hour_breakdown[h] = {
        "n": len(h_trades),
        "wr": round(wins/len(h_trades)*100, 2),
        "net": round(float(arr.sum()), 2),
        "avg": round(float(arr.mean()), 3),
        "impact_if_blocked": round(-float(arr.sum()), 2),
    }
for h in range(24):
    hb = hour_breakdown[h]
    print(f"{h:>4} | {hb['n']:>5} | {hb['wr']:>6.2f} | {hb['net']:>10.2f} | {hb['avg']:>7.3f} | {hb.get('impact_if_blocked', 0):>+8.2f}", flush=True)
results["hour_breakdown"] = hour_breakdown

# ===== 2. PROGRESSIVE SESSION BLOCK =====
print("\n=== PROGRESSIVE SESSION BLOCK ===", flush=True)
sorted_hours = sorted(range(24), key=lambda h: hour_breakdown[h]["net"])
print(f"hours sorted by net (worst -> best): {sorted_hours[:10]}", flush=True)
print(f"{'block_top_N':>11} | {'blocked':>40} | {'n':>5} | {'WR%':>6} | {'net':>10} | {'PF':>5} | score", flush=True)
print("-" * 110, flush=True)
best_block_score = score(b0); best_blocked = []; best_block_stats = b0
session_table = []
for n_block in range(0, 16):
    blocked = sorted_hours[:n_block]
    cfg = dict(baseline); cfg["hours_block"] = blocked if blocked else None
    s = simulate(**cfg)
    sc = score(s)
    session_table.append({"n_block": n_block, "blocked_hours": blocked, **s, "score": round(sc, 2)})
    print(f"{n_block:>11} | {str(sorted(blocked)):>40} | {s['n']:>5} | {s['wr']:>6.2f} | {s['net_pnl']:>10.2f} | {str(s['pf']):>5} | {sc:>9.2f}", flush=True)
    if sc > best_block_score:
        best_block_score = sc; best_blocked = blocked; best_block_stats = s
baseline["hours_block"] = best_blocked if best_blocked else None
print(f"  -> BEST block list: {sorted(best_blocked) if best_blocked else 'none'} | net=${best_block_stats['net_pnl']} | WR={best_block_stats['wr']}%", flush=True)
results["session_table"] = session_table
results["session_best_blocked"] = best_blocked

# ===== 3. MAX-SPREAD =====
print("\n=== MAX-SPREAD FILTER ===", flush=True)
print(f"{'pts':>6} | {'n':>5} | {'WR%':>6} | {'net':>10} | {'PF':>5} | {'DD':>9} | score", flush=True)
print("-" * 80, flush=True)
spread_table = []; best_spread = None; best_spread_score = score(best_block_stats); best_spread_stats = best_block_stats
for sp in [None, 100, 50, 30, 25, 20, 17, 15, 13, 10, 8, 5]:
    cfg = dict(baseline); cfg["max_spread_pts"] = sp
    s = simulate(**cfg); sc = score(s)
    spread_table.append({"max_spread_pts": sp, **s, "score": round(sc, 2)})
    label = "no-cap" if sp is None else str(sp)
    print(f"{label:>6} | {s['n']:>5} | {s['wr']:>6.2f} | {s['net_pnl']:>10.2f} | {str(s['pf']):>5} | {s['max_dd']:>9.2f} | {sc:>9.2f}", flush=True)
    if sc > best_spread_score:
        best_spread_score = sc; best_spread = sp; best_spread_stats = s
baseline["max_spread_pts"] = best_spread
print(f"  -> BEST max_spread_pts: {best_spread} | net=${best_spread_stats['net_pnl']} | WR={best_spread_stats['wr']}%", flush=True)
results["spread_table"] = spread_table

# ===== 4. POST-LOSS COOLDOWN =====
print("\n=== POST-LOSS COOLDOWN (minutes) ===", flush=True)
print(f"{'min':>5} | {'n':>5} | {'WR%':>6} | {'net':>10} | {'PF':>5} | score", flush=True)
print("-" * 80, flush=True)
cd_table = []; best_cd = 0; best_cd_score = score(best_spread_stats); best_cd_stats = best_spread_stats
for cd in [0, 5, 10, 15, 30, 60, 120, 240, 480, 1440]:
    cfg = dict(baseline); cfg["post_loss_cooldown_min"] = cd
    s = simulate(**cfg); sc = score(s)
    cd_table.append({"post_loss_cooldown_min": cd, **s, "score": round(sc, 2)})
    print(f"{cd:>5} | {s['n']:>5} | {s['wr']:>6.2f} | {s['net_pnl']:>10.2f} | {str(s['pf']):>5} | {sc:>9.2f}", flush=True)
    if sc > best_cd_score:
        best_cd_score = sc; best_cd = cd; best_cd_stats = s
baseline["post_loss_cooldown_min"] = best_cd
print(f"  -> BEST cooldown: {best_cd} min | net=${best_cd_stats['net_pnl']} | WR={best_cd_stats['wr']}%", flush=True)
results["cooldown_table"] = cd_table

# ===== 5. DAILY-LOSS CAP =====
print("\n=== DAILY-LOSS CAP ($) ===", flush=True)
print(f"{'cap':>6} | {'n':>5} | {'WR%':>6} | {'net':>10} | {'PF':>5} | score", flush=True)
print("-" * 80, flush=True)
dc_table = []; best_dc = None; best_dc_score = score(best_cd_stats); best_dc_stats = best_cd_stats
for dc in [None, 500, 200, 100, 75, 50, 30, 20, 10]:
    cfg = dict(baseline); cfg["daily_cap_loss"] = dc
    s = simulate(**cfg); sc = score(s)
    dc_table.append({"daily_cap_loss": dc, **s, "score": round(sc, 2)})
    label = "no-cap" if dc is None else f"-${dc}"
    print(f"{label:>6} | {s['n']:>5} | {s['wr']:>6.2f} | {s['net_pnl']:>10.2f} | {str(s['pf']):>5} | {sc:>9.2f}", flush=True)
    if sc > best_dc_score:
        best_dc_score = sc; best_dc = dc; best_dc_stats = s
baseline["daily_cap_loss"] = best_dc
print(f"  -> BEST daily cap: {best_dc} | net=${best_dc_stats['net_pnl']} | WR={best_dc_stats['wr']}%", flush=True)
results["daily_cap_table"] = dc_table

# ===== FINAL =====
print("\n=== FINAL STACKED ===", flush=True)
final = simulate(**baseline)
print(json.dumps(baseline, indent=2, default=str), flush=True)
print(f"  net=${final['net_pnl']} | WR={final['wr']}% | PF={final['pf']} | DD=${final['max_dd']}", flush=True)
print(f"  delta vs phase-1 start: ${final['net_pnl'] - b0['net_pnl']:+.2f} | WR Δ {final['wr'] - b0['wr']:+.2f}%", flush=True)
results["final_baseline"] = dict(baseline)
results["final_stats"] = final
OUT_J.write_text(json.dumps(results, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
