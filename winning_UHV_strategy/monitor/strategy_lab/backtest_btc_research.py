"""backtest_btc_research.py — find a BTC config that earns this weekend.

Hypothesis from XAU-failure analysis: BTC needs
  1. Higher timeframe (M15/M30/H1 — match BTC's macro structure)
  2. Let-winners-run exits (R:R multiple OR trailing stop) — BTC has momentum
  3. Wider SL (BTC has bigger noise)

Sweep:
  - Timeframes: M5, M15, M30, H1
  - Entries: S1 (UHV BO) and S3 (effort vs result)
  - Exit modes:
      * fixed TP (small/medium/large)
      * R:R multiple (TP = entry + N × SL_distance, N = 1.5, 2, 3, 5)
      * trailing stop (engage after +$X profit, trail by $Y)
  - SL: at UHV.low (S1) or wicking.low (S3), with buffer

Bar-replay (no ticks available) — directional only, no spread modeling.
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

COMMON   = Path(r"C:\Users\zeesh\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
BTC_CSV  = COMMON / "btc_m1.csv"
CONTRACT = 1.0


def load_btc_m1():
    bars = []
    with open(BTC_CSV, encoding="ascii", errors="replace") as f:
        for r in csv.DictReader(f):
            try:
                tm = datetime.strptime(r["time_iso"], "%Y.%m.%d %H:%M:%S")
            except Exception:
                continue
            bars.append({"time": tm, "open": float(r["open"]), "high": float(r["high"]),
                         "low": float(r["low"]), "close": float(r["close"]),
                         "vol": int(r["tick_volume"])})
    bars.sort(key=lambda b: b["time"])
    return bars


def aggregate(m1, k):
    """Aggregate M1 to k-minute bars. k accepts 5, 15, 30, 60."""
    out = {}
    for b in m1:
        ts = b["time"]
        if k < 60:
            bucket_min = (ts.minute // k) * k
            bt = ts.replace(minute=bucket_min, second=0, microsecond=0)
        else:
            hours_per_bar = k // 60
            bucket_hour = (ts.hour // hours_per_bar) * hours_per_bar
            bt = ts.replace(hour=bucket_hour, minute=0, second=0, microsecond=0)
        if bt not in out:
            out[bt] = {"time": bt, "open": b["open"], "high": b["high"],
                       "low": b["low"], "close": b["close"], "vol": b["vol"]}
        else:
            x = out[bt]
            x["high"] = max(x["high"], b["high"])
            x["low"]  = min(x["low"],  b["low"])
            x["close"] = b["close"]
            x["vol"] += b["vol"]
    return sorted(out.values(), key=lambda x: x["time"])


def find_fvgs(bars):
    fvgs = []
    for i in range(2, len(bars)):
        gl, gh = bars[i-2]["high"], bars[i]["low"]
        if gh <= gl: continue
        filled_at = None
        for j in range(i+1, len(bars)):
            if bars[j]["low"] < gl:
                filled_at = bars[j]["time"]; break
        fvgs.append({"t0": bars[i]["time"], "gap_low": gl, "gap_high": gh,
                     "filled_at": filled_at})
    return fvgs


def fvg_tapped_at(fvgs, bar):
    for f in fvgs:
        if f["t0"] >= bar["time"]: continue
        if f["filled_at"] is not None and f["filled_at"] <= bar["time"]: continue
        if bar["low"] <= f["gap_high"] and bar["high"] >= f["gap_low"]:
            return True
    return False


def is_uptrend(bars, idx, lookback, threshold_usd):
    if idx < lookback: return False
    return bars[idx]["close"] - bars[idx-lookback]["close"] > threshold_usd


def find_reds(bars, idx, max_lookback):
    reds = []
    for j in range(idx-1, max(idx - max_lookback - 1, -1), -1):
        b = bars[j]
        if b["close"] >= b["open"]:
            if reds and b["high"] > bars[reds[-1]]["high"]: break
        else:
            reds.append(j)
    return reds


def detect_s1_buy(bars, idx, fvgs, sl_buffer, trend_thresh, trend_lookback):
    bo = bars[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(bars, idx, trend_lookback, trend_thresh): return None
    reds = find_reds(bars, idx, max_lookback=15)
    if not reds: return None
    uhv_idx = max(reds, key=lambda j: bars[j]["vol"])
    uhv = bars[uhv_idx]
    if bo["close"] <= uhv["high"]: return None
    if bo["open"]  >  uhv["high"]: return None
    if not any(bars[j]["low"] < uhv["low"] for j in range(uhv_idx+1, idx+1)): return None
    if not any(fvg_tapped_at(fvgs, bars[j]) for j in reds): return None
    return {"entry": bo["close"], "sl": uhv["low"] - sl_buffer, "ref_t": uhv["time"], "side": +1}


def detect_s3_buy(bars, idx, fvgs, sl_buffer, trend_thresh, trend_lookback):
    bo = bars[idx]
    if bo["close"] <= bo["open"]: return None
    if not is_uptrend(bars, idx, trend_lookback, trend_thresh): return None
    reds = find_reds(bars, idx, max_lookback=15)
    if not reds: return None
    for red_idx in reds:
        red = bars[red_idx]
        if bo["low"] >= red["low"]: continue
        if bo["close"] <= red["low"]: continue
        if bo["vol"] <= red["vol"]: continue
        if not any(fvg_tapped_at(fvgs, bars[j]) for j in reds): continue
        return {"entry": bo["close"], "sl": bo["low"] - sl_buffer, "ref_t": red["time"], "side": +1}
    return None


def detect_signals(bars, fvgs, detector_fn, sl_buffer, trend_thresh, trend_lookback, tf_minutes):
    sigs = []
    fired = set()
    for idx in range(30, len(bars)):
        r = detector_fn(bars, idx, fvgs, sl_buffer, trend_thresh, trend_lookback)
        if r is None: continue
        if r["ref_t"] in fired: continue
        fired.add(r["ref_t"])
        r["fire_time"] = bars[idx]["time"] + timedelta(minutes=tf_minutes)
        sigs.append(r)
    return sigs


# ─── Exit modes ───
def replay_fixed(m1, sigs, tp_pts, lots):
    return _replay(m1, sigs, lots, mode="fixed", tp_pts=tp_pts)


def replay_rr(m1, sigs, rr_multiple, lots):
    return _replay(m1, sigs, lots, mode="rr", rr=rr_multiple)


def replay_trail(m1, sigs, trail_after_pts, trail_dist_pts, lots, max_tp_pts=None):
    return _replay(m1, sigs, lots, mode="trail",
                   trail_after=trail_after_pts, trail_dist=trail_dist_pts,
                   max_tp=max_tp_pts)


def _replay(m1, sigs, lots, mode, **kw):
    ppp = lots * CONTRACT
    done = []
    for s in sorted(sigs, key=lambda x: x["fire_time"]):
        entry_idx = next((i for i, b in enumerate(m1) if b["time"] >= s["fire_time"]), None)
        if entry_idx is None or entry_idx + 1 >= len(m1): continue
        e  = m1[entry_idx]["open"]
        sl = s["sl"]
        sl_dist = e - sl   # BUY side; positive
        if sl_dist <= 0: continue
        # Compute initial TP based on mode
        if mode == "fixed":
            tp = e + kw["tp_pts"]
        elif mode == "rr":
            tp = e + kw["rr"] * sl_dist
        elif mode == "trail":
            tp = e + (kw["max_tp"] or 999999.0)  # max cap
        peak = e
        cur_sl = sl
        why = None
        pnl = 0
        for j in range(entry_idx + 1, len(m1)):
            b = m1[j]
            # Update peak (BUY)
            if b["high"] > peak: peak = b["high"]
            # Engage trailing if mode == trail
            if mode == "trail" and (peak - e) >= kw["trail_after"]:
                trail_sl = peak - kw["trail_dist"]
                if trail_sl > cur_sl: cur_sl = trail_sl
            # Check SL first (conservative — assume the bar visited low before high if either could trigger)
            if b["low"] <= cur_sl:
                pnl = (cur_sl - e) * ppp
                why = "sl" if cur_sl == sl else "trail_sl"
                break
            if b["high"] >= tp:
                pnl = (tp - e) * ppp
                why = "tp"
                break
        if why is None:
            last = m1[-1]
            pnl = (last["close"] - e) * ppp
            why = "eod"
        done.append({"setup": s.get("setup", ""), "pnl": pnl, "why": why,
                     "e": e, "sl_final": cur_sl, "fire_time": s["fire_time"]})
    return done


def stats(trades, lots, multiplier=40):
    n = len(trades)
    if n == 0: return None
    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [t["pnl"] for t in trades if t["pnl"] < 0]
    n_w, n_l = len(wins), len(losses)
    pwin = n_w/(n_w+n_l) if (n_w+n_l) else 0
    w_avg = sum(wins)/n_w if n_w else 0
    l_avg = -sum(losses)/n_l if n_l else 0
    total = sum(t["pnl"] for t in trades)
    return dict(n=n, pwin=pwin, w_avg=w_avg, l_avg=l_avg, total=total,
                proj=total*multiplier)


def fmt(r):
    if r is None: return "no trades"
    return (f"n={r['n']:>3}  pwin={r['pwin']:.2f}  "
            f"W=${r['w_avg']:>6.1f}  L=${r['l_avg']:>6.1f}  "
            f"TOTAL=${r['total']:>+8.1f}  proj@0.40=${r['proj']:>+9.1f}")


def main():
    print("Loading BTC M1 bars...")
    m1 = load_btc_m1()
    days = (m1[-1]["time"] - m1[0]["time"]).total_seconds() / 86400
    print(f"  {len(m1)} M1 bars, span {days:.1f} days, price ${min(b['low'] for b in m1):.0f}-${max(b['high'] for b in m1):.0f}\n")

    # H1 FVGs (computed ONCE — same H1 FVGs used across all execution timeframes)
    h1 = aggregate(m1, 60)
    h1_fvgs = find_fvgs(h1)
    print(f"H1: {len(h1)} bars, {len(h1_fvgs)} bullish FVGs\n")

    LOTS = 0.01
    MULTI = 40    # report at 0.40 BTC

    # Per-timeframe configs (tuned for BTC's scale on each TF)
    tf_configs = {
        "M5":  {"trend_thresh": 100.0, "trend_lookback": 24, "sl_buffers": [10, 50]},
        "M15": {"trend_thresh": 200.0, "trend_lookback": 16, "sl_buffers": [25, 100]},
        "M30": {"trend_thresh": 300.0, "trend_lookback": 12, "sl_buffers": [50, 200]},
        "H1":  {"trend_thresh": 500.0, "trend_lookback": 12, "sl_buffers": [100, 400]},
    }

    BEST = []   # (total, label, info)

    for tf_name, tf_cfg in tf_configs.items():
        k_minutes = {"M5":5, "M15":15, "M30":30, "H1":60}[tf_name]
        bars = aggregate(m1, k_minutes)
        if len(bars) < 50: continue
        print(f"========== EXEC TIMEFRAME: {tf_name} ({len(bars)} bars) ==========")

        for setup_name, detector in [("S1", detect_s1_buy), ("S3", detect_s3_buy)]:
            for sl_buf in tf_cfg["sl_buffers"]:
                sigs = detect_signals(bars, h1_fvgs, detector, sl_buf,
                                      tf_cfg["trend_thresh"], tf_cfg["trend_lookback"],
                                      k_minutes)
                if not sigs:
                    continue

                # Exit mode: R:R multiples
                for rr in [1.5, 2.0, 3.0, 5.0]:
                    trades = replay_rr(m1, sigs, rr, LOTS)
                    r = stats(trades, LOTS, MULTI)
                    label = f"  {setup_name}  SLbuf=${sl_buf:>3}  RR={rr:>3.1f}        "
                    print(f"{label}{fmt(r)}")
                    if r and r["total"] > 0:
                        BEST.append((r["total"], f"{tf_name} {setup_name} SLbuf=${sl_buf} RR={rr}", r))

                # Exit mode: Trailing
                for trail_after in [100, 200, 500]:
                    for trail_dist in [50, 100, 200]:
                        if trail_dist >= trail_after: continue
                        trades = replay_trail(m1, sigs, trail_after, trail_dist, LOTS)
                        r = stats(trades, LOTS, MULTI)
                        label = f"  {setup_name}  SLbuf=${sl_buf:>3}  TRAIL@${trail_after:>3}/${trail_dist:>3} "
                        print(f"{label}{fmt(r)}")
                        if r and r["total"] > 0:
                            BEST.append((r["total"], f"{tf_name} {setup_name} SLbuf=${sl_buf} TRAIL@${trail_after}/${trail_dist}", r))

                # Exit mode: Fixed TPs
                for tp in [200, 500, 1000, 2000]:
                    trades = replay_fixed(m1, sigs, tp, LOTS)
                    r = stats(trades, LOTS, MULTI)
                    label = f"  {setup_name}  SLbuf=${sl_buf:>3}  FIXED TP=${tp:>4}    "
                    print(f"{label}{fmt(r)}")
                    if r and r["total"] > 0:
                        BEST.append((r["total"], f"{tf_name} {setup_name} SLbuf=${sl_buf} FIXED@${tp}", r))
        print()

    print("\n" + "="*80)
    print("PROFITABLE CONFIGS (sorted best to worst):")
    print("="*80)
    BEST.sort(key=lambda x: -x[0])
    for total, label, r in BEST[:20]:
        print(f"  {label:<50}  {fmt(r)}")


if __name__ == "__main__":
    main()
