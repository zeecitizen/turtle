"""ITERATION 2 — Zee's strategy from Lessons 1-9.

Pattern detection (BUY only — gold mostly uptrend per Lesson 7):

  SETUP CONDITIONS:
  1. FVG was formed earlier (3-bar gap: bar[i-2].h < bar[i].l)
  2. Price has come back to MITIGATE (touch) the FVG zone
  3. While mitigating, retracement candles (red) are forming
  4. Inside retracement, look for either ENTRY PATTERN A or B:

  ENTRY PATTERN A — NS-Breakout (Lessons 6-7):
    - CAB: a big-volume RED candle (vol >= 1.5x recent avg)
    - NS:  a small DEAD-volume RED candle AFTER CAB (vol <= 0.5x of prev two,
           body small, range small)
    - Sweep: next candle's WICK pokes below NS.low (body doesn't close below)
    - Break: same/next candle BODY closes above NS.high
    - Entry: at close of break candle
    - SL: below NS.low (or below sweep wick)

  ENTRY PATTERN B — Engulfing (Lesson 8):
    - Last RED retracement candle gets ENGULFED by a GREEN momentum candle
    - Green.body covers Red.body (open<=red_low, close>=red_high — at least body)
    - Green volume < Red volume (low-volume engulfing — institutional absorption)
    - Green wicks small (momentum candle, not weak)
    - Entry: at close of engulfing candle
    - SL: below both candles' low

Goal: match Zee's 24 Feb 11 setups.
"""
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_zee_fvg_v2_iter2.json")

# ── Build M1 bars Feb 10 22:00 → Feb 12 02:00 UTC ─────────────────
print("[1/7] Loading parquet ticks Feb 10-12...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
lo = int(datetime(2026, 2, 10, 22, 0, tzinfo=timezone.utc).timestamp() * 1000)
hi = int(datetime(2026, 2, 12,  2, 0, tzinfo=timezone.utc).timestamp() * 1000)
df = df[(df["time_msc"] >= lo) & (df["time_msc"] <= hi)].reset_index(drop=True)
df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1 = df.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts=("time_msc","last"),
).reset_index().drop(columns="m1")
m1["dt"] = pd.to_datetime(m1["ts"], unit="ms", utc=True)
m1["utc"] = m1["dt"].dt.strftime("%Y-%m-%d %H:%M")
bars = m1.to_dict("records")
print(f"  M1 bars: {len(bars):,}", flush=True)

# ── PARAMS (iter 2) ────────────────────────────────────────────────
FVG_MAX_AGE_BARS = 90        # FVG must mitigate within 90 minutes
CAB_VOL_MULT_MIN = 1.5       # CAB vol >= 1.5x recent 20-bar avg
CAB_BODY_PCT_MIN = 0.45      # CAB body >= 45% of range (real candle, not doji)
NS_VOL_MAX_RATIO = 0.50      # NS vol <= 0.50 of prev 2 candles avg
NS_RANGE_MAX_PTS = 1.5       # NS range small (< $1.5 in xauusd points)
NS_MAX_BARS_AFTER_CAB = 5    # NS must appear within 5 bars after CAB
SWEEP_MAX_BARS_AFTER_NS = 3  # sweep+break within 3 bars after NS
ENGULF_BODY_COVER_MIN = 0.95  # engulfing body covers >= 95% of prev body
ENGULF_VOL_MAX_RATIO = 0.80  # engulfing vol < 0.80 of engulfed bar vol
MOMENTUM_BODY_MIN = 0.55     # momentum candle body >= 55%
MOMENTUM_WICK_MAX = 0.35     # momentum candle wicks <= 35% combined

# ── STEP 1: Find FVGs ──────────────────────────────────────────────
print("[2/7] Detecting FVGs (3-bar gaps)...", flush=True)
fvgs = []
for i in range(2, len(bars)):
    c0, c2 = bars[i-2], bars[i]
    if c0["h"] < c2["l"]:
        fvgs.append({"forming_idx": i, "side": "buy", "hi": c2["l"], "lo": c0["h"],
                     "utc": c2["utc"]})
    elif c0["l"] > c2["h"]:
        fvgs.append({"forming_idx": i, "side": "sell", "hi": c0["l"], "lo": c2["h"],
                     "utc": c2["utc"]})
print(f"  FVGs: {len(fvgs)}", flush=True)

# ── HELPERS ────────────────────────────────────────────────────────
def is_red(b): return b["c"] < b["o"]
def is_green(b): return b["c"] > b["o"]
def body_pct(b):
    r = b["h"] - b["l"]
    return abs(b["c"] - b["o"]) / r if r > 0 else 0
def wick_pct(b):
    r = b["h"] - b["l"]
    if r <= 0: return 1
    upper = b["h"] - max(b["c"], b["o"])
    lower = min(b["c"], b["o"]) - b["l"]
    return (upper + lower) / r
def avg_vol(idx, lookback):
    lo_i = max(0, idx - lookback)
    vs = [bars[k]["v"] for k in range(lo_i, idx) if k != idx]
    return sum(vs) / len(vs) if vs else 0
def body_covers(eng, prev, min_cover=ENGULF_BODY_COVER_MIN):
    """Does eng candle's body cover prev candle's body (>= min_cover fraction)?"""
    eng_lo = min(eng["c"], eng["o"]); eng_hi = max(eng["c"], eng["o"])
    prev_lo = min(prev["c"], prev["o"]); prev_hi = max(prev["c"], prev["o"])
    overlap_lo = max(eng_lo, prev_lo); overlap_hi = min(eng_hi, prev_hi)
    overlap = max(0, overlap_hi - overlap_lo)
    prev_body = prev_hi - prev_lo
    return overlap >= min_cover * prev_body and prev_body > 0

# ── STEP 2: For each FVG, scan forward for mitigation + entry trigger ─
print("[3/7] Scanning for mitigation + entry triggers...", flush=True)
signals = []
seen_minutes = set()  # dedupe by minute
for fvg in fvgs:
    fi = fvg["forming_idx"]
    side = fvg["side"]
    for j in range(fi + 1, min(fi + 1 + FVG_MAX_AGE_BARS, len(bars))):
        b = bars[j]
        if not ((b["l"] <= fvg["hi"]) and (b["h"] >= fvg["lo"])):
            continue
        # ── Inside mitigation context ──
        # PATTERN A: NS-Breakout
        # Look back from j to find CAB (big-vol opposite-color candle in retracement)
        cab_idx = None
        for ci in range(max(0, j - 10), j + 3):
            cb = bars[ci]
            if side == "buy" and not is_red(cb): continue
            if side == "sell" and not is_green(cb): continue
            avg_v = avg_vol(ci, 20)
            if avg_v == 0 or cb["v"] < CAB_VOL_MULT_MIN * avg_v: continue
            if body_pct(cb) < CAB_BODY_PCT_MIN: continue
            cab_idx = ci
            break
        if cab_idx is not None:
            # Find NS after CAB
            for ns_i in range(cab_idx + 1, min(cab_idx + 1 + NS_MAX_BARS_AFTER_CAB, len(bars))):
                nb = bars[ns_i]
                if side == "buy" and not is_red(nb): continue
                if side == "sell" and not is_green(nb): continue
                # NS conditions
                prev_v = (bars[ns_i-1]["v"] + bars[ns_i-2]["v"]) / 2 if ns_i >= 2 else 0
                if prev_v == 0 or nb["v"] > NS_VOL_MAX_RATIO * prev_v: continue
                if (nb["h"] - nb["l"]) > NS_RANGE_MAX_PTS: continue
                # Find sweep + break
                for kk in range(ns_i + 1, min(ns_i + 1 + SWEEP_MAX_BARS_AFTER_NS, len(bars))):
                    sb = bars[kk]
                    # Sweep: wick pokes opposite direction (for buy: low below NS.low, body close above NS.low)
                    if side == "buy":
                        swept = sb["l"] < nb["l"] and sb["c"] > nb["l"]
                        broke = sb["c"] > nb["h"]
                    else:
                        swept = sb["h"] > nb["h"] and sb["c"] < nb["h"]
                        broke = sb["c"] < nb["l"]
                    if swept and broke:
                        # momentum check
                        if body_pct(sb) < MOMENTUM_BODY_MIN: continue
                        utc = sb["utc"]
                        if (utc, side) in seen_minutes: continue
                        seen_minutes.add((utc, side))
                        signals.append({
                            "pattern": "NS_breakout", "utc": utc, "side": side,
                            "entry_close": sb["c"], "fvg_utc": fvg["utc"],
                            "cab_utc": bars[cab_idx]["utc"],
                            "ns_utc": nb["utc"], "ns_low": nb["l"], "ns_high": nb["h"],
                        })
                        break
        # PATTERN B: Engulfing
        # Check current bar j against bar j-1: did current engulf prev opposite-color?
        if j >= 1:
            cur = bars[j]; prev = bars[j-1]
            if side == "buy" and is_green(cur) and is_red(prev):
                if body_covers(cur, prev) and cur["v"] < ENGULF_VOL_MAX_RATIO * prev["v"]:
                    if body_pct(cur) >= MOMENTUM_BODY_MIN and wick_pct(cur) <= MOMENTUM_WICK_MAX:
                        utc = cur["utc"]
                        if (utc, side) not in seen_minutes:
                            seen_minutes.add((utc, side))
                            signals.append({
                                "pattern": "engulfing", "utc": utc, "side": side,
                                "entry_close": cur["c"], "fvg_utc": fvg["utc"],
                                "engulfed_utc": prev["utc"],
                            })
            elif side == "sell" and is_red(cur) and is_green(prev):
                if body_covers(cur, prev) and cur["v"] < ENGULF_VOL_MAX_RATIO * prev["v"]:
                    if body_pct(cur) >= MOMENTUM_BODY_MIN and wick_pct(cur) <= MOMENTUM_WICK_MAX:
                        utc = cur["utc"]
                        if (utc, side) not in seen_minutes:
                            seen_minutes.add((utc, side))
                            signals.append({
                                "pattern": "engulfing", "utc": utc, "side": side,
                                "entry_close": cur["c"], "fvg_utc": fvg["utc"],
                                "engulfed_utc": prev["utc"],
                            })
        # Don't keep scanning this FVG once we've mitigated
        break

print(f"[4/7] Signals: {len(signals)}  (NS_breakout: {sum(1 for s in signals if s['pattern']=='NS_breakout')}, engulfing: {sum(1 for s in signals if s['pattern']=='engulfing')})", flush=True)
for s in signals[:50]:
    extra = f"CAB@{s.get('cab_utc','-')} NS@{s.get('ns_utc','-')}" if s['pattern']=='NS_breakout' else f"engulfed@{s.get('engulfed_utc','-')}"
    print(f"  {s['utc']} {s['side']:>4} [{s['pattern']:>13}] entry={s['entry_close']:.2f}  FVG@{s['fvg_utc']}  {extra}", flush=True)

# ── STEP 3: Cross-check against Zee's actual setups ────────────────
print("[5/7] Matching against Zee's Feb 11 24 setups...", flush=True)
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
            matches.append({"zee": zm, "detected": s["utc"], "side": zs, "pattern": s["pattern"], "delta_min": delta})
            break

print(f"  Zee setups: {len(ZEE_SETUPS)}")
print(f"  Detected:   {len(signals)}")
print(f"  MATCHES:    {len(matches)}/{len(ZEE_SETUPS)} = {len(matches)/len(ZEE_SETUPS)*100:.1f}%")
for m in matches:
    print(f"    {m['zee']} → {m['detected']} ({m['side']}, {m['pattern']}, Δ={m['delta_min']:.1f}m)")

# ── STEP 4: Save ───────────────────────────────────────────────────
OUT_J.write_text(json.dumps({
    "iteration": 2,
    "params": {
        "FVG_MAX_AGE_BARS": FVG_MAX_AGE_BARS, "CAB_VOL_MULT_MIN": CAB_VOL_MULT_MIN,
        "NS_VOL_MAX_RATIO": NS_VOL_MAX_RATIO, "NS_RANGE_MAX_PTS": NS_RANGE_MAX_PTS,
        "NS_MAX_BARS_AFTER_CAB": NS_MAX_BARS_AFTER_CAB,
        "SWEEP_MAX_BARS_AFTER_NS": SWEEP_MAX_BARS_AFTER_NS,
        "ENGULF_BODY_COVER_MIN": ENGULF_BODY_COVER_MIN,
        "ENGULF_VOL_MAX_RATIO": ENGULF_VOL_MAX_RATIO,
        "MOMENTUM_BODY_MIN": MOMENTUM_BODY_MIN,
        "MOMENTUM_WICK_MAX": MOMENTUM_WICK_MAX,
    },
    "fvgs_total": len(fvgs),
    "signals_count": len(signals),
    "signals_ns": sum(1 for s in signals if s['pattern']=='NS_breakout'),
    "signals_engulf": sum(1 for s in signals if s['pattern']=='engulfing'),
    "zee_setups": len(ZEE_SETUPS),
    "matches_count": len(matches),
    "matches": matches,
    "match_rate_pct": round(len(matches) / len(ZEE_SETUPS) * 100, 1),
    "signals": signals,
    "ts": datetime.now(timezone.utc).isoformat(),
}, indent=2, default=str))
print(f"[6/7] saved -> {OUT_J}", flush=True)
print("[7/7] DONE", flush=True)
