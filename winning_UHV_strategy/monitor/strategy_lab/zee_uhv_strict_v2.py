"""Round 2: MUCH stricter UHV entry filters + per-hour analysis.

Hypothesis: 13 trades/day with 55% WR isn't profitable because losses are 3-5x bigger than wins.
Solution: fire 3-5 high-quality trades/day instead. Tightening:

  - vol_ratio ≤ 0.40 (was 0.70) → breakout candle MUST be very quiet (true no-supply)
  - body_pct ≥ 0.80 (was 0.65) → only obvious momentum candles
  - UHV vol must be ≥ 2.0× the mean of last 20 bars (TRUE volume spike, not relative)
  - Same wick rejection ≤ 0.25
  - Use winning Zee-loose exit ($10/$3 trail)

Plus: dumps per-hour P&L breakdown so we can identify time-of-day winners.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_uhv_strict_v2.json")

LOTS = 0.10; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100

# === STRICT v2 ENTRY RULES ===
UHV_LOOKBACK         = 20
UHV_MAX_AGE_BARS     = 10
MIN_BODY_PCT         = 0.80              # ↑ from 0.65
MAX_VOL_RATIO        = 0.40              # ↓ from 0.70 (much quieter breakout candle)
MAX_OPPOSING_WICK    = 0.25
UHV_MIN_VOL_MULT     = 2.0               # NEW: UHV vol must be ≥ 2× recent 20-bar mean
RECENT_AVG_BARS      = 20                # window for "recent average vol"
SKIP_SYDNEY          = True
MIN_SPACING_SEC      = 60
DAILY_LOSS_USD       = 100.0

EXIT = {"trail_trigger": 10, "trail_drop": 3, "catastrophic_usd": 30,
        "scratch_sec": 30, "max_hold_min": 10}

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
    # NEW: UHV vol must be ≥ N× recent average
    recent_vols = [m1[j]["v"] for j in range(max(0, uhv_idx - RECENT_AVG_BARS), uhv_idx) if j != uhv_idx]
    if not recent_vols: return None
    recent_mean = sum(recent_vols) / len(recent_vols)
    if uhv["v"] < UHV_MIN_VOL_MULT * recent_mean: return None
    cur = m1[idx]
    vr = cur["v"] / uhv["v"]
    if vr > MAX_VOL_RATIO: return None
    rng = cur["h"] - cur["l"]
    if rng <= 0: return None
    body = abs(cur["c"] - cur["o"])
    if body / rng < MIN_BODY_PCT: return None
    is_red = uhv["c"] < uhv["o"]; is_green = uhv["c"] > uhv["o"]
    if not (is_red or is_green): return None
    if is_red:
        if cur["c"] <= uhv["h"]: return None
        if (cur["h"] - cur["c"]) / rng > MAX_OPPOSING_WICK: return None
        return {"side": "buy", "ts_end_ms": cur["ts_end_ms"], "vol_ratio": vr, "body_pct": body/rng,
                "uhv_vol_mult": uhv["v"]/recent_mean, "hour": cur["hour"]}
    else:
        if cur["c"] >= uhv["l"]: return None
        if (cur["c"] - cur["l"]) / rng > MAX_OPPOSING_WICK: return None
        return {"side": "sell", "ts_end_ms": cur["ts_end_ms"], "vol_ratio": vr, "body_pct": body/rng,
                "uhv_vol_mult": uhv["v"]/recent_mean, "hour": cur["hour"]}


def fill(sig):
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    if i0 >= len(ts_arr): return None
    if sig["side"] == "buy": return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def walk_trail(side, fi, entry_price, entry_ts, cfg):
    end_ts = entry_ts + cfg["max_hold_min"] * 60 * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    peak = -1e9; has_pos = False; armed = False
    cur_pnl = 0
    for k in range(fi + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:
            cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        peak = max(peak, cur_pnl)
        if cur_pnl > 0: has_pos = True
        if cur_pnl <= -cfg["catastrophic_usd"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SL", "age": elapsed, "peak": peak}
        if not armed and peak >= cfg["trail_trigger"]: armed = True
        if armed and (peak - cur_pnl) >= cfg["trail_drop"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "TRAIL", "age": elapsed, "peak": peak}
        if not has_pos and elapsed > cfg["scratch_sec"]:
            return {"pnl": cur_pnl - COMMISSION, "reason": "SCRATCH", "age": elapsed, "peak": peak}
    return {"pnl": cur_pnl - COMMISSION, "reason": "TIMEOUT", "age": cfg["max_hold_min"]*60, "peak": peak}


trades = []; last_entry = 0; daily = {}; halted = set()
for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + 5, len(m1)):
    bar = m1[idx]; date = bar["date"]
    if SKIP_SYDNEY and bar["hour"] < 6: continue
    if date in halted: continue
    if daily.get(date, 0) <= -DAILY_LOSS_USD: halted.add(date); continue
    if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
    sig = detect(idx)
    if not sig: continue
    f = fill(sig)
    if not f: continue
    fi, fp, ft = f
    r = walk_trail(sig["side"], fi, fp, ft, EXIT)
    daily[date] = daily.get(date, 0) + r["pnl"]
    trades.append({"date": date, "hour": sig["hour"], "side": sig["side"], "pnl": round(r["pnl"], 2),
                   "reason": r["reason"], "age": round(r["age"], 1), "peak": round(r["peak"], 2),
                   "volR": round(sig["vol_ratio"], 2), "body": round(sig["body_pct"], 2),
                   "uhv_mult": round(sig["uhv_vol_mult"], 1)})
    last_entry = ft

n = len(trades)
print(f"\nSTRICT v2 — entry: vol_ratio≤{MAX_VOL_RATIO}, body≥{MIN_BODY_PCT}, UHV vol ≥ {UHV_MIN_VOL_MULT}× recent avg", flush=True)
if n == 0:
    print("  No signals — filter too strict")
else:
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    net = sum(t["pnl"] for t in trades)
    avg = net / n
    reasons = {}
    for t in trades: reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    days_p = sum(1 for p in daily.values() if p > 0)
    days_l = sum(1 for p in daily.values() if p < 0)
    print(f"  n={n}  trades/day={n/86:.1f}  WR={wins/n*100:.1f}%  NET=${net:+.2f}  avg=${avg:+.2f}", flush=True)
    print(f"  days: profit={days_p}/{len(daily)}  loss={days_l}  halted={len(halted)}", flush=True)
    print(f"  reasons: {reasons}", flush=True)

    # === PER-HOUR BREAKDOWN ===
    print(f"\n  Per-hour P&L:", flush=True)
    print(f"  {'Hr':>4} {'n':>5} {'WR%':>6} {'Net':>9} {'Avg':>7}", flush=True)
    by_hr = {}
    for t in trades:
        by_hr.setdefault(t["hour"], []).append(t)
    for hr in sorted(by_hr):
        ts = by_hr[hr]
        w = sum(1 for t in ts if t["pnl"] > 0)
        net_h = sum(t["pnl"] for t in ts)
        print(f"  {hr:>4} {len(ts):>5} {w/len(ts)*100:>5.0f}% ${net_h:>+8.2f} ${net_h/len(ts):>+6.2f}", flush=True)

    print(f"\n  Sample best 5 trades (by peak):", flush=True)
    for t in sorted(trades, key=lambda t: -t["peak"])[:5]:
        print(f"    {t['date']} hr={t['hour']:>2}  {t['side']:>4}  volR={t['volR']:.2f}  body={t['body']:.2f}  uhv_mult={t['uhv_mult']:>3}x  pnl=${t['pnl']:+.2f}  peak=${t['peak']:+.2f}", flush=True)

OUT_J.write_text(json.dumps({
    "started": datetime.now(timezone.utc).isoformat(),
    "rules": f"vol_ratio≤{MAX_VOL_RATIO}, body≥{MIN_BODY_PCT}, UHV vol ≥ {UHV_MIN_VOL_MULT}× recent, wick≤{MAX_OPPOSING_WICK}, Zee-loose exit",
    "n": n,
    "summary": {
        "trades": n,
        "wr_pct": round(wins/n*100, 1) if n else 0,
        "net_usd": round(net, 2) if n else 0,
        "days_profit": days_p if n else 0,
        "days_loss": days_l if n else 0,
        "days_halted": len(halted) if n else 0,
        "trades_per_day": round(n/86, 2) if n else 0,
    } if n else {},
    "daily_pnl": {d: round(p, 2) for d, p in sorted(daily.items())} if n else {},
    "per_hour": {str(hr): {"n": len(ts), "wr_pct": round(sum(1 for t in ts if t["pnl"]>0)/len(ts)*100, 1),
                            "net_usd": round(sum(t["pnl"] for t in ts), 2)}
                  for hr, ts in by_hr.items()} if n else {},
}, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
