"""ITERATION 1 — Zee's actual strategy from his Loom course Lessons 1-4.

Pattern (his own words):
  1. Identify FVG = gap between candle[0].high and candle[2].low (buy FVG)
     OR candle[0].low and candle[2].high (sell FVG)
  2. Wait for price to return into FVG ("mitigation")
  3. Inside mitigation context, find UHV candle (highest volume in last N bars while in/around FVG)
  4. Draw line above UHV.high (for buy) / below UHV.low (for sell)
  5. Wait for momentum candle (big body, small wicks, larger than recent bars)
     with LOW VOLUME (less than UHV) that BREAKS the line
  6. ENTRY: at breakout candle close
  7. SL: below FVG-forming candle low (buy) / above FVG-forming candle high (sell)
  8. TP: 1:1 RR from entry

Goal: overlap detected signals with Zee's actual 24 setup minutes on Feb 11.
"""
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_fvg_v1_iter1.json")

# Build 1-minute bars from parquet ticks, Feb 10 23:00 - Feb 12 02:00 UTC
print("[1/6] Loading parquet ticks for Feb 10-12...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
lo = int(datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc).timestamp() * 1000)
hi = int(datetime(2026, 2, 12,  2, 0, tzinfo=timezone.utc).timestamp() * 1000)
df = df[(df["time_msc"] >= lo) & (df["time_msc"] <= hi)].reset_index(drop=True)
print(f"  Ticks: {len(df):,}", flush=True)

df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1 = df.groupby("m1", sort=True).agg(
    o=("bid", "first"), h=("bid", "max"), l=("bid", "min"), c=("bid", "last"),
    v=("bid", "count"), ts=("time_msc", "last"),
).reset_index().drop(columns="m1")
m1["dt"] = pd.to_datetime(m1["ts"], unit="ms", utc=True)
m1["utc"] = m1["dt"].dt.strftime("%Y-%m-%d %H:%M")
bars = m1.to_dict("records")
print(f"  M1 bars: {len(bars):,}", flush=True)

# ── ITERATION 1 PARAMETERS ────────────────────────────────────────
UHV_LOOKBACK = 20            # how far back to find UHV
UHV_MIN_VOL_MULT = 1.5       # UHV vol must be >= 1.5× average recent
FVG_MAX_AGE_BARS = 60        # FVG must be mitigated within 60m (1hr lookback)
MITIGATION_TOLERANCE = 0.0   # exact touch
MOMENTUM_BODY_MIN = 0.50     # breakout candle body% >= 0.50
MOMENTUM_VOL_MAX_RATIO = 0.80  # breakout vol < 0.80 of UHV vol
BREAKOUT_MAX_LOOKBACK = 5    # how many bars after UHV to allow breakout

# ── STEP 1: Find all FVGs in the bar series ────────────────────────
print("[2/6] Detecting FVGs (3-bar gaps)...", flush=True)
fvgs = []  # each: {start_idx, side, hi, lo, forming_idx (=start_idx)}
for i in range(2, len(bars)):
    c0, c1, c2 = bars[i-2], bars[i-1], bars[i]
    # Buy FVG: c0.high < c2.low — gap between them. c1 sits inside.
    if c0["h"] < c2["l"]:
        fvgs.append({"forming_idx": i, "side": "buy", "hi": c2["l"], "lo": c0["h"],
                     "ts": c2["ts"], "utc": c2["utc"]})
    # Sell FVG: c0.low > c2.high
    elif c0["l"] > c2["h"]:
        fvgs.append({"forming_idx": i, "side": "sell", "hi": c0["l"], "lo": c2["h"],
                     "ts": c2["ts"], "utc": c2["utc"]})
print(f"  FVGs found: {len(fvgs)}", flush=True)

# ── STEP 2: For each FVG, find mitigation event ────────────────────
print("[3/6] Tracking FVG mitigations...", flush=True)
signals = []
for fvg in fvgs:
    fi = fvg["forming_idx"]
    side = fvg["side"]
    # Search forward for price returning into the FVG zone
    for j in range(fi + 1, min(fi + 1 + FVG_MAX_AGE_BARS, len(bars))):
        b = bars[j]
        # Mitigation: candle's range overlaps with FVG zone
        touches = (b["l"] <= fvg["hi"]) and (b["h"] >= fvg["lo"])
        if not touches:
            continue
        # ── STEP 3: Inside mitigation, find UHV candle ─────────────
        # Look at bars in [max(0, j-3), j+3] for highest volume
        # But also require it's larger than recent average
        win_lo = max(0, j - 3)
        win_hi = min(len(bars), j + 4)
        uhv_idx = max(range(win_lo, win_hi), key=lambda k: bars[k]["v"])
        uhv = bars[uhv_idx]
        # Recent avg vol
        ref_lo = max(0, uhv_idx - UHV_LOOKBACK)
        ref_vols = [bars[k]["v"] for k in range(ref_lo, uhv_idx) if k != uhv_idx]
        if not ref_vols:
            continue
        avg_v = sum(ref_vols) / len(ref_vols)
        if uhv["v"] < UHV_MIN_VOL_MULT * avg_v:
            continue
        # UHV must be opposite color to trade direction (red for buy retracement, green for sell rally)
        is_red = uhv["c"] < uhv["o"]
        is_green = uhv["c"] > uhv["o"]
        if side == "buy" and not is_red:
            continue
        if side == "sell" and not is_green:
            continue
        # ── STEP 4: Wait for momentum + low-volume breakout candle ─
        breakout_line = uhv["h"] if side == "buy" else uhv["l"]
        found_breakout = False
        for k in range(uhv_idx + 1, min(uhv_idx + 1 + BREAKOUT_MAX_LOOKBACK, len(bars))):
            cb = bars[k]
            rng = cb["h"] - cb["l"]
            if rng <= 0:
                continue
            body = abs(cb["c"] - cb["o"])
            body_pct = body / rng
            if body_pct < MOMENTUM_BODY_MIN:
                continue
            # Direction match
            cb_is_green = cb["c"] > cb["o"]
            cb_is_red = cb["c"] < cb["o"]
            if side == "buy" and not cb_is_green:
                continue
            if side == "sell" and not cb_is_red:
                continue
            # Volume check
            if cb["v"] >= MOMENTUM_VOL_MAX_RATIO * uhv["v"]:
                continue
            # Breakout check
            if side == "buy" and cb["c"] <= breakout_line:
                continue
            if side == "sell" and cb["c"] >= breakout_line:
                continue
            # Signal!
            signals.append({
                "utc": cb["utc"], "side": side, "entry_close": cb["c"],
                "fvg_utc": fvg["utc"], "fvg_lo": fvg["lo"], "fvg_hi": fvg["hi"],
                "uhv_utc": uhv["utc"], "uhv_v": uhv["v"],
                "breakout_v": cb["v"], "breakout_body_pct": round(body_pct, 2),
                "ts": cb["ts"],
            })
            found_breakout = True
            break
        if found_breakout:
            break

print(f"[4/6] Signals detected: {len(signals)}", flush=True)
for s in signals[:30]:
    print(f"  {s['utc']} {s['side']} entry={s['entry_close']:.2f} FVG@{s['fvg_utc']} UHV@{s['uhv_utc']} body={s['breakout_body_pct']}", flush=True)

# ── STEP 5: Cross-check against Zee's 24 actual setup minutes ──────
print("[5/6] Cross-check with Zee's Feb 11 actual setups...", flush=True)
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
zee_min_set = {m: s for m, s in ZEE_SETUPS}
# For overlap: consider a signal as matching if its minute is within ±2 min of a Zee setup AND same side
sig_min = [(s["utc"], s["side"]) for s in signals]
matches = []
for zm, zs in ZEE_SETUPS:
    zm_dt = datetime.fromisoformat(zm + "+00:00")
    for s in signals:
        sm_dt = datetime.fromisoformat(s["utc"] + "+00:00")
        delta_min = abs((sm_dt - zm_dt).total_seconds() / 60)
        if delta_min <= 2 and s["side"] == zs:
            matches.append({"zee": zm, "detected": s["utc"], "side": zs, "delta_min": delta_min})
            break

print(f"  Zee setups: {len(ZEE_SETUPS)}")
print(f"  Detected signals: {len(signals)}")
print(f"  MATCHES (±2 min same-side): {len(matches)}/{len(ZEE_SETUPS)} = {len(matches)/len(ZEE_SETUPS)*100:.1f}%")
for m in matches:
    print(f"    {m['zee']} matched by detected @ {m['detected']} ({m['side']}, delta={m['delta_min']:.1f}m)")

# ── STEP 6: Save results ───────────────────────────────────────────
OUT_J.write_text(json.dumps({
    "iteration": 1,
    "params": {
        "UHV_LOOKBACK": UHV_LOOKBACK, "UHV_MIN_VOL_MULT": UHV_MIN_VOL_MULT,
        "FVG_MAX_AGE_BARS": FVG_MAX_AGE_BARS,
        "MOMENTUM_BODY_MIN": MOMENTUM_BODY_MIN,
        "MOMENTUM_VOL_MAX_RATIO": MOMENTUM_VOL_MAX_RATIO,
        "BREAKOUT_MAX_LOOKBACK": BREAKOUT_MAX_LOOKBACK,
    },
    "fvgs_total": len(fvgs),
    "signals": signals,
    "zee_setups": len(ZEE_SETUPS),
    "matches": matches,
    "match_rate_pct": round(len(matches) / len(ZEE_SETUPS) * 100, 1),
    "ts": datetime.now(timezone.utc).isoformat(),
}, indent=2, default=str))
print(f"[6/6] saved -> {OUT_J}", flush=True)
