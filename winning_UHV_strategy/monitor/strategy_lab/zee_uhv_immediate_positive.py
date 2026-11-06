"""Question (Zee 2026-05-11): how many UHV breakout trades go IMMEDIATELY positive after fill?

This decouples SIGNAL QUALITY from EXIT QUALITY. If 92% of signals go positive within
5-10 seconds, the entry edge is real — exit is just engineering. If only 50% go positive,
the signal isn't edged.

For each signal that passes the strict v2 filters:
  - Walk first 30 seconds tick by tick
  - Record: did P&L go > $0 at +1s, +3s, +5s, +10s, +30s
  - Record: peak P&L within each window
  - Aggregate: % of trades that went positive at each cutoff

Spread is included (entry at ask for buy, P&L on bid; mirror for sell). Commission excluded
since we're measuring directional quality, not net profitability.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_immediate_positive.json")

LOTS = 0.10; CONTRACT_SIZE = 100
UHV_LOOKBACK = 20; UHV_MAX_AGE_BARS = 10; RECENT_AVG_BARS = 20
UHV_MIN_VOL_MULT = 2.0
MAX_OPPOSING_WICK = 0.25
MIN_BODY_PCT = 0.80
MAX_VOL_RATIO = 0.40
MIN_SPACING_SEC = 60
SKIP_SYDNEY = True

CHECKPOINTS_SEC = [1, 3, 5, 10, 30]   # seconds after fill to measure

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
m1_grp["dow"]  = m1_grp["dt"].dt.dayofweek
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
            "date": cur["date"]}


def fill(sig):
    """Market-order: first tick after bar close. Fill at ask (buy) or bid (sell)."""
    i0 = int(np.searchsorted(ts_arr, sig["ts_end_ms"], side="right"))
    if i0 >= len(ts_arr): return None
    if sig["side"] == "buy": return i0, asks_arr[i0], int(ts_arr[i0])
    return i0, bids_arr[i0], int(ts_arr[i0])


def measure_positive_windows(side, fi, entry_price, entry_ts):
    """Walk ticks for max 30s, record per-checkpoint: max P&L, did go positive at any point."""
    end_ts = entry_ts + (max(CHECKPOINTS_SEC) + 1) * 1000
    i1 = int(np.searchsorted(ts_arr, end_ts, side="right"))
    cp_data = {sec: {"went_positive": False, "max_pnl": -1e9, "min_pnl": 1e9, "first_pos_age_s": None}
               for sec in CHECKPOINTS_SEC}
    for k in range(fi + 1, i1):
        elapsed = (ts_arr[k] - entry_ts) / 1000.0
        if side == "buy":
            cur_pnl = (bids_arr[k] - entry_price) * CONTRACT_SIZE * LOTS
        else:
            cur_pnl = (entry_price - asks_arr[k]) * CONTRACT_SIZE * LOTS
        for sec in CHECKPOINTS_SEC:
            if elapsed > sec: continue
            d = cp_data[sec]
            if cur_pnl > d["max_pnl"]: d["max_pnl"] = cur_pnl
            if cur_pnl < d["min_pnl"]: d["min_pnl"] = cur_pnl
            if cur_pnl > 0 and not d["went_positive"]:
                d["went_positive"] = True
                d["first_pos_age_s"] = round(elapsed, 2)
    return cp_data


print(f"\nScanning {len(m1):,} M1 bars for strict-v2 UHV signals...", flush=True)
records = []
last_entry = 0
for idx in range(UHV_LOOKBACK + RECENT_AVG_BARS + 5, len(m1)):
    bar = m1[idx]
    if SKIP_SYDNEY and bar["hour"] < 6: continue
    if int(bar["ts_end_ms"]) - last_entry < MIN_SPACING_SEC * 1000: continue
    sig = detect(idx)
    if not sig: continue
    f = fill(sig)
    if not f: continue
    fi, fp, ft = f
    cps = measure_positive_windows(sig["side"], fi, fp, ft)
    rec = {"date": sig["date"], "hour": sig["hour"], "dow": sig["dow"], "side": sig["side"],
           "entry_price": round(fp, 2), "entry_ts": ft}
    for sec in CHECKPOINTS_SEC:
        d = cps[sec]
        rec[f"pos_{sec}s"] = d["went_positive"]
        rec[f"max_pnl_{sec}s"] = round(d["max_pnl"], 2) if d["max_pnl"] > -1e8 else None
        rec[f"min_pnl_{sec}s"] = round(d["min_pnl"], 2) if d["min_pnl"] < 1e8 else None
    rec["first_pos_age_s"] = cps[max(CHECKPOINTS_SEC)]["first_pos_age_s"]
    records.append(rec)
    last_entry = ft

n = len(records)
print(f"  Total signals (strict v2 entry): {n}", flush=True)

if n == 0:
    print("  No signals — filter too strict")
else:
    print(f"\n=== IMMEDIATE-POSITIVE BEHAVIOUR ===", flush=True)
    print(f"  At each checkpoint, % of signals where price went POSITIVE at any point ≤ that time:", flush=True)
    print(f"  {'sec':>5}  {'% positive':>11}  {'avg max P&L':>13}  {'avg min P&L':>13}", flush=True)
    for sec in CHECKPOINTS_SEC:
        positives = [r for r in records if r[f"pos_{sec}s"]]
        pct = len(positives) / n * 100
        max_avg = np.mean([r[f"max_pnl_{sec}s"] for r in records if r[f"max_pnl_{sec}s"] is not None])
        min_avg = np.mean([r[f"min_pnl_{sec}s"] for r in records if r[f"min_pnl_{sec}s"] is not None])
        print(f"  ≤{sec:>3}s  {pct:>9.1f}%  ${max_avg:>+11.2f}  ${min_avg:>+11.2f}", flush=True)

    # Distribution of "first_pos_age_s" — how fast does it normally go positive?
    fp_ages = [r["first_pos_age_s"] for r in records if r["first_pos_age_s"] is not None]
    if fp_ages:
        print(f"\n  Of {len(fp_ages)} trades that went positive within 30s:", flush=True)
        print(f"    median time to first positive: {np.median(fp_ages):.2f}s", flush=True)
        print(f"    mean   time to first positive: {np.mean(fp_ages):.2f}s", flush=True)
        print(f"    p75    time to first positive: {np.percentile(fp_ages, 75):.2f}s", flush=True)
        print(f"    p90    time to first positive: {np.percentile(fp_ages, 90):.2f}s", flush=True)
    print(f"\n  Of {n - len(fp_ages)} trades that NEVER went positive in 30s:", flush=True)
    never_positive = [r for r in records if r["first_pos_age_s"] is None]
    if never_positive:
        worst = sorted(never_positive, key=lambda r: r["min_pnl_30s"] or 0)[:5]
        print(f"  Worst 5 (deepest min P&L within 30s):", flush=True)
        for r in worst:
            print(f"    {r['date']} {r['hour']:>2}h {r['side']:>4} entry=${r['entry_price']}  min_pnl_30s=${r['min_pnl_30s']}", flush=True)

    # Per-hour positivity
    print(f"\n=== PER-HOUR % positive within 5s ===", flush=True)
    print(f"  {'hr':>4} {'n':>4} {'%pos5s':>7} {'%pos10s':>8} {'%pos30s':>8}", flush=True)
    by_hr = {}
    for r in records:
        by_hr.setdefault(r["hour"], []).append(r)
    for hr in sorted(by_hr):
        rs = by_hr[hr]
        p5 = sum(1 for r in rs if r["pos_5s"]) / len(rs) * 100
        p10 = sum(1 for r in rs if r["pos_10s"]) / len(rs) * 100
        p30 = sum(1 for r in rs if r["pos_30s"]) / len(rs) * 100
        print(f"  {hr:>4} {len(rs):>4} {p5:>6.0f}% {p10:>7.0f}% {p30:>7.0f}%", flush=True)

# Save
OUT_J.write_text(json.dumps({
    "started": datetime.now(timezone.utc).isoformat(),
    "n_signals": n,
    "rules": "strict v2: vol_ratio≤0.40, body≥0.80, UHV vol≥2× recent, wick≤25%, sydney skip",
    "checkpoints_sec": CHECKPOINTS_SEC,
    "summary_pct_positive": {sec: round(sum(1 for r in records if r[f"pos_{sec}s"]) / max(1, n) * 100, 1)
                              for sec in CHECKPOINTS_SEC},
    "all_records_count": n,
}, indent=2, default=str))

# Save per-trade CSV for inspection
if n > 0:
    pd.DataFrame(records).to_csv(OUT_J.parent / "_zee_immediate_positive_trades.csv", index=False)
print(f"\n[DONE] -> {OUT_J}", flush=True)
