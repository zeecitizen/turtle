"""Original Turtle UHV Breakout — backtest on real Blueberry M1 ticks (last 120 days).

Zee's pattern (from original turtle.pine, cleaned up):
  1. CONFIRMED TREND on M1 — HH+HL for bull, LH+LL for bear (structural trend)
  2. VALID RETRACEMENT — price pulls back against trend (e.g., red bar closes below prior green low)
  3. UHV CANDLE in the retracement — highest tick-volume candle (climax of retracement)
  4. LOW-VOLUME MOMENTUM CANDLE — breakout candle body crosses above UHV high (bull) or below UHV low (bear)
     - Volume must DROP vs UHV (no-supply / no-demand pattern)
     - Strong body (≥60% of candle range)
  5. ENTRY at breakout candle close
  6. SL behind breakout wick + small buffer
  7. TP at R:R multiple (test 2R, 3R, 5R, 7R)
  8. INVALIDATION: close if any subsequent 1-min candle closes back below UHV midpoint

Sweep parameters; report best config + train/test split.
"""
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone
import json

CACHE = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_xauusd_ticks.parquet")
OUT_J = Path(r"C:\Users\zeesh\Documents\GitHub\turtle\monitor\strategy_lab\_original_turtle_uhv_results.json")
LOTS = 0.30; COMMISSION = 7.0 * LOTS; CONTRACT_SIZE = 100; SL_BUFFER = 0.05

print("[LOAD]...", flush=True)
df = pd.read_parquet(CACHE).sort_values("time_msc").reset_index(drop=True)
print(f"[LOAD] {len(df):,} ticks", flush=True)

# Build M1 bars with tick volume
df["m1"] = (df["time_msc"] // 60_000).astype(np.int64)
m1_grp = df.groupby("m1", sort=True).agg(
    o=("bid","first"), h=("bid","max"), l=("bid","min"), c=("bid","last"),
    v=("bid","count"), ts_end_ms=("time_msc","last"),
).reset_index().drop(columns="m1")
m1_grp["dt"] = pd.to_datetime(m1_grp["ts_end_ms"], unit="ms", utc=True)
m1_grp["date"] = m1_grp["dt"].dt.strftime("%Y-%m-%d")
m1 = m1_grp.to_dict("records")
print(f"M1 bars: {len(m1)}", flush=True)

# === STRUCTURAL TREND DETECTION (HH+HL or LH+LL) ===
def detect_swing_trend(idx, swing_lookback=15, swing_strength=3):
    """Identify recent swing highs/lows using fractals. Return 'up' / 'down' / None."""
    if idx < swing_lookback + swing_strength: return None
    # Find swing highs/lows in window [idx-swing_lookback : idx]
    swing_highs = []
    swing_lows = []
    for j in range(idx - swing_lookback, idx - swing_strength):
        is_high = all(m1[j]["h"] >= m1[k]["h"] for k in range(j-swing_strength, j+swing_strength+1))
        is_low = all(m1[j]["l"] <= m1[k]["l"] for k in range(j-swing_strength, j+swing_strength+1))
        if is_high: swing_highs.append((j, m1[j]["h"]))
        if is_low: swing_lows.append((j, m1[j]["l"]))
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        last_hh = swing_highs[-1][1] > swing_highs[-2][1]
        last_hl = swing_lows[-1][1] > swing_lows[-2][1]
        last_lh = swing_highs[-1][1] < swing_highs[-2][1]
        last_ll = swing_lows[-1][1] < swing_lows[-2][1]
        if last_hh and last_hl: return "up"
        if last_lh and last_ll: return "down"
    return None

# === DETECT UHV BREAKOUT SETUP ===
def detect_setup(idx, p):
    """VSA-style UHV reversal: background selling/buying → UHV climax → no-supply/no-demand breakout."""
    if idx < p["retracement_window"] + p["bg_lookback"] + 5: return None
    trend = detect_swing_trend(idx - 1, p["swing_lookback"], p["swing_strength"])

    win_start = max(0, idx - p["retracement_window"])
    uhv_idx = max(range(win_start, idx), key=lambda j: m1[j]["v"])
    uhv = m1[uhv_idx]
    if uhv["v"] == 0: return None
    if uhv_idx >= idx - 1: return None
    if uhv_idx < win_start + p["bg_lookback"]: return None  # need bg_lookback bars before UHV

    uhv_red = uhv["c"] < uhv["o"]
    uhv_green = uhv["c"] > uhv["o"]

    # === BACKGROUND CONTEXT: bars BEFORE the UHV candle ===
    bg_start = max(0, uhv_idx - p["bg_lookback"])
    bg_bars = m1[bg_start:uhv_idx]
    bg_red_count = sum(1 for b in bg_bars if b["c"] < b["o"])
    bg_green_count = sum(1 for b in bg_bars if b["c"] > b["o"])
    bg_majority_red = bg_red_count >= p["bg_min_count"]
    bg_majority_green = bg_green_count >= p["bg_min_count"]

    # === BREAKOUT CANDLE (current bar) ===
    cur = m1[idx]
    cur_body = abs(cur["c"] - cur["o"])
    cur_range = cur["h"] - cur["l"]
    if cur_range < 0.01: return None
    body_pct = cur_body / cur_range
    if body_pct < p["min_body_pct"]: return None

    # === NO-SUPPLY / NO-DEMAND check: breakout candle MUST have low volume vs UHV ===
    # No-supply pattern: bullish low-vol candle breaks UHV high (sellers exhausted)
    # No-demand pattern: bearish low-vol candle breaks UHV low (buyers exhausted)
    vol_ratio = cur["v"] / max(1, uhv["v"])
    if vol_ratio > p["max_vol_ratio"]: return None  # breakout vol must be <= max_vol_ratio of UHV

    # BUY: background selling → UHV red (selling climax) → no-supply green breakout
    if uhv_red and bg_majority_red and cur["c"] > cur["o"] and cur["c"] > uhv["h"]:
        if p["require_structural_trend"] and trend != "up": return None
        prior_high = max(m1[j]["h"] for j in range(bg_start, uhv_idx))
        if uhv["l"] >= prior_high - 0.20: return None
        return {"side": "buy", "entry": cur["c"],
                "uhv_idx": uhv_idx, "uhv_h": uhv["h"], "uhv_l": uhv["l"],
                "uhv_mid": (uhv["h"] + uhv["l"]) / 2,
                "breakout_wick_low": cur["l"],
                "bg_red_count": bg_red_count, "vol_ratio": round(vol_ratio, 2)}
    # SELL: background buying → UHV green (buying climax) → no-demand red breakout
    if uhv_green and bg_majority_green and cur["c"] < cur["o"] and cur["c"] < uhv["l"]:
        if p["require_structural_trend"] and trend != "down": return None
        prior_low = min(m1[j]["l"] for j in range(bg_start, uhv_idx))
        if uhv["h"] <= prior_low + 0.20: return None
        return {"side": "sell", "entry": cur["c"],
                "uhv_idx": uhv_idx, "uhv_h": uhv["h"], "uhv_l": uhv["l"],
                "uhv_mid": (uhv["h"] + uhv["l"]) / 2,
                "breakout_wick_high": cur["h"],
                "bg_green_count": bg_green_count, "vol_ratio": round(vol_ratio, 2)}
    return None

def simulate(idx, sig, p, max_bars=120):
    """Simulate trade: SL behind breakout wick, TP at R:R multiple, invalidation if close back inside UHV mid."""
    side = sig["side"]
    entry = sig["entry"]
    if side == "buy":
        sl = sig["breakout_wick_low"] - SL_BUFFER
    else:
        sl = sig["breakout_wick_high"] + SL_BUFFER
    risk = abs(entry - sl)
    if risk < 0.05: return None
    tp = entry + p["tp_r"] * risk if side == "buy" else entry - p["tp_r"] * risk

    for off in range(1, max_bars + 1):
        i = idx + off
        if i >= len(m1): break
        b = m1[i]
        if side == "buy":
            if b["l"] <= sl: return {"reason": "SL", "pnl": (sl - entry) * 100 * LOTS - COMMISSION, "R": -1, "age": off}
            if b["h"] >= tp: return {"reason": "TP", "pnl": (tp - entry) * 100 * LOTS - COMMISSION, "R": p["tp_r"], "age": off}
            # Invalidation: close back below UHV midpoint
            if p["use_invalidation"] and b["c"] < sig["uhv_mid"]:
                pnl_per_unit = (b["c"] - entry) * 100 * LOTS - COMMISSION
                return {"reason": "INVAL", "pnl": pnl_per_unit, "R": (b["c"] - entry) / risk, "age": off}
        else:
            if b["h"] >= sl: return {"reason": "SL", "pnl": (entry - sl) * 100 * LOTS - COMMISSION, "R": -1, "age": off}
            if b["l"] <= tp: return {"reason": "TP", "pnl": (entry - tp) * 100 * LOTS - COMMISSION, "R": p["tp_r"], "age": off}
            if p["use_invalidation"] and b["c"] > sig["uhv_mid"]:
                pnl_per_unit = (entry - b["c"]) * 100 * LOTS - COMMISSION
                return {"reason": "INVAL", "pnl": pnl_per_unit, "R": (entry - b["c"]) / risk, "age": off}
    last = m1[min(idx + max_bars, len(m1)-1)]
    move = (last["c"] - entry) if side == "buy" else (entry - last["c"])
    return {"reason": "TIME", "pnl": move * 100 * LOTS - COMMISSION, "R": move / risk, "age": max_bars}

def stats(trades):
    if not trades: return {"n": 0}
    arr = np.array([t["pnl"] for t in trades])
    wins = arr[arr > 0]; losses = arr[arr < 0]
    eq = arr.cumsum(); dd = float((np.maximum.accumulate(eq) - eq).max())
    return {"n": len(arr), "wr": round(100*len(wins)/len(arr), 2),
            "pf": round(float(wins.sum()/-losses.sum()), 2) if len(losses) and losses.sum() else None,
            "net": round(float(arr.sum()), 2), "avg": round(float(arr.mean()), 2),
            "max_dd": round(dd, 2),
            "best": round(float(arr.max()), 2), "worst": round(float(arr.min()), 2)}

def backtest(p):
    trades = []
    last_trade_idx = -1000
    for idx in range(p["retracement_window"] + 10, len(m1) - 1):
        if idx - last_trade_idx < p["cooldown_bars"]: continue
        sig = detect_setup(idx, p)
        if not sig: continue
        result = simulate(idx, sig, p)
        if result is None: continue
        result.update({"date": m1[idx]["date"], "side": sig["side"], "entry": sig["entry"], "ts_end_ms": m1[idx]["ts_end_ms"]})
        trades.append(result)
        last_trade_idx = idx
    return trades

# === SWEEP ===
SWEEP = []
# VSA-strict variants: background context + no-supply / no-demand
for retr_win in [10, 15, 20]:
    for tp_r in [2.0, 3.0, 5.0, 7.0]:
        for min_body in [0.50, 0.65, 0.80]:
            for max_vol_ratio in [0.50, 0.70]:    # breakout vol must be ≤ X% of UHV
                for bg_min in [3, 4]:              # need ≥3 (or ≥4) red bars in 5-bar bg window
                    for req_trend in [False, True]:
                        SWEEP.append({
                            "retracement_window": retr_win,
                            "swing_lookback": 15, "swing_strength": 3,
                            "tp_r": tp_r,
                            "min_body_pct": min_body,
                            "max_vol_ratio": max_vol_ratio,
                            "bg_lookback": 5, "bg_min_count": bg_min,
                            "require_structural_trend": req_trend,
                            "use_invalidation": True,
                            "cooldown_bars": 5,
                        })

print(f"[SWEEP] {len(SWEEP)} configs", flush=True)
results = []
import time; t0 = time.time()
for i, p in enumerate(SWEEP):
    trades = backtest(p)
    s = stats(trades); s.update(p); s["trades"] = trades
    results.append(s)
    if (i+1) % 30 == 0: print(f"  {i+1}/{len(SWEEP)} ({time.time()-t0:.0f}s)", flush=True)

ok = [r for r in results if r.get("n", 0) >= 30]
ok.sort(key=lambda r: r["net"], reverse=True)
print(f"\n=== TOP 12 (n>=30, sorted by net) ===", flush=True)
print(f"{'retr':>4} {'tp':>4} {'body':>5} {'volR':>5} {'bg':>3} {'trend':>5} | {'n':>4} {'wr%':>5} {'pf':>5} {'net$':>10} {'dd':>9}", flush=True)
for r in ok[:12]:
    print(f"{r['retracement_window']:>4} {r['tp_r']:>4.1f} {r['min_body_pct']:>5.2f} {r['max_vol_ratio']:>5.2f} {r['bg_min_count']:>3} {str(r['require_structural_trend']):>5} | {r['n']:>4} {r['wr']:>5.1f} {str(r['pf']):>5} {r['net']:>10.2f} {r['max_dd']:>9.2f}", flush=True)

ok_wr = [r for r in results if r.get("n", 0) >= 30]
ok_wr.sort(key=lambda r: r["wr"], reverse=True)
print(f"\n=== TOP 12 by WIN RATE (n>=30) ===", flush=True)
print(f"{'retr':>4} {'tp':>4} {'body':>5} {'volR':>5} {'bg':>3} {'trend':>5} | {'n':>4} {'wr%':>5} {'pf':>5} {'net$':>10} {'dd':>9}", flush=True)
for r in ok_wr[:12]:
    print(f"{r['retracement_window']:>4} {r['tp_r']:>4.1f} {r['min_body_pct']:>5.2f} {r['max_vol_ratio']:>5.2f} {r['bg_min_count']:>3} {str(r['require_structural_trend']):>5} | {r['n']:>4} {r['wr']:>5.1f} {str(r['pf']):>5} {r['net']:>10.2f} {r['max_dd']:>9.2f}", flush=True)

# Train/test split on top 5 by net
print(f"\n=== TRAIN/TEST SPLIT ON TOP 5 BY NET ===", flush=True)
print(f"{'retr':>4} {'tp':>4} {'body':>5} {'volR':>5} {'bg':>3} {'trend':>5} | {'tr_n':>4} {'tr_wr':>5} {'tr_pf':>5} {'tr_net':>9} || {'te_n':>4} {'te_wr':>5} {'te_pf':>5} {'te_net':>9}", flush=True)
train_test = []
for r in ok[:5]:
    trades = r["trades"]
    all_dates = sorted(set(t["date"] for t in trades))
    if not all_dates: continue
    cutoff = all_dates[int(len(all_dates) * 0.75)]
    trn = [t for t in trades if t["date"] < cutoff]
    tst = [t for t in trades if t["date"] >= cutoff]
    s_trn = stats(trn) if trn else {"n":0}
    s_tst = stats(tst) if tst else {"n":0}
    print(f"{r['retracement_window']:>4} {r['tp_r']:>4.1f} {r['min_body_pct']:>5.2f} {r['max_vol_ratio']:>5.2f} {r['bg_min_count']:>3} {str(r['require_structural_trend']):>5} | {s_trn.get('n',0):>4} {s_trn.get('wr',0):>5.1f} {str(s_trn.get('pf')):>5} {s_trn.get('net',0):>9.2f} || {s_tst.get('n',0):>4} {s_tst.get('wr',0):>5.1f} {str(s_tst.get('pf')):>5} {s_tst.get('net',0):>9.2f}", flush=True)
    train_test.append({"config": {k:v for k,v in r.items() if k != "trades"}, "train": s_trn, "test": s_tst})

doc = {"started": datetime.now(timezone.utc).isoformat(),
       "top12_by_net": [{k:v for k,v in r.items() if k != "trades"} for r in ok[:12]],
       "top12_by_wr": [{k:v for k,v in r.items() if k != "trades"} for r in ok_wr[:12]],
       "train_test_top5": train_test}
OUT_J.write_text(json.dumps(doc, indent=2, default=str))
print(f"\n[DONE] -> {OUT_J}", flush=True)
