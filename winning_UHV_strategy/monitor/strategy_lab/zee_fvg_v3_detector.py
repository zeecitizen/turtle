"""ITERATION 3 — Lesson 10 refinement: multi-timeframe FVG + liquidity-sweep engulfing.

THE ACTUAL ZEE STRATEGY (per Lesson 10):
  1. Mark FVGs on HIGHER timeframe (5m, 15m, 30m, 1h)
  2. Switch to LOWER timeframe (1m) for execution
  3. Wait for price to come to FVG zone on M1
  4. ENTRY TRIGGER: Liquidity-sweep engulfing
     - Last red candle in retracement (any normal volume)
     - Next green candle WICKS BELOW red's low (sweep)
     - Same green candle CLOSES BACK INSIDE red's body
     - Green volume > Red volume (institutional buying)
     - Green's upper wick small (no rejection)
  5. Entry at green close
  6. SL below green's lower wick
  7. TP at structural high (prev swing)

For SELL (downtrend): mirror.

Multi-TF FVG approach: detect FVG on M5, check M1 entry within FVG zone.
"""
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_fvg_v3_iter3.json")

# ── Build M1 + M5 bars Feb 10-12 ───────────────────────────────────
print("[1/8] Loading parquet ticks Feb 10-12...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
lo = int(datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc).timestamp() * 1000)
hi = int(datetime(2026, 2, 12,  2, 0, tzinfo=timezone.utc).timestamp() * 1000)
df = df[(df["time_msc"] >= lo) & (df["time_msc"] <= hi)].reset_index(drop=True)

def build_bars(df, period_ms, period_label):
    df = df.copy()
    df["period"] = (df["time_msc"] // period_ms).astype(np.int64)
    g = df.groupby("period", sort=True).agg(
        o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
        v=("bid","count"), ts=("time_msc","last"),
    ).reset_index().drop(columns="period")
    g["dt"] = pd.to_datetime(g["ts"], unit="ms", utc=True)
    g["utc"] = g["dt"].dt.strftime("%Y-%m-%d %H:%M")
    return g.to_dict("records")

bars_m1 = build_bars(df, 60_000, "M1")
bars_m5 = build_bars(df, 5 * 60_000, "M5")
print(f"  M1 bars: {len(bars_m1):,}  M5 bars: {len(bars_m5):,}", flush=True)

# ── PARAMS (iter 3) ────────────────────────────────────────────────
FVG_TF = "M5"                # detect FVGs on M5
FVG_MAX_AGE_BARS_M5 = 30     # FVG must mitigate within 30 M5 bars = 2.5h
SWEEP_MIN_WICK_PTS = 0.05    # min wick poke below red's low (pts) — at least small sweep
ENGULF_VOL_RATIO_MIN = 1.1   # green vol >= 1.1x red vol (institutional)
ENGULF_BODY_INSIDE = 0.0     # green close must be inside red body (close > red.low)
ENGULF_UPPER_WICK_MAX = 0.30 # green's upper wick <= 30% of green range
RED_MIN_RANGE_PTS = 0.1      # red candle must have some range (not doji)
MAX_TRIGGER_PER_FVG = 5      # don't allow too many triggers per FVG

# ── STEP 1: Detect FVGs on M5 ──────────────────────────────────────
print("[2/8] Detecting FVGs on M5 bars...", flush=True)
fvgs = []
for i in range(2, len(bars_m5)):
    c0, c2 = bars_m5[i-2], bars_m5[i]
    if c0["h"] < c2["l"]:
        fvgs.append({"side": "buy", "hi": c2["l"], "lo": c0["h"],
                     "formed_ts": c2["ts"], "utc": c2["utc"], "tf": "M5"})
    elif c0["l"] > c2["h"]:
        fvgs.append({"side": "sell", "hi": c0["l"], "lo": c2["h"],
                     "formed_ts": c2["ts"], "utc": c2["utc"], "tf": "M5"})
print(f"  M5 FVGs: {len(fvgs)}", flush=True)

# ── HELPERS ────────────────────────────────────────────────────────
def is_red(b): return b["c"] < b["o"]
def is_green(b): return b["c"] > b["o"]

# ── STEP 2: For each M1 bar, check if it falls in any unmitigated FVG zone ──
print("[3/8] Scanning M1 bars for sweep-engulfing inside M5 FVG zones...", flush=True)
signals = []
seen = set()
# For efficiency: sort FVGs by formed_ts
fvgs_sorted = sorted(fvgs, key=lambda f: f["formed_ts"])

# Walk M1 bars from index 1 onwards
for j in range(1, len(bars_m1)):
    cur = bars_m1[j]
    prev = bars_m1[j-1]
    # Find FVGs active at this point (formed before, within age window, price touches zone)
    cur_ts = cur["ts"]
    active_fvgs_buy = []
    active_fvgs_sell = []
    for f in fvgs_sorted:
        if f["formed_ts"] >= cur_ts: break
        age_min = (cur_ts - f["formed_ts"]) / 60000
        if age_min > FVG_MAX_AGE_BARS_M5 * 5: continue  # M5 bars = 5 min each
        # Does cur bar's range touch FVG zone?
        if not ((cur["l"] <= f["hi"]) and (cur["h"] >= f["lo"])):
            continue
        if f["side"] == "buy":
            active_fvgs_buy.append(f)
        else:
            active_fvgs_sell.append(f)
    # ── BUY pattern: prev=red, cur=green liquidity-sweep engulfing
    if active_fvgs_buy and is_red(prev) and is_green(cur):
        red_range = prev["h"] - prev["l"]
        if red_range < RED_MIN_RANGE_PTS: continue
        # Sweep: cur low < prev low - SWEEP_MIN_WICK_PTS
        if cur["l"] >= prev["l"] - SWEEP_MIN_WICK_PTS: continue
        # Close back inside: cur close > prev low
        if cur["c"] <= prev["l"]: continue
        # Volume: green > red * ratio
        if cur["v"] < ENGULF_VOL_RATIO_MIN * prev["v"]: continue
        # Upper wick small
        cur_range = cur["h"] - cur["l"]
        if cur_range > 0:
            upper_wick = cur["h"] - max(cur["c"], cur["o"])
            if upper_wick / cur_range > ENGULF_UPPER_WICK_MAX: continue
        utc = cur["utc"]
        if (utc, "buy") in seen: continue
        seen.add((utc, "buy"))
        signals.append({
            "pattern": "liq_sweep_engulf", "utc": utc, "side": "buy",
            "entry_close": cur["c"],
            "red_utc": prev["utc"], "red_low": prev["l"], "red_vol": prev["v"],
            "green_vol": cur["v"], "green_low_sweep": prev["l"] - cur["l"],
            "fvg_count": len(active_fvgs_buy),
            "fvg_first": active_fvgs_buy[0]["utc"],
        })
    # ── SELL pattern: prev=green, cur=red liq-sweep engulfing
    if active_fvgs_sell and is_green(prev) and is_red(cur):
        green_range = prev["h"] - prev["l"]
        if green_range < RED_MIN_RANGE_PTS: continue
        if cur["h"] <= prev["h"] + SWEEP_MIN_WICK_PTS: continue
        if cur["c"] >= prev["h"]: continue
        if cur["v"] < ENGULF_VOL_RATIO_MIN * prev["v"]: continue
        cur_range = cur["h"] - cur["l"]
        if cur_range > 0:
            lower_wick = min(cur["c"], cur["o"]) - cur["l"]
            if lower_wick / cur_range > ENGULF_UPPER_WICK_MAX: continue
        utc = cur["utc"]
        if (utc, "sell") in seen: continue
        seen.add((utc, "sell"))
        signals.append({
            "pattern": "liq_sweep_engulf", "utc": utc, "side": "sell",
            "entry_close": cur["c"],
            "green_utc": prev["utc"], "green_high": prev["h"], "green_vol": prev["v"],
            "red_vol": cur["v"], "red_high_sweep": cur["h"] - prev["h"],
            "fvg_count": len(active_fvgs_sell),
            "fvg_first": active_fvgs_sell[0]["utc"],
        })

print(f"[4/8] Signals: {len(signals)}", flush=True)
for s in signals[:60]:
    print(f"  {s['utc']} {s['side']:>4} entry={s['entry_close']:.2f}  red_vol={s.get('red_vol','-')}/green_vol={s.get('green_vol','-')}  FVGs={s['fvg_count']}", flush=True)

# ── STEP 3: Match against Zee's 24 setups ──────────────────────────
print("[5/8] Matching against Zee's Feb 11 setups...", flush=True)
ZEE_SETUPS = [
    ("2026-02-10 23:32","buy"), ("2026-02-10 23:59","buy"),
    ("2026-02-11 00:09","sell"),("2026-02-11 00:29","buy"),
    ("2026-02-11 14:49","buy"), ("2026-02-11 14:52","buy"),
    ("2026-02-11 14:54","buy"), ("2026-02-11 14:58","buy"),
    ("2026-02-11 15:02","buy"), ("2026-02-11 15:36","buy"),
    ("2026-02-11 15:37","buy"), ("2026-02-11 15:49","buy"),
    ("2026-02-11 16:24","buy"), ("2026-02-11 16:41","buy"),
    ("2026-02-11 17:08","sell"),("2026-02-11 17:11","sell"),
    ("2026-02-11 17:20","sell"),("2026-02-11 17:26","sell"),
    ("2026-02-11 17:29","buy"), ("2026-02-11 17:32","buy"),
    ("2026-02-11 17:36","buy"), ("2026-02-11 17:38","buy"),
    ("2026-02-11 17:41","sell"),("2026-02-11 17:42","sell"),
]
matches = []
for zm, zs in ZEE_SETUPS:
    zm_dt = datetime.fromisoformat(zm + "+00:00")
    for s in signals:
        sm_dt = datetime.fromisoformat(s["utc"] + "+00:00")
        delta = abs((sm_dt - zm_dt).total_seconds() / 60)
        if delta <= 2 and s["side"] == zs:
            matches.append({"zee": zm, "detected": s["utc"], "side": zs, "delta_min": delta})
            break

print(f"  Zee setups: {len(ZEE_SETUPS)}")
print(f"  Detected:   {len(signals)}")
print(f"  MATCHES:    {len(matches)}/{len(ZEE_SETUPS)} = {len(matches)/len(ZEE_SETUPS)*100:.1f}%")
for m in matches:
    print(f"    {m['zee']} → {m['detected']} ({m['side']}, Δ={m['delta_min']:.1f}m)")

# ── STEP 4: Save ───────────────────────────────────────────────────
OUT_J.write_text(json.dumps({
    "iteration": 3,
    "params": {
        "FVG_TF": FVG_TF, "FVG_MAX_AGE_BARS_M5": FVG_MAX_AGE_BARS_M5,
        "SWEEP_MIN_WICK_PTS": SWEEP_MIN_WICK_PTS,
        "ENGULF_VOL_RATIO_MIN": ENGULF_VOL_RATIO_MIN,
        "ENGULF_UPPER_WICK_MAX": ENGULF_UPPER_WICK_MAX,
        "RED_MIN_RANGE_PTS": RED_MIN_RANGE_PTS,
    },
    "fvgs_m5_total": len(fvgs),
    "signals_count": len(signals),
    "zee_setups": len(ZEE_SETUPS),
    "matches_count": len(matches),
    "matches": matches,
    "match_rate_pct": round(len(matches) / len(ZEE_SETUPS) * 100, 1),
    "signals": signals,
    "ts": datetime.now(timezone.utc).isoformat(),
}, indent=2, default=str))
print(f"[6/8] saved -> {OUT_J}", flush=True)
print("[7/8] DONE", flush=True)
