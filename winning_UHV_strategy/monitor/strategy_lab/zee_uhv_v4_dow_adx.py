"""v4: Day-of-week filter + ADX regime filter (both via walk-forward).

Plan:
  1. Strict v2 entry (vol_ratio≤0.40, body≥0.80, UHV vol≥2x recent avg)
  2. Add ADX(14) regime gate — ADX > 25 = trending market (good for breakouts)
  3. Walk-forward: train first 60 days, test last 26
  4. On train: identify (day-of-week, regime) combos with WR≥70%
  5. On test: apply same combos, check if positive

If walk-forward passes, we have a real edge.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_uhv_v4_dow_adx.json")

LOTS = 0.10; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100
UHV_LOOKBACK = 20; UHV_MAX_AGE_BARS = 10; RECENT_AVG_BARS = 20
UHV_MIN_VOL_MULT = 2.0
MAX_OPPOSING_WICK = 0.25
MIN_BODY_PCT = 0.80
MAX_VOL_RATIO = 0.40
MIN_SPACING_SEC = 60
DAILY_LOSS_USD = 100.0
ADX_PERIOD = 14
ADX_TRENDING_THRESHOLD = 25     # ADX > this = trending market
EXIT = {"trail_trigger": 10, "trail_drop": 3, "catastrophic_usd": 30, "scratch_sec": 30, "max_hold_min": 10}

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1_grp = df.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1_grp["hour"] = m1_grp["dt"].dt.hour
m1_grp["dow"] = m1_grp["dt"].dt.dayofweek   # 0=Mon, 4=Fri

# ADX via standard formula
high = m1_grp["h"].to_numpy(); low = m1_grp["l"].to_numpy(); close = m1_grp["c"].to_numpy()
tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
plus_dm = np.where((high - np.roll(high, 1)) > (np.roll(low, 1) - low),
                    np.maximum(high - np.roll(high, 1), 0), 0)
minus_dm = np.where((np.roll(low, 1) - low) > (high - np.roll(high, 1)),
                     np.maximum(np.roll(low, 1) - low, 0), 0)

# Wilder's smoothing approximation via ewma
def wilder(arr, period):
    arr = np.asarray(arr, dtype=float)
    out = np.full_like(arr, np.nan)
    if len(arr) < period: return out
    out[period - 1] = arr[:period].mean()
    for i in range(period, len(arr)):
        out[i] = (out[i - 1] * (period - 1) + arr[i]) / period
    return out

tr_n = wilder(tr, ADX_PERIOD)
plus_di = 100 * wilder(plus_dm, ADX_PERIOD) / np.where(tr_n == 0, np.nan, tr_n)
minus_di = 100 * wilder(minus_dm, ADX_PERIOD) / np.where(tr_n == 0, np.nan, tr_n)
dx = 100 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, np.nan, (plus_di + minus_di))
adx = wilder(np.nan_to_num(dx, nan=0.0), ADX_PERIOD)
m1_grp["adx"] = adx

m1 = m1_grp.to_dict("records")
ts_arr = df["time_msc"].to_numpy(dtype=np.int64)
bids_arr = df["bid"].to_numpy(dtype=np.float64)
asks_arr = df["ask"].to_numpy(dtype=np.float64)


def detect(idx):
    if idx < UHV_LOOKBACK + RECENT_AVG_BARS + 5: return None
    win_lo = idx - UHV_LOOKBACK
    uhv_idx = max(range(win_lo, idx), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] <= 0 or (idx - uhv_idx) > UHV_MAX_AGE_BARS: return None
    rv = [m1[j]["v"] for j in range(max(0, uhv_idx - RECENT_AVG_BARS), uhv_idx) if j != uhv_idx]
    if not rv: return None
    if uhv["v"] < UHV_MIN_VOL_MULT * (sum(rv) / len(rv)): return None
    cur = m1[idx]
    if cur["v"] / uhv["v"] > MAX_VOL_RATIO: return None
    rng = cur["h"] - cur["l"]
    if rng <= 0: return None
    body = abs(cur["c"] - cur["o"])
    if body / rng < MIN_BODY_PCT: return None
    is_red = uhv["c"] < uhv["o"]; is_green = uhv["c"] > uhv["o"]
    if not (is_red or is_green): return None
    if is_red:
        if cur["c"] <= uhv["h"]: return None
        if (cur["h"] - cur["c"]) / rng > MAX_OPPOSING_WICK: return None
        side = "buy"
    else:
        if cur["c"] >= uhv["l"]: return None
        if (cur["c"] - cur["l"]) / rng > MAX_OPPOSING_WICK: return None
        side = "sell"
    return {"side": side, "ts_end_ms": cur["ts_end_ms"], "hour": cur["hour"], "dow": cur["dow"],
            "date": cur["date"], "adx": cur["adx"]}


def fill(sig):
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    if i0 >= len(ts_arr): return None
    if sig["side"] == "buy": return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def walk(side, fi, entry_price, entry_ts, cfg):
    end_ts = entry_ts + cfg["max_hold_min"] * 60 * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9; has_pos = False; armed = False; cur_pnl = 0
    for k in range(fi + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy": cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:             cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        peak = max(peak, cur_pnl)
        if cur_pnl > 0: has_pos = True
        if cur_pnl <= -cfg["catastrophic_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "peak": peak}
        if not armed and peak >= cfg["trail_trigger"]: armed = True
        if armed and (peak - cur_pnl) >= cfg["trail_drop"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TRAIL", "peak": peak}
        if not has_pos and elapsed > cfg["scratch_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SCRATCH", "peak": peak}
    return {"pnl": cur_pnl - COMMISSION, "reason": "TIMEOUT", "peak": peak}


def run_window(date_lo, date_hi, dow_set=None, require_trending=False):
    trades = []; last_entry = 0; daily = {}; halted = set()
    for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + ADX_PERIOD + 5, len(m1)):
        bar = m1[idx]; date = bar["date"]
        if date < date_lo or date >= date_hi: continue
        if bar["hour"] < 6: continue
        if dow_set is not None and bar["dow"] not in dow_set: continue
        if require_trending and (np.isnan(bar["adx"]) or bar["adx"] < ADX_TRENDING_THRESHOLD): continue
        if date in halted: continue
        if daily.get(date, 0) <= -DAILY_LOSS_USD: halted.add(date); continue
        if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
        sig = detect(idx)
        if not sig: continue
        f = fill(sig)
        if not f: continue
        fi, fp, ft = f
        r = walk(sig["side"], fi, fp, ft, EXIT)
        daily[date] = daily.get(date, 0) + r["pnl"]
        trades.append({"date": date, "hour": sig["hour"], "dow": sig["dow"], "adx": round(sig["adx"], 1),
                       "side": sig["side"], "pnl": round(r["pnl"], 2), "reason": r["reason"], "peak": round(r["peak"], 2)})
        last_entry = ft
    return trades, daily, halted


dates = sorted(set(b["date"] for b in m1))
split_idx = int(len(dates) * 0.70)
train_lo = dates[0]; train_hi = dates[split_idx]
test_lo  = dates[split_idx]; test_hi = "9999-99-99"

print(f"TRAIN: {train_lo} .. {train_hi}  ({split_idx} days)", flush=True)
print(f"TEST:  {test_lo} .. (end)   ({len(dates)-split_idx} days)", flush=True)

# === DOW-only walk-forward ===
print(f"\n[TRAIN] all-DOW run (find winning days-of-week)...", flush=True)
tr_trades, _, _ = run_window(train_lo, train_hi)
by_dow = {}
for t in tr_trades:
    by_dow.setdefault(t["dow"], []).append(t)
dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
print(f"  {'DoW':>4} {'n':>4} {'WR%':>5} {'Net':>9}", flush=True)
winning_dows = set()
for dow in sorted(by_dow):
    ts = by_dow[dow]
    w = sum(1 for t in ts if t["pnl"] > 0)
    net = sum(t["pnl"] for t in ts)
    wr = w / len(ts) * 100
    mk = " ⭐" if wr >= 70 and len(ts) >= 3 and net > 0 else ""
    print(f"  {dow_names[dow]:>4} {len(ts):>4} {wr:>4.0f}% ${net:>+8.2f}{mk}", flush=True)
    if wr >= 70 and len(ts) >= 3 and net > 0: winning_dows.add(dow)

print(f"\n  Train-winning DOWs: {sorted([dow_names[d] for d in winning_dows])}", flush=True)
te_trades, te_daily, te_halted = run_window(test_lo, test_hi, dow_set=winning_dows)
print(f"\n[TEST] DOW filter only ({sorted(winning_dows)})", flush=True)
if not te_trades:
    print(f"  No trades on TEST")
    dow_verdict = "NO_TRADES"
else:
    n = len(te_trades); w = sum(1 for t in te_trades if t["pnl"]>0)
    net = sum(t["pnl"] for t in te_trades)
    print(f"  n={n}  WR={w/n*100:.1f}%  NET=${net:+.2f}  days_profit={sum(1 for p in te_daily.values() if p>0)}/{len(te_daily)}", flush=True)
    dow_verdict = "GENERALIZES" if net > 0 else "OVERFIT"

# === ADX-only walk-forward ===
print(f"\n[TEST] ADX>{ADX_TRENDING_THRESHOLD} only (no train, just regime gate)...", flush=True)
te_trades_adx, te_daily_adx, te_halted_adx = run_window(test_lo, test_hi, require_trending=True)
if not te_trades_adx:
    print(f"  No trades on TEST with ADX gate")
    adx_verdict = "NO_TRADES"
else:
    n = len(te_trades_adx); w = sum(1 for t in te_trades_adx if t["pnl"]>0)
    net = sum(t["pnl"] for t in te_trades_adx)
    print(f"  n={n}  WR={w/n*100:.1f}%  NET=${net:+.2f}  days_profit={sum(1 for p in te_daily_adx.values() if p>0)}/{len(te_daily_adx)}", flush=True)
    adx_verdict = "POSITIVE" if net > 0 else "NEGATIVE"

# === COMBO: DOW + ADX ===
print(f"\n[TEST] DOW filter AND ADX>{ADX_TRENDING_THRESHOLD}...", flush=True)
te_trades_combo, te_daily_combo, te_halted_combo = run_window(test_lo, test_hi, dow_set=winning_dows, require_trending=True)
if not te_trades_combo:
    print(f"  No trades on TEST with combo gate")
    combo_verdict = "NO_TRADES"
else:
    n = len(te_trades_combo); w = sum(1 for t in te_trades_combo if t["pnl"]>0)
    net = sum(t["pnl"] for t in te_trades_combo)
    print(f"  n={n}  WR={w/n*100:.1f}%  NET=${net:+.2f}  days_profit={sum(1 for p in te_daily_combo.values() if p>0)}/{len(te_daily_combo)}", flush=True)
    combo_verdict = "GENERALIZES" if net > 0 else "OVERFIT"

print(f"\n=== VERDICTS ===", flush=True)
print(f"  DOW filter only:       {dow_verdict}", flush=True)
print(f"  ADX gate only:         {adx_verdict}", flush=True)
print(f"  DOW + ADX combo:       {combo_verdict}", flush=True)

OUT_J.write_text(json.dumps({
    "started": datetime.now(timezone.utc).isoformat(),
    "winning_dows_train": sorted([dow_names[d] for d in winning_dows]),
    "dow_verdict": dow_verdict,
    "adx_verdict": adx_verdict,
    "combo_verdict": combo_verdict,
    "test_dow_trades": len(te_trades),
    "test_adx_trades": len(te_trades_adx) if te_trades_adx else 0,
    "test_combo_trades": len(te_trades_combo) if te_trades_combo else 0,
}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
